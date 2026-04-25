---
name: autonovel:revise
description: Rewrite one chapter from a brief, preserving voice and continuity.
argument-hint: "<chapter-number> --book <short-name>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/world.md
  - shared/characters.md
  - shared/canon.md
  - books/{book}/voice.md
  - books/{book}/briefs/ch{chapter:02d}.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{prev}.md
writes:
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
  - books/{book}/pending_canon.md
context_mode: book
---

<purpose>
Rewrite chapter `{chapter}` of book `{book}` by following
`books/{book}/briefs/ch{chapter:02d}.md` literally. Preserve voice,
world, and character continuity; obey the brief's cut list, rewrite
list, and target length. Successor to `gen_revision.py`. Bells
learning: the writer overshoots briefs by ~30%; the brief itself
already bakes in the ~0.77 correction, so write to the brief's stated
target, not a mental "safe" overshoot.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `<chapter-number> --book <short-name>`.
   Missing args are a usage error — stop with a one-line reminder.

2. Use `file_read` on `project.yaml` to resolve the book entry and the
   defaults block.

3. Use `file_read` on `books/{book}/briefs/ch{chapter:02d}.md`. If the
   brief is missing, stop and surface:
   "run `/autonovel:brief {chapter} --book {book}` first".

4. Use `file_read` on the shared canon: `shared/world.md`,
   `shared/characters.md`, `shared/canon.md`. These are guardrails, not
   raw material — the chapter must not contradict them.

5. Use `file_read` on `books/{book}/voice.md` (Parts 1 and 2). The
   voice fingerprint is the most important input after the brief.

6. Use `file_read` on `books/{book}/chapters/ch_{chapter}.md` (the
   current draft — the raw material the rewrite carves from) and, if
   the file exists, `books/{book}/chapters/ch_{prev}.md` (where
   `{prev}` = chapter - 1, zero-padded). Keep only the last ~2000
   words of the previous chapter for continuity.

7. Draft the rewrite. Follow the brief exactly. Honor the anti-pattern
   rules:
   - No triadic sensory lists (X. Y. Z.)
   - No "He did not [verb]" more than once
   - No "He thought about [X]" constructions
   - No "the way [X] did [Y]" more than twice
   - No "not X, but Y" formula in narration
   - No over-explaining after showing
   - At most two section breaks
   - At least one moment that genuinely surprises
   - 70%+ in-scene (dialogue and action, not summary)
   - Dialogue sounds like speech, not written prose
   Preserve the chapter's YAML frontmatter (`book`, `chapter`, `pov`,
   `story_time`, `events`) verbatim; update `status` to `revised` and
   recompute `word_count`.

8. Use `file_write` to overwrite
   `books/{book}/chapters/ch_{chapter}.md` with the full revised
   chapter. Do not truncate. Do not summarize.

9. **Regenerate the chapter summary.** Use `file_write` to overwrite
   `books/{book}/chapters/ch_{chapter}.summary.md` with a fresh
   150–250 word continuity summary covering: plot, POV state, cast on
   stage, threads opened, threads closed, story time. The shape is
   the same as `/autonovel:draft` step 12 — this is the continuity
   handoff future drafters will read, so it must reflect the
   *revised* chapter, not the draft it replaced.

10. Use `file_write` to append any new candidate canon facts to
    `books/{book}/pending_canon.md` (or add a single `no new facts`
    line if the rewrite established nothing new). Never edit
    `shared/canon.md` directly — that is what `/autonovel:promote-canon`
    is for.
</workflow>

<acceptance>
- `books/{book}/chapters/ch_{chapter}.md` exists, parses YAML
  frontmatter, and carries `status: revised` plus a fresh `word_count`.
- The rewrite differs from the prior draft (not a byte-for-byte copy).
- Chapter length is within ±15% of the brief's stated target.
- `books/{book}/chapters/ch_{chapter}.summary.md` exists and reflects
  the revised chapter (mtime is newer than the chapter file's prior
  draft).
- `books/{book}/pending_canon.md` grows by at least one line (either a
  candidate fact or the explicit `no new facts` marker).
</acceptance>
