---
name: autonovel:fix-read
description: Read every passage changed since a chapter's cold read where it sits, with the paragraph before and after it, as a line editor, and report what the changes broke — a pronoun now pointing at the wrong person, someone entering a scene unplaced, a line that no longer follows, a point now told twice, a pasted-in explanation — then stage the fixes and stamp each chapter read clean.
argument-hint: "--chapters <N,M,…|all> --book <short-name>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
  - task
reads:
  - books/{book}/chapters/*.md
  - books/{book}/voice.md
  - books/{book}/edit_logs/report_stamps.json
writes:
  - books/{book}/edit_logs/fix_read_*.md
  - books/{book}/briefs/conversation.md
  - books/{book}/edit_logs/report_stamps.json
context_mode: book
---

<purpose>
A cold reader reads a chapter whole (`/autonovel:first-read`). Every change
made after that read, by a light fix pass, a revise, an editor's hand or
a reorder's seam fix, is read by nobody unless someone reads it where it
sits. Scorers don't: they score the chapter, and when they check a cold
reader's item they ask whether the reported fault is gone, not whether
the fix made a new one.

One author, listening to an audiobook sample, found a scene where a
character came into a room from nowhere. The cold reader had found it
that morning. The editor's fix put the man in the room in the scene's
first sentence, which made the next paragraph's "He was a slight young
man" point at him, and the scorer that checked the fix passed it. The
author: "that seems like something that both autonovel and you should
have found and fixed." (2026-10-28)

This command is that read. It takes every run of paragraphs that differs
from the text the chapter's cold reader read, with the paragraph before
and after it, and reads them as a line editor. `release-check` asks for
it (`fixes_read`): a version doesn't go to the author with a changed
passage nobody has read in context.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`: `--chapters <N,M,…|all>` (default: the chapters
   `autonovel mechanical release-check books/{book}` lists under
   `fixes_read`), `--book <short-name>`.

2. Use `bash` to run `autonovel mechanical fix-context books/{book}
   --chapter N` (repeat `--chapter` for each) and keep its output: for each
   changed passage, the paragraph before it, what it was, what it is now,
   and the paragraph after it. A chapter with no changed passage needs no
   read; stamp it (step 6) and say so. Use `file_read` on
   `books/{book}/voice.md` Parts 1 and 2 once, for the register.

   **Context budget.** When the passages fit comfortably (up to about
   60,000 words), read them yourself. Otherwise give each `task` reader a
   few chapters' passages and this step's instructions, and keep every
   judgement in this conversation: check each fault a reader reports
   against the chapter before you accept it.

3. **Read each passage as a reader meets it**: the paragraph before, the
   new text, the paragraph after. When a passage opens or closes a scene
   or a chapter, also read the end of the previous scene or chapter in
   `books/{book}/chapters/ch_NN.md`. Then judge what the change broke:
   1. **Reference**: does every he, she, him, it, they, "the man" or "the
      other" point at the right person or thing? Is a person introduced
      before a pronoun leans on them?
   2. **Flow**: does each sentence follow from the one before? Does
      anyone enter, speak or act without being placed in the scene? Does
      a jump in time or place read plainly?
   3. **Told twice**: does the change now say what the paragraphs around
      it, or the same chapter, already say, in the same or other words?
   4. **Sense and fact**: does the changed sentence still mean what the
      scene needs? Did a cut remove something a later line depends on? Is
      a date, number or name now inconsistent within the chapter?
   5. **Voice**: does the new wording sound like the prose around it, or
      like an explanation pasted in? (voice.md Part 1 is the register.)
   Report only real faults a reader would trip on, not matters of taste.
   Most changes will be fine.

4. Use `file_write` on `books/{book}/edit_logs/fix_read_<YYYY-MM-DD>.md`
   (append when it exists): per chapter, the count of passages read, and
   for each fault the passage quoted as it now reads, the kind (1–5) and
   why in a sentence, and the smallest fix as exact replacement text (a
   clause or a sentence; history is moved, never cut; no new names or
   people).

5. For each chapter with a fault, use `file_write` to append one turn to
   `books/{book}/briefs/conversation.md` in the shape `/autonovel:talk`
   writes (`**Mode:** suggest`, `**Target:** chapter N`, each fault with
   its quote and its fix, `**Status:** queued`). The next step for those
   chapters is to carry the turns out (`/autonovel:revision-pass
   --chapters <them> --book {book}`, or the editor's own hand) and then
   run this command again on them: a fix is read in context like any
   other change.

6. For each chapter read with no fault, use `bash` to run `autonovel
   _stamp-report --book {book} --report fix_read --chapter N`, which
   records in `books/{book}/edit_logs/report_stamps.json` that its changes
   were read in context on the text as it now stands (the gate compares
   that fingerprint with the chapter's, and the cold read's copy of the
   text, kept beside it, is what `fix-context` measures the changes
   against). Never stamp a chapter with a fault still open.

7. Report, in plain sentences: the chapters read and passages read, every
   fault found (worst first) with its quote and fix, the chapters stamped,
   and the next step.
</workflow>

<acceptance>
- Every passage `fix-context` listed for the chapters asked for was read
  with the paragraph before and after it.
- `books/{book}/edit_logs/fix_read_<date>.md` records each chapter read
  and each fault with a quote and a fix.
- Each chapter with a fault has one queued turn; each chapter read clean
  is stamped `fix_read`; none with an open fault is stamped.
- No chapter file was edited by this command.
</acceptance>
