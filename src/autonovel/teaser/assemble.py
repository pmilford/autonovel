"""Cut-list model + ffmpeg command planner for teaser assembly (Phase 3).

Bridges the rendered clips into one teaser video. Like
``mechanical/audio.py`` (which computes chapter marks but never invokes
ffmpeg), this module is **plan-only**: it builds an editable
``cut_list.json`` from the teaser + the clips on disk, and assembles the
exact ffmpeg argv to stitch them — but it does NOT run ffmpeg. The
``/autonovel:teaser-assemble`` command body runs the command via the
``bash`` tool (the same division of labour as ``audiobook-assemble``),
then the viewer-panel cut critique judges the result.

Scope: hard cuts + concat-compatible fades, a still-image slideshow, real
video clips, OR a **mixed** cut that weaves video shots through a keyframe
slideshow (Phase 8), an optional ducked audio bed, and — opt-in — burned-in
title/stinger cards (Phase 8; off by default since models garble type and
cards are normally added in an editor, teaser-craft §4). True overlapping
cross-dissolves are still deferred (the xfade rework, FUTURE-TODOS).
"""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .shots import Teaser

_EXT = {"image": "png", "video": "mp4"}


# Transition INTO a clip. v1 emits fades (concat-compatible): `dissolve`
# renders as a fade-in for now — a true cross-dissolve needs the overlap
# (xfade) rework noted in FUTURE-TODOS.
TRANSITIONS = ("cut", "fade", "dissolve")


@dataclass
class CutEntry:
    shot_id: str
    clip: str                # path to the chosen clip file
    duration_s: float = 4.0
    text_card: str | None = None   # the card text (a note, or burned in with --burn-titles)
    transition: str = "cut"        # how this clip ENTERS: cut | fade | dissolve
    fade_out: bool = False         # fade this clip OUT to black at its end
    transition_dur: float = 0.5    # fade length (seconds)
    # Phase 8 — per-entry media so one cut can MIX dynamic video shots with
    # static keyframes: "image" (held for duration_s, silent) | "video"
    # (trimmed to duration_s, native audio). "" ⇒ infer from the cut's kind.
    media: str = ""
    # Phase 8 — how a burned-in text_card is placed: "title" (centered,
    # large) | "stinger" (lower third, smaller).
    card_kind: str = "stinger"
    # Phase 12 — a figure-identification lower-third ("Name — epithet") burned
    # at this clip's first ~2.5s so a first-time viewer knows WHO this is.
    # Distinct from a text_card (which is a story line); sits at the very
    # bottom. Set only on a figure's first appearance.
    identify: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "shot_id": self.shot_id, "clip": self.clip,
            "duration_s": self.duration_s, "transition": self.transition,
        }
        if self.fade_out:
            d["fade_out"] = True
        if self.transition_dur != 0.5:
            d["transition_dur"] = self.transition_dur
        if self.media:
            d["media"] = self.media
        if self.text_card:
            d["text_card"] = self.text_card
        if self.card_kind != "stinger":
            d["card_kind"] = self.card_kind
        if self.identify:
            d["identify"] = self.identify
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CutEntry":
        trans = d.get("transition", "cut")
        if trans not in TRANSITIONS:
            trans = "cut"
        media = str(d.get("media", "") or "")
        if media not in ("", "image", "video"):
            media = ""
        card_kind = str(d.get("card_kind", "stinger") or "stinger")
        if card_kind not in ("title", "stinger"):
            card_kind = "stinger"
        return cls(
            shot_id=str(d.get("shot_id", "")),
            clip=str(d.get("clip", "")),
            duration_s=float(d.get("duration_s", 4.0)),
            text_card=d.get("text_card"),
            transition=trans,
            fade_out=bool(d.get("fade_out", False)),
            transition_dur=float(d.get("transition_dur", 0.5)),
            media=media,
            card_kind=card_kind,
            identify=d.get("identify"),
        )

    def media_kind(self, cut_kind: str) -> str:
        """Resolve this entry's media (explicit ``media`` else the cut kind;
        a "mixed" cut with no explicit media falls back to image)."""
        if self.media in ("image", "video"):
            return self.media
        return "video" if cut_kind == "video" else "image"


# How clip audio (native dialogue/music) and an optional music bed combine.
AUDIO_MODES = ("auto", "none", "bed-only", "clip-only", "mix", "duck")


