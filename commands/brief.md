---
name: autonovel:brief
description: Generate a revision brief for one chapter from cuts, eval, or panel feedback.
argument-hint: "<chapter-number> --book <short-name> [--from cuts|eval|panel|auto]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - books/{book}/voice.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/edit_logs/ch{chapter:02d}_cuts.json
  - books/{book}/edit_logs/reader_panel.json
  - books/{book}/eval_logs/*.json
writes:
  - books/{book}/briefs/ch{chapter:02d}.md
context_mode: book
---

<purpose>
Produce `books/{book}/briefs/ch{chapter:02d}.md` — the targeted revision
instructions the next `/autonovel:revise` run will follow literally.
Default source is `auto`: detect the weakest chapter and assemble a
brief from whatever artifacts are newest (eval log, cuts file, reader
panel). Successor to `gen_brief.py`.

A good brief names specific passages to change, not vague moods.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `<chapter-number> --book <short-name>`.
   `--from` is one of `cuts`, `eval`, `panel`, or `auto` (default
   `auto`). Missing required args are a usage error — print a one-line
   reminder and stop.

2. Use `file_read` on `project.yaml` and `books/{book}/voice.md` for
   voice guardrails the brief must preserve (body-first emotion, no
   telling after showing, no triadic sensory lists, 70%+ in-scene,
   etc. — pull these from the voice.md Part 2 body, don't invent them).

3. Use `file_read` on `books/{book}/chapters/ch_{chapter}.md`. If
   missing, surface the gap and stop.

4. Load source artifacts per `--from`:
   - `cuts`: read
     `books/{book}/edit_logs/ch{chapter:02d}_cuts.json` (run
     `/autonovel:adversarial-edit` first if missing).
   - `eval`: read the most recent
     `books/{book}/eval_logs/ch{chapter:02d}_*.json` file.
   - `panel`: read `books/{book}/edit_logs/reader_panel.json` and
     isolate the entries that name this chapter number.
   - `auto`: read whichever of the above exist, preferring the most
     recent. If two or more exist, merge signals (cuts weighted highest
     because they're the most concrete).

5. Draft the revision brief. Required sections, as Markdown H2s:
   - `## Chapter {chapter} — revision target` (one-line goal)
   - `## What works` (two or three sentences from the source material)
   - `## What drags` (concrete, quote-level, ordered by impact)
   - `## Specific cuts` (quoted passages to remove, carried over from
     the cuts JSON if present)
   - `## Specific rewrites` (before → after snippets where the source
     suggested them)
   - `## Voice guardrails` (bulleted — preserve from voice.md Part 2)
   - `## Weak scenes` *(only when the eval log's
     `beat_coverage.weakest_scenes` array has any entries)* — for
     each entry, write one bullet naming the scene by index, the
     missing beat(s) (goal / conflict / disaster_or_decision /
     consequence), and the prescription verbatim from the eval log
     (or a sharpened version). This is what turns "tighten chapter
     8" into "scene 8.2 needs a decision before the break" — the
     single most surgical brief surface. Quote the scene's
     `opening_line` so the rewrite knows exactly which scene to
     touch. Omit the section when no scenes are weak.
   - `## Stability check` *(only when the eval log's
     `irreversible_change` score is below 7)* — name the chapter's
     final scene, name what reverted (board reset to opening / change
     softened / no consequence committed), and prescribe ONE specific
     irreversible commitment the rewrite must add: a death, a public
     revelation, a signed contract, a destroyed object, a refused
     offer, an oath broken, a door closed. Use the eval log's
     `irreversible_change.fix` verbatim or sharpen it; never fall
     back to vague "raise stakes" — the Stability Trap (AI's default
     to safe, round-edged endings) is the named ceiling failure from
     the Bells production, and only specific irreversible commitments
     break it. Omit the section when the score is ≥7.
   - `## Custom-rubric findings` *(only when present)* — for every
     criterion in the eval log's `custom_rubric` array (or the panel
     log's `custom_rubric` block) that scored below 6 or was named
     by any reader, write one bullet: the rule, the violation
     finding, and the prescription (what the revise should do
     instead). These are the book-specific rules from voice.md Part
     3. They are NOT optional — a brief that ignores a flagged
     custom-rubric finding will produce a revise that still violates
     the rule. Omit the section entirely when no findings apply.
   - `## Target length` (in words — the Bells learning is that
     `gen_revision` overshoots ~30%, so brief for `target × 0.77` if a
     final target applies)

6. Use `file_write` to save to
   `books/{book}/briefs/ch{chapter:02d}.md`. Overwrite any prior brief
   for this chapter — briefs are disposable working documents, not
   canonical artifacts.

7. Print the target length and the count of specific cuts / rewrites
   collected.
</workflow>

<acceptance>
- `books/{book}/briefs/ch{chapter:02d}.md` exists and contains every
  required H2 section from step 5.
- The brief quotes at least one passage from the chapter (no brief can
  be voice-only hand-waving; specificity is the point).
- `## Target length` names a word-count number, not a vague target.
</acceptance>
