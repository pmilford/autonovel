"""Tier-1 tests for movie-teaser Phase 1 *final*: the malformed-input
guard on ``shots.load`` and the two new commands (``teaser`` orchestrator,
``teaser-critique``).

Structure/robustness only — the creative critique is judged by the LLM in
the command body (feedback_avoid_brittle_python).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel.teaser import shots as shots_mod

_COMMANDS = Path(__file__).resolve().parent.parent.parent / "commands"


def _run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", *argv],
        capture_output=True, text=True,
    )


# ------------------- malformed-input guard (the probe crash) -------------


def test_load_rejects_non_object_top_level(tmp_path: Path) -> None:
    """A teaser.json whose top level is a list/string must raise a clear
    ValueError, not an opaque AttributeError ('str' object has no
    attribute 'get') — the failure mode hit while probing the validator."""
    for payload in ('"just a string"', "[1, 2, 3]", "42"):
        p = tmp_path / "bad.json"
        p.write_text(payload, encoding="utf-8")
        with pytest.raises(ValueError, match="top level must be a JSON object"):
            shots_mod.load(p)


def test_cli_validate_clean_error_on_malformed_top_level(tmp_path: Path) -> None:
    p = tmp_path / "probe.json"
    p.write_text('"not a teaser"', encoding="utf-8")
    out = _run("teaser-validate", str(p))
    assert out.returncode == 2  # handled error, not a crash
    assert "top level must be a JSON object" in out.stderr


# ------------------------- the new commands ------------------------------


def test_teaser_orchestrator_command_exists_and_chains() -> None:
    body = (_COMMANDS / "teaser.md").read_text(encoding="utf-8")
    assert "name: autonovel:teaser" in body
    # Chains the two free planning stages.
    assert "/autonovel:teaser-beats" in body
    assert "/autonovel:shot-prompts" in body
    # Runs each stage in a fresh subagent for context hygiene.
    assert "task" in body.lower() and "fresh subagent" in body.lower()
    # Stays free — no generation.
    assert "free" in body.lower()


def test_teaser_critique_command_is_read_only_and_two_pass() -> None:
    body = (_COMMANDS / "teaser-critique.md").read_text(encoding="utf-8")
    assert "name: autonovel:teaser-critique" in body
    # Mechanical pass goes through the CLI helper (pipx-safe; see contract).
    assert "autonovel mechanical teaser-critique" in body
    # Read-only on the load-bearing teaser.json.
    assert "read-only" in body.lower() and "never mutate" in body.lower()
    # Writes an advisory report.
    assert "critique.md" in body
