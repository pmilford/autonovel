---
name: autonovel:remove-chapter
description: Delete a chapter; renumber subsequent chapters; patch continuity and outline.
argument-hint: "<chapter-number> --book <short-name>"
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
Sidequest: delete chapter `N` from book `{book}`, renumber every
chapter after it by `-1`, and patch continuity so the narrative still
tracks. Updates `books/{book}/outline.md` and surfaces every
`shared/events.md` row whose `rendered_in` points into this book so
the user can reconcile the ledger.

CLAUDE.md: renumber by `bash` + `mv`, never by hand. Work from the
lowest chapter after the hole upward so no two files collide.

Lands in one checkpoint so `autonovel rollback` undoes the whole
operation including the deletion.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `<chapter-number> --book <short-name>`.
   Missing or non-positive integer is a usage error. If the chapter
   does not exist, stop.

2. Use `file_read` on `books/{book}/chapters/ch_{chapter}.md` to
   capture its `story_time`, `events`, and any cross-book pointers
   before deletion. Use `file_read` on `books/{book}/outline.md` to
   locate the entry that is about to disappear.

3. Use `file_read` on `shared/events.md`. Surface every
   `rendered_in` row that names `{book}/ch_{chapter:02d}` or any
   chapter > `{chapter}` in this book. These are the references
   renumbering cannot fix silently — print them as a checklist. If
   any row points at the chapter being deleted, stop until the user
   either promotes the event to a different chapter or confirms the
   event is being retired.

4. Use `file_read` on `books/{book}/voice.md` and the chapter
   immediately before (`ch_{chapter-1:02d}`) and after
   (`ch_{chapter+1:02d}`) the hole. Continuity patching happens by
   drafting a short bridging paragraph at the top of the chapter that
   will take the deleted slot's number. Keep it voice-consistent and
   short — do not rewrite either neighbor wholesale.

5. Use `bash` to delete the file:
   `rm books/{book}/chapters/ch_{chapter:02d}.md`.
   Then renumber upward from the next chapter:
   `mv ch_{chapter+1:02d}.md ch_{chapter:02d}.md`, then
   `mv ch_{chapter+2:02d}.md ch_{chapter+1:02d}.md`, and so on.
   Work in ascending order so each rename writes into an empty slot.

6. Patch the frontmatter of every renamed file with `file_write`.
   The `chapter:` field must match the new filename number. The
   chapter that inherits the deleted slot also receives the one
   bridging paragraph from step 4, merged into its body (after the
   frontmatter block).

7. Use `file_write` to rebuild `books/{book}/outline.md`: delete the
   entry whose `## Chapter {chapter}` header matches the deleted
   file and renumber every subsequent `## Chapter N` heading by
   `-1`. Keep every beat line verbatim.

8. Print a summary: which chapter was deleted, how many chapters
   were renumbered, and the list of `shared/events.md` rows the
   user should eyeball.
</workflow>

<acceptance>
- Exactly one fewer chapter file exists under
  `books/{book}/chapters/` than before the command.
- The deleted chapter's filename is gone; no file at
  `books/{book}/chapters/ch_{chapter:02d}.md` has the original
  chapter's `story_time`, `events`, and `pov` verbatim.
- Every chapter originally numbered > `{chapter}` is now at its old
  number minus one (filenames and frontmatter `chapter:` fields
  agree).
- `books/{book}/outline.md` has exactly one fewer `## Chapter N`
  heading than before, with numbering contiguous.
- If `shared/events.md` had a `rendered_in` row pinning the
  deleted chapter, the command surfaced it and stopped without
  writing until confirmation.
</acceptance>
