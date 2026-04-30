---
name: autonovel:extract-chapter-titles
description: Backfill 2-6 word evocative chapter titles into frontmatter for chapters drafted before titles became standard.
argument-hint: "--book <short-name> [--chapters <range>] [--force]"
model_tier: light
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - books/{book}/chapters/ch_*.md
  - books/{book}/chapters/ch_*.summary.md
writes:
  - books/{book}/chapters/ch_*.md
context_mode: book
---

<purpose>
Books drafted before the title-by-default shipped (autonovel
pre-2026-04-30) have no `title:` field in chapter frontmatter, so
typeset's TOC reads `Chapter I`, `Chapter II`, `…` rather than
`Chapter VII — The Apothecary's Mortar`. This command walks the
missing-title chapters, generates a 2-6 word evocative phrase per
chapter from its plot summary + opening prose, and writes it into
the frontmatter `title:` field.

Light tier — Haiku is good at evocative-phrase distillation from
short text, and the per-chapter context (just the summary's Plot
section + first 200 words of prose) is small. ~$0.001 per chapter
on light tier.

Pure mechanical inspector + LLM step — `autonovel mechanical
chapter-titles <book>` is the inspector that returns which
chapters need work; this slash-command runs the LLM step.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` defaults via
   `_begin`. Optional `--chapters <range>` limits the sweep
   (e.g. `--chapters 1-10` or `--chapters 5,7,12`); default is
   every chapter that needs backfill. `--force` regenerates
   titles even for chapters that already have one (use sparingly;
   the existing title is usually the right answer).

2. **Inspect.** Use `bash` to run:

   ```
   autonovel mechanical chapter-titles books/{book} --format json
   ```

   Parse the JSON. The `missing` list names chapters with no
   title at all. The `heading_only` list names chapters with a
   `# Heading` line but no frontmatter `title:` — these
   already work in typeset but moving the title into frontmatter
   is cleaner.

   Filter to the user's `--chapters` argument when present.
   Default behaviour:
     - Without `--force`: process the `missing` list only.
     - With `--force`: process every chapter in the `--chapters`
       range (or all when no range).

3. **Per-chapter LLM generation.** For each chapter to process:

   a. `file_read` the chapter file.
   b. `file_read` the chapter's summary file
      (`books/{book}/chapters/ch_NN.summary.md`) when present —
      its `**Plot:**` section is the best single input for a
      title.
   c. Generate a 2-6 word evocative title. Same constraints as
      `commands/draft.md` step 11:
        - Concrete object or phrase from the chapter's central
          beat — what the chapter is *about*, not a plot summary.
        - Examples: "The Apothecary's Mortar", "What Tommaso
          Knew", "Carnival Hours", "Salt and Saltpeter".
        - Avoid cliché ("The Beginning", "A New Hope").
        - Avoid POV-character names alone (the running header
          already shows POV).
        - Avoid generic abstractions ("Confrontation",
          "Decision").

   d. Use `file_write` to update the chapter file with the new
      `title:` field in frontmatter. Preserve every other
      frontmatter field verbatim. If the file already has a
      `# Heading` line as the first content line, the heading
      can stay (typeset prefers the frontmatter title; the
      heading is harmless).

4. Print a one-screen summary:

   ```
   📚 Backfilled chapter titles for {book}

   ch  1: "The Apothecary's Mortar"
   ch  2: "Salt and Saltpeter"
   …

   Wrote N chapter file(s); skipped M (already had titles).

   Verify: re-run `autonovel mechanical chapter-titles
   books/{book}` to confirm every chapter now reads
   `✅ frontmatter` rather than `❌ missing`.

   Then: /autonovel:typeset --book {book} surfaces the new titles
   in the TOC + chapter opening pages + running header.
   ```
</workflow>

<acceptance>
- For each processed chapter, the file's YAML frontmatter
  contains a non-empty `title:` field after the run.
- Every other frontmatter field is preserved verbatim
  (`book`, `chapter`, `pov`, `story_time`, `events`, `status`,
  `word_count`).
- Without `--force`, chapters that already have a title in
  frontmatter are not modified.
- Re-running `autonovel mechanical chapter-titles` after this
  command reports `❌ missing` for zero processed chapters.
</acceptance>
