"""Beat-sheet structure + the teaser budget planner (mechanical).

A *beat* is one story turning point worth showing; the teaser arc is
hook → escalation → title → button (PRD §11, teaser-craft.md §8). This
module gives the ``teaser-beats`` command a deterministic budget — how
many beats/shots a given ``--length`` wants, and the per-role timing —
so the LLM works to a target instead of guessing. It does NOT pick the
beats (that's the creative LLM step); it bounds the count and shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import providers

ROLES = ("hook", "escalation", "title", "button")


@dataclass
class Beat:
    id: str
    role: str
    description: str  # the human-facing beat note
    source: str = ""  # where it came from (e.g. "outline: ch12 turn", "eval: peak tension")

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "role": self.role, "description": self.description, "source": self.source}


@dataclass
class BeatSheet:
    title: str
    length_s: int
    beats: list[Beat] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "length_s": self.length_s,
            "beats": [b.to_dict() for b in self.beats],
        }


# Teaser pacing model (teaser-craft.md §7-8). Phase 11 reworks it for
# *longer* runtimes: a 180 s piece is NOT 60×3 s of montage — it is a
# compressed story whose key beats (hook, turn, button) hold longer and
# whose escalation is grouped into a few **movements** that each build. The
# average shot therefore lengthens gently with the runtime instead of
# staying a flat ~3 s, so the cut breathes instead of strobing.
_HOOK_S = (4.0, 6.0)
_ESCALATION_CUT_S = (1.5, 2.5)
_TURN_HOLD_S = (3.0, 5.0)   # the midpoint reversal lands; let it land
_FINAL_HOLD_S = (3.0, 5.0)
_MIN_BEATS = 6
_MAX_BEATS = 20


def _avg_shot_s(length: int, cap: float) -> float:
    """Average shot length — ~3 s up to a minute, lengthening gently for
    longer teasers so the cut breathes (capped by the provider clip cap)."""
    base = 3.0 + max(0, length - 60) / 120.0   # 60s→3.0, 180s→4.0, 300s→5.0
    return round(min(base, cap), 2)


def _movements(length: int) -> int:
    """How many escalation *movements* (mini-builds) to group beats into —
    a longer teaser earns more movements, not just more clips (Phase 11)."""
    return max(2, min(4, 1 + round(length / 60)))


def _dialogue_target(length: int) -> int:
    """How many *loaded* dialogue lines a teaser of this length should mine
    (bp 5, Phase 11). ~1 per 20 s, floored at 2, capped at 10 — thin
    dialogue is the #1 felt failure, so longer teasers must say more."""
    return max(2, min(10, round(length / 20)))


def plan(length_s: int, provider: str = "generic") -> dict[str, Any]:
    """Recommend a beat/shot budget + per-role timing for a teaser.

    Pure function of (length, provider). Returned by ``teaser-plan`` and
    consumed by both teaser-beats and shot-prompts so the LLM hits a
    target. Never raises on odd input — clamps instead.
    """
    prof = providers.get(provider)
    length = max(10, int(length_s))
    # Shot budget from average teaser pacing, but no clip longer than the
    # provider's native cap.
    avg = _avg_shot_s(length, prof.max_clip_s)
    shot_target = max(4, round(length / avg))
    # Beats: roughly one per shot, but capped to a hand-authorable range;
    # a single beat can expand to several shots in shot-prompts.
    beat_target = max(_MIN_BEATS, min(_MAX_BEATS, round(length / 8)))
    hook_s = min(_HOOK_S[1], prof.max_clip_s)
    final_s = min(_FINAL_HOLD_S[1], prof.max_clip_s)
    return {
        "length_s": length,
        "provider": prof.name,
        "provider_clip_cap_s": prof.max_clip_s,
        "provider_native_audio": prof.audio,
        "beat_target": beat_target,
        "beat_range": [_MIN_BEATS, min(_MAX_BEATS, max(_MIN_BEATS, beat_target + 4))],
        "shot_target": shot_target,
        "avg_shot_s": avg,
        # Phase 11 storytelling targets (consumed by teaser-beats/shot-prompts):
        "movements": _movements(length),
        "dialogue_target": _dialogue_target(length),
        "structure": {
            "hook": {"shots": 1, "seconds_each": list(_clamp_range(_HOOK_S, prof.max_clip_s)),
                     "note": "one arresting opening image; intrigue, don't explain"},
            "escalation": {"seconds_each": list(_clamp_range(_ESCALATION_CUT_S, prof.max_clip_s)),
                           "movements": _movements(length),
                           "note": "group beats into movements; each movement builds "
                                   "to its own small peak, stakes rising across all of them"},
            "turn": {"seconds": list(_clamp_range(_TURN_HOLD_S, prof.max_clip_s)),
                     "placement": "~midpoint", "note": "the reversal — hold it; this is "
                     "what makes the cut a story, not a montage"},
            "title": {"placement": "~2/3 in", "note": "brand beat before the button"},
            "button": {"seconds": list(_clamp_range(_FINAL_HOLD_S, prof.max_clip_s)),
                       "note": "final hook AFTER the title; deepen the question, don't resolve it"},
        },
        "hook_seconds": hook_s,
        "final_hold_seconds": final_s,
    }


def _clamp_range(rng: tuple[float, float], cap: float) -> tuple[float, float]:
    return (min(rng[0], cap), min(rng[1], cap))
