---
name: autonovel:revision-pass
description: Sweep check-anachronism + brief + revise + evaluate across a range of chapters in one invocation.
argument-hint: "--chapters <range> [--book <name>] [--skip-anachronism] [--skip-eval] [--parallel [N]]"
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
  - shared/period_bans.txt
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_*.summary.md
  - books/{book}/edit_logs/ch{chapter:02d}_anachronism.md
  - books/{book}/eval_logs/ch{chapter:02d}_eval.json
writes:
  - books/{book}/edit_logs/ch{chapter:02d}_anachronism.md
  - books/{book}/briefs/ch{chapter:02d}.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
  - books/{book}/eval_logs/ch{chapter:02d}_eval.json
  - books/{book}/pending_canon.md
context_mode: book
---

<purpose>
Run the standard revision loop across multiple chapters in one
invocation. For each chapter in the requested range, sequentially
runs:

  1. `check-anachronism` (period-vocabulary + LLM semantic check)
  2. `brief --from auto` (synthesize revision brief from cuts/eval/panel)
  3. `revise` (rewrite chapter against the brief; regenerates the summary)
  4. `evaluate --chapter N` (score the revised version)

This is the "I have 3 drafted chapters, I want them all revised in
one go" command. Author preference 2026-04-25: minimise required
typing for the standard end-to-end flow while keeping the option to
skip individual stages.

