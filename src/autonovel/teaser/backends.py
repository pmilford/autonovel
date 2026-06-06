"""Render backends for teaser clips (Phase 4: real free video backends).

Pollinations' free no-key promise is dead (every generate endpoint now
needs a Bearer key; video models cost real money). This module adds the
*actual* free/cheap, scriptable backends researched 2026-06-06 (see
``docs/teaser-render-providers.md``):

  - ``grok``      xAI Grok Imagine — DEFAULT. Native dialogue+music, 5
                  free gens/day + $25 signup, no card. Async create→poll→get.
  - ``kie``       kie.ai reseller — one key fronts Veo3/Kling2.6/Grok/
                  Seedance (all with audio); 80 free credits, no card.
  - ``veo``       Veo via the Gemini API (predictLongRunning). Native
                  audio. (The $300-GCP-credit path is Vertex/ADC — manual;
                  see the docs. This adapter drives the API-key path.)
  - ``magichour`` Magic Hour — recurring free (100/day), no card, SILENT
                  (layer an audio bed in teaser-assemble).
  - ``fal``       fal.ai — $20 one-time credit, no card.
  - ``flow``      Google Flow (AI Pro) — GUI-only, NO API. Handled as a
                  *manual* backend (instructions + watch the clips dir);
                  never an HTTP call.

Design discipline (same as the rest of the teaser pipeline):
  - **No LLM here.** This is mechanical HTTP only; the KEEP/REGENERATE/
    UPGRADE clip critique is the vision-LLM step in the command body
    (feedback_avoid_brittle_python).
  - **httpx client seam.** Every network call goes through an injectable
    client so tests never hit the network (mirrors export/wikimedia and
    the Pollinations path in ``render.py``).
  - **Capabilities are data** (``providers.py``), not branches here.

Each backend is a function ``render_one(req, *, key, net) -> bytes`` that
returns the raw clip bytes (MP4/PNG). ``render.py`` writes them to disk.
"""

from __future__ import annotations

import json as _json
import os
import time
from pathlib import Path
from typing import Any, Callable

# Provider → ordered env-var names to look up the key/token under.
ENV_VARS: dict[str, tuple[str, ...]] = {
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "grok": ("XAI_API_KEY", "GROK_API_KEY"),
    "kie": ("KIE_API_KEY",),
    "veo": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "magichour": ("MAGICHOUR_API_KEY", "MAGIC_HOUR_API_KEY"),
    "fal": ("FAL_KEY", "FAL_API_KEY"),
    "pollinations": ("POLLINATIONS_TOKEN", "POLLINATIONS_API_KEY"),
}

# Where to point a user who is missing a key (free signup).
KEY_HELP: dict[str, str] = {
    "gemini": "Gemini API key at https://aistudio.google.com/apikey "
              "(GEMINI_API_KEY; free tier available, image gen ~$0.04/img)",
    "grok": "free key at https://x.ai (5 gens/day + $25 signup, no card)",
    "kie": "free key at https://kie.ai (80 credits, no card)",
    "veo": "Gemini API key at https://aistudio.google.com/apikey (paid; "
           "the $300 GCP credit needs the Vertex path — see the docs)",
    "magichour": "free key at https://magichour.ai (100 credits/day, no card)",
    "fal": "key at https://fal.ai ($20 one-time signup credit, no card)",
    "pollinations": "free account token at https://auth.pollinations.ai",
}


class RenderError(Exception):
    """A backend failure with a machine-readable ``kind``.

    kinds: ``auth`` (401/403/missing key), ``payment`` (402 — needs a
    paid/funded account), ``rate`` (429 after retries), ``timeout``
    (job never finished), ``http`` (other status), ``backend`` (job
    reported failure), ``unsupported`` (e.g. flow / wrong kind).
    """

    def __init__(self, message: str, *, kind: str = "http") -> None:
        super().__init__(message)
        self.kind = kind


# --------------------------------------------------------------------------
# Key resolution (explicit flag → env → .env), with a one-time dotenv load.
# --------------------------------------------------------------------------

_DOTENV_LOADED = False


