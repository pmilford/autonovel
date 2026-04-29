---
name: autonovel:dialogue
description: Per-chapter dialogue-mechanics linter — adverb-heavy speech tags, said-bookisms, repeated speech-verb stutters.
argument-hint: "[--book <short-name>] [--summary-only] [--format markdown|json]"
model_tier: light
allowed-tools:
  - bash
reads:
  - books/{book}/chapters/ch_*.md
writes: []
context_mode: book
---

<purpose>
Pure-mechanical pre-flight scanner for the small set of dialogue
patterns that are reliable AI tells: adverb-heavy speech tags
(*"she said quietly"*), said-bookisms in dense clusters
(*exclaimed / murmured / whispered* within a few lines), and
repeated-speech-verb stutters (the same non-`said` verb three
times within ten lines).

This catches the long tail of dialogue tells before they reach a
heavy-tier evaluate run — the LLM judge already covers them under
`prose_quality` but only on chapters that have been evaluated. This
scanner runs over the whole book in milliseconds, costs nothing,
and surfaces hit lines with location so the user can fix them in a
fast revise loop.

Pure mechanical. No LLM call. Light tier.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` defaults via
   `_begin`. Optional `--summary-only` (skip the per-hit block;
   show only the per-chapter table). `--format markdown|json`.

2. Use the `Bash` tool to call the housekeeping helper:

   ```
   autonovel mechanical dialogue books/{book} --format <format>
   ```

   The helper scans every `ch_NN.md` under
   `books/{book}/chapters/`, strips YAML frontmatter, and emits
   per-chapter counts of: adverb tags (`said quietly`-style),
   said-bookisms (`exclaimed`, `murmured`, etc.), and stutters
   (one non-said verb 3+ times within a 10-line window).

3. Print the helper's stdout verbatim. Do not editorialise.

4. Do not touch disk. This command is read-only by contract.
</workflow>

<acceptance>
- No files are written.
- Markdown output contains a per-chapter table with one row per
  drafted `ch_NN.md` in chapter-number order.
- When the per-chapter total is >0 and `--summary-only` is not
  passed, the output includes a `## Chapter N hits` block with
  one bullet per offending line + location + snippet.
- When `--format json`, every count from the markdown output is
  recoverable from the JSON.
</acceptance>
