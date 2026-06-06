"""Render a structured ``Shot`` into provider-ready prompt prose (PRD §8).

The LLM fills the structured fields; this module assembles them into the
canonical Veo/Sora field order so the wording/ordering is deterministic
and consistent across shots. Phase 1 ships the ``generic`` dialect (one
rich prose paragraph + separate negative + separate dialogue block);
Phase 2 adds per-provider dialects (Veo prose / Sora +Dialogue / Runway
terse / Luma enum). Unknown dialects fall back to ``generic``.
"""

from __future__ import annotations

from . import providers
from .shots import Shot


def render_prose(shot: Shot) -> str:
    """The visual prompt as one paragraph, in canonical order:
    framing → subject+appearance → action → setting → lighting →
    palette → camera move → lens → style → mood."""
    parts: list[str] = []
    framing = ", ".join(p for p in (shot.shot_size, shot.camera_angle) if p)
    if framing:
        parts.append(framing.capitalize() + ".")
    subj = shot.subject_name.upper() if shot.subject_name else ""
    if subj and shot.subject_appearance:
        parts.append(f"{subj} ({shot.subject_appearance})")
    elif subj:
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


def render_dialogue_block(shot: Shot) -> str:
    lines = []
    for d in shot.dialogue():
        spk = (d.get("speaker") or "").strip()
        line = (d.get("line") or "").strip()
        if line:
            lines.append(f"{spk}: {line}" if spk else line)
    return "\n".join(lines)


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
        f"*Aspect:* {shot.aspect_ratio}",
        "",
        "**Prompt**",
        "",
        render_prose(shot) or "_(empty — fill the structured fields)_",
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
