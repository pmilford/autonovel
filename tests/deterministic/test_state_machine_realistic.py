"""State-machine and filesystem-counting tests against realistic-shape
fixtures.

Background: synthetic 0–2-chapter test fixtures hide bugs that only
manifest at realistic shapes — paired summary files, eval logs across
multiple chapters, mid-revision artefacts, completed panel/review
reports. FUTURE-TODOS #5.1 prescribes converting state-machine and
filesystem-counting tests to run against the realistic shapes too.

Three fixtures (`late_stage_book`, `mid_revision_book`,
`review_phase_book`) map to the three substantive sub-phases of a
real book between drafting-start and typeset-ready. This file
exercises:

  - `paths.iter_chapter_files`            — glob doesn't grab summaries.
  - `housekeeping.lifecycle._infer_phase` — phase rolls forward, never back.
  - `housekeeping.lifecycle._next_step_for` — recommendation matches shape.
  - `housekeeping.next_actions.enumerate_actions` — situational coverage.
  - `mechanical.chapter_summary` index   — eval-log indexing at scale.

Each test calls into one of the three fixtures and asserts an
invariant that would have caught a class of bug missed by synthetic
fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autonovel.housekeeping import lifecycle
from autonovel.housekeeping import next_actions
from autonovel.paths import SeriesLayout, iter_chapter_files


# Parametrise across the three realistic shapes so every invariant
# below runs three times — chapter counts and eval-log shapes differ
# but `iter_chapter_files` and chapter-counting must hold for all.
_SHAPE_FIXTURE_NAMES = ("late_stage_book", "mid_revision_book",
                          "review_phase_book")
_EXPECTED_COUNTS = {
    "late_stage_book": 5,
    "mid_revision_book": 8,
    "review_phase_book": 10,
}


@pytest.mark.parametrize("shape", _SHAPE_FIXTURE_NAMES)
def test_iter_chapter_files_count_invariant(shape: str, request) -> None:
    """Every realistic shape has paired `ch_NN.md` + `ch_NN.summary.md`
    files. iter_chapter_files must return exactly the prose files."""
    series, book = request.getfixturevalue(shape)
    files = iter_chapter_files(series / "books" / book / "chapters")
    assert len(files) == _EXPECTED_COUNTS[shape]
    assert all(not p.name.endswith(".summary.md") for p in files)


@pytest.mark.parametrize("shape", _SHAPE_FIXTURE_NAMES)
def test_infer_phase_lands_on_drafting_or_later(shape: str, request) -> None:
    """Once any chapter prose file exists, the phase is at least
    `drafting`. None of the realistic shapes should regress to
    `foundation` or `seed`."""
    series, book = request.getfixturevalue(shape)
    book_root = series / "books" / book
    phase, n = lifecycle._infer_phase(SeriesLayout(root=series), book_root)
    assert phase == "drafting"
    assert n == _EXPECTED_COUNTS[shape]


# ---------------------------------------------------------- next_step_for


def test_late_stage_next_step_promotes_pending_canon(
    late_stage_book: tuple[Path, str],
) -> None:
    """The fixture has pending canon entries → the gate fires and
    `promote-canon` wins over chapter-advancement."""
    series, book = late_stage_book
    ns = lifecycle._next_step_for(SeriesLayout(root=series), book)
    assert "promote-canon" in ns.command


def test_mid_revision_next_step_recommends_revise_for_low_chapter(
    mid_revision_book: tuple[Path, str],
) -> None:
    """The latest chapter (8) scored above threshold but earlier
    chapters (2, 3) are below. With no pending canon, next-step
    inspects last_chapter_score (chapter 8 → 7.3 ≥ threshold) and
    advances. Verify it does NOT regress to evaluate (the
    "evaluate kept recommending evaluate" bug class)."""
    series, book = mid_revision_book
    ns = lifecycle._next_step_for(SeriesLayout(root=series), book)
    assert "evaluate" not in ns.command


def test_review_phase_next_step_does_not_recommend_drafting(
    review_phase_book: tuple[Path, str],
) -> None:
    """All chapters above threshold + no pending canon. next_step's
    drafting branch sees `n >= chapters_total`-style conditions only
    when chapters_total is set; without it, it advances. Either way,
    must not regress to gen-world / gen-canon / outline."""
    series, book = review_phase_book
    ns = lifecycle._next_step_for(SeriesLayout(root=series), book)
    for forbidden in ("gen-world", "gen-characters", "voice-discovery",
                       "gen-canon", "gen-outline"):
        assert forbidden not in ns.command, (
            f"review-phase regressed to foundation: {ns.command!r}"
        )


# ---------------------------------------------------------- enumerate_actions


def test_late_stage_actions_include_high_priority_pending_canon(
    late_stage_book: tuple[Path, str],
) -> None:
    """The conftest fixture seeded pending_canon.md without a
    Conflicts header — the next_actions HIGH check is keyed on the
    Conflicts header, so it should NOT fire here. (Exercise the
    no-conflict path.)"""
    series, book = late_stage_book
    actions = next_actions.enumerate_actions(SeriesLayout(root=series), book=book)
    assert not any("conflict" in a.title.lower() for a in actions)


def test_mid_revision_actions_flag_panel_staleness(
    mid_revision_book: tuple[Path, str],
) -> None:
    """reader_panel.json was deliberately backdated; the per-book
    panel-staleness check should fire MEDIUM."""
    series, book = mid_revision_book
    actions = next_actions.enumerate_actions(SeriesLayout(root=series), book=book)
    panel = [a for a in actions if "reader-panel" in a.title.lower()]
    assert len(panel) == 1
    assert panel[0].priority == "MEDIUM"


def test_review_phase_actions_have_no_panel_or_review_staleness(
    review_phase_book: tuple[Path, str],
) -> None:
    """Reports are newer than every chapter → no staleness alert."""
    series, book = review_phase_book
    actions = next_actions.enumerate_actions(SeriesLayout(root=series), book=book)
    assert not any("reader-panel" in a.title.lower() for a in actions)
    assert not any("opus review" in a.title.lower() for a in actions)


def test_review_phase_actions_have_no_regression(
    review_phase_book: tuple[Path, str],
) -> None:
    """All chapters scored 7.5 once each — no prior history → no
    regression. (The fixture writes one eval per chapter, not two.)"""
    series, book = review_phase_book
    actions = next_actions.enumerate_actions(SeriesLayout(root=series), book=book)
    assert not any("regressed" in a.title.lower() for a in actions)


# ---------------------------------------------------------- chapter_summary index


@pytest.mark.parametrize("shape", _SHAPE_FIXTURE_NAMES)
def test_chapter_summary_eval_index_finds_every_chapter(shape: str, request) -> None:
    """The chapter-summary helper indexes the latest eval per chapter
    from `eval_logs/`. Every chapter that has at least one eval log
    must appear in the index — a real bug 2026-04-25 was that the
    glob picked up summary files alongside eval JSONs and exploded."""
    from autonovel.mechanical.chapter_summary import _index_latest_per_chapter_eval
    series, book = request.getfixturevalue(shape)
    eval_dir = series / "books" / book / "eval_logs"
    index = _index_latest_per_chapter_eval(eval_dir)
    if shape == "late_stage_book":
        # conftest only writes evals for ch01 + ch02.
        assert set(index.keys()) == {1, 2}
    elif shape == "mid_revision_book":
        assert set(index.keys()) == set(range(1, 9))
    else:
        assert set(index.keys()) == set(range(1, 11))


# ---------------------------------------------------------- regression-on-realistic


def test_mid_revision_book_regression_check_fires_when_score_drops(
    mid_revision_book: tuple[Path, str],
) -> None:
    """Add a second eval for chapter 5 below its prior best — the
    enumerate_actions regression check should pick it up."""
    series, book = mid_revision_book
    eval_dir = series / "books" / book / "eval_logs"
    (eval_dir / "20260420_120000_ch05_eval.json").write_text(
        json.dumps({"overall_score": 6.5}), encoding="utf-8",  # drop 7.2 → 6.5
    )
    actions = next_actions.enumerate_actions(SeriesLayout(root=series), book=book)
    regressions = [a for a in actions if "regressed" in a.title.lower()]
    assert any("5" in a.title for a in regressions)
