"""Tier-1 tests for `autonovel _begin` / `_end` lifecycle."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from autonovel import command_log, last_action, lock
from autonovel.housekeeping import lifecycle
from autonovel.housekeeping.scaffold import new_book
from autonovel.paths import SeriesLayout


@pytest.fixture
def demo_series(series_root: Path) -> SeriesLayout:
    series = SeriesLayout(root=series_root)
    new_book(series, book_name="one", pov="Ana")
    return series


def test_begin_creates_lock_and_checkpoint(demo_series: SeriesLayout) -> None:
    result = lifecycle.begin("autonovel:draft", "5 --book one", series=demo_series)
    assert demo_series.lock_file.exists()
    assert result.checkpoint is not None
    # Two writes are declared by commands/draft.md; both should resolve under books/one.
    resolved_strs = {str(p.relative_to(demo_series.root)) for p in result.resolved_writes}
    assert "books/one/chapters/ch_05.md" in resolved_strs
    assert "books/one/pending_canon.md" in resolved_strs

    # Checkpoint snapshotted pending_canon.md (which exists) as .bak and the
    # ch_05.md as .absent.
    cp_dir = result.checkpoint.directory
    assert (cp_dir / "books/one/pending_canon.md.bak").exists()
    assert (cp_dir / "books/one/chapters/ch_05.md.absent").exists()


def test_end_releases_lock_and_writes_last_action(demo_series: SeriesLayout) -> None:
    lifecycle.begin("autonovel:draft", "5 --book one", series=demo_series)
    result = lifecycle.end(
        "autonovel:draft",
        "5 --book one",
        status="ok",
        wrote=["books/one/chapters/ch_05.md"],
        series=demo_series,
    )
    assert not demo_series.lock_file.exists()
    la = last_action.read(demo_series.last_action_file)
    assert la is not None
    assert la.command == "autonovel:draft"
    assert la.book == "one"
    assert la.next_standard_step  # non-empty
    assert "/autonovel:draft" in result.footer  # footer contains the command line
    assert "**Next:**" in result.footer

    log_entries = command_log.read_all(demo_series.command_log_file)
    assert any(e.command == "autonovel:draft" and e.status == "ok" for e in log_entries)


def test_end_error_marks_interrupted_and_skips_last_action(demo_series: SeriesLayout) -> None:
    lifecycle.begin("autonovel:draft", "5 --book one", series=demo_series)
    lifecycle.end(
        "autonovel:draft",
        "5 --book one",
        status="error",
        wrote=[],
        series=demo_series,
    )
    info = lock.read(demo_series.lock_file)
    assert info is not None and info.status == "interrupted"
    assert last_action.read(demo_series.last_action_file) is None
    log_entries = command_log.read_all(demo_series.command_log_file)
    assert any(e.status == "error" for e in log_entries)


def test_begin_refuses_when_live_lock(demo_series: SeriesLayout) -> None:
    lifecycle.begin("autonovel:draft", "5 --book one", series=demo_series)
    with pytest.raises(Exception):
        # A second begin should fail because the lock is held by our own live PID.
        lifecycle.begin("autonovel:next", "--book one", series=demo_series)


def test_begin_unknown_command_raises(demo_series: SeriesLayout) -> None:
    with pytest.raises(lifecycle.BeginError):
        lifecycle.begin("autonovel:nope", "", series=demo_series)


def test_argument_parsing_produces_book_and_chapter() -> None:
    from autonovel.adapters.base import discover_commands
    from autonovel.adapters.installer import _commands_source_dir

    draft = next(c for c in discover_commands(_commands_source_dir()) if c.name == "autonovel:draft")
    ctx = lifecycle._parse_arguments(draft, "7 --book inquisitor")
    assert ctx["book"] == "inquisitor"
    assert ctx["chapter"] == "07"
    assert ctx["prev"] == "06"


# ---------------------------------------------------------------------------
# next-step phase inference (PR-9 fixup) — STATE.md decisions log.
#
# Bug being prevented: book.status in project.yaml is set to "seed" at
# scaffold time and is not advanced by every command. The earlier
# implementation read book.status directly, so a series that had run
# gen-world/characters/canon/voice-discovery/gen-outline still got
# /autonovel:gen-world recommended as "next". The fixed implementation
# infers phase from filesystem artefacts.


def test_next_step_after_gen_outline_is_not_gen_world(demo_series: SeriesLayout) -> None:
    """After /autonovel:gen-outline writes a populated outline.md, the
    next-step recommendation must move past the seed-phase suggestion of
    /autonovel:gen-world."""
    book_root = demo_series.books / "one"
    outline = book_root / "outline.md"
    outline.write_text(
        "# Outline\n\n"
        "## Chapter 1 — Arrival\n"
        "- story_time: 1521-04-12\n"
        "- events: []\n"
        "- beats:\n"
        "  - Tommaso lands at the Rialto.\n"
        "  - The witness fails to appear.\n"
        "  - The fire ledger goes missing.\n",
        encoding="utf-8",
    )
    lifecycle.begin("autonovel:gen-outline", "--book one", series=demo_series)
    result = lifecycle.end(
        "autonovel:gen-outline",
        "--book one",
        status="ok",
        wrote=["books/one/outline.md"],
        series=demo_series,
    )
    assert result.last_action is not None
    assert result.last_action.next_standard_step is not None
    # The bug: this used to be "/autonovel:gen-world" because phase was
    # always "seed". After the fixup it should be anything OTHER than
    # gen-world — evaluate-phase-foundation or draft-1 are acceptable.
    assert "gen-world" not in result.last_action.next_standard_step, (
        f"next-step regressed to gen-world after gen-outline; got "
        f"{result.last_action.next_standard_step!r}"
    )
    assert "**Next:**" in result.footer


def test_next_step_after_drafting_advances_chapter(demo_series: SeriesLayout) -> None:
    """When chapters/ already has a drafted file, next-step must be a
    drafting-phase recommendation, not a foundation-phase one."""
    book_root = demo_series.books / "one"
    chapters = book_root / "chapters"
    chapters.mkdir(exist_ok=True)
    (chapters / "ch_01.md").write_text(
        "---\nbook: one\nchapter: 1\npov: Ana\nstory_time: 2020-01-01\n"
        "events: []\nstatus: draft\n---\n\nProse goes here.\n",
        encoding="utf-8",
    )
    lifecycle.begin("autonovel:draft", "1 --book one", series=demo_series)
    result = lifecycle.end(
        "autonovel:draft",
        "1 --book one",
        status="ok",
        wrote=["books/one/chapters/ch_01.md"],
        series=demo_series,
    )
    next_cmd = result.last_action.next_standard_step
    assert next_cmd is not None
    # Drafting-phase suggestions: draft N+1, revise N, or adversarial-edit all.
    # All start with /autonovel: and are NOT foundation-phase commands.
    assert "gen-world" not in next_cmd
    assert "gen-characters" not in next_cmd
    assert "gen-canon" not in next_cmd
