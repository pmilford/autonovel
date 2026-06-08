"""Tier-1 tests: /autonovel:next is teaser-aware (2026-06-07).

`next` only knew the chapter pipeline; now it surfaces the teaser flow's next
step when a teaser is in progress (beats → shots → render gate → render →
assemble), and stays silent for books not making one.
"""

from __future__ import annotations

import json
from pathlib import Path

from autonovel.housekeeping.next_actions import _teaser_actions
from autonovel.teaser import quality as quality_mod
from autonovel.teaser import shots as shots_mod
from autonovel.teaser.shots import Shot, Spine, Teaser


def _pass_quality(root: Path) -> None:
    """Write a passing quality.json so a story-complete teaser clears the
    quality gate too (reaches render/assemble steps) — needs the Phase-12
    viewer-blind read, not just strong scores."""
    quality_mod.dump(
        quality_mod.QualityScore(
            scores={k: 8 for k in quality_mod.DIMENSION_KEYS},
            legibility=[quality_mod.SceneRead(shot_id=s, clear=True, who="x",
                                              what="y", why="z") for s in ("01", "02")],
            viewer_takeaway="A stranger wants the film.", would_watch=True),
        root / "teaser" / "quality.json")


def _book(tmp_path: Path) -> Path:
    root = tmp_path / "books" / "b"
    (root / "teaser").mkdir(parents=True)
    return root


def _ready_teaser() -> Teaser:
    sp = Spine(dramatic_question="Q?", logline="L", want="w", opposing_force="f",
               emotional_arc="a→b", score_direction="s", genre="thriller")
    return Teaser(title="T", length_s=12, provider="veo", spine=sp, shots=[
        Shot(id="01", role="hook", subject_name="J", subject_appearance="x",
             action="a", palette=["amber"], text_card="open",
             audio={"dialogue": [{"speaker": "J", "line": "one"}]}),
        Shot(id="02", role="button", subject_name="J", subject_appearance="x",
             action="b", palette=["amber"], text_card="close",
             audio={"dialogue": [{"speaker": "J", "line": "two"}]}),
    ])


def test_no_teaser_dir_silent(tmp_path: Path) -> None:
    root = tmp_path / "books" / "b"
    root.mkdir(parents=True)
    assert _teaser_actions(root, "b") == []


def test_empty_teaser_dir_silent(tmp_path: Path) -> None:
    root = _book(tmp_path)
    assert _teaser_actions(root, "b") == []  # dir but nothing started


def test_brief_only_points_at_beats(tmp_path: Path) -> None:
    root = _book(tmp_path)
    (root / "teaser" / "brief.md").write_text("# brief", encoding="utf-8")
    acts = _teaser_actions(root, "b")
    assert len(acts) == 1 and "teaser-beats" in acts[0].command


def test_beats_only_points_at_shot_prompts(tmp_path: Path) -> None:
    root = _book(tmp_path)
    (root / "teaser" / "beats.md").write_text("# beats", encoding="utf-8")
    acts = _teaser_actions(root, "b")
    assert len(acts) == 1 and "shot-prompts" in acts[0].command


def test_blocked_gate_points_at_revise(tmp_path: Path) -> None:
    root = _book(tmp_path)
    # teaser.json with NO spine → story gate blocked
    (root / "teaser" / "teaser.json").write_text(json.dumps({
        "title": "T", "provider": "veo", "shots": [
            {"id": "01", "role": "hook", "duration_s": 4,
             "subject": {"name": "J", "appearance": "x"}, "action": "a"}]}),
        encoding="utf-8")
    acts = _teaser_actions(root, "b")
    assert len(acts) == 1 and "teaser-revise" in acts[0].command
    assert acts[0].priority == "MEDIUM"


def test_story_complete_but_unscored_points_at_critique(tmp_path: Path) -> None:
    # Phase 11: story gate passes but no quality.json yet → score it first.
    root = _book(tmp_path)
    shots_mod.dump(_ready_teaser(), root / "teaser" / "teaser.json")
    acts = _teaser_actions(root, "b")
    assert len(acts) == 1 and "teaser-critique" in acts[0].command


def test_quality_blocked_points_at_revise(tmp_path: Path) -> None:
    # Phase 11: scored but below the bar → de-boring revise.
    root = _book(tmp_path)
    shots_mod.dump(_ready_teaser(), root / "teaser" / "teaser.json")
    quality_mod.dump(
        quality_mod.QualityScore(scores={**{k: 8 for k in quality_mod.DIMENSION_KEYS},
                                         "dialogue_quality": 2}),
        root / "teaser" / "quality.json")
    acts = _teaser_actions(root, "b")
    assert len(acts) == 1 and "teaser-revise" in acts[0].command


def test_ready_no_clips_points_at_render(tmp_path: Path) -> None:
    root = _book(tmp_path)
    shots_mod.dump(_ready_teaser(), root / "teaser" / "teaser.json")
    _pass_quality(root)
    acts = _teaser_actions(root, "b")
    assert len(acts) == 1 and "teaser-render" in acts[0].command


def test_clips_present_points_at_assemble(tmp_path: Path) -> None:
    root = _book(tmp_path)
    shots_mod.dump(_ready_teaser(), root / "teaser" / "teaser.json")
    _pass_quality(root)
    clips = root / "teaser" / "clips"
    clips.mkdir()
    (clips / "shot_01.png").write_bytes(b"\x89PNG")
    acts = _teaser_actions(root, "b")
    assert len(acts) == 1 and "teaser-assemble" in acts[0].command


def test_assembled_cut_is_silent(tmp_path: Path) -> None:
    root = _book(tmp_path)
    shots_mod.dump(_ready_teaser(), root / "teaser" / "teaser.json")
    (root / "teaser" / "t_teaser_latest.mp4").write_bytes(b"\x00")
    assert _teaser_actions(root, "b") == []  # done
