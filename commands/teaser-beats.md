---
name: autonovel:teaser-beats
description: Select the 8-20 teaser-worthy beats (hook → escalation → title → button) from a book's story, honouring trailer craft. Writes the hand-editable beat-sheet that shot-prompts turns into shot prompts.
argument-hint: "--book <short-name> [--length 30|60|90|120|180] [--provider generic|veo|sora|runway|kling|luma|pollinations] [--force]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - books/{book}/treatment.md
  - books/{book}/outline.md
  - books/{book}/eval_logs/*.json
  - books/{book}/chapters/*.md
  - books/{book}/teaser/beats.md
writes:
  - books/{book}/teaser/beats.md
context_mode: book
---

<purpose>
Pick the moments a teaser is built from. A teaser sells a **tone and a
question**, not the plot (see `docs/teaser-craft.md`). This command reads
the story and selects 8-20 **beats** arranged on the teaser arc —
**hook → escalation → title → button** — then writes a hand-editable
beat-sheet at `books/{book}/teaser/beats.md`. The next command,
`/autonovel:shot-prompts`, turns each beat into provider-ready shot
prompts.

It does NOT generate prompts or call any image/video tool. It is the
cheap, free planning step you edit before spending anything.

The mechanical budget (how many beats/shots, per-role timing) comes from
`autonovel mechanical teaser-plan`, so the creative selection works to a
target instead of guessing.
</purpose>

<workflow>
**Read-failure policy.** `books/{book}/outline.md` (or
`books/{book}/treatment.md`) is the load-bearing spine — stop if neither
exists. Treat `eval_logs/*.json` and `chapters/*.md` as best-effort
enrichment; if a read fails, note the gap and proceed. Do not retry on
`file_read` errors for the best-effort inputs.

1. Parse `$ARGUMENTS`. Required: `--book <short-name>`. Optional:
   `--length <seconds>` (default: `project.yaml :: teaser.length_s` if
   set, else `90`; use `180` for the Future Vision X-Prize 3-minute
   trailer), `--provider <name>` (default `generic`), `--force`.

2. **Refusal-on-overwrite.** If `books/{book}/teaser/beats.md` already
   exists with author edits and `--force` was not passed, stop with:
   "books/{book}/teaser/beats.md already exists; pass `--force` to
   regenerate or hand-edit it directly".

3. **Get the budget.** Use the `bash` tool:
   `autonovel mechanical teaser-plan --length <seconds> --provider <name> --format human`
   This prints the recommended beat count, shot count, and per-role
   timing (hook 4-6s, escalation 1.5-2.5s cuts, title ~2/3 in, button
   3-5s). Aim for the printed `beat_target`.

4. **Read the story.** Prefer `books/{book}/treatment.md` when it exists
   (it is already a film-shaped narrative — the best beat source); else
   read `books/{book}/outline.md` for the spine. Use
   `books/{book}/eval_logs/*.json` to find the load-bearing /
   highest-tension scenes (the `pacing` and `irreversible_change`
   signals) — those earn teaser beats. Skim `books/{book}/chapters/*.md`
   only for the concrete image of a chosen beat (best-effort).

5. **Select the beats** on the teaser arc, applying
   `docs/teaser-craft.md` craft:
   - **hook** (1 beat): the single most arresting image or the dramatic
     question. Intrigue, don't explain.
   - **escalation** (most beats): rising stakes, accelerating; each beat
     a visible turn, not exposition.
   - **title** (1 beat): where the title card lands (~2/3 in).
   - **button** (1 beat): a final beat AFTER the title that deepens the
     question. **Withhold the ending** — for `--audience`-style optimism
     (X-Prize) you may reveal the *vision* but never the *resolution*.
   Keep to ~one protagonist face (cast discipline, teaser-craft §7.2).

6. **Write `books/{book}/teaser/beats.md`** in this shape (hand-editable;
   shot-prompts reads it back):

   ```markdown
   # {Display Title} — Teaser beat-sheet

   *Length:* {seconds}s · *Provider target:* {provider} · *Beats:* {n}

   <!-- Edit freely: reorder, rewrite, add/cut beats. Then run
        /autonovel:shot-prompts --book {book}. -->

   ## B01 — hook
   *Source:* {outline beat / eval peak / chapter N}
   {One-line beat note: the visible moment + why it hooks.}

   ## B02 — escalation
   ...

   ## B{n} — button
   {The final after-title beat. Withhold the resolution.}
   ```

7. Print a one-screen summary: beat count by role, target length, and the
   next step:

   ```
   🎬 Wrote books/{book}/teaser/beats.md — {n} beats
        (hook {h} · escalation {e} · title {t} · button {b}), target {seconds}s.

   Edit the beats if you like, then:
     /autonovel:shot-prompts --book {book} --provider {provider}
   ```
</workflow>

<acceptance>
- `books/{book}/teaser/beats.md` exists, opens with a
  `# ... Teaser beat-sheet` heading, and lists beats with `## B<NN> —
  <role>` headings where role ∈ {hook, escalation, title, button}.
- Beat count is within the range printed by `teaser-plan` (≥6, ≤20),
  with exactly one `hook` and at least one `button`.
- The button beat does not reveal the story's resolution (withholding).
- Refusal on overwrite without `--force` is the default.
- No image/video tool is invoked; the command is free.
</acceptance>
