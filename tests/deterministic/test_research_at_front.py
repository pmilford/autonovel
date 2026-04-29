"""Tier-1 tests for the research-at-front-of-foundation wiring.

Three production-side surfaces have to stay aligned for the
research-first foundation flow:

  - `_foundation_gap` recommends `/autonovel:research --from-seed`
    before `gen-world` when `project.yaml :: period.start` is set
    and `shared/research/notes/` is empty. (Already tested in
    test_lifecycle.py — referenced here for completeness.)
  - `commands/gen-world.md` and `commands/gen-canon.md` declare
    `shared/research/notes/*.md` under `reads:` AND mention
    reading the notes in their workflow body. (Tested by the
    Tier-2 contract test that reads-stems must appear in the
    body; this file adds higher-precision regression locks.)
  - The frontmatter contract test catches `reads:` declarations
    that don't appear in the body.

This file's tests focus on the third concern with explicit
fixtures so a future maintainer who removes the research-notes
read instruction breaks a fast deterministic test rather than
discovering the regression at production time.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autonovel.adapters.base import discover_commands


@pytest.fixture
def commands() -> dict:
    here = Path(__file__).resolve().parent.parent.parent / "commands"
    return {c.name: c for c in discover_commands(here)}


def test_gen_world_declares_research_notes_under_reads(commands) -> None:
    cmd = commands["autonovel:gen-world"]
    assert any("research/notes" in p for p in cmd.reads), cmd.reads


def test_gen_canon_declares_research_notes_under_reads(commands) -> None:
    cmd = commands["autonovel:gen-canon"]
    assert any("research/notes" in p for p in cmd.reads), cmd.reads


def test_gen_world_body_mentions_research_notes(commands) -> None:
    cmd = commands["autonovel:gen-world"]
    body = cmd.body.lower()
    assert "research" in body, "gen-world body must mention research"
    assert "notes" in body, "gen-world body must mention notes/"


def test_gen_canon_body_mentions_research_notes(commands) -> None:
    cmd = commands["autonovel:gen-canon"]
    body = cmd.body.lower()
    assert "research" in body, "gen-canon body must mention research"
    assert "notes" in body, "gen-canon body must mention notes/"


def test_gen_canon_body_keeps_research_tag_through_promote(commands) -> None:
    """Canon entries seeded from research notes carry a
    `[research:<slug>]` tag so promote-canon's tagged-survives-
    untagged conflict resolution still works for them."""
    cmd = commands["autonovel:gen-canon"]
    assert "research:" in cmd.body, (
        "gen-canon must instruct the model to preserve the "
        "[research:<slug>] tag through to canon bullets"
    )


def test_gen_world_body_nudges_when_notes_missing(commands) -> None:
    """When `period.start` is set but `shared/research/notes/` is
    empty, gen-world surfaces a one-line nudge to run
    /autonovel:research --from-seed first. Without that nudge,
    period projects can silently bypass the research step."""
    cmd = commands["autonovel:gen-world"]
    body = cmd.body.lower()
    assert "from-seed" in body or "research --from-seed" in body, (
        "gen-world body must mention `/autonovel:research --from-seed` "
        "as the recovery path when notes are missing"
    )


def test_gen_canon_body_nudges_when_notes_missing(commands) -> None:
    cmd = commands["autonovel:gen-canon"]
    body = cmd.body.lower()
    # gen-canon uses the same "no research notes" nudge phrasing.
    assert "research" in body and "notes" in body, (
        "gen-canon body must mention research-notes nudge"
    )
