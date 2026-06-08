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
    single dimension < 5) AND the **viewer-blind legibility read** (every
    scene must be legible to a first-time viewer; the teaser must read as
    something a stranger would want to watch), so the render gate and the
    commands share one rule, and
  - reports the *weakest* dimensions so the de-boring revise pass knows
    what to lift.

**Why the legibility read exists (Phase 12).** A self-scored rubric is
gameable: the *same model* that wrote the teaser scores it, and it can see
its own intent (the spine, the beat notes, the character names) — so it
grades the *script* it meant, not the *experience* a stranger gets, and
passes itself with eloquent 8s while the rendered teaser is an illegible
tour of objects (a ledger, a riderless horse, seven wax seals). The fix is
an **external, viewer-blind** judgement: the ``teaser-critique`` command
builds, per shot, only what a stranger actually perceives (the visible
action + the spoken line + any on-screen text — the names/spine/beat-notes
*hidden*), asks a skeptic first-time viewer "who / what / why?", and records
whether each scene is ``clear``. The gate blocks on any illegible scene and
on a teaser a stranger wouldn't want to watch. This module only validates
that read and applies the rule — the judging is the LLM's (taste and a
viewer's eye are never mechanical).

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

SCHEMA = "teaser-quality/2"

# Gate thresholds (Phase 11). A teaser is "interesting enough to spend a
# real render on" only when the overall score clears OVERALL_MIN *and* no
# single dimension is below DIM_MIN (one dead dimension sinks the teaser —
# a brilliant hook can't rescue dialogue nobody can stand).
OVERALL_MIN = 7.0
DIM_MIN = 5


@dataclass
class SceneRead:
    """One scene's *viewer-blind* legibility read (Phase 12). Authored by the
    skeptic first-time-viewer judge from ONLY what a stranger perceives
    (visible action + spoken line + on-screen text — names/spine/beat-notes
    hidden). ``clear`` is the gate-bearing field: can a first-timer tell what
    this scene is and why it matters? ``who``/``what``/``why`` record the
    judge's actual read (empty/"can't tell" when ``clear`` is False)."""

    shot_id: str
    clear: bool = False
    who: str = ""
    what: str = ""
    why: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"shot_id": self.shot_id, "clear": bool(self.clear),
                "who": self.who, "what": self.what, "why": self.why,
                "note": self.note}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SceneRead":
        return cls(
            shot_id=str(d.get("shot_id", "")),
            clear=bool(d.get("clear", False)),
            who=str(d.get("who", "") or ""),
            what=str(d.get("what", "") or ""),
            why=str(d.get("why", "") or ""),
            note=str(d.get("note", "") or ""),
        )


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
    # Phase 12 — the viewer-blind layer (the un-gameable part of the gate):
    legibility: list[SceneRead] = field(default_factory=list)
    viewer_takeaway: str = ""      # "a stranger comes away thinking: ___"
    would_watch: bool | None = None  # would that stranger want the film?
    genre: str = ""                # the genre the teaser was judged in (audit)

    # --- arithmetic (computed, never persisted as source of truth) ---
    def illegible_shots(self) -> list[str]:
        """Shot ids the first-time-viewer judge could NOT read (gate-blocking)."""
        return [r.shot_id for r in self.legibility if not r.clear]
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
        range, overall ≥ ``overall_min``, no dimension < ``dim_min``, AND the
        viewer-blind read is present, every scene legible, and a stranger
        would want to watch (Phase 12 — the un-gameable half)."""
        if self.missing_dimensions() or self.out_of_range():
            return False
        if self.overall() < overall_min or self.low_dimensions(dim_min):
            return False
        # Viewer-blind legibility (the un-gameable half): a self-score alone
        # is not enough — require an external first-time-viewer read where
        # every scene is legible and the takeaway makes a stranger want it.
        if not self.legibility:
            return False
        if self.illegible_shots():
            return False
        if self.would_watch is not True:
            return False
        if not self.viewer_takeaway.strip():
            return False
        return True

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
        # Viewer-blind layer (Phase 12).
        if not self.legibility:
            reasons.append("no viewer-blind legibility read — re-score with "
                           "teaser-critique (a self-score alone is not trusted)")
        else:
            bad_scenes = self.illegible_shots()
            if bad_scenes:
                reasons.append(f"illegible to a first-time viewer: shot(s) "
                               f"{', '.join(bad_scenes)} (a stranger can't tell "
                               f"who/what/why — show people + identify them, not objects)")
            if self.would_watch is not True:
                reasons.append("would_watch is not true — a stranger would not "
                               "want the film from this teaser")
            if not self.viewer_takeaway.strip():
                reasons.append("no viewer_takeaway — state what a stranger comes "
                               "away believing")
        return reasons

    def verdict(self, **kw: Any) -> str:
        return "PASS" if self.passes(**kw) else "BLOCK"

    # --- I/O ---
    def to_dict(self) -> dict[str, Any]:
        # Persist the computed fields too (for human reading / the summary),
        # but ``from_dict`` recomputes them — ``scores`` + ``legibility`` are
        # the only truth.
        return {
            "schema": SCHEMA,
            "genre": self.genre,
            "overall": self.overall(),
            "verdict": self.verdict(),
            "scores": {k: self.scores[k] for k in self.scores},
            "notes": {k: self.notes[k] for k in self.notes},
            "legibility": [r.to_dict() for r in self.legibility],
            "illegible_shots": self.illegible_shots(),
            "viewer_takeaway": self.viewer_takeaway,
            "would_watch": self.would_watch,
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
        leg_raw = d.get("legibility") or []
        legibility = [SceneRead.from_dict(r) for r in leg_raw
                      if isinstance(r, dict)] if isinstance(leg_raw, list) else []
        ww = d.get("would_watch")
        would_watch = ww if isinstance(ww, bool) else None
        return cls(scores=scores, notes=notes, legibility=legibility,
                   viewer_takeaway=str(d.get("viewer_takeaway", "") or ""),
                   would_watch=would_watch, genre=str(d.get("genre", "") or ""))


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
    """A scaffold the LLM judge fills in (all dimensions, 0 = un-scored, plus
    the viewer-blind legibility read the gate requires)."""
    return {
        "schema": SCHEMA,
        "genre": "",
        "scores": {k: 0 for k in DIMENSION_KEYS},
        "notes": {k: "" for k in DIMENSION_KEYS},
        "legibility": [
            {"shot_id": "<id>", "clear": False, "who": "", "what": "",
             "why": "", "note": "judged from on-screen action + spoken line + "
             "card ONLY; names/spine/beat-notes hidden"},
        ],
        "viewer_takeaway": "",
        "would_watch": False,
    }
