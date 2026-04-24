---
name: autonovel:art-vectorize
description: Convert ornament + scene-break PNGs to SVG via potrace.
argument-hint: "--book <short-name> [--target <stem>]"
model_tier: light
allowed-tools:
  - file_read
  - bash
reads:
  - books/{book}/art/*.png
writes:
  - books/{book}/art/svg/*.svg
context_mode: book
---

<purpose>
Replace `gen_art.py vectorize`. Pure mechanical — call `potrace` on
each PNG that belongs in the vector pipeline (all chapter ornaments
and the scene break; NOT the cover or map). No LLM work.

Emits SVGs under `books/{book}/art/svg/` so the typeset PDF can use
the cleaner vector versions with `\includegraphics{ornament_chNN.pdf}`
(the user converts `.svg → .pdf` with `rsvg-convert` or `inkscape`
before typesetting; the conversion step is documented in the postamble
footer so the user can do it by hand or via `/autonovel:typeset
--convert-vectors`).
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` is required. Optional
   `--target <stem>` limits the conversion to a single file (e.g.
   `--target ornament_ch05` only vectorises that ornament).

2. Use `bash: which potrace` to confirm the tool is installed. If not,
   surface a single-line install hint (`apt install potrace` /
   `brew install potrace`) and stop without writing anything.

3. Collect the target file list:
   - No `--target`: every `books/{book}/art/ornament_ch*.png` plus
     `books/{book}/art/scene_break.png` if it exists.
   - With `--target <stem>`: just `books/{book}/art/{stem}.png` (error
     out if the file is missing).

4. For each PNG, use `bash` to:
   - Convert to a 1-bit PBM via `python3 -c "from PIL import Image;
     img = Image.open('<png>').convert('L').point(lambda x: 0 if x < 180
     else 255, '1'); img.save('<pbm>')"`.
   - Run `potrace <pbm> -s -o <svg> --turdsize 4 --opttolerance 0.2`.
   - Unlink the temp PBM.

5. Print a one-screen summary: one line per file with input path →
   output path + byte count, or FAILED + the potrace error if it
   tripped. Skip the "PDF conversion" step — that is a separate
   manual step the typeset command handles.
</workflow>

<acceptance>
- For every PNG in the target set (excluding cover + map), a matching
  SVG exists under `books/{book}/art/svg/`.
- Temporary PBMs created during conversion are removed before the
  command exits.
- If `potrace` is not installed, no SVGs are written and the stop
  message names the package to install.
</acceptance>
