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


# Teaser pacing model (teaser-craft.md §7): hook holds longer, the
# escalation cuts fast, the final image holds. Average ~3 s/shot.
_AVG_SHOT_S = 3.0
_HOOK_S = (4.0, 6.0)
_ESCALATION_CUT_S = (1.5, 2.5)
_FINAL_HOLD_S = (3.0, 5.0)
_MIN_BEATS = 6
_MAX_BEATS = 20


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
    avg = min(_AVG_SHOT_S, prof.max_clip_s)
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
        "avg_shot_s": round(avg, 2),
        "structure": {
            "hook": {"shots": 1, "seconds_each": list(_clamp_range(_HOOK_S, prof.max_clip_s)),
                     "note": "one arresting opening image; intrigue, don't explain"},
            "escalation": {"seconds_each": list(_clamp_range(_ESCALATION_CUT_S, prof.max_clip_s)),
                           "note": "accelerating cuts, rising stakes, intercut text cards"},
            "title": {"placement": "~2/3 in", "note": "brand beat before the button"},
            "button": {"seconds": list(_clamp_range(_FINAL_HOLD_S, prof.max_clip_s)),
                       "note": "final hook AFTER the title; deepen the question, don't resolve it"},
        },
        "hook_seconds": hook_s,
        "final_hold_seconds": final_s,
    }


def _clamp_range(rng: tuple[float, float], cap: float) -> tuple[float, float]:
    return (min(rng[0], cap), min(rng[1], cap))
