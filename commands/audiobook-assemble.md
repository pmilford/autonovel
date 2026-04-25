---
name: autonovel:audiobook-assemble
description: Stitch chapter MP3s into a single audiobook with chapter marks.
argument-hint: "--book <short-name> [--format mp3|m4b] [--pause 2.0]"
model_tier: light
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - books/{book}/audiobook/chapters/ch_*.mp3
  - books/{book}/audiobook/chapters/*_manifest.json
  - books/{book}/audiobook/scripts/ch*_script.json
writes:
  - books/{book}/audiobook/full_audiobook.mp3
  - books/{book}/audiobook/full_audiobook.m4b
  - books/{book}/audiobook/chapter_marks.json
context_mode: book
---

<purpose>
Replace `gen_audiobook.py --assemble`. Two improvements:

  1. Proper chapter marks via
     `autonovel mechanical audio-marks`. The pre-rewrite
     version concatenated chapter MP3s with no marks, so chapter
     navigation in any player was broken.
  2. Optional `m4b` output (the audiobook-native container with
     embedded chapter ledger via `ffmetadata`), requiring `ffmpeg`.

Light tier — no LLM.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` is required. Optional
   `--format mp3|m4b` (default `mp3` — the universal container;
   `m4b` needs `ffmpeg`), `--pause <seconds>` (default 2.0 seconds
   of silence between chapters — matches the mechanical module
   default).

2. Enumerate chapter MP3s with `bash: ls
   books/{book}/audiobook/chapters/ch_*.mp3 | sort`. Skip any file
   whose sibling `_manifest.json` reports failed chunks (partial
   chapter). If fewer than one chapter is clean, stop with a
   single-line message listing what is missing.

3. Derive per-chapter runtimes with `bash` via a single `python3 -c
   "from pydub import AudioSegment; import sys, json; print(json.dumps([...]))"` that opens each
   clean chapter MP3 and emits `[{chapter, title, duration}]`. Titles
   come from `books/{book}/audiobook/scripts/ch*_script.json` — each
   chapter's script carries the title in its top-level `title` key. If `pydub` is not
   installed, fall back to `ffprobe -v 0 -show_entries
   format=duration -of csv=p=0 <path>` for the durations.

4. Compute chapter marks with `bash: autonovel mechanical
   audio-marks <rows.json> --pause <pause> --format ffmetadata`.
   Save both the JSON mark list and the ffmetadata text.

5. `--format mp3`: concatenate the chapter MP3s (interspersed with
   `--pause` seconds of silence generated on the fly via
   `pydub.AudioSegment.silent(duration=...)`) into
   `books/{book}/audiobook/full_audiobook.mp3`. Emit
   `chapter_marks.json` alongside; players with external cue support
   can consume it.

6. `--format m4b`: use `ffmpeg -i concat:... -i <ffmetadata> -map_metadata 1
   -c:a aac -b:a 64k <out.m4b>` to produce the m4b with embedded
   chapter marks. If `ffmpeg` is not installed, stop with an install
   hint — do not silently fall back to mp3.

7. Print a one-screen summary: total runtime, size, chapter count,
   format, and whether marks are embedded (m4b) or external JSON
   (mp3).
</workflow>

<acceptance>
- `books/{book}/audiobook/full_audiobook.mp3` (and, if requested,
  `full_audiobook.m4b`) exists.
- `chapter_marks.json` lists every included chapter's start time in
  cumulative seconds.
- Chapters whose manifest reports failed chunks are excluded from the
  assembled audiobook and surfaced in the summary.
</acceptance>
