"""Thin, stateless render adapter for teaser clips (Phase 3.5).

Turns the structured shot prompts into actual media via a **free, no-key**
backend (Pollinations by default — image keyframes are the rock-solid
free path; `--kind video` targets Pollinations' experimental video URL).

BRIGHT LINES (PRD §23.2 — keep this adapter thin on purpose):
  - clips land on **disk only**; NO state file, NO database, NO manifest
    the rest of the pipeline depends on. Re-running just re-downloads.
  - **NO auto-assembly** — this stops at per-shot media files; stitching
    them is Phase 3 (ffmpeg).
  - **free default backend**; `--dry-run` builds the full request plan
    (the exact URLs) without spending a byte of bandwidth.

This module does HTTP (the same way `export/wikimedia` does, via an
injectable httpx client seam so tests never hit the network) but **never
calls an LLM**. The clip critique (KEEP / REGENERATE / UPGRADE-TO-PAID)
is the vision-LLM step in the `/autonovel:teaser-render` command body —
quality is judged there, not here (feedback_avoid_brittle_python).
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from . import providers, render_prompt
from .shots import Shot, Teaser

POLLINATIONS_IMAGE = "https://image.pollinations.ai/prompt/"
# Experimental free video endpoint; image keyframes are the reliable path.
POLLINATIONS_VIDEO = "https://video.pollinations.ai/prompt/"

USER_AGENT = "autonovel/0.2 (https://github.com/pmilford/autonovel; teaser render)"

_EXT = {"image": "png", "video": "mp4"}
_DEFAULT_HEIGHT = 480  # 480p dev default — watermarks + low res are fine for dev passes.


@dataclass
class RenderRequest:
    shot_id: str
    kind: str            # "image" | "video"
    url: str
    out_path: str
    prompt: str
    seed: int
    width: int
    height: int
    take: int = 1
    provider: str = "pollinations"
    duration_s: float = 5.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "shot_id": self.shot_id, "kind": self.kind, "url": self.url,
            "out_path": self.out_path, "prompt": self.prompt, "seed": self.seed,
            "width": self.width, "height": self.height, "take": self.take,
            "provider": self.provider, "duration_s": self.duration_s,
        }


@dataclass
class RenderResult:
    shot_id: str
    out_path: str
    ok: bool
    bytes: int = 0
    take: int = 1
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "shot_id": self.shot_id, "out_path": self.out_path, "ok": self.ok,
            "bytes": self.bytes, "take": self.take, "error": self.error,
        }


def aspect_to_size(aspect_ratio: str, height: int = _DEFAULT_HEIGHT) -> tuple[int, int]:
    """Derive (width, height) from an ``W:H`` aspect string at a given
    height. Falls back to 16:9 on a malformed ratio. Widths are rounded
    to an even number (encoder-friendly)."""
    try:
        w, h = aspect_ratio.split(":")
        ratio = float(w) / float(h)
    except Exception:  # noqa: BLE001
        ratio = 16 / 9
    width = int(round(height * ratio))
    if width % 2:
        width += 1
    return width, height


def _seed_for(shot: Shot, take: int) -> int:
    """Deterministic per-(shot, take) seed: reproducible across runs, but
    each take differs. Honour an explicit ``shot.seed`` for take 1."""
    if shot.seed is not None and take == 1:
        return int(shot.seed)
    return zlib.crc32(f"{shot.id}:{take}".encode("utf-8"))


def build_request(
    shot: Shot,
    *,
    provider: str = "pollinations",
    kind: str = "image",
    out_dir: Path,
    width: int | None = None,
    height: int = _DEFAULT_HEIGHT,
    take: int = 1,
    model: str | None = None,
) -> RenderRequest:
    """Build the deterministic download request for one shot/take."""
    prompt = render_prompt.render_visual(shot, provider)
    if width is None:
        width, height = aspect_to_size(shot.aspect_ratio, height)
    seed = _seed_for(shot, take)
    # Pollinations is a plain GET (URL carries everything). The async
    # backends (grok/kie/veo/magichour/fal) build their own POST bodies
    # at render time — the request only needs the prompt + dims, so the
    # `url` field is a human-readable note for the dry-run plan.
    if provider == "pollinations":
        params: dict[str, Any] = {"width": width, "height": height, "seed": seed}
        if model:
            params["model"] = model
        base = POLLINATIONS_VIDEO if kind == "video" else POLLINATIONS_IMAGE
        url = base + quote(prompt, safe="") + "?" + urlencode(params)
    else:
        url = f"{provider}:async (POST at render time)"
    ext = _EXT.get(kind, "png")
    suffix = f"_take{take}" if take > 1 else ""
    out_path = Path(out_dir) / f"shot_{shot.id}{suffix}.{ext}"
    return RenderRequest(
        shot_id=shot.id, kind=kind, url=url, out_path=str(out_path),
        prompt=prompt, seed=seed, width=width, height=height, take=take,
        provider=provider, duration_s=float(getattr(shot, "duration_s", 5.0) or 5.0),
    )


def plan(
    teaser: Teaser,
    *,
    provider: str = "pollinations",
    kind: str = "image",
    out_dir: Path,
    width: int | None = None,
    height: int = _DEFAULT_HEIGHT,
    takes: int = 1,
    model: str | None = None,
    only_shot: str | None = None,
) -> list[RenderRequest]:
    """Build the request plan for every shot (× ``takes``). Pure — no I/O."""
    reqs: list[RenderRequest] = []
    for s in teaser.shots:
        if only_shot is not None and s.id != only_shot:
            continue
        for t in range(1, max(1, takes) + 1):
            reqs.append(build_request(
                s, provider=provider, kind=kind, out_dir=out_dir,
                width=width, height=height, take=t, model=model,
            ))
    return reqs


def _get_bytes(url: str, *, client=None, key: str | None = None) -> bytes:
    """Single GET, httpx client seam for tests (mirrors export/wikimedia).

    Pollinations now needs a free account token (Bearer) and returns
    **402** when the (gated) tier is hit — surface that as a typed
    ``RenderError`` so the command can print one actionable message
    instead of N identical failures.
    """
    import httpx
    from .backends import RenderError
    headers = {"User-Agent": USER_AGENT}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if client is None:
        with httpx.Client(timeout=180, follow_redirects=True) as c:
            r = c.get(url, headers=headers)
    else:
        r = client.get(url, headers=headers)
    status = getattr(r, "status_code", None)
    if status == 402:
        raise RenderError(
            "402 Payment Required from Pollinations — anonymous/free image "
            "generation is gated. Set a free account token "
            "(POLLINATIONS_TOKEN, get one at https://auth.pollinations.ai) "
            "or render video with --provider grok.",
            kind="payment",
        )
    if status in (401, 403):
        raise RenderError(
            f"{status} from Pollinations — set a valid POLLINATIONS_TOKEN "
            "(https://auth.pollinations.ai).",
            kind="auth",
        )
    r.raise_for_status()
    return r.content


def render(
    requests: list[RenderRequest],
    *,
    client=None,
    token: str | None = None,
    delay: float | None = None,
    max_retries: int = 4,
    sleep=None,
) -> list[RenderResult]:
    """Download each request to disk. Errors are isolated per request —
    one failed clip never aborts the batch (the command re-runs failures).

    Routing: ``pollinations`` is a plain GET (free flux keyframes, now
    needs a token); every other provider is an async create→poll→download
    backend in ``backends.py``. Requests are paced ≥ the provider's
    ``min_interval_s`` apart (or ``delay`` if given) with 429/503 backoff.

    A terminal **402/auth** error short-circuits the rest of the batch
    (re-trying 35 times with the same missing key is pointless) — the
    command surfaces the one actionable message.
    """
    from . import providers as _prov
    from . import backends as _be

    results: list[RenderResult] = []
    if not requests:
        return results

    provider = requests[0].provider or "pollinations"
    prof = _prov.get(provider)

    # Offline stub: synthesize placeholder keyframes locally — no network,
    # no key, no quota. The free way to validate the pipeline end-to-end
    # before spending a real backend's limited free generations.
    if provider == "stub":
        for req in requests:
            out = Path(req.out_path)
            try:
                content = _be.make_stub(req)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(content)
                results.append(RenderResult(
                    shot_id=req.shot_id, out_path=req.out_path, ok=True,
                    bytes=len(content), take=req.take,
                ))
            except Exception as exc:  # noqa: BLE001
                results.append(RenderResult(
                    shot_id=req.shot_id, out_path=req.out_path, ok=False,
                    take=req.take, error=str(exc),
                ))
        return results
    min_interval = delay if delay is not None else prof.min_interval_s
    limiter = _be.RateLimiter(
        min_interval=min_interval, max_retries=max_retries, sleep=sleep,
    )
    key = _be.resolve_key(provider, token=token)

    # Manual backends (Flow) never make HTTP calls.
    if _be.is_manual(provider):
        for req in requests:
            results.append(RenderResult(
                shot_id=req.shot_id, out_path=req.out_path, ok=False,
                take=req.take,
                error=f"{provider} is a manual backend — render in the GUI "
                      f"and drop the MP4 at {req.out_path}.",
            ))
        return results

    # Keyed backends with no key resolved: fail fast with guidance.
    if provider != "pollinations" and prof.needs_key and not key:
        help_ = _be.KEY_HELP.get(provider, "set the provider API key")
        for req in requests:
            results.append(RenderResult(
                shot_id=req.shot_id, out_path=req.out_path, ok=False,
                take=req.take,
                error=f"no API key for {provider} — {help_}.",
            ))
        return results

    net = _be.Net(client=client, limiter=limiter, user_agent=USER_AGENT)
    try:
        for req in requests:
            out = Path(req.out_path)
            try:
                if provider == "pollinations":
                    content = _get_bytes(req.url, client=client, key=key)
                else:
                    content = _be.render_one(req, provider=provider, key=key, net=net)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(content)
                results.append(RenderResult(
                    shot_id=req.shot_id, out_path=req.out_path, ok=True,
                    bytes=len(content), take=req.take,
                ))
            except _be.RenderError as exc:
                results.append(RenderResult(
                    shot_id=req.shot_id, out_path=req.out_path, ok=False,
                    take=req.take, error=str(exc),
                ))
                # A missing-key / payment wall hits every request the same
                # way — stop the batch instead of repeating it N times.
                if exc.kind in ("payment", "auth"):
                    break
            except Exception as exc:  # noqa: BLE001
                results.append(RenderResult(
                    shot_id=req.shot_id, out_path=req.out_path, ok=False,
                    take=req.take, error=str(exc),
                ))
    finally:
        net.close()
    return results
