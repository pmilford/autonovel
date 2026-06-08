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


def test_title_shot_blocks_overlay_title_not_all_text() -> None:
    r = _req(Shot(id="23", role="title", action="a vellum ledger page on a desk",
                  setting="study", text_card="THE FINAL TOLL"))
    low = r.negative_prompt.lower()
    # targets OVERLAY/poster title type...
    for term in ("title text", "movie title", "caption", "watermark"):
        assert term in low, term
    # ...but NOT broad writing terms that would also kill diegetic ledgers
    assert "letters" not in low and "typography" not in low
    assert "words" not in low
    # the card TEXT itself is never pushed into the visual prompt
    assert "THE FINAL TOLL" not in r.prompt


def test_text_card_on_content_shot_does_NOT_force_text_free() -> None:
    # An escalation shot of a ledger that ALSO has a burned-in stinger card
    # must keep its diegetic writing — the card is a post overlay, not a
    # reason to blank the model's text. No forced no-text terms here.
    r = _req(Shot(id="05", role="escalation", subject_name="J", subject_appearance="x",
                  action="reads the forged ledger, columns of figures",
                  text_card="One ledger could burn it down"))
    assert "title text" not in r.negative_prompt.lower()
    assert "Negative prompt:" not in r.prompt  # no authored negative, none forced


def test_ledger_content_shot_keeps_authored_negative_only() -> None:
    # A ledger shot's negative is whatever the author wrote — we send it
    # verbatim and add NOTHING (so the author can omit "text" to keep the
    # account numbers legible).
    r = _req(Shot(id="18", role="escalation", subject_name="J", subject_appearance="x",
                  action="an open account book, ink figures in columns",
                  negative_prompt="blurry, distorted hands, extra limbs"))
    assert r.negative_prompt == "blurry, distorted hands, extra limbs"
    assert "Negative prompt: blurry, distorted hands, extra limbs" in r.prompt
    assert "title text" not in r.prompt.lower()


def test_title_terms_merge_with_authored_negative() -> None:
    r = _req(Shot(id="23", role="title", action="a parchment plate",
                  text_card="TITLE", negative_prompt="blurry, distorted hands"))
    low = r.negative_prompt.lower()
    assert "blurry" in low and "distorted hands" in low  # authored preserved
    assert "movie title" in low                           # overlay-title added
    assert low.count("watermark") == 1                    # not duplicated


def test_negative_round_trips_in_to_dict() -> None:
    r = _req(Shot(id="01", role="hook", subject_name="J", subject_appearance="x",
                  action="a", negative_prompt="blurry"))
    assert r.to_dict()["negative_prompt"] == "blurry"
