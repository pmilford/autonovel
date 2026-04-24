---
name: autonovel:review
description: Deep dual-persona manuscript review — literary critic plus professor of fiction.
argument-hint: "--book <short-name>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - books/{book}/outline.md
  - books/{book}/chapters/*.md
writes:
  - books/{book}/edit_logs/review.json
  - books/{book}/edit_logs/review.md
context_mode: book
---

<purpose>
Send the full manuscript to a heavy-tier model for a two-persona review:
first a literary critic (newspaper book review style), then a professor
of fiction giving specific, actionable craft suggestions. This is
phase 3b of the revision loop — the signal that the book has stopped
improving in measurable ways. Successor to the deleted `review.py`.

Stop revising when:
  - ★★★★½ or better AND no major unqualified items, OR
  - most flagged items are qualified hedges ("individually fine",
    "largely successful", "cost of ambition"), OR
  - fewer than 3 total items surface.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `--book <short-name>`. Missing is a usage
   error — print a reminder and stop.

2. Use `file_read` on `project.yaml` to get the book title (fall back to
   the book's `seed.txt` first-line title or `books/{book}/outline.md`
   first heading if the config has no explicit title).

3. Use `file_read` to glob `books/{book}/chapters/*.md` in order.
   Concatenate with `\n\n---\n\n` separators into one manuscript
   payload.

4. Run the dual-persona review as a single LLM call with a combined
   prompt: "Read this novel. Review it first as a literary critic
   (like a newspaper book review), then as a professor of fiction with
   specific, actionable craft suggestions. Be fair but honest; you
   don't have to find defects." Use a heavy-tier model (Opus-class);
   Claude Code's runtime picks this via `model_tier: heavy`.

5. Parse the review. Extract:
   - star rating if present (`★★★★½` or similar)
   - professor-stage items as `[{number, title, severity, type,
     qualified, suggestion, full_text}]`
   - severity: `major` | `moderate` | `minor` (keyword match)
   - type: `compression` | `addition` | `mechanical` | `structural` | `revision`
   - qualified: true if the item hedges ("individually fine",
     "largely successful", "costs of ambition", "thematically coherent")

6. Compute the stop-revising verdict per <purpose> above and record it.

7. Use `file_write` twice:
   - `books/{book}/edit_logs/review.json` — the parsed, structured review
   - `books/{book}/edit_logs/review.md` — the raw human-readable review text

8. Print the star rating, item counts (total, major, qualified), and the
   stop verdict with its reason.
</workflow>

<acceptance>
- Both `books/{book}/edit_logs/review.json` and
  `books/{book}/edit_logs/review.md` exist.
- The JSON contains `stars` (number or null), `total_items`,
  `major_items`, `qualified_items`, and a top-level `stop_revising`
  boolean plus `stop_reason` string.
- The Markdown file is at least 500 words of review prose.
</acceptance>
