"""Render a structured ``Shot`` into provider-ready prompt prose (PRD §8).

The LLM fills the structured fields; this module assembles them into the
canonical Veo/Sora field order so the wording/ordering is deterministic
and consistent across shots. This is a **format translation**, not a
quality judgement — each provider's UI/API wants the same facts in a
different shape (``feedback_avoid_brittle_python``: deterministic
assembly, no word-lists, unknown values pass through verbatim).

Dialects (keyed off ``providers.ProviderProfile.dialect``):

- ``generic`` / ``veo`` / ``sora`` (and pollinations, kling) — one rich
  **prose** paragraph in canonical order. Veo/Sora are trained on natural
  language; this is their native shape.
- ``runway`` — **terse**, comma-separated keyword phrases. Runway Gen-4
  prefers compact descriptive tags over long prose.
- ``luma`` — **enum**: concise description plus the camera move mapped to
  Luma Dream Machine's enumerated motion control.

``render_visual(shot, provider)`` is the dispatcher; unknown dialects
fall back to prose.
"""

from __future__ import annotations

from . import providers
from .shots import Shot

# Canonical field order, shared by every dialect (PRD §8).
# (label, accessor) — accessor returns the rendered fragment or "".


def _framing(shot: Shot) -> str:
    return ", ".join(p for p in (shot.shot_size, shot.camera_angle) if p)


def _subject(shot: Shot) -> str:
    subj = shot.subject_name.upper() if shot.subject_name else ""
    if subj and shot.subject_appearance:
        return f"{subj} ({shot.subject_appearance})"
    return subj


def _palette(shot: Shot, joiner: str = ", ") -> str:
    return (joiner.join(shot.palette) + " palette") if shot.palette else ""


def render_prose(shot: Shot) -> str:
    """The visual prompt as one paragraph, in canonical order:
    framing → subject+appearance → action → setting → lighting →
    palette → camera move → lens → style → mood."""
    parts: list[str] = []
    framing = _framing(shot)
    if framing:
        parts.append(framing.capitalize() + ".")
    subj = _subject(shot)
    if subj:
        parts.append(subj)
    if shot.action:
        parts.append(shot.action.rstrip("."))
    if shot.setting:
        parts.append(shot.setting)
    if shot.lighting:
        parts.append(shot.lighting)
    if shot.palette:
        parts.append(", ".join(shot.palette) + " palette")
    if shot.camera_movement:
        parts.append(shot.camera_movement)
    if shot.lens:
        parts.append(shot.lens)
    if shot.style:
        parts.append(shot.style)
    if shot.mood:
        parts.append(shot.mood)
    # Join with ". " but avoid doubling separators.
    text = ". ".join(p.rstrip(". ") for p in parts if p)
    return (text + ".") if text and not text.endswith(".") else text


def render_terse(shot: Shot) -> str:
    """Comma-separated keyword phrases (Runway Gen-4 dialect). Same
    canonical order as prose; no sentences, no trailing periods."""
    frags = [
        _framing(shot),
        _subject(shot),
        shot.action.rstrip("."),
        shot.setting,
        shot.lighting,
        _palette(shot, joiner="/"),
        shot.camera_movement,
        shot.lens,
        shot.style,
        shot.mood,
    ]
    return ", ".join(f.strip() for f in frags if f and f.strip())


# Luma Dream Machine exposes camera motion as an enumerated control; map
# common free-text moves onto it. Unknown moves pass through verbatim so
# the LLM's wording is never silently dropped.
_LUMA_CAMERA = {
    "static": "Static",
    "push in": "Push In", "push-in": "Push In", "push_in": "Push In",
    "dolly in": "Push In", "dolly-in": "Push In",
    "pull out": "Pull Out", "pull-out": "Pull Out", "pull_out": "Pull Out",
    "dolly out": "Pull Out", "dolly-out": "Pull Out",
    "pan left": "Pan Left", "pan right": "Pan Right",
    "tilt up": "Move Up", "tilt down": "Move Down",
    "move left": "Move Left", "move right": "Move Right",
    "move up": "Move Up", "move down": "Move Down",
    "truck left": "Move Left", "truck right": "Move Right",
    "orbit": "Orbit Left", "orbit left": "Orbit Left", "orbit right": "Orbit Right",
    "crane up": "Crane Up", "crane down": "Crane Down",
    "zoom in": "Zoom In", "zoom out": "Zoom Out",
}


