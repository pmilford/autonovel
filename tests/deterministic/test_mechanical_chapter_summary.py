"""Tier-1 tests for `autonovel mechanical chapter-summary`.

Locks the per-chapter index pulled from frontmatter + summary.md +
latest eval log. The /autonovel:chapter-summary command relies on
this helper for the one-line-per-chapter table writers reach for
when asking "which chapters happen in <date range>?" or "where
does <character> appear?".
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.mechanical.chapter_summary import (
    render_markdown_table,
    summarize_chapters,
)


def _make_book(tmp_path: Path) -> Path:
    book = tmp_path / "book"
    (book / "chapters").mkdir(parents=True)
    (book / "eval_logs").mkdir(parents=True)
    return book


def _make_chapter(book: Path, num: int, *, pov: str = "Tommaso",
                  story_time: str = "1521-12-04",
                  body: str = "Real prose body.",
                  word_count: int = 3200,
                  status: str = "drafted") -> None:
    (book / "chapters" / f"ch_{num:02d}.md").write_text(
        f"---\n"
        f"book: tiny\n"
        f"chapter: {num}\n"
        f"pov: {pov}\n"
        f"story_time: {story_time}\n"
        f"events: []\n"
        f"status: {status}\n"
        f"word_count: {word_count}\n"
        f"---\n"
        f"# Chapter {num}: A Title\n\n"
        f"{body}\n",
        encoding="utf-8",
    )


def _make_summary(book: Path, num: int, *, plot: str,
                  cast: str, story_time: str = "1521-12-04",
                  location: str | None = None) -> None:
    parts = [f"**Plot:** {plot}\n"]
    if location is not None:
        parts.insert(0, f"**Location:** {location}\n")
    parts.extend([
        f"**POV state:** Tommaso now suspects Niccolò.\n",
        f"**Cast on stage:** {cast}\n",
        f"**Threads opened:** the missing ledger.\n",
        f"**Threads closed:** —\n",
        f"**Story time:** {story_time}\n",
    ])
    (book / "chapters" / f"ch_{num:02d}.summary.md").write_text(
        "\n".join(parts), encoding="utf-8",
    )


def _make_eval(book: Path, num: int, score: float,
               timestamp: str = "20260425_154000") -> None:
    (book / "eval_logs" / f"{timestamp}_ch{num:02d}.json").write_text(
        json.dumps({"overall_score": score, "raw_judge_score": score}),
        encoding="utf-8",
    )


def test_basic_three_chapter_book(tmp_path: Path) -> None:
    book = _make_book(tmp_path)
    _make_chapter(book, 1, story_time="1521-12-04")
    _make_chapter(book, 2, story_time="1521-12-08", pov="Lucia")
    _make_chapter(book, 3, story_time="1521-12-15")
    _make_summary(book, 1, plot="Fire at the apothecary; saltpeter found.",
                  cast="Tommaso — POV; Niccolò — first appearance",
                  story_time="1521-12-04")
    _make_summary(book, 2, plot="Council of Ten convenes; Lucia accused.",
                  cast="Lucia — POV; Marco; Tommaso",
                  story_time="1521-12-08")
    _make_eval(book, 1, 7.4)
    _make_eval(book, 2, 6.9)
    _make_eval(book, 3, 7.1)

    rows = summarize_chapters(book)
    assert [r.chapter for r in rows] == [1, 2, 3]
    assert rows[0].pov == "Tommaso"
    assert rows[1].pov == "Lucia"
    assert rows[0].story_time == "1521-12-04"
    assert rows[0].plot == "Fire at the apothecary; saltpeter found."
    assert rows[0].cast == ["Tommaso", "Niccolò"]
    assert rows[1].cast == ["Lucia", "Marco", "Tommaso"]
    assert rows[0].score == 7.4
    assert rows[1].score == 6.9
    assert rows[2].score == 7.1


def test_chapter_without_summary_falls_back_to_dashes(tmp_path: Path) -> None:
    """A chapter that's been drafted but never summarised should
    appear in the table with `—` in the cast/plot columns — never
    silently excluded. (Common state for chapters drafted before
    summary.md became standard.)"""
    book = _make_book(tmp_path)
    _make_chapter(book, 1)
    rows = summarize_chapters(book)
    assert len(rows) == 1
    assert rows[0].plot is None
    assert rows[0].cast == []
    # Frontmatter fields still populated.
    assert rows[0].pov == "Tommaso"
    assert rows[0].story_time == "1521-12-04"
    assert rows[0].word_count == 3200


def test_chapter_without_eval_shows_score_none(tmp_path: Path) -> None:
    book = _make_book(tmp_path)
    _make_chapter(book, 1)
    rows = summarize_chapters(book)
    assert rows[0].score is None


def test_latest_eval_wins_over_older_one(tmp_path: Path) -> None:
    """When multiple eval logs exist for the same chapter, the
    latest by filename timestamp wins. Real books have many eval
    logs because every revise + evaluate cycle writes a fresh one."""
    book = _make_book(tmp_path)
    _make_chapter(book, 1)
    _make_eval(book, 1, 6.0, timestamp="20260424_100000")
    _make_eval(book, 1, 7.5, timestamp="20260425_180000")  # later
    _make_eval(book, 1, 6.8, timestamp="20260424_180000")  # in between
    rows = summarize_chapters(book)
    assert rows[0].score == 7.5


def test_summary_story_time_overrides_frontmatter_story_time(tmp_path: Path) -> None:
    """The summary's Story time tends to be more specific than the
    frontmatter's (which is often a range). Prefer summary."""
    book = _make_book(tmp_path)
    _make_chapter(book, 1, story_time="1521-12-04 to 1521-12-12")
    _make_summary(book, 1, plot="X.", cast="A", story_time="1521-12-08")
    rows = summarize_chapters(book)
    assert rows[0].story_time == "1521-12-08"


