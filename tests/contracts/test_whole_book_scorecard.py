"""Tier-2: the whole-book scorecard is wired from the study text to the judge.

The author asked (2026-10-25) where the whole-book reviews were and what
they checked: main plot, subplots, action and pace, character
development, location development, historical development and accuracy,
unexpected plot points, and what else. `evaluate --full` had fifteen
dimensions, none for subplots, pace across the book, secondary arcs,
setting that develops, accuracy or surprise. The researched criteria live
in EDITING.md §22; evaluate --full scores them, the genre guide adds the
historical pair, and the developmental edit counts the same evidence.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_COMMANDS = _ROOT / "commands"
_CRAFT = _ROOT / "src" / "autonovel" / "templates" / "series" / "shared" / "craft"

_AREAS = {
    "22.1": "turning_points",
    "22.2": "subplots",
    "22.3": "pace_distribution",
    "22.4": "secondary_arcs",
    "22.5": "setting_development",
    "22.7": "surprise",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_editing_has_the_scorecard_with_anchors_and_sources() -> None:
    text = _read(_CRAFT / "EDITING.md")
    assert "## §22 Measuring the whole book, area by area" in text
    for section, dim in _AREAS.items():
        assert f"### {section} " in text and f"`{dim}`" in text
    assert "### 22.6 " in text and "`history_accuracy`" in text
    assert "### 22.8 The smaller checks (`book_checks`)" in text
    part = text.split("## §22 Measuring the whole book", 1)[1]
    assert part.count("**Anchors") >= 7
    assert "[V]" in part and "[S]" in part and "[U]" not in part.replace("[U] is used", "")


def test_evaluate_full_scores_every_area_and_reads_the_study_text() -> None:
    body = _read(_COMMANDS / "evaluate.md")
    assert "EDITING.md` §22" in body
    for section, dim in _AREAS.items():
        assert f"`{dim}`" in body and f"§{section}" in body
    assert "`book_checks`" in body and "**Worst first:**" in body
    assert "structure_subscore + 1.0" in body


def test_historical_guide_gives_the_whole_book_pair_weights() -> None:
    guide = _read(_CRAFT / "genres" / "historical.md")
    assert "**`history_accuracy`** (weight 4)" in guide
    assert "**`history_development`** (weight 3)" in guide


def test_developmental_edit_counts_the_scorecard_evidence() -> None:
    body = _read(_COMMANDS / "developmental-edit.md")
    assert "EDITING.md` §22" in body and "promise ledger" in body
