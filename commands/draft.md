---
name: autonovel:draft
description: Draft one chapter of a book as full prose.
argument-hint: "<chapter-number> --book <short-name>"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
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
  - books/{book}/chapters/ch_{prev}.md
  - books/{book}/chapters/ch_*.summary.md
writes:
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
  - books/{book}/pending_canon.md
context_mode: book
---

<purpose>
Write chapter `{chapter}` of book `{book}` as full prose, obeying the series
voice, world, characters, outline beats, and canon. Respect story-time:
chapters from other books with `story_time` less than or equal to this
chapter's `story_time` are readable context; chapters later in story-time are
off-limits.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `<chapter-number> --book <short-name>`. If the
   chapter number or `--book` is missing, stop and print a one-line usage
   reminder. Do not touch disk.

2. Use `file_read` on `project.yaml`. Resolve the book entry, its `pov`, and
   the defaults block (`chapter_target_words`, `chapter_threshold`).

3. Use `file_read` on `books/{book}/outline.md`. Locate the entry for chapter
   `{chapter}`. Capture its beats, its `story_time`, and any events it
   references. If the chapter is not in the outline, stop and surface the gap.

4. Use `file_read` on `shared/world.md`, `shared/characters.md`,
   `shared/canon.md`, and `shared/events.md`. For every event the outline
   references, use only the `canonical` field and this book's
   `rendered_in` row from `shared/events.md` — ignore other books' POV rows.

5. Use `file_read` on any `shared/research/notes/*.md` that the outline entry
   for this chapter names explicitly. Do not load the full research tree.

6. Use `file_read` on `books/{book}/voice.md`. Both Part 1 (series voice) and
   Part 2 (book fingerprint) are in scope.

7. If `books/{book}/chapters/ch_{prev}.md` exists (where `{prev}` = chapter - 1,
   zero-padded to two digits), read it and keep only the last ~1000 words as
   immediate continuity.

8. **Read every prior summary** for narrative continuity. Use `file_read`
   on `books/{book}/chapters/ch_*.summary.md` for chapters 1 through
   `{prev}` (any that exist). Each file is ~150-250 words and contains
   the chapter's plot, character moves, threads opened, threads
   resolved. Together with the last-1000-words quote from step 7,
   these summaries are the load-bearing context that prevents chapter
   N from forgetting what chapter 1 set up. If a summary is missing
   for a drafted chapter — likely a chapter drafted before this
   summarization step shipped — note the gap but do not regenerate it
   inline; the user can backfill via `/autonovel:summarize-chapter`.

9. Use `task` to fan out loading of sibling-book chapters whose `story_time`
   is less than or equal to this chapter's `story_time`. Budget the loader —
   truncate oldest first, summarize rather than quote beyond ~8000 tokens.

10. Draft the chapter. Target length comes from
   `project.yaml :: defaults.chapter_target_words`. Obey `ANTI-PATTERNS.md`
   and `ANTI-SLOP.md`. Do not use any word that appears in
   `shared/period_bans.txt`.

11. Use `file_write` to write `books/{book}/chapters/ch_{chapter}.md`. Start
    with a YAML frontmatter block per `docs/chapter-frontmatter.md`:
    `book`, `chapter`, `pov`, `story_time` (ISO date or range), `events`,
    `status: drafted`, and `word_count`.

12. **Write the chapter summary.** Use `file_write` to save a
    150–250 word summary at
    `books/{book}/chapters/ch_{chapter}.summary.md`. Cover six things,
    each as a one or two sentence section:
      - **Plot:** what happened in this chapter (action, decisions,
        outcomes — not theme).
      - **POV state:** what the POV character knows, wants, fears at
        the close that they didn't at the open.
      - **Cast on stage:** every named character who appeared,
        with their role in this chapter (e.g. "Tommaso — POV;
        Niccolò — first appearance, declined to speak").
      - **Threads opened:** new mysteries, conflicts, promises this
        chapter introduced that future chapters need to pay off.
      - **Threads closed:** earlier setups this chapter resolved
        (cite the earlier chapter when known).
      - **Story time:** the ISO date or date range covered.
    Future drafts read this file as continuity context (step 8). It
    is NOT a chapter summary for the reader — it is a continuity
    handoff to the next drafter.

13. Use `file_write` to append any new candidate canon facts to
    `books/{book}/pending_canon.md`. If none are new, append a single line
    noting that no new facts were discovered in this chapter. Never edit
    `shared/canon.md` directly — that is what `autonovel promote-canon` is for.
</workflow>

<acceptance>
- `books/{book}/chapters/ch_{chapter}.md` exists and is at least 2000 words.
- Its YAML frontmatter parses and contains `book`, `chapter`, `pov`,
  `story_time`, `events`, and `status: drafted`.
- `books/{book}/chapters/ch_{chapter}.summary.md` exists and is between
  100 and 400 words.
- `books/{book}/pending_canon.md` has at least one new line appended (either
  a candidate fact or an explicit no-new-facts marker).
- No case-insensitive word-boundary match of any word from
  `shared/period_bans.txt` appears anywhere in the chapter body.
</acceptance>
