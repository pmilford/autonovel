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

from autonovel.teaser import assemble, beats, critique, providers, quality
from autonovel.teaser.shots import Shot, Spine, Teaser


def _run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "autonovel.mechanical", *argv],
                          capture_output=True, text=True)


# ----------------------------- quality module ----------------------------

def _full_scores(**override: int) -> dict[str, int]:
    s = {k: 8 for k in quality.DIMENSION_KEYS}
    s.update(override)
    return s


def _passing(shot_ids=("01", "02"), **override: int) -> quality.QualityScore:
    """A fully-passing scorecard: strong dims AND a clean viewer-blind read
    (every scene legible + a stranger would watch) — the Phase-12 gate needs
    both halves."""
    return quality.QualityScore(
        scores=_full_scores(**override),
        legibility=[quality.SceneRead(shot_id=s, clear=True, who="the merchant",
                                      what="a choice", why="it matters") for s in shot_ids],
        viewer_takeaway="A stranger comes away wanting to watch the film.",
        would_watch=True, genre="historical fiction")


def test_quality_gate_passes_when_all_strong() -> None:
    s = _passing()
    assert s.passes()
    assert s.verdict() == "PASS"
    assert s.overall() == 8.0
    assert s.gate_reasons() == []


def test_strong_scores_alone_do_not_pass_without_legibility() -> None:
    # The core Phase-12 fix: a self-score with no viewer-blind read is NOT
    # trusted — exactly the hole that passed the boring Fugger teaser.
    s = quality.QualityScore(scores=_full_scores())
    assert not s.passes()
    assert any("legibility" in r for r in s.gate_reasons())


def test_illegible_scene_blocks_even_with_strong_scores() -> None:
    s = _passing()
    s.legibility[1].clear = False  # one scene a stranger can't read
    assert not s.passes()
    assert s.illegible_shots() == ["02"]
    assert any("illegible" in r for r in s.gate_reasons())


def test_would_not_watch_blocks() -> None:
    s = _passing()
    s.would_watch = False
    assert not s.passes()
    assert any("would_watch" in r for r in s.gate_reasons())


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
    quality.dump(_passing(), qp)
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
    short = beats.plan(30)            # default mode = short
    long = beats.plan(180)
    assert short["movements"] <= long["movements"]
    assert long["movements"] >= 3
    assert short["shot_target"] < long["shot_target"]
    # longer teasers use longer average shots (breathe, not strobe)
    assert long["avg_shot_s"] > short["avg_shot_s"]
    assert "turn" in long["structure"]
    # Phase 13: in SHORT mode dialogue is sparse (the VO spine carries it);
    # the in-scene-dialogue scaling now belongs to TRAILER mode.
    assert short["dialogue_target"] <= 3
    assert short["voiceover_target"] >= 4
    assert beats.plan(180, mode="trailer")["dialogue_target"] >= 6


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
    quality.dump(_passing(), quality.quality_path(p))
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


# ----------------- Phase 12: legibility / drama-over-mechanism ------------

def test_quality_v2_round_trips_legibility() -> None:
    s = _passing()
    s.legibility[0].who = "Jakob Fugger"
    d = s.to_dict()
    assert d["schema"] == "teaser-quality/2"
    s2 = quality.QualityScore.from_dict(d)
    assert s2.legibility[0].who == "Jakob Fugger"
    assert s2.would_watch is True and s2.passes()
    # a tampered would_watch can't be smuggled past a real illegible scene
    d["legibility"][0]["clear"] = False
    assert not quality.QualityScore.from_dict(d).passes()


def test_shot_identify_round_trips_and_is_omitted_when_empty() -> None:
    s = Shot(id="01", role="hook", subject_name="Jakob Fugger",
             subject_appearance="x", action="a",
             identify="Jakob Fugger — the richest man in Europe")
    assert "identify" in s.to_dict()
    assert Shot.from_dict(s.to_dict()).identify.startswith("Jakob Fugger")
    assert "identify" not in Shot(id="02", role="hook", subject_name="J",
                                  subject_appearance="x", action="a").to_dict()


