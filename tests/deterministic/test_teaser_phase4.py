"""Tier-1 tests for movie-teaser Phase 4: real free render backends.

Network-free — every backend runs against a scripted httpx-like client.
Covers key resolution, rate-limit/backoff, the create→poll→download flow
for each provider, early-402/auth fail-fast, and the manual (flow) path.
The clip critique remains the vision-LLM step in the command body
(feedback_avoid_brittle_python), so nothing here judges pixels.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel.teaser import backends, render
from autonovel.teaser import shots as shots_mod
from autonovel.teaser.shots import Shot, Teaser


# ------------------------------ fakes ------------------------------------


class Resp:
    def __init__(self, *, status=200, json=None, content=b"", headers=None, text=None):
        self.status_code = status
        self._json = json
        self.content = content
        self.headers = headers or {}
        self.text = text if text is not None else ""

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class ScriptClient:
    """Maps a URL substring → a Resp (or a list of Resps consumed in order)."""

    def __init__(self, *, post=None, get=None):
        self._post = post or {}
        self._get = get or {}
        self.calls: list[tuple[str, str]] = []

    def _match(self, table, url):
        for key, val in table.items():
            if key in url:
                if isinstance(val, list):
                    return val.pop(0)
                return val
        raise AssertionError(f"no scripted response for {url}")

    def post(self, url, headers=None, json=None):
        self.calls.append(("POST", url))
        return self._match(self._post, url)

    def get(self, url, headers=None):
        self.calls.append(("GET", url))
        return self._match(self._get, url)


def _net(client):
    lim = backends.RateLimiter(min_interval=0.0, sleep=lambda _s: None)
    return backends.Net(client=client, limiter=lim)


def _req(**kw):
    base = dict(
        shot_id="01a", kind="video", url="grok:async", out_path="/tmp/x.mp4",
        prompt='A figure. "Run," she says.', seed=7, width=854, height=480,
        take=1, provider="grok", duration_s=8.0,
    )
    base.update(kw)
    return render.RenderRequest(**base)


# --------------------------- key resolution ------------------------------


def test_resolve_key_precedence(monkeypatch) -> None:
    monkeypatch.setattr(backends, "_DOTENV_LOADED", True)  # skip .env
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    assert backends.resolve_key("grok", token="explicit") == "explicit"  # flag wins
    assert backends.resolve_key("grok") is None                          # nothing set
    monkeypatch.setenv("GROK_API_KEY", "envkey")
    assert backends.resolve_key("grok") == "envkey"                      # env found
    monkeypatch.setenv("XAI_API_KEY", "primary")
    assert backends.resolve_key("grok") == "primary"                     # first listed wins


# --------------------------- rate limiter --------------------------------


def test_rate_limiter_paces() -> None:
    clock = {"t": 0.0}
    slept: list[float] = []
    lim = backends.RateLimiter(
        min_interval=5.0, sleep=lambda s: slept.append(s),
        monotonic=lambda: clock["t"],
    )
    lim.pace()                 # first call: no wait
    lim.pace()                 # immediately again: must wait ~5s
    assert slept and abs(slept[0] - 5.0) < 1e-9


def test_rate_limiter_backoff_honours_retry_after() -> None:
    slept: list[float] = []
    lim = backends.RateLimiter(sleep=lambda s: slept.append(s))
    lim.backoff(1, retry_after=3.0)
    assert slept[-1] == 3.0
    lim.backoff(2)             # exponential when no Retry-After
    assert slept[-1] == 4.0    # base_backoff(2) ** 2


# ------------------------------- Net -------------------------------------


def test_net_402_and_auth_are_typed() -> None:
    n = _net(ScriptClient(get={"x": Resp(status=402)}))
    with pytest.raises(backends.RenderError) as ei:
        n.get_json("http://h/x")
    assert ei.value.kind == "payment"
    n2 = _net(ScriptClient(get={"x": Resp(status=401)}))
    with pytest.raises(backends.RenderError) as ei2:
        n2.get_json("http://h/x")
    assert ei2.value.kind == "auth"


def test_net_retries_429_then_succeeds() -> None:
    c = ScriptClient(get={"x": [Resp(status=429, headers={"Retry-After": "0"}),
                               Resp(status=200, json={"ok": 1})]})
    n = _net(c)
    assert n.get_json("http://h/x") == {"ok": 1}
    assert sum(1 for m, _ in c.calls if m == "GET") == 2


# ----------------------------- backends ----------------------------------


def test_grok_create_poll_download() -> None:
    c = ScriptClient(
        post={"videos/generations": Resp(json={"request_id": "r1"})},
        get={"videos/r1": [Resp(json={"status": "pending"}),
                           Resp(json={"status": "done", "video": {"url": "https://cdn/v.mp4"}})],
             "cdn/v.mp4": Resp(content=b"MP4BYTES")},
    )
    out = backends.render_one(_req(provider="grok"), provider="grok", key="k", net=_net(c))
    assert out == b"MP4BYTES"


def test_grok_synchronous_response() -> None:
    c = ScriptClient(
        post={"videos/generations": Resp(json={"video": {"url": "https://cdn/s.mp4"}})},
        get={"cdn/s.mp4": Resp(content=b"SYNC")},
    )
    out = backends.render_one(_req(provider="grok"), provider="grok", key="k", net=_net(c))
    assert out == b"SYNC"


def test_kie_create_poll_download() -> None:
    c = ScriptClient(
        post={"jobs/createTask": Resp(json={"data": {"taskId": "t9"}})},
        get={"recordInfo": [Resp(json={"data": {"state": "waiting"}}),
                            Resp(json={"data": {"state": "success",
                                                "resultJson": json.dumps(
                                                    {"resultUrls": ["https://cdn/k.mp4"]})}})],
             "cdn/k.mp4": Resp(content=b"KIE")},
    )
    out = backends.render_one(_req(provider="kie"), provider="kie", key="k", net=_net(c))
    assert out == b"KIE"


def test_veo_predict_long_running() -> None:
    c = ScriptClient(
        post={"predictLongRunning": Resp(json={"name": "operations/op1"})},
        get={"operations/op1": [Resp(json={"done": False}),
                                Resp(json={"done": True, "response": {"generateVideoResponse": {
                                    "generatedSamples": [{"video": {"uri": "https://g/veo.mp4"}}]}}})],
             "g/veo.mp4": Resp(content=b"VEO")},
    )
    out = backends.render_one(_req(provider="veo"), provider="veo", key="k", net=_net(c))
    assert out == b"VEO"


def test_magichour_create_poll_download() -> None:
    c = ScriptClient(
        post={"text-to-video": Resp(json={"id": "p1"})},
        get={"video-projects/p1": [Resp(json={"status": "rendering"}),
                                   Resp(json={"status": "complete",
                                              "downloads": [{"url": "https://cdn/m.mp4"}]})],
             "cdn/m.mp4": Resp(content=b"MH")},
    )
    out = backends.render_one(_req(provider="magichour"), provider="magichour", key="k", net=_net(c))
    assert out == b"MH"


def test_fal_queue_flow() -> None:
    c = ScriptClient(
        post={"queue.fal.run": Resp(json={"status_url": "https://q/status",
                                          "response_url": "https://q/response"})},
        get={"q/status": Resp(json={"status": "COMPLETED"}),
             "q/response": Resp(json={"video": {"url": "https://cdn/f.mp4"}}),
             "cdn/f.mp4": Resp(content=b"FAL")},
    )
    out = backends.render_one(_req(provider="fal"), provider="fal", key="k", net=_net(c))
    assert out == b"FAL"


def test_backend_failure_is_typed() -> None:
    c = ScriptClient(
        post={"videos/generations": Resp(json={"request_id": "r1"})},
        get={"videos/r1": Resp(json={"status": "failed", "error": "nsfw"})},
    )
    with pytest.raises(backends.RenderError) as ei:
        backends.render_one(_req(), provider="grok", key="k", net=_net(c))
    assert ei.value.kind == "backend"


def test_flow_is_manual() -> None:
    assert backends.is_manual("flow") is True
    with pytest.raises(backends.RenderError) as ei:
        backends.render_one(_req(provider="flow"), provider="flow", key="", net=_net(ScriptClient()))
    assert ei.value.kind == "unsupported"


# --------------------------- render() routing ----------------------------


def test_render_missing_key_fails_fast_with_guidance(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(backends, "_DOTENV_LOADED", True)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    reqs = [_req(out_path=str(tmp_path / "a.mp4")),
            _req(shot_id="02b", out_path=str(tmp_path / "b.mp4"))]
    results = render.render(reqs)  # no key, no client
    assert len(results) == 2
    assert all(not r.ok for r in results)
    assert "no API key for grok" in results[0].error
    assert not (tmp_path / "a.mp4").exists()  # nothing hit the network


def test_render_manual_provider(tmp_path) -> None:
    reqs = [_req(provider="flow", out_path=str(tmp_path / "a.mp4"))]
    results = render.render(reqs)
    assert results[0].ok is False
    assert "manual backend" in results[0].error


def test_render_grok_writes_bytes(tmp_path) -> None:
    c = ScriptClient(
        post={"videos/generations": Resp(json={"request_id": "r1"})},
        get={"videos/r1": Resp(json={"status": "done", "video": {"url": "https://cdn/v.mp4"}}),
             "cdn/v.mp4": Resp(content=b"CLIP")},
    )
    out = tmp_path / "shot_01a.mp4"
    reqs = [_req(out_path=str(out))]
    results = render.render(reqs, client=c, token="k")
    assert results[0].ok and out.read_bytes() == b"CLIP"


def test_render_pollinations_402_short_circuits(tmp_path) -> None:
    """A 402 wall hits every request identically — stop after the first."""
    class C402:
        def __init__(self):
            self.gets = 0

        def get(self, url, headers=None):
            self.gets += 1
            return Resp(status=402)

    c = C402()
    reqs = render.plan(
        Teaser(title="X", provider="pollinations", shots=[
            Shot(id="01a", role="hook", duration_s=5.0, aspect_ratio="16:9",
                 shot_size="wide", subject_name="A", subject_appearance="x",
                 action="y", setting="z", palette=["amber"]),
            Shot(id="02b", role="button", duration_s=5.0, aspect_ratio="16:9",
                 shot_size="wide", subject_name="A", subject_appearance="x",
                 action="y", setting="z", palette=["amber"]),
        ]),
        out_dir=tmp_path, kind="image",
    )
    results = render.render(reqs, client=c)
    assert results and results[0].error and "402" in results[0].error
    assert c.gets == 1  # short-circuited, did not retry the second shot


# ------------------------------- CLI -------------------------------------


def _run(*argv):
    return subprocess.run([sys.executable, "-m", "autonovel.mechanical", *argv],
                          capture_output=True, text=True)


def test_stub_backend_offline(tmp_path) -> None:
    """The stub provider writes a real PNG keyframe with NO network/key."""
    out = tmp_path / "shot_01a.png"
    reqs = [_req(provider="stub", kind="image", out_path=str(out))]
    results = render.render(reqs)  # no client, no key, no network
    assert results[0].ok
    data = out.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"  # valid PNG signature
    assert results[0].bytes == len(data)


def test_stub_via_cli_renders_for_free(tmp_path) -> None:
    t = Teaser(title="X", provider="stub", shots=[
        Shot(id="01a", role="hook", duration_s=5.0, aspect_ratio="16:9",
             shot_size="wide", subject_name="A", subject_appearance="x",
             action="y", setting="z", palette=["amber"])])
    p = tmp_path / "teaser.json"
    shots_mod.dump(t, p)
    out = _run("teaser-render", str(p), "--format", "json",
               "--out-dir", str(tmp_path / "clips"))
    data = json.loads(out.stdout)
    assert data["rendered"] == 1 and data["failed"] == 0
    assert (tmp_path / "clips" / "shot_01a.png").exists()


def test_cli_dry_run_reports_key_status(tmp_path) -> None:
    t = Teaser(title="X", provider="grok", shots=[
        Shot(id="01a", role="hook", duration_s=8.0, aspect_ratio="16:9",
             shot_size="wide", subject_name="A", subject_appearance="x",
             action="y", setting="z", palette=["amber"])])
    p = tmp_path / "teaser.json"
    shots_mod.dump(t, p)
    out = _run("teaser-render", str(p), "--dry-run", "--format", "json",
               "--provider", "magichour")
    data = json.loads(out.stdout)
    assert data["provider"] == "magichour"
    assert data["kind"] == "video"        # auto → video for a video backend
    assert data["needs_key"] is True
    assert not (tmp_path / "clips").exists()
