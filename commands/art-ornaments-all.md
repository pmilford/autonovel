---
name: autonovel:art-ornaments-all
description: Generate a per-chapter ornament for every chapter, keyed to chapter content.
argument-hint: "--book <short-name> [--provider fal] [--chapters <N,M,...>]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - books/{book}/art/visual_style.json
  - books/{book}/art/picks.json
  - books/{book}/art/ornament_reference.png
  - books/{book}/chapters/*.md
writes:
  - books/{book}/art/ornament_ch*.png
context_mode: book
---

<purpose>
Replace `gen_art.py ornaments-all`. Unlike the pre-rewrite version —
which used a single generic style prompt for every chapter — this
command reads each chapter's opening so the ornament can reference
chapter content (the sound motif for a bell chapter, a key for a lock
chapter, etc.).

If `books/{book}/art/ornament_reference.png` exists (i.e. the user has
run `/autonovel:art-pick --surface ornament`), provider calls use
image-to-image with that reference so the whole set looks like a
coherent series. Otherwise plain text-to-image is fine — just noisier.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` is required. Optional:
   `--provider` (defaults to `project.yaml :: image.provider` then
   `fal`), `--chapters N,M,...` (comma-separated; default all).

2. Use `file_read` on `project.yaml`, `books/{book}/art/visual_style.json`,
   and `books/{book}/art/picks.json`. If `visual_style.json` is missing,
   surface "run `/autonovel:art-style --book {book}` first" and stop.

3. Resolve the provider API key. Missing key → stop with a single-line
   message naming the env var (`FAL_KEY` / `REPLICATE_API_TOKEN` /
   `OPENAI_API_KEY`). Do not fail silently — the user needs to know.

4. Determine the reference image: `books/{book}/art/ornament_reference.png`
   if it exists. If not, print a one-line note that the set will not be
   style-anchored and continue.

5. Enumerate chapter files with `bash`: `ls books/{book}/chapters/ch_*.md`.
   Skip any chapter already in the `--chapters` exclusion if provided.
   For each chapter:
   - `file_read` the chapter to get its title line and first ~400
     words. Pick a symbolic motif from that content (e.g. "a cracked
     bell silhouette", "a wax seal", "a single key laid horizontally").
   - Build the prompt: motif + `visual_style.json :: art_style` +
     palette + "symbolic, small, white background, no text".
   - Shell out to the provider (image-to-image with the reference PNG
     if available, otherwise text-to-image), save the result to
     `books/{book}/art/ornament_ch{chapter:02d}.png` (two-digit).
   - Pause a second between calls to stay under rate limits.

6. Print a one-screen summary: one line per chapter with `Ch NN → path
   (bytes)`. Highlight any chapter whose prompt reused the motif of
   the previous chapter — that is a signal to hand-tune the
   reused motifs.
</workflow>

<acceptance>
- For every chapter file under `books/{book}/chapters/ch_*.md` (or the
  `--chapters` subset), a matching
  `books/{book}/art/ornament_ch{chapter:02d}.png` exists on success.
- The prompt for each chapter is derived from that chapter's own text,
  not a single series-wide template.
- If the provider API key is missing, no PNGs are written.
</acceptance>
