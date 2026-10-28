"""The step after a book's last outlined chapter (kingmaker2, 2026-10-22).

A 19-chapter book finished drafting and `_end` offered `/autonovel:draft
20`: nothing told the next-step logic how many chapters the outline
declares, and `state.json` still read `phase: seed`, `chapters_total: 0`.
"""

from __future__ import annotations

import json
from pathlib import Path

from autonovel.housekeeping import lifecycle
from autonovel.paths import SeriesLayout, outline_chapter_numbers


def _outline_with(book_root: Path, n: int) -> None:
    blocks = "\n\n".join(f"## Chapter {i} — Title {i}\n\n- story_time: 2020-01-{i:02d}\n- beats: x"
                         for i in range(1, n + 1))
    (book_root / "outline.md").write_text(f"# Outline\n\n{blocks}\n", encoding="utf-8")


def test_outline_chapter_numbers_reads_h2_and_h3(tmp_path: Path) -> None:
    p = tmp_path / "outline.md"
    p.write_text("# O\n\n## Act I\n\n### Chapter 1 — A\n\n## Chapter 2\n\n## Chapter 3 — C\n",
                 encoding="utf-8")
    assert outline_chapter_numbers(p) == [1, 2, 3]
    assert outline_chapter_numbers(tmp_path / "missing.md") == []


def test_last_outlined_chapter_leads_to_developmental_edit(
    review_phase_book: tuple[Path, str],
) -> None:
    series, book = review_phase_book
    book_root = series / "books" / book
    _outline_with(book_root, 10)  # the fixture drafts and scores ch 1-10
    ns = lifecycle._next_step_for(SeriesLayout(root=series), book)
    assert ns.command == f"/autonovel:developmental-edit --book {book}"
    assert "draft 11" not in ns.command

    (book_root / "edit_logs").mkdir(exist_ok=True)
    (book_root / "edit_logs" / "editor_letter.md").write_text("# Editor's letter\n", encoding="utf-8")
    ns = lifecycle._next_step_for(SeriesLayout(root=series), book)
    # The letter is written; the structure review is next (whole_book.py).
    assert ns.command == f"/autonovel:structure-review --book {book}"


def test_mid_book_still_advances(review_phase_book: tuple[Path, str]) -> None:
    series, book = review_phase_book
    _outline_with(series / "books" / book, 12)
    ns = lifecycle._next_step_for(SeriesLayout(root=series), book)
    assert ns.command == f"/autonovel:draft 11 --book {book}"


def test_end_syncs_book_state(review_phase_book: tuple[Path, str]) -> None:
    series, book = review_phase_book
    book_root = series / "books" / book
    _outline_with(book_root, 10)
    state_path = book_root / "state.json"
    assert json.loads(state_path.read_text())["phase"] == "seed"
    lifecycle._sync_book_state(SeriesLayout(root=series), book)
    state = json.loads(state_path.read_text())
    assert state["chapters_drafted"] == 10
    assert state["chapters_total"] == 10
    assert state["phase"] == "revision"

    # Phase never moves backwards.
    state["phase"] = "review"
    state_path.write_text(json.dumps(state))
    lifecycle._sync_book_state(SeriesLayout(root=series), book)
    assert json.loads(state_path.read_text())["phase"] == "review"


def test_a_book_that_passes_the_release_gate_goes_to_its_build() -> None:
    """Bug class (2026-10-28): after the release gate passed, the footer's
    Next sent one book back to the structure review, because a light fix had
    made the review file older than the chapters; the gate, which measures
    the change, said the review still stood."""
    from autonovel.housekeeping.whole_book import WholeBookState, next_whole_book_step
    s = WholeBookState(letter="stale", structure="stale", panel="stale", review="stale",
                       release_ready=True)
    step = next_whole_book_step("b", s)
    assert step.command == "/autonovel:typeset --book b"
    assert "diff --book b --annotate" in step.rationale
    s.release_ready = False
    assert next_whole_book_step("b", s).command == "/autonovel:structure-review --book b"


def test_a_stamped_review_stands_through_a_light_fix(tmp_path: Path, monkeypatch) -> None:
    from autonovel.housekeeping import release_gate, whole_book
    path = tmp_path / "edit_logs" / "reader_panel.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(release_gate, "report_state", lambda root, key: ("light", [3]))
    assert whole_book._stamped_freshness(tmp_path, "reader_panel", path, newest=9e12) == "fresh"
    monkeypatch.setattr(release_gate, "report_state", lambda root, key: ("older", [3]))
    assert whole_book._stamped_freshness(tmp_path, "reader_panel", path, newest=0) == "stale"
    monkeypatch.setattr(release_gate, "report_state", lambda root, key: ("unstamped", []))
    assert whole_book._stamped_freshness(tmp_path, "reader_panel", path, newest=9e12) == "stale"
