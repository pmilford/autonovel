"""Tier-1 tests for `housekeeping/sweep_progress.py` and the
`autonovel _sweep-*` hidden CLI subcommands.

The sweep-progress file at `.autonovel/sweep-progress.json` is
written by `draft-pass` / `revision-pass` per chapter and read by
`/autonovel:resume` for "continue from chapter N" recovery after
an interrupted sweep.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel.housekeeping import sweep_progress
from autonovel.housekeeping.sweep_progress import SweepProgress
from autonovel.paths import SeriesLayout


# ----------------------------------------------------- helpers


def _layout(series_root: Path) -> SeriesLayout:
    return SeriesLayout(root=series_root)


# ----------------------------------------------------- start / read / clear


def test_start_writes_progress_file(series_root: Path) -> None:
    layout = _layout(series_root)
    progress = sweep_progress.start(
        layout, command="autonovel:draft-pass", book="b", chapters=[5, 6, 7],
    )
    assert progress.command == "autonovel:draft-pass"
    assert progress.book == "b"
    assert progress.chapters == [5, 6, 7]
    assert progress.completed == []
    # File round-trips.
    again = sweep_progress.read(layout)
    assert again is not None
    assert again.chapters == [5, 6, 7]


def test_start_overwrites_prior_progress(series_root: Path) -> None:
    """A new sweep wipes any in-flight tracking — the new sweep is
    the user's chosen recovery path."""
    layout = _layout(series_root)
    sweep_progress.start(layout, command="autonovel:draft-pass", book="b",
                         chapters=[1, 2])
    sweep_progress.mark_done(layout, 1)
    sweep_progress.start(layout, command="autonovel:revision-pass",
                         book="b", chapters=[5, 6])
    progress = sweep_progress.read(layout)
    assert progress is not None
    assert progress.command == "autonovel:revision-pass"
    assert progress.chapters == [5, 6]
    assert progress.completed == []  # wiped


def test_clear_removes_file(series_root: Path) -> None:
    layout = _layout(series_root)
    sweep_progress.start(layout, command="autonovel:draft-pass",
                         book="b", chapters=[1, 2])
    sweep_progress.clear(layout)
    assert sweep_progress.read(layout) is None


def test_read_when_no_file_returns_none(series_root: Path) -> None:
    assert sweep_progress.read(_layout(series_root)) is None


def test_read_handles_corrupt_json_gracefully(series_root: Path) -> None:
    layout = _layout(series_root)
    layout.autonovel.mkdir(parents=True, exist_ok=True)
    (layout.autonovel / "sweep-progress.json").write_text("{not json", encoding="utf-8")
    assert sweep_progress.read(layout) is None


# ----------------------------------------------------- mark_done / failed


def test_mark_done_appends_to_completed(series_root: Path) -> None:
    layout = _layout(series_root)
    sweep_progress.start(layout, command="autonovel:draft-pass",
                         book="b", chapters=[1, 2, 3])
    progress = sweep_progress.mark_done(layout, 2, summary="ch2 ok")
    assert progress is not None
    assert [c.chapter for c in progress.completed] == [2]
    assert progress.completed[0].summary == "ch2 ok"


def test_mark_done_no_progress_silent_noop(series_root: Path) -> None:
    """Stray mark-done call when no sweep is in flight → silent
    no-op (return None). A misbehaving sweep mustn't fail by trying
    to record progress against a non-existent file."""
    layout = _layout(series_root)
    assert sweep_progress.mark_done(layout, 1) is None


def test_mark_done_replaces_prior_record(series_root: Path) -> None:
    """Marking the same chapter done twice updates the record
    instead of duplicating it."""
    layout = _layout(series_root)
    sweep_progress.start(layout, command="autonovel:draft-pass",
                         book="b", chapters=[1])
    sweep_progress.mark_done(layout, 1, summary="first")
    progress = sweep_progress.mark_done(layout, 1, summary="second")
    assert progress is not None
    assert len(progress.completed) == 1
    assert progress.completed[0].summary == "second"


def test_mark_done_clears_prior_failure(series_root: Path) -> None:
    """If a chapter previously failed and is now redone successfully,
    the failure record drops off."""
    layout = _layout(series_root)
    sweep_progress.start(layout, command="autonovel:draft-pass",
                         book="b", chapters=[1])
    sweep_progress.mark_failed(layout, 1, "oops")
    progress = sweep_progress.mark_done(layout, 1, summary="retry ok")
    assert progress is not None
    assert progress.failed == []
    assert len(progress.completed) == 1


