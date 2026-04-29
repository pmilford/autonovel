"""Tier-1 tests for `autonovel.mechanical.pov_bleed`."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.mechanical.pov_bleed import (
    build_report,
    parse_cast,
    render_markdown,
    scan_chapter,
)


def _seed_series(tmp_path: Path, *, characters_md: str | None = None,
                  chapters: dict[int, tuple[str, str]] | None = None) -> Path:
    series = tmp_path / "series"
    book = series / "books" / "b"
    chapters_dir = book / "chapters"
    shared = series / "shared"
    chapters_dir.mkdir(parents=True)
    shared.mkdir(parents=True)
    if characters_md is not None:
        (shared / "characters.md").write_text(characters_md, encoding="utf-8")
    for n, (pov, prose) in (chapters or {}).items():
        (chapters_dir / f"ch_{n:02d}.md").write_text(
            f"---\nchapter: {n}\npov: {pov}\n---\n\n{prose}\n",
            encoding="utf-8",
        )
    return book


# ---------------------------------------------------------- parse_cast


def test_parse_cast_bullet_form(tmp_path: Path) -> None:
    p = tmp_path / "characters.md"
    p.write_text(
        "# Cast\n\n"
        "- **Tommaso** — POV, apothecary's son\n"
        "- **Lucia** — Tommaso's neighbour\n"
        "- **Niccolò** — antagonist\n",
        encoding="utf-8",
    )
    cast = parse_cast(p)
    assert {"Tommaso", "Lucia", "Niccolò"} <= cast


def test_parse_cast_heading_form(tmp_path: Path) -> None:
    p = tmp_path / "characters.md"
    p.write_text(
        "# Cast\n\n"
        "## Tommaso\nApothecary.\n\n"
        "## Niccolò\nAntagonist.\n",
        encoding="utf-8",
    )
    cast = parse_cast(p)
    assert "Tommaso" in cast
    assert "Niccolò" in cast


def test_parse_cast_missing_returns_empty(tmp_path: Path) -> None:
    assert parse_cast(tmp_path / "nope.md") == set()


# ---------------------------------------------------------- scan_chapter


def test_scan_flags_non_pov_interiority_verb() -> None:
    text = (
        "---\nchapter: 1\npov: Tommaso\n---\n\n"
        "Niccolò thought of his father.\n"
        "Lucia walked away."
    )
    report = scan_chapter(text, cast={"Tommaso", "Niccolò", "Lucia"})
    # Niccolò + thought = bleed; Lucia + walked = NOT bleed (action verb).
    assert any(h.name == "Niccolò" and h.pattern == "verb"
                for h in report.hits)
    assert not any(h.name == "Lucia" for h in report.hits)


def test_scan_flags_possessive_interiority() -> None:
    text = (
        "---\nchapter: 1\npov: Tommaso\n---\n\n"
        "Niccolò's mind raced. Lucia's hat was wet."
    )
    report = scan_chapter(text, cast={"Tommaso", "Niccolò", "Lucia"})
    poss = [h for h in report.hits if h.pattern == "possessive"]
    assert len(poss) == 1
    assert poss[0].name == "Niccolò"
    assert poss[0].verb_or_noun == "mind"


def test_scan_does_not_flag_pov_interiority() -> None:
    text = (
        "---\nchapter: 1\npov: Tommaso\n---\n\n"
        "Tommaso thought of the bell. Tommaso's heart raced."
    )
    report = scan_chapter(text, cast={"Tommaso", "Niccolò"})
    assert report.hits == []


def test_scan_no_cast_returns_empty() -> None:
    text = (
        "---\nchapter: 1\npov: Tommaso\n---\n\n"
        "Niccolò thought of his father."
    )
    report = scan_chapter(text, cast=set())
    assert report.hits == []
    assert report.pov == "Tommaso"


def test_scan_records_pov_and_word_count() -> None:
    text = "---\nchapter: 1\npov: Lucia\n---\n\nFive words of body prose."
    report = scan_chapter(text, cast={"Tommaso"})
    assert report.pov == "Lucia"
    assert report.word_count == 5


# ---------------------------------------------------------- build_report


def test_build_report_orders_chapters_and_loads_cast(tmp_path: Path) -> None:
    book = _seed_series(
        tmp_path,
        characters_md="- **Tommaso** — POV\n- **Niccolò** — antag\n",
        chapters={
            2: ("Tommaso", "Niccolò thought."),
            1: ("Tommaso", "Niccolò walked."),
        },
    )
    report = build_report(book)
    assert [c.chapter for c in report.chapters] == [1, 2]
    # Ch1: action verb walked → no hit. Ch2: thought → hit.
    assert report.chapters[0].total == 0
    assert report.chapters[1].total == 1


def test_build_report_no_cast_zero_hits(tmp_path: Path) -> None:
    book = _seed_series(
        tmp_path, characters_md=None,
        chapters={1: ("Tommaso", "Niccolò thought.")},
    )
    report = build_report(book)
    assert report.cast_size == 0
    assert all(c.hits == [] for c in report.chapters)


def test_build_report_explicit_cast_override(tmp_path: Path) -> None:
    book = _seed_series(
        tmp_path, characters_md=None,
        chapters={1: ("Tommaso", "Niccolò thought.")},
    )
    report = build_report(book, cast_override={"Tommaso", "Niccolò"})
    assert report.cast_size == 2
    assert report.chapters[0].total == 1


# ---------------------------------------------------------- render


def test_render_markdown_no_cast_message(tmp_path: Path) -> None:
    book = _seed_series(tmp_path, characters_md=None,
                          chapters={1: ("Tommaso", "Prose.")})
    out = render_markdown(build_report(book), book="b")
    assert "No cast loaded" in out


def test_render_markdown_table_columns(tmp_path: Path) -> None:
    book = _seed_series(
        tmp_path, characters_md="- **Tommaso**\n- **Niccolò**\n",
        chapters={1: ("Tommaso", "Niccolò thought of the bell.")},
    )
    out = render_markdown(build_report(book), book="b")
    assert "POV bleed scan — b" in out
    assert "| Ch | POV | Words | Suspect lines |" in out
    assert "Chapter 1" in out


def test_render_markdown_summary_only_omits_hits(tmp_path: Path) -> None:
    book = _seed_series(
        tmp_path, characters_md="- **Tommaso**\n- **Niccolò**\n",
        chapters={1: ("Tommaso", "Niccolò thought.")},
    )
    out = render_markdown(build_report(book), book="b", show_hits=False)
    assert "Chapter 1" not in out.split("\n", 5)[-1] or "L" not in out


# ---------------------------------------------------------- CLI


def test_cli_pov_bleed_markdown(tmp_path: Path) -> None:
    book = _seed_series(
        tmp_path, characters_md="- **Tommaso**\n- **Niccolò**\n",
        chapters={1: ("Tommaso", "Niccolò thought.")},
    )
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "pov-bleed", str(book)],
        capture_output=True, text=True, check=True,
    )
    assert "POV bleed scan" in proc.stdout


def test_cli_pov_bleed_json(tmp_path: Path) -> None:
    book = _seed_series(
        tmp_path, characters_md="- **Tommaso**\n- **Niccolò**\n",
        chapters={1: ("Tommaso", "Niccolò thought of the bell.")},
    )
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "pov-bleed",
         str(book), "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["cast_size"] == 2
    assert payload["chapters"][0]["total"] == 1