def _load_dotenv_once() -> None:
    """Best-effort: load a project-local ``.env`` so keys placed there by
    the user (``autonovel`` convention) reach ``os.environ``. Idempotent
    and never fatal — a missing python-dotenv or .env is fine."""
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    try:
        from dotenv import load_dotenv, find_dotenv
        load_dotenv(find_dotenv(usecwd=True), override=False)
    except Exception:  # noqa: BLE001
        pass


def resolve_key(provider: str, *, token: str | None = None) -> str | None:
    """Resolve a provider key: explicit ``token`` wins, else the first
    set env var (after loading ``.env``). Returns None when none found."""
    if token:
        return token
    _load_dotenv_once()
    for name in ENV_VARS.get(provider, ()):  # noqa: SIM110
        val = os.environ.get(name)
        if val:
            return val
    return None


# --------------------------------------------------------------------------
# Rate limiting + retry/backoff (keyed off providers.py min_interval_s).
# --------------------------------------------------------------------------


class RateLimiter:
    """Spaces calls ≥ ``min_interval`` apart and retries transient HTTP
    (429/503), honouring ``Retry-After`` with bounded exponential
    backoff. ``sleep``/``monotonic`` are injectable so tests are instant.
    """

    def __init__(
        self,
        *,
        min_interval: float = 0.0,
        max_retries: int = 4,
        base_backoff: float = 2.0,
        max_backoff: float = 60.0,
        sleep: Callable[[float], None] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self.min_interval = max(0.0, min_interval)
        self.max_retries = max(0, max_retries)
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self._sleep = sleep or time.sleep
        self._mono = monotonic or time.monotonic
        self._last: float | None = None

    def pace(self) -> None:
        """Block until at least ``min_interval`` has elapsed since the
        previous paced call."""
        if self.min_interval <= 0:
            self._last = self._mono()
            return
        now = self._mono()
        if self._last is not None:
            wait = self.min_interval - (now - self._last)
            if wait > 0:
                self._sleep(wait)
        self._last = self._mono()

    def backoff(self, attempt: int, *, retry_after: float | None = None) -> None:
        """Sleep before retry ``attempt`` (1-based). Honours an explicit
        ``Retry-After`` (seconds), else exponential backoff."""
        if retry_after is not None and retry_after >= 0:
            delay = min(retry_after, self.max_backoff)
        else:
            delay = min(self.base_backoff ** attempt, self.max_backoff)
        self._sleep(delay)


# --------------------------------------------------------------------------
# Thin HTTP wrapper over the injectable client (httpx-compatible).
# --------------------------------------------------------------------------


def _retry_after_seconds(headers: Any) -> float | None:
    try:
        raw = headers.get("Retry-After") or headers.get("retry-after")
    except Exception:  # noqa: BLE001
        return None
    if not raw:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


class Net:
    """Auth-aware HTTP with rate-limit pacing + transient retry.

    Built on an injected httpx-like client (``.get``/``.post`` returning
    objects with ``.status_code``, ``.headers``, ``.json()``, ``.content``).
    When no client is injected one real ``httpx.Client`` is opened for the
    batch and closed by ``close()``.
    """

    def __init__(
        self,
        *,
        client: Any = None,
        limiter: RateLimiter | None = None,
        user_agent: str = "autonovel/0.2 (teaser render)",
    ) -> None:
        self._client = client
        self._owns = False
        self.limiter = limiter or RateLimiter()
        self.user_agent = user_agent

    def _ensure(self) -> Any:
        if self._client is None:
            import httpx
            self._client = httpx.Client(timeout=180, follow_redirects=True)
            self._owns = True
        return self._client

    def close(self) -> None:
        if self._owns and self._client is not None:
            try:
                self._client.close()
            except Exception:  # noqa: BLE001
                pass
            self._client = None
            self._owns = False

    def __enter__(self) -> "Net":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: Any = None,
        paced: bool = True,
    ) -> Any:
        """One request with pacing + retry on 429/503. Raises
        ``RenderError`` (typed) on auth/payment/other terminal status."""
        client = self._ensure()
        hdrs = {"User-Agent": self.user_agent}
        if headers:
            hdrs.update(headers)
        attempt = 0
        while True:
            if paced:
                self.limiter.pace()
            if method.upper() == "POST":
                resp = client.post(url, headers=hdrs, json=json)
            else:
                resp = client.get(url, headers=hdrs)
            status = getattr(resp, "status_code", None)
            # Fake clients in tests may omit status_code: fall back to
            # raise_for_status() and treat as success.
            if status is None:
                if hasattr(resp, "raise_for_status"):
                    resp.raise_for_status()
                return resp
            if status in (429, 503) and attempt < self.limiter.max_retries:
                attempt += 1
                self.limiter.backoff(
                    attempt, retry_after=_retry_after_seconds(getattr(resp, "headers", {})),
                )
                continue
            if status == 402:
                raise RenderError(
                    f"402 Payment Required from {url} — the free/anonymous "
                    f"tier is gated; this account needs funding/a paid tier.",
                    kind="payment",
                )
            if status in (401, 403):
                raise RenderError(
                    f"{status} from {url} — bad or missing API key.",
                    kind="auth",
                )
            if status == 429:
                raise RenderError(f"429 Too Many Requests from {url} (retries exhausted).",
                                  kind="rate")
            if status >= 400:
                raise RenderError(f"HTTP {status} from {url}: {_body_snippet(resp)}",
                                  kind="http")
            return resp

    def get_json(self, url: str, **kw: Any) -> Any:
        return self.request("GET", url, **kw).json()

    def post_json(self, url: str, **kw: Any) -> Any:
        return self.request("POST", url, **kw).json()

    def get_bytes(self, url: str, **kw: Any) -> bytes:
        return self.request("GET", url, **kw).content


