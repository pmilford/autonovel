"""Implementation of `autonovel _begin` and `autonovel _end`.

The adapter-injected preamble/postamble invokes these via Bash. They do all
the lock, checkpoint, last-action, and command-log bookkeeping that
REWRITE-PLAN.md §21.2 requires, so command authors don't reimplement it.
"""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from .. import checkpoints, command_log, last_action, lock, project as project_mod
from ..adapters.base import CommandDef, discover_commands
from ..adapters.installer import _commands_source_dir
from ..paths import SeriesLayout, load_series
from .next_step import PipelineState, next_step


@dataclass
class BeginResult:
    lock_info: lock.LockInfo
    checkpoint: checkpoints.Checkpoint | None
    resolved_writes: list[Path]


class BeginError(RuntimeError):
    pass


def begin(command_name: str, arg_string: str, *, runtime: str = "claude",
          series: SeriesLayout | None = None) -> BeginResult:
    series = series or load_series()
    cmd = _load_command(command_name)
    ctx = _parse_arguments(cmd, arg_string)
    resolved = _resolve_writes(cmd, ctx, series.root)

    lock_info = lock.acquire(
        series.lock_file,
        runtime=runtime,
        command=command_name,
        args=shlex.split(arg_string) if arg_string else [],
    )

    cp: checkpoints.Checkpoint | None = None
    if resolved:
        cp = checkpoints.create(
            series.checkpoints,
            series.root,
            resolved,
            command=command_name,
            args=shlex.split(arg_string) if arg_string else [],
        )

    return BeginResult(lock_info=lock_info, checkpoint=cp, resolved_writes=resolved)


@dataclass
class EndResult:
    last_action: last_action.LastAction | None
    footer: str


def end(command_name: str, arg_string: str, *, status: str, wrote: list[str],
        series: SeriesLayout | None = None) -> EndResult:
    series = series or load_series()
    cmd = _load_command(command_name)
    ctx = _parse_arguments(cmd, arg_string)
    book = ctx.get("book")

    if status != "ok":
        lock.mark_interrupted(series.lock_file)
        command_log.append(
            series.command_log_file,
            command=command_name,
            args=shlex.split(arg_string) if arg_string else [],
            status=status,
            wrote=list(wrote),
            note="workflow reported failure",
        )
        return EndResult(last_action=None, footer="")

    lock.release(series.lock_file)

    ns = _next_step_for(series, book) if book else None
    la = last_action.write(
        series.last_action_file,
        command=command_name,
        args=shlex.split(arg_string) if arg_string else [],
        wrote=list(wrote),
        book=book,
        next_standard_step=ns.command if ns else None,
        next_rationale=ns.rationale if ns else None,
        sidequests=_default_sidequests(command_name, ctx),
    )
    command_log.append(
        series.command_log_file,
        command=command_name,
        args=shlex.split(arg_string) if arg_string else [],
        status="ok",
        wrote=list(wrote),
    )
    return EndResult(last_action=la, footer=_render_footer(command_name, arg_string, wrote, la))


# ---------------------------------------------------------------------------
# Helpers


_ARG_HINT_PLACEHOLDER = re.compile(r"<([^>]+)>")
_PATH_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _load_command(name: str) -> CommandDef:
    for cmd in discover_commands(_commands_source_dir()):
        if cmd.name == name:
            return cmd
    raise BeginError(f"unknown command: {name!r}")


def _parse_arguments(cmd: CommandDef, arg_string: str) -> dict[str, str]:
    """Best-effort parse of $ARGUMENTS into a dict keyed by placeholder name."""
    tokens = shlex.split(arg_string) if arg_string else []
    ctx: dict[str, str] = {}

    # Pull out `--key value` pairs; collect bare positionals separately.
    positionals: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.startswith("--"):
            key = t[2:]
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                ctx[key] = tokens[i + 1]
                i += 2
                continue
            ctx[key] = "true"
            i += 1
            continue
        positionals.append(t)
        i += 1

    # Map positional tokens to `<foo>` entries in the argument-hint, in order.
    if cmd.argument_hint:
        pos_names = [
            m.group(1) for m in _ARG_HINT_PLACEHOLDER.finditer(cmd.argument_hint)
            if not m.group(1).startswith("--")
        ]
        # Skip placeholders that look like `--book <short-name>` (those are flag values).
        bare_positions = [n for n in pos_names if not _looks_like_flag_value(n, cmd.argument_hint)]
        for name, value in zip(bare_positions, positionals):
            key = _normalize_key(name)
            ctx.setdefault(key, value)

    # Derived convenience: chapter → chapter, {prev} → chapter-1 zero-padded.
    if "chapter" in ctx or "chapter_number" in ctx:
        ch = ctx.get("chapter") or ctx.get("chapter_number")
        try:
            n = int(ch)
        except (TypeError, ValueError):
            pass
        else:
            ctx["chapter"] = f"{n:02d}"
            ctx["prev"] = f"{max(n - 1, 0):02d}"
    return ctx


