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


# Cheap candidate-generator for "this subject is an object, not a person"
# (Phase 12). NOT a quality gate — it only nudges; the LLM viewer-blind
# legibility read is the real judge (feedback_avoid_brittle_python).
_OBJECT_ARTICLES = ("a ", "an ", "the ")


def _looks_object_subject(name: str) -> bool:
    """Heuristic: a subject phrase that reads as a thing, not a person
    ("a ledger loss entry", "the electoral map", "seven wax seals"). A
    person named with a leading article is rare; a crowd is its own case."""
    n = name.strip().lower()
    if not n:
        return False
    if n.endswith(" crowd") or n.startswith("crowd"):
        return False
    return n.startswith(_OBJECT_ARTICLES) or n[:1].isdigit() or n.startswith("seven ")


def _base_person(name: str) -> str:
    """Strip an age/parenthetical qualifier so 'Jakob Fugger (boy)' and
    'Jakob Fugger (elder)' collapse to one figure for the identify check."""
    n = name.split("(")[0].strip()
    # drop a trailing "and a ..." companion clause
    n = n.split(" and ")[0].strip()
    return n


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

    # --- story spine (Phase 6 — narrative craft). A teaser must mean
    # something: pose a question, state a stake, let us hear the cast, and
    # carry the premise. These are the flags that catch a "set of clips
    # with no story" (advisory, like the rest — the LLM critic + the
    # command body treat them as must-fix). ---
    sp = teaser.spine
    if not sp.dramatic_question.strip():
        rep.add("", "no-dramatic-question",
                "no dramatic question — name the ONE question the teaser poses and "
                "never answers; every beat should advance or complicate it (bp 1)")
    if not sp.logline.strip():
        rep.add("", "no-logline",
                "no logline — write the one-sentence premise the text cards carry (bp 6)")
    if not sp.want.strip() or not sp.opposing_force.strip():
        rep.add("", "no-stakes",
                "no stated want + opposing force — surface what the protagonist wants "
                "and what stands in the way; conflict is the intrigue (bp 4)")
    if not sp.emotional_arc.strip():
        rep.add("", "no-emotional-arc",
                "no emotional arc — name the tonal journey (e.g. 'unease → dread → "
                "defiant hope') so the cut builds instead of idling (bp 8)")
    if not sp.genre.strip():
        rep.add("", "no-genre",
                "no genre/tone — name what KIND of story this is so the hook can "
                "telegraph it in the first ~10s (bp 9)")
    # Phase 11 — a teaser is a micro-story, not a montage: it needs ONE turn.
    if not sp.turn.strip():
        rep.add("", "no-turn",
                "no midpoint turn/reversal in the spine — name the ONE beat that "
                "flips the story (the moment the viewer's read of it turns over); "
                "without a turn the cut goes in a flat, predictable line (Phase 11)")

    # --- character development: show want AND cost, not just a face (Phase 11). ---
    cb = teaser.character_beat_kinds()
    if "want" not in cb or "cost" not in cb:
        miss = [k for k in ("want", "cost") if k not in cb]
        rep.add("", "no-character-arc",
                f"no shot tagged character_beat={'/'.join(miss)} — mark ≥1 beat "
                f"showing the protagonist's WANT and ≥1 showing the COST/change, so "
                f"the teaser earns a flicker of character, not just a recurring face "
                f"(Phase 11)")

    # --- dialogue + text cards carry the meaning (bp 5, bp 6). ---
    dlg = teaser.dialogue_line_count()
    if prof.audio and dlg < 2:
        rep.add("", "thin-dialogue",
                f"only {dlg} spoken line(s) on {prof.name} (native audio) — viewers "
                f"learn nothing about the story; mine 3-6 loaded lines from the "
                f"manuscript and assign them to shots (bp 5)")
    cards = teaser.text_card_count()
    # Phase 12: text cards are no longer required (a card slideshow is the
    # crutch that papers over illegible visuals — real shorts carry meaning
    # in spoken dialogue, not stacked cards). Flag the *crutch* instead: too
    # many cards. The title + at most ~1-2 (a button line) is plenty.
    n_shots = max(1, len(teaser.shots))
    if cards > 3 and cards > n_shots // 3:
        rep.add("", "too-many-cards",
                f"{cards} text cards across {n_shots} shots — that's a slideshow. "
                f"Carry the story in spoken dialogue + sparing VO and more "
                f"characters talking; reserve cards for the title and maybe one "
                f"button line (Phase 12)")

    # --- teaser-level arc + 4-act role order (bp 2). ---
    roles = [s.role for s in teaser.shots]
    if "hook" not in roles:
        rep.add("", "no-hook", "no shot with role 'hook' — the teaser needs an opener")
    elif roles[0] != "hook":
        rep.add("", "hook-not-first",
                "the 'hook' is not the first shot — the arresting image must open "
                "the teaser (bp 2)")
    if roles.count("hook") > 1:
        rep.add("", "multiple-hooks",
                f"{roles.count('hook')} 'hook' shots — a teaser has exactly one "
                f"opening hook (bp 2)")
    if "title" not in roles:
        rep.add("", "no-title",
                "no shot with role 'title' — place the brand/title beat ~2/3 in (bp 2)")
    if "button" not in roles:
        rep.add("", "no-button", "no shot with role 'button' — end on a hook after the title")
    elif roles[-1] != "button":
        rep.add("", "button-not-last",
                "the 'button' is not the final shot — the withholding stinger must "
                "close the teaser (bp 2, bp 7)")
    # title should land after the escalation and before the button (~2/3 in).
    if "title" in roles and "button" in roles:
        if roles.index("title") > len(roles) - 1 - roles[::-1].index("button"):
            rep.add("", "title-after-button",
                    "the title card lands after the button — title goes ~2/3 in, "
                    "then the button closes (bp 2)")

    # --- rising stakes ladder across the escalation (bp 3). ---
    esc = [s for s in teaser.shots if s.role == "escalation"]
    if esc:
        unranked = [s for s in esc if s.stakes_level is None]
        if unranked:
            rep.add("", "no-stakes-ladder",
                    f"{len(unranked)}/{len(esc)} escalation shots have no "
                    f"stakes_level — rank them so each beat raises the stakes over "
                    f"the last (a ladder, not a montage of equals) (bp 3)")
        else:
            levels = [s.stakes_level for s in esc]
            if any(b < a for a, b in zip(levels, levels[1:])):
                rep.add("", "stakes-not-rising",
                        f"escalation stakes_level dips ({levels}) — order the "
                        f"escalation so the stakes only rise (bp 3)")

    # --- drama over mechanism + legibility (Phase 12, advisory candidate
    # generators — the real enforcement is the LLM viewer-blind legibility
    # gate; these just surface the usual illegibility culprits cheaply). ---
    obj_shots = [s for s in teaser.shots
                 if s.role in ("hook", "escalation")
                 and _looks_object_subject(s.subject_name)
                 and not s.dialogue() and not s.identify.strip()]
    if obj_shots:
        ids = ", ".join(s.id for s in obj_shots)
        rep.add("", "instrument-only-shot",
                f"{len(obj_shots)} shot(s) ({ids}) look like OBJECT/instrument shots "
                f"(a ledger, a seal, a riderless horse) with no person acting and no "
                f"line — a stranger can't tell what they mean. Center a NAMED person "
                f"making a visible choice, or cut. Show the man buying the emperor, "
                f"not the wax (Phase 12)")
    # A named figure who never gets identified reads as a stranger in costume.
    person_names = {s.subject_name.strip() for s in teaser.shots
                    if s.subject_name.strip() and not _looks_object_subject(s.subject_name)}
    identified = {s.identify.split("—")[0].strip().lower()
                  for s in teaser.shots if s.identify.strip()}
    for name in sorted(person_names):
        base = _base_person(name)
        if base and not any(base.lower() in idf or idf in base.lower()
                            for idf in identified):
            rep.add("", "unidentified-figure",
                    f"{name!r} never gets an `identify` lower-third — a first-time "
                    f"viewer won't know who they are or why they matter. Give the "
                    f"first appearance a short 'Name — epithet' (e.g. 'Jakob Fugger "
                    f"— the richest man in Europe') (Phase 12)")

    # --- cast discipline: one hero face (bp 11) — count only real PEOPLE, so
    # object "subjects" (a ledger, seven seals) can't be rationalised as cast. ---
    names = {s.subject_name.strip() for s in teaser.shots
             if s.subject_name.strip() and not _looks_object_subject(s.subject_name)}
    if len(names) > 3:
        rep.add("", "cast-sprawl",
                f"{len(names)} named faces ({', '.join(sorted(names))}) — a teaser "
                f"sells ONE hero's stakes; keep ≤3 named faces and make the rest "
                f"silhouettes/crowd (no consistency lock needed) (bp 11)")

    total = teaser.total_duration_s()
    if teaser.length_s and abs(total - teaser.length_s) > max(8.0, 0.25 * teaser.length_s):
        rep.add("", "length-mismatch",
                f"shots total {total:g}s vs target {teaser.length_s}s — add/trim shots")
    return rep


# Finding codes that BLOCK a real render (Phase 6 narrative gate, bp 12):
# their presence means the teaser has no story yet, so spending a real
# generation would be wasted. Ordering/ladder/cast flags stay advisory (a
# deliberate artistic choice shouldn't hard-block a render); the offline
# `stub` backend is exempt from the gate entirely.
# NOTE (Phase 12): `thin-text-cards` was removed from the gate — requiring
# ≥2 cards pushed teasers toward a card slideshow (the crutch that papers
# over illegible visuals). Meaning now rides spoken dialogue; legibility is
# enforced by the LLM viewer-blind QUALITY gate (teaser/quality.py), not by
# counting cards.
STORY_GATE_CODES = (
    "no-dramatic-question", "no-logline", "no-stakes", "no-emotional-arc",
    "no-genre", "thin-dialogue", "no-hook", "no-button",
)


def story_gate_failures(report: Report) -> list[Finding]:
    """The blocking narrative-gate findings in ``report`` (bp 12)."""
    return [f for f in report.findings if f.code in STORY_GATE_CODES]


def story_ready(report: Report) -> bool:
    """True when no blocking narrative-gate finding is present (bp 12)."""
    return not story_gate_failures(report)
