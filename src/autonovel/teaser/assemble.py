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


@dataclass
class CutEntry:
    shot_id: str
    clip: str                # path to the chosen clip file
    duration_s: float = 4.0
    text_card: str | None = None   # noted for the editor; NOT burned in
    transition: str = "cut"        # v1: hard cut only

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "shot_id": self.shot_id, "clip": self.clip,
            "duration_s": self.duration_s, "transition": self.transition,
        }
        if self.text_card:
            d["text_card"] = self.text_card
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CutEntry":
        return cls(
            shot_id=str(d.get("shot_id", "")),
            clip=str(d.get("clip", "")),
            duration_s=float(d.get("duration_s", 4.0)),
            text_card=d.get("text_card"),
            transition=d.get("transition", "cut"),
        )


@dataclass
class CutList:
    title: str
    kind: str = "image"          # "image" (slideshow) | "video"
    width: int = 854
    height: int = 480
    fps: int = 30
    audio_bed: str | None = None
    entries: list[CutEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "title": self.title, "kind": self.kind,
            "width": self.width, "height": self.height, "fps": self.fps,
            "entries": [e.to_dict() for e in self.entries],
        }
        if self.audio_bed:
            d["audio_bed"] = self.audio_bed
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CutList":
        return cls(
            title=str(d.get("title", "")),
            kind=d.get("kind", "image"),
            width=int(d.get("width", 854)),
            height=int(d.get("height", 480)),
            fps=int(d.get("fps", 30)),
            audio_bed=d.get("audio_bed"),
            entries=[CutEntry.from_dict(e) for e in (d.get("entries") or [])],
        )

    def total_duration_s(self) -> float:
        return sum(e.duration_s for e in self.entries)


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
    cut = CutList(
        title=teaser.title, kind=kind, width=width, height=height, fps=fps,
        audio_bed=audio_bed, entries=entries,
    )
    return cut, missing


def _scale_pad(width: int, height: int) -> str:
    """A scale+pad chain that fits any source into WxH without distortion
    (letterbox/pillarbox), then locks SAR."""
    return (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1")


def ffmpeg_command(cut_list: CutList, out_path: Path | str) -> list[str]:
    """Build the ffmpeg argv that stitches the cut-list into one mp4.

    Pure function (no execution) so it is unit-testable. Image kind →
    a slideshow (`-loop 1 -t <dur>` per still); video kind → trim each
    clip to its `duration_s` then concat. Optional audio bed is mixed and
    the output is trimmed to the shorter of video/audio (`-shortest`).
    """
    if not cut_list.entries:
        raise ValueError("cut_list has no entries — nothing to assemble")
    w, h, fps = cut_list.width, cut_list.height, cut_list.fps
    argv: list[str] = ["ffmpeg", "-y"]
    # Inputs.
    for e in cut_list.entries:
        if cut_list.kind == "image":
            argv += ["-loop", "1", "-t", f"{e.duration_s:g}", "-i", e.clip]
        else:
            argv += ["-i", e.clip]
    if cut_list.audio_bed:
        argv += ["-i", cut_list.audio_bed]
    # Filtergraph: normalise each input, then concat.
    n = len(cut_list.entries)
    chains: list[str] = []
    for i, e in enumerate(cut_list.entries):
        pre = "" if cut_list.kind == "image" else f"trim=0:{e.duration_s:g},setpts=PTS-STARTPTS,"
        chains.append(f"[{i}:v]{pre}{_scale_pad(w, h)},fps={fps}[v{i}]")
    concat_inputs = "".join(f"[v{i}]" for i in range(n))
    chains.append(f"{concat_inputs}concat=n={n}:v=1:a=0[v]")
    argv += ["-filter_complex", ";".join(chains), "-map", "[v]"]
    if cut_list.audio_bed:
        argv += ["-map", f"{n}:a", "-c:a", "aac", "-shortest"]
    argv += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), str(out_path)]
    return argv


def ffmpeg_command_str(cut_list: CutList, out_path: Path | str) -> str:
    """Shell-ready, properly-quoted form of :func:`ffmpeg_command` for a
    command body to run via the ``bash`` tool."""
    return shlex.join(ffmpeg_command(cut_list, out_path))
