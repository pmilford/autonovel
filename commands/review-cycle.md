---
name: autonovel:review-cycle
description: Make a drafted book ready for its author — run every whole-book review that hasn't read the text as it stands (said-once, structure review, reader panel, dual review, evaluate --full, developmental edit; then every chapter scored strictly), judge their findings, act on the ones that hold, re-score what changed, and repeat until `release-check` passes. No version goes to the author before it does.
argument-hint: "--book <short-name> [--max-rounds N]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
  - task
reads:
  - project.yaml
  - books/{book}/chapters/*.md
  - books/{book}/chapters/ch_*.summary.md
  - books/{book}/eval_logs/*.json
  - books/{book}/edit_logs/report_stamps.json
  - books/{book}/edit_logs/said_once_ledger.md
  - books/{book}/edit_logs/structure_review.json
  - books/{book}/edit_logs/structure_review.md
  - books/{book}/edit_logs/editor_letter.md
  - books/{book}/edit_logs/reader_panel.json
  - books/{book}/edit_logs/review.json
  - books/{book}/edit_logs/review.md
  - books/{book}/briefs/conversation.md
  - books/{book}/design.md
writes:
  - books/{book}/chapters/*.md
  - books/{book}/eval_logs/*.json
  - books/{book}/edit_logs/*.md
  - books/{book}/edit_logs/*.json
  - books/{book}/briefs/*.md
  - books/{book}/canon.md
  - books/{book}/pending_canon.md
  - shared/canon.md
context_mode: book
---

<purpose>
The pipeline has six whole-book reviews and a per-chapter score, and
until now nothing ran them: the order lived in a footer line and in
`/autonovel:next`, `/autonovel:run-pipeline` only suggests, and
`/autonovel:typeset` built a book for the author whatever state they
were in. One author was sent four versions with reviews that had never
read them: "You are wasting my time asking me to read content that has
not been reviewed and corrected by our tools." (2026-10-25)

This command is the cycle a publisher runs before a manuscript goes back
to its author, and it acts on what it finds:

1. the whole-book reviews that haven't read this text, in the order each
   needs the last: said-once (repetition across and inside chapters) and
   the structure review; once the structure gate passes, the reader
   panel, the dual review and the whole-book scorecard (`evaluate
   --full`); then the developmental edit (one reader, the editor's
   letter), which says where it disagrees with all of them;
2. the editor (this conversation) reads every report, judges each
   finding, and stages the ones that hold as fixes;
3. the fixes are made chapter by chapter;
4. every chapter scored, strictly, on the text as it then stands;
5. `autonovel mechanical release-check` decides whether to go round
   again (at most `--max-rounds`, default 3).

Whole-book reviews stand through a light fix pass (a few sentences in a
chapter); a rewrite sends them back to be read again
(`release-check`'s limits). Chapter scores describe one text exactly and
are always retaken.

It never sends anything to the author. When the gate passes it says so
and names the build to make; when it can't pass within the rounds, it
says what is still open and why.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`: `--book <short-name>` (defaults via `_begin`),
   `--max-rounds N` (default 3). Use `file_read` on `project.yaml` for
   `defaults.dimension_floor` and on `books/{book}/design.md` for the
   author's recorded decisions (names, places, the climax) that no fix
   may undo.

2. Use `bash` to run `autonovel mechanical release-check books/{book}
   --format json`. If `passes` is true, print that the book is ready for
   its author and stop. Otherwise print the open checks.

3. **Each round**, in this order, doing only the steps whose check is
   open. Every step that runs another command runs it as a `task`
   subagent: give it the path printed by `autonovel _command-path <name>`
   (e.g. `autonovel _command-path evaluate`), tell it to read that file in
   full and follow its `<workflow>` for the arguments given, to skip the
   `<autonovel-preamble>` and `<autonovel-postamble>` (this command holds
   the lock), to run the stamp command the workflow names, and to change
   no file the workflow doesn't write. Give it the genre line `_begin`
   printed. The whole-book reviews come first and the chapter scores
   last (step 5): a score describes one text exactly, so a chapter
   scored before this round's fixes would have to be scored again.

   a. **said-once** and **structure-review**, each when its check is
      open, side by side (neither reads the other): `said-once --book
      {book} --stage` (it reads the chapters itself, act by act) and
      `structure-review --book {book}`.
   b. Only when the structure gate passes (`release-check`'s
      `structure_review` check is ok): **reader-panel**, **review** and
      **evaluate --full**, each when open, side by side.
   c. **developmental-edit**, when open: `developmental-edit --book
      {book} --stage`, last, so its letter can say where it disagrees
      with every instrument above. One reader, every chapter in order.

4. **Judge the findings before acting on them.** Read every report the
   round produced, with `file_read`: each chapter's eval log under
   `books/{book}/eval_logs/*.json`; `books/{book}/edit_logs/said_once_ledger.md`;
   `books/{book}/edit_logs/structure_review.json` and
   `books/{book}/edit_logs/structure_review.md`;
   `books/{book}/edit_logs/editor_letter.md`;
   `books/{book}/edit_logs/reader_panel.json`;
   `books/{book}/edit_logs/review.json` and `books/{book}/edit_logs/review.md`;
   the book score; and `books/{book}/edit_logs/report_stamps.json` for
   which text each read. Check a finding against the chapter itself
   (`books/{book}/chapters/*.md`, and its summary
   `books/{book}/chapters/ch_*.summary.md` for context) before you
   believe it. For each
   finding decide: holds (stage it), holds in part (stage the part), or
   doesn't (note why: a payoff counted as a repeat, a period detail a
   reviewer would cut, a name the author decided, a fix that would damage
   what works). Nothing the genre's reader came for is cut; history is
   moved, never removed; a place or person keeps the name `design.md`
   records. Write the judgements to
   `books/{book}/edit_logs/review_cycle_round<N>.md`: per report, what was
   staged and what wasn't, and why. Stage every held finding as a turn in
   `books/{book}/briefs/conversation.md` in the shape `/autonovel:talk`
   writes (`**Mode:** suggest`, `**Target:** chapter N`, the finding with
   its line and quote, the fix, `**Status:** queued`), one turn per
   chapter. A finding that needs a cross-chapter move (merge, cut,
   reorder, split) or an author's decision is not staged: list it for the
   author in the round notes and in the final report.

5. **Make the fixes, then score.** For every chapter with a queued turn, a dimension
   under the floor, or an open cold-reader item: one subagent per
   chapter, in chapter order, following `autonovel _command-path
   revision-pass` step 3's per-chapter sequence for that chapter (brief
   from the queued turns and the eval log, then revise, then evaluate,
   then `_stamp-summary` and `_stamp-eval`), skipping its anachronism
   check unless the chapter's dateline or period content changed. Then,
   for every chapter `release-check` still lists under `chapter_scores`
   (changed by no fix but scored on an older text), one subagent per
   chapter, up to four at a time: `evaluate --chapter N --book {book}`.
   Each returns its overall score, every dimension, the weakest,
   `top_3_revisions`, the cold reader's open items and its repeats;
   judge them as step 4 does before the next round. Read
   every change it made (`autonovel mechanical diff-chapters --book
   {book} --from checkpoint:latest --chapters N --format hunks`) and put
   back anything it cut that a reader came for, as revise's "Account
   for every cut" says. Flip the turns it carried out to `**Status:**
   applied`. Revisions write `books/{book}/chapters/*.md`, their
   summaries, eval logs, briefs under `books/{book}/briefs/*.md`, edit
   logs under `books/{book}/edit_logs/*.md` and
   `books/{book}/edit_logs/*.json`, and canon: after the last chapter of
   the round, use `bash` to run `autonovel _promote-canon --book {book}
   --no-lock`, which moves `books/{book}/pending_canon.md` into
   `books/{book}/canon.md` and `shared/canon.md`.

6. Run `release-check` again. If it passes, go to step 7. If it doesn't
   and rounds remain, start the next round at step 3 with what is still
   open. If no rounds remain, go to step 7 and say it isn't ready.

7. **Report**, in plain sentences, worst item first: every chapter's
   score and lowest dimension as it now stands, before and after the
   cycle; what each whole-book review found and what was done about it;
   what the editor declined to act on, and why; what needs the author's
   decision; and the gate's verdict. When it passes, the next step is
   `/autonovel:typeset --book {book}` and `/autonovel:diff --book {book}
   --annotate` for the author's change page; when it doesn't, the next
   step is what is still open. Never send or typeset a version for the
   author from this command.
</workflow>

<acceptance>
- `release-check` was run at the start and at the end of every round,
  and its final verdict is reported.
- Every whole-book review that ran was stamped (`autonovel
  _stamp-report`), and every chapter scored was stamped
  (`autonovel _stamp-eval`).
- `books/{book}/edit_logs/review_cycle_round<N>.md` exists for every
  round, listing each finding as staged, staged in part, or declined,
  with the reason.
- Every staged turn this command queued is `applied` by the end, or
  listed as still open in the report.
- No version was sent to the author.
</acceptance>
