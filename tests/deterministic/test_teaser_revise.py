"""Tier-1 tests for the teaser revise-loop + richer stub cards (2026-06-07).

The teaser flow gained the missing "revise" half (act on the critique in
place, like the book's evaluate→revise) and a clearer critique verdict, and
the offline stub keyframe now draws a labelled scene card (location /
dialogue / plot) so the free first-pass review reads clearly.
"""

from __future__ import annotations

from pathlib import Path

from autonovel.teaser import render, backends
from autonovel.teaser.render import RenderRequest
from autonovel.teaser.shots import Shot
from autonovel.housekeeping.lifecycle import _teaser_next_step, _TEASER_NEXT


def _shot():
    return Shot(id="01", role="hook", subject_name="JAKOB",
                subject_appearance="fur-collared merchant",
                action="snaps the ledger shut",
                setting="candlelit counting-house, Augsburg",
                beat_note="Jakob realises the accounts are forged",
                text_card="In a city built on debt",
                audio={"dialogue": [{"speaker": "JAKOB", "line": "They said the books would balance."}]})


# ----------------------- richer stub scene card --------------------------


def test_build_request_populates_card() -> None:
    req = render.build_request(_shot(), provider="stub", kind="image", out_dir=Path("/tmp"))
    assert req.card["location"].startswith("candlelit")
    assert "JAKOB" in req.card["dialogue"] and "balance" in req.card["dialogue"]
    assert "forged" in req.card["plot"]
    assert req.card["role"] == "hook"
    assert req.card["text_card"] == "In a city built on debt"


def test_card_round_trips_in_to_dict() -> None:
    req = render.build_request(_shot(), provider="stub", kind="image", out_dir=Path("/tmp"))
    assert req.to_dict()["card"]["plot"] == "Jakob realises the accounts are forged"


def test_stub_draws_card_png() -> None:
    req = render.build_request(_shot(), provider="stub", kind="image", out_dir=Path("/tmp"))
    png = backends.make_stub(req)
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 1000


def test_stub_bare_request_still_renders() -> None:
    bare = RenderRequest(shot_id="x", kind="image", url="", out_path="",
                         prompt="a wide shot of the sea at dawn", seed=3,
                         width=320, height=180)
    assert not bare.card
    png = backends.make_stub(bare)  # falls back to drawing the prompt
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


# ----------------------- revise-loop next step ---------------------------


def test_teaser_revise_in_next_step_chain() -> None:
    ns = _teaser_next_step("autonovel:teaser-revise", "medieval-king-maker")
    assert ns is not None
    assert "teaser-critique" in ns.command  # re-confirm after applying fixes
    assert "draft" not in ns.command


def test_critique_points_at_revise() -> None:
    # the teaser-critique next-step rationale names teaser-revise as the way
    # to ACT on findings (no forced hand edits).
    _, rationale = _TEASER_NEXT["autonovel:teaser-critique"]
    assert "teaser-revise" in rationale


def test_orchestrator_next_step_is_render_not_critique() -> None:
    # the /autonovel:teaser orchestrator now runs critique→revise itself, so
    # its next step is render (validate via stub), not "go critique".
    ns = _teaser_next_step("autonovel:teaser", "medieval-king-maker")
    assert ns is not None and "teaser-render" in ns.command
    assert "teaser-critique" not in ns.command
