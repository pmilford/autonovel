"""Cut-list model + ffmpeg command planner for teaser assembly (Phase 3).

Bridges the rendered clips into one teaser video. Like
``mechanical/audio.py`` (which computes chapter marks but never invokes
ffmpeg), this module is **plan-only**: it builds an editable
``cut_list.json`` from the teaser + the clips on disk, and assembles the
exact ffmpeg argv to stitch them — but it does NOT run ffmpeg. The
``/autonovel:teaser-assemble`` command body runs the command via the
``bash`` tool (the same division of labour as ``audiobook-assemble``),
then the viewer-panel cut critique judges the result.

v1 scope (thin on purpose): hard cuts (concat), a still-image slideshow
(the free Pollinations dev default) or pre-made video clips, and an
optional audio bed. No burned-in text (title/subtitle cards belong in an
editor — models garble text; teaser-craft §4), no crossfades yet.
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
    text_card: str | None = None   # noted for the editor; NOT burned in
    transition: str = "cut"        # how this clip ENTERS: cut | fade | dissolve
    fade_out: bool = False         # fade this clip OUT to black at its end
    transition_dur: float = 0.5    # fade length (seconds)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "shot_id": self.shot_id, "clip": self.clip,
            "duration_s": self.duration_s, "transition": self.transition,
        }
        if self.fade_out:
            d["fade_out"] = True
        if self.transition_dur != 0.5:
            d["transition_dur"] = self.transition_dur
        if self.text_card:
            d["text_card"] = self.text_card
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CutEntry":
        trans = d.get("transition", "cut")
        if trans not in TRANSITIONS:
            trans = "cut"
        return cls(
            shot_id=str(d.get("shot_id", "")),
            clip=str(d.get("clip", "")),
            duration_s=float(d.get("duration_s", 4.0)),
            text_card=d.get("text_card"),
            transition=trans,
            fade_out=bool(d.get("fade_out", False)),
            transition_dur=float(d.get("transition_dur", 0.5)),
        )


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
            entries=[CutEntry.from_dict(e) for e in (d.get("entries") or [])],
        )

    def total_duration_s(self) -> float:
        return sum(e.duration_s for e in self.entries)

    def has_clip_audio(self) -> bool:
        """Whether the clips carry native audio (explicit, else inferred
        from kind: video clips do, image stills don't)."""
        if self.clip_audio is not None:
            return self.clip_audio
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
) -> tuple[CutList, list[str]]:
    """Build a default cut-list from the teaser + the clips on disk.

    Returns ``(cut_list, missing_shot_ids)``. A shot whose clip is not on
    disk is skipped (and reported) — assembly proceeds with what exists so
    a single un-rendered shot never blocks a preview. Pure + filesystem
    reads; no ffmpeg, no LLM.
    """
    ext = _EXT.get(kind, "png")
    entries: list[CutEntry] = []
    missing: list[str] = []
    for s in teaser.shots:
        suffix = f"_take{take}" if take > 1 else ""
        clip = Path(clips_dir) / f"shot_{s.id}{suffix}.{ext}"
        if not clip.exists():
            missing.append(s.id)
            continue
        entries.append(CutEntry(
            shot_id=s.id, clip=str(clip), duration_s=s.duration_s,
            text_card=s.text_card,
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
    # Clip audio is only real for concatenated video clips that carry it.
    use_clip_audio = (cut_list.kind == "video"
                      and cut_list.has_clip_audio()
                      and mode in ("clip-only", "mix", "duck"))

    argv: list[str] = ["ffmpeg", "-y"]
    for e in cut_list.entries:
        if cut_list.kind == "image":
            argv += ["-loop", "1", "-t", f"{e.duration_s:g}", "-i", e.clip]
        else:
            argv += ["-i", e.clip]
    if has_bed:
        argv += ["-i", cut_list.audio_bed]
    bed_idx = n if has_bed else None

    # Video chains + concat (carrying clip audio when we need it).
    chains: list[str] = []
    for i, e in enumerate(cut_list.entries):
        pre = "" if cut_list.kind == "image" else f"trim=0:{e.duration_s:g},setpts=PTS-STARTPTS,"
        chains.append(f"[{i}:v]{pre}{_scale_pad(w, h)},fps={fps}{_fade_chain(e)}[v{i}]")
    if use_clip_audio:
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
