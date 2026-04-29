"""Tier-1 tests for `mechanical/research_index.py` and the
`autonovel mechanical research-index` CLI subcommand.

Covers note metadata extraction (title / updated date / period /
counts), filtering (--grep, --cites), render shapes, and CLI
round-trip.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.mechanical import research_index as ri


# ----------------------------------------------------- parse_note


def _make_note(tmp_path: Path, slug: str, *, body: str | None = None) -> Path:
    notes = tmp_path / "shared" / "research" / "notes"
    notes.mkdir(parents=True, exist_ok=True)
    path = notes / f"{slug}.md"
    if body is None:
        body = (
            f"# Research notes: {slug}\n\n"
            "Updated 2026-04-25. Period: 1450-1550 Italy.\n\n"
            "## Summary\n\n"
            "Jakob Fugger arrived in Augsburg in 1478 [fugger-augsburg].\n"
            "Maximilian I's election was financed by the Fugger bank "
            "[fugger-loans-1519].\n\n"
            "## Material detail\n\n"
            "Copper from the Tyrolean mines was the load-bearing "
            "asset class [tyrol-copper].\n\n"
            "## Uncertainties\n"
            "- Speculative: precise interest rates on early loans.\n"
            "- Uncertain: which guild halls Fugger personally visited.\n\n"
            "## Candidate Canon Entries\n"
            "- [Fugger arrived Augsburg] 1478\n"
            "- [Fugger financed Maximilian] 1490s\n\n"
            "## Sources\n"
            "- [fugger-augsburg] Augsburg city archives, https://example.org/aug.\n"
            "- [fugger-loans-1519] DOI:10.0001/fugger.\n"
            "- [tyrol-copper] Tyrol mining records, https://example.org/tyrol.\n"
        )
    path.write_text(body, encoding="utf-8")
    return path


def test_parse_note_extracts_all_fields(tmp_path: Path) -> None:
    path = _make_note(tmp_path, "fugger-banking")
    note = ri.parse_note(path)
    assert note.slug == "fugger-banking"
    assert "fugger-banking" in note.title or "Research notes" in note.title
    assert note.last_updated == "2026-04-25"
    assert "Italy" in note.period
    assert note.source_count == 3
    assert note.candidate_canon_count == 2
    assert note.uncertainty_count == 2
    # Body should have at least the three [shortname] body citations.
    assert note.body_citation_count >= 3


def test_parse_note_handles_missing_optional_sections(tmp_path: Path) -> None:
    path = _make_note(
        tmp_path, "minimal",
        body="# Minimal note\n\nJust some prose with [cite-a].\n",
    )
    note = ri.parse_note(path)
    assert note.slug == "minimal"
    assert note.source_count == 0  # no Sources block
    assert note.candidate_canon_count == 0
    assert note.uncertainty_count == 0
    assert note.body_citation_count == 1


def test_parse_note_excludes_sources_block_from_body_citation_count(
    tmp_path: Path,
) -> None:
    """Citation count should NOT include the [shortname] entries
    listed under `## Sources` (those are bibliography entries, not
    body references)."""
    body = (
        "# Note\n\n## Summary\n\n"
        "Fact one [a]. Fact two [b]. Fact three [a].\n\n"  # 3 in body
        "## Sources\n\n"
        "- [a] some source.\n- [b] another source.\n"  # 2 in sources
    )
    path = _make_note(tmp_path, "n", body=body)
    note = ri.parse_note(path)
    assert note.body_citation_count == 3
    assert note.source_count == 2


# ----------------------------------------------------- build_index


def test_build_index_returns_empty_when_no_notes(tmp_path: Path) -> None:
    """No `shared/research/notes/` dir → empty index."""
    series = tmp_path / "series"
    series.mkdir()
    idx = ri.build_index(series)
    assert idx.notes == []


def test_build_index_finds_all_md(tmp_path: Path) -> None:
    series = tmp_path
    _make_note(series, "fugger-banking")
    _make_note(series, "maximilian-court")
    _make_note(series, "tyrol-copper")
    idx = ri.build_index(series)
    slugs = [n.slug for n in idx.notes]
    assert slugs == ["fugger-banking", "maximilian-court", "tyrol-copper"]


# ----------------------------------------------------- filter_index


def test_filter_index_grep_filters_by_substring(tmp_path: Path) -> None:
    series = tmp_path
    _make_note(series, "fugger-banking",
                body="# Fugger\n\nJakob Fugger and Maximilian.\n")
    _make_note(series, "venice-glassmakers",
                body="# Venice\n\nMurano glassmakers in 1500s.\n")
    idx = ri.build_index(series)
    f1 = ri.filter_index(idx, grep="Fugger")
    assert [n.slug for n in f1] == ["fugger-banking"]
    f2 = ri.filter_index(idx, grep="GLASS")  # case-insensitive
    assert [n.slug for n in f2] == ["venice-glassmakers"]


def test_filter_index_cites_filters_by_sources_block(tmp_path: Path) -> None:
    """--cites only matches inside the ## Sources block, not body
    prose. A URL mentioned in body but NOT in sources mustn't match."""
    series = tmp_path
    _make_note(series, "a", body=(
        "# A\n\nSee https://example.org/foo for context.\n\n"
        "## Sources\n- [a] https://example.org/bar\n"
    ))
    _make_note(series, "b", body=(
        "# B\n\nSome prose.\n\n"
        "## Sources\n- [b] https://example.org/foo (the right URL).\n"
    ))
    idx = ri.build_index(series)
    f = ri.filter_index(idx, cites_match="example.org/foo")
    assert [n.slug for n in f] == ["b"]


