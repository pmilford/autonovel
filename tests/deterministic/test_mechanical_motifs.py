"""Tier-1 tests for the per-chapter motif tracker
(`autonovel.mechanical.motifs`)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel.mechanical.motifs import (
    Motif,
    build_report,
    parse_motifs_file,
    render_markdown,
    scan_chapter,
)


# ---------------------------------------------------------- parse_motifs_file


def test_parse_motifs_file_basic(tmp_path: Path) -> None:
    p = tmp_path / "motifs.md"
    p.write_text(
        "# Motifs\n\n"
        "- bells: bell, bells, ringing\n"
        "- mortar: mortar, pestle, herb, herbs\n",
        encoding="utf-8",
    )
    motifs = parse_motifs_file(p)
    assert [m.slug for m in motifs] == ["bells", "mortar"]
    assert motifs[0].keywords == ["bell", "bells", "ringing"]
    assert motifs[1].keywords == ["mortar", "pestle", "herb", "herbs"]


def test_parse_motifs_file_missing_returns_empty(tmp_path: Path) -> None:
    assert parse_motifs_file(tmp_path / "nope.md") == []


def test_parse_motifs_file_skips_prose_lines(tmp_path: Path) -> None:
    """Bullet shape is required — commentary in the file is fine."""
    p = tmp_path / "motifs.md"
    p.write_text(
        "# Motifs\n\nThe central images of the book.\n\n"
        "- bells: bell, bells\n\n"
        "Add new motifs as the writer notices them in voice-discovery.\n"
        "- river: river, current\n",
        encoding="utf-8",
    )
    motifs = parse_motifs_file(p)
    assert [m.slug for m in motifs] == ["bells", "river"]


def test_parse_motifs_file_skips_empty_keyword_list(tmp_path: Path) -> None:
    p = tmp_path / "motifs.md"
    p.write_text("- bells:   \n", encoding="utf-8")
    assert parse_motifs_file(p) == []


def test_parse_motifs_file_dedupes_slug(tmp_path: Path) -> None:
    """Two bullets for the same slug → first wins, rest ignored."""
    p = tmp_path / "motifs.md"
    p.write_text(
        "- bells: bell\n"
        "- bells: chime, peal\n",
        encoding="utf-8",
    )
    motifs = parse_motifs_file(p)
    assert len(motifs) == 1
    assert motifs[0].keywords == ["bell"]


# ---------------------------------------------------------- scan_chapter


def test_scan_chapter_word_boundary() -> None:
    """`bell` must NOT match `bellhop`. `bells` must match `bells.`"""
    motifs = [Motif(slug="bells", keywords=["bell", "bells"])]
    text = "The bell rang. Bellhop arrived. Bells, bells, bells."
    wc, counts = scan_chapter(text, motifs)
    assert counts["bells"] == 4  # bell + Bells x3
    assert wc > 0


def test_scan_chapter_strips_frontmatter() -> None:
    """YAML frontmatter must not contribute to motif counts — a chapter
    whose `events:` field includes the word `bell` shouldn't inflate
    the bell count."""
    motifs = [Motif(slug="bells", keywords=["bell"])]
    text = (
        "---\n"
        "chapter: 1\n"
        "events: [bell-toll, bell-broken]\n"
        "---\n\n"
        "The morning began silently."
    )
    wc, counts = scan_chapter(text, motifs)
    assert counts["bells"] == 0


def test_scan_chapter_case_insensitive() -> None:
    motifs = [Motif(slug="bells", keywords=["bell"])]
    text = "BELL Bell bell bELL"
    _, counts = scan_chapter(text, motifs)
    assert counts["bells"] == 4


# ---------------------------------------------------------- build_report


def _populate_book(book_root: Path, *, n_chapters: int,
                    motif_text: str, prose_per_chapter: dict[int, str]) -> None:
    book_root.mkdir(parents=True, exist_ok=True)
    (book_root / "motifs.md").write_text(motif_text, encoding="utf-8")
    chapters = book_root / "chapters"
    chapters.mkdir(exist_ok=True)
    for n in range(1, n_chapters + 1):
        (chapters / f"ch_{n:02d}.md").write_text(
            f"---\nchapter: {n}\n---\n\n" + prose_per_chapter.get(n, "Empty chapter."),
            encoding="utf-8",
        )


def test_build_report_emits_one_row_per_chapter(tmp_path: Path) -> None:
    book = tmp_path / "b"
    _populate_book(book, n_chapters=4, motif_text="- bells: bell\n",
                    prose_per_chapter={
                        1: "The bell rang twice.",
                        2: "Silence; no bells today.",
                        3: "Bell. Bell. Bell.",
                        4: "Quiet morning, bell free.",
                    })
    report = build_report(book)
    assert len(report.rows) == 4
    assert report.rows[0].counts["bells"] == 1
    # ch02 contains "bells" → matches the bell keyword (word-boundary
    # actually does NOT match because keyword is "bell" not "bells");
    # bells is plural → no match. Confirm.
    assert report.rows[1].counts["bells"] == 0
    assert report.rows[2].counts["bells"] == 3
    assert report.rows[3].counts["bells"] == 1  # `bell free` includes "bell"


def test_build_report_back_half_warning_fires_on_drop(tmp_path: Path) -> None:
    book = tmp_path / "b"
    _populate_book(book, n_chapters=10, motif_text="- bells: bell\n",
                    prose_per_chapter={
                        1: "Bell.", 2: "Bell.", 3: "Bell.", 4: "Bell.",
                        5: "Bell.",
                        # back half (cutoff at chapter 6 in a 10-chapter book):
                        6: "Quiet.", 7: "Bell.", 8: "Quiet.",
                        9: "Bell.", 10: "Quiet.",
                    })
    report = build_report(book)
    warned_chapters = sorted(w.chapter for w in report.warnings if w.motif == "bells")
    # ch6, ch8, ch10 are zero-hit in the back half → warnings.
    assert warned_chapters == [6, 8, 10]


def test_build_report_silent_when_motif_never_used(tmp_path: Path) -> None:
    """A motif declared but never used (in any chapter) shouldn't
    trigger back-half warnings — that's noise, not signal."""
    book = tmp_path / "b"
    _populate_book(book, n_chapters=10, motif_text="- river: river\n",
                    prose_per_chapter={n: "Plain prose." for n in range(1, 11)})
    report = build_report(book)
    assert report.warnings == []


