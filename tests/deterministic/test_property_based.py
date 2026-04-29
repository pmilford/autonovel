"""Property-based tests via `hypothesis`.

Background: targeted unit tests catch known bug shapes; property
tests catch the *unknown* ones by generating random valid book
layouts and asserting invariants that must hold across them all.
The failure modes this targets:

- glob patterns that pick up files they shouldn't
  (`ch_*.md` matching `ch_NN.summary.md`).
- phase inference that regresses to an earlier phase under unusual
  shapes.
- next-step recommendations that come back empty or with
  placeholders unsubstituted.
- chapter-summary indexer mis-counting eval logs across naming
  conventions.
- enumerate_actions returning a row with priority outside the
  defined set or a target outside the book.
- entity-track / motifs / dashboard helpers crashing on edge-case
  prose (empty chapters, all-frontmatter files, single
  characters, Unicode-heavy text).

These tests run as Tier-1 (deterministic). hypothesis is a hard
dependency under `[test]`; if not installed they skip cleanly.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings, strategies as st

from autonovel.housekeeping import lifecycle, next_actions, scaffold
from autonovel.housekeeping.next_step import (
    PipelineState,
    next_step as decision_table_next_step,
)
from autonovel.mechanical.chapter_summary import summarize_chapters
from autonovel.mechanical.dashboard import build_dashboard
from autonovel.mechanical.entity_track import build_report as build_entity_report
from autonovel.mechanical.motifs import build_report as build_motif_report
from autonovel.paths import SeriesLayout, iter_chapter_files


# ---------------------------------------------------------- strategies


# A "shape" of a book layout — what the property tests vary over.
# Each strategy generates one component; the helpers below assemble
# them into a real on-disk series.

_chapter_count = st.integers(min_value=0, max_value=12)
_score = st.one_of(st.none(), st.floats(min_value=0.0, max_value=10.0,
                                          allow_nan=False, allow_infinity=False))
_pov = st.sampled_from(["Tommaso", "Lucia", "Niccolò", "Anselmo", "Beatrice"])
_status = st.sampled_from(["drafted", "revised", "evaluated"])

# Prose that exercises tricky edges: empty / Unicode / dialogue-heavy /
# ascii-only. Keep small to keep hypothesis fast.
_prose = st.one_of(
    st.just("Plain English prose."),
    st.just("Niccolò spoke. Tommaso replied. Lucia waited."),
    st.just("\"Dialogue,\" she said.\n\n\"More dialogue.\""),
    st.just("Tommaso wandered.\n\n***\n\nA new scene began."),
    st.just(""),  # empty body — tests robustness
)


@st.composite
def _book_layout(draw) -> dict:
    """Generate a random book layout description."""
    n_ch = draw(_chapter_count)
    chapters: list[dict] = []
    for n in range(1, n_ch + 1):
        chapters.append({
            "n": n,
            "pov": draw(_pov),
            "status": draw(_status),
            "prose": draw(_prose),
            "score": draw(_score),
            "has_summary": draw(st.booleans()),
        })
    return {
        "chapter_count": n_ch,
        "chapters": chapters,
        "has_motifs": draw(st.booleans()),
        "has_entities": draw(st.booleans()),
        "has_pending_canon": draw(st.booleans()),
    }


def _materialise(tmp_path: Path, layout: dict) -> SeriesLayout:
    """Realise a layout as on-disk files. Reuses scaffold.new_series so
    the foundation files are populated and `_infer_phase` doesn't
    bail at the seed stage."""
    series_dir = tmp_path / "demo"
    if series_dir.exists():
        # hypothesis reuses tmp_path across @given iterations — clean.
        import shutil
        shutil.rmtree(series_dir)
    res = scaffold.new_series(series_dir, series_name="demo")
    scaffold.new_book(res.series, book_name="b", pov="Tommaso")
    layout_obj = SeriesLayout(root=res.series.root)

    long = "Real content. " * 30
    (layout_obj.shared / "world.md").write_text(
        f"# World\n\n{long}\n", encoding="utf-8")
    (layout_obj.shared / "characters.md").write_text(
        f"# Characters\n\n{long}\n", encoding="utf-8")
    (layout_obj.shared / "canon.md").write_text(
        f"# Canon\n\n{long}\n- [Tommaso birthday] 1487-05-12\n",
        encoding="utf-8")
    book_root = layout_obj.books / "b"
    (book_root / "voice.md").write_text(f"# Voice\n\n{long}\n", encoding="utf-8")
    (book_root / "outline.md").write_text(f"# Outline\n\n{long}\n", encoding="utf-8")

    chapters = book_root / "chapters"
    chapters.mkdir(exist_ok=True)
    eval_dir = book_root / "eval_logs"
    eval_dir.mkdir(exist_ok=True)
    for ch in layout["chapters"]:
        n = ch["n"]
        (chapters / f"ch_{n:02d}.md").write_text(
            f"---\nbook: b\nchapter: {n}\npov: {ch['pov']}\n"
            f"events: []\nstatus: {ch['status']}\nword_count: 100\n---\n\n"
            + (ch["prose"] or "Prose."),
            encoding="utf-8",
        )
        if ch["has_summary"]:
            (chapters / f"ch_{n:02d}.summary.md").write_text(
                f"**Plot:** ch{n}.\n**Cast on stage:** {ch['pov']}\n"
                f"**Story time:** 2020-01-{n:02d}.\n",
                encoding="utf-8",
            )
        if ch["score"] is not None:
            (eval_dir / f"ch{n:02d}_eval.json").write_text(
                json.dumps({"overall_score": ch["score"]}),
                encoding="utf-8",
            )

    if layout["has_motifs"]:
        (book_root / "motifs.md").write_text(
            "- bell: bell, bells\n- mortar: mortar\n", encoding="utf-8")
    if layout["has_entities"]:
        (book_root / "entities.md").write_text(
            "- jakob: Jakob\n- lucia: Lucia\n", encoding="utf-8")
    if layout["has_pending_canon"]:
        (book_root / "pending_canon.md").write_text(
            "# Pending\n- [foo] bar\n", encoding="utf-8")

    return layout_obj


_PROPERTY_SETTINGS = settings(
    max_examples=25,
    deadline=None,  # filesystem ops in helpers can spike on slow runners
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


# ---------------------------------------------------------- invariants


@given(_book_layout())
@_PROPERTY_SETTINGS
def test_iter_chapter_files_never_includes_summary_files(
    tmp_path_factory, layout
) -> None:
    """The 2026-04-25 production bug: iter_chapter_files returned
    `ch_NN.md` AND `ch_NN.summary.md`. This is a regression-by-
    invariant — for every randomly-generated layout, no entry in
    iter_chapter_files's output should end in `.summary.md`."""
    tmp = tmp_path_factory.mktemp("prop")
    series = _materialise(tmp, layout)
    files = iter_chapter_files(series.books / "b" / "chapters")
    for p in files:
        assert not p.name.endswith(".summary.md"), p.name
    # Count must equal layout's chapter count exactly.
    assert len(files) == layout["chapter_count"]


