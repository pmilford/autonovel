"""Tier-2: a cold reader's report is stamped with the text it read, and an
item the editor declines is recorded beside it, not counted open again.

Bug classes (2026-10-25): every cold-reader report on one book predated two
versions and two review rounds, and the gate counted their items as if a
reader had seen the text going to the author; and with no place to record
an editor's judgement that a reader was wrong about the book (a deliberate
mystery, a fact an earlier chapter gave), every scorer would count the item
open again and the gate could never pass.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _flat(rel: str) -> str:
    return re.sub(r"\s+", " ", (ROOT / rel).read_text(encoding="utf-8"))


def test_every_writer_of_a_cold_read_stamps_it() -> None:
    for rel in ("commands/first-read.md", "commands/draft.md", "commands/draft-pass.md"):
        assert "--report first_read --chapter" in _flat(rel), rel
    assert "_archive-first-read" in _flat("commands/first-read.md")


def test_the_editors_calls_are_honoured_by_every_reader_of_the_report() -> None:
    craft = _flat("src/autonovel/templates/series/shared/craft/FIRST-READER.md")
    assert "## Editor's calls" in craft and "declined" in craft
    evaluate = _flat("commands/evaluate.md")
    assert "Editor's calls" in evaluate and "declined_items" in evaluate
    assert "Editor's calls" in _flat("commands/brief.md")
    cycle = _flat("commands/review-cycle.md")
    assert "Editor's calls" in cycle and "first-read N --book {book}" in cycle
