"""Tier-1 tests for `mechanical/impact.py` and the
`autonovel mechanical impact-of` CLI subcommand.

Covers Superseded-block parsing, token extraction, chapter grep,
report assembly, render shapes (markdown + JSON), the CLI
round-trip, and (at the bottom) regression locks for the
`/autonovel:impact-of` slash-command body shape — the
`--with-llm` and `--source research` modes added 2026-04-29 PM.
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


# ----------------------------- mtime-driven stale-chapters detector


def test_stale_chapters_voice_discovery_flags_old_chapter(
    tmp_path: Path,
) -> None:
    import os
    series, book_root = _build_series(tmp_path)
    voice = book_root / "voice.md"
    voice.write_text("# Voice\n\nFingerprint.\n", encoding="utf-8")
    # Voice is "newer"; chapter is older.
    older = 1_000_000.0
    newer = 2_000_000.0
    ch1 = book_root / "chapters" / "ch_01.md"
    ch1.write_text("---\nchapter: 1\n---\n\nProse.\n", encoding="utf-8")
    os.utime(ch1, (older, older))
    os.utime(voice, (newer, newer))
    report = impact_mod.build_stale_chapters_report(
        book_root, series_root=series,
        source_command="voice-discovery",
    )
    assert report.foundation_path is not None
    assert "voice.md" in report.foundation_path
    assert len(report.stale_chapters) == 1
    assert report.stale_chapters[0].chapter == 1


def test_stale_chapters_add_character_uses_shared_path(
    tmp_path: Path,
) -> None:
    import os
    series, book_root = _build_series(tmp_path)
    chars = series / "shared" / "characters.md"
    chars.write_text("# Characters\n\n- **Alice**\n", encoding="utf-8")
    older = 1_000_000.0
    newer = 2_000_000.0
    ch1 = book_root / "chapters" / "ch_01.md"
    ch1.write_text("---\nchapter: 1\n---\n\n", encoding="utf-8")
    os.utime(ch1, (older, older))
    os.utime(chars, (newer, newer))
    report = impact_mod.build_stale_chapters_report(
        book_root, series_root=series,
        source_command="add-character",
    )
    assert "characters.md" in (report.foundation_path or "")
    assert len(report.stale_chapters) == 1


def test_stale_chapters_chapter_newer_than_foundation_silent(
    tmp_path: Path,
) -> None:
    """Chapter mtime ≥ foundation mtime → not stale."""
    import os
    series, book_root = _build_series(tmp_path)
    voice = book_root / "voice.md"
    voice.write_text("# Voice\n", encoding="utf-8")
    older = 1_000_000.0
    newer = 2_000_000.0
    os.utime(voice, (older, older))
    ch1 = book_root / "chapters" / "ch_01.md"
    ch1.write_text("---\nchapter: 1\n---\n", encoding="utf-8")
    os.utime(ch1, (newer, newer))
    report = impact_mod.build_stale_chapters_report(
        book_root, series_root=series,
        source_command="voice-discovery",
    )
    assert report.stale_chapters == []


def test_stale_chapters_no_foundation_file_emits_empty(
    tmp_path: Path,
) -> None:
    series, book_root = _build_series(tmp_path)
    # No voice.md.
    report = impact_mod.build_stale_chapters_report(
        book_root, series_root=series,
        source_command="voice-discovery",
    )
    assert report.foundation_mtime is None
    assert report.stale_chapters == []


def test_stale_chapters_unknown_source_returns_empty(
    tmp_path: Path,
) -> None:
    series, book_root = _build_series(tmp_path)
    report = impact_mod.build_stale_chapters_report(
        book_root, series_root=series,
        source_command="not-a-real-source",
    )
    assert report.foundation_path is None


def test_render_stale_chapters_action_plan(tmp_path: Path) -> None:
    import os
    series, book_root = _build_series(tmp_path)
    voice = book_root / "voice.md"
    voice.write_text("# Voice\n", encoding="utf-8")
    older = 1_000_000.0
    newer = 2_000_000.0
    for n in (1, 3, 5):
        ch = book_root / "chapters" / f"ch_{n:02d}.md"
        ch.write_text(f"---\nchapter: {n}\n---\n", encoding="utf-8")
        os.utime(ch, (older, older))
    os.utime(voice, (newer, newer))
    report = impact_mod.build_stale_chapters_report(
        book_root, series_root=series,
        source_command="voice-discovery",
    )
    md = impact_mod.render_stale_chapters_markdown(report, book="test-book")
    assert "/autonovel:revise --chapter 1" in md
    assert "/autonovel:revise --chapter 3" in md
    assert "/autonovel:revise --chapter 5" in md
    assert "1,3,5" in md  # revision-pass sweep hint


def test_render_stale_chapters_no_stale_says_clean(tmp_path: Path) -> None:
    import os
    series, book_root = _build_series(tmp_path)
    voice = book_root / "voice.md"
    voice.write_text("# Voice\n", encoding="utf-8")
    older = 1_000_000.0
    newer = 2_000_000.0
    os.utime(voice, (older, older))
    ch1 = book_root / "chapters" / "ch_01.md"
    ch1.write_text("---\nchapter: 1\n---\n", encoding="utf-8")
    os.utime(ch1, (newer, newer))
    report = impact_mod.build_stale_chapters_report(
        book_root, series_root=series,
        source_command="voice-discovery",
    )
    md = impact_mod.render_stale_chapters_markdown(report)
    assert "Every chapter is newer" in md or "Nothing to revise" in md


def test_cli_impact_of_voice_discovery_mtime(tmp_path: Path) -> None:
    """CLI round-trip with --source voice-discovery emits the
    mtime-driven report shape."""
    import os
    series, book_root = _build_series(tmp_path)
    voice = book_root / "voice.md"
    voice.write_text("# Voice\n", encoding="utf-8")
    older = 1_000_000.0
    newer = 2_000_000.0
    ch1 = book_root / "chapters" / "ch_01.md"
    ch1.write_text("---\nchapter: 1\n---\n", encoding="utf-8")
    os.utime(ch1, (older, older))
    os.utime(voice, (newer, newer))
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "impact-of",
         str(book_root), "--series-root", str(series),
         "--source", "voice-discovery", "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data["report_kind"] == "mtime-driven"
    assert data["source_command"] == "voice-discovery"
    assert len(data["stale_chapters"]) == 1


def test_cli_impact_of_gen_canon_uses_canon_path(tmp_path: Path) -> None:
    """gen-canon source shares the canon-driven helper with
    promote-canon — Superseded blocks drive the report shape."""
    series, book_root = _build_series(tmp_path)
    # _build_series writes a canon with a Superseded block.
    (book_root / "chapters" / "ch_02.md").write_text(
        "---\nchapter: 2\n---\n\nFugger arrived in 1473.\n",
        encoding="utf-8",
    )
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "impact-of",
         str(book_root), "--series-root", str(series),
         "--source", "gen-canon", "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data["report_kind"] == "canon-driven"
    assert data["source_command"] == "gen-canon"
    # Superseded block found; chapter 2 references the prior value.
    assert data["chapters_with_matches"] == [2]


# ----------------------------------- /autonovel:impact-of body locks


@pytest.fixture
def impact_of_cmd():
    from autonovel.adapters.base import discover_commands
    here = Path(__file__).resolve().parent.parent.parent / "commands"
    return next(c for c in discover_commands(here) if c.name == "autonovel:impact-of")


def test_argument_hint_lists_with_llm_and_source_research(impact_of_cmd) -> None:
    hint = impact_of_cmd.argument_hint or ""
    assert "--with-llm" in hint
    assert "research" in hint


def test_argument_hint_lists_mtime_driven_sources(impact_of_cmd) -> None:
    """The Phase-2 source extension added voice-discovery,
    add-character, gen-characters, gen-world, add-source plus
    gen-canon. argument-hint must enumerate them so users discover
    the option."""
    hint = impact_of_cmd.argument_hint or ""
    for src in ("gen-canon", "voice-discovery", "add-character",
                 "gen-world", "add-source"):
        assert src in hint, f"missing source {src!r} in argument-hint"


def test_body_documents_classification_buckets(impact_of_cmd) -> None:
    """The four classification labels must be named verbatim — they
    shape the action checklist filtering."""
    body = impact_of_cmd.body
    for label in ("HIGH", "MEDIUM", "LOW", "FALSE_POSITIVE"):
        assert label in body, f"impact-of body missing label {label}"


def test_body_documents_research_mode(impact_of_cmd) -> None:
    body = impact_of_cmd.body
    assert "--source research" in body
    assert "research-index" in body  # mechanical helper invoked
    assert "Candidate Canon Entries" in body  # what the LLM extracts


def test_body_documents_no_llm_fallback(impact_of_cmd) -> None:
    """Research mode is LLM by default; --no-llm reverts to literal
    grep over the citations."""
    body = impact_of_cmd.body
    assert "--no-llm" in body


# ----------------------------------------- rename-verify (rename-character)


def _write_command_log(series: Path, entries: list[dict]) -> None:
    log = series / ".autonovel" / "command-log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("\n".join(json.dumps(e) for e in entries) + "\n",
                    encoding="utf-8")


def test_rename_verify_no_log_returns_empty(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    report = impact_mod.build_rename_verify_report(
        book_root, series_root=series,
    )
    assert report.rename is None
    assert report.matches == []


def test_rename_verify_finds_straggler_old_name(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    _write_command_log(series, [{
        "timestamp": "2026-05-01T12:00:00+00:00",
        "command": "autonovel:rename-character",
        "args": ["--old", "Niccolò", "--new", "Marco", "--book", "test-book"],
        "status": "ok",
    }])
    (book_root / "chapters" / "ch_01.md").write_text(
        "---\nchapter: 1\n---\n\n"
        "Niccolò opened the door.\n"
        "Marco followed.\n",
        encoding="utf-8",
    )
    report = impact_mod.build_rename_verify_report(
        book_root, series_root=series,
    )
    assert report.rename is not None
    assert report.rename.old == "Niccolò"
    assert report.rename.new == "Marco"
    assert report.chapters_with_matches == [1]
    assert any("Niccolò" in m.line_text for m in report.matches)


def test_rename_verify_picks_most_recent_entry(tmp_path: Path) -> None:
    """Older renames must not shadow the most recent one."""
    series, book_root = _build_series(tmp_path)
    _write_command_log(series, [
        {
            "timestamp": "2026-04-30T10:00:00+00:00",
            "command": "autonovel:rename-character",
            "args": ["--old", "Alice", "--new", "Beth"],
            "status": "ok",
        },
        {
            "timestamp": "2026-05-01T10:00:00+00:00",
            "command": "autonovel:rename-character",
            "args": ["--old", "Charles", "--new", "David"],
            "status": "ok",
        },
    ])
    report = impact_mod.build_rename_verify_report(
        book_root, series_root=series,
    )
    assert report.rename is not None
    assert report.rename.old == "Charles"


def test_rename_verify_skips_failed_entries(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    _write_command_log(series, [
        {
            "timestamp": "2026-04-30T10:00:00+00:00",
            "command": "autonovel:rename-character",
            "args": ["--old", "Alice", "--new", "Beth"],
            "status": "ok",
        },
        {
            "timestamp": "2026-05-01T10:00:00+00:00",
            "command": "autonovel:rename-character",
            "args": ["--old", "Charles", "--new", "David"],
            "status": "error",
        },
    ])
    report = impact_mod.build_rename_verify_report(
        book_root, series_root=series,
    )
    assert report.rename is not None
    assert report.rename.old == "Alice"


def test_rename_verify_word_boundary(tmp_path: Path) -> None:
    """The old name must match on word boundaries — `Anna` should not
    match inside `Annapurna`."""
    series, book_root = _build_series(tmp_path)
    _write_command_log(series, [{
        "timestamp": "2026-05-01T12:00:00+00:00",
        "command": "autonovel:rename-character",
        "args": ["--old", "Anna", "--new", "Bea"],
        "status": "ok",
    }])
    (book_root / "chapters" / "ch_01.md").write_text(
        "---\nchapter: 1\n---\n\n"
        "She climbed Annapurna in winter.\n",
        encoding="utf-8",
    )
    report = impact_mod.build_rename_verify_report(
        book_root, series_root=series,
    )
    assert report.matches == []


def test_render_rename_verify_clean_says_so(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    _write_command_log(series, [{
        "timestamp": "2026-05-01T12:00:00+00:00",
        "command": "autonovel:rename-character",
        "args": ["--old", "Niccolò", "--new", "Marco"],
        "status": "ok",
    }])
    report = impact_mod.build_rename_verify_report(
        book_root, series_root=series,
    )
    md = impact_mod.render_rename_verify_markdown(report)
    assert "rename took cleanly" in md
    assert "Niccolò" in md and "Marco" in md


def test_render_rename_verify_no_log(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    report = impact_mod.build_rename_verify_report(
        book_root, series_root=series,
    )
    md = impact_mod.render_rename_verify_markdown(report)
    assert "No `/autonovel:rename-character` invocation" in md


def test_render_rename_verify_action_plan(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    _write_command_log(series, [{
        "timestamp": "2026-05-01T12:00:00+00:00",
        "command": "autonovel:rename-character",
        "args": ["--old", "Old", "--new", "New"],
        "status": "ok",
    }])
    for n in (2, 4):
        (book_root / "chapters" / f"ch_{n:02d}.md").write_text(
            f"---\nchapter: {n}\n---\n\nOld walked away.\n",
            encoding="utf-8",
        )
    report = impact_mod.build_rename_verify_report(
        book_root, series_root=series,
    )
    md = impact_mod.render_rename_verify_markdown(report, book="test-book")
    assert "/autonovel:revise --chapter 2 --book test-book" in md
    assert "/autonovel:revise --chapter 4 --book test-book" in md


def test_cli_impact_of_rename_character_json(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    _write_command_log(series, [{
        "timestamp": "2026-05-01T12:00:00+00:00",
        "command": "autonovel:rename-character",
        "args": ["--old", "Old", "--new", "New"],
        "status": "ok",
    }])
    (book_root / "chapters" / "ch_01.md").write_text(
        "---\nchapter: 1\n---\n\nOld stood up.\n",
        encoding="utf-8",
    )
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "impact-of",
         str(book_root), "--series-root", str(series),
         "--source", "rename-character", "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data["report_kind"] == "rename-verify"
    assert data["rename"]["old"] == "Old"
    assert data["chapters_with_matches"] == [1]


# ----------------------------------- renumber-refs (merge / reorder / remove)


def test_chapter_ref_pattern_finds_arabic_and_roman(tmp_path: Path) -> None:
    ch = tmp_path / "ch_03.md"
    ch.write_text(
        "---\nchapter: 3\n---\n\n"
        "As we saw in chapter 7, the door was locked.\n"
        "Chapter VII gave us the key.\n"
        "By ch. 12 the case was closed.\n"
        "Just a thematic mention of CHAPTERS without numbers.\n",
        encoding="utf-8",
    )
    matches = impact_mod.find_chapter_number_references(ch)
    refs = sorted(m.referenced for m in matches)
    assert refs == ["12", "7", "VII"]


def test_renumber_refs_no_log_still_scans(tmp_path: Path) -> None:
    """Helpful default: even without a logged renumber, list every
    cross-reference so the user can audit after a manual reorder."""
    series, book_root = _build_series(tmp_path)
    (book_root / "chapters" / "ch_02.md").write_text(
        "---\nchapter: 2\n---\n\n"
        "As in chapter 5, things shifted.\n",
        encoding="utf-8",
    )
    report = impact_mod.build_renumber_refs_report(
        book_root, series_root=series, source_command="reorder",
    )
    assert report.most_recent_timestamp is None
    assert report.chapters_with_matches == [2]


def test_renumber_refs_picks_up_logged_invocation(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    _write_command_log(series, [{
        "timestamp": "2026-05-01T09:00:00+00:00",
        "command": "autonovel:reorder",
        "args": ["--from", "5", "--to", "2"],
        "status": "ok",
    }])
    (book_root / "chapters" / "ch_03.md").write_text(
        "---\nchapter: 3\n---\n\nAs in chapter 5, things shifted.\n",
        encoding="utf-8",
    )
    report = impact_mod.build_renumber_refs_report(
        book_root, series_root=series, source_command="reorder",
    )
    assert report.most_recent_timestamp == "2026-05-01T09:00:00+00:00"
    assert report.most_recent_args == ["--from", "5", "--to", "2"]


def test_renumber_refs_unknown_source_returns_empty(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    report = impact_mod.build_renumber_refs_report(
        book_root, series_root=series,
        source_command="not-a-renumber",
    )
    assert report.matches == []
    assert report.chapters_with_matches == []


def test_render_renumber_refs_clean_says_so(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    (book_root / "chapters" / "ch_01.md").write_text(
        "---\nchapter: 1\n---\n\nNothing about other chapters.\n",
        encoding="utf-8",
    )
    report = impact_mod.build_renumber_refs_report(
        book_root, series_root=series, source_command="merge-chapters",
    )
    md = impact_mod.render_renumber_refs_markdown(report)
    assert "Nothing to reconcile" in md


def test_render_renumber_refs_action_plan(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    for n, ref in ((2, "chapter 5"), (4, "Chapter VII")):
        (book_root / "chapters" / f"ch_{n:02d}.md").write_text(
            f"---\nchapter: {n}\n---\n\nAs in {ref}, the day broke.\n",
            encoding="utf-8",
        )
    report = impact_mod.build_renumber_refs_report(
        book_root, series_root=series, source_command="merge-chapters",
    )
    md = impact_mod.render_renumber_refs_markdown(report, book="test-book")
    assert "/autonovel:revise --chapter 2 --book test-book" in md
    assert "/autonovel:revise --chapter 4 --book test-book" in md
    assert "ch 02" in md
    assert "ch 04" in md


def test_cli_impact_of_remove_chapter_json(tmp_path: Path) -> None:
    series, book_root = _build_series(tmp_path)
    (book_root / "chapters" / "ch_03.md").write_text(
        "---\nchapter: 3\n---\n\nSee ch. 12 for context.\n",
        encoding="utf-8",
    )
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "impact-of",
         str(book_root), "--series-root", str(series),
         "--source", "remove-chapter", "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data["report_kind"] == "renumber-refs"
    assert data["source_command"] == "remove-chapter"
    assert data["chapters_with_matches"] == [3]


# ------------------------------------ regression locks for argument-hint


def test_argument_hint_lists_rename_and_renumber_sources(impact_of_cmd) -> None:
    hint = impact_of_cmd.argument_hint or ""
    for src in ("rename-character", "merge-chapters", "reorder", "remove-chapter"):
        assert src in hint, f"missing source {src!r} in argument-hint"
