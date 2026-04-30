"""Tier-1 tests for `autonovel.tui` — the pure functions and the
read-only state loader. The textual App itself runs in an event
loop and is exercised by hand; these tests pin the data shape.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel import tui
from autonovel.paths import SeriesLayout


# ----------------------------------------------------- _sparkline


def test_sparkline_empty_returns_empty_string() -> None:
    assert tui._sparkline([]) == ""
    assert tui._sparkline([None, None, None]) == ""


def test_sparkline_uniform_uses_low_block() -> None:
    out = tui._sparkline([7.0, 7.0, 7.0])
    # All same value → all blocks at the bottom of the range.
    assert out == "▁▁▁"


def test_sparkline_monotonic_increases() -> None:
    out = tui._sparkline([1.0, 2.0, 3.0, 4.0, 5.0])
    assert out[0] == "▁"  # lowest
    assert out[-1] == "█"  # highest


def test_sparkline_none_renders_as_dot() -> None:
    out = tui._sparkline([5.0, None, 8.0])
    assert out[1] == "·"
    assert out[0] in tui._SPARK_BLOCKS
    assert out[2] in tui._SPARK_BLOCKS


# ----------------------------------------------------- slash-command extraction


def test_extract_slash_command_name_simple() -> None:
    assert tui._extract_slash_command_name(
        "/autonovel:revise --chapter 5 --book b"
    ) == "autonovel:revise"


def test_extract_slash_command_name_in_revision_pass() -> None:
    assert tui._extract_slash_command_name(
        "/autonovel:revision-pass --chapters 1-5 --book b"
    ) == "autonovel:revision-pass"


def test_extract_slash_command_name_returns_none_for_bash() -> None:
    """`autonovel _next-actions` is a bash invocation, not a slash-
    command — return None so the caller falls back to the generic
    rationale."""
    assert tui._extract_slash_command_name(
        "autonovel _next-actions --book b"
    ) is None


def test_extract_slash_command_name_returns_none_for_empty() -> None:
    assert tui._extract_slash_command_name("") is None
    assert tui._extract_slash_command_name(None) is None  # type: ignore[arg-type]


# ----------------------------------------------------- _command_index


def test_command_index_returns_known_commands() -> None:
    """The shipped commands include impact-of, evaluate, revise, etc.
    The cache fills lazily; first call must populate."""
    idx = tui._command_index()
    assert "autonovel:evaluate" in idx
    assert "autonovel:revise" in idx
    assert "autonovel:impact-of" in idx


def test_command_index_caches_across_calls() -> None:
    """Same dict object on the second call (cache hit)."""
    a = tui._command_index()
    b = tui._command_index()
    assert a is b


# ----------------------------------------------------- _load_state


def _layout(series_root: Path) -> SeriesLayout:
    return SeriesLayout(root=series_root)


def test_load_state_minimal_series_does_not_crash(
    series_root: Path,
) -> None:
    """A fresh series scaffolded by conftest's `series_root` fixture
    has no chapters / eval logs / research notes / commands. The
    state loader must return a complete dict without raising."""
    from autonovel.housekeeping import scaffold
    layout = _layout(series_root)
    scaffold.new_book(layout, book_name="the-book", pov="POV")
    state = tui._load_state(layout, "the-book")
    # Required keys all present.
    for key in ("series_name", "book", "book_names", "rows",
                "lock_state", "sweep", "cost_today", "cost_total",
                "next_actions", "canonical_action", "recent",
                "foundation", "front_matter", "reviews",
                "pending_canon", "research_notes"):
        assert key in state, f"_load_state missing key {key!r}"


def test_load_state_late_stage_book_populates_rows(
    late_stage_book: tuple[Path, str],
) -> None:
    series, book = late_stage_book
    state = tui._load_state(_layout(series), book)
    # Late-stage fixture has 5 chapters with summaries + 2 eval logs.
    assert len(state["rows"]) == 5
    scored = [r for r in state["rows"] if r.get("score") is not None]
    assert len(scored) >= 2


def test_load_state_includes_pending_canon_status(
    late_stage_book: tuple[Path, str],
) -> None:
    series, book = late_stage_book
    state = tui._load_state(_layout(series), book)
    # Late-stage fixture has pending_canon.md with no conflict header.
    assert state["pending_canon"] in ("clean", "pending entries")


def test_load_state_lists_book_names_in_project(
    late_stage_book: tuple[Path, str],
) -> None:
    series, book = late_stage_book
    state = tui._load_state(_layout(series), book)
    assert book in state["book_names"]


# ----------------------------------------------------- CLI graceful degradation


def test_cli_tui_without_textual_prints_install_hint(
    monkeypatch: pytest.MonkeyPatch, series_root: Path,
) -> None:
    """When textual isn't importable, `autonovel tui` exits 2 with a
    clear pip / pipx install hint instead of stack-tracing."""
    monkeypatch.setattr(tui, "_TEXTUAL_AVAILABLE", False)
    rc = tui.run_tui(series=_layout(series_root))
    assert rc == 2


def test_cli_tui_invalid_series_returns_2(tmp_path: Path) -> None:
    """No series at the cwd → exit 2 with a clear error."""
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "tui",
         "--series", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert out.returncode == 2
