"""Sweep progress tracking — interrupt-safe per-chapter checkpoints.

Surfaced 2026-04-29 as a follow-up to the long-sweep context-
exhaustion fix (FUTURE-TODOS): when a `draft-pass` or
`revision-pass` interrupts mid-sweep (power loss, /clear, budget
exhaustion), the user shouldn't have to figure out
`--chapters <remaining>` by hand. This module records progress
per-chapter so `/autonovel:resume` can offer "continue from
chapter N" with a precise list of remaining chapters.

State lives at `.autonovel/sweep-progress.json` and is wiped by
the sweep itself when it completes cleanly. While the file
exists, a sweep is considered in-flight.

Public API:

    start(series, *, command, book, chapters) -> SweepProgress
    mark_done(series, chapter, *, summary) -> SweepProgress
    mark_failed(series, chapter, error) -> SweepProgress
    read(series) -> SweepProgress | None
    clear(series) -> None
    remaining(progress) -> list[int]
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..paths import SeriesLayout


_FILENAME = "sweep-progress.json"


@dataclass
class CompletedChapter:
    chapter: int
    finished_at: str           # ISO UTC
    summary: str = ""          # one-line summary of what the chapter run did

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter,
            "finished_at": self.finished_at,
            "summary": self.summary,
        }


@dataclass
class FailedChapter:
    chapter: int
    failed_at: str
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter,
            "failed_at": self.failed_at,
            "error": self.error,
        }


@dataclass
class SweepProgress:
    command: str               # e.g. "autonovel:draft-pass"
    book: str | None
    started_at: str
    chapters: list[int]        # the full target range
    completed: list[CompletedChapter] = field(default_factory=list)
    failed: list[FailedChapter] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "book": self.book,
            "started_at": self.started_at,
            "chapters": self.chapters,
            "completed": [c.to_dict() for c in self.completed],
            "failed": [f.to_dict() for f in self.failed],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SweepProgress":
        return cls(
            command=data["command"],
            book=data.get("book"),
            started_at=data["started_at"],
            chapters=list(data.get("chapters", [])),
            completed=[
                CompletedChapter(
                    chapter=c["chapter"],
                    finished_at=c["finished_at"],
                    summary=c.get("summary", ""),
                ) for c in data.get("completed", [])
            ],
            failed=[
                FailedChapter(
                    chapter=f["chapter"],
                    failed_at=f["failed_at"],
                    error=f.get("error", ""),
                ) for f in data.get("failed", [])
            ],
        )


# ----------------------------------------------------- I/O


def _path(series: SeriesLayout) -> Path:
    return series.autonovel / _FILENAME


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def start(series: SeriesLayout, *, command: str, book: str | None,
          chapters: list[int]) -> SweepProgress:
    """Begin tracking a new sweep. Overwrites any pre-existing
    progress file (the sweep command is the canonical "I'm starting
    over" signal — if a stale file existed, the new sweep is the
    user's chosen recovery path)."""
    series.autonovel.mkdir(parents=True, exist_ok=True)
    progress = SweepProgress(
        command=command,
        book=book,
        started_at=_now_utc(),
        chapters=list(chapters),
    )
    _write(series, progress)
    return progress


def mark_done(series: SeriesLayout, chapter: int, *,
               summary: str = "") -> SweepProgress | None:
    """Record that `chapter` finished cleanly. Best-effort: if no
    sweep is in flight (no progress file), silently no-op so a
    misbehaving sweep doesn't error out."""
    progress = read(series)
    if progress is None:
        return None
    # Drop any prior failed-then-redone record for the same chapter.
    progress.failed = [f for f in progress.failed if f.chapter != chapter]
    # Don't double-count a chapter; if already completed, refresh the
    # finished_at and summary instead of appending a duplicate.
    progress.completed = [c for c in progress.completed if c.chapter != chapter]
    progress.completed.append(CompletedChapter(
        chapter=chapter,
        finished_at=_now_utc(),
        summary=summary,
    ))
    _write(series, progress)
    return progress


def mark_failed(series: SeriesLayout, chapter: int, error: str = "") -> SweepProgress | None:
    progress = read(series)
    if progress is None:
        return None
    progress.failed = [f for f in progress.failed if f.chapter != chapter]
    progress.failed.append(FailedChapter(
        chapter=chapter,
        failed_at=_now_utc(),
        error=error,
    ))
    _write(series, progress)
    return progress


def read(series: SeriesLayout) -> SweepProgress | None:
    p = _path(series)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return SweepProgress.from_dict(data)


def clear(series: SeriesLayout) -> None:
    p = _path(series)
    if p.is_file():
        p.unlink()


def remaining(progress: SweepProgress) -> list[int]:
    """Chapters in the original target list that have not been marked
    completed. Failures are still considered remaining (a failed
    chapter can be retried)."""
    done = {c.chapter for c in progress.completed}
    return [c for c in progress.chapters if c not in done]


def _write(series: SeriesLayout, progress: SweepProgress) -> None:
    series.autonovel.mkdir(parents=True, exist_ok=True)
    _path(series).write_text(
        json.dumps(progress.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )


# ----------------------------------------------------- render


def render_human(progress: SweepProgress) -> str:
    rem = remaining(progress)
    parts: list[str] = []
    parts.append(f"### Sweep in flight: `/{progress.command}`")
    if progress.book:
        parts.append(f"- Book: `{progress.book}`")
    parts.append(f"- Started: {progress.started_at}")
    parts.append(f"- Target chapters: {progress.chapters}")
    parts.append(
        f"- Completed: {[c.chapter for c in progress.completed]} "
        f"({len(progress.completed)} of {len(progress.chapters)})"
    )
    if progress.failed:
        parts.append(
            f"- Failed: {[(f.chapter, f.error) for f in progress.failed]}"
        )
    if rem:
        parts.append("")
        parts.append(f"**Remaining: {rem}**")
        parts.append("")
        if len(rem) == 1:
            parts.append(
                f"To continue: re-run `/{progress.command}` with "
                f"`--chapter {rem[0]}` (or `--chapters {rem[0]}` for the "
                f"sweep variant)."
            )
        else:
            chapters_str = ",".join(str(c) for c in rem)
            parts.append(
                f"To continue: re-run `/{progress.command} --chapters "
                f"{chapters_str}`."
            )
    else:
        parts.append("")
        parts.append("All chapters complete. Run `autonovel _sweep-clear` "
                     "to mark the sweep done, or it'll auto-clear on the "
                     "next sweep start.")
    return "\n".join(parts) + "\n"
