"""Tier-1 tests for Phase 10: directory-nesting clarity.

The `<series>/books/<book>/` layout is correct, but when a book's name
equals its series-root directory name the path reads as doubled
(`…/medieval-king-maker/books/medieval-king-maker/`) and looks like a bug.
`paths.looks_doubled`/`nesting_note` describe it, `doctor` warns on it, and
flags a *real* `books/books/` doubling as a PROBLEM.
"""

from __future__ import annotations

from pathlib import Path

from autonovel import paths
from autonovel.housekeeping import doctor, scaffold
from autonovel.paths import SeriesLayout


def test_looks_doubled() -> None:
    assert paths.looks_doubled(Path("/x/medieval-king-maker"), "medieval-king-maker")
    assert not paths.looks_doubled(Path("/x/fugger-saga"), "king-maker")


def test_nesting_note_text() -> None:
    note = paths.nesting_note(Path("/x/saga"), "saga")
    assert "doubled path is correct" in note
    assert paths.nesting_note(Path("/x/saga"), "book-one") == ""


def _new_series(tmp_path: Path, name: str) -> SeriesLayout:
    res = scaffold.new_series(tmp_path / name, series_name=name)
    return res.series


def test_doctor_warns_on_name_collision(tmp_path: Path) -> None:
    series = _new_series(tmp_path, "saga")
    scaffold.new_book(series, book_name="saga")  # same as series → doubled-looking
    report = doctor.run(series.root, export_tools=False)
    assert any("nesting:" in w and "saga" in w for w in report.warnings)
    # a distinct book name produces no nesting warning
    scaffold.new_book(series, book_name="book-two")
    report2 = doctor.run(series.root, export_tools=False)
    assert not any("book-two" in w for w in report2.warnings if "nesting" in w)


def test_doctor_flags_real_books_books_doubling(tmp_path: Path) -> None:
    series = _new_series(tmp_path, "saga")
    scaffold.new_book(series, book_name="book-one")
    (series.books / "books").mkdir()  # the actual bug
    report = doctor.run(series.root, export_tools=False)
    assert any("books/books/" in p for p in report.problems)
    assert not report.ok


def test_no_collision_clean(tmp_path: Path) -> None:
    series = _new_series(tmp_path, "fugger-saga")
    scaffold.new_book(series, book_name="king-maker")
    report = doctor.run(series.root, export_tools=False)
    assert not any("nesting" in w for w in report.warnings)
    assert not any("books/books" in p for p in report.problems)
