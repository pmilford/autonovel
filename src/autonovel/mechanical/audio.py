"""Audiobook script parsing + chunking + chapter-mark stitching.

Everything mechanical about audiobooks lives here so the commands that
shell out to ElevenLabs stay free of string-munging. Split across:

  - `validate_script` — shape-check a parsed script (JSON array of
    {speaker, text} objects; every speaker must be declared in voices).
  - `chunk_segments` — pack segments into API-budget chunks (default
    4500 chars, matching ElevenLabs' 5000-char per-call ceiling with
    headroom).
  - `chapter_marks` — given a list of `(chapter, duration_seconds)`
    rows, produce cumulative chapter timestamps for an m4b chapter
    ledger (the simple format expected by `mp4chaps`/`ffmpeg`).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


MAX_CHARS_PER_CALL = 4500  # matches pre-rewrite gen_audiobook.py
DEFAULT_PAUSE_BETWEEN_CHAPTERS = 2.0  # seconds of silence


@dataclass
class ScriptProblems:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings}


def validate_script(script: dict, voices: dict[str, str] | None = None) -> ScriptProblems:
    """Shape-check a parsed chapter script.

    Required top-level keys: `chapter`, `title`, `segments`.
    Each segment must be `{"speaker": str, "text": str}`; empty
    strings surface as warnings, not errors.

    If `voices` is given, every speaker must appear as a key; unknown
    speakers surface as errors (they would fail at TTS time anyway, so
    we catch them early).
    """
    p = ScriptProblems()
    if not isinstance(script, dict):
        p.errors.append("script root is not a JSON object")
        return p
    for key in ("chapter", "title", "segments"):
        if key not in script:
            p.errors.append(f"missing required key: {key!r}")
    segments = script.get("segments")
    if not isinstance(segments, list):
        p.errors.append("`segments` must be a list")
        return p
    if not segments:
        p.errors.append("`segments` is empty")
        return p
    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            p.errors.append(f"segment {i}: not an object")
            continue
        speaker = seg.get("speaker")
        text = seg.get("text")
        if not isinstance(speaker, str) or not speaker:
            p.errors.append(f"segment {i}: missing or empty speaker")
        if not isinstance(text, str):
            p.errors.append(f"segment {i}: text must be a string")
            continue
        if not text.strip():
            p.warnings.append(f"segment {i}: text is whitespace-only")
        if voices is not None and isinstance(speaker, str) and speaker:
            if speaker not in voices:
                p.errors.append(f"segment {i}: speaker {speaker!r} not in voices map")
    return p


@dataclass
class AudioChunk:
    """A single TTS call's worth of segments."""

    segments: list[dict]
    chars: int

    def to_dict(self) -> dict:
        return {"segments": self.segments, "chars": self.chars}


def chunk_segments(
    segments: list[dict],
    voices: dict[str, str],
    *,
    max_chars: int = MAX_CHARS_PER_CALL,
) -> list[AudioChunk]:
    """Pack segments into chunks that fit within the per-call char budget.

    Each output segment is `{text, voice_id}` suitable for ElevenLabs'
    `text_to_dialogue.convert(inputs=...)`. Bracketed audio tags
    (`[softly]`, `[pause]`) are kept in the text as-is — ElevenLabs v3
    interprets them at render time. Segments whose text is whitespace
    after tag-stripping are dropped (they would emit zero audio).

    Segments longer than `max_chars` are split on sentence boundaries;
    if a sentence itself exceeds the budget it still goes through
    unsplit (the TTS provider will truncate, but the caller sees the
    over-budget chunk in the report).
    """
    if not voices:
        raise ValueError("voices map is empty; cannot resolve any speaker")
    fallback = next(iter(voices.values()))
    chunks: list[AudioChunk] = []
    current: list[dict] = []
    current_chars = 0

    def flush() -> None:
        nonlocal current, current_chars
        if current:
            chunks.append(AudioChunk(segments=current, chars=current_chars))
            current = []
            current_chars = 0

    for seg in segments:
        speaker = seg["speaker"]
        text = seg["text"]
        voice_id = voices.get(speaker) or voices.get("MINOR") or voices.get("NARRATOR") or fallback
        clean = re.sub(r"\[.*?\]", "", text).strip()
        if not clean:
            continue
        seg_chars = len(text)
        if seg_chars > max_chars:
            flush()
            sentences = re.split(r"(?<=[.!?])\s+", text)
            sub: list[str] = []
            sub_chars = 0
            for sent in sentences:
                if not sent:
                    continue
                if sub_chars + len(sent) + 1 > max_chars and sub:
                    joined = " ".join(sub)
                    chunks.append(AudioChunk(
                        segments=[{"text": joined, "voice_id": voice_id}],
                        chars=len(joined),
                    ))
                    sub = []
                    sub_chars = 0
                sub.append(sent)
                sub_chars += len(sent) + 1
            if sub:
                joined = " ".join(sub)
                chunks.append(AudioChunk(
                    segments=[{"text": joined, "voice_id": voice_id}],
                    chars=len(joined),
                ))
            continue
        if current_chars + seg_chars > max_chars and current:
            flush()
        current.append({"text": text, "voice_id": voice_id})
        current_chars += seg_chars

    flush()
    return chunks


@dataclass
class ChapterMark:
    chapter: int
    title: str
    start: float  # seconds from audiobook start
    duration: float

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter,
            "title": self.title,
            "start": round(self.start, 3),
            "duration": round(self.duration, 3),
        }


def chapter_marks(
    rows: list[tuple[int, str, float]],
    *,
    pause: float = DEFAULT_PAUSE_BETWEEN_CHAPTERS,
) -> list[ChapterMark]:
    """Compute cumulative start-times from `(chapter, title, duration)` rows.

    `pause` seconds of silence are inserted *between* chapters, not
    before the first one and not after the last one. That matches how
    `audiobook-assemble` concatenates chapter MP3s with silence pads.
    """
    if pause < 0:
        raise ValueError("pause must be non-negative")
    marks: list[ChapterMark] = []
    cursor = 0.0
    for i, (ch, title, dur) in enumerate(rows):
        if dur < 0:
            raise ValueError(f"chapter {ch}: negative duration")
        marks.append(ChapterMark(chapter=ch, title=title, start=cursor, duration=dur))
        cursor += dur
        if i < len(rows) - 1:
            cursor += pause
    return marks


def format_chapter_marks_mp4chaps(marks: list[ChapterMark]) -> str:
    """Emit the `mp4chaps`/ffmpeg-chapters ledger format."""
    out = [";FFMETADATA1"]
    for m in marks:
        start_ms = int(round(m.start * 1000))
        end_ms = int(round((m.start + m.duration) * 1000))
        out.append("[CHAPTER]")
        out.append("TIMEBASE=1/1000")
        out.append(f"START={start_ms}")
        out.append(f"END={end_ms}")
        out.append(f"title={m.title}")
    return "\n".join(out) + "\n"


def load_script(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
