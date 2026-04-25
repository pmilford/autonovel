"""Tier-2 contract tests.

For every command file:
  - every path under `reads:` is mentioned by the body,
  - every path under `writes:` is mentioned by the body,
  - every `{placeholder}` in paths is either declared in argument-hint,
    derivable (prev = chapter - 1), or a shell glob (`*`).

And: new-series -> new-book produces the template files that commands declare
under their `reads:` list (for paths that don't depend on runtime state).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from autonovel.adapters.base import CommandDef, discover_commands
from autonovel.adapters.installer import _commands_source_dir
from autonovel.housekeeping import scaffold
from autonovel.paths import SeriesLayout


KNOWN_PLACEHOLDERS = {"book", "chapter", "prev", "topic"}


def _all_commands() -> list[CommandDef]:
    return discover_commands(_commands_source_dir())


@pytest.mark.parametrize("cmd", _all_commands(), ids=lambda c: c.name)
def test_reads_paths_mentioned_in_body(cmd: CommandDef) -> None:
    for path in cmd.reads:
        stem = _path_stem(path)
        assert stem in cmd.body, (
            f"{cmd.name}: declares reads `{path}` but `{stem}` never appears in body"
        )


@pytest.mark.parametrize("cmd", _all_commands(), ids=lambda c: c.name)
def test_writes_paths_mentioned_in_body(cmd: CommandDef) -> None:
    for path in cmd.writes:
        stem = _path_stem(path)
        assert stem in cmd.body, (
            f"{cmd.name}: declares writes `{path}` but `{stem}` never appears in body"
        )


@pytest.mark.parametrize("cmd", _all_commands(), ids=lambda c: c.name)
def test_placeholders_are_declared(cmd: CommandDef) -> None:
    placeholders = _collect_placeholders(cmd.reads + cmd.writes)
    if not placeholders:
        return
    hint = cmd.argument_hint or ""
    for ph in placeholders:
        if ph in KNOWN_PLACEHOLDERS:
            continue
        # Allow things like `{book}` to be present in the hint text.
        assert ph in hint, (
            f"{cmd.name}: placeholder `{{{ph}}}` appears in path but is not in "
            f"argument-hint `{hint}`"
        )


@pytest.mark.parametrize("cmd", _all_commands(), ids=lambda c: c.name)
def test_no_writes_outside_series(cmd: CommandDef) -> None:
    for w in cmd.writes:
        assert not w.startswith("/"), f"{cmd.name}: absolute write path {w!r}"
        assert ".." not in Path(w).parts, f"{cmd.name}: write path escapes series: {w!r}"


def test_new_series_satisfies_static_reads(tmp_path: Path) -> None:
    """Every non-placeholder, non-glob read path exists after new-series+new-book.

    `.autonovel/` state files (last-action.json, in-progress.lock) are
    explicitly excluded: they are ephemeral, created by `_end` / `_begin`
    during pipeline runs, and the reading commands handle their absence.
    """
    result = scaffold.new_series(tmp_path / "s", series_name="s")
    series = SeriesLayout(root=result.series.root)
    scaffold.new_book(series, book_name="one", pov="Ana")

    missing: list[str] = []
    for cmd in _all_commands():
        for raw in cmd.reads:
            if "{" in raw or "*" in raw:
                continue
            if raw.startswith(".autonovel/"):
                continue  # ephemeral runtime state
            if not (series.root / raw).exists():
                missing.append(f"{cmd.name} -> {raw}")
    assert not missing, f"missing after scaffold: {missing}"


# ---------------------------------------------------------------------------


_PATH_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _path_stem(path: str) -> str:
    """A shortened form of a path that should appear in the body.

    Strips any leading `*/`, placeholder segments, and globs so that the
    check matches how command authors refer to files (e.g. `outline.md`
    rather than the full `books/{book}/outline.md`).
    """
    parts = [p for p in path.split("/") if p]
    if not parts:
        return path
    last = parts[-1]
    # If the final segment is a glob, keep the penultimate directory as a hint.
    if "*" in last and len(parts) >= 2:
        return parts[-2]
    return last


def _collect_placeholders(paths: list[str]) -> set[str]:
    found: set[str] = set()
    for p in paths:
        for m in _PATH_PLACEHOLDER_RE.finditer(p):
            found.add(m.group(1))
    return found


# ---------------------------------------------------------------------------
# Best-effort prior-chapter reads must stay best-effort. The 2026-04-25
# author-testing stall was a draft 3 looping on Read retries for ch_02.
# The fix is wording in the command body — lock it so a future refactor
# of draft.md/revise.md can't silently regress.

def test_draft_marks_prior_chapter_read_as_best_effort():
    from pathlib import Path
    body = (Path(__file__).resolve().parent.parent.parent
            / "commands" / "draft.md").read_text(encoding="utf-8")
    # The exact wording is part of the contract — if you reword it,
    # update this test deliberately, do not just edit the body.
    assert "Best-effort" in body
    assert "do not retry" in body.lower()
    # Per-chapter summaries are explicitly the load-bearing surface.
    assert "load-bearing continuity" in body


def test_revise_marks_prior_chapter_read_as_best_effort():
    from pathlib import Path
    body = (Path(__file__).resolve().parent.parent.parent
            / "commands" / "revise.md").read_text(encoding="utf-8")
    assert "best-effort" in body.lower()
    assert "do not retry" in body.lower()


# ---------------------------------------------------------------------------
# Research --from-seed → promote-canon must be a fully-automatic update
# path. Author preference 2026-04-25: no manual editing of canon when
# research changes a date. The contract is encoded in the bodies of
# research.md (auto-pipe candidates into pending_canon) and
# promote-canon.md (research-tagged entries win contradictions).

def test_research_from_seed_auto_pipes_into_pending_canon():
    from pathlib import Path
    body = (Path(__file__).resolve().parent.parent.parent
            / "commands" / "research.md").read_text(encoding="utf-8")
    assert "[research:" in body, (
        "research.md must spell out the research-tag suffix that "
        "promote-canon keys on for citation-wins-conflicts behaviour"
    )
    assert "pending_canon.md" in body
    assert "Auto-pipe research candidates" in body or "auto-pipe" in body.lower()


def test_promote_canon_prefers_research_tagged_entries():
    from pathlib import Path
    body = (Path(__file__).resolve().parent.parent.parent
            / "commands" / "promote-canon.md").read_text(encoding="utf-8")
    # The exception clause + supersede mechanism must be present.
    assert "[research:" in body
    assert "Superseded" in body
    assert "research-tagged" in body.lower() or "research entry" in body.lower()


# ---------------------------------------------------------------------------
# Mechanical-helper invocation — must use `autonovel mechanical <subcmd>`,
# never `python -m autonovel.mechanical`. The latter only works when
# `autonovel` is importable from the system Python, which is NOT the case
# under pipx install (autonovel is isolated in pipx's own venv). Author
# hit this 2026-04-25: /autonovel:check-anachronism failed mid-run because
# `python -m autonovel.mechanical period-bans …` couldn't find the module.

def test_no_command_uses_python_m_autonovel_mechanical():
    """Every mechanical-helper invocation must go through the
    `autonovel mechanical` subcommand of the main CLI, which IS on
    $PATH after pipx install."""
    from pathlib import Path
    commands_dir = Path(__file__).resolve().parent.parent.parent / "commands"
    offenders: list[tuple[str, int, str]] = []
    for md in sorted(commands_dir.glob("*.md")):
        for i, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            if "python -m autonovel.mechanical" in line:
                offenders.append((md.name, i, line.strip()))
            if "python3 -m autonovel.mechanical" in line:
                offenders.append((md.name, i, line.strip()))
    assert not offenders, (
        f"command files still invoke `python -m autonovel.mechanical`; "
        f"replace with `autonovel mechanical`. Offenders:\n"
        + "\n".join(f"  {n}:{i}: {l}" for n, i, l in offenders)
    )


# ---------------------------------------------------------------------------
# Evaluate output must render scores as a real markdown table, not as
# free-text "dimension: N" lines. Author 2026-04-25: text-only output
# was hard to scan against the prior chapter's eval. Locking the
# wording so a future refactor can't strip it.

def test_evaluate_summary_requires_markdown_table():
    from pathlib import Path
    body = (Path(__file__).resolve().parent.parent.parent
            / "commands" / "evaluate.md").read_text(encoding="utf-8")
    assert "markdown table" in body.lower()
    # The example table shape — rows separated by `|` characters and a
    # `|---|---|` header rule — must be present.
    assert "| Dimension | Score |" in body
    assert "|---|---|---|" in body or "|---|---|" in body


# ---------------------------------------------------------------------------
# evaluate.md gained four reader-interest / writing-quality signals
# 2026-04-25. Lock the wording so future refactors can't strip them
# silently.

def test_evaluate_runs_cliche_scanner():
    from pathlib import Path
    body = (Path(__file__).resolve().parent.parent.parent
            / "commands" / "evaluate.md").read_text(encoding="utf-8")
    assert "autonovel mechanical cliches" in body
    # Must feed the slop_penalty pipeline.
    assert "density_per_1000_words" in body or "cliche" in body.lower()


def test_evaluate_runs_sensory_scanner():
    from pathlib import Path
    body = (Path(__file__).resolve().parent.parent.parent
            / "commands" / "evaluate.md").read_text(encoding="utf-8")
    assert "autonovel mechanical sensory" in body
    assert "dominant_channel" in body


def test_evaluate_full_emits_pacing_curve_table():
    from pathlib import Path
    body = (Path(__file__).resolve().parent.parent.parent
            / "commands" / "evaluate.md").read_text(encoding="utf-8")
    assert "pacing-curve" in body.lower() or "pacing curve" in body.lower()
    # The exact column shape — rows separated by `|` characters.
    assert "| Ch | Words | Score |" in body


def test_evaluate_full_surfaces_tension_drop_alarm():
    from pathlib import Path
    body = (Path(__file__).resolve().parent.parent.parent
            / "commands" / "evaluate.md").read_text(encoding="utf-8")
    assert "Tension-drop" in body or "Tension drop" in body
    assert "three or more consecutive" in body.lower() or "consecutive chapters" in body.lower()


def test_evaluate_chapter_1_scores_first_page_hook():
    from pathlib import Path
    body = (Path(__file__).resolve().parent.parent.parent
            / "commands" / "evaluate.md").read_text(encoding="utf-8")
    assert "hook_strength" in body
    assert "first 250 words" in body.lower()


# ---------------------------------------------------------------------------
# draft-pass must promote canon BETWEEN chapters, not only at sweep end.
# Author 2026-04-25: chapter 11 was inventing facts that chapter 8 had
# already established because canon promotion was deferred to end-of-
# sweep. The fix moves promote-canon into step (e) of the per-chapter
# loop so chapter N+1 sees N's discoveries.

def test_draft_pass_promotes_canon_per_chapter():
    from pathlib import Path
    body = (Path(__file__).resolve().parent.parent.parent
            / "commands" / "draft-pass.md").read_text(encoding="utf-8")
    # The per-chapter promote-canon step must be present in the
    # workflow (step e), not just in the end-of-sweep step (4).
    assert "Promote pending canon for this chapter" in body
    # Rationale must explain why per-chapter timing matters.
    assert "BEFORE chapter N+1" in body or "before chapter N+1" in body.lower()