def luma_camera(movement: str) -> str:
    """Map a free-text camera move onto Luma's motion enum; pass through
    unknown moves verbatim (lower-cased lookup, normalised separators)."""
    key = movement.strip().lower().replace("_", " ").replace("-", " ").strip()
    return _LUMA_CAMERA.get(key, movement.strip())


def render_enum(shot: Shot) -> str:
    """Luma dialect: a concise description plus an explicit
    ``Camera: <enum>`` directive (Luma controls motion separately)."""
    frags = [
        _framing(shot),
        _subject(shot),
        shot.action.rstrip("."),
        shot.setting,
        shot.lighting,
        _palette(shot, joiner="/"),
        shot.lens,
        shot.style,
        shot.mood,
    ]
    desc = ", ".join(f.strip() for f in frags if f and f.strip())
    if shot.camera_movement:
        cam = luma_camera(shot.camera_movement)
        desc = f"{desc}. Camera: {cam}" if desc else f"Camera: {cam}"
    return desc


def render_visual(shot: Shot, provider: str = "generic") -> str:
    """Dispatch to the provider's render dialect. Unknown → prose."""
    dialect = providers.get(provider).dialect
    if dialect == "runway":
        return render_terse(shot)
    if dialect == "luma":
        return render_enum(shot)
    return render_prose(shot)


def render_dialogue_block(shot: Shot) -> str:
    lines = []
    for d in shot.dialogue():
        spk = (d.get("speaker") or "").strip()
        line = (d.get("line") or "").strip()
        if line:
            lines.append(f"{spk}: {line}" if spk else line)
    return "\n".join(lines)


def render_audio_for_prompt(
    shot: Shot, voices: dict[str, str] | None = None,
) -> str:
    """Compact audio spec appended to the BACKEND prompt for video gen
    (Phase 5.5/5.6) — so the model speaks the lines (with lipsync) and
    lays the SFX/ambience. ``voices`` maps a speaker name → its locked,
    age-resolved voice descriptor, injected so the voice holds scene to
    scene. Empty string when the shot has no audio. Plain text (not
    markdown) — it is concatenated onto the visual prompt.
    """
    voices = voices or {}
    out: list[str] = []
    amb = (shot.audio.get("ambience") or "").strip()
    sfx = (shot.audio.get("sfx") or "").strip()
    dlg = shot.dialogue()
    if dlg:
        out.append("Dialogue (speak aloud, lip-synced):")
        for d in dlg:
            spk = (d.get("speaker") or "").strip()
            line = (d.get("line") or "").strip()
            if not line:
                continue
            # Per-line voice override wins over the manifest descriptor.
            desc = (d.get("voice") or voices.get(spk) or "").strip()
            who = spk or "Narrator"
            vtag = f" [voice: {desc}]" if desc else ""
            out.append(f'- {who}{vtag}: "{line}"')
    if sfx:
        out.append(f"Sound effects: {sfx}.")
    if amb:
        out.append(f"Ambience: {amb}.")
    return "\n".join(out)


def render_markdown(shot: Shot, provider: str = "generic") -> str:
    """The hand-edit-friendly per-shot file: human beat note + the
    rendered prompt + the separate negative/dialogue/consistency fields.
    """
    prof = providers.get(provider)
    out: list[str] = [f"## Shot {shot.id} — {shot.role}", ""]
    if shot.beat_note:
        out += [f"*Beat:* {shot.beat_note}", ""]
    out += [
        f"*Duration:* {shot.duration_s:g}s (cap {prof.max_clip_s:g}s, {prof.name}) · "
        f"*Aspect:* {shot.aspect_ratio} · *Dialect:* {prof.dialect}",
        "",
        "**Prompt**",
        "",
        render_visual(shot, provider) or "_(empty — fill the structured fields)_",
        "",
    ]
    if shot.negative_prompt:
        out += ["**Negative prompt**", "", shot.negative_prompt, ""]
    dlg = render_dialogue_block(shot)
    if dlg:
        label = "**Dialogue**" if prof.audio else "**Dialogue** (provider has no native audio — VO in post)"
        out += [label, "", dlg, ""]
    audio_amb = shot.audio.get("ambience")
    audio_sfx = shot.audio.get("sfx")
    if audio_amb or audio_sfx:
        out += ["**Audio**", ""]
        if audio_amb:
            out.append(f"- ambience: {audio_amb}")
        if audio_sfx:
            out.append(f"- sfx: {audio_sfx}")
        out.append("")
    if shot.reference_image:
        out += [f"**Reference image:** `{shot.reference_image}` "
                f"(consistency: {prof.consistency})", ""]
    return "\n".join(out).rstrip() + "\n"
