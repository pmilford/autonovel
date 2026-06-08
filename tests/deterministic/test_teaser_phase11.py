"""Tier-1 tests for movie-teaser Phase 11: storytelling QUALITY (2026-06-08).

Phase 6 enforced story *structure* (a spine block exists, ≥N dialogue lines
exist, cards exist, 4-act roles, monotonic stakes_level) — a floor, not
quality. A teaser passed every mechanical gate and was still boring. Phase
11 adds the *interestingness* half:

  - an LLM-authored quality scorecard (`quality.json`) + a HARD quality gate
    (overall ≥ 7 AND no dimension < 5), computed in one place,
  - a spine `turn` (the midpoint reversal) and per-shot `character_beat`,
  - a length-aware pacing model (movements, dialogue target),
  - the render gate refuses a real generation on a story-complete teaser
    that is not interesting enough.

Renders here only ever use `--dry-run` or `--provider stub` — never a keyed
provider (a non-dry keyed render actually spends).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.teaser import beats, critique, providers, quality
from autonovel.teaser.shots import Shot, Spine, Teaser


def _run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "autonovel.mechanical", *argv],
                          capture_output=True, text=True)


# ----------------------------- quality module ----------------------------

def _full_scores(**override: int) -> dict[str, int]:
    s = {k: 8 for k in quality.DIMENSION_KEYS}
    s.update(override)
    return s


def test_quality_gate_passes_when_all_strong() -> None:
    s = quality.QualityScore(scores=_full_scores())
    assert s.passes()
    assert s.verdict() == "PASS"
    assert s.overall() == 8.0
    assert s.gate_reasons() == []


def test_quality_gate_blocks_on_one_dead_dimension() -> None:
    s = quality.QualityScore(scores=_full_scores(dialogue_quality=3))
    assert not s.passes()
    assert any("dialogue_quality" in r for r in s.gate_reasons())
    # the dead dimension is the first weakest (the de-boring target)
    assert s.weakest(1) == [("dialogue_quality", 3)]


def test_quality_gate_blocks_on_low_overall_even_if_no_dim_dead() -> None:
    # all 6 -> overall 6 < 7, but every dim >= 5 (no dead dim)
    s = quality.QualityScore(scores=_full_scores(**{k: 6 for k in quality.DIMENSION_KEYS}))
    assert not s.low_dimensions()
    assert not s.passes()
    assert any("overall" in r for r in s.gate_reasons())


def test_quality_gate_blocks_when_unscored() -> None:
    s = quality.QualityScore(scores={"hook_grip": 9})
    assert not s.passes()
    assert s.missing_dimensions()
    assert any("un-scored" in r for r in s.gate_reasons())


def test_quality_out_of_range_rejected() -> None:
    s = quality.QualityScore(scores=_full_scores(hook_grip=11))
    assert not s.passes()
    assert "hook_grip" in s.out_of_range()
    # bool is not a valid score (bool is an int subclass)
    s2 = quality.QualityScore(scores={**_full_scores(), "coherence": True})
    assert "coherence" in s2.missing_dimensions()


def test_quality_round_trips_and_recomputes_verdict() -> None:
    s = quality.QualityScore(scores=_full_scores(surprise_turn=2),
                             notes={"surprise_turn": "no reversal at all"})
    d = s.to_dict()
    assert d["verdict"] == "BLOCK" and "surprise_turn" in d["weakest"]
    s2 = quality.QualityScore.from_dict(d)
    assert s2.scores == s.scores and s2.notes["surprise_turn"]
    # a tampered persisted verdict is ignored — recomputed from scores
    d["verdict"] = "PASS"
    assert quality.QualityScore.from_dict(d).verdict() == "BLOCK"


def test_quality_cli_template_and_gate(tmp_path: Path) -> None:
    out = _run("teaser-quality", "--template")
    assert out.returncode == 0
    tmpl = json.loads(out.stdout)
    assert set(tmpl["scores"]) == set(quality.DIMENSION_KEYS)

    qp = tmp_path / "quality.json"
    quality.dump(quality.QualityScore(scores=_full_scores()), qp)
    ok = _run("teaser-quality", str(qp))
    assert ok.returncode == 0 and "PASS" in ok.stdout

    quality.dump(quality.QualityScore(scores=_full_scores(button=2)), qp)
    blocked = _run("teaser-quality", str(qp), "--format", "json")
    assert blocked.returncode == 3
    pay = json.loads(blocked.stdout)
    assert pay["passes"] is False and pay["verdict"] == "BLOCK"

    # missing scorecard -> exit 3, not a crash
    miss = _run("teaser-quality", str(tmp_path / "nope.json"))
    assert miss.returncode == 3


# --------------------------- spine.turn + character ----------------------

def test_spine_turn_round_trips_and_is_omitted_when_empty() -> None:
    sp = Spine(dramatic_question="q", turn="the ally is the enemy")
    assert "turn" in sp.to_dict()
    assert Spine.from_dict(sp.to_dict()).turn == "the ally is the enemy"
    # additive: an old spine with no turn omits the key
    assert "turn" not in Spine(dramatic_question="q").to_dict()


def test_no_turn_is_advisory_not_a_story_gate_block() -> None:
    # a full spine WITHOUT a turn must still be story-ready (turn is enforced
    # by the quality gate, not the structural story gate)
    sp = Spine(dramatic_question="q", logline="l", want="w", opposing_force="f",
               emotional_arc="a", score_direction="s", genre="thriller")  # no turn
    t = Teaser(title="T", length_s=12, provider="veo", spine=sp, shots=[
        Shot(id="01", role="hook", subject_name="J", subject_appearance="x", action="a",
             text_card="c1", audio={"dialogue": [{"speaker": "J", "line": "one"}]}),
        Shot(id="02", role="button", subject_name="J", subject_appearance="x", action="b",
             text_card="c2", audio={"dialogue": [{"speaker": "J", "line": "two"}]}),
    ])
    rep = critique.critique(t, providers.get("veo"))
    codes = {f.code for f in rep.findings}
    assert "no-turn" in codes                      # advisory flag present
    assert "no-turn" not in critique.STORY_GATE_CODES
    assert critique.story_ready(rep)               # but not blocking


def test_character_beat_round_trips_and_critique_flags_missing() -> None:
    s = Shot(id="01", role="hook", subject_name="J", subject_appearance="x",
             action="a", character_beat="want")
    assert s.to_dict()["character_beat"] == "want"
    t = Teaser(title="T", provider="veo", shots=[s])
    assert t.character_beat_kinds() == {"want"}
    rep = critique.critique(t, providers.get("veo"))
    # has 'want' but no 'cost' -> still flagged
    assert "no-character-arc" in {f.code for f in rep.findings}
    assert "no-character-arc" not in critique.STORY_GATE_CODES


# ------------------------------ pacing model -----------------------------

def test_plan_adds_movements_and_dialogue_target() -> None:
    short = beats.plan(30)
    long = beats.plan(180)
    assert short["movements"] <= long["movements"]
    assert long["movements"] >= 3
    assert short["dialogue_target"] == 2          # floor
    assert long["dialogue_target"] >= 6           # 180s says more
    assert short["shot_target"] < long["shot_target"]
    # longer teasers use longer average shots (breathe, not strobe)
    assert long["avg_shot_s"] > short["avg_shot_s"]
    assert "turn" in long["structure"]


def test_plan_human_output_mentions_movements_and_turn() -> None:
    out = _run("teaser-plan", "--length", "180", "--format", "human")
    assert out.returncode == 0
    assert "movements" in out.stdout and "turn" in out.stdout


# ----------------------- render gate: quality (Phase 11) -----------------

def _story_complete(tmp_path: Path) -> Path:
    """A teaser that PASSES the structural story gate (full spine, dialogue,
    cards) — so only the new quality gate can block it."""
    t = {
        "title": "T", "length_s": 8, "provider": "veo",
        "spine": {"dramatic_question": "Q?", "logline": "L", "want": "w",
                  "opposing_force": "f", "emotional_arc": "a→b",
                  "score_direction": "s", "genre": "thriller", "turn": "it flips"},
        "shots": [
            {"id": "01", "role": "hook", "duration_s": 4,
             "subject": {"name": "J", "appearance": "x"}, "action": "a",
             "palette": ["amber"], "text_card": "A clerk.",
             "audio": {"dialogue": [{"speaker": "J", "line": "You owe me."}]}},
            {"id": "02", "role": "button", "duration_s": 4,
             "subject": {"name": "J", "appearance": "x"}, "action": "b",
             "palette": ["amber"], "text_card": "Coming.",
             "audio": {"dialogue": [{"speaker": "J", "line": "Not yet."}]}},
        ]}
    p = tmp_path / "teaser.json"
    p.write_text(json.dumps(t), encoding="utf-8")
    return p


def test_render_gate_blocks_story_complete_teaser_without_quality(tmp_path: Path) -> None:
    p = _story_complete(tmp_path)
    out = _run("teaser-render", str(p), "--provider", "veo", "--kind", "video",
               "--dry-run", "--format", "json")
    assert out.returncode == 0
    pay = json.loads(out.stdout)
    assert pay["narrative_gate_blocks"] is False   # structure is fine
    assert pay["quality_gate_blocks"] is True      # but not scored -> blocked
    assert pay["quality_gate_reasons"]


def test_render_gate_clears_with_passing_quality(tmp_path: Path) -> None:
    p = _story_complete(tmp_path)
    quality.dump(quality.QualityScore(scores=_full_scores()),
                 quality.quality_path(p))
    out = _run("teaser-render", str(p), "--provider", "veo", "--kind", "video",
               "--dry-run", "--format", "json")
    pay = json.loads(out.stdout)
    assert pay["quality_gate_blocks"] is False
    assert pay["quality_overall"] == 8.0


def test_render_gate_quality_blocks_on_low_score(tmp_path: Path) -> None:
    p = _story_complete(tmp_path)
    quality.dump(quality.QualityScore(scores=_full_scores(coherence=2)),
                 quality.quality_path(p))
    out = _run("teaser-render", str(p), "--provider", "veo", "--kind", "video",
               "--dry-run", "--format", "json")
    pay = json.loads(out.stdout)
    assert pay["quality_gate_blocks"] is True
    assert any("coherence" in r for r in pay["quality_gate_reasons"])


def test_render_gate_stub_exempt_from_quality(tmp_path: Path) -> None:
    p = _story_complete(tmp_path)  # no quality.json
    out = _run("teaser-render", str(p), "--provider", "stub", "--kind", "image",
               "--dry-run", "--format", "json")
    pay = json.loads(out.stdout)
    assert pay["quality_gate_blocks"] is False     # stub never quality-gated


def test_render_gate_skip_override_bypasses_quality(tmp_path: Path) -> None:
    p = _story_complete(tmp_path)  # no quality.json
    out = _run("teaser-render", str(p), "--provider", "veo", "--kind", "video",
               "--dry-run", "--format", "json", "--skip-narrative-gate")
    pay = json.loads(out.stdout)
    assert pay["quality_gate_blocks"] is False
