---
name: autonovel:impact-of
description: After a foundation mutation, list the chapters that reference the old fact and need revising — kills the ls / grep / cat workflow.
argument-hint: "[--book <short-name>] [--source promote-canon] [--format markdown|json]"
model_tier: light
allowed-tools:
  - bash
reads:
  - shared/canon.md
  - books/{book}/chapters/ch_*.md
writes: []
context_mode: book
---

<purpose>
"What should I revise after `/autonovel:promote-canon`?" — the
exact "now what?" moment that used to require manual `ls` +
`grep` across `shared/canon.md` Superseded blocks and
`books/<book>/chapters/`. autonovel exists to collapse that
investigation into one command.

This command is the mechanical first pass: parse every
`## Superseded <date>` block in `shared/canon.md`, extract the
tokens unique to each prior value (i.e. the "wrong values" still
potentially in chapter prose), grep every chapter for them, and
emit a per-chapter action checklist of `/autonovel:revise
--chapter N` calls.

Mechanical, candidate-generator only — per the brittle-Python
rule, this is a review list not a quality gate. Some matches
will be false positives (a year that coincides with the flipped
fact in unrelated context, a name reused with a different
meaning); skim each snippet before revising. The LLM-side
semantic scan that adds cross-chapter reasoning is queued as a
follow-up in FUTURE-TODOS.

Pure mechanical. No LLM call. Light tier — milliseconds.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` defaults via
   `_begin`. Optional `--source promote-canon` (the only source
   supported today; future sources may include `research`,
   `voice-discovery`, etc.). Optional `--format markdown|json`
   (default `markdown`).

2. Use `bash` to invoke the helper:

   ```
   autonovel mechanical impact-of books/{book} --source promote-canon
   ```

   The helper:
     - parses `shared/canon.md` for `## Superseded <UTC-date>`
       blocks (the exact format `/autonovel:promote-canon`
       writes when a research-tagged entry beats a prior fact)
     - extracts (prior_value, new_value) pairs and computes
       tokens unique to prior — those are the "values still
       potentially in chapter prose" worth grepping for
     - greps every `books/{book}/chapters/ch_*.md` for those
       tokens (case-insensitive, word-boundary), strips the
       YAML frontmatter before scanning so frontmatter fields
       don't inflate matches
     - emits a markdown report grouped by superseded fact,
       ending in an action checklist of `/autonovel:revise
       --chapter N` calls

3. Print the helper's stdout verbatim. Do not editorialise.

4. Do not touch disk. This command is read-only by contract.
</workflow>

<acceptance>
- No files written.
- Every chapter referenced in the action plan has at least one
  matched line snippet shown above it (so the user can judge
  the false-positive risk before acting).
- When `shared/canon.md` has no `## Superseded` blocks, the
  output explains that this means no facts flipped during the
  most recent promote-canon — nothing to act on here.
</acceptance>
