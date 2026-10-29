"""Tier-2 contract for `/autonovel:screenplay` (film pipeline F1).

What the command promises the author, locked so a later edit can't
quietly drop it: the craft it reads, the mechanical check it runs, the
critic scored on SCREEN.md's own rubric, a cold reader who sees only the
script, every change from the book written down, no new named people,
and the genre's payload carried rather than cut.
"""

from __future__ import annotations

import re
from pathlib import Path

from autonovel.housekeeping import scaffold

REPO = Path(__file__).resolve().parents[2]
BODY = " ".join((REPO / "commands" / "screenplay.md").read_text(encoding="utf-8").split())
SCREEN = (scaffold.craft_template_dir() / "SCREEN.md").read_text(encoding="utf-8")


def test_reads_the_screen_craft_and_the_genre_guide() -> None:
    assert "shared/craft/SCREEN.md" in BODY
    assert "## On screen" in BODY and "## The promise" in BODY
    assert "voice.md" in BODY and "Parts 1 and 2" in BODY


def test_runs_fountain_check_and_stamps_the_chapters() -> None:
    assert "autonovel mechanical fountain-check" in BODY
    assert "--stamp" in BODY
    assert "exits 0" in BODY


def test_critic_uses_screen_md_rubric_in_fresh_rounds() -> None:
    assert "fresh subagent" in BODY
    assert "§8" in BODY and "SC1–SC12" in BODY
    assert "no dimension below 7" in BODY
    assert "### Response" in BODY


def test_cold_reader_sees_only_the_script() -> None:
    assert "knows nothing of the book" in BODY
    assert "not to open any other file" in BODY
    assert "§9" in BODY
    assert "must-fix" in BODY


def test_every_change_recorded_and_no_new_named_people() -> None:
    for move in ("CUT", "CONDENSE", "COMPRESS", "DISPLACE", "ALTER", "INVENT", "EXTERNALISE"):
        assert move in BODY, move
    assert "no new named person" in BODY.lower() or "no new named people" in BODY.lower()
    assert "pace alone is never the reason" in BODY


def test_first_minute_is_marked() -> None:
    assert "First minute:" in BODY
    assert "first minute to render" in BODY.lower()


def test_writes_nothing_in_the_book() -> None:
    assert "No chapter, canon, cast, design or outline file is written" in BODY


def test_screen_md_rubric_matches_what_the_command_and_checker_use() -> None:
    dims = re.findall(r"^\| `([a-z_]+)` \|", SCREEN, re.MULTILINE)
    assert dims == ["format", "scene_turns", "visual_storytelling", "dialogue", "clarity",
                    "fidelity", "history_on_screen", "period_register", "pace_and_length",
                    "sequence_arc"]
    for n in range(1, 13):
        assert f"**SC{n}**" in SCREEN, n
    # The scene-line grammar fountain-check parses is the one SCREEN.md teaches.
    assert "= <ID> | <source> | <turn>" in SCREEN
    assert "Roles:" in SCREEN and "First minute:" in SCREEN
