---
name: autonovel:art-prompts
description: Author per-chapter art prompt files (one .md per chapter+surface) from outline + summary + visual_style + world.
argument-hint: "--book <short-name> [--chapters <range>] [--surface ornament|plate|scene-break] [--style lineart|full|symbolic] [--force]"
model_tier: light
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - shared/world.md
  - books/{book}/outline.md
  - books/{book}/art/visual_style.json
  - books/{book}/chapters/ch_*.summary.md
  - books/{book}/chapters/ch_*.md
writes:
  - books/{book}/art/prompts/ch{chapter:02d}_{surface}.md
context_mode: book
---

<purpose>
Today, `art-ornaments-all` builds its per-chapter image prompt
inline from the chapter's title + first ~400 words of prose, then
immediately calls the provider — the prompt itself is never written
to disk. The user can't preview, hand-edit, or feed it to a different
generator (Midjourney, ComfyUI, a hand-commissioned artist, etc.).

This command separates *prompt authoring* from *image generation*:

- `/autonovel:art-prompts` writes one prompt file per chapter.
- `/autonovel:art-ornaments-all` reads the prompt file when present,
  falls back to inline derivation when not.

The prompt file is a small markdown document with a motif sentence,
a one-line rationale, the rendered prompt body, the universal
constraints (white background / no text), and the style metadata
copied out of `visual_style.json`. Useful as a hand-edit target,
useful as input to a different image generator.

Outline + summary are richer motif sources than the first 400 words
of prose: they name the chapter's *turning point*, not just its
opening register. So this is also the right starting point for
plates and full art, not just small ornaments.

`model_tier: light` — the LLM only picks one or two motif phrases
per chapter. Cheap, fast, safe to re-run.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` is required. Optional:
   - `--chapters <range>` — one of `1-5`, `3,7,9`, `all`. Default
     `all`.
   - `--surface ornament|plate|scene-break` — default `ornament`.
     `ornament` is small + symbolic; `plate` is full-page art for
     hardback editions; `scene-break` is a minimal horizontal
     decoration between scenes.
   - `--style lineart|full|symbolic` — default `lineart` for
     `ornament` / `scene-break`, `full` for `plate`.
   - `--force` — overwrite an existing prompt file. Without
     `--force`, refuse to overwrite and surface "use --force to
     regenerate".

2. Use `file_read` on `books/{book}/art/visual_style.json`. If
   missing, surface `Run /autonovel:art-style --book {book} first`
   and stop. The visual style is the per-book single source of
   truth for palette / mood / ornament concept.

3. Use `file_read` on `shared/world.md` (first ~3000 words is
   plenty — we just need genre cues for the motif), and on
   `books/{book}/outline.md` (the whole file; the chapter section
   is the richest motif source).

4. Enumerate the target chapters. For each:

   a. `file_read` `books/{book}/chapters/ch_{chapter:02d}.summary.md`
      when present (the structured Plot / Cast / Threads /
      Story-time fields written by `/autonovel:summarize-chapter`).
      Fall back to `file_read` of the first ~400 words of
      `ch_{chapter:02d}.md` when no summary exists.

   b. **Pick a motif.** From the chapter section of `outline.md`
      + the summary's `Plot` field + relevant world details, pick
      one symbolic image that crystallises this chapter — the
      apothecary's cracked mortar, a single key laid horizontally,
      a wax seal half-broken. Prefer concrete physical objects
      over abstract concepts. If the chapter has no obvious
      anchor, fall back to a setting detail (a window with one
      shutter open, a candle burning to its base).

   c. **Build the rationale.** One sentence — *why* this motif
      for this chapter. Names the chapter's turning point
      explicitly so a reader of the prompt file can judge the
      pick.

   d. **Render the prompt body.** The actual generator-input
      string. Stitch together: motif sentence + style line from
      `visual_style.json :: art_style` + palette hint +
      universal constraints (`pure white background, single
      subject centred, no text, no border, no shadows`). For
      `--style lineart`, add `clean black ink line drawing,
      symbolic / iconic`; for `--style full`, add the colour
      palette + `painterly`; for `--style symbolic`, force
      single-subject framing and remove painterly markers.

   e. Use `file_write` on
      `books/{book}/art/prompts/ch{chapter:02d}_{surface}.md`
      with this exact structure:

      ```markdown
      # Chapter NN — {surface} art prompt

      ## Motif
      <one sentence naming the symbolic image>

      ## Rationale
      <one sentence — why this motif for this chapter>

      ## Prompt
      <the rendered generator-input string, multi-line as needed>

      ## Universal constraints
      - Pure white background.
      - No text on the image.
      - Single subject, centred; no overlapping elements.
      - Symbolic / iconic; not photorealistic.

      ## Style
      - art_style: <copied from visual_style.json>
      - palette: <copied from visual_style.json :: color_palette>
      - texture: <copied>
      - surface: {surface}
      - render_style: {style}

      ## Source inputs
      - outline section: ch{NN} (lines or section heading)
      - summary file: present|absent
      - world cues: <one short phrase, e.g. "venetian guild quarter">
      ```

      When the prompt file already exists and `--force` is not
      set, skip the chapter (count it under "skipped — already
      authored").

5. Print a one-screen summary table:

   ```
   chapter | surface | motif | status
   1       | ornament | cracked mortar | written
   2       | ornament | wax seal half-broken | written
   3       | ornament | (skipped — exists; use --force) |
   ```

   Highlight any chapter where the motif looks generic (e.g.
   "a candle", "a window") with a one-line `tip:` suggesting the
   user hand-edit before generation.
</workflow>

<acceptance>
- For each requested chapter, exactly one
  `books/{book}/art/prompts/ch{NN:02d}_{surface}.md` exists on
  success.
- Each prompt file contains the six sections above (Motif,
  Rationale, Prompt, Universal constraints, Style, Source inputs).
- Without `--force`, an existing prompt file is preserved
  verbatim (idempotent re-run is safe).
- No image provider is called. No `*.png` files are written. This
  command is prompt-authoring only.
- When `art/visual_style.json` is missing, no prompt files are
  written.
</acceptance>
