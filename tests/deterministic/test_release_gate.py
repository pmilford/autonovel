"""Tier-1: no version goes to the author before the whole-book reviews have
read it and their fixes are made (`housekeeping.release_gate`).

Bug class (author, 2026-10-25, after four versions of one book went out
with the reader panel and the dual review never run, a developmental edit
two versions old and every chapter scored before the last pass): "You are
wasting my time asking me to read content that has not been reviewed and
corrected by our tools." The footer printed the next review as a
suggestion; typeset built the book for the author regardless.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel import summaries
from autonovel.housekeeping import next_actions, release_gate
from autonovel.housekeeping.scaffold import new_book
from autonovel.mechanical.typeset import render_novel_tex
from autonovel.paths import SeriesLayout

SUMMARY = "**Plot:** " + "Ana crosses the river and pays the toll. " * 5 + "\n"


def _para(n: int, i: int) -> str:
    return f"Paragraph {i} of chapter {n}: Ana counts the tolls at the river gate."


@pytest.fixture
def book(series_root: Path) -> Path:
    series = SeriesLayout(root=series_root)
    new_book(series, book_name="one", pov="Ana")
    root = series.books / "one"
    (root / "chapters").mkdir(parents=True, exist_ok=True)
    (root / "eval_logs").mkdir(exist_ok=True)
    (root / "edit_logs").mkdir(exist_ok=True)
    for n in (1, 2, 3):
        body = "\n\n".join(_para(n, i) for i in range(10))
        path = root / "chapters" / f"ch_{n:02d}.md"
        path.write_text(f"---\nchapter: {n}\n---\n\n{body}\n", encoding="utf-8")
        (root / "chapters" / f"ch_{n:02d}.summary.md").write_text(SUMMARY, encoding="utf-8")
        summaries.stamp(path)
    return root


def _score(book: Path, n: int, low: float = 7.5, open_items: list[str] | None = None) -> None:
    data = {"overall_score": 7.8, "weakest_dimension": "repetition", "weakest_score": low,
            "dimensions": {"repetition": {"score": low}, "engagement": {"score": 8.0}}}
    if open_items is not None:
        data["first_reader"] = {"open_items": open_items, "all_fixed": not open_items}
    (book / "eval_logs" / f"20261025_120000_ch{n:02d}.json").write_text(json.dumps(data))
    summaries.stamp_eval(book / "chapters" / f"ch_{n:02d}.md")


def _first_read(book: Path, n: int, when: str = "2026-10-25T11:00:00+00:00") -> None:
    """A cold reader's report on chapter n, stamped as read before the score
    `_score` writes (12:00)."""
    (book / "edit_logs" / f"first_read_ch{n:02d}.md").write_text("# first read\n")
    release_gate.stamp_first_read(book, n)
    path = book / "edit_logs" / release_gate.STAMPS_FILE
    stamps = json.loads(path.read_text())
    stamps["first_read"][str(n)]["when"] = when
    path.write_text(json.dumps(stamps))


def _write_reports(book: Path) -> None:
    for key, (_what, rel, _cmd) in release_gate.REPORTS.items():
        if key == "full_eval":
            (book / "eval_logs" / "20261025_130000_full.json").write_text("{}")
        else:
            (book / rel).write_text("{}" if rel.endswith(".json") else "# report\n")


def _pass_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    from autonovel.mechanical import structure_review

    class _Rep:
        gate = {"passes": True, "reasons": []}

    monkeypatch.setattr(structure_review, "check", lambda *a, **k: _Rep())


def _by_key(rep: release_gate.GateReport) -> dict[str, release_gate.Check]:
    return {c.key: c for c in rep.checks}


def test_a_book_never_reviewed_is_not_ready(book: Path) -> None:
    rep = release_gate.check(book)
    assert not rep.passes
    checks = _by_key(rep)
    assert checks["summaries"].ok
    assert not checks["chapter_scores"].ok and "1-3" in checks["chapter_scores"].detail
    for key in release_gate.REPORTS:
        assert not checks[key].ok and checks[key].detail == "never run on this book"
    assert "Not ready" in release_gate.render_markdown(rep)
    assert "/autonovel:review-cycle --book one" in release_gate.render_markdown(rep)


def test_a_report_without_a_stamp_counts_as_unread(book: Path) -> None:
    _write_reports(book)
    checks = _by_key(release_gate.check(book))
    assert checks["said_once"].detail == "doesn't record which text it read"


def test_everything_current_passes(book: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _pass_structure(monkeypatch)
    for n in (1, 2, 3):
        _first_read(book, n)
        _score(book, n, open_items=[])
    _write_reports(book)
    for key in release_gate.REPORTS:
        release_gate.stamp_report(book, key)
    rep = release_gate.check(book)
    assert rep.passes, release_gate.render_markdown(rep)
    assert "**Ready.**" in release_gate.render_markdown(rep)


def test_floor_cold_readers_and_queued_fixes_hold_the_gate(book: Path) -> None:
    for n in (1, 2, 3):
        _first_read(book, n)
    _score(book, 1, low=5.0)
    _score(book, 2, open_items=["Lost: who is the toll-keeper?"])
    _score(book, 3)
    (book / "briefs").mkdir(exist_ok=True)
    (book / "briefs" / "conversation.md").write_text(
        "## 2026-10-25 — turn 1 — suggest\n\n**Target:** chapter 3\n\n**Status:** queued\n\n"
        "## 2026-10-25 — turn 2 — suggest\n\n**Target:** chapter 1\n\n**Status:** applied\n",
        encoding="utf-8")
    checks = _by_key(release_gate.check(book, floor=7.0))
    assert not checks["floor"].ok and "ch 1 repetition 5.0" in checks["floor"].detail
    assert not checks["cold_readers"].ok and checks["cold_readers"].detail == "open in ch 2"
    assert not checks["fixes_acted_on"].ok and "ch 3" in checks["fixes_acted_on"].detail


def test_a_cold_reader_must_have_read_the_text_as_it_stands(book: Path) -> None:
    """Every report on one book predated two versions and two review
    rounds; the gate counted their items as if a reader had seen this text
    (2026-10-25)."""
    for n in (1, 2, 3):
        _score(book, n, open_items=[])
    check = _by_key(release_gate.check(book))["cold_readers"]
    assert not check.ok and "no cold reader has read the text as it stands: ch 1-3" in check.detail
    assert check.command.startswith("/autonovel:first-read 1 --book one")

    for n in (1, 2, 3):
        _first_read(book, n)
    assert _by_key(release_gate.check(book))["cold_readers"].ok
    assert release_gate.first_read_state(book, 1) == "current"

    # A light fix (one paragraph in ten) leaves the read standing; a rewrite doesn't.
    ch1 = book / "chapters" / "ch_01.md"
    ch1.write_text(ch1.read_text().replace("Paragraph 3 of chapter 1", "Paragraph three of chapter 1"))
    assert release_gate.first_read_state(book, 1) == "light"
    ch2 = book / "chapters" / "ch_02.md"
    ch2.write_text(ch2.read_text().replace("Ana counts", "Ana weighs"))
    assert release_gate.first_read_state(book, 2) == "older"


def test_earlier_cold_reads_are_archived_before_a_new_one(book: Path) -> None:
    """An old second reader's report left in place is read by evaluate as
    the latest report on the new text."""
    (book / "edit_logs" / "first_read_ch01.md").write_text("# old first\n")
    (book / "edit_logs" / "first_read_ch01_2.md").write_text("# old second\n")
    (book / "edit_logs" / "first_read_ch10.md").write_text("# chapter 10\n")
    series_root = book.parent.parent
    r = _run(series_root, "_archive-first-read", "--book", "one", "--chapter", "1")
    assert r.returncode == 0, r.stderr
    assert release_gate.first_read_reports(book, 1) == []
    assert (book / "edit_logs" / "first_read_ch10.md").exists()
    archived = sorted(p.name for p in (book / "edit_logs" / "first_read_archive").iterdir())
    assert len(archived) == 2 and archived[0].startswith("first_read_ch01_")
    assert release_gate.first_read_state(book, 1) == "missing"


def test_a_chapter_scored_before_its_cold_read_is_not_checked(book: Path) -> None:
    for n in (1, 2, 3):
        _first_read(book, n)
        _score(book, n, open_items=[])
    _first_read(book, 3, when="2026-10-25T13:00:00+00:00")   # after the 12:00 score
    check = _by_key(release_gate.check(book))["cold_readers"]
    assert not check.ok and "scored before its cold read" in check.detail and "ch 3" in check.detail
    assert check.command.startswith("/autonovel:evaluate --chapter 3 --book one")


def test_a_whole_book_dimension_under_the_floor_holds_the_gate(book: Path) -> None:
    (book / "eval_logs" / "20261026_031244_full.json").write_text(json.dumps({
        "dimensions": {"overall_engagement": {"score": 6.5}, "causal_chain": {"score": 9.0},
                       "pace_distribution": {"score": 6.5}}}))
    check = _by_key(release_gate.check(book, floor=7.0))["book_floor"]
    assert not check.ok and "overall_engagement 6.5" in check.detail
    assert "causal_chain" not in check.detail
    # A light fix lets the score stand but doesn't lift it: the gate says
    # to take it again.
    assert "evaluate --full" in check.detail


def test_a_light_fix_pass_keeps_a_report_and_a_rewrite_does_not(book: Path) -> None:
    _write_reports(book)
    release_gate.stamp_report(book, "said_once")
    assert release_gate.report_state(book, "said_once") == ("current", [])

    # One sentence changed in one chapter: the ledger still stands.
    ch2 = book / "chapters" / "ch_02.md"
    ch2.write_text(ch2.read_text().replace(_para(2, 4), _para(2, 4) + " She doesn't look up."))
    state, changed = release_gate.report_state(book, "said_once")
    assert (state, changed) == ("light", [2])
    check = _by_key(release_gate.check(book))["said_once"]
    assert check.ok and "light fixes since in ch 2" in check.detail

    # Half a chapter rewritten: it must be read again.
    text = ch2.read_text()
    for i in range(5):
        text = text.replace(_para(2, i), f"New paragraph {i}: the gate is shut.")
    ch2.write_text(text)
    state, changed = release_gate.report_state(book, "said_once")
    assert state == "older" and changed == [2]
    assert not _by_key(release_gate.check(book))["said_once"].ok


def test_a_chapter_added_since_the_report_sends_it_back(book: Path) -> None:
    _write_reports(book)
    release_gate.stamp_report(book, "review")
    (book / "chapters" / "ch_04.md").write_text("---\nchapter: 4\n---\n\nNew.\n")
    assert release_gate.report_state(book, "review") == ("older", [4])


def test_stamp_report_refuses_an_unknown_report(book: Path) -> None:
    with pytest.raises(KeyError):
        release_gate.stamp_report(book, "panel")


def test_next_puts_the_gate_first_for_a_drafted_book(book: Path) -> None:
    series = SeriesLayout(root=book.parent.parent)
    actions = next_actions.enumerate_actions(series, book="one")
    gate = [a for a in actions if a.title.startswith("Not ready for the author")]
    assert gate and gate[0].priority == "HIGH"
    assert gate[0].command == "/autonovel:review-cycle --book one"


def test_draft_notice_renders_empty_unless_filled() -> None:
    template = "Typeset by autonovel.\n@DRAFT_NOTICE@\n"
    assert "@DRAFT_NOTICE@" not in render_novel_tex(template, {})
    assert "Draft: not yet" in render_novel_tex(
        template, {"DRAFT_NOTICE": "Draft: not yet through the whole-book review"})


# ------------------------------------------------------------ CLI


def _run(series_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "autonovel.cli", *args], cwd=series_root,
                          capture_output=True, text=True, env={**os.environ})


def test_cli_stamp_report_and_release_check(book: Path) -> None:
    series_root = book.parent.parent
    r = _run(series_root, "mechanical", "release-check", "books/one", "--format", "json")
    assert r.returncode == 1, r.stderr
    data = json.loads(r.stdout)
    assert data["passes"] is False and data["open"] >= 7

    (book / "edit_logs" / "said_once_ledger.md").write_text("# ledger\n")
    r = _run(series_root, "_stamp-report", "--book", "one", "--report", "said_once")
    assert r.returncode == 0, r.stderr
    stamps = json.loads((book / "edit_logs" / "report_stamps.json").read_text())
    assert set(stamps["said_once"]["chapters"]) == {"1", "2", "3"}
    r = _run(series_root, "mechanical", "release-check", "books/one")
    assert "✓ the whole-book repetition ledger read this text" in r.stdout

    (book / "edit_logs" / "first_read_ch02.md").write_text("# first read\n")
    r = _run(series_root, "_stamp-report", "--book", "one", "--report", "first_read", "--chapter", "2")
    assert r.returncode == 0, r.stderr
    assert release_gate.first_read_state(book, 2) == "current"
    r = _run(series_root, "_stamp-report", "--book", "one", "--report", "first_read")
    assert r.returncode == 1 and "--chapter" in r.stderr


def test_turn_status_marks_numbered_turns_and_the_gate_follows(book: Path) -> None:
    (book / "briefs").mkdir(exist_ok=True)
    conv = book / "briefs" / "conversation.md"
    conv.write_text(
        "## 2026-10-25 — turn 7 — suggest\n**Target:** chapter 1\n\n**Status:** queued\n\n"
        "## 2026-10-25 — turn 8 — suggest\n**Target:** chapter 2\n\n**Status:** queued\n\n"
        "## 2026-10-25 — turn 9 — suggest\n**Target:** chapter 3\n\n**Status:** applied\n",
        encoding="utf-8")
    assert release_gate._queued_turns(book) == [1, 2]
    prev = release_gate.set_turn_status(book, [7, 8], "applied")
    assert prev == {7: "queued", 8: "queued"}
    assert release_gate._queued_turns(book) == []
    release_gate.set_turn_status(book, [9], "declined")
    text = conv.read_text()
    assert text.count("**Status:** applied") == 2 and "**Status:** declined" in text
    with pytest.raises(KeyError):
        release_gate.set_turn_status(book, [10], "applied")
    r = _run(book.parent.parent, "_turn-status", "--book", "one", "--turns", "7", "--status", "queued")
    assert r.returncode == 0 and "turn 7: applied -> queued" in r.stdout


def test_cli_command_path_points_at_the_command_source(series_root: Path) -> None:
    r = _run(series_root, "_command-path", "evaluate")
    assert r.returncode == 0, r.stderr
    path = Path(r.stdout.strip())
    assert path.name == "evaluate.md" and path.is_file()
