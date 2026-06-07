"""Versioned takes for teaser renders (Phase 5.8).

Re-rendering a shot used to overwrite it, losing a take you might have
preferred. This module keeps **every** render: each produced clip is
archived into a ``takes/`` subdir under a monotonic, never-reused number,
while the primary ``shot_<id>.<ext>`` stays the "latest" pointer the rest
of the pipeline (cut-list, assemble) reads. You can list the takes and
**promote** an earlier one back to latest.

Pure + filesystem only (copies bytes; no ffmpeg, no LLM, no network).
Mirrors the typeset ``<slug>_<timestamp>`` + ``_latest`` versioning idea,
applied per shot.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# A produced clip is `shot_<id>.<ext>` (latest) or `shot_<id>_take<N>.<ext>`.
_NAME_RE = re.compile(r"^shot_(?P<id>.+?)(?:_take(?P<take>\d+))?$")
_CLIP_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm", ".gif")


def parse_clip_name(path: Path) -> tuple[str, int | None, str]:
    """``shot_01a_take3.mp4`` → ("01a", 3, ".mp4"); ``shot_01a.png`` →
    ("01a", None, ".png"). Raises ValueError on a non-clip name."""
    m = _NAME_RE.match(path.stem)
    if not m:
        raise ValueError(f"not a shot clip filename: {path.name}")
    take = int(m.group("take")) if m.group("take") else None
    return m.group("id"), take, path.suffix


def next_take_number(takes_dir: Path, shot_id: str, ext: str) -> int:
    """The next free archival take number for ``shot_id`` in
    ``takes_dir`` (1 if none yet). Monotonic — never reuses a number even
    if an earlier take was deleted (max+1)."""
    ext = ext if ext.startswith(".") else f".{ext}"
    hi = 0
    if takes_dir.is_dir():
        for p in takes_dir.glob(f"shot_{shot_id}_take*{ext}"):
            try:
                _id, take, _e = parse_clip_name(p)
            except ValueError:
                continue
            if take and take > hi:
                hi = take
    return hi + 1


def archive_take(src: Path, takes_dir: Path) -> Path:
    """Copy a freshly-rendered clip into ``takes_dir`` under the next free
    take number; return the archived path. Never overwrites an existing
    take. The source (the latest pointer) is left in place."""
    src = Path(src)
    shot_id, _take, ext = parse_clip_name(src)
    takes_dir = Path(takes_dir)
    takes_dir.mkdir(parents=True, exist_ok=True)
    n = next_take_number(takes_dir, shot_id, ext)
    dest = takes_dir / f"shot_{shot_id}_take{n}{ext}"
    shutil.copy2(src, dest)
    return dest


def archive_script(src: Path, archive_dir: Path | None = None,
                   *, when: datetime | None = None) -> Path | None:
    """Timestamp-archive a teaser *script* artifact (``beats.md`` /
    ``teaser.json`` / a shot file) before it is regenerated, so a
    ``--force`` re-run never destroys the previous version (Phase 6).

    Copies ``src`` to ``<archive_dir>/<stem>_<YYYYMMDD>_<HHMM><ext>``
    (default ``archive_dir`` = ``<src dir>/script-takes``). Returns the
    archived path, or ``None`` if ``src`` does not exist (nothing to keep —
    a no-op, not an error). Never overwrites: a same-minute re-run gets a
    ``_2``/``_3`` suffix. Pure filesystem; no LLM, no network.

    The portraits/location reference *originals* live in ``refs/`` and are
    untouched by this — only the generated scripts are versioned here, so a
    full pipeline re-run keeps every prior script AND reuses the approved
    references.
    """
    src = Path(src)
    if not src.is_file():
        return None
    archive_dir = Path(archive_dir) if archive_dir else src.parent / "script-takes"
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = (when or datetime.now()).strftime("%Y%m%d_%H%M")
    base, ext = src.stem, src.suffix
    dest = archive_dir / f"{base}_{stamp}{ext}"
    n = 2
    while dest.exists():
        dest = archive_dir / f"{base}_{stamp}_{n}{ext}"
        n += 1
    shutil.copy2(src, dest)
    return dest


@dataclass
class TakeInfo:
    shot_id: str
    take: int
    path: str
    bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {"shot_id": self.shot_id, "take": self.take,
                "path": self.path, "bytes": self.bytes}


def list_takes(takes_dir: Path) -> dict[str, list[TakeInfo]]:
    """Map shot id → its archived takes (sorted by take number)."""
    out: dict[str, list[TakeInfo]] = {}
    takes_dir = Path(takes_dir)
    if not takes_dir.is_dir():
        return out
    for p in sorted(takes_dir.iterdir()):
        if p.suffix.lower() not in _CLIP_EXTS or not p.is_file():
            continue
        try:
            shot_id, take, _ext = parse_clip_name(p)
        except ValueError:
            continue
        if take is None:
            continue
        out.setdefault(shot_id, []).append(
            TakeInfo(shot_id=shot_id, take=take, path=str(p),
                     bytes=p.stat().st_size))
    for v in out.values():
        v.sort(key=lambda t: t.take)
    return out


def promote_take(takes_dir: Path, clips_dir: Path, shot_id: str, take: int) -> Path:
    """Copy ``takes/shot_<id>_take<N>.<ext>`` back to the latest pointer
    ``clips/shot_<id>.<ext>`` so the next cut-list/assemble uses it.
    Returns the latest-pointer path. Raises FileNotFoundError if the take
    does not exist."""
    takes_dir, clips_dir = Path(takes_dir), Path(clips_dir)
    matches = list(takes_dir.glob(f"shot_{shot_id}_take{take}.*"))
    matches = [m for m in matches if m.suffix.lower() in _CLIP_EXTS]
    if not matches:
        raise FileNotFoundError(
            f"no take {take} for shot {shot_id} in {takes_dir}")
    src = matches[0]
    clips_dir.mkdir(parents=True, exist_ok=True)
    dest = clips_dir / f"shot_{shot_id}{src.suffix}"
    shutil.copy2(src, dest)
    return dest
