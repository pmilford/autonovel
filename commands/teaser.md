---
name: autonovel:teaser
description: One-command teaser pipeline — plan the beats, turn them into provider-ready shot prompts, then run the critique→revise loop to a READY render gate. Chains teaser-beats → shot-prompts → (teaser-critique ⟳ teaser-revise) in fresh subagents so the parent context stays clean. All free; stops before any render.
argument-hint: "--book <short-name> [--length 30|60|90|120|180] [--provider generic|veo|sora|runway|kling|luma|pollinations] [--with-treatment] [--revise-rounds <n>] [--no-revise] [--force]"
model_tier: standard
allowed-tools:
  - file_read
  - bash
  - task
reads:
  - project.yaml
  - books/{book}/treatment.md
  - books/{book}/teaser/beats.md
  - books/{book}/teaser/teaser.json
  - books/{book}/teaser/critique.md
writes:
  - books/{book}/teaser/beats.md
  - books/{book}/teaser/teaser.json
  - books/{book}/teaser/shots/shot_*.md
  - books/{book}/teaser/critique.md
context_mode: book
---

<purpose>
The single entry point for making a teaser. It runs the free planning
pipeline end-to-end —

  1. `/autonovel:teaser-beats` → `books/{book}/teaser/beats.md`
     (the story spine + hook → escalation → title → button beat-sheet), then
  2. `/autonovel:shot-prompts` → `books/{book}/teaser/teaser.json` +
     `books/{book}/teaser/shots/shot_*.md`
     (the richly-described, provider-ready shot prompts, with the free
     mechanical + LLM pre-generation critique built in), then
  3. the **critique → revise loop**: `/autonovel:teaser-critique` writes the
     verdict, and `/autonovel:teaser-revise` **applies its findings in place**
     (filling the spine, strengthening dialogue/cards, repairing the 4-act
     order + stakes ladder) — looping until the **render gate is READY** or
     the round budget is spent. This is what gets you a renderable teaser
     from one command instead of leaving you to fix the critique by hand.

— then it prints one combined summary plus the next step. Nothing here calls
an image/video tool; the whole pipeline is **free** and **stops before any
render** (rendering is the deliberate, quota-bearing `/autonovel:teaser-render`
step, with its own free stub-validate + approval gate). You can still run the
sub-commands individually (and hand-edit `beats.md` between them); this is the
convenience wrapper that does all three with one invocation.

Each stage runs in a **fresh `task` subagent conversation** so the parent
doesn't accumulate the (heavy) shot-authoring prose + tool output — the
same context-hygiene discipline `/autonovel:draft-pass` uses for long
sweeps. The subagents do all the writing; this command coordinates and
reports.

Craft lives in `docs/teaser-craft.md` (read by the sub-commands). The
treatment (the prose deliverable that *reveals* the ending) is a separate
command, `/autonovel:treatment`; pass `--with-treatment` to run it first
when no treatment exists yet.
</purpose>

<workflow>
**Read-failure policy.** `project.yaml` is load-bearing — stop if it is
missing or `--book` names no known book. `books/{book}/treatment.md`,
`beats.md`, and `teaser.json` are checked only for existence (overwrite
guard); never retry their reads.

1. Parse `$ARGUMENTS`. Required: `--book <short-name>`. Optional:
   `--length <seconds>` (default: `project.yaml :: teaser.length_s` if
   set, else `90`; use `180` for the Future Vision X-Prize 3-minute
   trailer), `--provider <name>` (default `generic`), `--with-treatment`,
   `--revise-rounds <n>` (default `2` — how many critique→revise passes the
   loop may run), `--no-revise` (skip the loop; stop after shot-prompts),
   `--force`. Confirm the book exists in `project.yaml`; if not, stop with
   a one-line usage reminder. Touch no disk on a parse error.

2. **Overwrite guard.** Unless `--force`, check
   `books/{book}/teaser/beats.md` and `books/{book}/teaser/teaser.json`.
   If either already exists with author content, stop with:
   "books/{book}/teaser/* already exists; pass `--force` to regenerate the
   whole teaser, or run `/autonovel:teaser-beats` / `/autonovel:shot-prompts`
   individually to redo just one stage." Pass `--force` through to both
   sub-commands when supplied. With `--force`, each sub-command **archives
   the prior `beats.md` / `teaser.json` to `teaser/script-takes/`** before
   regenerating (so a full re-run never loses a previous script), and the
   character/location reference originals in `teaser/refs/` are reused
   untouched — re-running the whole pipeline changes the scripts but keeps
   the approved portraits and location plates.

