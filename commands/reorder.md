---
name: autonovel:reorder
description: Move a chapter to a new position; renumber neighbors; patch cross-references.
argument-hint: "--from <A> --to <B> --book <short-name>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - books/{book}/outline.md
  - books/{book}/voice.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/*.md
  - shared/events.md
writes:
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/outline.md
context_mode: book
---

<purpose>
Sidequest: move chapter `A` to position `B` within the same book and
renumber every chapter in between. Updates the outline, patches the
frontmatter, and scans `shared/events.md` for `rendered_in` rows that
point into this book — if any row references the moved chapter by
number, report it so a human can fix the ledger.

CLAUDE.md: chapter renumber runs via `bash` + `mv`, never an LLM
rename loop. Do the sequence in an order that avoids collisions —
either highest-down or lowest-up depending on the direction of the
move.

Lands in one checkpoint so `autonovel rollback` undoes the whole
operation.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `--from <A> --to <B> --book <short-name>`.
   Both `A` and `B` must be positive integers. If `A == B`, stop and
   print "nothing to do". If either is missing or out of range
   (greater than the current chapter count), stop with a usage error.

2. Use `file_read` on `books/{book}/outline.md` to confirm chapter
   count and the target's beats. Use `file_read` on
   `books/{book}/chapters/ch_{chapter}.md` (the source `A`) to
   capture the frontmatter — `story_time`, `events`, `pov` — which
   must survive the move untouched.

3. Use `file_read` on `shared/events.md`. If any `rendered_in` row
   names `{book}/ch_{A:02d}` or any chapter between `A` and `B`
   inclusive, surface those rows to the user and ask them to confirm.
   The ledger references are the one thing renumbering cannot fix
   automatically — fiction has room for one chapter to render an
   event, but we should not silently retarget a canonical line.

4. Use `bash` to renumber. Do it in two phases so no two files
   collide on the same name:

   - Move the source out of the way:
     `mv ch_{A:02d}.md ch_{book}_move.md` (use a unique stash name).
   - Shift the block between `A` and `B`. If `B > A`, every chapter
     in `(A, B]` moves down by one (`mv ch_{N:02d}.md ch_{N-1:02d}.md`
     in ascending order). If `B < A`, every chapter in `[B, A)`
     moves up by one (`mv ch_{N:02d}.md ch_{N+1:02d}.md` in
     descending order).
   - Rename the stashed file into its new slot:
     `mv ch_{book}_move.md ch_{B:02d}.md`.

5. Patch the frontmatter of every file whose number changed. Use
   `file_write` to rewrite the YAML block so `chapter:` matches the
   new filename number. Do not touch `story_time`, `events`, `pov`,
   or `status`.

6. Use `file_write` to rebuild `books/{book}/outline.md` so the
   `## Chapter N` headings are in the new order (move the source
   entry into its new slot; renumber the block accordingly).
   Keep every beat line exactly as written.

7. Use `file_read` on `books/{book}/voice.md` only to confirm it is
   present; the voice file is never modified by reorder.

8. Print a one-line summary of the renumber (`ch_{A:02d} → ch_{B:02d};
   shifted N chapters by ±1`) and the list of `shared/events.md` rows
   the user should eyeball.
</workflow>

<acceptance>
- The number of chapter files under `books/{book}/chapters/` is
  unchanged (reorder never adds or removes chapters).
- `books/{book}/chapters/ch_{chapter}.md` at the new position `B`
  has frontmatter `chapter: B` and the original `story_time`,
  `events`, and `pov` from position `A`.
- Every chapter that moved has matching filename number and
  frontmatter `chapter:` field.
- `books/{book}/outline.md` has the same count of `## Chapter N`
  headings as before, and their order reflects the new numbering.
- The command stops without writing if any `rendered_in` row in
  `shared/events.md` pins the moved chapter to its old number and
  the user has not confirmed.
</acceptance>