def test_plot_truncates_to_first_sentence(tmp_path: Path) -> None:
    book = _make_book(tmp_path)
    _make_chapter(book, 1)
    _make_summary(
        book, 1,
        plot="First sentence ends here. Second sentence shouldn't appear.",
        cast="A",
    )
    rows = summarize_chapters(book)
    assert rows[0].plot == "First sentence ends here."


def test_cast_strips_role_descriptors(tmp_path: Path) -> None:
    """Cast on stage entries look like `Tommaso — POV; Niccolò —
    first appearance, declined to speak`. We want just the names."""
    book = _make_book(tmp_path)
    _make_chapter(book, 1)
    _make_summary(
        book, 1,
        plot="X.",
        cast="Tommaso — POV; Niccolò — first appearance, declined; Marco",
    )
    rows = summarize_chapters(book)
    assert rows[0].cast == ["Tommaso", "Niccolò", "Marco"]


def test_chapter_files_not_matching_pattern_are_skipped(tmp_path: Path) -> None:
    """Adjunct files (.summary.md, .draft.md) MUST NOT be parsed as
    chapter files — that would double-count. Same exclusion the
    typeset and ePub paths use via iter_chapter_files()."""
    book = _make_book(tmp_path)
    _make_chapter(book, 1)
    _make_summary(book, 1, plot="X.", cast="A")
    rows = summarize_chapters(book)
    assert len(rows) == 1
    assert rows[0].chapter == 1


def test_word_count_falls_back_when_frontmatter_missing(tmp_path: Path) -> None:
    """A chapter drafted before word_count became standard should
    still get a word count via fallback (real splitting of body)."""
    book = _make_book(tmp_path)
    body = "alpha beta gamma delta epsilon"
    (book / "chapters" / "ch_01.md").write_text(
        "---\nbook: tiny\nchapter: 1\npov: Tommaso\nstory_time: 1521-12-04\n"
        "events: []\nstatus: drafted\n---\n"
        "# Chapter 1\n\n" + body + "\n",
        encoding="utf-8",
    )
    rows = summarize_chapters(book)
    assert rows[0].word_count == 5


