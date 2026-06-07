"""The per-shot schema + ``teaser.json`` I/O (mechanical; PRD §8).

A ``Shot`` is the unit a video model renders: one framing, one camera
move, one subject action. A ``Teaser`` is an ordered list of shots plus
the teaser-level metadata. The LLM (in the command body) fills these
structured fields; this module validates the *structure* and round-trips
``teaser.json``. Quality ("is this a good shot?") is judged by the
LLM/vision critic, never here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import providers

ROLES = ("hook", "escalation", "title", "button")


@dataclass
class Spine:
    """The teaser's story spine (Phase 6 — narrative craft).

    A teaser sells a *tone and a question*, not a tour of scenes. These
    fields are the throughline that the per-shot beats must serve, so a
    re-reader (and the critique) can check the teaser actually means
    something. The LLM authors them in ``teaser-beats`` / ``shot-prompts``;
    this module only round-trips the structure (never judges the wording).

    - ``dramatic_question`` — the ONE question the teaser poses and never
      answers (best-practice 1). Every beat advances or complicates it.
    - ``logline`` — the one-sentence premise the text cards carry (bp 6).
    - ``want`` / ``opposing_force`` — what the protagonist wants and what
      stands in the way; conflict is what makes a teaser intriguing (bp 4).
    - ``emotional_arc`` — the tonal journey, e.g. ``"unease → dread →
      defiant hope"`` (bp 8).
    - ``score_direction`` — the musical/tonal spine for the bed/score the
      whole cut rides (bp 8).
    - ``genre`` — the genre/tone the hook must telegraph in the first
      ~10 s so a viewer knows what *kind* of story this is (bp 9).
    """

    dramatic_question: str = ""
    logline: str = ""
    want: str = ""
    opposing_force: str = ""
    emotional_arc: str = ""
    score_direction: str = ""
    genre: str = ""

    def is_empty(self) -> bool:
        return not any(
            (self.dramatic_question, self.logline, self.want,
             self.opposing_force, self.emotional_arc, self.score_direction,
             self.genre)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dramatic_question": self.dramatic_question,
            "logline": self.logline,
            "want": self.want,
            "opposing_force": self.opposing_force,
            "emotional_arc": self.emotional_arc,
            "score_direction": self.score_direction,
            "genre": self.genre,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "Spine":
        d = d or {}
        return cls(
            dramatic_question=str(d.get("dramatic_question", "") or ""),
            logline=str(d.get("logline", "") or ""),
            want=str(d.get("want", "") or ""),
            opposing_force=str(d.get("opposing_force", "") or ""),
            emotional_arc=str(d.get("emotional_arc", "") or ""),
            score_direction=str(d.get("score_direction", "") or ""),
            genre=str(d.get("genre", "") or ""),
        )


@dataclass
class Shot:
    id: str
    role: str = "escalation"
    duration_s: float = 4.0
    aspect_ratio: str = "16:9"
    shot_size: str = ""
    camera_angle: str = ""
    subject_name: str = ""
    subject_appearance: str = ""
    action: str = ""
    setting: str = ""
    lighting: str = ""
    palette: list[str] = field(default_factory=list)
    camera_movement: str = ""
    lens: str = ""
    style: str = ""
    mood: str = ""
    # audio: {"ambience": str, "sfx": str, "dialogue": [{"speaker","line"}]}
    audio: dict[str, Any] = field(default_factory=dict)
    negative_prompt: str = ""
    reference_image: str | None = None
    last_frame: str | None = None
    seed: int | None = None
    text_card: str | None = None
    # In-story year of this shot (Phase 5.6) — drives auto voice-aging:
    # a character's age variant is picked from this year. Optional.
    story_year: int | None = None
    # Rising-stakes rank within the escalation (Phase 6, bp 3). The LLM
    # assigns an increasing integer to escalation shots so the teaser is a
    # ladder, not a montage of equals; ``critique`` checks monotonicity.
    # Optional — None means "not ranked" (flagged for escalation shots).
    stakes_level: int | None = None
    # Human-facing one-line beat note (the dual-render pair; PRD §18.2).
    beat_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "role": self.role,
            "duration_s": self.duration_s,
            "aspect_ratio": self.aspect_ratio,
            "shot_size": self.shot_size,
            "camera_angle": self.camera_angle,
            "subject": {"name": self.subject_name, "appearance": self.subject_appearance},
            "action": self.action,
            "setting": self.setting,
            "lighting": self.lighting,
            "palette": list(self.palette),
            "camera_movement": self.camera_movement,
            "lens": self.lens,
            "style": self.style,
            "mood": self.mood,
            "audio": dict(self.audio),
            "negative_prompt": self.negative_prompt,
        }
        if self.reference_image is not None:
            d["reference_image"] = self.reference_image
        if self.last_frame is not None:
            d["last_frame"] = self.last_frame
        if self.seed is not None:
            d["seed"] = self.seed
        if self.text_card is not None:
            d["text_card"] = self.text_card
        if self.story_year is not None:
            d["story_year"] = self.story_year
        if self.stakes_level is not None:
            d["stakes_level"] = self.stakes_level
        if self.beat_note:
            d["beat_note"] = self.beat_note
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Shot":
        subject = d.get("subject") or {}
        return cls(
            id=str(d.get("id", "")),
            role=d.get("role", "escalation"),
            duration_s=float(d.get("duration_s", 4.0)),
            aspect_ratio=d.get("aspect_ratio", "16:9"),
            shot_size=d.get("shot_size", ""),
            camera_angle=d.get("camera_angle", ""),
            subject_name=subject.get("name", ""),
            subject_appearance=subject.get("appearance", ""),
            action=d.get("action", ""),
            setting=d.get("setting", ""),
            lighting=d.get("lighting", ""),
            palette=list(d.get("palette") or []),
            camera_movement=d.get("camera_movement", ""),
            lens=d.get("lens", ""),
            style=d.get("style", ""),
            mood=d.get("mood", ""),
            audio=dict(d.get("audio") or {}),
            negative_prompt=d.get("negative_prompt", ""),
            reference_image=d.get("reference_image"),
            last_frame=d.get("last_frame"),
            seed=d.get("seed"),
            text_card=d.get("text_card"),
            story_year=d.get("story_year"),
            stakes_level=d.get("stakes_level"),
            beat_note=d.get("beat_note", ""),
        )

    def dialogue(self) -> list[dict[str, str]]:
        d = self.audio.get("dialogue") or []
        return d if isinstance(d, list) else []


@dataclass
class Teaser:
    title: str
    length_s: int = 90
    provider: str = "generic"
    spine: Spine = field(default_factory=Spine)
    shots: list[Shot] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "title": self.title,
            "length_s": self.length_s,
            "provider": self.provider,
        }
        # Omit the spine block entirely when empty so existing teasers
        # round-trip byte-identical (additive; nothing breaks).
        if not self.spine.is_empty():
            d["spine"] = self.spine.to_dict()
        d["shots"] = [s.to_dict() for s in self.shots]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Teaser":
        return cls(
            title=str(d.get("title", "")),
            length_s=int(d.get("length_s", 90)),
            provider=d.get("provider", "generic"),
            spine=Spine.from_dict(d.get("spine")),
            shots=[Shot.from_dict(s) for s in (d.get("shots") or [])],
        )

    def total_duration_s(self) -> float:
        return sum(s.duration_s for s in self.shots)

    def dialogue_line_count(self) -> int:
        """Total spoken dialogue lines across all shots (bp 5)."""
        return sum(len(s.dialogue()) for s in self.shots)

    def text_card_count(self) -> int:
        """Number of shots that carry a text card (bp 6)."""
        return sum(1 for s in self.shots if (s.text_card or "").strip())


def load(path: Path) -> Teaser:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(
            "teaser.json top level must be a JSON object "
            '{"title", "length_s", "provider", "shots":[...]}'
        )
    return Teaser.from_dict(data)


def dump(teaser: Teaser, path: Path) -> None:
    Path(path).write_text(
        json.dumps(teaser.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def validate(teaser: Teaser, provider: providers.ProviderProfile | None = None) -> list[str]:
    """Return a list of *hard* structural problems (empty == valid).

    Structural only — completeness/quality advisories live in
    ``critique`` so a draft still validates while the critic nudges it.
    """
    prof = provider or providers.get(teaser.provider)
    problems: list[str] = []
    if not teaser.title:
        problems.append("teaser title is empty")
    if not teaser.shots:
        problems.append("teaser has no shots")
    seen: set[str] = set()
    for i, s in enumerate(teaser.shots):
        tag = s.id or f"shot[{i}]"
        if not s.id:
            problems.append(f"{tag}: missing id")
        elif s.id in seen:
            problems.append(f"{tag}: duplicate id")
        seen.add(s.id)
        if s.role not in ROLES:
            problems.append(f"{tag}: role {s.role!r} not in {ROLES}")
        if not isinstance(s.duration_s, (int, float)) or s.duration_s <= 0:
            problems.append(f"{tag}: duration_s must be a positive number")
        elif s.duration_s > prof.max_clip_s:
            problems.append(
                f"{tag}: duration {s.duration_s}s exceeds {prof.name} native cap "
                f"{prof.max_clip_s}s"
            )
        if not s.subject_name:
            problems.append(f"{tag}: subject.name is empty (consistency needs a named subject)")
        if not s.subject_appearance:
            problems.append(f"{tag}: subject.appearance is empty")
        if not s.action:
            problems.append(f"{tag}: action is empty")
        if not isinstance(s.palette, list):
            problems.append(f"{tag}: palette must be a list")
        if not isinstance(s.negative_prompt, str):
            problems.append(f"{tag}: negative_prompt must be a string (separate field)")
        if not isinstance(s.audio, dict):
            problems.append(f"{tag}: audio must be an object")
        else:
            dlg = s.audio.get("dialogue")
            if dlg is not None and not isinstance(dlg, list):
                problems.append(f"{tag}: audio.dialogue must be a list of {{speaker,line}}")
    return problems
