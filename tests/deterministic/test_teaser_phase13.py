"""Tier-1 tests for movie-teaser Phase 13: the AI-video SHORT (2026-06-08).

A full Fugger run on Phases 11+12 was still incoherent: 180s of 30+
independently-generated clips never stitch into a story. Research (No Film
School, the 2026 AI-short workflow, character-consistency writeups) says AI
narrative shorts cohere at 45-60s / 6-12 shots, carried by a single
first-person VOICEOVER spine. Phase 13 adds a `mode` knob (short|trailer,
default short), a `spine.narrator` + per-shot `voiceover`, a few-longer-shots
planner, and mode-aware critique. One pipeline, no duplication.
"""

from __future__ import annotations

import json
import subprocess
import sys

from autonovel.teaser import beats, critique, providers
from autonovel.teaser.shots import DEFAULT_MODE, MODES, Shot, Spine, Teaser


def _run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "autonovel.mechanical", *argv],
                          capture_output=True, text=True)


# ------------------------------- data model ------------------------------

def test_mode_defaults_to_short_and_round_trips() -> None:
    assert DEFAULT_MODE == "short" and "short" in MODES and "trailer" in MODES
    t = Teaser(title="T", shots=[])
    assert t.mode == "short"
    # default omitted from JSON so pre-Phase-13 teasers round-trip identical
    assert "mode" not in t.to_dict()
    t2 = Teaser(title="T", mode="trailer", shots=[])
    assert t2.to_dict()["mode"] == "trailer"
    assert Teaser.from_dict(t2.to_dict()).mode == "trailer"
    # an unknown mode falls back to the default
    assert Teaser.from_dict({"title": "X", "mode": "bogus", "shots": []}).mode == "short"


def test_narrator_and_voiceover_round_trip_and_omit_when_empty() -> None:
    sp = Spine(dramatic_question="q", narrator="Jakob in old age, looking back")
    assert sp.to_dict()["narrator"].startswith("Jakob")
    assert "narrator" not in Spine(dramatic_question="q").to_dict()
    s = Shot(id="01", role="hook", subject_name="J", subject_appearance="x",
             action="a", voiceover="I learned that money moves at the speed of a secret.")
    assert "voiceover" in s.to_dict()
    assert Shot.from_dict(s.to_dict()).voiceover.startswith("I learned")
    assert "voiceover" not in Shot(id="02", role="hook", subject_name="J",
                                   subject_appearance="x", action="a").to_dict()


# --------------------------------- planner -------------------------------

def test_short_plan_is_few_longer_shots_capped_at_12() -> None:
    p = beats.plan(60, mode="short")
    assert p["mode"] == "short"
    assert 6 <= p["shot_target"] <= 12
    assert p["shot_cap"] == 12
    assert beats.plan(180, mode="short")["shot_target"] <= 12   # hard cap
    assert p["voiceover_target"] >= 4                           # the spine
    assert p["avg_shot_s"] >= 4.0                               # longer, not strobe


def test_trailer_plan_keeps_the_longer_montage_shape() -> None:
    short = beats.plan(180, mode="short")
    trailer = beats.plan(180, mode="trailer")
    assert trailer["shot_target"] > short["shot_target"]        # montage = more shots
    assert trailer["voiceover_target"] == 0


def test_plan_warns_above_90s_short() -> None:
    assert beats.plan(120, mode="short")["warn_long_for_ai_video"] is True
    assert beats.plan(60, mode="short")["warn_long_for_ai_video"] is False


def test_cli_plan_mode(tmp_path) -> None:  # noqa: ANN001
    out = _run("teaser-plan", "--length", "60", "--mode", "short", "--format", "json")
    assert out.returncode == 0
    d = json.loads(out.stdout)
    assert d["mode"] == "short" and d["voiceover_target"] >= 4
    human = _run("teaser-plan", "--length", "60", "--mode", "short", "--format", "human")
    assert "VOICEOVER" in human.stdout


# --------------------------- mode-aware critique -------------------------

def _short_teaser(**kw) -> Teaser:  # noqa: ANN003
    sp = Spine(dramatic_question="q", logline="l", want="w", opposing_force="f",
               emotional_arc="a", score_direction="s", genre="historical fiction",
               turn="it flips", narrator="Jakob in old age")
    shots = [
        Shot(id=f"{i:02d}", role=("hook" if i == 0 else "button" if i == 5 else "escalation"),
             subject_name="Jakob Fugger", subject_appearance="x", action=f"acts {i}",
             identify=("Jakob Fugger — banker" if i == 0 else ""),
             character_beat=("want" if i == 1 else "cost" if i == 4 else ""),
             voiceover=f"line {i}", palette=["amber"])
        for i in range(6)
    ]
    t = Teaser(title="T", length_s=40, provider="veo", mode="short", spine=sp, shots=shots)
    for k, v in kw.items():
        setattr(t, k, v)
    return t


def test_short_mode_does_not_gate_on_thin_dialogue() -> None:
    # In a short, in-scene dialogue is intentionally sparse — the VO carries it.
    t = _short_teaser()  # no audio.dialogue anywhere
    codes = {f.code for f in critique.critique(t, providers.get("veo")).findings}
    assert "thin-dialogue" not in codes
    assert critique.story_ready(critique.critique(t, providers.get("veo")))


def test_short_mode_flags_thin_narration_and_missing_narrator() -> None:
    t = _short_teaser()
    for s in t.shots:
        s.voiceover = ""          # strip the spine
    t.spine.narrator = ""
    codes = {f.code for f in critique.critique(t, providers.get("veo")).findings}
    assert "thin-narration" in codes
    assert "no-narrator" in codes
    # advisory, not a hard story-gate block (the quality gate enforces cohesion)
    assert "thin-narration" not in critique.STORY_GATE_CODES
    assert "no-narrator" not in critique.STORY_GATE_CODES


def test_short_mode_flags_too_many_shots() -> None:
    sp = Spine(genre="x", narrator="J")
    shots = [Shot(id=f"{i:02d}", role="escalation", subject_name="Jakob Fugger",
                  subject_appearance="x", action="a", voiceover=f"l{i}",
                  identify="Jakob Fugger — banker") for i in range(15)]
    t = Teaser(title="T", length_s=90, provider="veo", mode="short", spine=sp, shots=shots)
    codes = {f.code for f in critique.critique(t, providers.get("veo")).findings}
    assert "too-many-shots" in codes


def test_trailer_mode_still_gates_on_thin_dialogue() -> None:
    sp = Spine(dramatic_question="q", logline="l", want="w", opposing_force="f",
               emotional_arc="a", score_direction="s", genre="x", turn="t")
    t = Teaser(title="T", length_s=12, provider="veo", mode="trailer", spine=sp, shots=[
        Shot(id="01", role="hook", subject_name="J", subject_appearance="x", action="a"),
        Shot(id="02", role="button", subject_name="J", subject_appearance="x", action="b"),
    ])
    codes = {f.code for f in critique.critique(t, providers.get("veo")).findings}
    assert "thin-dialogue" in codes
