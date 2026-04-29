---
name: autonovel:motifs
description: Per-chapter motif density tracker — how often each motif keyword appears per chapter, with back-half drop warnings.
argument-hint: "[--book <short-name>] [--format markdown|json]"
model_tier: light
allowed-tools:
  - bash
reads:
  - books/{book}/motifs.md
  - books/{book}/chapters/ch_*.md
writes: []
context_mode: book
---

<purpose>
Some books reward repetition of a central image — the bell, the
apothecary's mortar, a recurring colour, an animal that means
something in the book's emotional grammar. AI drafts tend to under-
or over-use these images: the writer drops a motif in a strong
opening chapter, then forgets it for ten chapters; or hammers it
into every paragraph until it stops carrying weight.

This command counts occurrences of each motif's keyword set in
every drafted chapter and emits a per-chapter density table. It
also flags motifs that drop to zero in the back half of the book
(the writer set the image up but didn't pay it off).

Pure mechanical. No LLM. Light tier — runs in seconds, costs
nothing, safe to call repeatedly.

The judgement half — *should* this motif appear in this chapter?
— is left to the writer or to a follow-up brief.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` defaults via
   `_begin`. `--format markdown|json` (default `markdown`).

2. **Config check.** If `books/{book}/motifs.md` does not exist,
   the helper still runs and emits a "no motifs configured"
   message that names the file path. Tell the user how to author
   one:

   ```
   No motifs configured. Create books/{book}/motifs.md with one
   bullet per motif:

       - bells: bell, bells, ringing, peal, toll
       - mortar: mortar, pestle, herb, herbs, balm
       - river: river, current, banks, water

   Then re-run /autonovel:motifs.
   ```

3. Use the `Bash` tool to call the housekeeping helper:

   ```
   autonovel mechanical motifs books/{book} --format <format>
   ```

   The helper reads `books/{book}/motifs.md`, scans every
   `ch_NN.md` under `books/{book}/chapters/` (frontmatter is
   stripped before counting so YAML fields don't inflate hits),
   matches motif keywords on word boundaries (case-insensitive),
   and emits a markdown table with one row per chapter and one
   column per motif. Zero-hit cells render as `·` for visual
   contrast.

4. The helper appends a `## Warnings` section when one or more
   motifs drop to zero in any back-half chapter (`chapter_count
   // 2 + 1` and beyond). The warning fires only if the motif
   was used at least once in the front half — a motif the writer
   simply never used doesn't generate noise.

5. Print the helper's stdout verbatim. Do not editorialise.
</workflow>

<acceptance>
- Output is markdown or JSON per `--format`.
- The markdown table has one row per drafted `ch_NN.md` under
  `books/{book}/chapters/`, in chapter-number order.
- Chapters without any motif hits still appear in the table (every
  motif column shows `·`).
- Books with fewer than 4 chapters skip the back-half warning
  block (too short to diagnose a drop).
- When `motifs.md` is missing or has no parseable bullets, the
  helper emits the no-motifs message and exits 0.
</acceptance>