@given(_book_layout())
@_PROPERTY_SETTINGS
def test_infer_phase_returns_a_known_phase(tmp_path_factory, layout) -> None:
    """`_infer_phase` must always return one of the known phase
    names — never empty, never garbage. With a populated foundation
    + zero or more chapters, valid outputs are 'foundation' or
    'drafting' (no chapters drafted yet → foundation; ≥1 → drafting)."""
    tmp = tmp_path_factory.mktemp("prop")
    series = _materialise(tmp, layout)
    book_root = series.books / "b"
    phase, n = lifecycle._infer_phase(series, book_root)
    assert phase in {"seed", "foundation", "drafting", "revision",
                      "review", "export", "done"}
    assert n == layout["chapter_count"]


@given(_book_layout())
@_PROPERTY_SETTINGS
def test_next_step_for_returns_non_empty_command(tmp_path_factory, layout) -> None:
    """Every layout must produce SOME command recommendation. An
    empty command would mean `/autonovel:next` shows the user nothing
    actionable — that's a bug. The command must also be a real
    `/autonovel:*` slash-command (or `autonovel <subcommand>` for
    promote-canon) reference, not a placeholder."""
    tmp = tmp_path_factory.mktemp("prop")
    series = _materialise(tmp, layout)
    ns = lifecycle._next_step_for(series, "b")
    assert ns.command, "next_step returned an empty command"
    assert ns.rationale, "next_step returned an empty rationale"
    assert ns.command.startswith(("/autonovel:", "autonovel ")), ns.command
    # No unsubstituted placeholders.
    assert "{" not in ns.command
    assert "}" not in ns.command