def _body_snippet(resp: Any, limit: int = 300) -> str:
    try:
        txt = getattr(resp, "text", None)
        if txt is None:
            txt = resp.content.decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return "<unreadable body>"
    txt = " ".join(txt.split())
    return txt[:limit]


def _dig(obj: Any, *path: Any, default: Any = None) -> Any:
    """Walk dict keys / list indices; return ``default`` on any miss."""
    cur = obj
    for key in path:
        try:
            cur = cur[key]
        except (KeyError, IndexError, TypeError):
            return default
    return cur


def _poll(
    fetch: Callable[[], Any],
    *,
    done: Callable[[Any], bool],
    failed: Callable[[Any], str | None],
    result: Callable[[Any], str | None],
    limiter: RateLimiter,
    max_polls: int = 60,
) -> str:
    """Poll a long-running job to completion; return the result media URL.

    ``fetch`` returns the latest status JSON. ``done``/``failed``/
    ``result`` interpret it. Spacing between polls reuses the limiter's
    ``min_interval`` (min 1s) so we don't hammer the status endpoint.
    """
    poll_gap = max(1.0, limiter.min_interval)
    for _ in range(max_polls):
        status = fetch()
        err = failed(status)
        if err:
            raise RenderError(f"backend reported failure: {err}", kind="backend")
        if done(status):
            url = result(status)
            if not url:
                raise RenderError("job done but no result URL in response.", kind="backend")
            return url
        limiter._sleep(poll_gap)  # noqa: SLF001 — intentional shared sleep seam
    raise RenderError(f"job did not finish after {max_polls} polls.", kind="timeout")


# --------------------------------------------------------------------------
# Per-provider backends. Each: render_one(req, *, key, net) -> bytes.
# `req` is a render.RenderRequest (duck-typed: .prompt .seed .width
# .height .kind .shot_id .take). Audio is steered through the prompt.
# --------------------------------------------------------------------------


