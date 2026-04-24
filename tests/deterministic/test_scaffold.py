"""New-series and new-book scaffolding (PR 1 acceptance)."""

from __future__ import annotations

from pathlib import Path

import pytest

from autonovel import project as project_mod
from autonovel.housekeeping import scaffold
from autonovel.paths import SeriesLayout


EXPECTED_SHARED_FILES = [
    "shared/world.md",
    "shared/characters.md",
    "shared/canon.md",
    "shared/events.md",
    "shared/timeline.md",
    "shared/MYSTERY.md",
    "shared/period_bans.txt",
    "shared/sources.bib",
    "shared/research/sources.yaml",
]

EXPECTED_SERIES_DIRS = [
    "shared",
    "shared/research",
    "shared/research/seed",
    "shared/research/notes",
    "books",
    ".autonovel",
    ".autonovel/checkpoints",
    ".autonovel/session-notes",
]


def test_new_series_creates_expected_tree(tmp_path: Path) -> None:
    result = scaffold.new_series(tmp_path / "renaissance-europe", series_name="renaissance-europe", genre="historical-fiction")
    root = result.series.root

    assert (root / "project.yaml").is_file()
    for d in EXPECTED_SERIES_DIRS:
        assert (root / d).is_dir(), f"missing {d}"
    for f in EXPECTED_SHARED_FILES:
        assert (root / f).is_file(), f"missing {f}"

    assert (root / ".gitignore").is_file()
    assert (root / ".autonovel/state.json").is_file()

    cfg = project_mod.load(root / "project.yaml")
    assert cfg.series_name == "renaissance-europe"
    assert cfg.genre == "historical-fiction"
    assert cfg.books == []
    assert project_mod.validate(cfg) == []


def test_new_series_rejects_bad_name(tmp_path: Path) -> None:
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.new_series(tmp_path / "Bad Name", series_name="Bad Name")


def test_new_series_rejects_non_empty_target(tmp_path: Path) -> None:
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "junk").write_text("x", encoding="utf-8")
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.new_series(tmp_path / "demo", series_name="demo")


def test_new_book_creates_book_tree(series_root: Path) -> None:
    series = SeriesLayout(root=series_root)
    result = scaffold.new_book(series, book_name="one", pov="Ana", story_time_range=[2020, 2021])

    book = result.book_root
    assert book.is_dir()
    for rel in ("seed.txt", "voice.md", "outline.md", "pending_canon.md", "state.json", "results.tsv"):
        assert (book / rel).is_file(), f"missing books/one/{rel}"
    for rel in ("chapters", "briefs", "edit_logs", "eval_logs", "typeset"):
        assert (book / rel).is_dir(), f"missing books/one/{rel}/"

    cfg = project_mod.load(series.project_file)
    assert [b.name for b in cfg.books] == ["one"]
    assert cfg.books[0].pov == "Ana"
    assert cfg.books[0].story_time_range == [2020, 2021]


def test_new_book_rejects_duplicate(series_root: Path) -> None:
    series = SeriesLayout(root=series_root)
    scaffold.new_book(series, book_name="one")
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.new_book(series, book_name="one")


def test_project_yaml_validates_schema(tmp_path: Path) -> None:
    bad = tmp_path / "project.yaml"
    bad.write_text("series_name: ''\nbooks:\n  - name: one\n  - name: one\n", encoding="utf-8")
    cfg = project_mod.load(bad)
    problems = project_mod.validate(cfg)
    assert any("series_name" in p for p in problems)
    assert any("one" in p for p in problems)


def test_two_books_coexist(series_root: Path) -> None:
    series = SeriesLayout(root=series_root)
    scaffold.new_book(series, book_name="one")
    scaffold.new_book(series, book_name="two", pov="B")
    cfg = project_mod.load(series.project_file)
    names = sorted(b.name for b in cfg.books)
    assert names == ["one", "two"]
