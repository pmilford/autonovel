"""Tier-1 tests for `autonovel.mechanical.summary_query` — the
small filter DSL over chapter-summary rows."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel.mechanical.chapter_summary import ChapterRow
from autonovel.mechanical.summary_query import (
    QueryError,
    filter_rows,
    render_markdown,
)


def _row(**kw) -> ChapterRow:
    """Helper to construct a ChapterRow with sensible defaults."""
    defaults = dict(
        chapter=1, story_time=None, pov=None, score=None,
        word_count=None, plot=None, cast=None, location=None,
        status=None,
    )
    defaults.update(kw)
    return ChapterRow(**defaults)


# ---------------------------------------------------------- empty + sanity


def test_empty_expr_returns_all_rows() -> None:
    rows = [_row(chapter=1), _row(chapter=2), _row(chapter=3)]
    assert filter_rows(rows, "") == rows
    assert filter_rows(rows, "   ") == rows


def test_empty_rows_returns_empty() -> None:
    assert filter_rows([], "score > 5") == []


# ---------------------------------------------------------- comparisons


def test_eq_string() -> None:
    rows = [_row(chapter=1, pov="Lucia"), _row(chapter=2, pov="Tommaso")]
    out = filter_rows(rows, 'pov == "Lucia"')
    assert [r.chapter for r in out] == [1]


def test_neq_string() -> None:
    rows = [_row(chapter=1, pov="Lucia"), _row(chapter=2, pov="Tommaso")]
    out = filter_rows(rows, 'pov != "Lucia"')
    assert [r.chapter for r in out] == [2]


def test_numeric_lt() -> None:
    rows = [_row(chapter=1, score=6.5), _row(chapter=2, score=7.5)]
    assert [r.chapter for r in filter_rows(rows, "score < 7.0")] == [1]


def test_numeric_gte() -> None:
    rows = [_row(chapter=1, score=6.5), _row(chapter=2, score=7.5)]
    assert [r.chapter for r in filter_rows(rows, "score >= 7.0")] == [2]


def test_iso_date_range_via_lex_cmp() -> None:
    rows = [
        _row(chapter=1, story_time="1521-10-15"),
        _row(chapter=2, story_time="1521-11-04"),
        _row(chapter=3, story_time="1522-03-01"),
    ]
    out = filter_rows(rows,
                      'story_time >= "1521-11" and story_time <= "1522-02"')
    assert [r.chapter for r in out] == [2]


def test_word_count_range_via_in() -> None:
    rows = [
        _row(chapter=1, word_count=2000),
        _row(chapter=2, word_count=3200),
        _row(chapter=3, word_count=5000),
    ]
    out = filter_rows(rows, "word_count in 2500..4000")
    assert [r.chapter for r in out] == [2]


def test_chapter_range_in() -> None:
    rows = [_row(chapter=n) for n in (1, 5, 8, 12)]
    out = filter_rows(rows, "chapter in 5..10")
    assert [r.chapter for r in out] == [5, 8]


# ---------------------------------------------------------- contains


def test_cast_contains_finds_member() -> None:
    rows = [
        _row(chapter=1, cast=["Tommaso", "Lucia"]),
        _row(chapter=2, cast=["Tommaso"]),
        _row(chapter=3, cast=["Niccolò"]),
    ]
    out = filter_rows(rows, "cast contains Niccolò")
    assert [r.chapter for r in out] == [3]


def test_cast_contains_case_insensitive() -> None:
    rows = [_row(chapter=1, cast=["Tommaso", "Lucia"])]
    assert filter_rows(rows, "cast contains lucia") == rows


def test_cast_contains_missing_field_returns_empty() -> None:
    rows = [_row(chapter=1, cast=None)]
    assert filter_rows(rows, "cast contains Tommaso") == []


def test_plot_contains_substring() -> None:
    rows = [
        _row(chapter=1, plot="Tommaso opens the book of accounts."),
        _row(chapter=2, plot="Lucia walks home."),
    ]
    out = filter_rows(rows, 'plot contains "book of accounts"')
    assert [r.chapter for r in out] == [1]


def test_location_contains() -> None:
    rows = [
        _row(chapter=1, location="Venice / Rialto"),
        _row(chapter=2, location="Padua"),
    ]
    out = filter_rows(rows, "location contains Padua")
    assert [r.chapter for r in out] == [2]


# ---------------------------------------------------------- boolean


def test_and_combines() -> None:
    rows = [
        _row(chapter=1, pov="Lucia", score=6.0),
        _row(chapter=2, pov="Lucia", score=7.5),
        _row(chapter=3, pov="Tommaso", score=6.0),
    ]
    out = filter_rows(rows, 'pov == "Lucia" and score < 7.0')
    assert [r.chapter for r in out] == [1]


def test_or_combines() -> None:
    rows = [
        _row(chapter=1, location="Venice"),
        _row(chapter=2, location="Padua"),
        _row(chapter=3, location="Augsburg"),
    ]
    out = filter_rows(rows, 'location contains Padua or location contains Venice')
    assert [r.chapter for r in out] == [1, 2]


def test_not_negates() -> None:
    rows = [_row(chapter=1, pov="Lucia"), _row(chapter=2, pov="Tommaso")]
    out = filter_rows(rows, 'not pov == "Lucia"')
    assert [r.chapter for r in out] == [2]


def test_parens_override_precedence() -> None:
    rows = [
        _row(chapter=1, pov="Lucia", score=8.0),
        _row(chapter=2, pov="Tommaso", score=6.0),
        _row(chapter=3, pov="Tommaso", score=8.0),
    ]
    # Without parens, `and` binds tighter than `or` — so this picks
    # ch1 OR (Tommaso AND <7) = ch1 + ch2 = [1, 2].
    out = filter_rows(rows,
                      'pov == "Lucia" or pov == "Tommaso" and score < 7.0')
    assert [r.chapter for r in out] == [1, 2]
    # Parens flip precedence: (Lucia OR Tommaso) AND <7 = [2].
    out = filter_rows(rows,
                      '(pov == "Lucia" or pov == "Tommaso") and score < 7.0')
    assert [r.chapter for r in out] == [2]


def test_double_pipe_and_double_amp_synonyms() -> None:
    rows = [
        _row(chapter=1, pov="Lucia", score=6.0),
        _row(chapter=2, pov="Tommaso", score=8.0),
    ]
    out = filter_rows(rows, 'pov == "Lucia" || score >= 8.0')
    assert [r.chapter for r in out] == [1, 2]
    out = filter_rows(rows, 'pov == "Lucia" && score < 7.0')
    assert [r.chapter for r in out] == [1]


# ---------------------------------------------------------- null handling


def test_null_score_is_excluded_from_numeric_filter() -> None:
    rows = [
        _row(chapter=1, score=7.5),
        _row(chapter=2, score=None),
    ]
    out = filter_rows(rows, "score >= 7.0")
    assert [r.chapter for r in out] == [1]


def test_null_passes_neq_to_anything() -> None:
    rows = [_row(chapter=1, score=None)]
    out = filter_rows(rows, "score != 7.0")
    assert [r.chapter for r in out] == [1]


# ---------------------------------------------------------- errors


def test_unknown_field_raises() -> None:
    with pytest.raises(QueryError) as exc:
        filter_rows([_row()], "wibble == 1")
    assert "wibble" in str(exc.value)


def test_missing_operator_raises() -> None:
    with pytest.raises(QueryError):
        filter_rows([_row()], "pov")


def test_unbalanced_paren_raises() -> None:
    with pytest.raises(QueryError):
        filter_rows([_row()], '(pov == "Lucia"')


def test_lone_operator_raises() -> None:
    with pytest.raises(QueryError):
        filter_rows([_row()], "==")


# ---------------------------------------------------------- render


def test_render_markdown_empty_emits_no_match() -> None:
    out = render_markdown([], expr='pov == "Nobody"', book="b")
    assert "No matching chapters" in out
    assert "filter" in out


def test_render_markdown_table_columns() -> None:
    rows = [
        _row(chapter=1, story_time="1521-11-04", pov="Tommaso",
              score=7.5, word_count=3000, location="Venice",
              plot="A scene happens."),
    ]
    out = render_markdown(rows, expr=None, book="b")
    assert "| Ch |" in out
    assert "| 1 |" in out
    assert "Tommaso" in out
    assert "1 chapter(s) matched" in out


def test_render_markdown_escapes_pipe_in_location_and_plot() -> None:
    rows = [_row(chapter=1, location="Venice | Rialto",
                  plot="A | piped | plot.")]
    out = render_markdown(rows)
    # Pipes inside cells must be backslash-escaped so they don't
    # split the table column count.
    assert "\\|" in out


# ---------------------------------------------------------- CLI


def _seed(book_root: Path) -> None:
    """Seed a small book with two chapters so summarize_chapters
    has something to filter."""
    chapters = book_root / "chapters"
    chapters.mkdir(parents=True, exist_ok=True)
    for n, pov, score in [(1, "Lucia", 6.0), (2, "Tommaso", 7.5)]:
        (chapters / f"ch_{n:02d}.md").write_text(
            f"---\nchapter: {n}\npov: {pov}\nstory_time: 2020-01-{n:02d}\n"
            f"events: []\nstatus: drafted\nword_count: 3000\n---\n\nProse.",
            encoding="utf-8",
        )
        (chapters / f"ch_{n:02d}.summary.md").write_text(
            f"**Plot:** ch{n}.\n**Cast on stage:** {pov}\n"
            f"**Story time:** 2020-01-{n:02d}.\n",
            encoding="utf-8",
        )
    eval_dir = book_root / "eval_logs"
    eval_dir.mkdir(parents=True, exist_ok=True)
    for n, score in [(1, 6.0), (2, 7.5)]:
        (eval_dir / f"ch{n:02d}_eval.json").write_text(
            json.dumps({"overall_score": score}), encoding="utf-8"
        )


def test_cli_summary_query_markdown(tmp_path: Path) -> None:
    book = tmp_path / "demo"
    _seed(book)
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "summary-query",
         str(book), "--where", 'pov == "Lucia"'],
        capture_output=True, text=True, check=True,
    )
    assert "Summary query" in proc.stdout
    assert "1 chapter(s) matched" in proc.stdout


def test_cli_summary_query_json(tmp_path: Path) -> None:
    book = tmp_path / "demo"
    _seed(book)
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "summary-query",
         str(book), "--where", "score < 7.0", "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["matched"] == 1
    assert payload["rows"][0]["chapter"] == 1


def test_cli_summary_query_no_filter_returns_all(tmp_path: Path) -> None:
    book = tmp_path / "demo"
    _seed(book)
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "summary-query",
         str(book), "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["matched"] == 2


def test_cli_summary_query_invalid_expr_exits_non_zero(tmp_path: Path) -> None:
    book = tmp_path / "demo"
    _seed(book)
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "summary-query",
         str(book), "--where", "wibble == 1"],
        capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert "wibble" in proc.stderr.lower()