def _looks_like_flag_value(name: str, hint: str) -> bool:
    # A `<short-name>` placeholder that sits after `--book` is a flag value.
    m = re.search(r"--[a-z-]+\s+<" + re.escape(name) + r">", hint)
    return m is not None


def _normalize_key(name: str) -> str:
    return name.replace("-", "_").replace(" ", "_")


def _resolve_writes(cmd: CommandDef, ctx: dict[str, str], series_root: Path) -> list[Path]:
    out: list[Path] = []
    ctx_for_paths = dict(ctx)
    # The argument-hint uses `<short-name>` for the book, but `writes:` uses
    # `{book}`. Remap common aliases.
    if "book" not in ctx_for_paths:
        for alias in ("short-name", "short_name"):
            if alias in ctx_for_paths:
                ctx_for_paths["book"] = ctx_for_paths[alias]
                break
    if "chapter" not in ctx_for_paths and "chapter_number" in ctx_for_paths:
        ctx_for_paths["chapter"] = ctx_for_paths["chapter_number"]

    for raw in cmd.writes:
        resolved = _substitute_placeholders(raw, ctx_for_paths)
        if resolved is None:
            # Unresolved placeholder — skip rather than crash; the command
            # body is responsible for the real write.
            continue
        out.append(series_root / resolved)
    return out


def _substitute_placeholders(path: str, ctx: dict[str, str]) -> str | None:
    def repl(match: re.Match[str]) -> str:
        key = _normalize_key(match.group(1))
        if key not in ctx:
            raise KeyError(key)
        return ctx[key]

    try:
        return _PATH_PLACEHOLDER.sub(repl, path)
    except KeyError:
        return None


def _next_step_for(series: SeriesLayout, book: str) -> object:
    cfg = project_mod.load(series.project_file)
    entry = cfg.book_by_name(book)
    phase = entry.status if entry is not None else "seed"
    state = PipelineState(book=book, phase=phase)
    return next_step(state)


def _default_sidequests(command_name: str, ctx: dict[str, str]) -> list[dict[str, str]]:
    book = ctx.get("book")
    chapter = ctx.get("chapter")
    if command_name == "autonovel:draft" and book and chapter:
        try:
            n = int(chapter)
        except ValueError:
            return []
        return [
            {"command": f"/autonovel:shorten --chapter {n} --target-words 2800 --book {book}",
             "why": "compress without dropping below the 1800-word floor"},
            {"command": f"/autonovel:revise {n} --book {book}",
             "why": "rewrite against a revision brief"},
            {"command": "autonovel rollback",
             "why": "undo this draft entirely"},
        ]
    return []


def _render_footer(command_name: str, arg_string: str, wrote: list[str],
                   la: last_action.LastAction) -> str:
    lines = [
        "",
        "---",
        f"**Done:** /{command_name} {arg_string}".rstrip(),
    ]
    if wrote:
        lines.append("**Wrote:** " + ", ".join(wrote))
    if la.next_standard_step:
        lines.append(f"**Next:** {la.next_standard_step}")
        if la.next_rationale:
            lines.append(f"  *({la.next_rationale})*")
    if la.sidequests:
        lines.append("")
        lines.append("Other options (see `/autonovel:sidequest` for the full list):")
        for sq in la.sidequests:
            lines.append(f"- {sq['command']}")
            if sq.get("why"):
                lines.append(f"    *{sq['why']}*")
    return "\n".join(lines)
