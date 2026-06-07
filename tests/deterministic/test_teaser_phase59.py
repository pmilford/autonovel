"""Tier-1 tests for movie-teaser Phase 5.9: music score policy + audio
seam-fades, plus the Veo fixed-duration snap.

Music: dialogue/SFX/ambience stay native per clip; `--score bed|none`
tells the model to add no background score so a single teaser-wide bed
carries it (or it stays scoreless). `native` may let the model score, and
the assembler can soften per-clip music pops with audio seam-fades.
"""

from __future__ import annotations

from pathlib import Path

from autonovel.teaser import assemble as asm, backends, render, render_prompt as rp
from autonovel.teaser.assemble import CutEntry, CutList
from autonovel.teaser.shots import Shot, Teaser


def _fc(argv):
    return argv[argv.index("-filter_complex") + 1]


def _shot(sid="01", **kw):
    base = dict(id=sid, role="hook", duration_s=8.0, aspect_ratio="16:9",
                shot_size="wide", subject_name="JAKOB", subject_appearance="x",
                action="acts", setting="Augsburg", palette=["amber"],
                audio={"dialogue": [{"speaker": "JAKOB", "line": "Now."}]})
    base.update(kw)
    return Shot(**base)


# ---------------------------- score policy -------------------------------


def test_score_native_no_suppression() -> None:
    out = rp.render_audio_for_prompt(_shot(), score="native")
    assert "No musical score" not in out
    assert 'JAKOB: "Now."' in out


def test_score_bed_suppresses_model_music() -> None:
    out = rp.render_audio_for_prompt(_shot(), score="bed")
    assert "No musical score" in out and "diegetic" in out
    assert 'JAKOB: "Now."' in out          # dialogue still present


def test_score_none_suppresses_too() -> None:
    assert "No musical score" in rp.render_audio_for_prompt(_shot(), score="none")


def test_build_request_threads_score(tmp_path) -> None:
    req = render.build_request(_shot(), provider="veo", kind="video",
                               out_dir=tmp_path, score="bed")
    assert "No musical score" in req.prompt


def test_plan_threads_score(tmp_path) -> None:
    t = Teaser(title="X", provider="veo", shots=[_shot("01")])
    reqs = render.plan(t, provider="veo", kind="video", out_dir=tmp_path, score="bed")
    assert "No musical score" in reqs[0].prompt
    # default native → no suppression
    reqs2 = render.plan(t, provider="veo", kind="video", out_dir=tmp_path)
    assert "No musical score" not in reqs2[0].prompt


# --------------------------- audio seam-fade -----------------------------


def _vid_cut(sf=0.0, n=2):
    return CutList(title="X", kind="video", audio_seam_fade=sf,
                   entries=[CutEntry(f"{i:02d}", f"/c/{i}.mp4", 8.0) for i in range(n)])


def test_seam_fade_off_by_default() -> None:
    fc = _fc(asm.ffmpeg_command(_vid_cut(0.0), "o.mp4"))
    assert "afade" not in fc
    assert "concat=n=2:v=1:a=1[v][aclip]" in fc


def test_seam_fade_applies_per_clip_audio() -> None:
    fc = _fc(asm.ffmpeg_command(_vid_cut(0.2), "o.mp4"))
    assert "afade=t=in:st=0:d=0.2" in fc
    assert "afade=t=out:st=7.8:d=0.2" in fc
    assert "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][aclip]" in fc


def test_seam_fade_round_trip(tmp_path) -> None:
    c = _vid_cut(0.15)
    p = tmp_path / "cut_list.json"
    asm.dump(c, p)
    assert asm.load(p).audio_seam_fade == 0.15


# ----------------------- Veo fixed-duration snap -------------------------


def _req(duration_s):
    return render.RenderRequest(
        shot_id="01", kind="video", url="x", out_path="/tmp/x.mp4",
        prompt="p", seed=1, width=854, height=480, take=1, provider="veo",
        duration_s=duration_s)


def test_clip_seconds_snaps_to_allowed() -> None:
    snap = lambda d: backends._clip_seconds(_req(d), cap=8, default=8, allowed=(4, 6, 8))
    assert snap(5) == 4      # tie 4/6 → shorter
    assert snap(7) == 6      # tie 6/8 → shorter
    assert snap(6) == 6
    assert snap(3) == 4
    assert snap(100) == 8
    # without `allowed`, clamps as before
    assert backends._clip_seconds(_req(5), cap=8, default=8) == 5


def test_veo_body_duration_is_allowed_value() -> None:
    class Resp:
        def __init__(self, **k): self.__dict__.update(k); self.status_code=200; self.headers={}
        def json(self): return self._j
        def raise_for_status(self): pass
    posts = []
    class C:
        def post(self, url, headers=None, json=None):
            posts.append(json)
            r = Resp(); r._j = {"name": "operations/op1"}; return r
        def get(self, url, headers=None):
            r = Resp()
            if url.endswith("/operations/op1"):
                r._j = {"done": True, "response": {"generateVideoResponse": {
                    "generatedSamples": [{"video": {"uri": "https://g/v.mp4"}}]}}}
            else:
                r._j = None; r.content = b"V"
            return r
    net = backends.Net(client=C(), limiter=backends.RateLimiter(sleep=lambda _s: None))
    backends.render_one(_req(5.0), provider="veo", key="k", net=net)
    dur = posts[0]["parameters"]["durationSeconds"]
    assert dur == 4 and isinstance(dur, int)   # 5 → snapped to 4, numeric