def test_instrument_only_shot_flagged() -> None:
    t = Teaser(title="T", length_s=12, provider="veo", spine=Spine(genre="x"), shots=[
        Shot(id="01", role="hook", subject_name="Jakob Fugger",
             subject_appearance="x", action="stands", identify="Jakob Fugger — banker"),
        # an object shot with no person, no line, no identify → the horse
        Shot(id="02", role="escalation", subject_name="a riderless courier horse",
             subject_appearance="a horse", action="stands in the road"),
        Shot(id="03", role="button", subject_name="Jakob Fugger",
             subject_appearance="x", action="b"),
    ])
    codes = {f.code for f in critique.critique(t, providers.get("veo")).findings}
    assert "instrument-only-shot" in codes
    assert "instrument-only-shot" not in critique.STORY_GATE_CODES  # advisory


def test_unidentified_figure_flagged() -> None:
    t = Teaser(title="T", length_s=8, provider="veo", spine=Spine(genre="x"), shots=[
        Shot(id="01", role="hook", subject_name="Albrecht of Brandenburg",
             subject_appearance="an archbishop", action="signs"),  # never identified
        Shot(id="02", role="button", subject_name="Albrecht of Brandenburg",
             subject_appearance="an archbishop", action="leaves"),
    ])
    codes = {f.code for f in critique.critique(t, providers.get("veo")).findings}
    assert "unidentified-figure" in codes
    # giving the first appearance an identify clears it
    t.shots[0].identify = "Albrecht of Brandenburg — an archbishop who bought his office"
    codes2 = {f.code for f in critique.critique(t, providers.get("veo")).findings}
    assert "unidentified-figure" not in codes2


def test_identify_lower_third_burns_even_without_burn_titles(tmp_path: Path) -> None:
    ce = assemble.CutEntry(shot_id="01", clip="a.mp4", duration_s=4.0,
                           media="video",
                           identify="Jakob Fugger — the richest man in Europe")
    cl = assemble.CutList(title="T", entries=[ce], kind="video", burn_titles=False)
    cmd = " ".join(assemble.ffmpeg_command(cl, tmp_path / "out.mp4"))
    assert "drawtext" in cmd and "the richest man in Europe" in cmd
    # round-trips through the cut-list JSON
    assert assemble.CutEntry.from_dict(ce.to_dict()).identify == ce.identify


def test_build_cut_list_carries_identify(tmp_path: Path) -> None:
    cd = tmp_path / "clips"; cd.mkdir()
    (cd / "shot_01.mp4").write_bytes(b"x")
    t = Teaser(title="T", provider="veo", shots=[
        Shot(id="01", role="hook", subject_name="Jakob Fugger",
             subject_appearance="x", action="a",
             identify="Jakob Fugger — banker", duration_s=4.0)])
    result = assemble.build_cut_list(t, cd, kind="video")
    cl = result[0] if isinstance(result, tuple) else result
    assert cl.entries[0].identify == "Jakob Fugger — banker"


def test_cast_sprawl_collapses_age_ladder_and_ignores_objects() -> None:
    # A hero shown across a life (boy/man/elder) is ONE face, not three; and
    # object "subjects" never count as cast.
    t = Teaser(title="T", length_s=20, provider="veo", spine=Spine(genre="x"), shots=[
        Shot(id="01", role="hook", subject_name="Jakob Fugger (boy)",
             subject_appearance="x", action="a", identify="Jakob Fugger — banker"),
        Shot(id="02", role="escalation", subject_name="Jakob Fugger (man)",
             subject_appearance="y", action="b"),
        Shot(id="03", role="escalation", subject_name="Jakob Fugger (elder)",
             subject_appearance="z", action="c"),
        Shot(id="04", role="escalation", subject_name="the electoral map",
             subject_appearance="a map", action="unrolls"),
        Shot(id="05", role="button", subject_name="Jakob Fugger (elder)",
             subject_appearance="z", action="d"),
    ])
    codes = {f.code for f in critique.critique(t, providers.get("veo")).findings}
    assert "cast-sprawl" not in codes  # one hero (Jakob), the map doesn't count


def test_too_many_cards_flagged_not_thin() -> None:
    shots = [Shot(id=f"{i:02d}", role="escalation", subject_name="Jakob Fugger",
                  subject_appearance="x", action="a", text_card=f"card {i}",
                  identify="Jakob Fugger — banker") for i in range(6)]
    t = Teaser(title="T", length_s=24, provider="veo", spine=Spine(genre="x"), shots=shots)
    codes = {f.code for f in critique.critique(t, providers.get("veo")).findings}
    assert "too-many-cards" in codes
    assert "thin-text-cards" not in codes