def _grok(req: Any, *, key: str, net: Net) -> bytes:
    """xAI Grok Imagine video — async create → poll → download.

    Ref: https://docs.x.ai/developers/models/grok-imagine-video
      POST  https://api.x.ai/v1/videos/generations  (Bearer)
      GET   https://api.x.ai/v1/videos/{request_id}
    Native dialogue+music: put dialogue in quotes in the prompt.
    """
    auth = {"Authorization": f"Bearer {key}"}
    duration = _clip_seconds(req, cap=15, default=8)
    body = {
        "model": getattr(req, "model", None) or "grok-imagine-video",
        "prompt": req.prompt,
        "duration": duration,
    }
    # Image-to-video: animate from the shot's keyframe (Phase 5.3).
    init = _init_image(req, net=net)
    if init:
        mime, b64 = init
        body["image"] = f"data:{mime};base64,{b64}"
    created = net.post_json("https://api.x.ai/v1/videos/generations",
                            headers=auth, json=body)
    rid = _dig(created, "request_id") or _dig(created, "id")
    if not rid:
        # Some responses return the finished video synchronously.
        url = _dig(created, "video", "url") or _dig(created, "url")
        if url:
            return net.get_bytes(url)
        raise RenderError(f"grok: no request_id in response: {created}", kind="backend")

    def fetch() -> Any:
        return net.get_json(f"https://api.x.ai/v1/videos/{rid}", headers=auth)

    url = _poll(
        fetch,
        done=lambda s: str(_dig(s, "status")).lower() in ("done", "succeeded", "completed"),
        failed=lambda s: (str(_dig(s, "status")).lower() == "failed")
                          and (_dig(s, "error") or "generation failed") or None,
        result=lambda s: _dig(s, "video", "url") or _dig(s, "url"),
        limiter=net.limiter,
    )
    return net.get_bytes(url)


def _kie(req: Any, *, key: str, net: Net) -> bytes:
    """kie.ai unified jobs API — fronts many audio models.

    Ref: https://docs.kie.ai/market/quickstart
      POST  https://api.kie.ai/api/v1/jobs/createTask  (Bearer)
      GET   https://api.kie.ai/api/v1/jobs/recordInfo?taskId=...
    Model chosen via --model (default a cheap Veo-3-fast with audio).
    """
    auth = {"Authorization": f"Bearer {key}"}
    model = getattr(req, "model", None) or "veo3-fast"
    body = {
        "model": model,
        "input": {
            "prompt": req.prompt,
            "aspect_ratio": _aspect(req),
            "duration": _clip_seconds(req, cap=10, default=8),
        },
    }
    # Image-to-video start frame (Phase 5.3).
    init = _init_image(req, net=net)
    if init:
        mime, b64 = init
        body["input"]["image_url"] = f"data:{mime};base64,{b64}"
    created = net.post_json("https://api.kie.ai/api/v1/jobs/createTask",
                            headers=auth, json=body)
    task_id = _dig(created, "data", "taskId") or _dig(created, "taskId") or _dig(created, "data", "task_id")
    if not task_id:
        raise RenderError(f"kie: no taskId in response: {created}", kind="backend")

    def fetch() -> Any:
        return net.get_json(
            f"https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}", headers=auth)

    def _state(s: Any) -> str:
        return str(_dig(s, "data", "state") or _dig(s, "data", "status") or "").lower()

    url = _poll(
        fetch,
        done=lambda s: _state(s) in ("success", "completed", "done"),
        failed=lambda s: (_state(s) in ("fail", "failed", "error"))
                          and (_dig(s, "data", "failMsg") or "task failed") or None,
        result=lambda s: _kie_result_url(s),
        limiter=net.limiter,
    )
    return net.get_bytes(url)


def _kie_result_url(s: Any) -> str | None:
    # kie wraps results variously; resultJson is often a JSON string.
    rj = _dig(s, "data", "resultJson")
    if isinstance(rj, str):
        try:
            rj = _json.loads(rj)
        except ValueError:
            rj = None
    for cand in (
        _dig(rj, "resultUrls", 0) if rj else None,
        _dig(rj, "videoUrl") if rj else None,
        _dig(s, "data", "resultUrls", 0),
        _dig(s, "data", "videoUrl"),
        _dig(s, "data", "result", "url"),
    ):
        if cand:
            return cand
    return None


