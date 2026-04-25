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
    resolved_book: str | None = None
    book_inferred: bool = False  # True if `--book` was missing and we filled it in
    abandoned_lock: lock.LockInfo | None = None  # set when we took over a stale lock


class BeginError(RuntimeError):
    pass


def begin(command_name: str, arg_string: str, *, runtime: str = "claude",
          series: SeriesLayout | None = None) -> BeginResult:
    series = series or load_series()
    cmd = _load_command(command_name)
    ctx = _parse_arguments(cmd, arg_string)

    book_was_explicit = "book" in ctx
    ctx = _infer_book(ctx, series)
    book_inferred = "book" in ctx and not book_was_explicit
    resolved_book = ctx.get("book")

    resolved = _resolve_writes(cmd, ctx, series.root)

    lock_info, abandoned = lock.acquire_with_takeover(
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

    return BeginResult(
        lock_info=lock_info,
        checkpoint=cp,
        resolved_writes=resolved,
        resolved_book=resolved_book,
        book_inferred=book_inferred,
        abandoned_lock=abandoned,
    )


@dataclass
class EndResult:
    last_action: last_action.LastAction | None
    footer: str


def end(command_name: str, arg_string: str, *, status: str, wrote: list[str],
        series: SeriesLayout | None = None) -> EndResult:
    series = series or load_series()
    cmd = _load_command(command_name)
    ctx = _parse_arguments(cmd, arg_string)
    ctx = _infer_book(ctx, series)
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


def _infer_book(ctx: dict[str, str], series: SeriesLayout) -> dict[str, str]:
    """If `--book` was not in `$ARGUMENTS`, fill it in from
    `last-action.json` (the book of the most recent command) or, failing
    that, from a single-book project. If neither yields a book and the
    project has multiple books, leave `ctx` untouched — the caller
    surfaces a usage error.
    """
    if "book" in ctx:
        return ctx

    # 1. Most recent book the user worked on.
    try:
        la = last_action.read(series.last_action_file)
    except Exception:  # noqa: BLE001 — last-action file may be malformed
        la = None
    if la is not None and la.book:
        try:
            cfg = project_mod.load(series.project_file)
        except Exception:  # noqa: BLE001
            cfg = None
        if cfg is not None and cfg.book_by_name(la.book) is not None:
            ctx = dict(ctx)
            ctx["book"] = la.book
            return ctx

    # 2. Single-book series — only one possible book.
    try:
        cfg = project_mod.load(series.project_file)
    except Exception:  # noqa: BLE001
        return ctx
    if len(cfg.books) == 1:
        ctx = dict(ctx)
        ctx["book"] = cfg.books[0].name
        return ctx

    return ctx


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
    """Build a PipelineState for `book` and ask next_step what to suggest.

    Decision order:
      1. Foundation gap — if any of the five foundation artefacts is
         empty, recommend running it. Walks world → characters → voice
         → canon → outline so the user never has to remember the
         sequence.
      2. Pending-canon gate — if `pending_canon.md` has entries that
         haven't been promoted, surface that *between* chapters (after
         a draft is evaluated, before the next is started) so chapter
         N+1 sees the new facts. Skipped during foundation phase since
         no canon candidates exist yet.
      3. Generic next_step decision tree — phase-driven (drafting →
         evaluate → revise / advance, etc.). Phase is inferred from the
         filesystem rather than `project.yaml :: books[].status` to
         keep the recommendation self-correcting after rollbacks.
    """
    cfg = project_mod.load(series.project_file)
    entry = cfg.book_by_name(book)
    book_root = series.books / book

    missing = _foundation_gap(series, book_root)
    if missing is not None:
        from .next_step import NextStep
        return NextStep(command=missing.command, rationale=missing.rationale)

    pending = _pending_canon_gate(series, book_root)
    if pending is not None:
        from .next_step import NextStep
        return NextStep(command=pending.command, rationale=pending.rationale)

    phase, chapters_drafted = _infer_phase(series, book_root)
    state = PipelineState(
        book=book,
        phase=phase,
        chapters_drafted=chapters_drafted,
        foundation_threshold=cfg.defaults.get("foundation_threshold", 7.5),
        chapter_threshold=cfg.defaults.get("chapter_threshold", 6.0),
    )

    # Read the latest chapter's eval score from eval_logs/ if any
    # exists. Without this, /autonovel:next loops on "evaluate
    # --chapter N" because next_step's drafting branch can't decide
    # between "advance" and "revise" without a score, and falls back
    # to recommending evaluate. Author hit this 2026-04-25.
    if chapters_drafted > 0:
        last_n = chapters_drafted
        score = _last_eval_score(book_root, last_n)
        state.last_chapter_number = last_n
        state.last_chapter_score = score

    if entry is not None and _phase_rank(entry.status) > _phase_rank(state.phase):
        state.phase = entry.status
    return next_step(state)


def _last_eval_score(book_root: Path, chapter: int) -> float | None:
    """Return the most recent `overall_score` recorded for `chapter` in
    `books/<book>/eval_logs/`, or None if no eval has run yet."""
    eval_dir = book_root / "eval_logs"
    if not eval_dir.is_dir():
        return None
    candidates = sorted(eval_dir.glob(f"ch{chapter:02d}*.json"))
    if not candidates:
        return None
    import json
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    score = data.get("overall_score")
    try:
        return float(score) if score is not None else None
    except (TypeError, ValueError):
        return None


@dataclass
class _FoundationGap:
    command: str
    rationale: str


def _pending_canon_gate(series: SeriesLayout, book_root: Path) -> "_FoundationGap | None":
    """Return a `promote-canon` recommendation when:
      - the user has at least one drafted chapter (drafting / revision
        phase — no canon candidates exist before drafting starts),
      - `books/<book>/pending_canon.md` has content beyond its
        template stub,
      - and the file's modification time is newer than the most recent
        run of `/autonovel:promote-canon` for this series (so we don't
        re-suggest a freshly-emptied pending file).

    Returning None means "no gate" — fall through to the generic
    next_step decision tree.
    """
    from ..paths import iter_chapter_files
    chapters_dir = book_root / "chapters"
    if not chapters_dir.is_dir():
        return None
    drafted = bool(iter_chapter_files(chapters_dir))
    if not drafted:
        return None

    pending = book_root / "pending_canon.md"
    if not _pending_canon_has_entries(pending):
        return None

    # Skip if pending_canon.md is older than the last successful
    # /autonovel:promote-canon run (logged in command-log.jsonl).
    last_promote = _last_command_run(series, "autonovel:promote-canon")
    if last_promote is not None and pending.stat().st_mtime <= last_promote:
        return None

    book_name = book_root.name
    return _FoundationGap(
        command=f"/autonovel:promote-canon --book {book_name}",
        rationale=(
            "pending_canon.md has new candidate facts; promote them so "
            "the next chapter draft sees them"
        ),
    )


def _pending_canon_has_entries(pending_path: Path) -> bool:
    """True if `pending_canon.md` carries at least one bullet entry of
    its expected `- [headline] body` shape. Robust to template length
    drift; we don't compare byte counts because real candidate entries
    are often shorter than the template's explanatory text."""
    if not pending_path.is_file():
        return False
    try:
        text = pending_path.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ", "+ ")) and len(stripped) > 4:
            return True
    return False


def _last_command_run(series: SeriesLayout, command_name: str) -> float | None:
    """Return the UNIX timestamp of the most recent successful run of
    `command_name`, or None if there isn't one. Reads
    `.autonovel/command-log.jsonl`."""
    from datetime import datetime
    from .. import command_log
    try:
        entries = command_log.read_all(series.command_log_file)
    except Exception:  # noqa: BLE001
        return None
    latest: float | None = None
    for e in entries:
        if e.command != command_name or e.status != "ok":
            continue
        try:
            ts = datetime.fromisoformat(e.timestamp).timestamp()
        except (ValueError, AttributeError):
            continue
        if latest is None or ts > latest:
            latest = ts
    return latest


def _foundation_gap(series: SeriesLayout, book_root: Path) -> "_FoundationGap | None":
    """Return the first missing foundation artefact, or None if all are
    in place. Order:
      0. (period-only) research-from-seed if `project.yaml :: period.start`
         is set and `shared/research/notes/` is empty. Skipped for
         contemporary projects with no period.
      1-5. world → characters → voice → canon → outline.
    """
    book_name = book_root.name

    # Step 0: research-from-seed when the project has a period set, so
    # gen-world and gen-canon are built on cited primary sources rather
    # than the LLM's general knowledge.
    if _project_has_period(series) and not _research_notes_populated(series):
        return _FoundationGap(
            command=f"/autonovel:research --from-seed --book {book_name}",
            rationale=(
                "project has a period set but shared/research/notes/ is "
                "empty; research the seed before generating world/canon"
            ),
        )

    checks = [
        (series.shared / "world.md", "/autonovel:gen-world",
         "shared/world.md is empty; foundation starts with the world"),
        (series.shared / "characters.md", "/autonovel:gen-characters",
         "shared/characters.md is empty; cast registry comes after the world"),
        (book_root / "voice.md", f"/autonovel:voice-discovery --book {book_name}",
         "voice.md Part 2 is unfilled; pick a voice before generating canon"),
        (series.shared / "canon.md", "/autonovel:gen-canon",
         "shared/canon.md is empty; seed hard facts before outlining"),
        (book_root / "outline.md", f"/autonovel:gen-outline --book {book_name}",
         "outline.md is empty; outline before drafting"),
    ]
    for path, command, rationale in checks:
        if not _is_populated(path, min_chars=120,
                             exclude_markers=("(empty", "Generated by", "Seeded by", "Filled by", "Leave empty until then")):
            return _FoundationGap(command=command, rationale=rationale)
    return None


def _project_has_period(series: SeriesLayout) -> bool:
    """True when `project.yaml :: period.start` is non-null. Used to
    decide whether to insert research-from-seed at the front of the
    foundation chain."""
    try:
        cfg = project_mod.load(series.project_file)
    except Exception:  # noqa: BLE001
        return False
    period = cfg.period or {}
    return period.get("start") not in (None, "")


def _research_notes_populated(series: SeriesLayout) -> bool:
    """True when `shared/research/notes/` contains at least one .md
    file with substantive content. Ignores `.gitkeep` and template
    placeholders."""
    notes_dir = series.shared / "research" / "notes"
    if not notes_dir.is_dir():
        return False
    for p in notes_dir.glob("*.md"):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if "# Research" in text and len(text.strip()) > 200:
            return True
    return False


# Rank phases so we can pick the more-advanced of "filesystem says X,
# project.yaml says Y". Unknown phases sort below "seed".
_PHASE_ORDER = (
    "unknown", "seed", "foundation", "outlined", "drafting",
    "revision", "review", "export", "done",
)


def _phase_rank(phase: str) -> int:
    try:
        return _PHASE_ORDER.index(phase)
    except ValueError:
        return 0


def _infer_phase(series: SeriesLayout, book_root: Path) -> tuple[str, int]:
    """Walk the on-disk artefacts and return (phase, chapters_drafted).

    Order of checks is most-advanced first: a book that has been drafted
    and reviewed should not regress to "outlined" because outline.md
    still exists.
    """
    from ..paths import iter_chapter_files
    chapters_dir = book_root / "chapters"
    chapter_files = iter_chapter_files(chapters_dir)
    n_chapters = len(chapter_files)

    # Drafting / revision: chapters exist.
    if n_chapters > 0:
        # We don't yet distinguish drafting from revision from review at
        # the filesystem level (the project would need eval_logs / review
        # markers). next_step's drafting branch handles "draft N+1 vs
        # revise N" via last_chapter_score, which we don't have here —
        # so default to drafting and let the user fall through to the
        # standard next-chapter recommendation.
        return ("drafting", n_chapters)

    # Outlined: outline.md is non-trivial.
    outline = book_root / "outline.md"
    if _is_populated(outline, min_chars=120, exclude_markers=("(empty",)):
        return ("foundation", 0)  # foundation phase, but next_step's
        # foundation branch recommends draft-1 when foundation_score
        # ≥ threshold; without that score we let the user run evaluate
        # to advance.

    # Voice discovered.
    voice = book_root / "voice.md"
    if _is_populated(voice, min_chars=400, exclude_markers=("(empty", "Generated by", "Seeded by", "Filled by", "Leave empty until then")):
        return ("foundation", 0)

    # Foundation under way: any of the shared/ files written.
    for fname in ("world.md", "characters.md", "canon.md"):
        if _is_populated(series.shared / fname, min_chars=120,
                         exclude_markers=("(empty", "Generated by", "Seeded by", "Filled by", "Leave empty until then")):
            return ("foundation", 0)

    return ("seed", 0)


def _is_populated(path: Path, *, min_chars: int, exclude_markers: tuple[str, ...]) -> bool:
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    stripped = text.strip()
    if len(stripped) < min_chars:
        return False
    if any(marker in text for marker in exclude_markers):
        return False
    return True


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
