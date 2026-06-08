"""The teaser *interestingness* rubric + the HARD quality gate (Phase 11).

Phase 6 made a teaser *structurally* complete: it checks a spine block
exists, that there are dialogue lines and text cards, that the 4-act roles
are present and the stakes_level rises. That is a **floor, not quality** —
a teaser can satisfy every mechanical gate and still be a flat tour of
clips, because nothing checks whether the dramatic question is *sharp*, the
dialogue has *subtext*, the beats *actually escalate in felt stakes*, there
is a *turn*, the hook *grips*, or the button *teases*. **Presence ≠
interesting.**

This module is the data + gate for the quality half. The *scores* are
authored by the LLM judge in the ``teaser-critique`` command body (taste is
not mechanical — per ``feedback_avoid_brittle_python`` Python never judges
quality); this module only:

  - defines the eight scored dimensions (one rubric, one place),
  - round-trips ``teaser/quality.json`` (the persisted scorecard),
  - **computes the gate verdict** from the scores (overall ≥ 7 AND no
    single dimension < 5), so the render gate and the commands share one
    rule, and
  - reports the *weakest* dimensions so the de-boring revise pass knows
    what to lift.

No LLM, no network — pure data + arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json

# The eight interestingness dimensions (Phase 11). Each is scored 1-10 by
# the LLM judge. ``key`` is the JSON field; ``prompt`` is the question the
# judge answers — kept here so the rubric lives in exactly one place and the
# command body / docs can quote it verbatim.
DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("hook_grip",
     "Would a stranger keep watching after the first ~10 s? Does the opening "
     "image/line arrest, not merely establish?"),
    ("question_sharpness",
     "Is the dramatic question sharp and specific to THIS story — not a "
     "generic 'will they survive?' that fits any trailer?"),
    ("stakes_escalation",
     "Do the stakes rise beat to beat — specific, felt, and irreversible — "
     "or is it a montage of equals?"),
    ("character",
     "Do we learn who someone IS — what they want and what it costs them — "
     "or just see a recurring face?"),
    ("dialogue_quality",
     "Do the lines carry subtext and a distinct voice, with at least one "
     "quotable line — or are they filler/on-the-nose?"),
    ("surprise_turn",
     "Is there a genuine turn/reversal that re-frames the story — or does it "
     "go in a straight, predictable line?"),
    ("coherence",
     "Does it add up to ONE legible story a first-time viewer could follow, "
     "not disconnected pretty clips?"),
    ("button",
     "Does the ending withhold the resolution AND deepen the question so a "
     "viewer NEEDS the film — not a tidy, round-edged close?"),
)

DIMENSION_KEYS: tuple[str, ...] = tuple(k for k, _ in DIMENSIONS)

SCHEMA = "teaser-quality/1"

# Gate thresholds (Phase 11). A teaser is "interesting enough to spend a
# real render on" only when the overall score clears OVERALL_MIN *and* no
# single dimension is below DIM_MIN (one dead dimension sinks the teaser —
# a brilliant hook can't rescue dialogue nobody can stand).
OVERALL_MIN = 7.0
DIM_MIN = 5


@dataclass
class QualityScore:
    """An LLM-authored interestingness scorecard for a teaser.

    ``scores`` maps each dimension key → 1-10. ``notes`` is an optional
    per-dimension one-liner (why the score; what would lift it). Everything
    else (overall, verdict, weakest) is *computed* — never trust a persisted
    overall/verdict, recompute from ``scores`` so the gate can't be gamed by
    editing the verdict line.
    """

    scores: dict[str, int] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)

    # --- arithmetic (computed, never persisted as source of truth) ---
    def known_scores(self) -> dict[str, int]:
        """Only the recognised dimensions with an integer score."""
        out: dict[str, int] = {}
        for k in DIMENSION_KEYS:
            v = self.scores.get(k)
            if isinstance(v, bool):  # bool is an int subclass; reject it
                continue
            if isinstance(v, int):
                out[k] = v
        return out

    def overall(self) -> float:
        ks = self.known_scores()
        if not ks:
            return 0.0
        return round(sum(ks.values()) / len(ks), 2)

    def missing_dimensions(self) -> list[str]:
        """Rubric dimensions with no valid score yet (un-judged)."""
        ks = self.known_scores()
        return [k for k in DIMENSION_KEYS if k not in ks]

    def out_of_range(self) -> list[str]:
        return [k for k, v in self.known_scores().items() if not (1 <= v <= 10)]

    def low_dimensions(self, threshold: int = DIM_MIN) -> list[str]:
        """Dimensions scoring below ``threshold`` (in rubric order)."""
        ks = self.known_scores()
        return [k for k in DIMENSION_KEYS if k in ks and ks[k] < threshold]

    def weakest(self, k: int = 3) -> list[tuple[str, int]]:
        """The ``k`` lowest-scoring dimensions (worst first) — the targets
        for the adversarial de-boring revise pass."""
        ks = self.known_scores()
        ordered = sorted(ks.items(), key=lambda kv: (kv[1], DIMENSION_KEYS.index(kv[0])))
        return ordered[:k]

    def passes(self, *, overall_min: float = OVERALL_MIN,
               dim_min: int = DIM_MIN) -> bool:
        """True when the teaser clears the quality gate: fully scored, in
        range, overall ≥ ``overall_min``, no dimension < ``dim_min``."""
        if self.missing_dimensions() or self.out_of_range():
            return False
        return self.overall() >= overall_min and not self.low_dimensions(dim_min)

    def gate_reasons(self, *, overall_min: float = OVERALL_MIN,
                     dim_min: int = DIM_MIN) -> list[str]:
        """Human-readable reasons the gate fails (empty when it passes)."""
        reasons: list[str] = []
        miss = self.missing_dimensions()
        if miss:
            reasons.append(f"un-scored dimension(s): {', '.join(miss)}")
        bad = self.out_of_range()
        if bad:
            reasons.append(f"score(s) out of 1-10 range: {', '.join(bad)}")
        if not miss and not bad:
            ov = self.overall()
            if ov < overall_min:
                reasons.append(f"overall {ov:g} < {overall_min:g} (still boring overall)")
            low = self.low_dimensions(dim_min)
            if low:
                ks = self.known_scores()
                pretty = ", ".join(f"{k}={ks[k]}" for k in low)
                reasons.append(f"dead dimension(s) below {dim_min}: {pretty}")
        return reasons

    def verdict(self, **kw: Any) -> str:
        return "PASS" if self.passes(**kw) else "BLOCK"

    # --- I/O ---
    def to_dict(self) -> dict[str, Any]:
        # Persist the computed fields too (for human reading / the summary),
        # but ``from_dict`` recomputes them — ``scores`` is the only truth.
        return {
            "schema": SCHEMA,
            "overall": self.overall(),
            "verdict": self.verdict(),
            "scores": {k: self.scores[k] for k in self.scores},
            "notes": {k: self.notes[k] for k in self.notes},
            "weakest": [k for k, _ in self.weakest()],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "QualityScore":
        d = d or {}
        raw = d.get("scores") or {}
        scores: dict[str, int] = {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, bool):
                    continue
                if isinstance(v, int):
                    scores[str(k)] = v
                elif isinstance(v, float) and v.is_integer():
                    scores[str(k)] = int(v)
        notes_raw = d.get("notes") or {}
        notes = {str(k): str(v) for k, v in notes_raw.items()} if isinstance(notes_raw, dict) else {}
        return cls(scores=scores, notes=notes)


def load(path: Path) -> QualityScore:
    return QualityScore.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def dump(score: QualityScore, path: Path) -> None:
    Path(path).write_text(
        json.dumps(score.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def quality_path(teaser_json: Path) -> Path:
    """The scorecard sits next to ``teaser.json`` as ``quality.json``."""
    return Path(teaser_json).parent / "quality.json"


def blank_template() -> dict[str, Any]:
    """A scaffold the LLM judge fills in (all dimensions, 0 = un-scored)."""
    return {
        "schema": SCHEMA,
        "scores": {k: 0 for k in DIMENSION_KEYS},
        "notes": {k: "" for k in DIMENSION_KEYS},
    }
