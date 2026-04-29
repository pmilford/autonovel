"""Tier-1 tests for `autonovel.mechanical.dashboard`."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel.mechanical.dashboard import (
    ChapterMetrics,
    DashboardReport,
    _aggregate,
    _count_scenes,
    _dialogue_density,
    _tension_drops,
    build_dashboard,
    render_markdown,
    sparkline,
)


# ---------------------------------------------------------- helpers


def _seed_chapter(book_root: Path, n: int, *, prose: str = "Default prose.",
                  word_count: int = 100, pov: str = "Tommaso") -> None:
    chapters = book_root / "chapters"
    chapters.mkdir(parents=True, exist_ok=True)
    (chapters / f"ch_{n:02d}.md").write_text(
        f"---\nbook: tiny\nchapter: {n}\npov: {pov}\nstory_time: 2020-01-{n:02d}\n"
        f"events: []\nstatus: drafted\nword_count: {word_count}\n---\n\n{prose}\n",
        encoding="utf-8",
    )


def _seed_summary(book_root: Path, n: int, cast: list[str]) -> None:
    chapters = book_root / "chapters"
    chapters.mkdir(parents=True, exist_ok=True)
    cast_str = "; ".join(c for c in cast)
    (chapters / f"ch_{n:02d}.summary.md").write_text(
        f"**Plot:** ch{n}.\n**Location:** somewhere.\n"
        f"**POV state:** changed.\n"
        f"**Cast on stage:** {cast_str}\n"
        f"**Threads opened:** one.\n**Threads closed:** zero.\n"
        f"**Story time:** 2020-01-{n:02d}.\n",
        encoding="utf-8",
    )


def _seed_eval(book_root: Path, n: int, score: float) -> None:
    eval_dir = book_root / "eval_logs"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / f"ch{n:02d}_eval.json").write_text(
        json.dumps({"overall_score": score}), encoding="utf-8"
    )


def _seed_full_eval(book_root: Path, ts: str, rows: list[dict]) -> None:
    eval_dir = book_root / "eval_logs"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / f"{ts}_full.json").write_text(
        json.dumps({"rows": rows}), encoding="utf-8"
    )


# ---------------------------------------------------------- mechanical extractors


def test_count_scenes_one_when_no_breaks() -> None:
    assert _count_scenes("Just one scene of prose.") == 1


def test_count_scenes_zero_for_empty() -> None:
    assert _count_scenes("") == 0
    assert _count_scenes("   \n  ") == 0


def test_count_scenes_with_asterisk_breaks() -> None:
    text = "Scene one.\n\n* * *\n\nScene two.\n\n***\n\nScene three."
    assert _count_scenes(text) == 3


def test_count_scenes_with_dash_breaks() -> None:
    text = "Scene one.\n\n---\n\nScene two."
    assert _count_scenes(text) == 2


def test_dialogue_density_basic() -> None:
    text = '"Hello," she said.\n\nShe walked away.\n\n"Goodbye."'
    # 2 of 3 paragraphs open with a quote.
    d = _dialogue_density(text)
    assert d is not None
    assert abs(d - 2 / 3) < 0.01


def test_dialogue_density_empty_returns_none() -> None:
    assert _dialogue_density("") is None
    assert _dialogue_density("\n\n\n") is None


# ---------------------------------------------------------- sparkline


def test_sparkline_constant_series_is_uniform() -> None:
    out = sparkline([5.0, 5.0, 5.0, 5.0])
    assert len(out) == 4
    assert len(set(out)) == 1


def test_sparkline_monotonic_series_is_monotonic() -> None:
    out = sparkline([1.0, 3.0, 5.0, 7.0, 9.0], lo=0.0, hi=10.0)
    # Each char's index in the block-set must rise.
    blocks = "▁▂▃▄▅▆▇█"
    indices = [blocks.index(c) for c in out]
    assert indices == sorted(indices)


def test_sparkline_none_renders_as_space() -> None:
    out = sparkline([1.0, None, 3.0], lo=0.0, hi=5.0)
    assert out[1] == " "


def test_sparkline_empty_series() -> None:
    assert sparkline([]) == ""


def test_sparkline_all_none_returns_spaces() -> None:
    out = sparkline([None, None, None])
    assert out == "   "


# ---------------------------------------------------------- aggregate


def test_aggregate_computes_basic_stats() -> None:
    rows = [
        ChapterMetrics(chapter=1, score=7.5, tension=6.0),
        ChapterMetrics(chapter=2, score=6.5, tension=7.0),
        ChapterMetrics(chapter=3, score=8.0, tension=8.0),
    ]
    a = _aggregate(rows, threshold=7.0)
    assert a is not None
    assert a.chapter_count == 3
    assert a.score_mean == 7.33
    assert a.score_min == 6.5
    assert a.score_max == 8.0
    assert a.tension_min == 6.0
    assert a.longest_sub_threshold_streak == 1


def test_aggregate_longest_streak() -> None:
    rows = [
        ChapterMetrics(chapter=1, score=8.0),
        ChapterMetrics(chapter=2, score=6.5),
        ChapterMetrics(chapter=3, score=6.0),
        ChapterMetrics(chapter=4, score=5.5),
        ChapterMetrics(chapter=5, score=8.0),
        ChapterMetrics(chapter=6, score=6.5),
    ]
    a = _aggregate(rows, threshold=7.0)
    assert a is not None
    assert a.longest_sub_threshold_streak == 3


def test_aggregate_empty_rows_returns_none() -> None:
    assert _aggregate([], threshold=7.0) is None


# ---------------------------------------------------------- tension drops


def test_tension_drop_detects_three_consecutive() -> None:
    rows = [
        ChapterMetrics(chapter=1, tension=6.0),
        ChapterMetrics(chapter=2, tension=7.0),
        ChapterMetrics(chapter=3, tension=7.5),
        ChapterMetrics(chapter=4, tension=7.0),
        ChapterMetrics(chapter=5, tension=6.5),
        ChapterMetrics(chapter=6, tension=6.0),
        ChapterMetrics(chapter=7, tension=7.0),
    ]
    drops = _tension_drops(rows)
    assert len(drops) == 1
    assert drops[0].start == 3
    assert drops[0].end == 6
    assert drops[0].values == [7.5, 7.0, 6.5, 6.0]


def test_tension_drop_ignores_two_consecutive() -> None:
    rows = [
        ChapterMetrics(chapter=1, tension=8.0),
        ChapterMetrics(chapter=2, tension=7.0),  # only 2 declines
        ChapterMetrics(chapter=3, tension=8.5),
    ]
    assert _tension_drops(rows) == []


def test_tension_drop_handles_none_gaps() -> None:
    rows = [
        ChapterMetrics(chapter=1, tension=8.0),
        ChapterMetrics(chapter=2, tension=7.0),
        ChapterMetrics(chapter=3, tension=None),  # gap breaks the run
        ChapterMetrics(chapter=4, tension=6.0),
        ChapterMetrics(chapter=5, tension=5.0),
    ]
    # No 3-long run on either side of the gap.
    assert _tension_drops(rows) == []


# ---------------------------------------------------------- build_dashboard


def test_build_dashboard_minimal_book(tmp_path: Path) -> None:
    book = tmp_path / "the-book"
    for n in (1, 2, 3):
        _seed_chapter(book, n, prose=f"Prose for {n}. " * 10)
        _seed_eval(book, n, 7.5)
    report = build_dashboard(book)
    assert len(report.rows) == 3
    assert all(r.score == 7.5 for r in report.rows)
    assert report.aggregate is not None
    assert report.aggregate.chapter_count == 3


def test_build_dashboard_pulls_tension_from_full_eval(tmp_path: Path) -> None:
    book = tmp_path / "the-book"
    for n in (1, 2):
        _seed_chapter(book, n)
    _seed_full_eval(book, "20260420_120000", rows=[
        {"chapter": 1, "tension": 6.5, "beats_hit": "4/4",
         "irreversible_change": 7.0},
        {"chapter": 2, "tension": 7.0, "beats_hit": "3/4"},
    ])
    report = build_dashboard(book)
    assert report.rows[0].tension == 6.5
    assert report.rows[0].beats_hit == "4/4"
    assert report.rows[0].irreversible_change == 7.0


def test_build_dashboard_picks_latest_full_eval(tmp_path: Path) -> None:
    book = tmp_path / "the-book"
    _seed_chapter(book, 1)
    _seed_full_eval(book, "20260101_120000", rows=[
        {"chapter": 1, "tension": 5.0},
    ])
    _seed_full_eval(book, "20260420_120000", rows=[
        {"chapter": 1, "tension": 8.0},
    ])
    report = build_dashboard(book)
    assert report.rows[0].tension == 8.0


def test_build_dashboard_cast_size_from_summary(tmp_path: Path) -> None:
    book = tmp_path / "b"
    _seed_chapter(book, 1)
    _seed_summary(book, 1, ["Tommaso", "Lucia", "Niccolò"])
    report = build_dashboard(book)
    assert report.rows[0].cast_size == 3


def test_build_dashboard_motif_density_from_motifs_file(tmp_path: Path) -> None:
    book = tmp_path / "b"
    (book).mkdir(parents=True)
    (book / "motifs.md").write_text("- bell: bell\n", encoding="utf-8")
    _seed_chapter(book, 1, prose="Bell rang. Bell tolled.")
    report = build_dashboard(book)
    assert report.rows[0].motif_density == 2


def test_build_dashboard_no_full_eval_emits_dashes(tmp_path: Path) -> None:
    book = tmp_path / "b"
    _seed_chapter(book, 1)
    report = build_dashboard(book)
    assert report.rows[0].tension is None
    assert report.rows[0].beats_hit is None
    assert "(missing" in report.sources["tension"]


def test_build_dashboard_no_chapters_returns_empty_report(tmp_path: Path) -> None:
    book = tmp_path / "b"
    book.mkdir()
    (book / "chapters").mkdir()
    report = build_dashboard(book)
    assert report.rows == []
    assert report.aggregate is None


# ---------------------------------------------------------- render


def test_render_markdown_includes_book_and_table(tmp_path: Path) -> None:
    book = tmp_path / "the-book"
    _seed_chapter(book, 1)
    _seed_eval(book, 1, 7.5)
    out = render_markdown(build_dashboard(book))
    assert "Dashboard — the-book" in out
    assert "| Ch |" in out
    assert "Score" in out


def test_render_markdown_omits_columns_with_no_data(tmp_path: Path) -> None:
    book = tmp_path / "b"
    _seed_chapter(book, 1)
    out = render_markdown(build_dashboard(book))
    # No score → no Score column.
    assert "Score" not in out.split("\n")[2]  # header line


def test_render_markdown_marks_low_scores(tmp_path: Path) -> None:
    book = tmp_path / "b"
    _seed_chapter(book, 1)
    _seed_eval(book, 1, 6.0)  # below default threshold
    out = render_markdown(build_dashboard(book), threshold=7.0)
    assert "⚠" in out


def test_render_markdown_emits_tension_drop_block(tmp_path: Path) -> None:
    book = tmp_path / "b"
    for n in range(1, 5):
        _seed_chapter(book, n)
    _seed_full_eval(book, "20260420_120000", rows=[
        {"chapter": 1, "tension": 8.0},
        {"chapter": 2, "tension": 7.0},
        {"chapter": 3, "tension": 6.0},
        {"chapter": 4, "tension": 5.0},
    ])
    out = render_markdown(build_dashboard(book))
    assert "Tension drops" in out
    assert "revision-pass" in out


def test_render_markdown_no_chapters_message(tmp_path: Path) -> None:
    book = tmp_path / "b"
    book.mkdir()
    (book / "chapters").mkdir()
    out = render_markdown(build_dashboard(book))
    assert "No chapters drafted" in out


# ---------------------------------------------------------- CLI round-trip


def test_cli_dashboard_markdown(tmp_path: Path) -> None:
    book = tmp_path / "the-book"
    _seed_chapter(book, 1, prose="Prose. " * 50)
    _seed_eval(book, 1, 7.2)
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "dashboard", str(book)],
        capture_output=True, text=True, check=True,
    )
    assert "Dashboard — the-book" in proc.stdout


def test_cli_dashboard_json(tmp_path: Path) -> None:
    book = tmp_path / "b"
    _seed_chapter(book, 1)
    _seed_eval(book, 1, 7.0)
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "dashboard",
         str(book), "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["book"] == "b"
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["score"] == 7.0


def test_cli_dashboard_threshold_flag(tmp_path: Path) -> None:
    book = tmp_path / "b"
    _seed_chapter(book, 1)
    _seed_eval(book, 1, 6.0)
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "dashboard",
         str(book), "--threshold", "8.0", "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["aggregate"]["threshold"] == 8.0
    assert payload["aggregate"]["longest_sub_threshold_streak"] == 1
