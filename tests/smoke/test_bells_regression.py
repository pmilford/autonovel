"""Tier-4 regression harness (REWRITE-PLAN.md §12.4).

Frozen set: the final Bells chapters + the `evaluate.py` scores they
produced before the rewrite. For each chapter we re-run the rewritten
`/autonovel:evaluate` and assert the drift is within policy.

Gating:
  - `@pytest.mark.smoke` (costs real spend via `claude -p`).
  - `@pytest.mark.regression` (extra marker so `-m "smoke and not
    regression"` can exclude it on ordinary smoke sweeps).
  - Skips cleanly when `tests/fixtures/bells-reference/chapters/` is
    empty (the Bells prose lives on the `autonovel/bells` branch; see
    the fixture README for how to populate).

Drift policy:
  - `slop_penalty`: deterministic; pinned to ±0.1 (any real change
    means `src/autonovel/mechanical/slop.py` changed).
  - `overall_score`: LLM-judged; pinned to ±0.5 per REWRITE-PLAN §12.4.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autonovel.mechanical import slop_score


REF_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "bells-reference"
SLOP_TOLERANCE = 0.1
OVERALL_TOLERANCE = 0.5


def _load_reference() -> dict:
    return json.loads((REF_DIR / "scores.json").read_text(encoding="utf-8"))


def _available_chapters() -> list[tuple[str, Path]]:
    chdir = REF_DIR / "chapters"
    if not chdir.is_dir():
        return []
    return sorted(
        (p.stem.split("_")[-1], p)
        for p in chdir.glob("ch_*.md")
        if p.stat().st_size > 0
    )


@pytest.mark.smoke
@pytest.mark.regression
def test_bells_mechanical_slop_pinned() -> None:
    """Deterministic check: the mechanical slop scanner's output on each
    frozen Bells chapter matches the reference to within `SLOP_TOLERANCE`.

    This runs without invoking a model — it's a Tier-1-style guard that
    piggy-backs on the Bells fixture because the regex surface and the
    Bells reference scores move together.
    """
    ref = _load_reference()
    chapters = _available_chapters()
    if not chapters:
        pytest.skip(
            "bells-reference/chapters/ is empty; populate it from the "
            "autonovel/bells branch (see fixture README) to run this test"
        )
    ref_chapters = ref.get("chapters", {})
    if not ref_chapters:
        pytest.skip(
            "bells-reference/scores.json has no frozen entries yet; "
            "populate it with a pre-rewrite evaluate.py run"
        )

    drifts = []
    for key, path in chapters:
        if key not in ref_chapters:
            continue
        expected = ref_chapters[key].get("slop_penalty")
        if expected is None:
            continue
        actual = slop_score(path.read_text(encoding="utf-8")).slop_penalty
        delta = abs(actual - expected)
        if delta > SLOP_TOLERANCE:
            drifts.append(f"ch_{key}: expected {expected}, got {actual} (Δ={delta:.2f})")

    assert not drifts, "mechanical slop scores drifted:\n  " + "\n  ".join(drifts)


@pytest.mark.smoke
@pytest.mark.regression
def test_bells_overall_score_within_half_point(tmp_runtime_series) -> None:
    """Run `/autonovel:evaluate --chapter N` against each frozen Bells
    chapter and assert the drift in `overall_score` stays under ±0.5.

    Skipped cleanly when the fixture is empty. Requires a live
    `claude` runtime (smoke-tier cost).
    """
    chapters = _available_chapters()
    ref_chapters = _load_reference().get("chapters", {})
    if not chapters or not ref_chapters:
        pytest.skip("bells-reference is not populated — see fixture README")

    # NOTE for the agent re-entering this code later:
    #
    # The Bells prose is a single-book project under the pre-rewrite
    # repo layout; the rewritten commands are series-shaped. Bridging
    # the two is the actual work of this test, which is why it's
    # gated until the fixture is populated. The intended shape is:
    #
    #   1. Build a throwaway series under `tmp_runtime_series` with
    #      one book named "bells".
    #   2. Copy each frozen chapter into
    #      `books/bells/chapters/ch_NN.md`.
    #   3. Invoke `/autonovel:evaluate --chapter N --book bells`.
    #   4. Read the eval log, compare `overall_score` to the reference.
    #
    # This is left as a TODO wrapped in an explicit skip so the
    # harness doesn't silently pass.
    pytest.skip("Bells → series bridge not implemented yet; see inline TODO")
