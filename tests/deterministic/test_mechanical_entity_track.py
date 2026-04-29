"""Tier-1 tests for the named-entity tracker
(`autonovel.mechanical.entity_track`)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.mechanical.entity_track import (
    Entity,
    build_report,
    derive_entities_from_canon,
    parse_entities_file,
    scan_chapter,
)


# ---------------------------------------------------------- parse_entities_file


def test_parse_entities_file_basic(tmp_path: Path) -> None:
    p = tmp_path / "entities.md"
    p.write_text(
        "# Entities\n\n"
        "- jakob: Jakob, Jakob Fugger\n"
        "- diary: cipher diary, diary\n",
        encoding="utf-8",
    )
    out = parse_entities_file(p)
    assert [e.slug for e in out] == ["jakob", "diary"]
    assert out[0].keywords == ["Jakob", "Jakob Fugger"]
    assert out[1].keywords == ["cipher diary", "diary"]


def test_parse_entities_file_missing_returns_empty(tmp_path: Path) -> None:
    assert parse_entities_file(tmp_path / "nope.md") == []


# ---------------------------------------------------------- canon fallback


def test_derive_entities_from_canon(tmp_path: Path) -> None:
    canon = tmp_path / "canon.md"
    canon.write_text(
        "# Canon\n\n"
        "- [Tommaso birthday] 1487-05-12\n"
        "- [Niccolò first appears] 1492-03\n"
        "- [Mint fire date] 1521-11-04\n",
        encoding="utf-8",
    )
    out = derive_entities_from_canon(canon)
    slugs = [e.slug for e in out]
    assert "tommaso" in slugs
    assert "niccolò" in slugs
    assert "mint" in slugs


def test_derive_entities_skips_short_heads(tmp_path: Path) -> None:
    """Single-letter or two-letter head tokens generate noise; skip
    them."""
    canon = tmp_path / "canon.md"
    canon.write_text("- [A b c] foo\n", encoding="utf-8")
    assert derive_entities_from_canon(canon) == []


def test_derive_entities_missing_canon_returns_empty(tmp_path: Path) -> None:
    assert derive_entities_from_canon(tmp_path / "nope.md") == []


# ---------------------------------------------------------- scan_chapter


def test_scan_chapter_word_boundary_case_insensitive() -> None:
    entities = [Entity(slug="jakob", keywords=["Jakob"])]
    text = "Jakob looked up. JAKOB walked in. Jakobs (plural — no match)."
    wc, counts = scan_chapter(text, entities)
    assert counts["jakob"] == 2  # Jakob + JAKOB; "Jakobs" not matched


def test_scan_chapter_strips_frontmatter() -> None:
    entities = [Entity(slug="jakob", keywords=["Jakob"])]
    text = (
        "---\n"
        "chapter: 1\n"
        "events: [Jakob-arrival]\n"  # would inflate the count
        "---\n\n"
        "The morning was quiet."
    )
    _, counts = scan_chapter(text, entities)
    assert counts["jakob"] == 0


# ---------------------------------------------------------- build_report


def _populate(book_root: Path, *, n_chapters: int,
               entities_text: str | None,
               prose: dict[int, str],
               canon_text: str | None = None,
               series_root: Path | None = None) -> None:
    book_root.mkdir(parents=True, exist_ok=True)
    if entities_text is not None:
        (book_root / "entities.md").write_text(entities_text, encoding="utf-8")
    chapters = book_root / "chapters"
    chapters.mkdir(exist_ok=True)
    for n in range(1, n_chapters + 1):
        (chapters / f"ch_{n:02d}.md").write_text(
            f"---\nchapter: {n}\n---\n\n" + prose.get(n, "Empty."),
            encoding="utf-8",
        )
    if canon_text is not None and series_root is not None:
        shared = series_root / "shared"
        shared.mkdir(parents=True, exist_ok=True)
        (shared / "canon.md").write_text(canon_text, encoding="utf-8")


def test_build_report_uses_entities_file_when_present(tmp_path: Path) -> None:
    book = tmp_path / "b"
    _populate(book, n_chapters=3,
               entities_text="- jakob: Jakob\n",
               prose={1: "Jakob.", 2: "No one.", 3: "Jakob! Jakob!"})
    report = build_report(book)
    assert report.source == "entities.md"
    assert [e.slug for e in report.entities] == ["jakob"]
    assert [r.counts["jakob"] for r in report.rows] == [1, 0, 2]


def test_build_report_falls_back_to_canon(tmp_path: Path) -> None:
    series = tmp_path / "series"
    book = series / "books" / "b"
    _populate(book, n_chapters=2,
               entities_text=None,
               prose={1: "Tommaso walked.", 2: "Niccolò arrived."},
               canon_text=("# Canon\n- [Tommaso birthday] 1487-05-12\n"
                            "- [Niccolò first appears] 1492-03\n"),
               series_root=series)
    report = build_report(book, series_root=series)
    assert report.source == "canon.md"
    slugs = [e.slug for e in report.entities]
    assert "tommaso" in slugs
    assert "niccolò" in slugs


def test_build_report_override_wins_over_files(tmp_path: Path) -> None:
    book = tmp_path / "b"
    _populate(book, n_chapters=1,
               entities_text="- jakob: Jakob\n",
               prose={1: "Lucia walked."})
    override = [Entity(slug="lucia", keywords=["Lucia"])]
    report = build_report(book, entities_override=override)
    assert report.source == "override"
    assert [e.slug for e in report.entities] == ["lucia"]
    assert report.rows[0].counts["lucia"] == 1


def test_build_report_no_source_yields_empty_entities(tmp_path: Path) -> None:
    book = tmp_path / "b"
    _populate(book, n_chapters=2, entities_text=None,
               prose={1: "Plain.", 2: "Plain."})
    report = build_report(book)
    assert report.entities == []
    assert report.source == "none"


# ---------------------------------------------------------- CLI round-trip


def test_cli_entity_track_markdown(tmp_path: Path) -> None:
    book = tmp_path / "b"
    _populate(book, n_chapters=2,
               entities_text="- jakob: Jakob\n",
               prose={1: "Jakob.", 2: "."})
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "entity-track", str(book)],
        capture_output=True, text=True, check=True,
    )
    assert "Entity tracker" in proc.stdout
    assert "jakob" in proc.stdout


def test_cli_entity_track_json(tmp_path: Path) -> None:
    book = tmp_path / "b"
    _populate(book, n_chapters=2,
               entities_text="- jakob: Jakob\n",
               prose={1: "Jakob.", 2: "Jakob Jakob."})
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "entity-track",
         str(book), "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["entities"] == ["jakob"]
    assert payload["source"] == "entities.md"
    assert payload["rows"][1]["counts"]["jakob"] == 2