# ----------------------------------------------------- markdown render


def test_render_table_basic(tmp_path: Path) -> None:
    book = _make_book(tmp_path)
    _make_chapter(book, 1)
    _make_summary(book, 1, plot="Fire at the apothecary.",
                  cast="Tommaso, Niccolò")
    _make_eval(book, 1, 7.4)
    rows = summarize_chapters(book)
    table = render_markdown_table(rows)
    assert "| Ch | Date" in table
    # Score column is renamed to Sco and tightened.
    assert "| Sco |" in table
    assert "Tommaso" in table
    assert "7.4" in table
    assert "Fire at the apothecary." in table


def test_location_is_parsed_and_prepended_to_plot(tmp_path: Path) -> None:
    """When the summary carries a Location field, the helper exposes
    it both on the row dict and in the rendered table — bolded and
    prepended to the Plot column with `**Loc** — plot` so a writer
    can scan the Plot column for "Venice" / "Augsburg" without
    needing a separate Location column."""
    book = _make_book(tmp_path)
    _make_chapter(book, 1)
    _make_summary(book, 1, plot="Fire at the apothecary.",
                  cast="Tommaso", location="Venice / Rialto")
    rows = summarize_chapters(book)
    assert rows[0].location == "Venice / Rialto"
    table = render_markdown_table(rows)
    assert "**Venice / Rialto** — Fire at the apothecary." in table


def test_chapter_without_location_falls_back_to_plot_only(tmp_path: Path) -> None:
    """Older summaries (written before the Location field shipped)
    must still render — the Plot column shows just plot, no
    location prefix."""
    book = _make_book(tmp_path)
    _make_chapter(book, 1)
    _make_summary(book, 1, plot="Fire at the apothecary.",
                  cast="Tommaso")  # no location
    rows = summarize_chapters(book)
    assert rows[0].location is None
    table = render_markdown_table(rows)
    # Plot still rendered; no `**…** —` prefix.
    assert "Fire at the apothecary." in table
    # Specifically: no bolded location marker before the plot text.
    line = [ln for ln in table.splitlines() if "Fire at the apothecary." in ln][0]
    assert "** —" not in line


def test_render_table_handles_no_chapters(tmp_path: Path) -> None:
    book = _make_book(tmp_path)
    rows = summarize_chapters(book)
    table = render_markdown_table(rows)
    assert "No chapters drafted yet" in table


def test_render_table_truncates_long_cast(tmp_path: Path) -> None:
    book = _make_book(tmp_path)
    _make_chapter(book, 1)
    _make_summary(
        book, 1, plot="X.",
        cast="; ".join(f"Char{i}" for i in range(20)),
    )
    rows = summarize_chapters(book)
    table = render_markdown_table(rows)
    # Cast column is bounded — should not blow row width.
    assert "…" in table


# ----------------------------------------------------- CLI roundtrip


def test_cli_markdown_default(tmp_path: Path) -> None:
    book = _make_book(tmp_path)
    _make_chapter(book, 1)
    _make_summary(book, 1, plot="Fire.", cast="Tommaso")
    _make_eval(book, 1, 7.0)
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "chapter-summary",
         str(book)],
        check=True, capture_output=True, text=True,
    )
    assert "| Ch | Date" in proc.stdout
    assert "Tommaso" in proc.stdout


def test_cli_json_format(tmp_path: Path) -> None:
    book = _make_book(tmp_path)
    _make_chapter(book, 1)
    _make_summary(book, 1, plot="Fire.", cast="Tommaso")
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "chapter-summary",
         str(book), "--format", "json"],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["chapter_count"] == 1
    assert payload["rows"][0]["chapter"] == 1
    assert payload["rows"][0]["pov"] == "Tommaso"
    assert payload["rows"][0]["plot"] == "Fire."
