"""Tier-1 tests for movie-teaser Phase 3.5: the thin free render adapter
and the video-provider resolver.

Network-free — the httpx client is injected (mirrors export/wikimedia).
URL/seed/path construction + filesystem facts only; the clip critique is
the vision-LLM step in the command body (feedback_avoid_brittle_python).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.teaser import render
from autonovel.teaser import shots as shots_mod
from autonovel.teaser.shots import Shot, Teaser


def _shot(**kw) -> Shot:
    base = dict(
        id="01a", role="hook", duration_s=5.0, aspect_ratio="16:9",
        shot_size="wide", subject_name="JAKOB",
        subject_appearance="14yo, plain wool doublet",
        action="He looks up", setting="Venice", palette=["amber"],
    )
    base.update(kw)
    return Shot(**base)


def _run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", *argv],
        capture_output=True, text=True,
    )


# ----------------------------- size / seed -------------------------------


def test_aspect_to_size() -> None:
    assert render.aspect_to_size("16:9", 480) == (854, 480)
    assert render.aspect_to_size("1:1", 480) == (480, 480)
    assert render.aspect_to_size("garbage", 480) == (854, 480)  # falls back to 16:9
    w, h = render.aspect_to_size("9:16", 480)
    assert (w, h) == (270, 480)


def test_seed_is_deterministic_and_take_varying() -> None:
    s = _shot()
    assert render._seed_for(s, 1) == render._seed_for(s, 1)  # stable across calls
    assert render._seed_for(s, 1) != render._seed_for(s, 2)  # takes differ
    # explicit seed honoured for take 1.
    assert render._seed_for(_shot(seed=99), 1) == 99


# ----------------------------- build / plan ------------------------------


def test_build_request_image_url_and_path(tmp_path: Path) -> None:
    req = render.build_request(_shot(), out_dir=tmp_path, kind="image")
    assert req.url.startswith(render.POLLINATIONS_IMAGE)
    assert "width=854" in req.url and "height=480" in req.url and "seed=" in req.url
    assert req.out_path.endswith("shot_01a.png")
    assert req.kind == "image"


def test_build_request_video_and_takes(tmp_path: Path) -> None:
    req = render.build_request(_shot(), out_dir=tmp_path, kind="video", take=2)
    assert req.url.startswith(render.POLLINATIONS_VIDEO)
    assert req.out_path.endswith("shot_01a_take2.mp4")


def test_plan_multiplies_by_takes_and_filters(tmp_path: Path) -> None:
    t = Teaser(title="X", provider="pollinations", shots=[
        _shot(id="01a"), _shot(id="02b", role="button"),
    ])
    reqs = render.plan(t, out_dir=tmp_path, takes=3)
    assert len(reqs) == 6  # 2 shots × 3 takes
    one = render.plan(t, out_dir=tmp_path, only_shot="02b")
    assert len(one) == 1 and one[0].shot_id == "02b"


# ----------------------------- render (no net) ---------------------------


class _FakeResp:
    def __init__(self, content: bytes, fail: bool = False) -> None:
        self.content = content
        self._fail = fail

    def raise_for_status(self) -> None:
        if self._fail:
            raise RuntimeError("HTTP 500")


class _FakeClient:
    """httpx-like seam; fails any URL whose prompt contains 'BOOM'."""

    def get(self, url, headers=None):  # noqa: ANN001
        return _FakeResp(b"\x89PNGdata", fail="BOOM" in url)


def test_render_writes_bytes_and_isolates_failures(tmp_path: Path) -> None:
    t = Teaser(title="X", provider="pollinations", shots=[
        _shot(id="01a", action="He looks up"),
        _shot(id="02b", role="button", action="BOOM everything explodes"),
    ])
    reqs = render.plan(t, out_dir=tmp_path / "clips")
    results = render.render(reqs, client=_FakeClient())
    ok = {r.shot_id: r for r in results if r.ok}
    bad = {r.shot_id: r for r in results if not r.ok}
    assert "01a" in ok and "02b" in bad      # one failure does not abort the batch
    assert (tmp_path / "clips" / "shot_01a.png").read_bytes() == b"\x89PNGdata"
    assert not (tmp_path / "clips" / "shot_02b.png").exists()
    assert ok["01a"].bytes == len(b"\x89PNGdata")


# ------------------------------- CLI -------------------------------------


def test_cli_teaser_render_dry_run_downloads_nothing(tmp_path: Path) -> None:
    t = Teaser(title="X", provider="pollinations", shots=[_shot(id="01a")])
    p = tmp_path / "teaser.json"
    shots_mod.dump(t, p)
    out = _run("teaser-render", str(p), "--dry-run", "--format", "json")
    assert out.returncode == 0
    data = json.loads(out.stdout)
    assert data["dry_run"] is True
    assert data["count"] == 1
    assert data["requests"][0]["url"].startswith(render.POLLINATIONS_IMAGE)
    # Nothing was written.
    assert not (tmp_path / "clips").exists()


def test_cli_resolve_video_provider_default_and_override() -> None:
    out = _run("resolve-video-provider")
    assert json.loads(out.stdout) == {"provider": "pollinations", "source": "default"}
    out2 = _run("resolve-video-provider", "--cli-provider", "veo")
    assert json.loads(out2.stdout) == {"provider": "veo", "source": "cli"}