3. **(optional) Treatment.** If `--with-treatment` was passed AND
   `books/{book}/treatment.md` does not already exist, spawn a `task`
   subagent to run `/autonovel:treatment --book {book}` (it reads the
   foundation and writes the treatment + brief). Wait for it. Skip
   silently if the treatment already exists or the flag was not passed —
   `shot-prompts` treats the treatment as best-effort enrichment.

4. **Stage 1 — beats.** Use the `task` tool to spawn a **fresh subagent
   conversation** and instruct it to run, exactly:
   `/autonovel:teaser-beats --book {book} --length {seconds} --provider {provider}{force}`
   (append ` --force` when `--force` was passed). Wait for it to finish.
   The subagent writes `books/{book}/teaser/beats.md`; capture only its
   one-line summary (beat counts by role, target length). If it reports a
   hard failure (e.g. no `outline.md`/`treatment.md` spine), stop and
   relay it — do not proceed to stage 2.

5. **Stage 2 — shot prompts.** Spawn a second **fresh `task` subagent**
   and instruct it to run, exactly:
   `/autonovel:shot-prompts --book {book} --length {seconds} --provider {provider}{force}`.
   Wait for it. This is the heavy stage: it authors the shots, runs the
   hard `teaser-validate` gate and the free `teaser-critique` + LLM critic
   pass, and writes `books/{book}/teaser/teaser.json` plus
   `books/{book}/teaser/shots/shot_*.md`. Capture its one-line summary
   (shot count, total seconds vs target, remaining advisory flags).

6. **Stage 3 — critique → revise loop (skip if `--no-revise`).** Spawn a
   third **fresh `task` subagent** and instruct it to run, exactly:
   `/autonovel:teaser-revise --book {book} --provider {provider} --max-rounds {revise_rounds}`.
   Wait for it. `teaser-revise` internally runs the mechanical critique,
   **applies the findings to `teaser.json` in place** (it is a no-op that
   reports "already clean" when there is nothing to fix — e.g. shot-prompts
   already produced a READY teaser), re-critiques, and loops up to
   `--max-rounds` until the **render gate is READY** or the budget is spent.
   It writes `books/{book}/teaser/critique.md` along the way. Capture its
   final one-line summary (flags before → after, gate READY/BLOCKED). Never
   fail the pipeline over a still-BLOCKED gate — relay it so the user can run
   another `teaser-revise` round or hand-edit.

7. **Combined summary.** Read the final gate status — `bash`:
   `autonovel mechanical teaser-critique books/{book}/teaser/teaser.json --provider {provider} --format json`
   (a story-spine flag in `findings` ⇒ gate BLOCKED; none ⇒ READY) — and the
   shot count via `autonovel mechanical teaser-validate … --format human`,
   then print:

   ```
   🎬 Teaser pipeline complete for {book} ({seconds}s, {provider}).
        Question: "{the dramatic question — the spine the teaser rides}"
        beats.md  — {b} beats (hook {h} · escalation {e} · title {t} · button {bt})
        teaser.json — {n} shots, {total}s total · {valid} · {k} advisory flags left
                      ({d} dialogue lines · {c} text cards)
        shots/    — {n} per-shot prompt files
        Render gate: {READY ✅ | BLOCKED ⚠️ on: <codes>}  (after {r} revise round(s))

   {If READY:}
   Next: develop references, then render:
     /autonovel:teaser-refs --book {book} --with-locations   (approve faces + places)
     /autonovel:teaser-render --book {book} --provider stub  (validate the chain free)
   then a real backend (see docs/teaser-render-providers.md). The render
   gate is READY, so a real render won't be refused.

   {If still BLOCKED:}
   The story gate is still BLOCKED on {codes}. Run one more
   /autonovel:teaser-revise --book {book}, or hand-edit teaser.json
   (see books/{book}/teaser/critique.md). Re-run /autonovel:teaser --force
   to rebuild from scratch.
   ```
</workflow>

<acceptance>
- After a successful run, `books/{book}/teaser/beats.md`,
  `books/{book}/teaser/teaser.json`, and `books/{book}/teaser/shots/shot_*.md`
  all exist, and `teaser.json` passes `autonovel mechanical teaser-validate`
  for the chosen provider.
- Unless `--no-revise`, Stage 3 ran the critique→revise loop and the summary
  reports the **render-gate verdict** (READY, or BLOCKED with the codes); a
  still-blocked gate is relayed, never a hard failure.
- Each stage ran in its own `task` subagent (fresh conversation); the
  parent printed only the combined summary, not the per-shot prose.
- The overwrite guard refuses to clobber an existing `beats.md`/`teaser.json`
  without `--force`.
- No image/video provider is called; the command is free and stops before
  any render.
- `--with-treatment` runs `/autonovel:treatment` first only when no
  treatment exists, and never blocks the teaser if it is absent.
</acceptance>
