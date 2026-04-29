"""Tier-1 tests for `autonovel.mechanical.period_register`."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.mechanical.period_register import (
    build_report,
    load_bans,
    render_markdown,
    scan_chapter,
)


def _seed_series(tmp_path: Path, *,
                  bans: list[str] | None = None,
                  chapters: dict[int, str] | None = None) -> Path:
    series = tmp_path / "series"
    book = series / "books" / "b"
    chapters_dir = book / "chapters"
    shared = series / "shared"
    chapters_dir.mkdir(parents=True)
    shared.mkdir(parents=True)
    if bans is not None:
        (shared / "period_bans.txt").write_text(
            "\n".join(bans) + "\n", encoding="utf-8")
    for n, prose in (chapters or {}).items():
        (chapters_dir / f"ch_{n:02d}.md").write_text(
            f"---\nchapter: {n}\n---\n\n{prose}\n", encoding="utf-8",
        )
    return book


# ---------------------------------------------------------- load_bans


def test_load_bans_strips_comments_and_blanks(tmp_path: Path) -> None:
    p = tmp_path / "bans.txt"
    p.write_text(
        "# Comment\n"
        "okay\n"
        "  spaced  \n"
        "\n"
        "trailing  # inline comment\n",
        encoding="utf-8",
    )
    assert load_bans(p) == ["okay", "spaced", "trailing"]


def test_load_bans_missing_returns_empty(tmp_path: Path) -> None:
    assert load_bans(tmp_path / "nope.txt") == []


# ---------------------------------------------------------- scan_chapter


def test_scan_chapter_word_boundary_case_insensitive() -> None:
    text = "---\n---\n\nThe okay one. OKAY again. okayness (suffix — no match)."
    report = scan_chapter(text, bans=["okay"])
    assert report.total == 2  # `okay` + `OKAY`; `okayness` doesn't match


def test_scan_chapter_strips_frontmatter() -> None:
    """Frontmatter should not contribute to hits."""
    text = "---\nchapter: 1\nokay: yes\n---\n\nPlain prose."
    report = scan_chapter(text, bans=["okay"])
    assert report.total == 0


def test_scan_chapter_empty_bans_zero_hits() -> None:
    text = "---\n---\n\nokay okay okay."
    report = scan_chapter(text, bans=[])
    assert report.total == 0


def test_scan_chapter_word_count_body_only() -> None:
    text = "---\nchapter: 1\n---\n\nFive words of body prose."
    report = scan_chapter(text, bans=[])
    assert report.word_count == 5


# ---------------------------------------------------------- build_report


def test_build_report_aggregates_summary(tmp_path: Path) -> None:
    book = _seed_series(tmp_path, bans=["okay", "alright"], chapters={
        1: "okay one.",
        2: "alright two. Okay three.",
        3: "alright alright alright.",
    })
    report = build_report(book)
    assert report.bans_count == 2
    # ch1: 1 (okay), ch2: 2 (alright + Okay), ch3: 3 (alright x3)
    assert [c.total for c in report.chapters] == [1, 2, 3]
    # Summary ranks worst offenders first.
    assert list(report.summary.keys())[0] == "alright"
    assert report.summary["alright"] == 4
    assert report.summary["okay"] == 2


def test_build_report_no_bans_file_yields_zero_hits(tmp_path: Path) -> None:
    book = _seed_series(tmp_path, bans=None, chapters={1: "prose."})
    report = build_report(book)
    assert report.bans_count == 0
    assert all(c.total == 0 for c in report.chapters)


def test_build_report_no_chapters(tmp_path: Path) -> None:
    book = _seed_series(tmp_path, bans=["okay"], chapters={})
    report = build_report(book)
    assert report.chapters == []


# ---------------------------------------------------------- render


def test_render_markdown_contains_summary_and_hits(tmp_path: Path) -> None:
    book = _seed_series(tmp_path, bans=["okay"], chapters={1: "okay one."})
    out = render_markdown(build_report(book), book="b")
    assert "Period register — b" in out
    assert "bans loaded: 1" in out
    assert "Worst offenders" in out
    assert "Chapter 1 hits" in out


def test_render_markdown_summary_only(tmp_path: Path) -> None:
    book = _seed_series(tmp_path, bans=["okay"], chapters={1: "okay one."})
    out = render_markdown(build_report(book), book="b", show_hits=False)
    assert "Worst offenders" in out
    assert "Chapter 1 hits" not in out


def test_render_markdown_no_bans(tmp_path: Path) -> None:
    book = _seed_series(tmp_path, bans=None, chapters={1: "prose."})
    out = render_markdown(build_report(book), book="b")
    assert "is missing or empty" in out


def test_render_markdown_no_chapters(tmp_path: Path) -> None:
    book = _seed_series(tmp_path, bans=["okay"], chapters={})
    out = render_markdown(build_report(book), book="b")
    assert "No chapters drafted" in out


# ---------------------------------------------------------- CLI


def test_cli_period_register_markdown(tmp_path: Path) -> None:
    book = _seed_series(tmp_path, bans=["okay"], chapters={1: "okay there."})
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "period-register",
         str(book)],
        capture_output=True, text=True, check=True,
    )
    assert "Period register" in proc.stdout
    assert "Worst offenders" in proc.stdout


def test_cli_period_register_json(tmp_path: Path) -> None:
    book = _seed_series(tmp_path, bans=["okay"],
                          chapters={1: "okay first.", 2: "no hits."})
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "period-register",
         str(book), "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["bans_count"] == 1
    assert payload["summary"] == {"okay": 1}
    assert len(payload["chapters"]) == 2
