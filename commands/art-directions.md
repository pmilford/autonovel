---
name: autonovel:art-directions
description: Generate N radically different art-direction prompts for one surface.
argument-hint: "--book <short-name> --surface cover|ornament|map|scene-break [--n 4]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/world.md
  - books/{book}/art/visual_style.json
writes:
  - books/{book}/art/directions/{surface}.json
context_mode: book
---

<purpose>
Replace `gen_art_directions.py`. Given a visual style and a target
surface, emit N *genuinely different* art direction prompts so that the
later `art-curate` step has variety to pick from. The Bells production
learned that varying one concept gives four copies of the same idea —
this step generates across abstraction, composition, medium, and palette
axes so the curate pass has real choices.

Heavy tier because the job is creative brief authoring, not mechanical
listing.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` and `--surface <one of
   cover|ornament|map|scene-break>` are required; `--n <int>` defaults
   to 4 (good variety without blowing an image budget). Anything else is
   a usage error — print a one-line reminder and stop.

2. Use `file_read` on `project.yaml` to confirm the book and pull
   `genre`. Use `file_read` on `books/{book}/art/visual_style.json`; if
   missing, surface "run `/autonovel:art-style --book {book}` first" and
   stop. For `map`, also load `shared/world.md` (first ~3000 chars) so
   the directions reference real locations.

3. Draft N direction objects, each with `direction` (one-word label),
   `concept` (one-sentence image), `medium` (ink wash, linocut,
   watercolor, digital collage, etc.), and `prompt` (the detailed
   image-generation prompt, 2-3 sentences, with the universal
   constraints appended — "no text, no lettering" for covers;
   "white background, no text" for ornaments and scene-breaks).

   Explicitly span these axes so the N variants read like work from
   different designers:
   - Abstraction: photorealistic → symbolic → pure abstract.
   - Composition: figure / landscape / close-up / typographic / texture.
   - Medium: painting / printmaking / ink / digital / collage.
   - Palette: full / monochrome / limited / high-contrast.

4. Use `file_write` to save the JSON array to
   `books/{book}/art/directions/{surface}.json`. This is the artifact
   `/autonovel:art-curate` consumes.

5. Print a one-screen summary: for each direction, label + concept
   (first 80 chars) + medium.
</workflow>

<acceptance>
- A JSON array of length `--n` is written to
  `books/{book}/art/directions/{surface}.json`.
- Every direction has the four keys listed in step 3.
- No two directions share the same `direction` label.
</acceptance>
