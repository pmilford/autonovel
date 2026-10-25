"""Tier-2: what the author decided or wrote survives a redesign and a pass.

Bug class (author, 2026-10-25, reading the fourth version of a book
re-designed from an earlier one):

  - "Is the front matter there, it got removed for no reason - why?"
    The redesign copied the art and plates but not the author's preface.
  - "Wells, bruges and strasbogh we decided to keep, why did you forget?"
    The decision lived in a report, not in design.md, and a say-once pass
    followed an older line of the places plan.
  - The old introduction opened on a historian's remark that no
    historian made.
"""

from __future__ import annotations

from pathlib import Path

from autonovel.housekeeping.next_actions import _missing_front_matter_actions

ROOT = Path(__file__).resolve().parents[2]


def _cmd(name: str) -> str:
    return " ".join((ROOT / "commands" / f"{name}.md").read_text(encoding="utf-8").split())


def test_redesign_copies_the_authors_preface() -> None:
    body = _cmd("design")
    assert "Copy `books/{from_book}/preface.md` too, unchanged" in body
    assert "`/autonovel:introduction`, `/autonovel:glossary` and `/autonovel:appendix`" in body


def test_introduction_keeps_a_redesigned_books_preface_and_names_its_sources() -> None:
    body = _cmd("introduction")
    assert "A re-designed book keeps the author's preface." in body
    assert "`redesign_of: <old>`" in body
    assert "unnamed authority" in body


def test_passes_never_change_names_the_author_decided() -> None:
    assert "never rename, unname or drop a place or a person" in _cmd("said-once")
    assert "A place or a person keeps the name the chapter gave it" in _cmd("revise")


def test_next_flags_a_preface_left_behind_by_a_redesign(tmp_path: Path) -> None:
    books = tmp_path / "books"
    old, new = books / "old", books / "new"
    (old).mkdir(parents=True)
    (old / "preface.md").write_text("# Preface\n\nWho was he?\n", encoding="utf-8")
    (new / "chapters").mkdir(parents=True)
    for n in (1, 2, 3):
        (new / "chapters" / f"ch_{n:02d}.md").write_text("---\nchapter: 1\n---\n\nText.\n")
    (new / "design.md").write_text("# Design\n\n- redesign_of: old\n", encoding="utf-8")
    [action] = _missing_front_matter_actions(new, "new")
    assert action.priority == "MEDIUM" and "preface" in action.title
    (new / "preface.md").write_text("# Preface\n\nWho was he?\n", encoding="utf-8")
    assert _missing_front_matter_actions(new, "new") == []
