---
name: autonovel:dashboard
description: Per-book at-a-glance dashboard — score / tension / pacing curve / aggregates / drop alarms. Re-renders without firing evaluate.
argument-hint: "[--book <short-name>] [--threshold <float>] [--format markdown|json]"
model_tier: light
allowed-tools:
  - bash
reads:
  - books/{book}/chapters/ch_*.md
  - books/{book}/chapters/ch_*.summary.md
  - books/{book}/eval_logs/*.json
  - books/{book}/motifs.md
writes: []
context_mode: book
---

<purpose>
The shape of the book at a glance. `/autonovel:evaluate --full`
already computes per-chapter score, tension, dialogue %, scene
count, beats-hit, and `irreversible_change`, but reading them
requires re-running evaluate (heavy-tier LLM cost) or hand-
parsing an old eval log. This command re-renders the latest
`<ts>_full.json` you already have, augments it with mechanical
dimensions that don't need an LLM (cast size, scene count,
dialogue density, motif density), and adds two visualisations
the original `--full` table didn't have:

- **Sparklines** for the score and tension series so the
  *shape* is visible at a glance (`▁▂▅▇▆▄▂▁` per chapter).
- **Per-book aggregates** — chapter count, mean / median /
  range / stdev of score, longest sub-threshold streak,
  tension mean and range — so multi-book series surface "Book
  Two has a flat back third" without manually scanning ten
  chapters.

It also re-runs the **tension-drop alarm** from
`/autonovel:evaluate --full` (≥3 consecutive chapters of
declining tension) so the user can act on the trend even
without an LLM turn.

Pure mechanical. No LLM call. Light tier — runs in
milliseconds, costs nothing.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` defaults via
   `_begin`. Optional `--threshold <float>` (default 7.0; pass
   the project's `chapter_threshold` from project.yaml when set
   per-series). Optional `--format markdown|json` (default
   `markdown`).

2. Use the `Bash` tool to call the housekeeping helper:

   ```
   autonovel mechanical dashboard books/{book} --threshold {T} --format <format>
   ```

   The helper inspects:
   - Chapter frontmatter (word counts, POV) and prose (scene
     breaks, dialogue density).
   - Each chapter's matching `ch_NN.summary.md` for cast size.
   - The latest `<ts>_full.json` under `eval_logs/` for tension,
     beats hit, and `irreversible_change`. When no full-mode
     eval has run, those columns show `—` and the source
     footer notes the gap.
   - Per-chapter eval logs for the latest `overall_score` per
     chapter (handles all three production naming conventions).
   - `books/{book}/motifs.md` if present, for per-chapter total
     motif keyword hits.

3. Print the helper's stdout verbatim. Do not editorialise.

4. The output ends with a `_sources_` block naming where each
   column came from. Surface this to the user when they ask
   "why is this column missing?" — typically the answer is
   "run `/autonovel:evaluate --full --book {book}` to populate
   tension / beats / irreversible_change".

5. Do not touch disk. This command is read-only by contract.
</workflow>

<acceptance>
- No files are written.
- Markdown output contains a per-chapter table with one row per
  drafted `ch_NN.md`, in chapter-number order.
- Columns with no populated values are omitted (no all-em-dash
  columns).
- When at least one chapter has a score, a `score:` sparkline
  line follows the table; same for tension when populated.
- When at least one tension-drop window of length ≥3 is
  detected, the output includes a `## ⚠️ Tension drops` block
  with revision-pass suggestions.
- When `--format json`, every cell value is the same as in the
  markdown table (no rounding loss, no display-only formatting).
- The output ends with a `_sources_` provenance footer.
</acceptance>
