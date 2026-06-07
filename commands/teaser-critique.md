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
     deterministic flags: **story-spine** (no-dramatic-question, no-logline,
     no-stakes, no-emotional-arc, no-genre, thin-dialogue, thin-text-cards),
     **4-act order** (hook-not-first, multiple-hooks, no-title,
     button-not-last, title-after-button), **stakes ladder**
     (no-stakes-ladder, stakes-not-rising), **cast** (cast-sprawl),
     appearance-drift, thin-prompt, no-palette, no-reference, multi-action,
     audio/negative unsupported for the provider, length-mismatch. The
     story-spine subset is the **render gate** (`teaser-render` refuses a
     real generation while any is present; `stub` is exempt) — bp 12.
  2. **LLM critic** — taste the mechanics can't judge. **Story (Phase 6,
     judge first):** does the teaser pose ONE dramatic question and never
     answer it (bp 1, 7)? Does each beat advance or complicate that
     question, and do the stakes *rise* beat to beat (a ladder, not equals,
     bp 3)? Does the **hook signal the genre** in the first ~10 s (bp 9)?
     Do the mined dialogue lines actually reveal stake/relationship/genre,
     or are they filler (bp 5)? Do the text cards carry the premise (bp 6)?
     Does the cut move along the stated emotional arc (bp 8)? Is it built on
     ONE hero face (bp 11)? Is every shot earning its place, or is some shot
     just "the character standing where/when they are" — **restraint**, cut
     it (bp 10)? Does the button **withhold** the resolution (bp 7)?
     **Then per shot:** does each prompt obey
     teaser-craft §4 (one subject, one action, present tense, only what's in
     frame, no un-filmable abstraction)? Is the appearance string reused
     verbatim? Does the shot serve its beat and the arc (hook that
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

4. **LLM critic pass.** `file_read` `books/{book}/teaser/teaser.json`.
   **First judge the story spine** (`docs/teaser-craft.md` §0): is there a
   real dramatic question that stays unanswered? do the beats answer it and
   escalate? is there a stated want + opposing force? do the dialogue lines
   and text cards make the story legible, or would a viewer "learn nothing"?
   does the cut move along the emotional arc? Then, for each shot, judge
   against `docs/teaser-craft.md` §4 (AI-legibility) and §6 (consistency),
   and against the beat it serves:
   - **Legibility:** one subject, one action, one camera move, present
     tense, concrete, only-what's-in-frame, no un-filmable abstraction, no
     legible on-screen text, content-word negatives (never "no …").
   - **Consistency:** the subject's appearance string is identical to every
     other shot with that subject; palette holds the 3-5 anchors.
   - **Service:** the shot earns its place — the hook intrigues without
     explaining *and signals the genre* (bp 9), escalation shots accelerate
     and raise stakes on a rising ladder (bp 3), the title lands ~⅔ in, the
     button deepens the question and does NOT reveal the resolution (bp 7).
     **Restraint** (bp 10): flag any shot that is just "the character
     standing where/when they are" — REWRITE or cut. **Cast** (bp 11): one
     hero face; demote extra named faces. (X-Prize: stakes + a real
     character + visual ambition + an *earned* optimistic future.)
   Rank shots worst-first; for each weak shot, write a one-line diagnosis
   and a concrete rewritten prompt suggestion.

5. **Write `books/{book}/teaser/critique.md`** — an advisory report:

   ```markdown
   # {Display Title} — Teaser critique

   *Provider:* {provider} · *Shots:* {n} · *Total:* {total}s / {target}s ·
   *Structurally:* {valid|INVALID}

   ## Verdict
   {2-3 sentences: is this teaser generation-ready? the top 1-3 things to fix.}

   ## Story spine
   *Dramatic question:* {the question, or ⚠️ MISSING}
   *Want vs. force:* {want — opposing force, or ⚠️ MISSING}
   *Genre:* {genre, or ⚠️ MISSING} · *Emotional arc:* {arc, or ⚠️ MISSING}
   *Dialogue lines:* {n} · *Text cards:* {n} · *4-act order:* {ok | issues}
   *Stakes ladder:* {rising | flat/dips} · *Named faces:* {n}
   *Render gate:* {READY | BLOCKED — lists the story flags that block a real render}
   {2-3 sentences: does it pose a question and withhold the answer? does the
   hook signal the genre? do the beats escalate? does a viewer learn the
   story from the dialogue/cards? one hero face? any filler shots to cut?}

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

6. Print a one-screen summary that **leads with the render-gate verdict and
   the exact next command** (this is the line the user acts on — make it
   unambiguous). Branch on whether the must-fix story-spine flags are
   present:

   **If the gate is READY** (no story-spine must-fix flags):
   ```
   ✅ Render gate: READY — books/{book}/teaser/critique.md written.
        {k} advisory flag(s) left ({r}/{n} shots could be sharpened).
   Next: /autonovel:teaser-render --book {book} --provider stub   (validate free)
         then a real backend.
   ```

   **If the gate is BLOCKED** (must-fix flags remain):
   ```
   ⚠️ Render gate: BLOCKED — {m} must-fix flag(s): {codes}.
        Full report: books/{book}/teaser/critique.md.
   Next: /autonovel:teaser-revise --book {book}
         — APPLIES these fixes to teaser.json in place (no hand edits, no
         regenerate). Then this command re-confirms. (For a clean re-author
         instead, /autonovel:shot-prompts --book {book} --force.)
   ```

   Always name `/autonovel:teaser-revise` as the way to ACT on the findings
   — the user should never be left to hand-edit unless they want to.
</workflow>

<acceptance>
- `books/{book}/teaser/critique.md` exists with a `## Verdict`, a
  `## Story spine` section (dramatic question / want vs. force / genre /
  emotional arc / dialogue + text-card counts / 4-act order / stakes ladder
  / named faces / **render-gate READY-or-BLOCKED**, flagging any missing), a
  `## Mechanical flags` section reflecting the linter output, and per-shot
  notes that mark each shot KEEP or REWRITE.
- The report states whether `teaser.json` is structurally valid (from
  `teaser-validate`) and never mutates `teaser.json`.
- Every mechanical flag from `autonovel mechanical teaser-critique` appears
  in the report; the LLM pass adds taste judgements the linter cannot make.
- No image/video provider is called; the command is free and re-runnable.
</acceptance>
