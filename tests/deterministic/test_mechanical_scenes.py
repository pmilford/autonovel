"""Tier-1 tests for `autonovel mechanical scenes` and the
split_scenes() helper.

The helper is the deterministic backbone for /autonovel:evaluate's
per-scene beat-coverage scoring (goal / conflict / disaster-or-decision
/ consequence). Without a stable per-scene index, the LLM judge has to
re-derive scene boundaries on every run and brief.md can't name weak
scenes by index. These tests lock the contract.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel.mechanical.scenes import split_scenes


def test_chapter_with_no_breaks_is_one_scene() -> None:
    text = "First sentence.\n\nSecond paragraph.\n"
    scenes = split_scenes(text)
    assert len(scenes) == 1
    assert scenes[0]["index"] == 1
    assert scenes[0]["word_count"] == 4
    assert scenes[0]["opening_line"] == "First sentence."
    assert scenes[0]["closing_line"] == "Second paragraph."


def test_three_scenes_split_by_triple_star() -> None:
    text = (
        "Scene one opens.\n\nScene one body.\n"
        "\n***\n\n"
        "Scene two opens.\n\nScene two body.\n"
        "\n***\n\n"
        "Scene three opens.\n\nScene three body.\n"
    )
    scenes = split_scenes(text)
    assert [s["index"] for s in scenes] == [1, 2, 3]
    assert "Scene one body" in scenes[0]["text"]
    assert "Scene two body" in scenes[1]["text"]
    assert "Scene three body" in scenes[2]["text"]
    assert scenes[0]["opening_line"] == "Scene one opens."
    assert scenes[2]["closing_line"] == "Scene three body."


def test_triple_dash_break_also_works() -> None:
    """Both `***` and `---` are accepted scene-break conventions
    (latex.py already treats both as scene breaks for typeset output;
    the splitter must match)."""
    text = "First scene.\n\n---\n\nSecond scene."
    scenes = split_scenes(text)
    assert len(scenes) == 2
    assert "First scene." in scenes[0]["text"]
    assert "Second scene." in scenes[1]["text"]


def test_yaml_frontmatter_is_stripped_before_splitting() -> None:
    """Chapter files start with `---\\n…\\n---\\n` YAML frontmatter.
    The closing `---` of the frontmatter must not register as a scene
    break, otherwise every chapter would have a phantom empty first
    scene plus the frontmatter as scene 0 fodder."""
    text = (
        "---\n"
        "book: test\n"
        "chapter: 1\n"
        "---\n"
        "Real opening sentence.\n"
        "\n***\n\n"
        "Second scene starts here.\n"
    )
    scenes = split_scenes(text)
    assert len(scenes) == 2
    assert "book: test" not in scenes[0]["text"]
    assert "chapter: 1" not in scenes[0]["text"]
    assert scenes[0]["opening_line"] == "Real opening sentence."
    assert "Second scene" in scenes[1]["text"]


def test_break_line_with_surrounding_whitespace_still_breaks() -> None:
    """`   ***   ` (with leading/trailing whitespace) is still a scene
    break. Real LLM-generated chapters often have stray indentation
    around the marker."""
    text = "First.\n\n  ***  \n\nSecond."
    scenes = split_scenes(text)
    assert len(scenes) == 2


def test_spaced_stars_still_break() -> None:
    """`* * *` (asterisks separated by spaces) is the convention some
    style guides prefer. Splitter accepts it."""
    text = "First.\n\n* * *\n\nSecond."
    scenes = split_scenes(text)
    assert len(scenes) == 2


def test_empty_scene_between_consecutive_breaks_is_dropped() -> None:
    """Two scene breaks in a row (`***\\n\\n***`) would otherwise
    create a zero-word phantom scene between them. Drop empty scenes
    so indices stay contiguous and meaningful."""
    text = "First.\n\n***\n\n***\n\nSecond."
    scenes = split_scenes(text)
    assert len(scenes) == 2
    assert [s["index"] for s in scenes] == [1, 2]


def test_chapter_opening_with_break_doesnt_create_phantom_scene_one() -> None:
    """A chapter that *opens* with a `***` (rare but possible) must
    not produce an empty scene 1 — that would make every other
    scene's index off-by-one."""
    text = "***\n\nReal first scene.\n"
    scenes = split_scenes(text)
    assert len(scenes) == 1
    assert scenes[0]["index"] == 1
    assert "Real first scene." in scenes[0]["text"]


def test_chapter_ending_with_break_doesnt_create_phantom_trailing_scene() -> None:
    text = "Only scene.\n\n***\n"
    scenes = split_scenes(text)
    assert len(scenes) == 1
    assert "Only scene." in scenes[0]["text"]


def test_word_count_matches_simple_split() -> None:
    text = "alpha beta gamma\n\n***\n\ndelta epsilon"
    scenes = split_scenes(text)
    assert scenes[0]["word_count"] == 3
    assert scenes[1]["word_count"] == 2


def test_long_opening_line_is_truncated_to_120_chars() -> None:
    """Compact scene index is the point of the JSON output — opening
    and closing lines that bloat over 120 chars are truncated with an
    ellipsis to keep the LLM-consumed JSON small."""
    long_line = "x" * 200
    text = long_line + "\n"
    scenes = split_scenes(text)
    assert len(scenes[0]["opening_line"]) == 120
    assert scenes[0]["opening_line"].endswith("…")


def test_horizontal_rule_inside_paragraph_is_not_a_break() -> None:
    """`---` inside a paragraph (e.g. a single hyphen-character line
    appearing mid-sentence due to a markdown rendering artifact)
    isn't a scene break unless it's on its own line. Real chapters
    don't typically have inline `---`; this test covers the
    accidental case."""
    text = "First sentence has --- a parenthetical.\n\nSecond sentence."
    scenes = split_scenes(text)
    assert len(scenes) == 1


# ---------------------------------------------------------- CLI roundtrip


def test_cli_emits_json_with_expected_shape(tmp_path: Path) -> None:
    chapter = tmp_path / "ch_01.md"
    chapter.write_text(
        "---\nchapter: 1\n---\n"
        "First scene body.\n\n***\n\n"
        "Second scene body.\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "scenes", str(chapter)],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["scene_count"] == 2
    assert payload["total_words"] == 6
    assert [s["index"] for s in payload["scenes"]] == [1, 2]
    # Default mode omits the heavy `text` field — the LLM judge
    # already has the chapter open.
    assert "text" not in payload["scenes"][0]


def test_cli_full_includes_prose(tmp_path: Path) -> None:
    chapter = tmp_path / "ch_02.md"
    chapter.write_text("Solo scene with words.\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "scenes",
         str(chapter), "--full"],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["scene_count"] == 1
    assert payload["scenes"][0]["text"] == "Solo scene with words."
