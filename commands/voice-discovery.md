---
name: autonovel:voice-discovery
description: Fill the book-specific fingerprint in Part 2 of the book's voice.md.
argument-hint: "--book <short-name>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/world.md
  - shared/characters.md
  - books/{book}/seed.txt
  - books/{book}/outline.md
  - books/{book}/voice.md
writes:
  - books/{book}/voice.md
context_mode: book
---

<purpose>
Populate Part 2 of `books/{book}/voice.md` — the book-specific fingerprint.
Part 1 is series-wide and usually handwritten; leave it alone. Part 2 is
the per-book register that every chapter's prose will match: sentence
rhythm, sensory palette, POV distance, what the narrator notices and what
they refuse to name.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `--book <short-name>`. If missing, stop and
   surface a one-line usage reminder. `--force` permits overwriting an
   already-populated Part 2.

2. Use `file_read` on `project.yaml`. Resolve the book entry and its POV.
   Capture `genre` and `period` — the voice has to sit inside the period's
   register.

3. Use `file_read` on `shared/world.md` and `shared/characters.md`. The
   POV's class, era, and profession all constrain vocabulary.

4. Use `file_read` on `books/{book}/seed.txt` and
   `books/{book}/outline.md`. A seed about grief reads differently from a
   seed about appetite; the outline's pacing shapes cadence.

5. Use `file_read` on `books/{book}/voice.md`. Keep Part 1 (series voice)
   verbatim. If Part 2 has substantive content (more than the template
   placeholder) and `--force` was not supplied, stop.

6. Draft Part 2. Keep it concrete and usable by a drafting model. Include:
   - sentence-length tendency and variance,
   - POV distance (close, middle, telescope), tense,
   - 6–12 word "palette" — sensory motifs the narrator returns to,
   - at least three "do not" rules specific to this POV (anachronisms to
     avoid, emotional registers the narrator refuses, punctuation habits
     to resist),
   - a two-sentence sample paragraph in-voice as a reference.

7. Use `file_write` to replace `books/{book}/voice.md` with Part 1
   (preserved verbatim) + the new Part 2 under its existing heading
   + Part 3 (preserved verbatim if present — see step 7a).

7a. **Preserve Part 3 (Custom rubric) verbatim.** If the existing
    voice.md contains a `## Part 3 — Custom rubric` section, keep
    its body byte-for-byte. Part 3 holds book-specific scoring
    criteria the user authored (or left as the placeholder); this
    command must never overwrite or "regenerate" it. The standard
    template's commented-out placeholder is preserved unchanged
    when no real content has been added. If voice.md has no Part
    3 section at all (older books from before the custom-rubric
    contract), append the template's Part 3 placeholder at the
    end so the surface exists for the user to fill in later.
</workflow>

<acceptance>
- `books/{book}/voice.md` still contains a `## Part 1` section matching
  what was there before this run.
- `## Part 2 — Book-specific fingerprint` (or `## Part 2 — Book
  fingerprint`) now contains concrete guidance: sentence-length guidance,
  POV distance, at least one palette line, and at least one `do not` rule.
- Part 2 is not empty and not only the template placeholder comment.
- A `## Part 3 — Custom rubric` section exists in the file (either
  preserved verbatim from a prior version or appended from the
  template placeholder). Its body is unchanged from the input.
</acceptance>
