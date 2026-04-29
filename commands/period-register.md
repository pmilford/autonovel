---
name: autonovel:period-register
description: Per-chapter table of every period-bans violation across the whole book — register lock for period fiction.
argument-hint: "[--book <short-name>] [--summary-only] [--format markdown|json]"
model_tier: light
allowed-tools:
  - bash
reads:
  - shared/period_bans.txt
  - books/{book}/chapters/ch_*.md
writes: []
context_mode: book
---

<purpose>
Surface every word in your manuscript that violates the period-
register rules in `shared/period_bans.txt`. The single-chapter
scanner runs as part of `/autonovel:evaluate` and
`/autonovel:check-anachronism`; this command rolls the same scan
across every drafted chapter in one pass and emits the worst
offenders so the author can revise focus areas without
re-evaluating the whole book.

Useful before a typeset / publish pass — confirms the book stays
in period across the full run, surfaces clusters that revise
should target.

Pure mechanical. No LLM call. Light tier — runs in milliseconds.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` defaults via
   `_begin`. Optional `--summary-only` (skip per-hit lines;
   emit only the per-chapter table + worst-offenders block).
   `--format markdown|json`.

2. Use the `Bash` tool to call the housekeeping helper:

   ```
   autonovel mechanical period-register books/{book} --format <format>
   ```

   The helper loads `shared/period_bans.txt`, scans every
   `ch_NN.md` under `books/{book}/chapters/` against it (case-
   insensitive, word-boundary), and emits per-chapter hit counts
   plus a worst-offenders summary.

3. If `shared/period_bans.txt` is missing or empty, the helper
   surfaces a one-line message naming the file path. Tell the
   user: "Add one banned word per line; `#` comments allowed."

4. Print the helper's stdout verbatim. Do not editorialise.

5. Do not touch disk. This command is read-only by contract.
</workflow>

<acceptance>
- No files are written.
- When `shared/period_bans.txt` has entries, the markdown output
  contains a per-chapter table and a `## Worst offenders` block
  ranked by total hit count.
- Without `--summary-only`, each chapter with hits also gets a
  `## Chapter N hits` block with one bullet per offending
  line + location + snippet.
- When `shared/period_bans.txt` is missing/empty, the output is
  the configuration-needed message and exits 0.
</acceptance>
