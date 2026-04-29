---
name: autonovel:show-dont-tell
description: Per-chapter pre-flight scanner for tell-candidate lines (emotion-state, interiority verbs, perception filters, narrator labels).
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
Cast a wider net than the existing slop scanner's small set of
`he felt a surge of` regexes to surface every candidate "tell"
line — so a brief / revise pass (or the LLM judge in
`/autonovel:evaluate`) has line-level targets instead of a single
chapter-level penalty.

Four pattern families flagged:

- **emotion-state**: `<X> was/felt/seemed/appeared/looked
  <emotion>` where `<emotion>` is a curated word like *angry,
  sad, terrified, relieved, ashamed*.
- **interiority**: `<X> knew/realised/understood/recognised/
  sensed/decided/remembered/wondered/hoped/feared/wished` —
  flagged regardless of context; the LLM judge sorts legitimate
  uses (e.g. `she knew the way home`) from telling-not-showing
  uses (e.g. `she knew her brother had betrayed her`).
- **perception-filter**: `<X> looked/sounded/seemed
  <adverb>` patterns (e.g. *looked angrily*, *sounded coldly*)
  that filter the reader's perception through the narrator's
  labelling.
- **narrator-label**: `It was <emotion>` and
  `There was <emotion>` constructions that skip embodiment.

The scanner does NOT compute a tell-vs-show ratio — that's the
LLM judge's job. We surface candidates with location and
snippet so the user can revise the worst ones in a fast loop.

Pure mechanical. No LLM call. Light tier — runs in
milliseconds.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` defaults via
   `_begin`. Optional `--summary-only` (skip the per-line block;
   emit only the per-chapter table). `--format markdown|json`.

2. Use the `Bash` tool to call the housekeeping helper. The
   helper scans every `ch_NN.md` under `books/{book}/chapters/`:

   ```
   autonovel mechanical show-dont-tell books/{book} --format <format>
   ```

   It strips YAML frontmatter,
   counts hits in each of the four pattern families, and emits a
   per-chapter table plus per-line hit lists with snippets.

3. Print the helper's stdout verbatim. Do not editorialise.

4. Do not touch disk. This command is read-only by contract.
</workflow>

<acceptance>
- No files are written.
- Markdown output contains a per-chapter table with one row per
  drafted `ch_NN.md` and columns for each pattern family
  (emotion-state, interiority, perception-filter, narrator-label)
  plus total and density-per-1000-words.
- Without `--summary-only`, each chapter with hits also gets a
  `## Chapter N candidates` block listing each suspect line by
  kind + match + snippet.
- The header note "use as a review queue, not a gate" appears
  when any candidates are listed.
</acceptance>
