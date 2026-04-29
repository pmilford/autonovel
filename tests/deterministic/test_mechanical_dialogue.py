"""Tier-1 tests for `autonovel.mechanical.dialogue`."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.mechanical.dialogue import (
    ADVERBS,
    SAID_BOOKISMS,
    build_report,
    render_markdown,
    scan_chapter,
)


def _frontmatter_chapter(body: str, n: int = 1) -> str:
    return (
        f"---\nbook: b\nchapter: {n}\npov: Tommaso\n"
        f"events: []\nstatus: drafted\nword_count: 100\n---\n\n"
        + body
    )


# ---------------------------------------------------------- scan_chapter


def test_adverb_tag_flagged() -> None:
    """`"…," she said quietly.` is the canonical adverb-tag tell."""
    text = _frontmatter_chapter('"Hello," she said quietly.')
    report = scan_chapter(text)
    assert report.adverb_hits == 1
    assert any(h.kind == "adverb" and h.adverb == "quietly"
                for h in report.hits)


def test_plain_said_unflagged() -> None:
    """`"…," she said.` is the convention; no flag."""
    text = _frontmatter_chapter('"Hello," she said.')
    report = scan_chapter(text)
    assert report.adverb_hits == 0
    assert report.bookism_hits == 0


def test_said_bookism_flagged() -> None:
    text = _frontmatter_chapter('"Help!" she exclaimed.')
    report = scan_chapter(text)
    assert report.bookism_hits == 1
    assert any(h.kind == "bookism" and h.verb == "exclaimed"
                for h in report.hits)


def test_bookism_with_adverb_flags_both() -> None:
    text = _frontmatter_chapter('"Hello," she murmured softly.')
    report = scan_chapter(text)
    assert report.adverb_hits == 1
    assert report.bookism_hits == 1


def test_stutter_three_in_window_flagged() -> None:
    """The same non-said verb 3 times within 10 lines."""
    body = "\n".join([
        '"Help!" she whispered.',
        "",
        "More prose here.",
        "",
        '"Why?" he whispered.',
        "",
        "Yet more.",
        "",
        '"Now!" she whispered.',
    ])
    text = _frontmatter_chapter(body)
    report = scan_chapter(text)
    assert report.bookism_hits == 3
    assert report.stutter_hits >= 1


def test_stutter_outside_window_not_flagged() -> None:
    """3 occurrences but spread out — no stutter."""
    spacer = "\nFiller line.\n" * 20
    body = '"A" she whispered.' + spacer + '"B" he whispered.' + spacer + '"C" she whispered.'
    text = _frontmatter_chapter(body)
    report = scan_chapter(text)
    assert report.bookism_hits == 3
    assert report.stutter_hits == 0


def test_strips_yaml_frontmatter() -> None:
    """Frontmatter shouldn't contribute to hits — `pov: Tommaso`
    line should not match a 'tommaso said' pattern."""
    text = _frontmatter_chapter("Plain prose.")
    report = scan_chapter(text)
    assert report.adverb_hits == 0
    assert report.bookism_hits == 0


def test_word_count_is_body_only() -> None:
    text = _frontmatter_chapter("Five words of body prose.")
    report = scan_chapter(text)
    assert report.word_count == 5


def test_empty_chapter_zero_hits() -> None:
    text = _frontmatter_chapter("")
    report = scan_chapter(text)
    assert report.total == 0
    assert report.word_count == 0


# ---------------------------------------------------------- build_report


def test_build_report_orders_chapters(tmp_path: Path) -> None:
    chapters = tmp_path / "b" / "chapters"
    chapters.mkdir(parents=True)
    for n in (3, 1, 2):
        (chapters / f"ch_{n:02d}.md").write_text(
            _frontmatter_chapter(f'"Hi," she said quietly.', n=n),
            encoding="utf-8",
        )
    report = build_report(tmp_path / "b")
    assert [c.chapter for c in report.chapters] == [1, 2, 3]


def test_build_report_empty_book(tmp_path: Path) -> None:
    book = tmp_path / "b"
    (book / "chapters").mkdir(parents=True)
    report = build_report(book)
    assert report.chapters == []


# ---------------------------------------------------------- render


def test_render_markdown_has_table_and_hits(tmp_path: Path) -> None:
    chapters = tmp_path / "b" / "chapters"
    chapters.mkdir(parents=True)
    (chapters / "ch_01.md").write_text(
        _frontmatter_chapter('"Hello," she exclaimed.'),
        encoding="utf-8",
    )
    out = render_markdown(build_report(tmp_path / "b"), book="b")
    assert "Dialogue mechanics — b" in out
    assert "| 1 |" in out
    assert "Chapter 1 hits" in out
    assert "exclaimed" in out


def test_render_markdown_summary_only_omits_hits(tmp_path: Path) -> None:
    chapters = tmp_path / "b" / "chapters"
    chapters.mkdir(parents=True)
    (chapters / "ch_01.md").write_text(
        _frontmatter_chapter('"Hello," she exclaimed.'),
        encoding="utf-8",
    )
    out = render_markdown(build_report(tmp_path / "b"), book="b",
                           show_hits=False)
    assert "Chapter 1 hits" not in out


def test_render_markdown_no_chapters(tmp_path: Path) -> None:
    book = tmp_path / "b"
    (book / "chapters").mkdir(parents=True)
    out = render_markdown(build_report(book), book="b")
    assert "No chapters drafted" in out


# ---------------------------------------------------------- CLI


def test_cli_dialogue_markdown(tmp_path: Path) -> None:
    chapters = tmp_path / "b" / "chapters"
    chapters.mkdir(parents=True)
    (chapters / "ch_01.md").write_text(
        _frontmatter_chapter('"Hi," she said quietly.'),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "dialogue",
         str(tmp_path / "b")],
        capture_output=True, text=True, check=True,
    )
    assert "Dialogue mechanics" in proc.stdout
    assert "quietly" in proc.stdout


def test_cli_dialogue_json(tmp_path: Path) -> None:
    chapters = tmp_path / "b" / "chapters"
    chapters.mkdir(parents=True)
    (chapters / "ch_01.md").write_text(
        _frontmatter_chapter('"Hi," she exclaimed.'),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "dialogue",
         str(tmp_path / "b"), "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["chapters"][0]["bookism_hits"] == 1
