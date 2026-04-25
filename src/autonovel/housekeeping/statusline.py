"""`autonovel statusline` — one-line summary for Claude Code's status bar.

Claude Code reads `statusLine.command`'s stdout and renders it. The
command must be fast (<200ms ideally; runs on every prompt) and must
not crash — if it errors, Claude Code silently suppresses the line.

Output format (mid-dot separators):

    medieval-king-maker · foundation · ch1 6.0 · idle  │  sonnet-4-6 · 12% · think:high · $0.42

Sections:
  - autonovel half: book, phase, last chapter (and score if known),
    lock state.
  - claude half: model, context-used %, thinking effort, session cost
    — pulled from whatever Claude Code passes us (stdin JSON if
    available, env vars as fallback). Missing fields are dropped.

Both halves degrade gracefully: outside a series, the autonovel half
is empty; without Claude Code session data, the claude half is empty.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from .. import last_action as last_action_mod
from .. import lock as lock_mod
from .. import project as project_mod
from ..paths import SeriesLayout, SeriesNotFound, find_series_root


SEP = " · "
HALF_SEP = "  │  "


@dataclass
class StatusContext:
    series_name: str | None = None
    book: str | None = None
    phase: str | None = None
    last_chapter_n: int | None = None
    last_chapter_score: float | None = None
    lock_status: str = "idle"  # idle | live | interrupted | abandoned | running
    lock_command: str | None = None  # name of the in-flight /autonovel:* command, if any

    model: str | None = None
    context_pct: int | None = None
    thinking_effort: str | None = None
    cost_usd: float | None = None


def gather(stdin_data: str | None = None, env: dict[str, str] | None = None) -> StatusContext:
    """Build a StatusContext from filesystem state and Claude Code session
    data. Both inputs are optional/pluggable so the function is testable
    without spawning Claude."""
    env = env if env is not None else dict(os.environ)
    ctx = StatusContext()

    try:
        series_root = find_series_root()
    except SeriesNotFound:
        _enrich_from_claude_session(ctx, stdin_data, env)
        return ctx

    series = SeriesLayout(root=series_root)
    _read_series(ctx, series)
    _enrich_from_claude_session(ctx, stdin_data, env)
    return ctx


def _read_series(ctx: StatusContext, series: SeriesLayout) -> None:
    try:
        cfg = project_mod.load(series.project_file)
        ctx.series_name = cfg.series_name
    except Exception:  # noqa: BLE001
        pass

    try:
        la = last_action_mod.read(series.last_action_file)
        if la is not None and la.book:
            ctx.book = la.book
    except Exception:  # noqa: BLE001
        pass

    # Single-book fallback when there's no last-action.
    if ctx.book is None:
        try:
            cfg = project_mod.load(series.project_file)
            if len(cfg.books) == 1:
                ctx.book = cfg.books[0].name
        except Exception:  # noqa: BLE001
            pass

    try:
        info = lock_mod.read(series.lock_file)
        if info is not None:
            ctx.lock_status = info.status or "live"
            # Surface the active command so a "stuck-looking"
            # statusline (Claude Code refreshes on user input only,
            # so during a long sweep the chapter count appears
            # frozen) at least tells the user WHAT is in flight.
            if info.command:
                ctx.lock_command = info.command
    except Exception:  # noqa: BLE001
        pass

    if ctx.book:
        # Defer the import to avoid a circular module-load on early CLI
        # bring-up — lifecycle imports next_step which imports project, etc.
        from .lifecycle import _infer_phase
        try:
            phase, n_chapters = _infer_phase(series, series.books / ctx.book)
            ctx.phase = phase
            if n_chapters > 0:
                ctx.last_chapter_n = n_chapters
        except Exception:  # noqa: BLE001
            pass


def _enrich_from_claude_session(ctx: StatusContext, stdin_data: str | None,
                                env: dict[str, str]) -> None:
    """Claude Code's session data arrives via either stdin JSON or env
    vars depending on version. Try stdin first, fall back to env, leave
    fields None if neither yields anything."""
    payload: dict | None = None
    if stdin_data and stdin_data.strip():
        try:
            payload = json.loads(stdin_data)
        except Exception:  # noqa: BLE001
            payload = None

    if isinstance(payload, dict):
        model = payload.get("model")
        if isinstance(model, dict):
            ctx.model = model.get("display_name") or model.get("id")
        elif isinstance(model, str):
            ctx.model = model

        usage = payload.get("usage") or payload.get("session") or {}
        ctx.context_pct = _coerce_int(usage.get("context_pct"))
        ctx.cost_usd = _coerce_float(usage.get("cost_usd") or usage.get("cost"))
        ctx.thinking_effort = usage.get("thinking") or payload.get("thinking_effort")

    # Env-var fallbacks, only fill what stdin missed.
    if ctx.model is None:
        ctx.model = (
            env.get("CLAUDE_MODEL_DISPLAY_NAME")
            or env.get("CLAUDE_MODEL_ID")
            or env.get("CLAUDE_MODEL")
        )
    if ctx.context_pct is None:
        ctx.context_pct = _coerce_int(env.get("CLAUDE_CONTEXT_PCT"))
    if ctx.cost_usd is None:
        ctx.cost_usd = _coerce_float(env.get("CLAUDE_COST_USD") or env.get("CLAUDE_SESSION_COST"))
    if ctx.thinking_effort is None:
        ctx.thinking_effort = env.get("CLAUDE_THINKING_EFFORT") or env.get("CLAUDE_THINKING")


def _coerce_int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _coerce_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def render(ctx: StatusContext) -> str:
    """Format the context as a one-line status string. Pure function;
    Tier-1 testable without filesystem or Claude Code."""
    autonovel_parts: list[str] = []
    if ctx.book:
        autonovel_parts.append(ctx.book)
    if ctx.phase and ctx.phase not in ("seed", "unknown"):
        autonovel_parts.append(ctx.phase)
    elif ctx.phase == "seed":
        autonovel_parts.append("seed")
    if ctx.last_chapter_n is not None:
        ch = f"ch{ctx.last_chapter_n:02d}"
        if ctx.last_chapter_score is not None:
            ch = f"{ch} {ctx.last_chapter_score:.1f}"
        autonovel_parts.append(ch)
    # Only surface the lock label when we have *some* autonovel context.
    # Outside a series the lock state is meaningless; rendering "idle"
    # alongside Claude session info would be confusing.
    if autonovel_parts:
        label = _lock_label(ctx.lock_status)
        # When a sweep / long command holds the lock, show its name
        # so a frozen-looking statusline (Claude Code refreshes on
        # user input only) at least tells the user what is running.
        if ctx.lock_command and label not in ("idle",):
            short = ctx.lock_command.replace("autonovel:", "")
            label = f"◍ {short}"
        autonovel_parts.append(label)

    claude_parts: list[str] = []
    if ctx.model:
        claude_parts.append(ctx.model)
    if ctx.context_pct is not None:
        claude_parts.append(f"{ctx.context_pct}%")
    if ctx.thinking_effort:
        claude_parts.append(f"think:{ctx.thinking_effort}")
    if ctx.cost_usd is not None:
        claude_parts.append(f"${ctx.cost_usd:.2f}")

    autonovel_half = SEP.join(autonovel_parts) if autonovel_parts else ""
    claude_half = SEP.join(claude_parts) if claude_parts else ""

    if autonovel_half and claude_half:
        return f"{autonovel_half}{HALF_SEP}{claude_half}"
    return autonovel_half or claude_half


def _lock_label(status: str) -> str:
    """Translate the lock's internal status string to a one-word label."""
    if status in ("idle", "released", "", None):
        return "idle"
    if status in ("live", "running"):
        return "in-flight"
    if status == "interrupted":
        return "INTERRUPTED"
    if status == "abandoned":
        return "abandoned"
    return status


def main() -> int:
    """CLI entry. Reads stdin if a non-tty is attached (Claude Code may
    pipe JSON in); falls back to env vars. Errors are swallowed so a
    misbehaving statusline never crashes Claude Code."""
    try:
        stdin_data: str | None = None
        if not sys.stdin.isatty():
            try:
                stdin_data = sys.stdin.read()
            except Exception:  # noqa: BLE001
                stdin_data = None
        ctx = gather(stdin_data=stdin_data)
        line = render(ctx)
        if line:
            print(line)
    except Exception:  # noqa: BLE001
        # Never let a bad statusline trip Claude Code.
        return 0
    return 0
