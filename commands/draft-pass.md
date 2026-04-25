---
name: autonovel:draft-pass
description: Draft a range of chapters end-to-end without per-chapter human input — same quality as /autonovel:draft, fewer keystrokes.
argument-hint: "--chapters <range> [--book <name>] [--skip-eval] [--retry-below <score>]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
  - task
reads:
  - project.yaml
  - shared/world.md
  - shared/characters.md
  - shared/canon.md
  - shared/events.md
  - shared/research/notes/*.md
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_*.summary.md
writes:
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
  - books/{book}/eval_logs/ch{chapter:02d}_eval.json
  - books/{book}/pending_canon.md
context_mode: book
---

<purpose>
Draft a range of chapters in one invocation. For each chapter in the
requested range, in ascending chapter-number order, performs:

  1. `draft N`        — same workflow as `/autonovel:draft`
  2. `evaluate N`     — score the new draft (skippable)
  3. `draft N` retry  — if score < `--retry-below`, retry once

This is the "I have an outline and want chapters 1 through 10 written
unattended" command. Quality of each chapter is **identical** to
running `/autonovel:draft N` ten times in a row — same model
(`model_tier: standard` → Sonnet), same context, same prompt. The
sweep just amortises the lock + preamble overhead and skips the
per-chapter human inspection point.

When NOT to use this: early in a new series when you're still
calibrating voice. Per-chapter `/autonovel:draft` lets you read
chapter 1, refine voice via `/autonovel:revoice`, and only advance
once you're happy. draft-pass plows through all N chapters against
whatever voice the foundation produced — so a bad voice
calibration becomes a bad first draft of the whole book.

When TO use this: foundation is solid, voice is set, you want
forward progress to first-draft completion. The Bells motto applies:
"forward progress over perfection." Revise after.

Sequential only. Drafts cannot run in parallel because chapter N+1's
draft reads chapter N's prose (`autonovel _tail-chapter --book {book}
--chapter {N-1}`) and chapter N's summary file (rolling continuity).
Both are written by chapter N's draft completion. Parallel drafting
would have N+1 starting before N's outputs exist.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Required: `--chapters <range>`. Range can be
   `N-M` (inclusive), `N,M,K` (comma-separated), or `all` (every
   chapter named in the outline that doesn't already have a chapter
   file). Optional: `--book` (defaults via `_begin`),
   `--skip-eval` (drop the per-chapter evaluate step), and
   `--retry-below <score>` (if a chapter's eval score is below
   this, redraft once before moving on; default 6.0 from
   `project.yaml :: defaults.chapter_threshold`). Missing
   `--chapters` → stop with a one-line usage hint.

2. Use `file_read` on `project.yaml` to resolve the book entry,
   `pov`, and `defaults.chapter_target_words` /
   `defaults.chapter_threshold`. Read `books/{book}/outline.md`
   and identify which chapter numbers are defined; resolve `all`
   to the list of outlined chapters that don't already have a
   chapter file in `books/{book}/chapters/`.

3. For each chapter N in the resolved range, **strictly in
   ascending chapter-number order** (drafts MUST be sequential —
   N+1 cannot start before N's prose and summary exist):

   a. **draft N**: reproduce the workflow of `/autonovel:draft N`
      inline — same context bundle (project.yaml, world,
      characters, canon, events, research notes the outline
      entry names, voice, prior summaries via
      `books/{book}/chapters/ch_*.summary.md`, prior chapter tail
      via `autonovel _tail-chapter --book {book} --chapter {N-1}
      --words 1000`). Write
      `books/{book}/chapters/ch_{N:02d}.md` with frontmatter and
      `books/{book}/chapters/ch_{N:02d}.summary.md` with the
      150–250 word continuity summary. Append candidate canon
      facts to `books/{book}/pending_canon.md`.

   b. **evaluate N** *(skip if `--skip-eval`)*: reproduce the
      workflow of `/autonovel:evaluate --chapter N`. Write
      `books/{book}/eval_logs/ch{N:02d}_eval.json`. Read the
      `overall_score`.

   c. **retry once if score is low**: if the score is below
      `--retry-below` (default `chapter_threshold`), repeat (a)
      once with the eval's `top_3_revisions` folded into the
      drafter's input ("the prior attempt scored X; address these
      specific weaknesses"). Re-evaluate after the retry. Move on
      either way — do not loop further. Forward progress over
      perfection.

   **Critical: do NOT call `autonovel _begin` or `autonovel _end`
   for any sub-step.** This command holds the series lock for the
   entire range — its own preamble already ran. Sub-steps that
   tried to acquire the lock would deadlock.

   After each chapter finishes, print one line:

   ```
   [ch N] draft: <words>w | eval: <score> | <ok | retried | failed>
   ```

   so the user has live progress. If a chapter's draft errors
   (e.g. outline entry missing for that chapter number), log the
   failure and continue to the next chapter.

4. After the loop completes, print a summary table:

   ```
   chapter | words | score | status
   --------|-------|-------|---------
        1  | 3100  |  7.4  | ok
        2  | 2950  |  6.1  | ok (retried once)
        3  | 3200  |  6.8  | ok
   ```

   Append a one-paragraph headline assessment.

5. The postamble's standard footer recommends the next step.
   Common cases:
   - All chapters ≥ threshold → `/autonovel:reader-panel --book
     {book}` (book-wide review) or `/autonovel:revision-pass
     --chapters all` (sweep revision).
   - Some chapters below threshold → `/autonovel:revision-pass
     --chapters <those>` to address the weakest.
   - `pending_canon.md` accumulated entries from the drafts →
     `/autonovel:promote-canon` first.
</workflow>

<files-touched>
This sweep delegates to the same set of files `/autonovel:draft`
touches for each chapter in the range, plus the per-chapter eval log.

Reads:
- `project.yaml`
- `shared/world.md`, `shared/characters.md`, `shared/canon.md`,
  `shared/events.md`
- `shared/research/notes/*.md` (when the outline names them)
- `books/{book}/voice.md`, `books/{book}/outline.md`
- `books/{book}/chapters/ch_*.summary.md` (rolling continuity)
- `books/{book}/chapters/ch_{chapter}.md` (during retry, to reread)

Writes (per chapter in range):
- `books/{book}/chapters/ch_{chapter}.md`
- `books/{book}/chapters/ch_{chapter}.summary.md`
- `books/{book}/eval_logs/ch{chapter:02d}_eval.json`
- `books/{book}/pending_canon.md` (drafts append candidate facts)
</files-touched>

<acceptance>
- For every chapter N in the resolved range,
  `books/{book}/chapters/ch_{N:02d}.md` exists, parses YAML
  frontmatter, and is at least 2000 words.
- For every chapter N, `books/{book}/chapters/ch_{N:02d}.summary.md`
  exists and is 100–400 words.
- Unless `--skip-eval` was passed, every chapter has a fresh
  `books/{book}/eval_logs/ch{N:02d}_eval.json`.
- The summary table is printed in the postamble footer.
- Drafts ran in strict ascending chapter-number order — chapter N+1's
  modification time is later than chapter N's.
</acceptance>
