"""Tier-1: a chapter's score says which text it was taken on.

Bug class (author, 2026-10-25, on a book called finished after a
whole-book pass cut about 160 repeats from chapters scored before it):
"Are you claiming a draft is done without applying known corrections?
Without scoring the current content to see how good?" The dashboard
showed every chapter's score as the book's, and its Reader column said
"27 left" for a chapter whose evaluator had found one item still open.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autonovel import summaries
from autonovel.mechanical import dashboard
from autonovel.mechanical.chapter_summary import chapter_score_details, latest_chapter_eval_path


def _book(tmp: Path) -> Path:
    book = tmp / "b"
    (book / "chapters").mkdir(parents=True)
    (book / "eval_logs").mkdir()
    (book / "chapters" / "ch_01.md").write_text(
        "---\nchapter: 1\ntitle: The Gate\n---\n\nHe came in at the night gate.\n", encoding="utf-8")
    return book


def _log(book: Path, name: str, **extra) -> Path:
    data = {"overall_score": 7.8,
            "dimensions": {"repetition": {"score": 6.5, "weakest_moment": "x"},
                           "engagement": {"score": 8.0}}}
    data.update(extra)
    path = book / "eval_logs" / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_stamp_eval_marks_the_latest_log_and_tracks_the_text(tmp_path: Path) -> None:
    book = _book(tmp_path)
    _log(book, "20261001_100000_ch01.json")
    newest = _log(book, "20261020_100000_ch01.json")
    chapter = book / "chapters" / "ch_01.md"
    assert latest_chapter_eval_path(book / "eval_logs", 1) == newest

    detail = chapter_score_details(book / "eval_logs")[1]
    assert summaries.score_state(chapter, detail.scored_text) == "unstamped"

    log, fp = summaries.stamp_eval(chapter)
    assert log == newest and json.loads(newest.read_text())["scored_text"] == fp
    detail = chapter_score_details(book / "eval_logs")[1]
    assert summaries.score_state(chapter, detail.scored_text) == "current"

    # A frontmatter edit is not a new text; a prose edit is.
    chapter.write_text(chapter.read_text().replace("title: The Gate", "title: Night"))
    assert summaries.score_state(chapter, detail.scored_text) == "current"
    chapter.write_text(chapter.read_text().replace("night gate", "river gate"))
    assert summaries.score_state(chapter, detail.scored_text) == "older"


def test_stamp_eval_refuses_a_log_named_out_of_order(tmp_path: Path) -> None:
    """A scorer named its log by local time, so it sorted before an
    older log and the stamp landed on the older score (2026-10-25)."""
    import os
    import time
    book = _book(tmp_path)
    older = _log(book, "20261026_005841_ch01.json")
    misnamed = _log(book, "20261025_182130_ch01.json")  # local time: sorts earlier
    now = time.time()
    os.utime(older, (now - 3600, now - 3600))
    os.utime(misnamed, (now, now))
    with pytest.raises(summaries.StampError, match="UTC"):
        summaries.stamp_eval(book / "chapters" / "ch_01.md")
    misnamed.rename(book / "eval_logs" / "20261026_012130_ch01.json")
    log, _fp = summaries.stamp_eval(book / "chapters" / "ch_01.md")
    assert log.name == "20261026_012130_ch01.json"


def test_stamp_eval_needs_a_log(tmp_path: Path) -> None:
    book = _book(tmp_path)
    with pytest.raises(summaries.StampError):
        summaries.stamp_eval(book / "chapters" / "ch_01.md")


def test_dashboard_says_which_text_each_score_describes(tmp_path: Path) -> None:
    book = _book(tmp_path)
    _log(book, "20261020_100000_ch01.json")
    summaries.stamp_eval(book / "chapters" / "ch_01.md")
    md = dashboard.render_markdown(dashboard.build_dashboard(book))
    assert "Scored on" in md and "this text" in md and "Not scores of the text" not in md

    chapter = book / "chapters" / "ch_01.md"
    chapter.write_text(chapter.read_text().replace("night gate", "river gate"))
    report = dashboard.build_dashboard(book)
    assert report.rows[0].scored == "older"
    md = dashboard.render_markdown(report)
    assert "older text ⚠" in md
    assert "Not scores of the text as it stands: ch 1." in md


def test_next_lists_scores_of_an_older_text(tmp_path: Path) -> None:
    from autonovel.housekeeping.next_actions import _score_stale_actions
    book = _book(tmp_path)
    _log(book, "20261020_100000_ch01.json")
    assert _score_stale_actions(book, "b") == []  # not recorded: not claimed stale
    summaries.stamp_eval(book / "chapters" / "ch_01.md")
    assert _score_stale_actions(book, "b") == []
    chapter = book / "chapters" / "ch_01.md"
    chapter.write_text(chapter.read_text().replace("night gate", "river gate"))
    [action] = _score_stale_actions(book, "b")
    assert action.priority == "HIGH" and "older text" in action.title
    assert action.command == "/autonovel:evaluate --chapter 1 --book b"


def test_reader_column_counts_open_items_not_the_last_report(tmp_path: Path) -> None:
    book = _book(tmp_path)
    _log(book, "20261020_100000_ch01.json", first_reader={
        "serious_items_first": ["a"] * 29, "serious_items_second": ["b"] * 27,
        "open_items": ["the opening is still crowded"], "all_fixed": False})
    report = dashboard.build_dashboard(book)
    assert report.rows[0].reader_status == "1 open"
