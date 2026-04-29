"""Tier-1 regression locks for the `--phase series` mode in
`commands/evaluate.md`.

The actual scoring is the LLM judge's job — Tier-3 smoke covers
live behaviour. These tests pin the contract surface so:

  - the new mode is documented in argument-hint and the Five
    Modes purpose-block summary,
  - the body explicitly calls `autonovel mechanical series-arc`
    via Bash (paired with the structural scoreboard),
  - the dimension list is complete and stable,
  - the eval log lands at `.autonovel/eval_logs/<ts>_series.json`
    (NOT under a single book — this is series-level),
  - the mode requires ≥2 books,
  - the unresolved_thread_payoff_plan array is required output.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autonovel.adapters.base import discover_commands


@pytest.fixture
def evaluate_cmd():
    here = Path(__file__).resolve().parent.parent.parent / "commands"
    return next(c for c in discover_commands(here) if c.name == "autonovel:evaluate")


def test_argument_hint_lists_phase_series(evaluate_cmd) -> None:
    assert "--phase series" in (evaluate_cmd.argument_hint or "")


def test_purpose_block_lists_five_modes(evaluate_cmd) -> None:
    """The high-level mode summary must include `--phase series`
    so users discover it without reading the workflow steps."""
    body = evaluate_cmd.body
    assert "--phase series" in body


def test_body_invokes_series_arc_helper(evaluate_cmd) -> None:
    """The mode is paired with the structural helper — the
    helper provides evidence, the LLM provides judgment."""
    body = evaluate_cmd.body
    assert "autonovel mechanical series-arc" in body


def test_dimension_list_complete(evaluate_cmd) -> None:
    body = evaluate_cmd.body
    expected = [
        "series_question",
        "early_setup_late_payoff",
        "cross_book_character_growth",
        "world_evolution_consistency",
        "tonal_continuity",
    ]
    missing = [d for d in expected if d not in body]
    assert not missing, f"--phase series missing dimensions: {missing}"


def test_eval_log_path_is_series_level(evaluate_cmd) -> None:
    body = evaluate_cmd.body
    assert ".autonovel/eval_logs/" in body
    assert "_series.json" in body


def test_requires_two_books(evaluate_cmd) -> None:
    body = evaluate_cmd.body
    assert "≥ 2" in body or ">= 2" in body or "two books" in body.lower()


def test_unresolved_thread_payoff_plan_required(evaluate_cmd) -> None:
    """Brief / revise need a concrete list of thread payoff
    debts to act on; this is the load-bearing output."""
    body = evaluate_cmd.body
    assert "unresolved_thread_payoff_plan" in body


def test_book_arg_not_required_in_series_mode(evaluate_cmd) -> None:
    """`--book` is required for every other mode but not for
    `--phase series` (it's whole-series)."""
    body = evaluate_cmd.body
    assert "EXCEPT `--phase series`" in body or (
        "--book" in body and "phase series" in body and "whole-series" in body
    )
