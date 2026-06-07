"""Tier-1 tests for the render-side fixes (2026-06-07):

- The negative prompt is now actually SENT (folded into the prompt as a
  trailing "Negative prompt:" line) — it was authored but dropped before.
- A `role: title` / text-card shot renders TEXT-FREE: no-legible-type terms
  are auto-added to its negative, so the model stops hallucinating a (wrong)
  title; the real title is burned in at assembly.
"""

from __future__ import annotations

from pathlib import Path

from autonovel.teaser import render
from autonovel.teaser.shots import Shot


def _req(shot, provider="gemini"):
    return render.build_request(shot, provider=provider, kind="image", out_dir=Path("/tmp"))


def test_authored_negative_is_folded_into_prompt() -> None:
    r = _req(Shot(id="01", role="hook", subject_name="J", subject_appearance="x",
                  action="runs through rain", negative_prompt="blurry, extra limbs"))
    assert "Negative prompt: blurry, extra limbs" in r.prompt
    assert r.negative_prompt == "blurry, extra limbs"


def test_no_negative_leaves_prompt_clean() -> None:
    r = _req(Shot(id="02", role="escalation", subject_name="J",
                  subject_appearance="x", action="waits"))
    assert "Negative prompt:" not in r.prompt
    assert r.negative_prompt == ""


def test_title_shot_is_text_free() -> None:
    r = _req(Shot(id="23", role="title", action="a vellum ledger page on a desk",
                  setting="study", text_card="THE FINAL TOLL"))
    low = r.negative_prompt.lower()
    for term in ("text", "letters", "typography", "title card", "watermark"):
        assert term in low, term
    assert "Negative prompt:" in r.prompt and "typography" in r.prompt
    # the card TEXT itself is never pushed into the visual prompt
    assert "THE FINAL TOLL" not in r.prompt


def test_text_card_shot_also_text_free() -> None:
    # not role=title, but carries a text_card → still text-free
    r = _req(Shot(id="05", role="escalation", subject_name="J", subject_appearance="x",
                  action="reads the ledger", text_card="One ledger could burn it down"))
    assert "letters" in r.negative_prompt.lower()


def test_title_text_free_merges_with_authored_negative() -> None:
    r = _req(Shot(id="23", role="title", action="a parchment plate",
                  text_card="TITLE", negative_prompt="blurry, distorted hands"))
    low = r.negative_prompt.lower()
    assert "blurry" in low and "distorted hands" in low  # authored preserved
    assert "typography" in low                            # no-text added
    # idempotent-ish: a term already present isn't duplicated
    assert low.count("watermark") == 1


def test_negative_round_trips_in_to_dict() -> None:
    r = _req(Shot(id="01", role="hook", subject_name="J", subject_appearance="x",
                  action="a", negative_prompt="blurry"))
    assert r.to_dict()["negative_prompt"] == "blurry"
