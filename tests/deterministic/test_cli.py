"""End-to-end acceptance: `autonovel new-series demo && autonovel new-book one --series demo`."""

from __future__ import annotations

import os
from pathlib import Path

from autonovel import cli


def _run(argv: list[str]) -> int:
    return cli.main(argv)


def test_acceptance_tree(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    rc = _run(["new-series", "demo"])
    assert rc == 0
    assert (tmp_path / "demo" / "project.yaml").is_file()

    monkeypatch.chdir(tmp_path / "demo")
    rc = _run(["new-book", "one"])
    assert rc == 0
    assert (tmp_path / "demo" / "books" / "one" / "seed.txt").is_file()

    rc = _run(["status"])
    assert rc == 0

    rc = _run(["doctor"])
    assert rc == 0

    rc = _run(["version"])
    assert rc == 0


def test_new_book_outside_series_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = _run(["new-book", "one"])
    assert rc != 0


def test_rollback_list_on_empty_is_clean(series_root: Path, monkeypatch) -> None:
    monkeypatch.chdir(series_root)
    rc = _run(["rollback", "--list"])
    assert rc == 0
