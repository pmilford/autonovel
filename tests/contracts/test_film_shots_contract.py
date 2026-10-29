"""Tier-2 contracts for the film stages after the screenplay: shot-list
(F3), storyboard, table-read and animatic (F4).

What each command promises the author, locked so a later edit can't
quietly drop it: the craft it reads, the mechanical checks it runs, the
critic or vision check in fresh conversations on CAMERA.md's own rubric,
the limits that keep a local machine safe, consent-free voices, and
nothing written outside `film/`.
"""

from __future__ import annotations

import re
from pathlib import Path

from autonovel.film import shots as sh
from autonovel.film import storyboard as sb
from autonovel.housekeeping import scaffold

REPO = Path(__file__).resolve().parents[2]
CAMERA = (scaffold.craft_template_dir() / "CAMERA.md").read_text(encoding="utf-8")
FLAT = " ".join(CAMERA.split())


def body(name: str) -> str:
    return " ".join((REPO / "commands" / f"{name}.md").read_text(encoding="utf-8").split())


# --------------------------------------------------------------- CAMERA.md

def test_camera_md_rubric_and_tests() -> None:
    dims = re.findall(r"^\| `([a-z_]+)` \|", CAMERA, re.MULTILINE)
    assert dims == ["coverage", "storytelling", "point_of_view", "geography", "motivated_movement",
                    "rhythm", "continuity", "light_and_period", "economy", "makeability"]
    for n in range(1, 13):
        assert f"**CT{n}**" in CAMERA, n
    assert "no dimension is below 7" in FLAT


def test_camera_md_teaches_the_schema_the_checker_enforces() -> None:
    for size in sh.SIZES:
        assert f"`{size}`" in CAMERA, size
    for word in ("line_side", "screen_direction", "eyeline.looks", "continuity_change", "crossing",
                 "timing.action_s", "timing.hold_s", "--retime"):
        assert word in FLAT, word
    # The timing heuristics it states are the ones the checker uses.
    assert f"lead (default {sh.DEFAULT_LEAD_S:g} s)" in FLAT
    assert f"tail ({sh.DEFAULT_TAIL_S:g} s)" in FLAT
    assert f"no insert or cutaway under {sh.MIN_SHOT_S['insert']:g} s" in FLAT
    assert f"no establishing view under {sh.MIN_SHOT_S['establishing']:g} s" in FLAT
    assert "regenerated at most twice" in FLAT and sb.MAX_REGENERATIONS == 2


def test_camera_md_says_prompts_are_positive() -> None:
    assert "Describe what is there, never what is not" in FLAT
    assert "no negative prompt field" in FLAT


# --------------------------------------------------------------- shot-list

def test_shot_list_reads_the_craft_and_the_bible() -> None:
    b = body("shot-list")
    assert "shared/craft/CAMERA.md" in b and "in full" in b
    assert "books/{book}/film/bible/look.yaml" in b
    assert "## On screen" in b


def test_shot_list_runs_the_checks_and_stamps() -> None:
    b = body("shot-list")
    assert "autonovel mechanical scene-lines" in b
    assert "autonovel mechanical shot-check" in b
    for flag in ("--retime", "--stamp", "--sheet"):
        assert flag in b, flag
    assert "exits 0" in b
    assert "never typed in" in b


def test_shot_list_critic_in_fresh_rounds_on_camera_md() -> None:
    b = body("shot-list")
    assert "fresh subagent" in b
    assert "§10" in b and "CT1–CT12" in b
    assert "no dimension below 7" in b
    assert "### Response" in b


def test_shot_list_writes_nothing_outside_film() -> None:
    assert "No script, scene list, bible or book file is written" in body("shot-list")


# --------------------------------------------------------------- storyboard

def test_storyboard_sheets_first_then_frames() -> None:
    b = body("storyboard")
    assert "Character sheets first" in b
    for view in ("front", "three_quarter", "profile"):
        assert view in b, view
    assert b.index("Character sheets first") < b.index("Write the frames")
    assert "approved: false" in b


def test_storyboard_prompts_positive_and_period_checked() -> None:
    b = body("storyboard")
    assert "positive only" in b and "no negative prompt" in b
    assert "not-at-this-date" in b
    assert "CAMERA.md §9" in b or "§9" in b


def test_storyboard_vision_check_and_regeneration_limit() -> None:
    b = body("storyboard")
    assert "fresh subagent" in b
    assert "autonovel mechanical keyframe-render" in b
    assert "autonovel mechanical keyframe-verdict" in b
    assert "autonovel mechanical keyframe-status" in b
    assert "at most twice" in b
    assert "Look at every frame yourself" in b or "look at every frame yourself" in b


def test_storyboard_machine_safety() -> None:
    b = body("storyboard")
    assert "--disable-pinned-memory" in b
    assert "One GPU job at a time" in b
    assert "--ram-limit" in b
    assert "No paid or keyed service" in b


# --------------------------------------------------------------- table-read

def test_table_read_voices_are_consent_free() -> None:
    b = body("table-read")
    assert "no person's recording is used" in b
    assert "written consent" in b and "film/consent/" in b
    assert "no real person, actor or singer is named" in b
    assert "consent" in b


def test_table_read_checks_every_take() -> None:
    b = body("table-read")
    assert "autonovel mechanical table-read" in b
    assert "transcriber" in b and "re-taken" in b
    assert "never matched" in b
    assert "One GPU job at a time" in b


# --------------------------------------------------------------- animatic

def test_animatic_needs_current_inputs_and_retimes() -> None:
    b = body("animatic")
    assert "autonovel mechanical shot-check" in b and "--retime" in b
    assert "line times from: table read" in b
    assert "autonovel mechanical keyframe-status" in b
    assert "autonovel mechanical animatic" in b


def test_animatic_viewer_sees_frames_and_transcript_only() -> None:
    b = body("animatic")
    assert "fresh subagent" in b
    assert "knows nothing of the book" in b
    assert "not to open the shot list" in b
    assert "±10%" in b


def test_engine_scripts_import_nothing_from_autonovel() -> None:
    from autonovel.film.engines import engine_path
    src = engine_path("voxcpm_lines").read_text(encoding="utf-8")
    assert "autonovel" not in "\n".join(l for l in src.splitlines() if l.startswith(("import", "from")))