# ----------------------------------------------------- render


def test_render_markdown_no_notes_explains_path(tmp_path: Path) -> None:
    series = tmp_path / "series"
    series.mkdir()
    md = ri.render_markdown(ri.build_index(series))
    assert "No research notes" in md
    assert "/autonovel:research" in md


def test_render_markdown_with_notes_emits_table(tmp_path: Path) -> None:
    series = tmp_path
    _make_note(series, "fugger-banking")
    _make_note(series, "maximilian-court")
    md = ri.render_markdown(ri.build_index(series))
    assert "fugger-banking" in md
    assert "maximilian-court" in md
    assert "| Slug |" in md
    # Footer guidance cross-references the LLM query mode.
    assert "/autonovel:research --query" in md


def test_render_markdown_with_filter_explains_filter(tmp_path: Path) -> None:
    series = tmp_path
    _make_note(series, "a", body="# A\n\nFugger.\n")
    _make_note(series, "b", body="# B\n\nNothing relevant.\n")
    md = ri.render_markdown(ri.build_index(series), grep="Fugger")
    assert "Filters" in md
    assert "1 of 2" in md  # filter narrowed to one


# ----------------------------------------------------- CLI round-trip


def test_cli_research_index_markdown(tmp_path: Path) -> None:
    series = tmp_path
    _make_note(series, "fugger-banking")
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "research-index",
         str(series)],
        capture_output=True, text=True, check=True,
    )
    assert "fugger-banking" in out.stdout
    assert "| Slug |" in out.stdout


def test_cli_research_index_json(tmp_path: Path) -> None:
    series = tmp_path
    _make_note(series, "fugger-banking")
    _make_note(series, "venice-glass",
                body="# Venice\n\nMurano glass.\n")
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "research-index",
         str(series), "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data["total_notes"] == 2
    slugs = sorted(n["slug"] for n in data["notes"])
    assert slugs == ["fugger-banking", "venice-glass"]


def test_cli_research_index_grep_filter(tmp_path: Path) -> None:
    series = tmp_path
    _make_note(series, "fugger-banking")
    _make_note(series, "venice-glass",
                body="# Venice\n\nMurano glass.\n")
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "research-index",
         str(series), "--grep", "Fugger", "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert [n["slug"] for n in data["notes"]] == ["fugger-banking"]
    assert data["total_notes"] == 2  # unfiltered total preserved