def _veo(req: Any, *, key: str, net: Net) -> bytes:
    """Veo via the Gemini API (API-key path; predictLongRunning).

    Ref: https://ai.google.dev/gemini-api/docs/video
      POST {base}/models/{model}:predictLongRunning   (x-goog-api-key)
      GET  {base}/{operation.name}
    Native audio is on by default — steer it via the prompt. NOTE: the
    $300 GCP credit only applies to the *Vertex* path (ADC), not this
    API-key path — see docs/teaser-render-providers.md.
    """
    base = "https://generativelanguage.googleapis.com/v1beta"
    auth = {"x-goog-api-key": key}
    model = getattr(req, "model", None) or "veo-3.1-fast-generate-preview"
    instance: dict[str, Any] = {"prompt": req.prompt}
    # Image-to-video: seed the first frame with the shot's keyframe (5.3).
    init = _init_image(req, net=net)
    if init:
        mime, b64 = init
        instance["image"] = {"bytesBase64Encoded": b64, "mimeType": mime}
    body = {
        "instances": [instance],
        "parameters": {
            "aspectRatio": _aspect(req),
            # Veo's API requires a NUMBER here — a string yields HTTP 400
            # (verified live 2026-06-06). Keep it an int.
            "durationSeconds": _clip_seconds(req, cap=8, default=8),
        },
    }
    created = net.post_json(f"{base}/models/{model}:predictLongRunning",
                            headers=auth, json=body)
    op = _dig(created, "name")
    if not op:
        raise RenderError(f"veo: no operation name in response: {created}", kind="backend")

    def fetch() -> Any:
        return net.get_json(f"{base}/{op}", headers=auth)

    status = _poll(
        fetch,
        done=lambda s: bool(_dig(s, "done")),
        failed=lambda s: _dig(s, "error", "message"),
        result=lambda s: _dig(s, "response", "generateVideoResponse",
                              "generatedSamples", 0, "video", "uri"),
        limiter=net.limiter,
    )
    # The file URI needs the same API key to download.
    return net.get_bytes(status, headers=auth)


def _magichour(req: Any, *, key: str, net: Net) -> bytes:
    """Magic Hour text-to-video — async, SILENT output.

    Ref: https://docs.magichour.ai/api-reference/video-projects/text-to-video
      POST https://api.magichour.ai/v1/text-to-video      (Bearer)
      GET  https://api.magichour.ai/v1/video-projects/{id}
    """
    auth = {"Authorization": f"Bearer {key}"}
    body = {
        "end_seconds": _clip_seconds(req, cap=10, default=5),
        "aspect_ratio": _aspect(req),
        "resolution": "720p",
        "style": {"prompt": req.prompt},
    }
    created = net.post_json("https://api.magichour.ai/v1/text-to-video",
                            headers=auth, json=body)
    pid = _dig(created, "id")
    if not pid:
        raise RenderError(f"magichour: no project id in response: {created}", kind="backend")

    def fetch() -> Any:
        return net.get_json(f"https://api.magichour.ai/v1/video-projects/{pid}", headers=auth)

    url = _poll(
        fetch,
        done=lambda s: str(_dig(s, "status")).lower() in ("complete", "completed"),
        failed=lambda s: (str(_dig(s, "status")).lower() in ("error", "failed"))
                          and (_dig(s, "error") or "render failed") or None,
        result=lambda s: _dig(s, "downloads", 0, "url"),
        limiter=net.limiter,
    )
    return net.get_bytes(url)


def _fal(req: Any, *, key: str, net: Net) -> bytes:
    """fal.ai queue API — model chosen via --model.

    Ref: https://docs.fal.ai/  (queue: submit → status → response)
      POST https://queue.fal.run/{model}                 (Key <key>)
      GET  {status_url}  →  GET {response_url}

    For ``--kind image`` with a reference plate this defaults to FLUX.1
    Kontext (reference-conditioned editing); the plate is passed as an
    ``image_url`` data-URI so a character's identity carries into the shot.
    """
    auth = {"Authorization": f"Key {key}"}
    is_image = getattr(req, "kind", "video") == "image"
    refs = list(getattr(req, "reference_images", ()) or ())
    if is_image:
        model = getattr(req, "model", None) or (
            "fal-ai/flux-pro/kontext" if refs else "fal-ai/flux/dev")
        body = {"prompt": req.prompt}
        if refs:
            mime, b64 = _load_ref(refs[0], net=net)
            body["image_url"] = f"data:{mime};base64,{b64}"
    else:
        model = getattr(req, "model", None) or "fal-ai/ltx-video"
        body = {"prompt": req.prompt, "aspect_ratio": _aspect(req)}
    created = net.post_json(f"https://queue.fal.run/{model}", headers=auth, json=body)
    status_url = _dig(created, "status_url")
    response_url = _dig(created, "response_url")
    if not status_url or not response_url:
        # Some sync responses embed the video directly.
        url = _fal_video_url(created)
        if url:
            return net.get_bytes(url)
        raise RenderError(f"fal: no status_url in response: {created}", kind="backend")

    def fetch() -> Any:
        return net.get_json(status_url, headers=auth)

    _poll(
        fetch,
        done=lambda s: str(_dig(s, "status")).upper() in ("COMPLETED", "OK"),
        failed=lambda s: (str(_dig(s, "status")).upper() in ("ERROR", "FAILED"))
                          and "fal job failed" or None,
        result=lambda s: "ready",  # the result lives at response_url
        limiter=net.limiter,
    )
    final = net.get_json(response_url, headers=auth)
    url = _fal_video_url(final)
    if not url:
        raise RenderError(f"fal: no video url in result: {final}", kind="backend")
    return net.get_bytes(url)


