---
name: autonovel:teaser-critique
description: Free, pre-generation critique of a teaser.json — the mechanical linter plus an LLM critic pass that scores each shot against trailer craft and flags weak prompts before you spend anything on generation. Writes an advisory report.
argument-hint: "--book <short-name> [--provider generic|veo|sora|runway|kling|luma|pollinations]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - books/{book}/teaser/teaser.json
  - books/{book}/treatment.md
  - books/{book}/art/visual_style.json
writes:
  - books/{book}/teaser/critique.md
context_mode: book
---

<purpose>
Criticise a teaser **before generating a single clip** — the cheapest place
to fix it (PRD §24.2). `/autonovel:shot-prompts` runs this critique once,
inline, while authoring; this is the **standalone, re-runnable** version you
point at a hand-edited `books/{book}/teaser/teaser.json` to re-check it
after you've reordered shots, rewritten prompts, or changed provider.

It does two passes and writes one report:

  1. **Mechanical linter** (`autonovel mechanical teaser-critique`) —
     deterministic flags: appearance-drift, thin-prompt, no-palette,
     no-reference, multi-action, audio/negative unsupported for the
     provider, missing hook/button, length-mismatch.
  2. **LLM critic** — taste the mechanics can't judge: does each prompt obey
     teaser-craft §4 (one subject, one action, present tense, only what's in
     frame, no un-filmable abstraction)? Is the appearance string reused
     verbatim? Does the shot serve its beat and the teaser's arc (hook that
     intrigues, escalation that accelerates, a button that withholds the
     ending)? For X-Prize teasers: stakes, a real character, visual ambition.

This command is **read-only on `teaser.json`** — it never mutates the shot
data (that is `/autonovel:shot-prompts`' job, or your own hand-edit). It
writes an advisory report with concrete, copy-pasteable rewrite suggestions
so you can apply the ones you agree with. No image/video tool is called; it
is free.
</purpose>

<workflow>
**Read-failure policy.** `books/{book}/teaser/teaser.json` is load-bearing —
stop if it is missing (run `/autonovel:shot-prompts` first). Treat
`books/{book}/treatment.md` and `books/{book}/art/visual_style.json` as
best-effort context for judging on-brief-ness and palette discipline; note
gaps and proceed without retrying.

1. Parse `$ARGUMENTS`. Required: `--book <short-name>`. Optional:
   `--provider <name>` (default: the `provider` recorded in `teaser.json`,
   else `generic`). Confirm the book exists in `project.yaml`.

2. **Mechanical pass.** Use `bash`:
   `autonovel mechanical teaser-critique books/{book}/teaser/teaser.json --provider <name> --format json`
   Parse the JSON `findings` (each `{shot_id, level, code, message}`). Also
   run `autonovel mechanical teaser-validate books/{book}/teaser/teaser.json --provider <name> --format json`
   so the report states whether the teaser is structurally valid.

3. **Load context (best-effort).** `file_read`
   `books/{book}/treatment.md` (what the film is, the real ending — so you
   can judge whether the button withholds it) and
   `books/{book}/art/visual_style.json` (the canonical palette anchors — so
   you can flag a shot whose palette drifts from the series grade).

4. **LLM critic pass.** `file_read` `books/{book}/teaser/teaser.json`. For
   each shot, judge against `docs/teaser-craft.md` §4 (AI-legibility) and §6
   (consistency), and against the beat it serves:
   - **Legibility:** one subject, one action, one camera move, present
     tense, concrete, only-what's-in-frame, no un-filmable abstraction, no
     legible on-screen text, content-word negatives (never "no …").
   - **Consistency:** the subject's appearance string is identical to every
     other shot with that subject; palette holds the 3-5 anchors.
   - **Service:** the shot earns its place — the hook intrigues without
     explaining, escalation shots accelerate and raise stakes, the title
     lands ~⅔ in, the button deepens the question and does NOT reveal the
     resolution. (X-Prize: stakes + a real character + visual ambition + an
     *earned* optimistic future.)
   Rank shots worst-first; for each weak shot, write a one-line diagnosis
   and a concrete rewritten prompt suggestion.

5. **Write `books/{book}/teaser/critique.md`** — an advisory report:

   ```markdown
   # {Display Title} — Teaser critique

   *Provider:* {provider} · *Shots:* {n} · *Total:* {total}s / {target}s ·
   *Structurally:* {valid|INVALID}

   ## Verdict
   {2-3 sentences: is this teaser generation-ready? the top 1-3 things to fix.}

   ## Mechanical flags ({k})
   {table or list of the linter findings, grouped by code; "none" if clean.}

   ## Per-shot notes (worst first)
   ### {shot id} — {role} — {KEEP | REWRITE}
   *Diagnosis:* {one line.}
   *Suggested prompt:* {the concrete rewrite, or "—" if KEEP.}

   ## Arc & pacing
   {does it hook → escalate → title → button? pacing accelerate then hold?
   does the button withhold the ending? cast discipline (one hero face)?}
   ```

6. Print a one-screen summary: structurally valid?, mechanical flag count
   by code, count of shots marked REWRITE, the single highest-value fix, and
   the next step:

   ```
   🔎 Wrote books/{book}/teaser/critique.md — {valid}; {k} mechanical flags,
        {r}/{n} shots flagged for rewrite. Top fix: {one line}.

   Apply the rewrites you agree with (edit teaser.json or the shot files,
   or re-run /autonovel:shot-prompts --force), then re-run this to confirm.
   ```
</workflow>

<acceptance>
- `books/{book}/teaser/critique.md` exists with a `## Verdict`, a
  `## Mechanical flags` section reflecting the linter output, and per-shot
  notes that mark each shot KEEP or REWRITE.
- The report states whether `teaser.json` is structurally valid (from
  `teaser-validate`) and never mutates `teaser.json`.
- Every mechanical flag from `autonovel mechanical teaser-critique` appears
  in the report; the LLM pass adds taste judgements the linter cannot make.
- No image/video provider is called; the command is free and re-runnable.
</acceptance>
