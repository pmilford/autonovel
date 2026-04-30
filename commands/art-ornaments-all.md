---
name: autonovel:art-ornaments-all
description: Generate a per-chapter ornament for every chapter, keyed to chapter content.
argument-hint: "--book <short-name> [--provider pollinations|fal|replicate|openai] [--chapters <N,M,...>]"
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
  - books/{book}/art/prompts/ch*_ornament.md
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
   `pollinations` for new projects / `fal` for legacy), `--chapters
   N,M,...` (comma-separated; default all).

2. Use `file_read` on `project.yaml`, `books/{book}/art/visual_style.json`,
   and `books/{book}/art/picks.json`. If `visual_style.json` is missing,
   surface "run `/autonovel:art-style --book {book}` first" and stop.

3. Resolve provider auth (or skip for pollinations):
   - `pollinations` → no key needed; the endpoint is open. Skip
     this step. **The right default for users who don't have or
     don't want to pay for an image-API key.**
   - `fal` → `FAL_KEY`.
   - `replicate` → `REPLICATE_API_TOKEN`.
   - `openai` → `OPENAI_API_KEY`.

   Missing paid-provider key → stop with a single-line message
   naming the env var, suggest switching to
   `--provider pollinations` for the free path. Do not fail
   silently.

4. Determine the reference image: `books/{book}/art/ornament_reference.png`
   if it exists. If not, print a one-line note that the set will not be
   style-anchored and continue.

5. Enumerate chapter files with `bash`: `ls books/{book}/chapters/ch_*.md`.
   Skip any chapter already in the `--chapters` exclusion if provided.

   Provider call shape:
   - `pollinations` → GET `https://image.pollinations.ai/prompt/
     <URL-encoded-prompt>?width=512&height=512&seed=<chapter-num>&nologo=true`.
     `curl -L -o <out>` streams the PNG. The seed is the chapter
     number so each chapter gets a deterministically-different
     ornament. No image-to-image (Pollinations doesn't support
     it); the reference image is a no-op for this provider —
     style coherence comes from the prompt instead.
   - `fal` / `replicate` / `openai` → image-to-image with the
     reference PNG, same shape as the pre-rewrite pipeline.

   For each chapter:
   - **Prefer the authored prompt file**:
     `books/{book}/art/prompts/ch{chapter:02d}_ornament.md`. When
     this file exists (the user ran `/autonovel:art-prompts` first
     and either accepted or hand-edited the result), `file_read`
     it and pull the body of the `## Prompt` section verbatim as
     the generator input. Do not regenerate the motif from prose —
     respect the authored prompt as-is.
   - **Fall back to inline derivation** when no prompt file
     exists: `file_read` the chapter to get its title line and
     first ~400 words. Pick a symbolic motif from that content
     (e.g. "a cracked bell silhouette", "a wax seal", "a single
     key laid horizontally"). Build the prompt: motif +
     `visual_style.json :: art_style` + palette + "symbolic,
     small, white background, no text".
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
- The prompt for each chapter is derived from that chapter's own text
  or from `books/{book}/art/prompts/ch{NN}_ornament.md` when present —
  not from a single series-wide template.
- When a per-chapter authored prompt file exists, the command uses
  its `## Prompt` body verbatim (no re-derivation). Use
  `/autonovel:art-prompts` to author or hand-edit those files first.
- If the provider API key is missing, no PNGs are written.
</acceptance>
