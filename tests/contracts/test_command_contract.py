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
