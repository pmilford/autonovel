---
name: autonovel:teaser
description: One-command teaser pipeline — plan the beats, then turn them into provider-ready shot prompts, with a free pre-generation critique. Chains teaser-beats → shot-prompts in fresh subagents so the parent context stays clean.
argument-hint: "--book <short-name> [--length 30|60|90|120|180] [--provider generic|veo|sora|runway|kling|luma|pollinations] [--with-treatment] [--force]"
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
writes:
  - books/{book}/teaser/beats.md
  - books/{book}/teaser/teaser.json
  - books/{book}/teaser/shots/shot_*.md
context_mode: book
---

<purpose>
The single entry point for making a teaser. It runs the two free planning
commands in order —

  1. `/autonovel:teaser-beats` → `books/{book}/teaser/beats.md`
     (the hook → escalation → title → button beat-sheet), then
  2. `/autonovel:shot-prompts` → `books/{book}/teaser/teaser.json` +
     `books/{book}/teaser/shots/shot_*.md`
     (the richly-described, provider-ready shot prompts, with the free
     mechanical + LLM pre-generation critique built in).

— and prints one combined summary plus the next step. Nothing here calls
an image/video tool; the whole pipeline is **free**. You can still run the
two commands individually (and hand-edit `beats.md` between them); this is
the convenience wrapper that does both with one invocation.

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
   `--force`. Confirm the book exists in `project.yaml`; if not, stop with
   a one-line usage reminder. Touch no disk on a parse error.

2. **Overwrite guard.** Unless `--force`, check
   `books/{book}/teaser/beats.md` and `books/{book}/teaser/teaser.json`.
   If either already exists with author content, stop with:
   "books/{book}/teaser/* already exists; pass `--force` to regenerate the
   whole teaser, or run `/autonovel:teaser-beats` / `/autonovel:shot-prompts`
   individually to redo just one stage." Pass `--force` through to both
   sub-commands when supplied.

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

6. **Combined summary.** After both stages, read the final
   `books/{book}/teaser/teaser.json` only to count shots / total seconds
   (use `bash`: `autonovel mechanical teaser-validate
   books/{book}/teaser/teaser.json --provider {provider} --format human`),
   then print:

   ```
   🎬 Teaser pipeline complete for {book} ({seconds}s, {provider}).
        beats.md  — {b} beats (hook {h} · escalation {e} · title {t} · button {bt})
        teaser.json — {n} shots, {total}s total · {valid} · {k} advisory flags left
        shots/    — {n} per-shot prompt files

   Edit any prompt in books/{book}/teaser/shots/ or the JSON directly,
   then re-critique with /autonovel:teaser-critique --book {book}.

   Next: generate the clips from these prompts (free dev pass:
   Pollinations — docs/teaser-craft.md / PRD §22), or wait for
   /autonovel:teaser-render (Phase 3.5).
   Re-run /autonovel:teaser --force to rebuild the whole teaser.
   ```
</workflow>

<acceptance>
- After a successful run, `books/{book}/teaser/beats.md`,
  `books/{book}/teaser/teaser.json`, and `books/{book}/teaser/shots/shot_*.md`
  all exist, and `teaser.json` passes `autonovel mechanical teaser-validate`
  for the chosen provider.
- Each stage ran in its own `task` subagent (fresh conversation); the
  parent printed only the combined summary, not the per-shot prose.
- The overwrite guard refuses to clobber an existing `beats.md`/`teaser.json`
  without `--force`.
- No image/video provider is called; the command is free.
- `--with-treatment` runs `/autonovel:treatment` first only when no
  treatment exists, and never blocks the teaser if it is absent.
</acceptance>
