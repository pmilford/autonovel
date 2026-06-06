"""Tier-1 tests for movie-teaser Phase 5.5+5.6: audio reaches the backend
prompt, and character voices are locked + auto-aged scene-to-scene.

Dialogue text is ours; the video model speaks it (lipsync + voice). The
only lever for a consistent/aged voice is a locked per-character
descriptor injected into every speaking shot's prompt — tested here.
"""

from __future__ import annotations

from pathlib import Path

from autonovel.teaser import render, render_prompt as rp
from autonovel.teaser import refmanifest as rm
from autonovel.teaser import shots as shots_mod
from autonovel.teaser.shots import Shot, Teaser
from autonovel.mechanical.__main__ import _load_teaser_voices_map


def _shot(sid="01", *, dialogue=None, sfx="", ambience="", story_year=None, **kw):
    audio = {}
    if dialogue:
        audio["dialogue"] = dialogue
    if sfx:
        audio["sfx"] = sfx
    if ambience:
        audio["ambience"] = ambience
    base = dict(id=sid, role="hook", duration_s=5.0, aspect_ratio="16:9",
                shot_size="wide", subject_name="JAKOB",
                subject_appearance="merchant", action="acts",
                setting="Augsburg", palette=["amber"], audio=audio,
                story_year=story_year)
    base.update(kw)
    return Shot(**base)


# ----------------------- audio-for-prompt (5.5) --------------------------


def test_audio_prompt_includes_dialogue_sfx_ambience() -> None:
    s = _shot(dialogue=[{"speaker": "JAKOB", "line": "We have no time."}],
              sfx="coins on oak", ambience="rain on glass")
    out = rp.render_audio_for_prompt(s)
    assert 'JAKOB: "We have no time."' in out
    assert "Sound effects: coins on oak." in out
    assert "Ambience: rain on glass." in out


def test_audio_prompt_injects_voice_descriptor() -> None:
    s = _shot(dialogue=[{"speaker": "JAKOB", "line": "Sit."}])
    out = rp.render_audio_for_prompt(s, {"JAKOB": "low dry baritone"})
    assert '[voice: low dry baritone]' in out


def test_audio_prompt_per_line_voice_override_wins() -> None:
    s = _shot(dialogue=[{"speaker": "JAKOB", "line": "Sit.", "voice": "rasping, aged"}])
    out = rp.render_audio_for_prompt(s, {"JAKOB": "prime baritone"})
    assert "rasping, aged" in out and "prime baritone" not in out


def test_audio_prompt_empty_when_no_audio() -> None:
    assert rp.render_audio_for_prompt(_shot()) == ""


# --------------------- build_request / plan wiring -----------------------


def test_build_request_video_appends_audio(tmp_path) -> None:
    s = _shot(dialogue=[{"speaker": "JAKOB", "line": "Now."}])
    req = render.build_request(s, provider="grok", kind="video", out_dir=tmp_path,
                              voices={"JAKOB": "gravel baritone"})
    assert 'JAKOB [voice: gravel baritone]: "Now."' in req.prompt


def test_build_request_image_omits_audio(tmp_path) -> None:
    s = _shot(dialogue=[{"speaker": "JAKOB", "line": "Now."}])
    req = render.build_request(s, provider="gemini", kind="image", out_dir=tmp_path,
                              voices={"JAKOB": "gravel baritone"})
    assert "voice:" not in req.prompt and "Now." not in req.prompt


def test_plan_threads_shot_voices(tmp_path) -> None:
    t = Teaser(title="X", provider="grok", shots=[
        _shot("01", dialogue=[{"speaker": "JAKOB", "line": "Go."}])])
    reqs = render.plan(t, provider="grok", kind="video", out_dir=tmp_path,
                       shot_voices={"01": {"JAKOB": "deep, weary"}})
    assert "[voice: deep, weary]" in reqs[0].prompt


# ----------------------- voice resolution (5.6) --------------------------


def test_resolve_voice_base_and_ages() -> None:
    cr = rm.CharacterRef(subject="JAKOB", voice="dry baritone", voice_ages=[
        {"name": "prime", "descriptor": "firm baritone", "from_year": 1490, "to_year": 1510},
        {"name": "old", "descriptor": "thin, rasping", "from_year": 1511},
    ])
    assert cr.resolve_voice(None) == "dry baritone"      # no year → base
    assert cr.resolve_voice(1500) == "firm baritone"     # in prime window
    assert cr.resolve_voice(1520) == "thin, rasping"     # in old (open-ended)
    assert cr.age_variant_name(1500) == "prime"
    assert cr.age_variant_name(1520) == "old"


def test_resolve_voice_no_ages_returns_base() -> None:
    cr = rm.CharacterRef(subject="X", voice="warm alto")
    assert cr.resolve_voice(1600) == "warm alto"


def test_voice_fields_round_trip(tmp_path) -> None:
    man = rm.RefManifest(subjects=[rm.CharacterRef(
        subject="JAKOB", status="locked", voice="dry baritone", birth_year=1459,
        voice_ages=[{"name": "old", "descriptor": "rasping", "from_year": 1510}])])
    p = tmp_path / "refs.yaml"
    rm.dump(man, p)
    cr = rm.load(p).get("JAKOB")
    assert cr.voice == "dry baritone" and cr.birth_year == 1459
    assert cr.resolve_voice(1515) == "rasping"


# -------------------- voices map (approval-gated + aged) -----------------


def test_voices_map_gates_and_ages(tmp_path) -> None:
    t = Teaser(title="X", provider="grok", shots=[
        _shot("01", dialogue=[{"speaker": "JAKOB", "line": "A."}], story_year=1500),
        _shot("02", dialogue=[{"speaker": "JAKOB", "line": "B."}], story_year=1520,
              role="escalation"),
        _shot("03", dialogue=[{"speaker": "ANNA", "line": "C."}], role="escalation"),
    ])
    shots_mod.dump(t, tmp_path / "teaser.json")
    man = rm.RefManifest(subjects=[
        rm.CharacterRef(subject="JAKOB", status="locked", voice="baritone",
                        voice_ages=[
                            {"name": "prime", "descriptor": "firm", "from_year": 1490, "to_year": 1510},
                            {"name": "old", "descriptor": "rasping", "from_year": 1511}]),
        rm.CharacterRef(subject="ANNA", status="pending", voice="alto"),  # not approved
    ])
    rm.dump(man, tmp_path / "refs.yaml")
    vmap = _load_teaser_voices_map(tmp_path / "teaser.json", None)
    assert vmap["01"]["JAKOB"] == "firm"     # 1500 → prime
    assert vmap["02"]["JAKOB"] == "rasping"  # 1520 → old (auto-aged)
    assert "03" not in vmap                   # ANNA pending → gated out
