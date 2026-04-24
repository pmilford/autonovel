---
name: autonovel:art-pick
description: Select one variant as the final art for a surface.
argument-hint: "--book <short-name> --surface cover|ornament|map|scene-break --variant <N>"
model_tier: light
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - books/{book}/art/picks.json
  - books/{book}/art/variants/{surface}_*.png
writes:
  - books/{book}/art/picks.json
  - books/{book}/art/{surface}.png
context_mode: book
---

<purpose>
Replace `gen_art.py pick`. Pure file operation — copies the chosen
variant to the canonical filename (`cover.png`, `ornament_reference.png`,
`map.png`, `scene_break.png`) and updates `picks.json`. No LLM work.

The `ornament` pick is special: it is the style reference for the
per-chapter ornament generation in `/autonovel:art-ornaments-all`, not
a finished ornament itself. We rename it to
`ornament_reference.png` on copy so callers cannot confuse it with a
per-chapter file.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. All three of `--book <short-name>`, `--surface`
   (one of `cover|ornament|map|scene-break`), and `--variant <N>` are
   required. Anything else is a usage error — print a one-line
   reminder and stop.

2. Use `file_read` on `books/{book}/art/picks.json`. If the variant
   file `books/{book}/art/variants/{surface}_NN.png` (two-digit N) does
   not exist, surface a single-line message listing the variants that
   do and stop.

3. Use `bash` to copy the variant to the canonical path
   `books/{book}/art/{surface}.png` — with the surface-specific rename
   rules below:
   - `cover` → `books/{book}/art/cover.png`
   - `ornament` → `books/{book}/art/ornament_reference.png` (not the
     literal `{surface}.png` — ornament's canonical name encodes that
     it is the *reference* for the per-chapter batch, not a chapter
     ornament itself).
   - `map` → `books/{book}/art/map.png`
   - `scene-break` → `books/{book}/art/scene_break.png`

4. Use `file_write` to update `picks.json` — set `picks[surface]` to
   `{"variant": <N>, "path": "<canonical path>"}`. Leave the `variants`
   block untouched.

5. Print the canonical path and byte count. For `ornament`, append
   `next: /autonovel:art-ornaments-all --book {book}` since the
   ornament pick is the reference style for the per-chapter batch.
</workflow>

<acceptance>
- The canonical image file exists at the mapped path.
- `picks.json` `picks[surface]` points at the chosen variant.
- The corresponding variant PNG is unchanged (copy, not move).
</acceptance>
