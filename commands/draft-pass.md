---
name: autonovel:draft-pass
description: Draft a range of chapters end-to-end with per-chapter eval + revise-on-low-score + canon promotion. Single-button "write the rest of the book."
argument-hint: "--chapters <range> [--book <name>] [--retry-below <score>] [--no-revise-low] [--no-anachronism] [--no-promote] [--skip-eval]"
model_tier: heavy
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
  - shared/period_bans.txt
  - shared/research/notes/*.md
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_*.summary.md
  - books/{book}/eval_logs/ch{chapter:02d}_eval.json
  - books/{book}/edit_logs/ch{chapter:02d}_anachronism.md
writes:
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
  - books/{book}/eval_logs/ch{chapter:02d}_eval.json
  - books/{book}/edit_logs/ch{chapter:02d}_anachronism.md
  - books/{book}/briefs/ch{chapter:02d}.md
  - books/{book}/pending_canon.md
  - shared/canon.md
context_mode: book
---

<purpose>
The "let it write the rest of the book" command. Drafts a range of
chapters end-to-end, fixes low-scoring chapters with brief+revise,
runs anachronism checks, and promotes pending canon at the end so
the final state is coherent — `shared/canon.md` reflects everything
the sweep discovered, every chapter is at or above threshold (or
explicitly flagged as below), and continuity summaries are fresh.

Per chapter, in ascending chapter-number order, sequentially:

  1. `draft N`              — full /autonovel:draft workflow
                              (writes ch_NN.md, ch_NN.summary.md,
                              appends pending_canon)
  2. `check-anachronism N`  — period-vocabulary + LLM semantic check
                              (skip via --no-anachronism)
  3. `evaluate N`           — score the new draft (skip via --skip-eval)
  4. **If score < threshold** AND --no-revise-low NOT set:
     a. `brief N --from auto`   — synthesize revision brief
     b. `revise N`              — rewrite per the brief; regenerates
                                  the chapter summary
     c. `evaluate N` again      — re-score
     d. keep whichever version scored higher; the other is in the
        checkpoint and recoverable via autonovel rollback

After every chapter in the range completes:

  5. **`promote-canon`**     — fold accumulated pending_canon entries
                              into shared/canon.md (skip via
                              --no-promote). Research-tagged entries
                              still win contradictions per the standard
                              promote-canon discipline.

Sequential only — drafts cannot run in parallel because chapter N+1's
draft reads chapter N's prose and summary. Same per-chapter
*drafting* quality as `/autonovel:draft N` repeated; the wrap is
about adding the immediate-fix-on-low-score loop and the canon
propagation that makes the *whole-book* result coherent.

When NOT to use this:

- Early in a series (chapters 1-3) when you're calibrating voice.
  Use per-chapter `/autonovel:draft` so you can fix voice before
  drift compounds.
- When you need a heavy revision pass: that's
  `/autonovel:revision-pass`, which adds adversarial-edit +
  reader-panel + multi-cycle iteration. draft-pass is a one-pass
  command; revision-pass is the multi-pass deepener.

When TO use this:

- Foundation is solid. Voice is set. You want a coherent
  first-draft-plus-immediate-fix of every remaining chapter and
  you'd rather review the whole book at once afterwards than each
  chapter in isolation.
- After a major change (added a character, restructured a chapter)
  and you want to redraft a range with the new context.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Required: `--chapters <range>`.
   Range can be `N-M` (inclusive), `N,M,K` (comma-separated), or
   `all` (every chapter named in the outline that lacks a chapter
   file). Optional flags:
     - `--book` (defaults via `_begin`)
     - `--retry-below <score>` (default project.yaml::defaults
       .chapter_threshold; below this, the revise loop fires)
     - `--no-revise-low` (skip step 4; just redraft once on low
       score)
     - `--no-anachronism` (skip step 2)
     - `--no-promote` (skip step 5)
     - `--skip-eval` (skip steps 3 and 4 entirely; pure drafting)
   Missing `--chapters` → stop with usage hint.

2. Use `file_read` on `project.yaml`. Resolve the book entry, `pov`,
   `defaults.chapter_target_words`, `defaults.chapter_threshold`.
   Read `books/{book}/outline.md` to identify chapter numbers
   defined; resolve `all` to outlined chapters that lack a chapter
   file.

3. **For each chapter N in the resolved range, in ascending order**
   (drafts MUST be sequential — N+1 reads N's prose and summary):

   a. **Draft N**: reproduce the workflow of `/autonovel:draft N`
      inline — same context bundle (project.yaml, world,
      characters, canon, events, research notes the outline names,
      voice, prior summaries, prior chapter tail via
      `autonovel _tail-chapter --book {book} --chapter {N-1}
      --words 1000`). Write `books/{book}/chapters/ch_{N:02d}.md`
      with frontmatter + the 150-250 word
      `books/{book}/chapters/ch_{N:02d}.summary.md`. Append
      candidate canon facts to `books/{book}/pending_canon.md`.

   b. **Anachronism check** (skip if `--no-anachronism`):
      reproduce the workflow of `/autonovel:check-anachronism N`
      inline. Run `autonovel mechanical period-bans
      books/{book}/chapters/ch_{N:02d}.md
      shared/period_bans.txt` for the deterministic half. Then
      LLM semantic pass for concept/metaphor anachronism. Combined
      report at `books/{book}/edit_logs/ch{N:02d}_anachronism.md`.
      Anachronism findings inform the brief in step (d) if the
      revise loop fires.

   c. **Evaluate** (skip if `--skip-eval`): reproduce the workflow
      of `/autonovel:evaluate --chapter N` inline. Write
      `books/{book}/eval_logs/ch{N:02d}_eval.json`. Read
      `overall_score`. Call this `score_v1`.

   d. **Revise loop** (skip if `--skip-eval` or `--no-revise-low`,
      or if `score_v1 >= threshold`):
      i.   Reproduce `/autonovel:brief N --from auto`'s workflow
           inline — read the eval log from (c), the anachronism
           report from (b), any cuts file. Synthesize
           `books/{book}/briefs/ch{N:02d}.md` with named-passage
           prescriptions.
      ii.  Reproduce `/autonovel:revise N`'s workflow inline —
           read the brief, the chapter, the prior chapter's tail
           (via `autonovel _tail-chapter`, best-effort, no retry).
           Rewrite `books/{book}/chapters/ch_{N:02d}.md`.
           Regenerate `books/{book}/chapters/ch_{N:02d}.summary.md`
           so chapter N+1's draft reads the revised version.
      iii. Re-evaluate. Call this `score_v2`.
      iv.  Keep whichever version scored higher. The other version
           is recoverable via the preamble's checkpoint
           (`autonovel rollback`).

   e. **Critical: do NOT call `autonovel _begin` or `autonovel
      _end` for any sub-step.** This command holds the series lock
      for the entire sweep; sub-steps that tried to acquire the
      lock would deadlock.

   f. After each chapter finishes, print one progress line:

      ```
      [ch N] draft <words>w · anachronism <hits> · eval <s1>
                 [→ revise → eval <s2>] · final <best>
      ```

      so the user has live progress. If a chapter errors, log the
      failure and continue — do not abort the whole sweep.

4. **After the loop completes, promote canon** (skip if
   `--no-promote`). Reproduce `/autonovel:promote-canon`'s workflow
   inline against `books/{book}/pending_canon.md` and any other
   books' pending files. Conflicts are parked under a `# Conflicts`
   header — they do not abort the sweep, but the summary in step
   (5) flags them so the user knows.

5. **Print a summary table** in the postamble footer:

   ```
   chapter | draft (words) | anach | eval v1 | eval v2 | final | revised?
   --------|---------------|-------|---------|---------|-------|----------
        4  | 3100          | 0     | 7.4     | —       | 7.4   | no
        5  | 2950          | 2     | 5.9     | 6.7     | 6.7   | yes
        6  | 3200          | 1     | 6.8     | —       | 6.8   | no
   ```

   Plus a one-paragraph headline ("Drafted 3 chapters; 1 revised
   on low score; 4 candidate canon entries promoted; 0 conflicts.
   Recommend `/autonovel:reader-panel --book {book}` for the
   whole-book pass.").

6. The postamble's standard footer recommends the next step.
   Common cases:
     - All chapters ≥ threshold and no conflicts →
       `/autonovel:reader-panel --book {book}` for whole-book
       depth review.
     - One or more chapters still below threshold →
       `/autonovel:revision-pass --chapters <those>` for the
       multi-pass deepener.
     - Canon conflicts parked → resolve them by hand-editing
       `pending_canon.md` (the `# Conflicts` section) and re-running
       `/autonovel:promote-canon`.
</workflow>

<files-touched>
This sweep delegates to the same set of files each underlying command
touches. For the contract record:

Reads:
- `project.yaml`
- `shared/world.md`, `shared/characters.md`, `shared/canon.md`,
  `shared/events.md`, `shared/period_bans.txt`
- `shared/research/notes/*.md` (when the outline names them)
- `books/{book}/voice.md`, `books/{book}/outline.md`
- `books/{book}/chapters/ch_{chapter}.md` (during retry / revise)
- `books/{book}/chapters/ch_*.summary.md` (rolling continuity)
- `books/{book}/eval_logs/ch{chapter:02d}_eval.json` (read by brief --from auto)
- `books/{book}/edit_logs/ch{chapter:02d}_anachronism.md` (read between eval and brief)

Writes (per chapter in range, plus the end-of-sweep promote):
- `books/{book}/chapters/ch_{chapter}.md`
- `books/{book}/chapters/ch_{chapter}.summary.md`
- `books/{book}/eval_logs/ch{chapter:02d}_eval.json`
- `books/{book}/edit_logs/ch{chapter:02d}_anachronism.md`
- `books/{book}/briefs/ch{chapter:02d}.md` (only if revise loop fires)
- `books/{book}/pending_canon.md`
- `shared/canon.md` (only at end-of-sweep promote, only if not --no-promote)
</files-touched>

<acceptance>
- For every chapter N in the resolved range,
  `books/{book}/chapters/ch_{N:02d}.md` exists, parses YAML
  frontmatter, is at least 2000 words.
- For every chapter N,
  `books/{book}/chapters/ch_{N:02d}.summary.md` exists and is
  100-400 words.
- Unless `--skip-eval` was passed, every chapter has a fresh
  `books/{book}/eval_logs/ch{N:02d}_eval.json`.
- Unless `--no-anachronism`, every chapter has a fresh
  `books/{book}/edit_logs/ch{N:02d}_anachronism.md`.
- Unless `--no-revise-low` or `--skip-eval`, every chapter that
  scored below threshold on its first eval has a corresponding
  `books/{book}/briefs/ch{N:02d}.md` from the revise loop, and the
  final chapter file is whichever version (draft or revise) scored
  higher.
- Unless `--no-promote`, the sweep ends with at most a few entries
  remaining in `books/{book}/pending_canon.md` (only the conflicts).
- A summary table is printed in the postamble footer.
</acceptance>
