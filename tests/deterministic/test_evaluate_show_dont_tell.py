"""Tier-1 regression locks for the show-don't-tell LLM-judge
upgrade in `commands/evaluate.md`.

The actual scoring is the LLM judge's job — Tier-3 smoke covers
the live behaviour. These tests pin the *contract* between the
mechanical pre-flight scanner (`autonovel mechanical
show-dont-tell`) and the evaluate command body so:

  - the dimension `show_dont_tell_ratio` exists in `--chapter`
    mode and `show_dont_tell_arc` in `--full` mode,
  - the body explicitly calls the mechanical scanner,
  - the direct / indirect / hybrid taxonomy is documented so
    the LLM can rely on a stable definition,
  - the `worst_offenders` array is required output.

Future edits that drop one of these surfaces fail a fast
deterministic test instead of waiting for a live eval to drift.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autonovel.adapters.base import discover_commands


@pytest.fixture
def evaluate_cmd():
    here = Path(__file__).resolve().parent.parent.parent / "commands"
    return next(c for c in discover_commands(here) if c.name == "autonovel:evaluate")


def test_dimension_listed_in_chapter_mode(evaluate_cmd) -> None:
    body = evaluate_cmd.body
    assert "show_dont_tell_ratio" in body, (
        "evaluate --chapter mode must list show_dont_tell_ratio "
        "in its dimension list"
    )


def test_dimension_listed_in_full_mode(evaluate_cmd) -> None:
    body = evaluate_cmd.body
    assert "show_dont_tell_arc" in body, (
        "evaluate --full mode must list show_dont_tell_arc "
        "in its dimension list"
    )


def test_body_calls_mechanical_scanner(evaluate_cmd) -> None:
    body = evaluate_cmd.body
    assert "autonovel mechanical show-dont-tell" in body, (
        "evaluate body must invoke the mechanical scanner via Bash "
        "before classifying candidates"
    )


def test_taxonomy_documented(evaluate_cmd) -> None:
    body = evaluate_cmd.body.lower()
    assert "direct" in body
    assert "indirect" in body
    assert "hybrid" in body


def test_worst_offenders_required_output(evaluate_cmd) -> None:
    body = evaluate_cmd.body
    assert "worst_offenders" in body, (
        "show_dont_tell_ratio dimension must include "
        "worst_offenders so brief / revise have line targets"
    )


def test_tell_heavy_chapters_surface_in_full_mode(evaluate_cmd) -> None:
    """`--full` aggregation must surface tell_heavy_chapters
    array so a sweep brief can target them."""
    body = evaluate_cmd.body
    assert "tell_heavy_chapters" in body


def test_zero_candidates_does_not_score_perfect(evaluate_cmd) -> None:
    """The body documents that a chapter with zero candidates
    scores 9.0, not 10.0 — flagging zero candidates is suspicious
    enough that we don't reward it as perfect."""
    body = evaluate_cmd.body
    assert "9.0" in body and "no tell candidates flagged" in body