def _fal_video_url(obj: Any) -> str | None:
    return (_dig(obj, "video", "url") or _dig(obj, "videos", 0, "url")
            or _dig(obj, "images", 0, "url") or _dig(obj, "image", "url")
            or _dig(obj, "url"))


def _init_image(req: Any, *, net: Net) -> tuple[str, str] | None:
    """Load this shot's image-to-video start frame (Phase 5.3) → (mime,
    base64), or None when the shot has no init frame. The composed,
    identity-locked keyframe the video backend animates from."""
    ref = getattr(req, "init_image", "") or ""
    if not ref:
        return None
    return _load_ref(ref, net=net)


def _load_ref(ref: str, *, net: Net) -> tuple[str, str]:
    """Load a reference image (local path or http(s) URL) → (mime, base64).

    Used by reference-conditioned image backends (gemini/fal) to attach a
    subject's canonical portrait so identity holds across shots.
    """
    import base64 as _b64
    if ref.startswith("http://") or ref.startswith("https://"):
        data = net.get_bytes(ref)
    else:
        p = Path(ref)
        if not p.exists():
            raise RenderError(f"reference image not found: {ref}", kind="unsupported")
        data = p.read_bytes()
    ext = (Path(ref).suffix.lower().lstrip(".") or "png")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "webp": "webp", "png": "png"}.get(ext, "png")
    return f"image/{mime}", _b64.b64encode(data).decode("ascii")


# Gemini native image models (June 2026). Default = Nano Banana 2.
GEMINI_IMAGE_DEFAULT = "gemini-3.1-flash-image-preview"


def _gemini_image(req: Any, *, key: str, net: Net) -> bytes:
    """Gemini native image generation ("Nano Banana") — synchronous,
    reference-conditioned, photoreal stills.

    Ref: https://ai.google.dev/gemini-api/docs/image-generation
      POST {base}/models/{model}:generateContent   (x-goog-api-key)
      body.contents[0].parts = [{text}, {inline_data:{mime_type,data}}...]
      generationConfig.responseModalities = ["TEXT","IMAGE"]
    The generated image returns inline (base64) in the response — no second
    fetch. Any reference images are attached as inline_data parts so the
    subject's identity carries from the canonical portrait into the shot.
    """
    if getattr(req, "kind", "image") != "image":
        raise RenderError("gemini backend renders images only (--kind image).",
                          kind="unsupported")
    base = "https://generativelanguage.googleapis.com/v1beta"
    model = getattr(req, "model", None) or GEMINI_IMAGE_DEFAULT
    auth = {"x-goog-api-key": key}
    # Aspect is steered via the prompt (robust across API field-name churn).
    aspect = _aspect(req)
    prompt = f"{req.prompt}\n\n[Framing: {aspect} widescreen cinematic still.]"
    parts: list[dict[str, Any]] = [{"text": prompt}]
    for ref in getattr(req, "reference_images", ()) or ():
        mime, b64 = _load_ref(ref, net=net)
        parts.append({"inline_data": {"mime_type": mime, "data": b64}})
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    resp = net.post_json(f"{base}/models/{model}:generateContent",
                         headers=auth, json=body)
    cand_parts = _dig(resp, "candidates", 0, "content", "parts", default=[]) or []
    for p in cand_parts:
        blob = p.get("inline_data") or p.get("inlineData")
        if blob and blob.get("data"):
            import base64 as _b64
            return _b64.b64decode(blob["data"])
    # No image part — surface any text/refusal the model returned.
    txt = next((p.get("text") for p in cand_parts if p.get("text")), None)
    raise RenderError(
        f"gemini returned no image part"
        + (f" (model said: {txt[:200]})" if txt else f": {str(resp)[:200]}"),
        kind="backend",
    )


