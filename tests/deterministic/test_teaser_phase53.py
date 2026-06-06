"""Tier-1 tests for movie-teaser Phase 5.3: image-to-video start frames.

A composed keyframe (image) becomes the first frame the video backends
(grok/veo/kie) animate from, so the identity-locked still turns into
motion. Network-free — scripted httpx-like client captures POST bodies.
"""

from __future__ import annotations

import base64
import io

import pytest

from autonovel.teaser import backends, render
from autonovel.teaser.shots import Shot, Teaser


class Resp:
    def __init__(self, *, status=200, json=None, content=b""):
        self.status_code = status
        self._json = json
        self.content = content
        self.headers = {}
        self.text = ""

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class CaptureClient:
    def __init__(self, *, post=None, get=None):
        self._post = post or {}
        self._get = get or {}
        self.posts: list[tuple[str, dict]] = []

    def _match(self, table, url):
        for k, v in table.items():
            if k in url:
                return v.pop(0) if isinstance(v, list) else v
        raise AssertionError(f"no scripted response for {url}")

    def post(self, url, headers=None, json=None):
        self.posts.append((url, json))
        return self._match(self._post, url)

    def get(self, url, headers=None):
        return self._match(self._get, url)


def _net(client):
    return backends.Net(client=client,
                        limiter=backends.RateLimiter(sleep=lambda _s: None))


def _png(tmp_path):
    from PIL import Image
    p = tmp_path / "shot_01.png"
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (1, 2, 3)).save(buf, format="PNG")
    p.write_bytes(buf.getvalue())
    return p


def _req(init_image="", **kw):
    base = dict(
        shot_id="01", kind="video", url="x", out_path="/tmp/x.mp4",
        prompt="JAKOB turns to the window", seed=1, width=854, height=480,
        take=1, provider="grok", duration_s=8.0, model=None,
        reference_images=(), init_image=init_image,
    )
    base.update(kw)
    return render.RenderRequest(**base)


# ------------------------------ plan() -----------------------------------


def _shot(sid="01"):
    return Shot(id=sid, role="hook", duration_s=5.0, aspect_ratio="16:9",
                shot_size="wide", subject_name="JAKOB",
                subject_appearance="merchant", action="acts",
                setting="Augsburg", palette=["amber"])


def test_plan_picks_up_keyframe_as_init(tmp_path) -> None:
    _png(tmp_path)  # tmp_path/shot_01.png
    t = Teaser(title="X", provider="grok", shots=[_shot("01"), _shot("02")])
    reqs = render.plan(t, provider="grok", kind="video", out_dir=tmp_path,
                       from_keyframes=True)
    by = {r.shot_id: r for r in reqs}
    assert by["01"].init_image.endswith("shot_01.png")  # keyframe found
    assert by["02"].init_image == ""                     # no keyframe → t2v


def test_plan_no_init_when_flag_off(tmp_path) -> None:
    _png(tmp_path)
    t = Teaser(title="X", provider="grok", shots=[_shot("01")])
    reqs = render.plan(t, provider="grok", kind="video", out_dir=tmp_path,
                       from_keyframes=False)
    assert reqs[0].init_image == ""


def test_plan_keyframe_only_for_video(tmp_path) -> None:
    _png(tmp_path)
    t = Teaser(title="X", provider="gemini", shots=[_shot("01")])
    reqs = render.plan(t, provider="gemini", kind="image", out_dir=tmp_path,
                       from_keyframes=True)
    assert reqs[0].init_image == ""  # image kind never seeds an init frame


# ----------------------------- backends ----------------------------------


def test_grok_attaches_init_image(tmp_path) -> None:
    p = _png(tmp_path)
    client = CaptureClient(
        post={"videos/generations": Resp(json={"request_id": "r1"})},
        get={"videos/r1": Resp(json={"status": "done", "video": {"url": "https://cdn/v.mp4"}}),
             "cdn/v.mp4": Resp(content=b"MP4")},
    )
    out = backends.render_one(_req(init_image=str(p)), provider="grok", key="k", net=_net(client))
    assert out == b"MP4"
    _url, body = client.posts[0]
    assert body.get("image", "").startswith("data:image/png;base64,")


def test_veo_attaches_init_image(tmp_path) -> None:
    p = _png(tmp_path)
    client = CaptureClient(
        post={"predictLongRunning": Resp(json={"name": "operations/op1"})},
        get={"operations/op1": Resp(json={"done": True, "response": {"generateVideoResponse": {
            "generatedSamples": [{"video": {"uri": "https://g/v.mp4"}}]}}}),
             "g/v.mp4": Resp(content=b"VEO")},
    )
    out = backends.render_one(_req(init_image=str(p), provider="veo"),
                              provider="veo", key="k", net=_net(client))
    assert out == b"VEO"
    _url, body = client.posts[0]
    img = body["instances"][0].get("image")
    assert img and img.get("bytesBase64Encoded") and img.get("mimeType") == "image/png"


def test_kie_attaches_init_image(tmp_path) -> None:
    p = _png(tmp_path)
    client = CaptureClient(
        post={"jobs/createTask": Resp(json={"data": {"taskId": "t1"}})},
        get={"recordInfo": Resp(json={"data": {"state": "success",
              "resultJson": '{"resultUrls": ["https://cdn/k.mp4"]}'}}),
             "cdn/k.mp4": Resp(content=b"KIE")},
    )
    out = backends.render_one(_req(init_image=str(p), provider="kie"),
                              provider="kie", key="k", net=_net(client))
    assert out == b"KIE"
    _url, body = client.posts[0]
    assert body["input"].get("image_url", "").startswith("data:image/png;base64,")


def test_video_without_init_is_pure_t2v(tmp_path) -> None:
    client = CaptureClient(
        post={"videos/generations": Resp(json={"request_id": "r1"})},
        get={"videos/r1": Resp(json={"status": "done", "video": {"url": "https://cdn/v.mp4"}}),
             "cdn/v.mp4": Resp(content=b"MP4")},
    )
    backends.render_one(_req(init_image=""), provider="grok", key="k", net=_net(client))
    _url, body = client.posts[0]
    assert "image" not in body  # no init frame → text-to-video, unchanged


def test_build_request_records_init_note(tmp_path) -> None:
    req = render.build_request(_shot("01"), provider="grok", kind="video",
                               out_dir=tmp_path, init_image="/k/shot_01.png")
    assert req.init_image == "/k/shot_01.png"
    assert "+init-frame" in req.url