def test_build_report_skips_warnings_below_four_chapters(tmp_path: Path) -> None:
    book = tmp_path / "b"
    _populate_book(book, n_chapters=3, motif_text="- bells: bell\n",
                    prose_per_chapter={1: "Bell.", 2: "Quiet.", 3: "Quiet."})
    report = build_report(book)
    assert report.warnings == []


def test_build_report_no_motifs_file_yields_empty_report(tmp_path: Path) -> None:
    book = tmp_path / "b"
    book.mkdir()
    chapters = book / "chapters"
    chapters.mkdir()
    (chapters / "ch_01.md").write_text("---\n---\n\nProse.", encoding="utf-8")
    report = build_report(book)
    assert report.motifs == []
    # Rows still get populated with chapter counts so the user can see
    # word counts without configuring motifs (cheap status info).
    assert len(report.rows) == 1


# ---------------------------------------------------------- render_markdown


def test_render_markdown_table_includes_every_motif(tmp_path: Path) -> None:
    book = tmp_path / "b"
    _populate_book(book, n_chapters=2, motif_text="- bells: bell\n- river: river\n",
                    prose_per_chapter={1: "Bell river.", 2: "Bell."})
    report = build_report(book)
    out = render_markdown(report, book="b")
    assert "Motif tracker" in out
    assert "| bells | river |" in out or "bells" in out and "river" in out
    # · marker for zero counts.
    assert "·" in out


def test_render_markdown_no_motifs_message_includes_book_name() -> None:
    from autonovel.mechanical.motifs import MotifReport
    report = MotifReport(motifs=[], rows=[], warnings=[])
    out = render_markdown(report, book="my-book")
    assert "my-book" in out
    assert "motifs.md" in out


# ---------------------------------------------------------- CLI round-trip


def test_cli_motifs_markdown(tmp_path: Path) -> None:
    book = tmp_path / "demo-book"
    _populate_book(book, n_chapters=3, motif_text="- bells: bell\n",
                    prose_per_chapter={1: "Bell.", 2: "Quiet.", 3: "Bell."})
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "motifs", str(book)],
        capture_output=True, text=True, check=True,
    )
    assert "Motif tracker" in proc.stdout
    assert "bells" in proc.stdout


def test_cli_motifs_json(tmp_path: Path) -> None:
    book = tmp_path / "demo-book"
    _populate_book(book, n_chapters=2, motif_text="- bells: bell\n",
                    prose_per_chapter={1: "Bell.", 2: "Quiet."})
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "motifs",
         str(book), "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["motifs"] == ["bells"]
    assert len(payload["rows"]) == 2
    assert payload["rows"][0]["counts"]["bells"] == 1