Sequential by default within a book — later chapters' revisions read
earlier chapters' refreshed summaries. **Parallel via `--parallel
[N]`** (opt-in, default off): fan up to N chapters across `Task`
subagents simultaneously. Trade-off: parallel is ~Nx faster, but
each chapter's revise reads the *pre-sweep* version of its
neighbours' summaries (chapter 5's revise won't see chapter 4's
fresh post-revise summary in the same pass), so continuity drift
stays one revision-pass behind. A second
`/autonovel:revision-pass` picks up the propagation. Default
parallelism when `--parallel` is given without a number is **3**
(matches typical rate-limit headroom on standard accounts).

One single lock + checkpoint covers the whole sweep — sub-steps do
NOT run their own `autonovel _begin`/`_end`, so there's exactly
one preamble/postamble across the run. Rollback restores every
chapter the sweep touched in one shot.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Required: `--chapters <range>`. The range
   can be `N-M` (inclusive), `N,M,K` (comma-separated), or `all`
   (every drafted chapter). `--book` defaults via `_begin`.
   `--skip-anachronism` and `--skip-eval` are independent flags
   that drop those stages from the per-chapter sequence. Missing
   `--chapters` → stop with a one-line usage hint.

2. Use `file_read` on `project.yaml` to resolve the book entry,
   `pov`, and `defaults.chapter_target_words`. Use the `Bash` tool
   to run `ls books/{book}/chapters/ch_*.md` and pull the existing
   chapter numbers; resolve `all` to the full list and validate that
   every requested chapter exists.

3. **Spawn one `task` subagent per chapter.** Per-chapter execution
   runs in a fresh subagent conversation, not in this parent
   conversation. Same context-saving discipline as draft-pass:
   the parent only sees one short summary string per chapter, so
   long sweeps don't exhaust the parent's context window.

   Two execution modes:

   - **Default (no `--parallel`):** spawn one Task at a time, in
     ascending chapter-number order. Each chapter's full sequence
     completes before the next is spawned. Maximum continuity
     fidelity (each chapter's revise reads its predecessors'
     refreshed summaries).
   - **`--parallel [N]`:** spawn up to N Task subagents
     simultaneously (default N=3). Faster but each parallel Task
     reads the *pre-sweep* version of its neighbours' summaries,
     so the rolling-summary context is one revision-pass stale
     within the run. Re-run revision-pass once more to propagate.

   For each chapter N, the subagent's prompt template (substitute
   {book}, N, and the active flags):

   a. **check-anachronism** *(skippable via --skip-anachronism)*:
      Use `Bash` to run
      `autonovel mechanical period-bans
      books/{book}/chapters/ch_{N:02d}.md shared/period_bans.txt`
      for the deterministic half. Then load
      `books/{book}/chapters/ch_{N:02d}.md`,
      `shared/world.md`, `shared/canon.md` and run an LLM semantic
      pass for concept/metaphor anachronism (the same logic
      `/autonovel:check-anachronism` carries out). Combine the
      regex hits and the LLM hits into a report at
      `books/{book}/edit_logs/ch{N:02d}_anachronism.md`. Do NOT
      modify the chapter.

   b. **brief --from auto**: Reproduce the body of
      `/autonovel:brief` — read the latest `eval_logs/ch{N:02d}*.json`,
      `edit_logs/ch{N:02d}_cuts.json` (if any), and the new
      anachronism report from (a) — then synthesize a revision
      brief at `books/{book}/briefs/ch{N:02d}.md`. The brief
      enumerates specific named passages to change, target word
      count, and prescriptions per anti-pattern.

   c. **revise**: Reproduce the body of `/autonovel:revise` — read
      the brief, the current chapter, the prior chapter's last
      ~2000 words via `autonovel _tail-chapter --book {book}
      --chapter {N-1} --words 2000` (best-effort, no retry),
      voice, and rewrite the chapter. Overwrite
      `books/{book}/chapters/ch_{N:02d}.md`. **Regenerate the
      summary** at `books/{book}/chapters/ch_{N:02d}.summary.md`
      so chapter N+1's revise reads the updated version.

   d. **evaluate** *(skippable via --skip-eval)*: Reproduce the
      body of `/autonovel:evaluate --chapter N` — score the revised
      chapter against the standard chapter dimensions, write
      `books/{book}/eval_logs/ch{N:02d}_eval.json`. The eval is
      what the next sweep iteration's brief will pull from.

   **Critical: do NOT call `autonovel _begin` or `autonovel _end`
   for any sub-step.** This command holds the series lock for the
   entire range — its own preamble already ran. Sub-steps that
   tried to acquire the lock would deadlock.

   After each chapter finishes, print one line:

   ```
   [ch N] anachronism: <count> hits | brief: <words>w | revise: <words>w (delta <±N>w) | eval: <score>
   ```

   so the user has live progress. If a sub-step errors, log the
   failure and continue to the next chapter — do not abort the
   whole sweep on one chapter's hiccup.

4. After the loop completes, print a summary table:

   ```
   chapter | anachronism | revise (words) | eval (score)
   --------|-------------|----------------|-------------
        1  | 2 hits      | 2900 (-150)    | 7.4
        2  | 0 hits      | 3200 (+50)     | 6.8
        3  | 1 hit       | 2750 (-300)    | 7.1
   ```

   Append a one-paragraph headline assessment ("3/3 chapters
   above threshold; chapter 2 closest to the floor; recommend
   `/autonovel:reader-panel` next").

5. The postamble's standard footer recommends the next step. With
   the sweep complete and chapters all above the threshold, that
   should be `/autonovel:reader-panel --book {book}` (book-wide
   pass) or `/autonovel:promote-canon` (if pending_canon has
   entries from any of the revises).
</workflow>

<files-touched>
This sweep delegates to the same set of files each underlying command
touches. For the contract record (and so a `--dry-run`-style audit
can enumerate them):

Reads:
- `project.yaml`
- `shared/world.md`, `shared/characters.md`, `shared/canon.md`
- `shared/period_bans.txt`
- `books/{book}/voice.md`, `books/{book}/outline.md`
- `books/{book}/chapters/ch_{chapter}.md` (per chapter in range)
- `books/{book}/chapters/ch_*.summary.md` (rolling continuity)
- `books/{book}/edit_logs/ch{chapter:02d}_anachronism.md` (read between stages)
- `books/{book}/eval_logs/ch{chapter:02d}_eval.json` (read by brief --from auto)

Writes (per chapter in range):
- `books/{book}/edit_logs/ch{chapter:02d}_anachronism.md`
- `books/{book}/briefs/ch{chapter:02d}.md`
- `books/{book}/chapters/ch_{chapter}.md`
- `books/{book}/chapters/ch_{chapter}.summary.md`
- `books/{book}/eval_logs/ch{chapter:02d}_eval.json`
- `books/{book}/pending_canon.md` (revise may append candidate facts)
</files-touched>

<acceptance>
- For every chapter N in the resolved range, the corresponding
  `books/{book}/chapters/ch_{N:02d}.md`,
  `books/{book}/chapters/ch_{N:02d}.summary.md`,
  `books/{book}/briefs/ch{N:02d}.md`, and
  `books/{book}/eval_logs/ch{N:02d}_eval.json` exist and have
  modification times newer than the start of the sweep.
- If `--skip-anachronism` was passed, no
  `books/{book}/edit_logs/ch{N:02d}_anachronism.md` was created
  by this run.
- The summary table is printed in the postamble footer; the user
  can read per-chapter results without opening the eval logs.
</acceptance>
