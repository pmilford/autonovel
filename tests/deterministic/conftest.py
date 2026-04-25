from __future__ import annotations

import json
from pathlib import Path

import pytest

from autonovel.housekeeping import scaffold


@pytest.fixture
def series_root(tmp_path: Path) -> Path:
    """A real series at tmp_path/demo, created via the scaffolder."""
    result = scaffold.new_series(tmp_path / "demo", series_name="demo", genre="literary")
    return result.series.root


@pytest.fixture
def late_stage_book(tmp_path: Path) -> tuple[Path, str]:
    """A series fixture representing a late-stage book — multiple
    drafted chapters, paired summaries, eval logs, briefs, edit logs,
    pending canon entries, and a populated foundation. Used to catch
    bugs that only manifest at scale (the 2026-04-25 chapter-count
    regression hit `ch_*.md` glob also matching `ch_NN.summary.md`,
    which only happens once summaries exist alongside chapters).

    Returns `(series_root, book_name)`. Caller can extend further if
    needed.
    """
    res = scaffold.new_series(tmp_path / "novel-project", series_name="novel-project")
    scaffold.new_book(res.series, book_name="the-book", pov="POV")
    series = res.series.root
    book = "the-book"
    book_root = series / "books" / book

    # Foundation: write enough content to all five artefacts that
    # _is_populated accepts them (the fixture-detection guards we
    # built around the foundation gap).
    long = "Real content. " * 30
    (series / "shared" / "world.md").write_text(f"# World\n\n{long}\n", encoding="utf-8")
    (series / "shared" / "characters.md").write_text(f"# Characters\n\n{long}\n", encoding="utf-8")
    (series / "shared" / "canon.md").write_text(
        f"# Canon\n\nHard facts true across all books in this series.\n\n"
        f"- [Tommaso birthday] 1487-05-12\n"
        f"- [Mint fire] 1521-11-04\n"
        f"- [Council seats] Ten members, two-year terms.\n"
        f"- [Currency] Ducat = 24 grossi.\n"
        f"- [Plague return] every 3-5 years through the 1520s.\n",
        encoding="utf-8",
    )
    (book_root / "voice.md").write_text(f"# Voice\n\n{long}\n", encoding="utf-8")
    (book_root / "outline.md").write_text(f"# Outline\n\n{long}\n", encoding="utf-8")

    # Five drafted chapters with paired summaries — the realistic
    # mid-revision shape.
    chapters = book_root / "chapters"
    chapters.mkdir(exist_ok=True)
    for n in (1, 2, 3, 4, 5):
        (chapters / f"ch_{n:02d}.md").write_text(
            f"---\nbook: {book}\nchapter: {n}\npov: POV\nstory_time: 2020-01-{n:02d}\n"
            f"events: []\nstatus: drafted\nword_count: 3000\n---\n\n"
            + (f"Prose for chapter {n}. " * 100),
            encoding="utf-8",
        )
        (chapters / f"ch_{n:02d}.summary.md").write_text(
            f"Plot: chapter {n} happened. POV state: changed. Cast: POV. "
            f"Threads opened: one. Threads closed: zero. Story time: 2020-01-{n:02d}.",
            encoding="utf-8",
        )

    # Eval logs for two chapters (the "user has run evaluate on
    # chapters 1 and 2 but not yet 3-5" case).
    eval_dir = book_root / "eval_logs"
    eval_dir.mkdir(exist_ok=True)
    for n, score in [(1, 7.4), (2, 5.9)]:
        (eval_dir / f"ch{n:02d}_eval.json").write_text(
            json.dumps({"overall_score": score, "weakest_dimension": "pacing"}),
            encoding="utf-8",
        )

    # A brief for chapter 2 (which scored low and is mid-revision).
    briefs = book_root / "briefs"
    briefs.mkdir(exist_ok=True)
    (briefs / "ch02.md").write_text("# Brief for ch 2\n\n- Tighten pacing.\n", encoding="utf-8")

    # An adversarial-edit cuts file for chapter 1.
    edit_logs = book_root / "edit_logs"
    edit_logs.mkdir(exist_ok=True)
    (edit_logs / "ch01_cuts.json").write_text(
        json.dumps({"cuts": [], "overall_fat_percentage": 4}), encoding="utf-8",
    )

    # Pending canon with research-tagged entries.
    (book_root / "pending_canon.md").write_text(
        "# Pending\n\n- [Anselmo's age in 1492] 19 [research:italy-1450-1550]\n"
        "- [Lucia first appears] 1492-08-03 (from the-book ch_03)\n",
        encoding="utf-8",
    )

    return series, book
