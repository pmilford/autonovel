---
name: autonovel:vagueness
description: Per-chapter pre-flight scanner for vague/abstract prose — filler nouns (thing, something, a lot), empty intensifiers (very, really), unearned evaluative adjectives (good, beautiful, interesting), and hedges (seemed to, somehow). A review queue for making prose concrete, not a gate.
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
The same flaw that made the teaser voiceover fuzzy ("I bought speed", "the
page no one read") shows up in prose: abstract filler nouns, empty
intensifiers, and unearned evaluative adjectives that *tell* instead of
rendering a concrete, specific image. This scanner casts a wide net to
surface candidate vague lines so a brief / revise pass — or the LLM
**concreteness lens** in `/autonovel:evaluate` — has line-level targets.

Four pattern families flagged (all CANDIDATES, never a gate):

- **filler-noun** — abstract stand-ins for a concrete thing: *thing(s),
  stuff, something, anything, everything, somehow, a lot, sort of, kind of,
  some kind of, a couple of*.
- **empty-intensifier** — modifiers that inflate without meaning: *very,
  really, quite, rather, somewhat, extremely, incredibly, absolutely,
  totally, literally, actually, basically*.
- **empty-evaluative** — adjectives that judge instead of show: *good, bad,
  nice, great, interesting, beautiful, amazing, wonderful, terrible,
  special, important, strange*.
- **hedge** — vagueness/approximation: *seemed to, somehow, in some way,
  more or less, or something, for some reason, in a way*.

The scanner does NOT compute a concreteness score — that's the LLM judge's
job (`/autonovel:evaluate` now scores a *concreteness / specificity* lens).
Many candidates are legitimate (a "good" meal, a "thing" in dialogue); this
is a fast, free review queue for the worst offenders, in the spirit of
`/autonovel:show-dont-tell`.

Pure mechanical. No LLM call. Light tier — runs in milliseconds.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` defaults via `_begin`. Optional
   `--summary-only` (skip the per-line block; emit only the per-chapter
   table). `--format markdown|json`.

2. Use the `bash` tool to call the housekeeping helper. It scans every
   `ch_NN.md` under `books/{book}/chapters/`:

   ```
   autonovel mechanical vagueness books/{book} --format <format>
   ```

   It strips YAML frontmatter, counts hits in each of the four families, and
   emits a per-chapter table plus per-line hit lists with snippets.

3. Print the helper's stdout verbatim. Do not editorialise — these are
   candidates, not verdicts. Point the user to `/autonovel:revise` (or a
   brief) to make the worst lines concrete, and note that
   `/autonovel:evaluate` judges concreteness properly.

4. Do not touch disk. This command is read-only by contract.
</workflow>

<acceptance>
- No files are written.
- Markdown output contains a per-chapter table (one row per drafted
  `ch_NN.md`) with total candidates + density-per-1000-words.
- Without `--summary-only`, each chapter with hits gets a `## Chapter N`
  block listing each candidate by kind + match + snippet.
- The header note framing it as a "review queue, not a gate" appears.
</acceptance>