@given(_book_layout())
@_PROPERTY_SETTINGS
def test_enumerate_actions_priorities_are_valid(tmp_path_factory, layout) -> None:
    tmp = tmp_path_factory.mktemp("prop")
    series = _materialise(tmp, layout)
    actions = next_actions.enumerate_actions(series, book="b")
    for a in actions:
        assert a.priority in {"HIGH", "MEDIUM", "LOW", "INFO"}
        assert a.title, f"action with empty title: {a}"
        assert a.rationale, f"action with empty rationale: {a}"


@given(_book_layout())
@_PROPERTY_SETTINGS
def test_summarize_chapters_count_matches_chapter_files(
    tmp_path_factory, layout
) -> None:
    tmp = tmp_path_factory.mktemp("prop")
    series = _materialise(tmp, layout)
    rows = summarize_chapters(series.books / "b")
    assert len(rows) == layout["chapter_count"]


@given(_book_layout())
@_PROPERTY_SETTINGS
def test_dashboard_does_not_crash_on_arbitrary_layouts(
    tmp_path_factory, layout
) -> None:
    """Dashboard must not crash — a downstream user runs it
    repeatedly on whatever shape their book is in."""
    tmp = tmp_path_factory.mktemp("prop")
    series = _materialise(tmp, layout)
    report = build_dashboard(series.books / "b")
    assert len(report.rows) == layout["chapter_count"]
    if layout["chapter_count"] == 0:
        assert report.aggregate is None


@given(_book_layout())
@_PROPERTY_SETTINGS
def test_entity_track_does_not_crash(tmp_path_factory, layout) -> None:
    tmp = tmp_path_factory.mktemp("prop")
    series = _materialise(tmp, layout)
    report = build_entity_report(series.books / "b", series_root=series.root)
    assert len(report.rows) == layout["chapter_count"]
    # When entities.md OR canon.md provides entities, source must be
    # a known label. When neither, source is "none".
    assert report.source in {"entities.md", "canon.md", "override", "none"}


@given(_book_layout())
@_PROPERTY_SETTINGS
def test_motifs_does_not_crash(tmp_path_factory, layout) -> None:
    tmp = tmp_path_factory.mktemp("prop")
    series = _materialise(tmp, layout)
    report = build_motif_report(series.books / "b")
    assert len(report.rows) == layout["chapter_count"]


# ---------------------------------------------------------- decision-table


# PipelineState's strategy — exercised independently of disk.
@st.composite
def _pipeline_state(draw) -> PipelineState:
    return PipelineState(
        book="b",
        phase=draw(st.sampled_from(["seed", "foundation", "drafting",
                                      "revision", "review", "export", "done"])),
        foundation_score=draw(st.floats(min_value=0.0, max_value=10.0,
                                          allow_nan=False, allow_infinity=False)),
        lore_score=draw(st.floats(min_value=0.0, max_value=10.0,
                                    allow_nan=False, allow_infinity=False)),
        chapters_drafted=draw(st.integers(min_value=0, max_value=20)),
        chapters_total=draw(st.integers(min_value=0, max_value=20)),
        last_chapter_number=draw(st.one_of(st.none(),
                                            st.integers(min_value=1, max_value=20))),
        last_chapter_score=draw(st.one_of(
            st.none(),
            st.floats(min_value=0.0, max_value=10.0,
                      allow_nan=False, allow_infinity=False),
        )),
        revision_cycles_run=draw(st.integers(min_value=0, max_value=10)),
        adversarial_done=draw(st.booleans()),
        reader_panel_done=draw(st.booleans()),
        review_done=draw(st.booleans()),
        has_pending_canon=draw(st.booleans()),
    )


@given(_pipeline_state())
@_PROPERTY_SETTINGS
def test_decision_table_always_returns_command_and_rationale(
    state: PipelineState,
) -> None:
    """The pure-function next_step decision table must produce a
    non-empty command + rationale for every legal PipelineState."""
    ns = decision_table_next_step(state)
    assert ns.command, ns
    assert ns.rationale, ns


@given(_pipeline_state())
@_PROPERTY_SETTINGS
def test_decision_table_command_uses_correct_namespace(
    state: PipelineState,
) -> None:
    """Every emitted command must be either a `/autonovel:*` slash
    command or an `autonovel <subcommand>` invocation. No other
    shapes are valid surface."""
    ns = decision_table_next_step(state)
    assert ns.command.startswith(("/autonovel:", "autonovel ")), ns.command
