"""Tier-1 tests for `mechanical/timeline.py` and the
`autonovel mechanical timeline-extract` CLI subcommand.

Locks the in-narrative date extractor (source 1 of the three-
source mixed timeline). The LLM-side referenced + context rows
are slash-command-body work; this module is the deterministic
mechanical pass.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.mechanical.timeline import (
    extract_in_narrative_dates,
    render_markdown,
)


def _make_chapter(book: Path, n: int, *,
                   story_time: str = "1492-08-03",
                   summary_story_time: str | None = None,
                   summary_plot: str = "Things happened.") -> None:
    chapters = book / "chapters"
    chapters.mkdir(parents=True, exist_ok=True)
    (chapters / f"ch_{n:02d}.md").write_text(
        f"---\nchapter: {n}\npov: POV\nstory_time: {story_time}\n"
        f"events: []\nstatus: drafted\nword_count: 1500\n---\n\n"
        f"Prose body for chapter {n}.\n",
        encoding="utf-8",
    )
    sm_st = summary_story_time or story_time
    (chapters / f"ch_{n:02d}.summary.md").write_text(
        f"**Plot:** {summary_plot}\n"
        f"**Cast on stage:** POV\n"
        f"**Story time:** {sm_st}\n",
        encoding="utf-8",
    )


# ----------------------------------------------------- extraction


def test_extracts_one_row_per_chapter(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _make_chapter(book, 1, story_time="1492-08-03",
                   summary_plot="Tommaso enters the apothecary.")
    _make_chapter(book, 2, story_time="1492-08-08",
                   summary_plot="Lucia arrives at the gate.")
    rows = extract_in_narrative_dates(book)
    assert len(rows) == 2
    assert rows[0].chapter == 1
    assert rows[0].date == "1492-08-03"
    assert "Tommaso" in rows[0].description
    assert rows[1].chapter == 2
    assert rows[1].date == "1492-08-08"
    assert all(r.source == "narrative" for r in rows)


def test_summary_story_time_overrides_frontmatter(tmp_path: Path) -> None:
    """Summary's `## Story time` is more specific than frontmatter
    for chapters that span multiple days."""
    book = tmp_path / "book"
    _make_chapter(book, 1,
                   story_time="1492-08",  # frontmatter: month range
                   summary_story_time="1492-08-12",  # summary: specific day
                   summary_plot="The fire.")
    rows = extract_in_narrative_dates(book)
    assert rows[0].date == "1492-08-12"


def test_year_only_dates_kept(tmp_path: Path) -> None:
    """Chapters with year-only story_time still get a row."""
    book = tmp_path / "book"
    _make_chapter(book, 1, story_time="1492",
                   summary_story_time="1492",
                   summary_plot="Some events.")
    rows = extract_in_narrative_dates(book)
    assert len(rows) == 1
    assert rows[0].date == "1492"


def test_chapter_without_story_time_skipped(tmp_path: Path) -> None:
    """No story_time + no summary date → row dropped (rather than
    inventing a placeholder)."""
    book = tmp_path / "book"
    chapters = book / "chapters"
    chapters.mkdir(parents=True)
    (chapters / "ch_01.md").write_text(
        "---\nchapter: 1\npov: POV\nstatus: drafted\nword_count: 1500\n---\n\n"
        "Prose.\n",
        encoding="utf-8",
    )
    rows = extract_in_narrative_dates(book)
    assert rows == []


def test_no_chapters_dir(tmp_path: Path) -> None:
    rows = extract_in_narrative_dates(tmp_path / "missing-book")
    assert rows == []


# ----------------------------------------------------- render


def test_render_markdown_sorts_by_date(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _make_chapter(book, 1, story_time="1492-09-01",
                   summary_plot="Late chapter.")
    _make_chapter(book, 2, story_time="1492-08-03",
                   summary_plot="Early chapter.")
    rows = extract_in_narrative_dates(book)
    md = render_markdown(rows)
    # 1492-08-03 comes before 1492-09-01 in the rendered output.
    assert md.index("1492-08-03") < md.index("1492-09-01")


def test_render_markdown_legend_block(tmp_path: Path) -> None:
    """Markers must be (1) typeset-safe — Unicode Geometric Shapes
    block, in every serif font; (2) visually distinct — three
    different shapes plus three different font weights so the
    category is visible at a glance even if a reader-eye sweep
    skips the label. User 2026-04-30 round 1 reported emoji
    didn't render in EB Garamond; round 3 reported the all-italic
    parenthetical replacements all looked the same."""
    book = tmp_path / "book"
    _make_chapter(book, 1)
    md = render_markdown(extract_in_narrative_dates(book))
    # Three distinct dingbat shapes.
    assert "◆" in md  # narrative (filled)
    assert "◇" in md  # referenced (open)
    assert "○" in md  # context (dot)
    # Three distinct font weights.
    assert "**◆ in story**" in md  # bold
    assert "*◇ referenced*" in md  # italic
    assert "○ context" in md       # plain
    # No emoji, no fallbacks-only-italic.
    assert "📖" not in md
    assert "🏛" not in md


def test_render_markdown_chapter_tag_present(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _make_chapter(book, 7, summary_plot="Mid-book event.")
    md = render_markdown(extract_in_narrative_dates(book))
    assert "(ch 7)" in md


def test_render_markdown_empty(tmp_path: Path) -> None:
    md = render_markdown([])
    assert "No dates found" in md


# ----------------------------------------------------- CLI


def test_cli_timeline_extract_markdown(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _make_chapter(book, 1, summary_plot="The opening.")
    _make_chapter(book, 2, story_time="1492-12-25",
                   summary_plot="Christmas day.")
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical",
         "timeline-extract", str(book)],
        capture_output=True, text=True, check=True,
    )
    assert "1492-12-25" in out.stdout
    assert "Christmas" in out.stdout
    assert "◆ in story" in out.stdout


def test_cli_timeline_extract_json(tmp_path: Path) -> None:
    book = tmp_path / "book"
    _make_chapter(book, 1, summary_plot="Event.")
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical",
         "timeline-extract", str(book), "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data["count"] == 1
    assert data["rows"][0]["source"] == "narrative"
