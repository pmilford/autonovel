"""Tier-1 tests for `mechanical/impact.py` and the
`autonovel mechanical impact-of` CLI subcommand.

Covers Superseded-block parsing, token extraction, chapter grep,
report assembly, render shapes (markdown + JSON), and the CLI
round-trip.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel.mechanical import impact as impact_mod


# ----------------------------------------------------- tokenise


def test_tokenise_drops_stopwords_and_short() -> None:
    tokens = impact_mod.tokenise_for_grep(
        "Fugger arrived in Augsburg in 1473 with two horses"
    )
    # "in" and "with" are stopwords; "two" is also dropped (stopword);
    # short noise tokens are filtered. Years kept as 4-digit.
    assert "fugger" in tokens
    assert "augsburg" in tokens
    assert "1473" in tokens
    assert "in" not in tokens
    assert "with" not in tokens


def test_tokenise_keeps_unicode_letters() -> None:
    """Non-ASCII letters in names (Niccolò, Fürst) must tokenise as
    one word, not split on the diacritic."""
    tokens = impact_mod.tokenise_for_grep("Niccolò met Fürst Anselmö")
    assert "niccolò" in tokens or "niccolo" in tokens or any("nicc" in t for t in tokens)
    assert any("fürst" in t or "furst" in t for t in tokens)


def test_tokenise_drops_pure_punctuation() -> None:
    assert impact_mod.tokenise_for_grep("...,;!?") == set()


# ----------------------------------------------------- parse supersedures


def test_parse_supersedures_simple_block() -> None:
    canon = (
        "# Canon\n\n"
        "- [Fugger arrived Augsburg] 1478\n\n"
        "## Superseded 2026-04-25\n\n"
        "- Prior canon line: `[Fugger arrived Augsburg] 1473`\n"
        "  - Superseded by: `[Fugger arrived Augsburg] 1478`\n"
        "  - Rationale: Research note found primary source.\n"
        "  - Research note: italy-1450-1550\n"
    )
    sups = impact_mod.parse_canon_supersedures(canon)
    assert len(sups) == 1
    s = sups[0]
    assert s.shortname == "Fugger arrived Augsburg"
    assert s.prior_value == "1473"
    assert s.new_value == "1478"
    assert s.research_slug == "italy-1450-1550"
    assert "primary source" in s.rationale
    assert s.timestamp == "2026-04-25"


def test_parse_supersedures_multiple_in_one_block() -> None:
    canon = (
        "## Superseded 2026-04-25\n\n"
        "- Prior canon line: `[Anselmo's age 1492] 19`\n"
        "  - Superseded by: `[Anselmo's age 1492] 24`\n"
        "  - Rationale: birth date pushed earlier.\n"
        "- Prior canon line: `[Lucia first appears] 1492-08-03`\n"
        "  - Superseded by: `[Lucia first appears] 1493-01-15`\n"
        "  - Rationale: parish records.\n"
    )
    sups = impact_mod.parse_canon_supersedures(canon)
    assert len(sups) == 2
    assert sups[0].shortname == "Anselmo's age 1492"
    assert sups[1].shortname == "Lucia first appears"


def test_parse_supersedures_multiple_blocks_concatenate() -> None:
    canon = (
        "## Superseded 2026-04-20\n\n"
        "- Prior canon line: `[A] x`\n"
        "  - Superseded by: `[A] y`\n"
        "  - Rationale: reason 1.\n\n"
        "## Superseded 2026-04-25\n\n"
        "- Prior canon line: `[B] m`\n"
        "  - Superseded by: `[B] n`\n"
        "  - Rationale: reason 2.\n"
    )
    sups = impact_mod.parse_canon_supersedures(canon)
    assert len(sups) == 2
    assert sups[0].timestamp == "2026-04-20"
    assert sups[1].timestamp == "2026-04-25"


def test_parse_supersedures_empty_when_no_block() -> None:
    canon = "# Canon\n\nNo supersedures here.\n- [Foo] bar\n"
    assert impact_mod.parse_canon_supersedures(canon) == []


# ----------------------------------------------------- grep tokens


def test_grep_tokens_uses_diff_against_new_value() -> None:
    s = impact_mod.Supersedure(
        shortname="Fugger arrived",
        prior_value="1473",
        new_value="1478",
    )
    tokens = s.grep_tokens()
    assert "1473" in tokens
    assert "1478" not in tokens


def test_grep_tokens_drops_shared_words() -> None:
    """Tokens that appear in BOTH prior and new are not "wrong" —
    they shouldn't show up in the diff."""
    s = impact_mod.Supersedure(
        shortname="Lucia first appears",
        prior_value="Venice in 1492",
        new_value="Venice in 1493",
    )
    tokens = s.grep_tokens()
    assert "1492" in tokens
    assert "1493" not in tokens
    assert "venice" not in tokens  # in both


# ----------------------------------------------------- find chapter references


def test_find_chapter_references_finds_token_in_prose(tmp_path: Path) -> None:
    chapter = tmp_path / "ch_03.md"
    chapter.write_text(
        "---\nchapter: 3\n---\n\n"
        "Fugger had arrived in Augsburg in 1473, the city still "
        "smelling of sawdust.\n",
        encoding="utf-8",
    )
    sup = impact_mod.Supersedure(
        shortname="Fugger arrived Augsburg",
        prior_value="1473",
        new_value="1478",
    )
    matches = impact_mod.find_chapter_references(chapter, [sup])
    assert len(matches) == 1
    assert matches[0].chapter == 3
    assert "1473" in matches[0].matched_tokens
    assert "1473" in matches[0].line_text


