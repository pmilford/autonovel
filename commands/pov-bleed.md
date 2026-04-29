---
name: autonovel:pov-bleed
description: Heuristic POV-bleed scan — flag interiority lines that name a non-POV character.
argument-hint: "[--book <short-name>] [--summary-only] [--format markdown|json]"
model_tier: light
allowed-tools:
  - bash
reads:
  - shared/characters.md
  - books/{book}/chapters/ch_*.md
writes: []
context_mode: book
---

<purpose>
Close-third POV is the convention for most autonovel drafts. The
classic AI failure mode is bleeding into omniscient: a line in
chapter N narrates what character X *thought*, *felt*, or *knew*,
where X is not the POV character — i.e. the narrator is reaching
inside a head the POV can't reach.

This is a pure-mechanical first pass. It surfaces lines matching
`<NameOfNonPOV> + <interiority verb>` (`thought`, `felt`, `knew`,
`realised`, `wondered`, `remembered`, `hoped`, `feared`,
`believed`, etc.) plus possessive interiority
(`<Name>'s mind / heart / thoughts / memory / longing`) and
counts them per chapter.

The LLM judge in `/autonovel:evaluate` already scores this under
`voice_adherence`; the scanner gives a fast, free pre-flight so
the user can revise before paying for an eval.

False-positive caveat: a non-POV character can legitimately have
their interiority reported by another character ("Niccolò
believed, Lucia could see, that ..."). The scanner can't tell.
Output is a *suggestion list* for human review, not a hard gate.

Pure mechanical. No LLM call. Light tier.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` defaults via
   `_begin`. Optional `--summary-only`. `--format markdown|json`.

2. Use the `Bash` tool to call the housekeeping helper. The
   helper reads every `ch_NN.md` under `books/{book}/chapters/`
   plus `shared/characters.md` for the cast list:

   ```
   autonovel mechanical pov-bleed books/{book} --format <format>
   ```

   The helper:
   - reads `shared/characters.md` to extract the named cast,
   - reads each `ch_NN.md`'s YAML frontmatter `pov:` field,
   - scans the prose for `<Name>` (any cast member NOT the chapter
     POV) immediately followed by an interiority verb, OR
     possessive `<Name>'s` followed by an interiority noun,
   - emits per-chapter counts + a per-line hit list with snippets.

3. If `shared/characters.md` is missing or has no cast entries,
   the helper surfaces a one-line config-needed message.

4. Print the helper's stdout verbatim. Do not editorialise.

5. Do not touch disk. This command is read-only by contract.
</workflow>

<acceptance>
- No files are written.
- When `shared/characters.md` has cast entries, the markdown
  output contains a per-chapter table with `Ch | POV | Words |
  Suspect lines`.
- Without `--summary-only`, each chapter with hits also gets a
  `## Chapter N (POV: <name>)` block with one bullet per
  suspect line, the offending name + verb, and a snippet.
- The header note that "false positives are common — treat as
  a review list, not a gate" appears in every per-chapter block
  with hits.
</acceptance>
