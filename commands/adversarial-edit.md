---
name: autonovel:adversarial-edit
description: Ask the judge to find 10-20 cut or rewrite candidates in one chapter.
argument-hint: "<chapter-number> --book <short-name>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - books/{book}/voice.md
  - books/{book}/chapters/ch_{chapter}.md
writes:
  - books/{book}/edit_logs/ch{chapter:02d}_cuts.json
context_mode: book
---

<purpose>
Adversarial edit: ask the judge to identify 10-20 specific passages in
one chapter that should be cut or rewritten. The output is a structured
cuts file — `/autonovel:apply-cuts` consumes it deterministically. The
cut list IS the revision plan. Per the Bells production learnings,
OVER-EXPLAIN and REDUNDANT dominate (~58% combined) and should be
prioritised.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `<chapter-number> --book <short-name>`.
   Missing args are a usage error — stop and surface a one-line reminder.

2. Use `file_read` on `project.yaml` to resolve the book entry.

3. Use `file_read` on `books/{book}/voice.md` — both parts. The voice
   defines what counts as "borrowed" versus "earned" in this book, so
   the judge needs it before grading.

4. Use `file_read` on `books/{book}/chapters/ch_{chapter}.md`. If the
   file is missing or empty, stop and surface the gap.

5. Run the adversarial-edit LLM pass with a ruthless-editor system
   prompt ("you quote exactly from the text; you never paraphrase; you
   respond with valid JSON"). Ask for 10-20 specific passages to cut or
   rewrite. Each cut must:
   - quote at least 25 characters of the original text verbatim so
     `/autonovel:apply-cuts` can find it unambiguously
   - classify as one of `FAT | REDUNDANT | OVER-EXPLAIN | GENERIC | TELL | STRUCTURAL`
   - give an action: `CUT` or `REWRITE`
   - for REWRITE, supply a replacement
   - include a one-line reason

6. Compute totals: `total_cuttable_words`, `overall_fat_percentage`
   (cuttable ÷ original × 100, rounded), a `tightest_passage` quote,
   a `loosest_passage` quote, and a one-sentence verdict.

7. Use `file_write` to save the result to
   `books/{book}/edit_logs/ch{chapter:02d}_cuts.json` with the exact
   shape:
   ```json
   {
     "cuts": [
       {"quote": "...", "type": "OVER-EXPLAIN", "reason": "...",
        "action": "CUT", "rewrite": null}
     ],
     "total_cuttable_words": N,
     "overall_fat_percentage": N,
     "tightest_passage": "...",
     "loosest_passage": "...",
     "one_sentence_verdict": "..."
   }
   ```

8. Print a one-screen summary: cut count, % fat, dominant types, verdict.
</workflow>

<acceptance>
- `books/{book}/edit_logs/ch{chapter:02d}_cuts.json` exists and parses
  as a JSON object with a `cuts` array.
- Every cut entry has `quote` (≥25 chars), `type` (one of the six
  legal types), and `action` (one of `CUT` | `REWRITE`).
- `overall_fat_percentage` is a number in [0, 100].
- No cut quote is a fabrication — every `quote` is a substring of the
  chapter (case-sensitive, exact or whitespace-normalised).
</acceptance>
