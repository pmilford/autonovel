"""Tier-1 tests for `src/autonovel/mechanical/audio.py`.

Three mechanical bits the PR-7 audiobook commands depend on:

  - `validate_script` catches the script shapes that would fail at TTS
    time (missing speaker/text, unknown speaker, bad root type).
  - `chunk_segments` packs within budget, never splits dialogue
    mid-segment unless a single segment exceeds the budget, and drops
    tag-only segments (which would emit silent audio).
  - `chapter_marks` emits cumulative start-times with the right pause
    between chapters and a zero-pause at the tail.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel.mechanical.audio import (
    MAX_CHARS_PER_CALL,
    chapter_marks,
    chunk_segments,
    format_chapter_marks_mp4chaps,
    validate_script,
)


# ---------------------------------------------------------------------------
# validate_script
# ---------------------------------------------------------------------------


def _good_script() -> dict:
    return {
        "chapter": 1,
        "title": "The Morning Pitch",
        "segments": [
            {"speaker": "NARRATOR", "text": "Cass woke to bells."},
            {"speaker": "CASS", "text": "[softly] Another day."},
        ],
    }


class TestValidateScript:
    def test_good_script_ok(self) -> None:
        p = validate_script(_good_script())
        assert p.ok
        assert not p.errors

    def test_missing_chapter_key(self) -> None:
        s = _good_script()
        del s["chapter"]
        p = validate_script(s)
        assert not p.ok
        assert any("chapter" in e for e in p.errors)

    def test_empty_segments_is_error(self) -> None:
        s = _good_script()
        s["segments"] = []
        p = validate_script(s)
        assert not p.ok

    def test_segments_must_be_list(self) -> None:
        s = _good_script()
        s["segments"] = "nope"
        p = validate_script(s)
        assert not p.ok

    def test_unknown_speaker_errors_when_voices_provided(self) -> None:
        voices = {"NARRATOR": "v1"}
        p = validate_script(_good_script(), voices)
        assert not p.ok
        assert any("CASS" in e for e in p.errors)

    def test_whitespace_only_text_is_warning(self) -> None:
        s = _good_script()
        s["segments"].append({"speaker": "NARRATOR", "text": "   "})
        p = validate_script(s)
        assert p.ok
        assert p.warnings

    def test_non_object_root(self) -> None:
        p = validate_script(["not", "a", "dict"])  # type: ignore[arg-type]
        assert not p.ok


# ---------------------------------------------------------------------------
# chunk_segments
# ---------------------------------------------------------------------------


class TestChunkSegments:
    VOICES = {"NARRATOR": "v_narr", "CASS": "v_cass"}

    def test_packs_under_budget(self) -> None:
        segs = [
            {"speaker": "NARRATOR", "text": "x" * 1000},
            {"speaker": "NARRATOR", "text": "y" * 1000},
            {"speaker": "NARRATOR", "text": "z" * 1000},
        ]
        chunks = chunk_segments(segs, self.VOICES, max_chars=2500)
        # 3000 chars in 2500 budget → at least 2 chunks, each ≤ budget
        assert len(chunks) >= 2
        for c in chunks:
            assert c.chars <= 2500

    def test_drops_tag_only_segments(self) -> None:
        segs = [
            {"speaker": "NARRATOR", "text": "[pause]"},
            {"speaker": "NARRATOR", "text": "real text"},
        ]
        chunks = chunk_segments(segs, self.VOICES)
        # Tag-only segment was dropped
        assert len(chunks) == 1
        assert chunks[0].segments[0]["text"] == "real text"

    def test_unknown_speaker_falls_back(self) -> None:
        """Unknown speaker should fall through to MINOR / NARRATOR / first voice."""
        segs = [{"speaker": "UNKNOWN", "text": "hello"}]
        chunks = chunk_segments(segs, self.VOICES)
        assert len(chunks) == 1
        # Falls back to NARRATOR since no MINOR is defined.
        assert chunks[0].segments[0]["voice_id"] == "v_narr"

    def test_empty_voices_rejected(self) -> None:
        with pytest.raises(ValueError):
            chunk_segments([{"speaker": "X", "text": "y"}], {})

    def test_oversize_segment_splits_on_sentences(self) -> None:
        long_text = " ".join(f"Sentence number {i}." for i in range(300))
        assert len(long_text) > MAX_CHARS_PER_CALL
        segs = [{"speaker": "NARRATOR", "text": long_text}]
        chunks = chunk_segments(segs, self.VOICES, max_chars=1000)
        assert len(chunks) > 1
        for c in chunks:
            assert c.chars <= 1000 or len(c.segments) == 1  # single-sentence over-budget is OK

    def test_chars_count_matches_segments(self) -> None:
        segs = [{"speaker": "NARRATOR", "text": "hello world"}]
        chunks = chunk_segments(segs, self.VOICES)
        assert chunks[0].chars == len("hello world")


# ---------------------------------------------------------------------------
# chapter_marks
# ---------------------------------------------------------------------------


class TestChapterMarks:
    def test_cumulative_with_pause(self) -> None:
        rows = [(1, "One", 100.0), (2, "Two", 200.0), (3, "Three", 50.0)]
        marks = chapter_marks(rows, pause=2.0)
        assert marks[0].start == pytest.approx(0.0)
        assert marks[1].start == pytest.approx(100.0 + 2.0)
        assert marks[2].start == pytest.approx(100.0 + 2.0 + 200.0 + 2.0)

    def test_no_trailing_pause(self) -> None:
        """Last chapter must not have a post-pause in cumulative time."""
        rows = [(1, "A", 10.0), (2, "B", 20.0)]
        marks = chapter_marks(rows, pause=5.0)
        # Second mark starts at 10 + 5 = 15; total runtime therefore ends
        # at 35, not 40.
        assert marks[-1].start + marks[-1].duration == pytest.approx(35.0)

    def test_zero_pause(self) -> None:
        rows = [(1, "A", 10.0), (2, "B", 20.0)]
        marks = chapter_marks(rows, pause=0)
        assert marks[1].start == pytest.approx(10.0)

    def test_negative_pause_rejected(self) -> None:
        with pytest.raises(ValueError):
            chapter_marks([(1, "A", 10.0)], pause=-1.0)

    def test_negative_duration_rejected(self) -> None:
        with pytest.raises(ValueError):
            chapter_marks([(1, "A", -1.0)], pause=0)

    def test_ffmetadata_format_has_ffmetadata1_header(self) -> None:
        marks = chapter_marks([(1, "A", 10.0)], pause=0)
        out = format_chapter_marks_mp4chaps(marks)
        assert out.startswith(";FFMETADATA1\n")
        assert "[CHAPTER]" in out
        assert "title=A" in out

    def test_ffmetadata_timebase_is_ms(self) -> None:
        marks = chapter_marks([(1, "A", 1.5)], pause=0)
        out = format_chapter_marks_mp4chaps(marks)
        assert "START=0" in out
        assert "END=1500" in out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    def test_audio_validate_exits_nonzero_on_bad_script(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"segments": []}), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "autonovel.mechanical", "audio-validate", str(bad)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_audio_marks_cli_round_trip(self, tmp_path: Path) -> None:
        rows = [{"chapter": 1, "title": "A", "duration": 10.0},
                {"chapter": 2, "title": "B", "duration": 5.0}]
        rows_path = tmp_path / "rows.json"
        rows_path.write_text(json.dumps(rows), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "autonovel.mechanical", "audio-marks",
             str(rows_path), "--pause", "2"],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["marks"][1]["start"] == pytest.approx(12.0)
