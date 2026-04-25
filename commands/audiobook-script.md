---
name: autonovel:audiobook-script
description: Parse chapters into speaker-attributed + emotion-tagged audiobook scripts.
argument-hint: "--book <short-name> [--chapters <N,M,...>] [--force]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - shared/characters.md
  - books/{book}/chapters/*.md
  - books/{book}/audiobook/voices.yaml
writes:
  - books/{book}/audiobook/scripts/ch{chapter:02d}_script.json
context_mode: book
---

<purpose>
Replace `gen_audiobook_script.py`. For each chapter, produce a JSON
array of `{speaker, text}` segments: every dialogue line attributed to
its speaker (quote marks stripped — the voice actor performs them),
every paragraph of narration as `NARRATOR`, and optional
`[audio tag]` prefixes to steer ElevenLabs v3 delivery.

Standard tier — the job is structured extraction with light emotional
judgement. The parser output is schema-validated by
`autonovel mechanical audio-validate` before the chapter's
script is written, so shape errors are caught at write time.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` is required. Optional:
   `--chapters 1,3,5` (default: every chapter) and `--force` (re-parse
   already-scripted chapters rather than skipping).

2. Use `file_read` on `project.yaml`, `shared/characters.md`, and
   `books/{book}/audiobook/voices.yaml` (if it exists). The voices
   file is authoritative for which speakers the TTS step can render;
   the parser refuses to invent new speaker names beyond what the
   voices file lists plus `NARRATOR`.

3. For each chapter in the target set:
   a. Use `file_read` on `books/{book}/chapters/ch_{chapter}.md`.
   b. Skip if `books/{book}/audiobook/scripts/ch{chapter:02d}_script.json`
      exists and `--force` was not passed.
   c. Parse the chapter into segments, applying these rules:
      - Narration = `NARRATOR`. Dialogue = the speaking character
        (resolve against `shared/characters.md`).
      - Strip surrounding quotation marks from dialogue.
      - "he said" / "she said" tags stay with the NARRATOR segment
        that follows the dialogue.
      - Scene breaks (`---`) become `{"speaker": "NARRATOR",
        "text": "[pause]"}`.
      - Chapter title becomes the first segment:
        `{"speaker": "NARRATOR", "text": "[slowly] Chapter N: <title>"}`.
      - Italicised internal thoughts stay with the character, tagged
        `[softly]` or `[whisper]`.
      - Emotional tags (`[nervous]`, `[firmly]`, `[gasp]`, etc.) are
        used *sparingly* — one tag per segment max, and most segments
        should carry none.
   d. Use `file_write` to save the JSON under
      `books/{book}/audiobook/scripts/ch{chapter:02d}_script.json`.
   e. Use `bash: autonovel mechanical audio-validate
      books/{book}/audiobook/scripts/ch{chapter:02d}_script.json
      books/{book}/audiobook/voices.yaml` to verify the shape and the
      speaker coverage. On a non-zero exit, surface the problem list
      and stop immediately — do not continue to the next chapter with
      a known-bad script.

4. Print a one-screen summary across all parsed chapters: total
   chapters, total segments, total characters, list of distinct
   speakers found, and the first chapter (if any) whose script
   failed validation.
</workflow>

<acceptance>
- One JSON script per target chapter is written under
  `books/{book}/audiobook/scripts/`.
- Every script passes `audio-validate` (shape + speaker coverage).
- No chapter file under `books/{book}/chapters/` is modified.
</acceptance>
