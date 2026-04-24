---
name: autonovel:art-style
description: Derive a per-book visual style from world + voice. Writes visual_style.json.
argument-hint: "--book <short-name>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/world.md
  - books/{book}/voice.md
  - books/{book}/outline.md
writes:
  - books/{book}/art/visual_style.json
context_mode: book
---

<purpose>
Replace the pre-rewrite `gen_art.py style` step. Reads the world + the
book's voice + the first line of the outline (for the title), and emits
a compact JSON file that later art commands (`art-directions`,
`art-curate`, `art-ornaments-all`) treat as their single source of
truth for palette, mood, and per-surface concepts.

This is a creative task — drafting-class. `model_tier: heavy`.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` is required; anything else
   is a usage error — print a one-line reminder and stop.

2. Use `file_read` on `project.yaml` to confirm the book exists and pull
   `genre` for framing (a fantasy novel's visual language is not a
   historical mystery's). Use `file_read` on `shared/world.md` (at most
   the first ~5000 words), `books/{book}/voice.md` (both parts), and
   `books/{book}/outline.md` (first ~500 chars for the title line).

3. Draft a visual style JSON with these keys:
   - `art_style`: one-sentence illustration style.
   - `color_palette`: 5-7 specific colours, named concretely.
   - `texture`: dominant visual texture.
   - `mood`: visual mood.
   - `reference_artists`: 2-3 real artists whose style approximates this.
   - `cover_concept`: specific image for the cover, no spoilers.
   - `ornament_concept`: small symbolic chapter ornament brief.
   - `scene_break_concept`: minimal horizontal scene break.
   - `map_concept`: map style (may be `null` if the book has no map).

4. Use `file_write` to save the JSON under
   `books/{book}/art/visual_style.json`. Pretty-print with two-space
   indent; this file is small and meant for the user to skim.

5. Print a one-screen summary: each key and the first 80 chars of its
   value. That is the UX — the user gets a preview of the style they
   just locked in.
</workflow>

<acceptance>
- A JSON object is written to `books/{book}/art/visual_style.json`.
- The JSON parses and contains every key listed in step 3.
- No other files are modified.
</acceptance>