@dataclass
class CutList:
    title: str
    kind: str = "image"          # "image" (slideshow) | "video"
    width: int = 854
    height: int = 480
    fps: int = 30
    audio_bed: str | None = None
    entries: list[CutEntry] = field(default_factory=list)
    # Phase 5.4 — how clip audio + the bed combine:
    #   auto      image→bed-only; video w/ clip audio + bed→duck; video w/
    #             clip audio, no bed→clip-only; video no audio→bed-only/none.
    #   none      drop all audio.   bed-only  ignore clip audio, use the bed.
    #   clip-only keep native clip dialogue/music, no bed.
    #   mix       clip audio + bed at equal level.
    #   duck      bed ducks UNDER the clip dialogue (sidechain compress).
    audio_mode: str = "auto"
    # Whether the video clips carry a native audio track (grok/veo/kie do;
    # magichour/stub/image stills do not). None ⇒ infer from kind.
    clip_audio: bool | None = None
    # Phase 5.9 — seconds of audio fade-in/out applied to EACH clip's own
    # audio at the cut boundaries, so per-clip native music (the `native`
    # score path) doesn't *pop* between shots. 0 ⇒ off. A true overlapping
    # cross-fade is the deferred xfade work (5.7b).
    audio_seam_fade: float = 0.0
    # Phase 8 — burn the text cards into the picture with ffmpeg drawtext
    # (opt-in). Off by default: models garble type, so cards are normally
    # added in an editor (teaser-craft §4); this is for a quick self-contained
    # cut. ``font_file`` is a .ttf/.otf path (e.g. EB Garamond); when unset,
    # ffmpeg's default font is used (needs fontconfig).
    burn_titles: bool = False
    font_file: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "title": self.title, "kind": self.kind,
            "width": self.width, "height": self.height, "fps": self.fps,
            "entries": [e.to_dict() for e in self.entries],
        }
        if self.audio_bed:
            d["audio_bed"] = self.audio_bed
        if self.audio_mode and self.audio_mode != "auto":
            d["audio_mode"] = self.audio_mode
        if self.clip_audio is not None:
            d["clip_audio"] = self.clip_audio
        if self.audio_seam_fade:
            d["audio_seam_fade"] = self.audio_seam_fade
        if self.burn_titles:
            d["burn_titles"] = True
        if self.font_file:
            d["font_file"] = self.font_file
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CutList":
        mode = str(d.get("audio_mode", "auto"))
        if mode not in AUDIO_MODES:
            mode = "auto"
        clip_audio = d.get("clip_audio")
        return cls(
            title=str(d.get("title", "")),
            kind=d.get("kind", "image"),
            width=int(d.get("width", 854)),
            height=int(d.get("height", 480)),
            fps=int(d.get("fps", 30)),
            audio_bed=d.get("audio_bed"),
            audio_mode=mode,
            clip_audio=(bool(clip_audio) if clip_audio is not None else None),
            audio_seam_fade=float(d.get("audio_seam_fade", 0.0)),
            burn_titles=bool(d.get("burn_titles", False)),
            font_file=d.get("font_file"),
            entries=[CutEntry.from_dict(e) for e in (d.get("entries") or [])],
        )

    def total_duration_s(self) -> float:
        return sum(e.duration_s for e in self.entries)

    def has_clip_audio(self) -> bool:
        """Whether the clips carry native audio (explicit, else inferred
        from kind: video — and mixed cuts, whose video segments carry it —
        do; an all-image slideshow does not)."""
        if self.clip_audio is not None:
            return self.clip_audio
        if self.kind == "mixed":
            return any(e.media_kind("mixed") == "video" for e in self.entries)
        return self.kind == "video"

    def resolve_audio_mode(self) -> str:
        """Resolve ``auto`` to a concrete mode from kind / clip-audio / bed."""
        mode = (self.audio_mode or "auto").lower()
        if mode != "auto":
            return mode
        has_bed = bool(self.audio_bed)
        if not self.has_clip_audio():
            return "bed-only" if has_bed else "none"
        return "duck" if has_bed else "clip-only"


def load(path: Path) -> CutList:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("cut_list.json top level must be a JSON object")
    return CutList.from_dict(data)


