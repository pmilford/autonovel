"""Tier-1 tests for `autonovel _tail-chapter`.

Replaces the LLM-side `Read offset/limit` hack that stalled author
testing on 2026-04-25 (drafter looped on retries when the chosen line
range overran EOF on a 146-line chapter). Helper must:

  - print exactly the last N words on stdout,
  - strip leading YAML frontmatter so the continuity quote is prose
    only,
  - exit zero with no output when the requested chapter doesn't
    exist (chapter 1 case — no prior chapter to quote).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from autonovel.housekeeping.scaffold import new_book, new_series


def _run(series_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "autonovel.cli", *args],
        cwd=series_root, capture_output=True, text=True,
    )


@pytest.fixture
def series_with_chapter(tmp_path: Path) -> tuple[Path, str, int]:
    res = new_series(tmp_path / "demo", series_name="demo")
    new_book(res.series, book_name="one")
    chapters = res.series.root / "books" / "one" / "chapters"
    chapters.mkdir(exist_ok=True)
    body = " ".join(f"word{i}" for i in range(1, 1501))  # 1500 words
    (chapters / "ch_02.md").write_text(
        "---\nbook: one\nchapter: 2\npov: Ana\nstory_time: 2020-01-02\n"
        "events: []\nstatus: drafted\nword_count: 1500\n---\n\n" + body + "\n",
        encoding="utf-8",
    )
    return res.series.root, "one", 2


def test_tail_chapter_returns_last_n_words(series_with_chapter):
    root, book, chapter = series_with_chapter
    r = _run(root, "_tail-chapter", "--book", book, "--chapter", str(chapter), "--words", "100")
    assert r.returncode == 0, r.stderr
    out = r.stdout.strip().split()
    assert len(out) == 100
    assert out == [f"word{i}" for i in range(1401, 1501)]


def test_tail_chapter_returns_all_words_when_smaller_than_request(series_with_chapter):
    root, book, chapter = series_with_chapter
    r = _run(root, "_tail-chapter", "--book", book, "--chapter", str(chapter), "--words", "5000")
    assert r.returncode == 0
    out = r.stdout.strip().split()
    assert len(out) == 1500


def test_tail_chapter_strips_frontmatter(series_with_chapter):
    root, book, chapter = series_with_chapter
    r = _run(root, "_tail-chapter", "--book", book, "--chapter", str(chapter), "--words", "1500")
    assert r.returncode == 0
    out = r.stdout
    # No frontmatter keys leak into the continuity quote.
    assert "book:" not in out
    assert "story_time:" not in out
    assert "status:" not in out
    assert "---" not in out


def test_tail_chapter_missing_chapter_is_silent_zero_exit(tmp_path: Path):
    res = new_series(tmp_path / "demo", series_name="demo")
    new_book(res.series, book_name="one")
    # No chapters drafted yet (chapter 1 case).
    r = _run(res.series.root, "_tail-chapter", "--book", "one", "--chapter", "1")
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_tail_chapter_empty_file_is_silent_zero_exit(tmp_path: Path):
    res = new_series(tmp_path / "demo", series_name="demo")
    new_book(res.series, book_name="one")
    chapters = res.series.root / "books" / "one" / "chapters"
    chapters.mkdir(exist_ok=True)
    (chapters / "ch_03.md").write_text("", encoding="utf-8")
    r = _run(res.series.root, "_tail-chapter", "--book", "one", "--chapter", "3")
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_tail_chapter_off_by_one_does_not_loop(tmp_path: Path):
    """The original bug: chapter has 146 lines, LLM asks for lines
    88-147 via Read offset/limit, fewer lines come back, retry. The
    helper avoids the issue by working in word-space, not line-space.
    Regression guard: ask for many more words than the file contains
    and verify single-shot success."""
    res = new_series(tmp_path / "demo", series_name="demo")
    new_book(res.series, book_name="one")
    chapters = res.series.root / "books" / "one" / "chapters"
    chapters.mkdir(exist_ok=True)
    # A 146-line chapter with realistic word distribution.
    lines = [" ".join(f"w{i}" for i in range(20)) for _ in range(146)]
    (chapters / "ch_02.md").write_text("\n".join(lines), encoding="utf-8")
    r = _run(res.series.root, "_tail-chapter", "--book", "one", "--chapter", "2", "--words", "1000")
    assert r.returncode == 0
    words = r.stdout.strip().split()
    assert len(words) == 1000
