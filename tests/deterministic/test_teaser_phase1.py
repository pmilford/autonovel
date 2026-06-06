"""Tier-1 tests for movie-teaser Phase 1: shot schema, beat planner,
prompt rendering, mechanical critique, and the CLI helpers.

Structure only — quality is judged by the LLM/vision critic in the
command bodies (feedback_avoid_brittle_python).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.teaser import beats, critique, providers, render_prompt
from autonovel.teaser import shots as shots_mod
from autonovel.teaser.shots import Shot, Teaser


def _good_shot(**kw) -> Shot:
    base = dict(
        id="S01", role="hook", duration_s=5.0, shot_size="wide",
        subject_name="JAKOB", subject_appearance="14yo, plain wool doublet",
        action="He looks up from the ledger", setting="Venice Rialto",
        lighting="torchlight", palette=["amber", "slate"], camera_movement="push_in",
        style="35mm film", mood="awe", negative_prompt="blurry",
        reference_image="refs/jakob.png",
    )
    base.update(kw)
    return Shot(**base)


# --------------------------- shots schema / IO ---------------------------


def test_shot_round_trips_through_dict() -> None:
    s = _good_shot(audio={"dialogue": [{"speaker": "JAKOB", "line": "Hi."}], "sfx": "bell"})
    s2 = Shot.from_dict(s.to_dict())
    assert s2.subject_name == "JAKOB"
    assert s2.subject_appearance == "14yo, plain wool doublet"
    assert s2.dialogue() == [{"speaker": "JAKOB", "line": "Hi."}]
    assert s2.palette == ["amber", "slate"]


def test_teaser_json_round_trip(tmp_path: Path) -> None:
    t = Teaser(title="X", length_s=30, provider="generic", shots=[_good_shot(), _good_shot(id="S02", role="button")])
    p = tmp_path / "teaser.json"
    shots_mod.dump(t, p)
    t2 = shots_mod.load(p)
    assert t2.title == "X"
    assert [s.id for s in t2.shots] == ["S01", "S02"]
    assert t2.total_duration_s() == 10.0


def test_validate_accepts_a_good_teaser() -> None:
    t = Teaser(title="X", shots=[_good_shot(), _good_shot(id="S02", role="button")])
    assert shots_mod.validate(t) == []


def test_validate_flags_hard_errors() -> None:
    t = Teaser(title="", shots=[
        Shot(id="", role="nonsense", duration_s=0, subject_name="", subject_appearance="", action=""),
        Shot(id="S01", role="hook", duration_s=4, subject_name="A", subject_appearance="x", action="y"),
        Shot(id="S01", role="hook", duration_s=4, subject_name="A", subject_appearance="x", action="y"),  # dup id
    ])
    problems = shots_mod.validate(t)
    joined = " ".join(problems)
    assert "title is empty" in joined
    assert "missing id" in joined
    assert "not in" in joined          # bad role
    assert "positive number" in joined  # duration 0
    assert "duplicate id" in joined


def test_validate_enforces_provider_clip_cap() -> None:
    # luma cap is 5s; a 10s shot must fail.
    t = Teaser(title="X", provider="luma", shots=[_good_shot(duration_s=10.0)])
    problems = shots_mod.validate(t, providers.get("luma"))
    assert any("exceeds luma native cap" in p for p in problems)


# ------------------------------- beats plan ------------------------------


def test_plan_scales_with_length_and_clamps_beats() -> None:
    short = beats.plan(30)
    long = beats.plan(180)
    assert short["shot_target"] < long["shot_target"]
    assert beats.plan(30)["beat_target"] >= 6        # min clamp
    assert beats.plan(600)["beat_target"] <= 20       # max clamp


def test_plan_respects_provider_clip_cap() -> None:
    p = beats.plan(90, provider="luma")  # 5s cap
    assert p["provider_clip_cap_s"] == 5.0
    assert p["hook_seconds"] <= 5.0
    assert p["avg_shot_s"] <= 5.0


# ----------------------------- render prompt -----------------------------


def test_render_prose_is_canonical_order() -> None:
    prose = render_prompt.render_prose(_good_shot())
    # framing precedes subject precedes action precedes setting.
    assert prose.index("Wide") < prose.index("JAKOB") < prose.index("looks up") < prose.index("Venice")
    assert "amber, slate palette" in prose


def test_render_markdown_includes_beat_and_negative() -> None:
    md = render_prompt.render_markdown(_good_shot(beat_note="the turn"), "generic")
    assert "*Beat:* the turn" in md
    assert "**Negative prompt**" in md
    assert "refs/jakob.png" in md


def test_render_markdown_marks_dialogue_for_silent_provider() -> None:
    s = _good_shot(audio={"dialogue": [{"speaker": "X", "line": "Hello."}]})
    md = render_prompt.render_markdown(s, "runway")  # runway has no native audio
    assert "no native audio" in md


# ------------------------------- critique --------------------------------


def test_critique_catches_appearance_drift() -> None:
    t = Teaser(title="X", shots=[
        _good_shot(id="S01", subject_appearance="young, plain doublet"),
        _good_shot(id="S02", role="button", subject_appearance="old, fur collar"),
    ])
    rep = critique.critique(t)
    assert any(f.code == "appearance-drift" for f in rep.findings)


def test_critique_flags_missing_hook_and_button() -> None:
    t = Teaser(title="X", shots=[_good_shot(id="S01", role="escalation")])
    codes = {f.code for f in critique.critique(t).findings}
    assert "no-hook" in codes
    assert "no-button" in codes


def test_critique_flags_audio_on_silent_provider() -> None:
    t = Teaser(title="X", provider="runway", shots=[
        _good_shot(id="S01", role="hook", audio={"sfx": "a bell"}),
        _good_shot(id="S02", role="button"),
    ])
    codes = {f.code for f in critique.critique(t, providers.get("runway")).findings}
    assert "audio-unsupported" in codes


def test_critique_clean_teaser_has_no_structural_flags() -> None:
    t = Teaser(title="X", length_s=10, shots=[
        _good_shot(id="S01", role="hook", duration_s=5.0),
        _good_shot(id="S02", role="button", duration_s=5.0),
    ])
    codes = {f.code for f in critique.critique(t).findings}
    # No appearance-drift (same string), hook+button present, length matches.
    assert "appearance-drift" not in codes
    assert "no-hook" not in codes
    assert "no-button" not in codes
    assert "length-mismatch" not in codes


# ------------------------------- CLI round-trips -------------------------


def _run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", *argv],
        capture_output=True, text=True,
    )


def test_cli_teaser_plan_json() -> None:
    out = _run("teaser-plan", "--length", "90", "--format", "json")
    assert out.returncode == 0
    data = json.loads(out.stdout)
    assert data["length_s"] == 90
    assert data["shot_target"] > 0


def test_cli_validate_and_critique(tmp_path: Path) -> None:
    t = Teaser(title="X", length_s=10, shots=[
        _good_shot(id="S01", role="hook", duration_s=5.0),
        _good_shot(id="S02", role="button", duration_s=5.0),
    ])
    p = tmp_path / "teaser.json"
    shots_mod.dump(t, p)
    val = _run("teaser-validate", str(p), "--format", "json")
    assert val.returncode == 0
    assert json.loads(val.stdout)["valid"] is True
    crit = _run("teaser-critique", str(p), "--format", "json")
    assert crit.returncode == 0
    assert "findings" in json.loads(crit.stdout)


def test_cli_validate_returns_nonzero_on_invalid(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text('{"title": "", "shots": []}', encoding="utf-8")
    val = _run("teaser-validate", str(p))
    assert val.returncode == 1  # invalid → nonzero so command bodies can branch


def test_cli_render_prompt(tmp_path: Path) -> None:
    t = Teaser(title="X", shots=[_good_shot(id="S01", role="hook")])
    p = tmp_path / "teaser.json"
    shots_mod.dump(t, p)
    out = _run("teaser-render-prompt", str(p), "--shot", "S01")
    assert out.returncode == 0
    assert "## Shot S01" in out.stdout
    assert "**Prompt**" in out.stdout


def test_cli_render_prompt_out_dir_writes_files(tmp_path: Path) -> None:
    t = Teaser(title="X", shots=[_good_shot(id="S01", role="hook"),
                                  _good_shot(id="S02", role="button")])
    p = tmp_path / "teaser.json"
    shots_mod.dump(t, p)
    out_dir = tmp_path / "shots"
    out = _run("teaser-render-prompt", str(p), "--out-dir", str(out_dir))
    assert out.returncode == 0
    assert (out_dir / "shot_S01.md").exists()
    assert (out_dir / "shot_S02.md").exists()
    assert "## Shot S01" in (out_dir / "shot_S01.md").read_text()
