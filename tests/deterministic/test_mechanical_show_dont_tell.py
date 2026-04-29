"""Tier-1 tests for `autonovel.mechanical.show_dont_tell`."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.mechanical.show_dont_tell import (
    EMOTIONS,
    INTERIORITY_VERBS,
    build_report,
    render_markdown,
    scan_chapter,
)


def _frontmatter_chapter(body: str, n: int = 1) -> str:
    return (
        f"---\nchapter: {n}\npov: Tommaso\n---\n\n" + body
    )


# ---------------------------------------------------------- emotion-state


def test_emotion_state_basic() -> None:
    text = _frontmatter_chapter("Lucia was sad. She felt happy. He seemed angry.")
    report = scan_chapter(text)
    kinds = [c.kind for c in report.candidates]
    assert kinds.count("emotion-state") == 3


def test_emotion_state_with_intensifier() -> None:
    text = _frontmatter_chapter("She was very angry.")
    report = scan_chapter(text)
    assert any(c.kind == "emotion-state" for c in report.candidates)


def test_emotion_state_unflagged_for_non_emotion_word() -> None:
    text = _frontmatter_chapter("She was busy.")  # not in EMOTIONS
    report = scan_chapter(text)
    assert all(c.kind != "emotion-state" for c in report.candidates)


# ---------------------------------------------------------- interiority


def test_interiority_verbs_flagged() -> None:
    text = _frontmatter_chapter(
        "She knew the answer. He realised the truth. They wondered why."
    )
    report = scan_chapter(text)
    kinds = [c.kind for c in report.candidates]
    assert kinds.count("interiority") == 3


def test_interiority_named_entity() -> None:
    text = _frontmatter_chapter("Niccolò knew the cost.")
    report = scan_chapter(text)
    assert any(c.kind == "interiority" and c.match == "knew"
                for c in report.candidates)


# ---------------------------------------------------------- perception-filter


def test_perception_filter_basic() -> None:
    text = _frontmatter_chapter(
        "He looked angrily at her. The reply sounded coldly."
    )
    report = scan_chapter(text)
    kinds = [c.kind for c in report.candidates]
    assert kinds.count("perception-filter") >= 1


# ---------------------------------------------------------- narrator-label


def test_narrator_label_flagged() -> None:
    text = _frontmatter_chapter(
        "It was sad. There was anxious silence. It was raining."
        # The third sentence shouldn't match (raining is not in EMOTIONS).
    )
    report = scan_chapter(text)
    labels = [c for c in report.candidates if c.kind == "narrator-label"]
    assert len(labels) >= 1
    assert any(c.match == "sad" for c in labels)


# ---------------------------------------------------------- frontmatter / wc


def test_strips_frontmatter() -> None:
    """Frontmatter shouldn't contribute to hits."""
    text = _frontmatter_chapter("Plain prose.")
    report = scan_chapter(text)
    assert report.total == 0
    assert report.word_count == 2


def test_density_per_1000_words() -> None:
    text = _frontmatter_chapter(" ".join(["word"] * 1000)
                                  + " She was sad.")
    report = scan_chapter(text)
    assert report.total >= 1
    assert 0.5 <= report.density_per_1000 <= 2.0


def test_density_zero_for_empty() -> None:
    text = _frontmatter_chapter("")
    report = scan_chapter(text)
    assert report.density_per_1000 == 0.0


def test_empty_word_list_constants() -> None:
    """Sanity: the curated constants are non-empty."""
    assert len(EMOTIONS) > 10
    assert len(INTERIORITY_VERBS) > 5


# ---------------------------------------------------------- build_report


def test_build_report_orders_chapters(tmp_path: Path) -> None:
    chapters = tmp_path / "b" / "chapters"
    chapters.mkdir(parents=True)
    for n in (3, 1, 2):
        (chapters / f"ch_{n:02d}.md").write_text(
            _frontmatter_chapter("She was sad.", n=n),
            encoding="utf-8",
        )
    report = build_report(tmp_path / "b")
    assert [c.chapter for c in report.chapters] == [1, 2, 3]


def test_build_report_empty_book(tmp_path: Path) -> None:
    book = tmp_path / "b"
    (book / "chapters").mkdir(parents=True)
    assert build_report(book).chapters == []


# ---------------------------------------------------------- render


def test_render_markdown_with_hits(tmp_path: Path) -> None:
    chapters = tmp_path / "b" / "chapters"
    chapters.mkdir(parents=True)
    (chapters / "ch_01.md").write_text(
        _frontmatter_chapter("She was sad. He knew the way."),
        encoding="utf-8",
    )
    out = render_markdown(build_report(tmp_path / "b"), book="b")
    assert "Show-don't-tell — b" in out
    assert "Chapter 1 candidates" in out
    assert "review queue" in out


def test_render_markdown_summary_only(tmp_path: Path) -> None:
    chapters = tmp_path / "b" / "chapters"
    chapters.mkdir(parents=True)
    (chapters / "ch_01.md").write_text(
        _frontmatter_chapter("She was sad."),
        encoding="utf-8",
    )
    out = render_markdown(build_report(tmp_path / "b"), book="b",
                           show_hits=False)
    assert "Chapter 1 candidates" not in out


def test_render_markdown_no_chapters(tmp_path: Path) -> None:
    book = tmp_path / "b"
    (book / "chapters").mkdir(parents=True)
    out = render_markdown(build_report(book), book="b")
    assert "No chapters drafted" in out


# ---------------------------------------------------------- CLI


def test_cli_show_dont_tell_markdown(tmp_path: Path) -> None:
    chapters = tmp_path / "b" / "chapters"
    chapters.mkdir(parents=True)
    (chapters / "ch_01.md").write_text(
        _frontmatter_chapter("She was sad."),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "show-dont-tell",
         str(tmp_path / "b")],
        capture_output=True, text=True, check=True,
    )
    assert "Show-don't-tell" in proc.stdout


def test_cli_show_dont_tell_json(tmp_path: Path) -> None:
    chapters = tmp_path / "b" / "chapters"
    chapters.mkdir(parents=True)
    (chapters / "ch_01.md").write_text(
        _frontmatter_chapter("She was sad. He knew the way."),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "show-dont-tell",
         str(tmp_path / "b"), "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["chapters"][0]["total"] >= 2