def test_mark_failed_appends(series_root: Path) -> None:
    layout = _layout(series_root)
    sweep_progress.start(layout, command="autonovel:draft-pass",
                         book="b", chapters=[1])
    progress = sweep_progress.mark_failed(layout, 1, "context exhausted")
    assert progress is not None
    assert progress.failed[0].chapter == 1
    assert "context exhausted" in progress.failed[0].error


# ----------------------------------------------------- remaining


def test_remaining_excludes_completed(series_root: Path) -> None:
    layout = _layout(series_root)
    sweep_progress.start(layout, command="autonovel:draft-pass",
                         book="b", chapters=[5, 6, 7, 8])
    sweep_progress.mark_done(layout, 5)
    sweep_progress.mark_done(layout, 7)
    progress = sweep_progress.read(layout)
    assert progress is not None
    assert sweep_progress.remaining(progress) == [6, 8]


def test_remaining_includes_failed(series_root: Path) -> None:
    """A failed chapter is still 'remaining' — the user can retry it."""
    layout = _layout(series_root)
    sweep_progress.start(layout, command="autonovel:draft-pass",
                         book="b", chapters=[5, 6])
    sweep_progress.mark_failed(layout, 5, "context")
    progress = sweep_progress.read(layout)
    assert progress is not None
    assert sweep_progress.remaining(progress) == [5, 6]


# ----------------------------------------------------- render_human


def test_render_human_shows_remaining(series_root: Path) -> None:
    layout = _layout(series_root)
    sweep_progress.start(layout, command="autonovel:draft-pass",
                         book="b", chapters=[5, 6, 7])
    sweep_progress.mark_done(layout, 5)
    progress = sweep_progress.read(layout)
    assert progress is not None
    out = sweep_progress.render_human(progress)
    assert "/autonovel:draft-pass" in out
    assert "Remaining: [6, 7]" in out
    assert "--chapters 6,7" in out


def test_render_human_single_remaining_uses_chapter_singular(
    series_root: Path,
) -> None:
    layout = _layout(series_root)
    sweep_progress.start(layout, command="autonovel:revision-pass",
                         book="b", chapters=[5, 6])
    sweep_progress.mark_done(layout, 5)
    progress = sweep_progress.read(layout)
    assert progress is not None
    out = sweep_progress.render_human(progress)
    assert "--chapter 6" in out


def test_render_human_when_complete_says_so(series_root: Path) -> None:
    layout = _layout(series_root)
    sweep_progress.start(layout, command="autonovel:draft-pass",
                         book="b", chapters=[5])
    sweep_progress.mark_done(layout, 5)
    progress = sweep_progress.read(layout)
    assert progress is not None
    out = sweep_progress.render_human(progress)
    assert "All chapters complete" in out


# ----------------------------------------------------- CLI round-trip


def test_cli_sweep_start_status_clear_round_trip(series_root: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(series_root)
    # Start.
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "_sweep-start",
         "--command", "autonovel:draft-pass",
         "--book", "the-book", "--chapters", "5,6,7"],
        capture_output=True, text=True, check=True,
    )
    assert "Sweep tracking started" in out.stdout
    # Status (in flight).
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "_sweep-status",
         "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data["in_flight"] is True
    assert data["chapters"] == [5, 6, 7]
    assert data["remaining"] == [5, 6, 7]
    # Mark done.
    subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "_sweep-mark-done",
         "--chapter", "5", "--summary", "ok"],
        capture_output=True, text=True, check=True,
    )
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "_sweep-status",
         "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data["remaining"] == [6, 7]
    # Clear.
    subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "_sweep-clear"],
        capture_output=True, text=True, check=True,
    )
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "_sweep-status",
         "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data == {"in_flight": False}


def test_cli_sweep_start_accepts_range_syntax(series_root: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(series_root)
    subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "_sweep-start",
         "--command", "autonovel:draft-pass",
         "--book", "b", "--chapters", "5-8"],
        capture_output=True, text=True, check=True,
    )
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "_sweep-status",
         "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data["chapters"] == [5, 6, 7, 8]


def test_cli_sweep_mark_done_silent_when_no_sweep(series_root: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(series_root)
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "_sweep-mark-done",
         "--chapter", "5"],
        capture_output=True, text=True, check=True,
    )
    # Returns 0 (silent no-op).
    assert out.returncode == 0
