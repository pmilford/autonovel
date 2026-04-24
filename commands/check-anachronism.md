---
name: autonovel:check-anachronism
description: Flag period-anachronistic vocabulary (deterministic) and semantic anachronism (LLM) in one chapter.
argument-hint: "<chapter-number> --book <short-name>"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - shared/period_bans.txt
  - shared/world.md
  - books/{book}/chapters/ch_{chapter}.md
writes:
  - books/{book}/edit_logs/ch{chapter:02d}_anachronism.json
context_mode: book
---

<purpose>
Two-pass anachronism scan. The mechanical pass uses the project's
`shared/period_bans.txt` word list and the same `period_bans` subcommand
`/autonovel:evaluate` already calls; the semantic pass asks the judge
for anachronisms the bans list cannot catch (concepts, institutions,
mental frames that did not exist in the period). Writes a JSON report
under `books/{book}/edit_logs/`; does not modify the chapter. Pair
with `/autonovel:revise` if the count is non-trivial.

This is a guardrail, not a taste filter: a false positive is cheap
(the writer ignores it); a false negative ("the apothecary checked
his watch") lands in the published book.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `<chapter-number> --book <short-name>`.
   Missing args are a usage error — stop with a one-line reminder.

2. Use `file_read` on `project.yaml` to resolve the book entry and
   pull `period.start`, `period.end`, `period.region`. These pin
   the window the semantic pass checks against.

3. Deterministic pass. Use the `bash` tool to run:
   `python -m autonovel.mechanical period-bans
    books/{book}/chapters/ch_{chapter}.md shared/period_bans.txt`
   Parse the JSON it prints: `{ "hits": [[word, count], ...],
   "total": N }`. If `shared/period_bans.txt` is missing, treat
   `hits` as empty (the semantic pass still runs).

4. Use `file_read` on `books/{book}/chapters/ch_{chapter}.md` and
   `shared/world.md`. The world bible pins what has already been
   declared period-consistent — something already in the world
   bible cannot be flagged as anachronism in a chapter.

5. Semantic pass (the LLM half). Read the chapter and surface any
   of the following the bans list would miss:
   - Concepts or institutions that did not exist in `period` — e.g.
     "weekend", "privacy" as a right, credit card, public school.
   - Mental frames — modern psychological vocabulary ("trauma" as
     diagnostic, "passive-aggressive", "self-actualize").
   - Material objects that are plausible-sounding but wrong for
     the decade — e.g. printed books before Gutenberg, tomato in
     an Italian kitchen before ~1550, tobacco in Europe before
     ~1560.
   - Metaphors that rely on later technology (clockwork precision
     in a non-mechanical setting, "like a photograph", "laser-
     focused").
   For each flag emit `{quote, reason, period_range,
   suggested_replacement}`. Keep `quote` to ≤ 200 characters;
   `reason` ≤ 2 sentences. Quotes must be exact substrings of the
   chapter.

6. Use `file_write` to save the report to
   `books/{book}/edit_logs/ch{chapter:02d}_anachronism.json` with
   the schema:

   ```json
   {
     "chapter": <N>,
     "book": "<name>",
     "period": {"start": "...", "end": "...", "region": "..."},
     "mechanical": {
       "hits": [["word", count], ...],
       "total": <N>
     },
     "semantic": [
       {"quote": "...", "reason": "...",
        "period_range": "1700-1900",
        "suggested_replacement": "..."}
     ],
     "summary": {
       "mechanical_total": <N>,
       "semantic_total": <N>,
       "verdict": "clean" | "minor" | "significant"
     }
   }
   ```

   Verdict rule: `clean` if both totals are 0; `minor` if combined
   total ≤ 3; `significant` otherwise.

7. Print a one-screen summary to stdout — the verdict, the top
   three hits of each kind, and the suggested next command
   (`/autonovel:revise <N> --book <name>` if `significant`).
</workflow>

<acceptance>
- `books/{book}/edit_logs/ch{chapter:02d}_anachronism.json` exists
  and parses as JSON.
- `mechanical.hits` is present (possibly empty).
- `semantic` is an array (possibly empty) where every element has
  `quote`, `reason`, `period_range`, `suggested_replacement`.
- `summary.verdict` is one of `clean`, `minor`, `significant`.
- The chapter file itself is unchanged (this command never rewrites
  prose; that is `/autonovel:revise`'s job).
</acceptance>
