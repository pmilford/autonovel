"""Tier-1 tests for `autonovel statusline` and `autonovel statusline-setup`.

The render function is pure — no filesystem, no Claude Code subprocess —
so we lock its output shape across the obvious context combinations.
The setup function is exercised against tmp_path series scaffolds.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autonovel.housekeeping import statusline, statusline_setup
from autonovel.housekeeping.scaffold import new_book, new_series
from autonovel.paths import SeriesLayout


# -------------------------------------------------------------------- render


def test_render_full_context() -> None:
    ctx = statusline.StatusContext(
        book="medieval-king-maker",
        phase="foundation",
        last_chapter_n=1,
        last_chapter_score=6.0,
        lock_status="idle",
        model="claude-sonnet-4-6",
        context_pct=12,
        thinking_effort="high",
        cost_usd=0.42,
    )
    line = statusline.render(ctx)
    assert "medieval-king-maker" in line
    assert "foundation" in line
    assert "ch01 6.0" in line
    assert "idle" in line
    assert "claude-sonnet-4-6" in line
    assert "12%" in line
    assert "think:high" in line
    assert "$0.42" in line
    # The two halves are split by │ when both are non-empty.
    assert "│" in line


def test_render_no_series() -> None:
    """Outside any series the autonovel half is empty; only Claude
    session info renders."""
    ctx = statusline.StatusContext(
        model="claude-opus-4-7",
        context_pct=8,
        cost_usd=0.10,
    )
    line = statusline.render(ctx)
    assert "│" not in line, "no autonovel half → no separator"
    assert "claude-opus-4-7" in line
    assert "$0.10" in line


def test_render_no_claude_session() -> None:
    """Without Claude session data (running outside Claude) only the
    autonovel half renders."""
    ctx = statusline.StatusContext(
        book="my-book",
        phase="drafting",
        last_chapter_n=3,
        lock_status="idle",
    )
    line = statusline.render(ctx)
    assert "│" not in line
    assert "my-book" in line
    assert "drafting" in line
    assert "ch03" in line


def test_render_in_flight_lock() -> None:
    """`live` lock status renders as `in-flight`."""
    ctx = statusline.StatusContext(book="b", lock_status="live")
    assert "in-flight" in statusline.render(ctx)


def test_render_interrupted_lock_is_loud() -> None:
    """An interrupted lock should be visible — uppercase as a flag."""
    ctx = statusline.StatusContext(book="b", lock_status="interrupted")
    assert "INTERRUPTED" in statusline.render(ctx)


def test_render_drops_seed_phase_when_chapters_present() -> None:
    """If we have a chapter count, surface that even at the seed phase.
    The phase label is the secondary signal."""
    ctx = statusline.StatusContext(book="b", phase="seed", last_chapter_n=1)
    line = statusline.render(ctx)
    assert "ch01" in line


def test_render_empty_when_no_signal() -> None:
    """Brand-new context with nothing populated — render produces an
    empty string rather than crashing or showing a lone `idle`."""
    ctx = statusline.StatusContext()
    out = statusline.render(ctx)
    assert out == ""


# -------------------------------------------------------------------- gather


def test_gather_outside_series(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    ctx = statusline.gather(stdin_data=None, env={})
    assert ctx.book is None
    assert ctx.series_name is None
    assert ctx.lock_status == "idle"


def test_gather_reads_series(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    res = new_series(tmp_path / "demo", series_name="demo")
    new_book(res.series, book_name="one")
    monkeypatch.chdir(res.series.root)

    ctx = statusline.gather(stdin_data=None, env={})
    assert ctx.series_name == "demo"
    # Single-book project — book auto-inferred even without last-action.
    assert ctx.book == "one"
    # No chapters drafted yet — phase is seed (foundation gap not yet checked).
    assert ctx.phase in ("seed", "foundation")


def test_gather_picks_up_claude_env_vars(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    env = {
        "CLAUDE_MODEL_DISPLAY_NAME": "Sonnet 4.6",
        "CLAUDE_CONTEXT_PCT": "23",
        "CLAUDE_COST_USD": "0.17",
        "CLAUDE_THINKING_EFFORT": "medium",
    }
    ctx = statusline.gather(stdin_data=None, env=env)
    assert ctx.model == "Sonnet 4.6"
    assert ctx.context_pct == 23
    assert ctx.cost_usd == 0.17
    assert ctx.thinking_effort == "medium"


def test_gather_picks_up_stdin_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    payload = json.dumps({
        "model": {"display_name": "Opus 4.7", "id": "claude-opus-4-7"},
        "usage": {"context_pct": 45, "cost_usd": 1.25},
        "thinking_effort": "high",
    })
    ctx = statusline.gather(stdin_data=payload, env={})
    assert ctx.model == "Opus 4.7"
    assert ctx.context_pct == 45
    assert ctx.cost_usd == 1.25
    assert ctx.thinking_effort == "high"


# -------------------------------------------------------------------- setup


def test_setup_creates_settings_file(tmp_path: Path) -> None:
    res = new_series(tmp_path / "demo", series_name="demo")
    series = res.series

    result = statusline_setup.setup(series)
    assert result.settings_path == series.root / ".claude" / "settings.json"
    assert result.settings_path.is_file()
    assert result.created is True
    assert result.statusline_added is True
    assert result.permissions_added > 0

    data = json.loads(result.settings_path.read_text(encoding="utf-8"))
    assert data["statusLine"]["command"] == "autonovel statusline"
    allow = data["permissions"]["allow"]
    assert "Read" in allow
    assert "Write" in allow
    assert any(p.startswith("Bash(autonovel") for p in allow)


def test_setup_is_idempotent(tmp_path: Path) -> None:
    res = new_series(tmp_path / "demo", series_name="demo")
    series = res.series
    first = statusline_setup.setup(series)
    second = statusline_setup.setup(series)
    assert second.created is False
    assert second.permissions_added == 0
    assert second.permissions_already_present > 0
    # Running twice does not duplicate allow entries.
    data = json.loads(first.settings_path.read_text(encoding="utf-8"))
    allow = data["permissions"]["allow"]
    assert len(allow) == len(set(allow))


def test_setup_preserves_existing_keys(tmp_path: Path) -> None:
    res = new_series(tmp_path / "demo", series_name="demo")
    series = res.series
    settings = series.root / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({
        "theme": "dark",
        "permissions": {"allow": ["Read", "MyCustomTool"]},
    }), encoding="utf-8")

    statusline_setup.setup(series)

    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["theme"] == "dark"
    allow = data["permissions"]["allow"]
    assert "MyCustomTool" in allow  # user's entry preserved
    assert "Read" in allow          # already present, kept once
    assert allow.count("Read") == 1


def test_setup_force_overwrites_statusline(tmp_path: Path) -> None:
    res = new_series(tmp_path / "demo", series_name="demo")
    series = res.series
    settings = series.root / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({
        "statusLine": {"type": "command", "command": "echo old"},
    }), encoding="utf-8")

    # Without --force, the existing statusLine is left alone.
    r1 = statusline_setup.setup(series, force=False)
    assert r1.statusline_added is False
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["statusLine"]["command"] == "echo old"

    # With --force, it gets overwritten.
    r2 = statusline_setup.setup(series, force=True)
    assert r2.statusline_added is True
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["statusLine"]["command"] == "autonovel statusline"


def test_setup_refuses_invalid_json_without_force(tmp_path: Path) -> None:
    res = new_series(tmp_path / "demo", series_name="demo")
    series = res.series
    settings = series.root / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(statusline_setup.SetupError):
        statusline_setup.setup(series, force=False)


def test_setup_force_recovers_from_invalid_json(tmp_path: Path) -> None:
    res = new_series(tmp_path / "demo", series_name="demo")
    series = res.series
    settings = series.root / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text("{garbage", encoding="utf-8")
    result = statusline_setup.setup(series, force=True)
    assert result.statusline_added is True
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["statusLine"]["command"] == "autonovel statusline"


def test_render_shows_active_command_during_sweep() -> None:
    """When a sweep command holds the lock, the statusline shows
    `◍ <command>` instead of just `in-flight` so the user knows
    *what* is running even when Claude Code's statusline refresh
    cadence makes the chapter count appear frozen."""
    ctx = statusline.StatusContext(
        book="b",
        phase="drafting",
        last_chapter_n=3,
        lock_status="running",
        lock_command="autonovel:draft-pass",
    )
    line = statusline.render(ctx)
    assert "◍ draft-pass" in line


def test_render_no_command_label_when_idle() -> None:
    """If the lock is idle, the active-command marker doesn't render
    (there's nothing to show)."""
    ctx = statusline.StatusContext(
        book="b",
        phase="drafting",
        last_chapter_n=3,
        lock_status="idle",
        lock_command="autonovel:draft-pass",   # stale, should not surface
    )
    line = statusline.render(ctx)
    assert "◍" not in line
    assert "idle" in line


def test_running_status_maps_to_in_flight_when_no_command() -> None:
    """LockInfo.status defaults to 'running'; the label should
    normalise to 'in-flight' when no command name is present."""
    ctx = statusline.StatusContext(book="b", lock_status="running")
    assert "in-flight" in statusline.render(ctx)


# -------------------------------------------------------------- debug capture


def test_debug_dump_writes_payload(tmp_path: Path, monkeypatch) -> None:
    """When AUTONOVEL_STATUSLINE_DEBUG=1, statusline.main writes a
    single-shot diagnostic to ~/.autonovel-statusline-debug.log
    containing the raw stdin, the parsed StatusContext fields, the
    rendered line, and any CLAUDE_*/AUTONOVEL_* env vars. This is the
    documented diagnostic for "the percentage doesn't show up" — the
    file reveals the actual JSON schema Claude Code is sending so the
    statusline's path list can be updated."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AUTONOVEL_STATUSLINE_DEBUG", "1")
    monkeypatch.setenv("CLAUDE_MODEL", "claude-sonnet-4-6")

    payload = json.dumps({
        "model": {"display_name": "Sonnet 4.6", "id": "claude-sonnet-4-6"},
        "usage": {"context_pct": 42},
        "cost": {"total_cost_usd": 1.23},
    })

    class _StubStdin:
        def isatty(self) -> bool:
            return False
        def read(self) -> str:
            return payload

    import sys as _sys
    monkeypatch.setattr(_sys, "stdin", _StubStdin())

    rc = statusline.main()
    assert rc == 0

    dump_path = Path(tmp_path) / ".autonovel-statusline-debug.log"
    assert dump_path.exists(), "debug-mode flag should produce a dump"
    dump = json.loads(dump_path.read_text())

    assert dump["stdin_raw"] == payload
    assert dump["stdin_parsed"]["usage"]["context_pct"] == 42
    assert dump["context"]["model"] == "Sonnet 4.6"
    assert dump["context"]["context_pct"] == 42
    assert "42%" in dump["rendered_line"]
    # CLAUDE_* / AUTONOVEL_* env vars are echoed for diagnosis.
    assert dump["env_relevant"]["CLAUDE_MODEL"] == "claude-sonnet-4-6"
    assert dump["env_relevant"]["AUTONOVEL_STATUSLINE_DEBUG"] == "1"


def test_context_pct_from_remaining_pct() -> None:
    """Newer Claude Code releases nest context info under
    `context_window` and report `remaining_pct`. Convert remaining→used
    at the read site so the statusline keeps showing 'used %'."""
    payload = json.dumps({
        "model": {"display_name": "Sonnet 4.6", "id": "claude-sonnet-4-6"},
        "context_window": {"remaining_pct": 73},
    })
    ctx = statusline.gather(stdin_data=payload, env={})
    assert ctx.context_pct == 27, "100 - 73 = 27% used"


def test_context_pct_from_used_pct() -> None:
    """Some Claude Code releases use `used_pct` directly under
    `context_window`. Read it as-is."""
    payload = json.dumps({
        "model": "claude-opus-4-7",
        "context_window": {"used_pct": 41},
    })
    ctx = statusline.gather(stdin_data=payload, env={})
    assert ctx.context_pct == 41


def test_context_pct_from_token_counts_inside_context_window() -> None:
    """Fallback path: payload carries raw token counts under
    `context_window` (tokens_used + total_tokens) instead of a direct
    percentage. Compute used % against the window declared in the same
    block, not the per-model default — this is what GPD relies on."""
    payload = json.dumps({
        "model": {"id": "claude-sonnet-4-6"},
        "context_window": {"tokens_used": 50_000, "total_tokens": 200_000},
    })
    ctx = statusline.gather(stdin_data=payload, env={})
    assert ctx.context_pct == 25


def test_context_pct_remaining_zero_means_full() -> None:
    """remaining=0 should render as 100% used (not None), so the bar
    stays informative when the model is at the wall."""
    payload = json.dumps({
        "model": "claude-opus-4-7",
        "context_window": {"remaining_pct": 0},
    })
    ctx = statusline.gather(stdin_data=payload, env={})
    assert ctx.context_pct == 100


def test_context_pct_legacy_path_still_works() -> None:
    """Old `usage.context_pct` path still resolves. Regression guard for
    older Claude Code versions or alternative runtimes."""
    payload = json.dumps({
        "model": "claude-sonnet-4-6",
        "usage": {"context_pct": 12},
    })
    ctx = statusline.gather(stdin_data=payload, env={})
    assert ctx.context_pct == 12


def test_debug_dump_skipped_when_flag_unset(tmp_path: Path, monkeypatch) -> None:
    """No env var → no dump file. The diagnostic is opt-in; we don't
    want every prompt-render writing a file under the user's home."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("AUTONOVEL_STATUSLINE_DEBUG", raising=False)

    class _StubStdin:
        def isatty(self) -> bool:
            return False
        def read(self) -> str:
            return ""

    import sys as _sys
    monkeypatch.setattr(_sys, "stdin", _StubStdin())

    rc = statusline.main()
    assert rc == 0

    dump_path = Path(tmp_path) / ".autonovel-statusline-debug.log"
    assert not dump_path.exists(), "debug dump must be opt-in"
