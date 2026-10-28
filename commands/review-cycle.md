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
  - books/{book}/edit_logs/first_read_ch*.md
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
   Start `books/{book}/edit_logs/review_cycle_round<N>.md` now with the
   release check's open items and every correction the last chapter
   scores asked for that is not yet made, and the round's starting
   point: the series' git commit when it is a git repository (commit
   first if the tree has changes), otherwise `checkpoint:latest`. Every
   cut check this round (step 5b) diffs from that point, and nothing is
   committed while a fix worker is writing: a commit in the middle hid
   half of one worker's cuts from its own check. Change no chapter while a
   whole-book review is reading the book (its line numbers and quotes
   would stop matching the text); note any fix you find meanwhile in the
   round notes and make it in step 5.

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
   the book score; the cold readers' reports,
   `books/{book}/edit_logs/first_read_ch*.md` (judge every serious item
   as you judge a finding; one that doesn't hold, a deliberate mystery
   or a fact an earlier chapter gave, goes under the report's `## Editor's
   calls` heading as **declined**, with why, as
   `shared/craft/FIRST-READER.md` says, so no scorer counts it open
   again. A reader given the early chapters as summaries (a report made
   before readers were given the full text, or a book too long to hold;
   the report's header says which) reports as unknown what an earlier
   chapter tells in full: that item is
   declined every time, with that chapter and line, or at most answered
   with a reminder of a few words. One round that fixed them as asked
   put a second gloss in every late chapter, and all four of the next
   panel's readers reported the book as saying everything twice); and
   `books/{book}/edit_logs/report_stamps.json` for which text each read.
   A point told again that two or more of the panel's readers report, or
   the panel and the dual review both, holds even where the said-once
   ledger kept it: readers of the whole book noticing it is the evidence
   that the mention is a repeat, not a reminder. Check a finding against the chapter itself
   (`books/{book}/chapters/*.md`, and its summary
   `books/{book}/chapters/ch_*.summary.md` for context) before you
   believe it. For each
   finding decide: holds (stage it), holds in part (stage the part), or
   doesn't (note why: a payoff counted as a repeat, the genre's payload a
   reviewer would cut, a name the author decided, a fix that would damage
   what works). Nothing the genre's reader came for is cut: what the
   genre guide's `## Cutting` protects (in historical fiction, the
   period) is moved or given to a person, never removed; a place or
   person keeps the name `design.md` records. Write the judgements to
   `books/{book}/edit_logs/review_cycle_round<N>.md`: per report, what was
   staged and what wasn't, and why. Stage every held finding as a turn in
   `books/{book}/briefs/conversation.md` in the shape `/autonovel:talk`
   writes (`**Mode:** suggest`, `**Target:** chapter N`, the finding with
   its line and quote, the fix, `**Status:** queued`), one turn per
   chapter. When a finding names several chapters ("the protagonist
   sees what his mistake cost, in chapters 9 and 11"), say in every one
   of its turns which chapter tells the point in full and which give it
   a clause, and check the chapters before and after for an earlier
   telling: staged one per chapter without that, each worker tells it in
   full, and on one book the fix made a third telling a scorer then marked
   down (`shared/craft/PROSE.md` §7 rule 9). Moving a scene or a
   passage from one chapter to another (an episode that belongs at the
   end of the chapter before; an explanation that belongs where it is at
   stake) is not a merge, cut, reorder or split of chapters: stage it as
   a pair of turns, one per chapter, and in step 5 give both chapters to
   one worker, the giving chapter's side first, so the passage arrives
   whole and isn't told in both. A finding that needs a cross-chapter move (merge, cut,
   reorder, split) or an author's decision is not staged: list it for the
   author in the round notes and in the final report.

5. **Make the fixes, then score.**
   a. **Fix.** For every chapter with a queued turn, a dimension under
      the floor, or an open cold-reader item: one subagent per chapter,
      following `autonovel _command-path revision-pass` step 3's
      per-chapter sequence for that chapter (brief from the queued turns
      and the latest eval log's top revisions and open cold-reader items,
      then revise, then `_stamp-summary`), skipping its anachronism check
      unless the chapter's dateline or period content changed, and
      **skipping its evaluate**. Run them in chapter order, or up to
      three at a time when no chapter's turns depend on another's (a line
      edit, a cut, a clause: revision-pass's `--parallel` trade-off); a
      chapter whose fix plants or pays something in another chapter runs
      after that chapter. Tell each subagent not to run `_promote-canon`
      and not to edit `briefs/conversation.md`: this command marks the
      turns and promotes once, after the round. But each one appends to
      `books/{book}/pending_canon.md` (never rewriting the file, since
      others append beside it) a replacement, written whole, or a
      retirement for every canon entry its change makes untrue, as
      revise step 10 says: a light pass that rewords a line a canon entry
      quotes leaves the canon describing a book that no longer exists,
      and the next draft or revise reads the canon.
   b. **Check the cuts.** Read every change each one made (`autonovel
      mechanical diff-chapters --book {book} --from <the round's
      starting point> --chapters N --format hunks`) and put back anything it cut that a
      reader came for, as revise's "Account for every cut" says. Mark a
      turn applied only when the worker's hand-back accounts for every
      numbered item in it (done, or skipped with a reason) and the diff
      shows the done ones; an item it doesn't mention wasn't made. Never
      add to a turn once its worker has started (the worker read it
      already): stage a new turn instead. Then use
      `bash` to mark the turns it carried out: `autonovel _turn-status
      --book {book} --turns <N,M,…> --status applied`, and any the editor
      decided against `--status declined` (the reason goes in the round
      notes); the gate counts only turns still `queued`.
   c. **Read cold.** For every chapter `release-check` lists under
      `cold_readers` as not read on the text as it stands (a rewrite, or a
      report older than the text; a light fix leaves the last read
      standing), after its last fix: `first-read N --book {book}`, one
      fresh subagent per chapter, several at a time (each spawns its own
      reader, who reads the book up to that chapter in full, and archives
      and stamps the report). A separate full-text reader finds the most:
      on one book, two to three times the told-again points of one reader
      going through the whole book, and none of the false "didn't know"
      items a reader given summaries invents. When every chapter needs a
      read and the cost matters more, `first-read --chapters <them> --book
      {book}` gives them to one reader who reads the book in order (about
      a tenth of the cost); the reader panel and said-once then carry
      more of the repeats. Then, in the same round, judge each report's serious items
      as step 4 says (the declines go under the report's `## Editor's
      calls`) and fix the ones that hold as a light pass, one subagent per
      chapter as in step 5a, with `shared/craft/FIRST-READER.md` "What the
      writer does with it" as the brief: a clause, a reorder, a cut repeat,
      never a rewrite. A fresh reader always finds something; fixing it
      only next round would send every chapter back to another fresh
      reader, round after round. Fixed lightly, the read still stands
      (`release-check` lets a cold read stand while no more than 15% of the words the reader read have changed; `autonovel mechanical read-change books/{book} --chapter N` shows how much has), and the
      scorer checks the items against the fixed text; a fix that has to go
      further is staged for the next round instead. Run the readers and
      these fixes before the scorers, so each scorer checks the report's
      items against the chapter as it stands (`open_items`). On one book every report predated
      two versions and two review rounds, and the gate had been counting
      items no reader had looked for in the text the author would read.
   d. **Score, by a reader who didn't write it.** For every chapter
      `release-check` lists under `chapter_scores` (every chapter just
      fixed, and any scored on an older text), fresh subagents, each
      scoring three or four chapters in a row (it reads the shared files
      once, which on one book halved the cost of a score), several at a
      time: `evaluate --chapter N --book {book}`, then `_stamp-eval`.
      Score a chapter once per round, after its last fix: when a round's
      reviews will change a chapter again, its score waits for them. Never let the subagent that revised a
      chapter score it: a writer judging its own text favours it
      (EDITING.md §5), and a score the author can't trust is no gate.
      Each returns its overall score, every dimension, the weakest,
      `top_3_revisions`, the cold reader's open items and its repeats;
      judge them as step 4 does before the next round. **What the scores
      send back this round:** only a dimension under the floor, an open
      cold-reader item, and a fault a reader is stopped by (a continuity
      slip, a historical error, a reference left pointing at nothing,
      often by this round's own cuts). Make those as the lightest edits
      that fix them and score those chapters again; every scorer finds
      something, and each fix sends its chapter back to a scorer, so
      prose polish (a gloss inside a speech, a long turn, a sum too many)
      goes in the round notes for the next round, not into this one.
   e. **Re-take the whole-book score** when `release-check`'s
      `book_floor` check was open at the round's start and this round
      fixed for it: once the round's last fix is made, one fresh
      subagent runs `evaluate --full --book {book}` on the fixed text and
      stamps it, alongside the chapter scorers (no score changes a
      chapter). A light fix lets the other whole-book reviews stand, but the
      score whose floor the fixes were meant to lift is only known
      lifted when it is taken again; without this step the gate reads
      the old score for ever.
   Revisions write `books/{book}/chapters/*.md`, their summaries, eval
   logs, briefs under `books/{book}/briefs/*.md`, edit logs under
   `books/{book}/edit_logs/*.md` and `books/{book}/edit_logs/*.json`,
   and canon: after the last chapter of the round, use `bash` to run
   `autonovel _promote-canon --book {book} --no-lock`, which moves
   `books/{book}/pending_canon.md` into `books/{book}/canon.md` and
   `shared/canon.md`.

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
