---
name: autonovel:reorder
description: Move a chapter to a new position; renumber neighbours and every record keyed by a chapter's number; check each new seam and stage the fixes; send back only the reviews the new order changed.
argument-hint: "--from <A> --to <B> --book <short-name> [--dry-run]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - books/{book}/outline.md
  - books/{book}/voice.md
  - books/{book}/chapters/*.md
  - books/{book}/edit_logs/said_once_ledger.md
  - shared/events.md
writes:
  - books/{book}/chapters/*.md
  - books/{book}/outline.md
  - books/{book}/design.md
  - books/{book}/cast.md
  - books/{book}/canon.md
  - books/{book}/appendix.md
  - books/{book}/briefs/*.md
  - books/{book}/briefs/conversation.md
  - books/{book}/eval_logs/*.json
  - books/{book}/edit_logs/*.md
  - books/{book}/edit_logs/*.json
  - books/{book}/typeset/plates.yaml
context_mode: book
---

<purpose>
Sidequest: move chapter `A` to position `B` within the same book and
renumber every chapter in between.

A chapter's number is its key in more than a dozen places: its summary,
its brief, every eval log, its cold reader's report, the copies of the
text each whole-book review read, the outline's entry, the plates placed
before it, and every "ch 10" in the reports, the design and the canon.
Renaming only `ch_NN.md` would leave each moved chapter with another
chapter's brief and score, and the release gate would count the whole
book as rewritten and send every review back. So the renumber runs as one
script, `autonovel _renumber`, which moves all of it by one map (CLAUDE.md:
renumbering by script, never an LLM rename loop) and then sends back only
what the new order changed:

- a chapter whose previous chapter is now another is scored again (its
  continuity was judged against the old one);
- a chapter whose earlier chapters are now a different set is read cold
  again (a cold reader's "I didn't know" depends on what came before);
- the structure review and the whole-book score read the book again,
  because they judge the order itself; the reader panel, the dual review
  and the editor's letter judge what is on the page, so their chapter
  references are rewritten to follow the text and they stand;
- the said-once ledger reads the book again only when a point's first
  telling now comes after a later one.

A reader meets each moved chapter after a different chapter than before,
so an opening that recapped what the old previous chapter told, or a
date line that re-set a scene the reader has just left, now reads wrong.
This command reads every new seam and stages the fixes.

Lands in one checkpoint so `autonovel rollback` undoes the whole
operation.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `--from <A> --to <B> --book <short-name>`;
   `--dry-run` prints what would move and changes nothing. If `A == B`,
   stop and print "nothing to do".

2. Use `file_read` on `books/{book}/outline.md` to confirm the chapter
   count and the moved chapter's beats, and on `shared/events.md`. If any
   `rendered_in` row names `{book}/ch_{A:02d}` or a chapter between `A`
   and `B`, show those rows to the user and ask them to confirm before
   going on: a canonical event ledger row is not retargeted silently.

3. Use `bash` to run the renumber:
   `autonovel _renumber --book {book} --from A --to B --format json`
   (with `--dry-run` first when the user asked for one, then stop). It
   moves every file named for a chapter (`books/{book}/chapters/*.md` and
   their summaries, `books/{book}/briefs/*.md`, `books/{book}/eval_logs/*.json`,
   the cold readers' reports and anachronism logs under
   `books/{book}/edit_logs/*.md` and `books/{book}/edit_logs/*.json`,
   ornaments), rewrites each chapter's `chapter:` field, rewrites every
   chapter reference in `books/{book}/outline.md` (and puts its entries
   back in reading order), `books/{book}/design.md`, `books/{book}/cast.md`,
   `books/{book}/canon.md`, `books/{book}/appendix.md`, the briefs and
   `books/{book}/briefs/conversation.md`, the summaries, the eval logs, the
   current whole-book reports and `books/{book}/typeset/plates.yaml`, and
   moves the review stamps with the text. Its JSON names `rescore` (the
   chapters to score again), `reread` (to read cold again),
   `order_reports` (the whole-book reviews to run again) and
   `said_once_inverted`. On an error, stop and show it.

4. **Read every new seam.** For each chapter in `rescore`, use `bash` to
   run `autonovel _tail-chapter --book {book} --chapter <N-1> --words 600`
   and `file_read` the first ~600 words of
   `books/{book}/chapters/ch_<N>.md` (and `books/{book}/voice.md` once,
   for the register; `books/{book}/edit_logs/said_once_ledger.md` says where
   each point an opening repeats is first told). Read them as a reader now meets them, the one after
   the other, and judge the opening:
   - it **continues**: the chapter before ends where this one picks up.
     Does it re-set a scene, a date or a year the reader has just left,
     or explain again what the last page told? Then the first line should
     carry on, not start over;
   - it **jumps** in time or place: does the dateline and first sentence
     say where and when plainly enough, and does anything in the opening
     lean on a chapter the reader has not reached yet?
   - it **recaps**: a reminder after a gap is a few words, never a second
     explanation (`shared/craft/PROSE.md` §7 rule 9). A recap the old
     order needed and the new one doesn't is cut.
   Judge the moved chapters' endings the same way against what now
   follows them. For each seam that needs work, use `file_write` to
   append one turn to `books/{book}/briefs/conversation.md` in the shape
   `/autonovel:talk` writes (`**Mode:** suggest`, `**Target:** chapter N`,
   the quoted opening or ending, the fix in a sentence or two, the rule
   that the chapter ends no longer than it began, `**Status:** queued`).
   A seam that reads well gets no turn; say so in the report.

5. Print the renumber (`ch A → ch B; shifted N chapters by ±1`), the
   seams read and the turns staged, and what the new order sent back: the
   chapters to score again and to read cold again, and the whole-book
   reviews to run again. The next step is `/autonovel:revision-pass
   --chapters <the staged chapters> --book {book}` when turns were staged,
   then `/autonovel:review-cycle --book {book}`, which scores, reads and
   reviews exactly what `release-check` now lists.
</workflow>

<acceptance>
- The number of chapter files under `books/{book}/chapters/` is
  unchanged (reorder never adds or removes chapters).
- Every moved chapter's frontmatter `chapter:` matches its file name, and
  its summary, brief, eval logs and cold-reader report moved with it.
- `books/{book}/outline.md` has the same `## Chapter N` headings as
  before, in reading order.
- `autonovel mechanical release-check books/{book}` lists exactly the
  chapters in `rescore` under chapter scores, the chapters in `reread`
  under cold readers, and the reviews in `order_reports`.
- Every seam between a moved chapter and its new neighbours was read,
  and each one that needs work has a queued turn.
- The command stopped without writing if a `rendered_in` row in
  `shared/events.md` pinned a moved chapter and the user had not
  confirmed.
</acceptance>