def make_stub(req: Any) -> bytes:
    """Offline placeholder keyframe — NO network, NO key, NO quota.

    The whole point (per the user's "test the pipeline before spending
    grok's daily limit"): synthesize a real, valid PNG per shot locally so
    the render → cut-list → ffmpeg-assembly chain can be validated for $0.
    Switch to a real backend (grok/veo/...) only once the pipeline works.

    The frame is a seed-derived solid colour overlaid with the shot id,
    role, duration, and a truncated prompt so you can eyeball ordering and
    timing in the assembled slideshow.
    """
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:  # noqa: BLE001
        raise RenderError(
            f"stub backend needs Pillow ({exc}); pip install 'autonovel[export]'.",
            kind="unsupported",
        )
    w = max(160, int(getattr(req, "width", 854) or 854))
    h = max(90, int(getattr(req, "height", 480) or 480))
    seed = int(getattr(req, "seed", 0) or 0)
    # Deterministic, legible colour from the seed (kept mid-bright).
    r = 60 + (seed & 0x7F)
    g = 60 + ((seed >> 7) & 0x7F)
    b = 60 + ((seed >> 14) & 0x7F)
    img = Image.new("RGB", (w, h), (r, g, b))
    draw = ImageDraw.Draw(img)
    prompt = (getattr(req, "prompt", "") or "")[:120]
    lines = [
        f"STUB · shot {getattr(req, 'shot_id', '?')} · take {getattr(req, 'take', 1)}",
        f"{getattr(req, 'duration_s', 0):g}s · {w}x{h}",
        prompt,
    ]
    y = max(8, h // 2 - 24)
    for line in lines:
        draw.text((12, y), line, fill=(245, 245, 245))
        y += 16
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _flow(req: Any, *, key: str, net: Net) -> bytes:
    """Flow is GUI-only — there is no API to call."""
    raise RenderError(
        "flow is a MANUAL backend (Google Flow is GUI-only — no API). "
        "Render the shots in Flow (labs.google/flow) and drop the MP4s "
        "into the clips dir, then run /autonovel:teaser-assemble.",
        kind="unsupported",
    )


# Backend dispatch table. Pollinations stays in render.py (a plain GET).
BACKENDS: dict[str, Callable[..., bytes]] = {
    "grok": _grok,
    "kie": _kie,
    "veo": _veo,
    "magichour": _magichour,
    "fal": _fal,
    "flow": _flow,
    "gemini": _gemini_image,
}

MANUAL_PROVIDERS = ("flow",)


# --------------------------------------------------------------------------
# Small shared helpers for request shape.
# --------------------------------------------------------------------------


def _aspect(req: Any) -> str:
    w, h = getattr(req, "width", 16), getattr(req, "height", 9)
    if not w or not h:
        return "16:9"
    return "9:16" if h > w else ("1:1" if h == w else "16:9")


def _clip_seconds(req: Any, *, cap: int, default: int) -> int:
    secs = getattr(req, "duration_s", None) or default
    try:
        secs = int(round(float(secs)))
    except (TypeError, ValueError):
        secs = default
    return max(1, min(int(cap), secs))


def is_manual(provider: str) -> bool:
    return provider in MANUAL_PROVIDERS


def render_one(req: Any, *, provider: str, key: str, net: Net) -> bytes:
    """Dispatch one request to its backend; return raw clip bytes."""
    fn = BACKENDS.get(provider)
    if fn is None:
        raise RenderError(f"no HTTP backend for provider {provider!r}.", kind="unsupported")
    return fn(req, key=key, net=net)
