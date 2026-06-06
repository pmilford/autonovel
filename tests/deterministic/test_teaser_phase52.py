"""Tier-1 tests for movie-teaser Phase 5.2: reference-conditioned
keyframes. Locked character references flow into the render so a
character's identity holds across separately-generated shots.

Network-free — the Gemini image backend + reference loading run against a
scripted httpx-like client. Covers: the Gemini Nano-Banana image backend
(reference-conditioned, image-only), reference loading (local/missing),
plan() threading shot_refs (drop-missing + cap), build_request style
override + Pollinations flux-kontext, and the refs-map APPROVAL GATE.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

import pytest

from autonovel.teaser import backends, render
from autonovel.teaser import refmanifest as rm
from autonovel.teaser import shots as shots_mod
from autonovel.teaser.shots import Shot, Teaser
from autonovel.mechanical.__main__ import _load_teaser_refs_map


# ------------------------------ fakes ------------------------------------


class Resp:
    def __init__(self, *, status=200, json=None, content=b"", headers=None):
        self.status_code = status
        self._json = json
        self.content = content
        self.headers = headers or {}
        self.text = ""

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class CaptureClient:
    """Captures POST bodies and returns a scripted response."""

    def __init__(self, *, post_resp):
        self.post_resp = post_resp
        self.posts: list[tuple[str, dict]] = []

    def post(self, url, headers=None, json=None):
        self.posts.append((url, json))
        return self.post_resp

    def get(self, url, headers=None):  # for ref download via URL (unused here)
        return Resp(content=b"REMOTE")


def _net(client):
    return backends.Net(client=client,
                        limiter=backends.RateLimiter(sleep=lambda _s: None))


def _png_bytes() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _req(**kw):
    base = dict(
        shot_id="01", kind="image", url="gemini:async", out_path="/tmp/x.png",
        prompt="JAKOB at his ledger", seed=3, width=854, height=480,
        take=1, provider="gemini", duration_s=8.0, model=None,
        reference_images=(),
    )
    base.update(kw)
    return render.RenderRequest(**base)


# --------------------------- gemini backend ------------------------------


def test_gemini_returns_inline_image(tmp_path) -> None:
    img_b64 = base64.b64encode(b"GENERATED").decode()
    resp = Resp(json={"candidates": [{"content": {"parts": [
        {"inline_data": {"mime_type": "image/png", "data": img_b64}}]}}]})
    out = backends.render_one(_req(), provider="gemini", key="k", net=_net(CaptureClient(post_resp=resp)))
    assert out == b"GENERATED"


def test_gemini_attaches_reference_parts(tmp_path) -> None:
    ref = tmp_path / "jakob_ref.png"
    ref.write_bytes(_png_bytes())
    img_b64 = base64.b64encode(b"COND").decode()
    client = CaptureClient(post_resp=Resp(json={"candidates": [{"content": {"parts": [
        {"inline_data": {"mime_type": "image/png", "data": img_b64}}]}}]}))
    out = backends.render_one(_req(reference_images=(str(ref),)),
                              provider="gemini", key="k", net=_net(client))
    assert out == b"COND"
    # the posted body carries a text part + an inline_data reference part
    _url, body = client.posts[0]
    parts = body["contents"][0]["parts"]
    assert any("text" in p for p in parts)
    assert any("inline_data" in p for p in parts), "reference image not attached"


def test_gemini_refuses_video_kind() -> None:
    with pytest.raises(backends.RenderError) as ei:
        backends.render_one(_req(kind="video"), provider="gemini", key="k",
                            net=_net(CaptureClient(post_resp=Resp(json={}))))
    assert ei.value.kind == "unsupported"


def test_gemini_no_image_part_is_typed() -> None:
    resp = Resp(json={"candidates": [{"content": {"parts": [
        {"text": "I can't generate that."}]}}]})
    with pytest.raises(backends.RenderError) as ei:
        backends.render_one(_req(), provider="gemini", key="k", net=_net(CaptureClient(post_resp=resp)))
    assert ei.value.kind == "backend" and "model said" in str(ei.value)


# --------------------------- reference loading ---------------------------


def test_load_ref_local(tmp_path) -> None:
    p = tmp_path / "ref.png"
    p.write_bytes(_png_bytes())
    mime, b64 = backends._load_ref(str(p), net=_net(CaptureClient(post_resp=Resp())))
    assert mime == "image/png" and base64.b64decode(b64) == _png_bytes()


def test_load_ref_missing_is_typed() -> None:
    with pytest.raises(backends.RenderError) as ei:
        backends._load_ref("/no/such/ref.png", net=_net(CaptureClient(post_resp=Resp())))
    assert ei.value.kind == "unsupported"


# ------------------------------ plan() -----------------------------------


def _shot(sid="01", **kw):
    base = dict(id=sid, role="hook", duration_s=5.0, aspect_ratio="16:9",
                shot_size="wide", subject_name="JAKOB",
                subject_appearance="fur-collared merchant", action="acts",
                setting="Augsburg", palette=["amber"])
    base.update(kw)
    return Shot(**base)


def test_plan_threads_refs_and_drops_missing(tmp_path) -> None:
    real = tmp_path / "refs" / "jakob_ref.png"
    real.parent.mkdir(parents=True)
    real.write_bytes(_png_bytes())
    t = Teaser(title="X", provider="gemini", shots=[_shot("01")])
    reqs = render.plan(
        t, provider="gemini", kind="image", out_dir=tmp_path / "clips",
        shot_refs={"01": [str(real), str(tmp_path / "missing.png"),
                          "https://h/remote.png"]}, max_refs=3)
    refs = reqs[0].reference_images
    assert str(real) in refs
    assert "https://h/remote.png" in refs            # http kept (not stat'd)
    assert str(tmp_path / "missing.png") not in refs  # missing local dropped


def test_plan_respects_max_refs(tmp_path) -> None:
    paths = []
    (tmp_path / "refs").mkdir()
    for i in range(4):
        p = tmp_path / "refs" / f"r{i}.png"
        p.write_bytes(_png_bytes())
        paths.append(str(p))
    t = Teaser(title="X", provider="gemini", shots=[_shot("01")])
    reqs = render.plan(t, provider="gemini", kind="image",
                       out_dir=tmp_path / "clips",
                       shot_refs={"01": paths}, max_refs=2)
    assert len(reqs[0].reference_images) == 2


# --------------------------- build_request -------------------------------


def test_build_request_style_override(tmp_path) -> None:
    s = _shot("01", style="period engraving")
    req = render.build_request(s, provider="gemini", kind="image",
                               out_dir=tmp_path, style_override="photoreal film still")
    assert "photoreal film still" in req.prompt
    assert "period engraving" not in req.prompt


def test_build_request_pollinations_flux_kontext_url_ref(tmp_path) -> None:
    s = _shot("01")
    req = render.build_request(s, provider="pollinations", kind="image",
                               out_dir=tmp_path,
                               reference_images=("https://h/portrait.png",))
    assert "flux-kontext" in req.url
    assert "image=" in req.url


# --------------------- refs-map approval gate (CLI) ----------------------


def test_load_teaser_refs_map_gates_on_approval(tmp_path) -> None:
    # Two subjects; JAKOB approved with a portrait on disk, ANNA pending.
    t = Teaser(title="X", provider="gemini", shots=[
        _shot("01", subject_name="JAKOB"),
        _shot("02", subject_name="ANNA", role="escalation")])
    shots_mod.dump(t, tmp_path / "teaser.json")
    (tmp_path / "refs").mkdir()
    (tmp_path / "refs" / "jakob_ref.png").write_bytes(_png_bytes())
    (tmp_path / "refs" / "anna_ref.png").write_bytes(_png_bytes())
    man = rm.RefManifest(subjects=[
        rm.CharacterRef(subject="JAKOB", status="locked", shots=["01"]),
        rm.CharacterRef(subject="ANNA", status="pending", shots=["02"]),
    ])
    rm.dump(man, tmp_path / "refs.yaml")
    refs_map = _load_teaser_refs_map(tmp_path / "teaser.json", None)
    assert "01" in refs_map                       # approved JAKOB flows
    assert refs_map["01"][0].endswith("jakob_ref.png")
    assert "02" not in refs_map                    # pending ANNA gated out


def test_load_teaser_refs_map_falls_back_to_plan_shots(tmp_path) -> None:
    """A locked subject with no explicit `shots:` inherits them from the
    auto plan (which groups shots by subject_name)."""
    t = Teaser(title="X", provider="gemini", shots=[_shot("01", subject_name="JAKOB")])
    shots_mod.dump(t, tmp_path / "teaser.json")
    (tmp_path / "refs").mkdir()
    (tmp_path / "refs" / "jakob_ref.png").write_bytes(_png_bytes())
    man = rm.RefManifest(subjects=[rm.CharacterRef(subject="JAKOB", status="approved")])
    rm.dump(man, tmp_path / "refs.yaml")
    refs_map = _load_teaser_refs_map(tmp_path / "teaser.json", None)
    assert refs_map.get("01") and refs_map["01"][0].endswith("jakob_ref.png")
