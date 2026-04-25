"""Tier-3 smoke: mystery outline produces clue ledger.

Per REWRITE-PLAN §12 genre-specific test: `/autonovel:gen-outline`
produces an outline with ≥3 red herrings and ≥1 true clue per act.
Chapters that plant clues are tagged in a foreshadowing/clue ledger.
"""

from __future__ import annotations

import re

import pytest

from .conftest import run_command_in_runtime


FIXTURE_NAME = "tiny-series-mystery"
BOOK_NAME = "book-one"


@pytest.mark.smoke
@pytest.mark.genre("mystery")
def test_mystery_outline_has_clue_ledger(tmp_runtime_series) -> None:
    series = tmp_runtime_series(FIXTURE_NAME)

    result = run_command_in_runtime(
        runtime="claude",
        command=f"/autonovel:gen-outline --book {BOOK_NAME}",
        cwd=series.path,
        allowed_tools=["Read", "Write", "Bash"],
        timeout=900,
    )
    assert result.returncode == 0, (
        f"claude returned {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    outline = series.path / "books" / BOOK_NAME / "outline.md"
    assert outline.is_file(), "books/book-one/outline.md not written by gen-outline"
    text = outline.read_text(encoding="utf-8")
    lower = text.lower()

    # ≥3 distinct mentions of red herrings.
    red_herrings = re.findall(r"red[\s\-]?herring", lower)
    assert len(red_herrings) >= 3, (
        f"outline mentions {len(red_herrings)} red herrings; ≥3 required"
    )

    # Clue ledger / foreshadowing section present.
    assert any(
        marker in lower
        for marker in ("clue ledger", "foreshadow", "## clues", "## ledger")
    ), "outline missing a clue/foreshadowing ledger section"

    # ≥1 true clue per act — Act/Part 1/2/3 sections each carry "clue".
    act_pattern = re.compile(r"(?mi)^#{1,6}\s+(?:Act|Part)\s+(?:1|2|3|I{1,3})\b.*$")
    starts = [m.start() for m in act_pattern.finditer(text)]
    assert len(starts) >= 3, (
        f"outline has {len(starts)} act/part headers; ≥3 required"
    )
    starts.append(len(text))
    for i in range(3):
        section = text[starts[i] : starts[i + 1]].lower()
        assert "clue" in section, f"act/part {i + 1} has no clue line"
