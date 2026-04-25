"""Scaffold helpers for `autonovel new-series` and `autonovel new-book`."""

from __future__ import annotations

import importlib.resources as resources
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .. import project as project_mod
from ..paths import SeriesLayout
from ..project import BookEntry, ProjectConfig


_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")


class ScaffoldError(ValueError):
    pass


@dataclass
class NewSeriesResult:
    series: SeriesLayout
    created: list[Path]


@dataclass
class NewBookResult:
    book_root: Path
    created: list[Path]


def _validate_name(name: str, kind: str) -> None:
    if not _NAME_RE.match(name):
        raise ScaffoldError(
            f"{kind} name must match [a-z][a-z0-9-]*; got {name!r}"
        )


def _template_root(which: str) -> Path:
    """Return the on-disk path of a packaged template tree."""
    ref = resources.files("autonovel").joinpath("templates", which)
    # importlib.resources.files returns a Traversable. For our simple case of
    # a directory tree shipped inside the wheel, `.as_posix()` works after we
    # resolve it via as_file.
    with resources.as_file(ref) as p:
        return Path(p)


def _copy_tree(src: Path, dst: Path, created: list[Path]) -> None:
    """Copy a template tree verbatim. Callers overwrite files that need substitution."""
    for item in sorted(src.rglob("*")):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if item.name == ".gitkeep":
            if not target.exists():
                target.write_text("", encoding="utf-8")
                created.append(target)
            continue
        target.write_bytes(item.read_bytes())
        created.append(target)


def new_series(root: Path, *, series_name: str, genre: str = "general") -> NewSeriesResult:
    _validate_name(series_name, "series")
    if root.exists() and any(root.iterdir()):
        raise ScaffoldError(f"{root} already exists and is not empty")
    root.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    tmpl = _template_root("series")
    _copy_tree(tmpl, root, created)

    cfg = ProjectConfig.default(series_name=series_name, genre=genre)
    project_mod.dump(cfg, root / "project.yaml")

    series = SeriesLayout(root=root)
    series.autonovel.mkdir(parents=True, exist_ok=True)
    series.checkpoints.mkdir(parents=True, exist_ok=True)
    series.session_notes.mkdir(parents=True, exist_ok=True)
    series.books.mkdir(parents=True, exist_ok=True)
    created.extend([series.autonovel, series.checkpoints, series.session_notes, series.books])

    _write_autonovel_state(series)
    created.append(series.state_file)

    _link_agent_aliases(root, created)
    return NewSeriesResult(series=series, created=created)


def _link_agent_aliases(root: Path, created: list[Path]) -> None:
    """Create AGENTS.md and GEMINI.md aliases pointing at CLAUDE.md.

    Codex CLI auto-loads AGENTS.md; Gemini CLI auto-loads GEMINI.md;
    Claude Code auto-loads CLAUDE.md. We ship CLAUDE.md in the
    template and create the other two as symlinks at scaffold time
    (mirrors the top-level repo's pattern). On platforms where
    symlinks aren't supported (rare; mostly old Windows non-WSL),
    fall back to copying so all three files exist.
    """
    primary = root / "CLAUDE.md"
    if not primary.is_file():
        return
    for alias_name in ("AGENTS.md", "GEMINI.md"):
        alias = root / alias_name
        if alias.exists() or alias.is_symlink():
            continue
        try:
            alias.symlink_to("CLAUDE.md")
        except (OSError, NotImplementedError):
            alias.write_bytes(primary.read_bytes())
        created.append(alias)


def new_book(series: SeriesLayout, *, book_name: str, pov: str | None = None,
             story_time_range: list[int] | None = None) -> NewBookResult:
    _validate_name(book_name, "book")
    cfg = project_mod.load(series.project_file)
    if cfg.book_by_name(book_name) is not None:
        raise ScaffoldError(f"book {book_name!r} already exists in project.yaml")

    book_root = series.books / book_name
    if book_root.exists() and any(book_root.iterdir()):
        raise ScaffoldError(f"{book_root} already exists and is not empty")
    book_root.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    tmpl = _template_root("book")
    _copy_tree(tmpl, book_root, created)
    _write_book_state(book_root / "state.json", book_name)

    cfg.books.append(BookEntry(
        name=book_name,
        pov=pov,
        story_time_range=story_time_range,
        status="seed",
    ))
    project_mod.dump(cfg, series.project_file)

    return NewBookResult(book_root=book_root, created=created)


def _write_autonovel_state(series: SeriesLayout) -> None:
    import json
    series.state_file.write_text(
        json.dumps({"version": 1, "phase": "seed", "books": {}}, indent=2),
        encoding="utf-8",
    )


def _write_book_state(path: Path, book_name: str) -> None:
    import json
    path.write_text(
        json.dumps(
            {
                "book": book_name,
                "phase": "seed",
                "iteration": 0,
                "foundation_score": 0.0,
                "lore_score": 0.0,
                "chapters_drafted": 0,
                "chapters_total": 0,
                "novel_score": 0.0,
                "debts": [],
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