def dump(cut_list: CutList, path: Path) -> None:
    Path(path).write_text(
        json.dumps(cut_list.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_cut_list(
    teaser: Teaser,
    clips_dir: Path,
    *,
    kind: str = "image",
    width: int = 854,
    height: int = 480,
    fps: int = 30,
    audio_bed: str | None = None,
    take: int = 1,
    audio_mode: str = "auto",
    clip_audio: bool | None = None,
    transitions: bool = True,
    audio_seam_fade: float = 0.0,
    burn_titles: bool = False,
    font_file: str | None = None,
) -> tuple[CutList, list[str]]:
    """Build a default cut-list from the teaser + the clips on disk.

    Returns ``(cut_list, missing_shot_ids)``. A shot whose clip is not on
    disk is skipped (and reported) — assembly proceeds with what exists so
    a single un-rendered shot never blocks a preview. Pure + filesystem
    reads; no ffmpeg, no LLM.

    ``kind="mixed"`` (Phase 8) picks, per shot, the dynamic ``shot_<id>.mp4``
    when present (native audio, trimmed to ``duration_s``) else the static
    ``shot_<id>.png`` (held for ``duration_s``, silent) — so a real teaser
    can weave a few motion shots through a keyframe slideshow.
    """
    suffix = lambda: f"_take{take}" if take > 1 else ""  # noqa: E731
    role_by_id = {s.id: s.role for s in teaser.shots}

    def _resolve(shot_id: str) -> tuple[Path | None, str]:
        cd = Path(clips_dir)
        sfx = suffix()
        if kind == "mixed":
            # prefer video (clips dir or a video/ subdir), else the still
            for cand in (cd / f"shot_{shot_id}{sfx}.mp4",
                         cd / "video" / f"shot_{shot_id}{sfx}.mp4"):
                if cand.exists():
                    return cand, "video"
            still = cd / f"shot_{shot_id}{sfx}.png"
            return (still if still.exists() else None), "image"
        ext = _EXT.get(kind, "png")
        clip = cd / f"shot_{shot_id}{sfx}.{ext}"
        return (clip if clip.exists() else None), ("video" if kind == "video" else "image")

    entries: list[CutEntry] = []
    missing: list[str] = []
    for s in teaser.shots:
        clip, media = _resolve(s.id)
        if clip is None:
            missing.append(s.id)
            continue
        entries.append(CutEntry(
            shot_id=s.id, clip=str(clip), duration_s=s.duration_s,
            text_card=s.text_card,
            media=(media if kind == "mixed" else ""),
            card_kind=("title" if role_by_id.get(s.id) == "title" else "stinger"),
            identify=(s.identify or None),
        ))
    # Safe transition defaults (Phase 5.7): ease in/out of black and fade
    # title cards. Everything else stays a hard cut — the artistic
    # placement of *other* transitions is the LLM's call in the command
    # body (see suggest_transitions). Disable with transitions=False.
    if transitions and entries:
        role_by_id = {s.id: s.role for s in teaser.shots}
        entries[0].transition = "fade"           # fade in from black
        entries[-1].fade_out = True              # fade out to black
        for e in entries:
            if role_by_id.get(e.shot_id) == "title":
                e.transition = "fade"
    cut = CutList(
        title=teaser.title, kind=kind, width=width, height=height, fps=fps,
        audio_bed=audio_bed, entries=entries,
        audio_mode=audio_mode, clip_audio=clip_audio,
        audio_seam_fade=audio_seam_fade,
        burn_titles=burn_titles, font_file=font_file,
    )
    return cut, missing


def _fade_chain(e: "CutEntry") -> str:
    """Per-clip fade filters (Phase 5.7), concat-compatible: a fade-IN from
    black when the clip's `transition` is fade/dissolve, and a fade-OUT to
    black when `fade_out`. Fade length is clamped to half the clip so the
    in/out don't overlap. Returns "" for a hard cut. (A true cross-dissolve
    between clips needs the xfade overlap rework — see FUTURE-TODOS; for now
    `dissolve` degrades to a fade-in.)"""
    dur = max(0.1, float(e.duration_s))
    td = max(0.0, min(float(e.transition_dur), dur / 2.0))
    parts: list[str] = []
    if e.transition in ("fade", "dissolve") and td > 0:
        parts.append(f"fade=t=in:st=0:d={td:g}")
    if e.fade_out and td > 0:
        parts.append(f"fade=t=out:st={dur - td:g}:d={td:g}")
    return ("," + ",".join(parts)) if parts else ""


@dataclass
class TransitionSuggestion:
    into_shot: str               # the shot this transition leads INTO
    after_shot: str | None       # the preceding shot (None at the open)
    suggested: str               # cut | fade | dissolve | fade-out
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "into_shot": self.into_shot, "after_shot": self.after_shot,
            "suggested": self.suggested, "reasons": list(self.reasons),
        }


def suggest_transitions(
    teaser: Teaser,
    *,
    year_gap: float = 2.0,
    slow_ratio: float = 1.5,
) -> list[TransitionSuggestion]:
    """Flag where a non-cut transition is *worth considering*, from
    STRUCTURED signals only (no prose judgement — that's the LLM's job in
    the command body, which may accept/override these):

      - **time jump** — `|Δstory_year|` ≥ ``year_gap`` between consecutive
        shots → a fade reads the ellipsis.
      - **location change** — the `setting` changes → a dissolve bridges it.
      - **pace shift (fast→slow)** — the shot's `duration_s` jumps by
        ≥ ``slow_ratio``× the previous, or the role moves into `title`/
        `button` → ease in with a fade.
      - **open / close** — fade in on the first shot, fade out on the last.

    Advisory: returns one suggestion per flagged boundary (plus open/close).
    A hard cut everywhere else is the default; the caller applies what it
    likes onto the cut-list entries.
    """
    shots = teaser.shots
    out: list[TransitionSuggestion] = []
    if not shots:
        return out
    out.append(TransitionSuggestion(shots[0].id, None, "fade", ["open (fade in from black)"]))
    for prev, cur in zip(shots, shots[1:]):
        reasons: list[str] = []
        suggested = "cut"
        py, cy = getattr(prev, "story_year", None), getattr(cur, "story_year", None)
        if py is not None and cy is not None and abs(cy - py) >= year_gap:
            reasons.append(f"time jump (Δ{abs(cy - py):g}y)")
            suggested = "fade"
        if _norm(prev.setting) and _norm(cur.setting) and _norm(prev.setting) != _norm(cur.setting):
            reasons.append(f"location change ({prev.setting} → {cur.setting})")
            suggested = "dissolve" if suggested == "cut" else suggested
        if prev.duration_s > 0 and cur.duration_s >= slow_ratio * prev.duration_s:
            reasons.append(f"pace slows ({prev.duration_s:g}s → {cur.duration_s:g}s)")
            suggested = suggested if suggested != "cut" else "fade"
        if cur.role in ("title", "button") and prev.role not in ("title", "button"):
            reasons.append(f"beat shift (→ {cur.role})")
            suggested = suggested if suggested != "cut" else "fade"
        if reasons:
            out.append(TransitionSuggestion(cur.id, prev.id, suggested, reasons))
    out.append(TransitionSuggestion(shots[-1].id, None, "fade-out", ["close (fade out to black)"]))
    return out


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _dt_escape(text: str) -> str:
    """Escape text for ffmpeg ``drawtext`` (which lives inside one shell-
    quoted -filter_complex arg). Backslash/colon/percent are ffmpeg-special;
    the straight apostrophe is swapped for a typographic one to dodge the
    nested-quote minefield entirely (it also just looks better on screen)."""
    t = (text or "").replace("\\", "\\\\").replace(":", "\\:").replace("%", "\\%")
    t = t.replace("'", "’").replace("\n", " ")
    return t


def _burn_chain(e: "CutEntry", w: int, h: int, font_file: str | None) -> str:
    """A per-segment ``drawtext`` filter for a burned-in text card (Phase 8),
    faded in/out over the segment, returned with a leading comma (or "").
    Title cards sit centered + large; stingers ride the lower third; an
    `identify` figure-label (Phase 12) rides the very bottom for the clip's
    first ~2.5s. Timing is segment-local because every segment is trimmed/held
    to duration_s."""
    dur = max(0.1, float(e.duration_s))
    td = max(0.1, min(float(e.transition_dur) or 0.5, dur / 2.0))
    ff = f"fontfile={font_file}:" if font_file else ""
    chain = ""
    if (e.text_card or "").strip():
        text = _dt_escape(e.text_card)
        if e.card_kind == "title":
            size, y = max(24, w // 16), "(h-text_h)/2"
        else:
            size, y = max(16, w // 30), "h-text_h-(h/10)"
        # alpha ramps 0→1 over td, holds, then 1→0 over the last td.
        alpha = (f"alpha='if(lt(t,{td:g}),t/{td:g},"
                 f"if(gt(t,{dur - td:g}),({dur:g}-t)/{td:g},1))'")
        chain += (f",drawtext={ff}text='{text}':x=(w-text_w)/2:y={y}:"
                  f"fontcolor=white:fontsize={size}:borderw=2:bordercolor=black@0.8:{alpha}")
    if (e.identify or "").strip():
        # Figure ID: small, very bottom, shown for the first ~2.5s (or clip
        # length if shorter), faded out — "who is this?" answered for a viewer.
        idt = _dt_escape(e.identify)
        hold = min(2.5, dur)
        fade = min(0.4, hold / 2.0)
        isize = max(14, w // 38)
        ialpha = (f"alpha='if(lt(t,{fade:g}),t/{fade:g},"
                  f"if(gt(t,{hold - fade:g}),max(0,({hold:g}-t)/{fade:g}),1))'")
        chain += (f",drawtext={ff}text='{idt}':x=(w-text_w)/2:y=h-text_h-(h/24):"
                  f"fontcolor=white:fontsize={isize}:borderw=2:bordercolor=black@0.85:"
                  f"enable='lt(t,{hold:g})':{ialpha}")
    return chain


def _scale_pad(width: int, height: int) -> str:
    """A scale+pad chain that fits any source into WxH without distortion
    (letterbox/pillarbox), then locks SAR."""
    return (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1")


def ffmpeg_command(cut_list: CutList, out_path: Path | str) -> list[str]:
    """Build the ffmpeg argv that stitches the cut-list into one mp4.

    Pure function (no execution) so it is unit-testable. Image kind →
    a slideshow (`-loop 1 -t <dur>` per still); video kind → trim each
    clip to its `duration_s` then concat.

    Audio (Phase 5.4) follows ``cut_list.resolve_audio_mode()``:
      - **none** — silent output.
      - **bed-only** — the music bed is the only track (clip audio dropped).
      - **clip-only** — keep the clips' native dialogue/music, no bed.
      - **mix** — clip audio + bed at equal level.
      - **duck** — the bed **ducks under the clip dialogue** (sidechain
        compress keyed on the concatenated clip audio), then is mixed in —
        so a music bed never buries the spoken lines.
    Clip audio is only available for ``kind == video`` with clip-bearing
    clips; the concat takes ``a=1`` only then.
    """
    if not cut_list.entries:
        raise ValueError("cut_list has no entries — nothing to assemble")
    w, h, fps = cut_list.width, cut_list.height, cut_list.fps
    n = len(cut_list.entries)
    has_bed = bool(cut_list.audio_bed)
    mode = cut_list.resolve_audio_mode()
    # Clip audio is only real for video (or mixed) cuts that carry it.
    use_clip_audio = (cut_list.kind in ("video", "mixed")
                      and cut_list.has_clip_audio()
                      and mode in ("clip-only", "mix", "duck"))

    # Per-entry media: explicit on a "mixed" cut, else the cut kind.
    seg_video = [e.media_kind(cut_list.kind) == "video" for e in cut_list.entries]
    is_mixed = cut_list.kind == "mixed"
    burn = cut_list.burn_titles
    ff = cut_list.font_file

    argv: list[str] = ["ffmpeg", "-y"]
    for i, e in enumerate(cut_list.entries):
        if seg_video[i]:
            argv += ["-i", e.clip]
        else:
            argv += ["-loop", "1", "-t", f"{e.duration_s:g}", "-i", e.clip]
    if has_bed:
        argv += ["-i", cut_list.audio_bed]
    bed_idx = n if has_bed else None

    # Mixed cuts need a silent audio source per *image* segment so the
    # concat (a=1) has an audio pad for every segment alongside the video
    # segments' native audio. One finite lavfi anullsrc per still.
    sil_idx: dict[int, int] = {}
    if is_mixed and use_clip_audio:
        nxt = n + (1 if has_bed else 0)
        for i, e in enumerate(cut_list.entries):
            if not seg_video[i]:
                argv += ["-f", "lavfi", "-t", f"{e.duration_s:g}",
                         "-i", "anullsrc=r=44100:cl=stereo"]
                sil_idx[i] = nxt
                nxt += 1

    # Video chains + concat (carrying clip audio when we need it).
    chains: list[str] = []
    for i, e in enumerate(cut_list.entries):
        pre = f"trim=0:{e.duration_s:g},setpts=PTS-STARTPTS," if seg_video[i] else ""
        # Burn text cards only when burn_titles is on; ALWAYS burn the
        # figure-identify lower-third (Phase 12 — it's load-bearing
        # legibility, not an optional card).
        if burn:
            burn_f = _burn_chain(e, w, h, ff)
        elif (e.identify or "").strip():
            id_only = CutEntry(shot_id=e.shot_id, clip=e.clip,
                               duration_s=e.duration_s, identify=e.identify,
                               transition_dur=e.transition_dur)
            burn_f = _burn_chain(id_only, w, h, ff)
        else:
            burn_f = ""
        chains.append(
            f"[{i}:v]{pre}{_scale_pad(w, h)},fps={fps}{_fade_chain(e)}{burn_f}[v{i}]")
    if is_mixed and use_clip_audio:
        # Normalize each segment's audio (native for video, silence for
        # stills) to a common format, then concat a=1.
        for i, e in enumerate(cut_list.entries):
            src = f"[{i}:a]" if seg_video[i] else f"[{sil_idx[i]}:a]"
            chains.append(f"{src}aformat=sample_rates=44100:channel_layouts=stereo,"
                          f"asetpts=PTS-STARTPTS[a{i}]")
        concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(n))
        chains.append(f"{concat_inputs}concat=n={n}:v=1:a=1[v][aclip]")
    elif use_clip_audio:
        # Optional per-clip audio seam-fade (5.9): soften the music/SFX pop
        # at each hard cut without overlapping (concat-compatible).
        sf = max(0.0, float(cut_list.audio_seam_fade))
        if sf > 0:
            alabels = []
            for i, e in enumerate(cut_list.entries):
                d = max(0.1, float(e.duration_s))
                fd = min(sf, d / 2.0)
                chains.append(
                    f"[{i}:a]afade=t=in:st=0:d={fd:g},"
                    f"afade=t=out:st={d - fd:g}:d={fd:g}[a{i}]")
                alabels.append(f"[a{i}]")
            concat_inputs = "".join(f"[v{i}]{alabels[i]}" for i in range(n))
        else:
            concat_inputs = "".join(f"[v{i}][{i}:a]" for i in range(n))
        chains.append(f"{concat_inputs}concat=n={n}:v=1:a=1[v][aclip]")
    else:
        concat_inputs = "".join(f"[v{i}]" for i in range(n))
        chains.append(f"{concat_inputs}concat=n={n}:v=1:a=0[v]")

    # Audio graph → an output label (or None for silent).
    # In `-map`, a filtergraph output is referenced with brackets ([a]);
    # a raw input stream is referenced WITHOUT them (2:a). The bed, mapped
    # straight through, is the latter; filtergraph results are the former.
    audio_label: str | None = None
    if mode == "clip-only" and use_clip_audio:
        audio_label = "[aclip]"
    elif mode == "bed-only" and has_bed:
        audio_label = f"{bed_idx}:a"
    elif mode == "mix" and use_clip_audio and has_bed:
        chains.append(f"[aclip][{bed_idx}:a]amix=inputs=2:duration=first:"
                      f"dropout_transition=0[a]")
        audio_label = "[a]"
    elif mode == "duck" and use_clip_audio and has_bed:
        # Split the dialogue: one copy keys the compressor, one is mixed.
        chains.append("[aclip]asplit=2[ak][am]")
        chains.append(f"[{bed_idx}:a][ak]sidechaincompress="
                      f"threshold=0.03:ratio=8:attack=20:release=300[bedduck]")
        chains.append("[am][bedduck]amix=inputs=2:duration=first:"
                      "dropout_transition=0[a]")
        audio_label = "[a]"
    elif has_bed:
        # Fallback (e.g. mode wanted clip audio but none available): bed only.
        audio_label = f"{bed_idx}:a"
    elif use_clip_audio:
        audio_label = "[aclip]"

    argv += ["-filter_complex", ";".join(chains), "-map", "[v]"]
    if audio_label is not None:
        argv += ["-map", audio_label, "-c:a", "aac"]
        # Trim to the video when a bed (which may run long) is the sole or
        # mixed source; -shortest is safe since [v] is finite.
        if has_bed and mode in ("bed-only",) :
            argv += ["-shortest"]
    argv += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), str(out_path)]
    return argv


def ffmpeg_command_str(cut_list: CutList, out_path: Path | str) -> str:
    """Shell-ready, properly-quoted form of :func:`ffmpeg_command` for a
    command body to run via the ``bash`` tool."""
    return shlex.join(ffmpeg_command(cut_list, out_path))
