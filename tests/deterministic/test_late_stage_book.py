"""Regression tests against a realistic late-stage book.

Background: through 2026-04-24/25, several bugs slipped past Tier 1+2
because synthetic test fixtures used 0-2 chapters with no adjunct files
(no summaries, no eval logs, no briefs, no edit logs, no
pending_canon). At realistic late-stage book shapes — chapters 1-5
drafted, summaries paired, evals run on some chapters, mid-revision —
glob patterns and state inference take different paths.

These tests use the `late_stage_book` fixture (see conftest.py) which
writes a populated five-chapter book with all the adjunct artefacts a
real run produces. Adding a regression here is cheap; the goal is to
make "pass against this fixture" the default coverage shape rather
than the exception.
"""

from __future__ import annotations

import json
from pathlib import Path

from autonovel.housekeeping import lifecycle
from autonovel.housekeeping import status as status_mod
from autonovel.paths import SeriesLayout, iter_chapter_files


def test_iter_chapter_files_excludes_summaries(late_stage_book: tuple[Path, str]) -> None:
    series, book = late_stage_book
    chapters = series / "books" / book / "chapters"
    files = iter_chapter_files(chapters)
    # 5 chapter files, NOT 10 (which would include the 5 summary files).
    assert len(files) == 5
    assert all(p.name.startswith("ch_") and not p.name.endswith(".summary.md")
               for p in files)


def test_count_chapters_late_stage(late_stage_book: tuple[Path, str]) -> None:
    series, book = late_stage_book
    n = status_mod._count_chapters(series / "books" / book / "chapters")
    assert n == 5


def test_next_step_recognizes_eval_score(late_stage_book: tuple[Path, str]) -> None:
    """Bug 2026-04-25: after `/autonovel:evaluate --chapter 5`, next-step
    should advance (score ≥ threshold) or revise (< threshold), not loop
    on `evaluate` again. This fixture has eval logs for chapters 1 and 2
    but not 3-5; chapter 5 (the latest) has no eval, so next-step should
    recommend evaluate of chapter 5."""
    series, book = late_stage_book
    layout = SeriesLayout(root=series)
    # Need to drop a fresh eval for chapter 5 to verify the score path.
    eval_dir = series / "books" / book / "eval_logs"
    (eval_dir / "ch05_eval.json").write_text(
        json.dumps({"overall_score": 7.2}), encoding="utf-8",
    )
    # Pending canon has entries — the gate would fire first; clear it
    # so we test the eval-score path directly.
    (series / "books" / book / "pending_canon.md").write_text(
        "# Pending\n", encoding="utf-8",
    )
    next_step = lifecycle._next_step_for(layout, book)
    # Score 7.2 ≥ 6.0 threshold → advance to chapter 6 draft.
    assert "draft 6" in next_step.command, (
        f"expected next-step to advance to draft 6 with score 7.2, "
        f"got {next_step.command!r}"
    )


def test_next_step_recommends_revise_below_threshold(
    late_stage_book: tuple[Path, str],
) -> None:
    """If the latest chapter scored below threshold, next-step
    recommends revise, not draft N+1. The fixture's chapter 2 has
    score 5.9 — but chapter 5 is the latest. We push chapter 5's
    score below threshold and verify."""
    series, book = late_stage_book
    eval_dir = series / "books" / book / "eval_logs"
    (eval_dir / "ch05_eval.json").write_text(
        json.dumps({"overall_score": 5.5}), encoding="utf-8",
    )
    # Clear pending_canon so the gate doesn't fire first.
    (series / "books" / book / "pending_canon.md").write_text(
        "# Pending\n", encoding="utf-8",
    )
    layout = SeriesLayout(root=series)
    next_step = lifecycle._next_step_for(layout, book)
    assert "revise" in next_step.command and "5" in next_step.command


def test_pending_canon_gate_fires_on_late_stage_book(
    late_stage_book: tuple[Path, str],
) -> None:
    """The fixture ships with two pending-canon entries (one
    research-tagged, one chapter-derived). Next-step must recommend
    `/autonovel:promote-canon` before any chapter advancement."""
    series, book = late_stage_book
    layout = SeriesLayout(root=series)
    next_step = lifecycle._next_step_for(layout, book)
    assert "promote-canon" in next_step.command


def test_no_command_body_glob_matches_summary_files() -> None:
    """Sanity scan: no command body uses `glob('ch_*.md')` literally
    in instructions to the LLM. The pattern matches both prose and
    summary files; the right glob is via `iter_chapter_files`."""
    commands_dir = (
        Path(__file__).resolve().parent.parent.parent / "commands"
    )
    offenders: list[tuple[str, int, str]] = []
    for md in sorted(commands_dir.glob("*.md")):
        for i, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            # Only flag literal `glob('ch_*.md')` or `glob("ch_*.md")`
            # in code-block context — README-style mentions of the
            # pattern in prose are fine.
            stripped = line.strip()
            if "glob" in stripped and ("ch_*.md" in stripped):
                # Guard: code-block fences or backticked snippets.
                if "`" in line or stripped.startswith(("    ", "\t")):
                    offenders.append((md.name, i, stripped))
    assert not offenders, (
        f"command bodies use literal `glob('ch_*.md')` (would also match "
        f"ch_NN.summary.md). Use `iter_chapter_files()` or filter "
        f"explicitly. Offenders:\n"
        + "\n".join(f"  {n}:{i}: {l}" for n, i, l in offenders)
    )