def test_find_chapter_references_strips_frontmatter(tmp_path: Path) -> None:
    """A token in YAML frontmatter must NOT trigger a match — only
    prose counts."""
    chapter = tmp_path / "ch_05.md"
    chapter.write_text(
        "---\nchapter: 5\nstory_time: 1473-08-12\n---\n\n"
        "She crossed the bridge.\n",
        encoding="utf-8",
    )
    sup = impact_mod.Supersedure(
        shortname="X", prior_value="1473", new_value="1478",
    )
    assert impact_mod.find_chapter_references(chapter, [sup]) == []


def test_find_chapter_references_skips_supersedures_with_no_unique_tokens(
    tmp_path: Path,
) -> None:
    """When prior and new values are identical, there are no tokens
    to grep for — silent."""
    chapter = tmp_path / "ch_01.md"
    chapter.write_text("---\nchapter: 1\n---\n\nProse with 1473.\n", encoding="utf-8")
    sup = impact_mod.Supersedure(
        shortname="Same", prior_value="1473", new_value="1473",
    )
    assert impact_mod.find_chapter_references(chapter, [sup]) == []


# ----------------------------------------------------- build_impact_report


def _build_series(tmp_path: Path, *, with_canon_supersede: bool = True) -> tuple[Path, Path]:
    """Minimal series shape: shared/canon.md + books/test-book/chapters/."""
    series = tmp_path / "series"
    (series / "shared").mkdir(parents=True)
    book_root = series / "books" / "test-book"
    (book_root / "chapters").mkdir(parents=True)
    if with_canon_supersede:
        (series / "shared" / "canon.md").write_text(
            "# Canon\n\n"
            "- [Fugger arrived Augsburg] 1478\n\n"
            "## Superseded 2026-04-25\n\n"
            "- Prior canon line: `[Fugger arrived Augsburg] 1473`\n"
            "  - Superseded by: `[Fugger arrived Augsburg] 1478`\n"
            "  - Rationale: primary source.\n"
            "  - Research note: italy-1450-1550\n",
            encoding="utf-8",
        )
    else:
        (series / "shared" / "canon.md").write_text("# Canon\n\nNothing.\n", encoding="utf-8")
    return series, book_root


def test_build_impact_report_finds_chapter_references(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    (book_root / "chapters" / "ch_02.md").write_text(
        "---\nchapter: 2\n---\n\n"
        "Fugger had arrived in 1473, full of plans.\n",
        encoding="utf-8",
    )
    (book_root / "chapters" / "ch_03.md").write_text(
        "---\nchapter: 3\n---\n\n"
        "She remembered her father's stories of Augsburg.\n",
        encoding="utf-8",
    )
    report = impact_mod.build_impact_report(book_root, series_root=series)
    assert len(report.supersedures) == 1
    # ch02 references "1473"; ch03 doesn't.
    assert report.chapters_with_matches == [2]
    assert any(m.chapter == 2 for m in report.matches)


def test_build_impact_report_no_supersedures_returns_empty(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path, with_canon_supersede=False)
    report = impact_mod.build_impact_report(book_root, series_root=series)
    assert report.supersedures == []
    assert report.chapters_with_matches == []


def test_build_impact_report_unsupported_source_returns_empty(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    report = impact_mod.build_impact_report(
        book_root, series_root=series, source_command="research",
    )
    assert report.supersedures == []


def test_build_impact_report_no_canon_file_returns_empty(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    (series / "shared" / "canon.md").unlink()
    report = impact_mod.build_impact_report(book_root, series_root=series)
    assert report.supersedures == []


# ----------------------------------------------------- render markdown


def test_render_markdown_lists_supersedure_and_action_plan(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    (book_root / "chapters" / "ch_02.md").write_text(
        "---\nchapter: 2\n---\n\nFugger arrived in 1473.\n",
        encoding="utf-8",
    )
    report = impact_mod.build_impact_report(book_root, series_root=series)
    md = impact_mod.render_impact_markdown(report, book="test-book")
    assert "Fugger arrived Augsburg" in md
    assert "1473" in md  # was
    assert "1478" in md  # now
    assert "/autonovel:revise --chapter 2" in md
    assert "Action plan" in md


def test_render_markdown_empty_supersedures_explains_no_action(tmp_path: Path) -> None:
    report = impact_mod.ImpactReport(
        source_command="promote-canon", supersedures=[],
    )
    md = impact_mod.render_impact_markdown(report)
    assert "No supersedures" in md or "no facts were superseded" in md


def test_render_markdown_no_chapters_match_explains_clean(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    # Chapter that doesn't reference 1473.
    (book_root / "chapters" / "ch_01.md").write_text(
        "---\nchapter: 1\n---\n\nA peaceful morning.\n",
        encoding="utf-8",
    )
    report = impact_mod.build_impact_report(book_root, series_root=series)
    md = impact_mod.render_impact_markdown(report, book="test-book")
    assert "Nothing to revise" in md or "_No chapters reference" in md


# ----------------------------------------------------- CLI round-trip


def test_cli_impact_of_markdown(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    (book_root / "chapters" / "ch_02.md").write_text(
        "---\nchapter: 2\n---\n\nFugger arrived in 1473.\n",
        encoding="utf-8",
    )
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "impact-of",
         str(book_root), "--series-root", str(series)],
        capture_output=True, text=True, check=True,
    )
    assert "Fugger arrived Augsburg" in out.stdout
    assert "/autonovel:revise --chapter 2" in out.stdout


def test_cli_impact_of_json_format(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    (book_root / "chapters" / "ch_02.md").write_text(
        "---\nchapter: 2\n---\n\nFugger arrived in 1473.\n",
        encoding="utf-8",
    )
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "impact-of",
         str(book_root), "--series-root", str(series), "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data["source_command"] == "promote-canon"
    assert data["chapters_with_matches"] == [2]
    assert len(data["supersedures"]) == 1
