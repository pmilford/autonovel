"""Mechanical pre-generation critique of a teaser (PRD §24.2).

This is the *structural* half of the self-critique: cheap, deterministic
checks that catch problems before a single clip is generated. The
*quality* half ("is this prompt good / on-brief / consistent in spirit?")
is the LLM critic in the ``shot-prompts`` command body — this module
never judges taste, only mechanics. Per ``feedback_avoid_brittle_python``,
findings are advisory FLAGs, not hard failures (use ``shots.validate``
for hard structural errors).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import providers
from .shots import Teaser

# Recommended fields whose absence weakens a shot but isn't invalid.
_RECOMMENDED = ("shot_size", "camera_movement", "lighting", "style", "mood")


@dataclass
class Finding:
    shot_id: str        # "" for teaser-level findings
    level: str          # "FLAG"
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"shot_id": self.shot_id, "level": self.level, "code": self.code, "message": self.message}


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def add(self, shot_id: str, code: str, message: str) -> None:
        self.findings.append(Finding(shot_id, "FLAG", code, message))

    def to_dict(self) -> dict[str, Any]:
        return {
            "flag_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
        }


def _looks_multi_action(action: str) -> bool:
    """Soft heuristic for >1 action in a clip (advisory only)."""
    a = action.strip()
    if " and then " in a.lower():
        return True
    # More than one sentence-ending punctuation followed by a capitalised word.
    import re
    return len(re.findall(r"[.!?]\s+[A-Z]", a)) >= 1


def critique(teaser: Teaser, provider: providers.ProviderProfile | None = None) -> Report:
    prof = provider or providers.get(teaser.provider)
    rep = Report()

    # --- consistency: a named subject must use ONE appearance string. ---
    appearances: dict[str, set[str]] = {}
    for s in teaser.shots:
        if s.subject_name and s.subject_appearance:
            appearances.setdefault(s.subject_name, set()).add(s.subject_appearance.strip())
    for name, variants in appearances.items():
        if len(variants) > 1:
            rep.add("", "appearance-drift",
                    f"{name!r} has {len(variants)} different appearance descriptions across "
                    f"shots — reuse ONE verbatim string for consistency (PRD §10).")

    # --- per-shot advisories. ---
    for s in teaser.shots:
        missing = [f for f in _RECOMMENDED if not getattr(s, f)]
        if missing:
            rep.add(s.id, "thin-prompt",
                    f"missing recommended fields: {', '.join(missing)}")
        if not s.palette:
            rep.add(s.id, "no-palette",
                    "no colour palette — name 3-5 anchors and hold them across shots")
        if not s.reference_image and s.subject_name:
            rep.add(s.id, "no-reference",
                    f"no reference_image for {s.subject_name} — identity will drift without one")
        if _looks_multi_action(s.action):
            rep.add(s.id, "multi-action",
                    "action may contain more than one action/sentence — one action per clip")
        # audio cue but provider can't do audio
        has_audio_cue = bool(s.audio.get("dialogue") or s.audio.get("sfx") or s.audio.get("ambience"))
        if has_audio_cue and not prof.audio:
            rep.add(s.id, "audio-unsupported",
                    f"{prof.name} has no native audio — score this in post, not in the clip")
        if s.negative_prompt and not prof.separate_negative:
            rep.add(s.id, "negative-unsupported",
                    f"{prof.name} has no separate negative-prompt field — lean on positive "
                    f"prompting + references instead")

    # --- teaser-level arc + length. ---
    roles = [s.role for s in teaser.shots]
    if "hook" not in roles:
        rep.add("", "no-hook", "no shot with role 'hook' — the teaser needs an opener")
    if "button" not in roles:
        rep.add("", "no-button", "no shot with role 'button' — end on a hook after the title")
    total = teaser.total_duration_s()
    if teaser.length_s and abs(total - teaser.length_s) > max(8.0, 0.25 * teaser.length_s):
        rep.add("", "length-mismatch",
                f"shots total {total:g}s vs target {teaser.length_s}s — add/trim shots")
    return rep
