"""Tier-1 tests for `mechanical/chapter_titles.py` and the
`autonovel mechanical chapter-titles` CLI subcommand.

Locks the title-source detection (frontmatter / heading-only /
missing) so the next-actions LOW signal and the
extract-chapter-titles slash-command both see the same shape.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.mechanical.chapter_titles import (
    inspect_titles,
    render_markdown,
)


def _make_chapters(tmp_path: Path) -> Path:
    book = tmp_path / "book"
    chapters = book / "chapters"
    chapters.mkdir(parents=True)
    return book


def _make_chapter(book: Path, n: int, *,
                   title: str | None = None,
                   heading: str | None = None) -> Path:
    parts = ["---", f"chapter: {n}", f"pov: POV"]
    if title is not None:
        parts.append(f"title: {title}")
    parts.extend(["status: drafted", "word_count: 1500", "---", ""])
    if heading:
        parts.append(f"# {heading}")
        parts.append("")
    parts.append("Prose body.")
    path = book / "chapters" / f"ch_{n:02d}.md"
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


# ----------------------------------------------------- detection


def test_inspect_detects_frontmatter_title(tmp_path: Path) -> None:
    book = _make_chapters(tmp_path)
    _make_chapter(book, 1, title="The Apothecary's Mortar")
    report = inspect_titles(book)
    assert report.total == 1
    assert report.with_title == 1
    assert report.missing == []
    assert report.heading_only == []
    assert report.rows[0].source == "frontmatter"
    assert report.rows[0].title == "The Apothecary's Mortar"


def test_inspect_detects_heading_only(tmp_path: Path) -> None:
    """No frontmatter title but a `# Heading` → source 'heading'.
    Typeset still renders these correctly via the fallback path."""
    book = _make_chapters(tmp_path)
    _make_chapter(book, 1, heading="Salt and Saltpeter")
    report = inspect_titles(book)
    assert report.rows[0].source == "heading"
    assert report.rows[0].title == "Salt and Saltpeter"
    assert report.heading_only == [1]
    assert report.missing == []


def test_inspect_detects_missing(tmp_path: Path) -> None:
    """No frontmatter title and no heading → source 'missing'."""
    book = _make_chapters(tmp_path)
    _make_chapter(book, 1)
    report = inspect_titles(book)
    assert report.rows[0].source == "missing"
    assert report.rows[0].title == ""
    assert report.missing == [1]


def test_inspect_mixed_book(tmp_path: Path) -> None:
    book = _make_chapters(tmp_path)
    _make_chapter(book, 1, title="Frontmatter Title")
    _make_chapter(book, 2, heading="Heading Title")
    _make_chapter(book, 3)  # missing
    _make_chapter(book, 4, title="Another Frontmatter")
    report = inspect_titles(book)
    assert report.total == 4
    assert report.with_title == 3
    assert report.missing == [3]
    assert report.heading_only == [2]


def test_inspect_no_chapters_dir(tmp_path: Path) -> None:
    """Book without a chapters/ directory → empty report (not
    crash)."""
    report = inspect_titles(tmp_path / "no-such-book")
    assert report.rows == []
    assert report.total == 0


# ----------------------------------------------------- render


def test_render_markdown_lists_each_status(tmp_path: Path) -> None:
    book = _make_chapters(tmp_path)
    _make_chapter(book, 1, title="A")
    _make_chapter(book, 2, heading="B")
    _make_chapter(book, 3)
    md = render_markdown(inspect_titles(book))
    assert "frontmatter" in md
    assert "Heading" in md
    assert "missing" in md
    # Action plan when there are missing titles.
    assert "extract-chapter-titles" in md
    assert "--chapters 3" in md


def test_render_markdown_empty(tmp_path: Path) -> None:
    md = render_markdown(inspect_titles(tmp_path / "nope"))
    assert "No chapter files" in md


def test_render_markdown_no_action_plan_when_clean(tmp_path: Path) -> None:
    book = _make_chapters(tmp_path)
    _make_chapter(book, 1, title="A")
    _make_chapter(book, 2, title="B")
    md = render_markdown(inspect_titles(book))
    assert "Backfill missing titles" not in md


# ----------------------------------------------------- CLI round-trip


def test_cli_chapter_titles_markdown(tmp_path: Path) -> None:
    book = _make_chapters(tmp_path)
    _make_chapter(book, 1, title="A")
    _make_chapter(book, 2)
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "chapter-titles",
         str(book)],
        capture_output=True, text=True, check=True,
    )
    assert "missing" in out.stdout.lower()
    assert "extract-chapter-titles" in out.stdout


def test_cli_chapter_titles_json(tmp_path: Path) -> None:
    book = _make_chapters(tmp_path)
    _make_chapter(book, 1, title="A")
    _make_chapter(book, 2)
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "chapter-titles",
         str(book), "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data["total"] == 2
    assert data["with_title"] == 1
    assert data["missing"] == [2]
