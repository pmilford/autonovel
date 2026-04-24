---
name: autonovel:cover-composite
description: Composite title + author text over the picked cover art (front only).
argument-hint: "--book <short-name> [--preset auto|dark|light] [--title X] [--author Y] [--subtitle Z]"
model_tier: light
allowed-tools:
  - file_read
  - bash
reads:
  - project.yaml
  - books/{book}/art/cover.png
writes:
  - books/{book}/art/cover_titled.png
context_mode: book
---

<purpose>
Replace `gen_cover_composite.py`. Renders crisp title + subtitle +
author text over the front-cover art using PIL — no AI text artifacts,
full typography control. This is the e-book / thumbnail cover; the
print wraparound lives in `/autonovel:cover-print`.

Light tier — pure PIL, no LLM.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` is required. Optional:
   `--title`, `--author`, `--subtitle` (default `"A Novel"`), `--preset
   auto|dark|light` (default `auto` — the script samples the top and
   bottom of the art and picks light-text-on-dark-band or
   dark-text-on-light-band accordingly).

2. Use `file_read` on `project.yaml` to resolve defaults for the three
   text fields if the user did not pass them: the book's display title
   is `books[{book}].title` or `project.yaml :: series_name` when the
   book doesn't carry its own title; the author comes from `author` at
   the project top level. If neither is set, use the book shortname and
   "Unknown" respectively and print a warning.

3. Confirm the cover art exists with `file_read` on
   `books/{book}/art/cover.png`. If missing, surface
   "run `/autonovel:art-pick --book {book} --surface cover` first" and
   stop.

4. Use `bash` to invoke a single-line PIL script that:
   - Loads the art, samples top+bottom brightness to auto-choose preset.
   - Uses `fc-match` to find EB Garamond (bold / regular / italic),
     falling back to Liberation Serif. Warn if neither is installed
     but continue with PIL's default font rather than failing outright.
   - Lays out title, author, subtitle with shadow-on-band for
     readability. Hard-code the layout from `gen_cover_composite.py`
     verbatim — the Bells production validated those proportions.
   - Saves to `books/{book}/art/cover_titled.png`.

   The exact single-line form is:
   ```
   python3 -c "from autonovel.export.cover import composite_cover; composite_cover(book='{book}', title='{title}', author='{author}', subtitle='{subtitle}', preset='{preset}')"
   ```
   `autonovel.export.cover` is shipped with the wheel; do not attempt
   to inline the ~150-line PIL script into this command body. (PR 9
   polishes the CLI surface further; the module lives at
   `src/autonovel/export/cover.py`.)

5. Print the output path + byte count + the preset that was actually
   used (so the user can re-run with `--preset light|dark` if auto
   picked the wrong one).
</workflow>

<acceptance>
- `books/{book}/art/cover_titled.png` exists on success.
- The command runs with no writer-model tokens — no LLM call.
- If the cover art is missing, no file is written and the stop message
  names the command to run first.
</acceptance>
