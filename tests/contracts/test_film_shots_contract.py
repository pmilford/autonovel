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
