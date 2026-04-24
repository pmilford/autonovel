---
name: autonovel:audiobook-generate
description: Render a chapter's audio from its script via ElevenLabs, with multi-take + best-take selection.
argument-hint: "--book <short-name> --chapter <N> [--takes 3] [--test]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - books/{book}/audiobook/scripts/ch{chapter:02d}_script.json
  - books/{book}/audiobook/voices.yaml
writes:
  - books/{book}/audiobook/chapters/ch_{chapter}.mp3
  - books/{book}/audiobook/chapters/ch_{chapter}_manifest.json
context_mode: book
---

<purpose>
Replace `gen_audiobook.py` per-chapter generation. Two improvements
over the pre-rewrite version:

  1. **Multi-take per chunk.** Each API chunk is generated N times
     (default 3) and an LLM listener picks the best take. The pre-
     rewrite version used whatever came back first; when ElevenLabs
     mispronounced or stumbled, the user had to re-run the whole
     chapter.
  2. **Chunking via the mechanical module.** `/autonovel:audiobook-
     script` wrote the script; `python -m autonovel.mechanical
     audio-chunk` packs it into TTS-budget chunks. The command never
     reimplements chunking.

Standard tier because the best-take judgement is an LLM call (one per
chunk, listening to short takes). The TTS calls themselves are not
writer-model traffic.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` and `--chapter <N>` are
   required. Optional `--takes` (default 3; set to 1 to disable
   best-take and run exactly one pass for speed) and `--test` (only
   the first 10 segments of the chapter — for voice / tagging
   calibration).

2. Resolve `ELEVENLABS_API_KEY`. Missing → stop naming the env var.
   Use `file_read` on the chapter script and voices file; missing
   script → "run `/autonovel:audiobook-script --book {book}
   --chapters {chapter}` first".

3. Chunk the script with `bash`:
   `python -m autonovel.mechanical audio-chunk
   books/{book}/audiobook/scripts/ch{chapter:02d}_script.json
   books/{book}/audiobook/voices.yaml`. Parse the JSON output. In
   `--test` mode, keep only the first 10 segments before chunking.

4. For each chunk:
   a. Call `text_to_dialogue.convert(inputs=chunk.segments)` up to
      `--takes` times. Retry with exponential backoff on transient
      failures (10s → 20s) as in the pre-rewrite version.
   b. If `--takes > 1`, send the takes plus the segment script to the
      LLM with a "which take sounds most natural" prompt and pick
      the winner. Keep the non-winner takes as
      `books/{book}/audiobook/chapters/ch_{chapter}_chunkNN_takeK.mp3`
      under a hidden `.rejected/` subdir so the user can audit.
   c. Write the winner's audio into a running concatenation buffer.

5. On all chunks done, write the concatenated MP3 to
   `books/{book}/audiobook/chapters/ch_{chapter}.mp3` (adding `_test`
   if `--test`). Also write
   `books/{book}/audiobook/chapters/ch_{chapter}_manifest.json`
   recording per-chunk outcomes (succeeded/failed; which take won;
   sizes). The `audiobook-assemble` command reads this manifest to
   know whether the chapter is complete.

6. Print a one-screen summary: chunk success/fail counts, winning
   takes histogram (take 1 won X times, take 2 won Y times — tells
   the user whether multi-take is pulling its weight), size, and
   the chapter's total runtime estimate from chunk byte lengths.
</workflow>

<acceptance>
- `books/{book}/audiobook/chapters/ch_{chapter}.mp3` exists on
  success.
- `ch_{chapter}_manifest.json` records every chunk as either
  `succeeded` with a winning take index or `failed` with the last
  error message.
- `--takes 1` produces the exact same chapter MP3 as the pre-rewrite
  single-take path (minus the chunking improvements).
</acceptance>
