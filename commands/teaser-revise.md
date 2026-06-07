---
name: autonovel:teaser-revise
description: Apply the teaser critique's findings to teaser.json IN PLACE — fix the flagged shots, fill the story spine, strengthen dialogue/cards, repair the 4-act order and stakes ladder — WITHOUT regenerating from scratch. The "revise" half of the teaser loop (mirrors how the book pipeline acts on evaluate). Preserves everything that already works.
argument-hint: "--book <short-name> [--provider generic|veo|sora|runway|kling|luma|pollinations] [--max-rounds <n>]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - books/{book}/teaser/teaser.json
  - books/{book}/teaser/critique.md
  - books/{book}/teaser/beats.md
  - books/{book}/treatment.md
  - books/{book}/chapters/*.md
writes:
  - books/{book}/teaser/teaser.json
  - books/{book}/teaser/shots/shot_*.md
context_mode: book
---

<purpose>
The teaser loop is **author → critique → revise**, exactly like the book
pipeline's draft → evaluate → revise. `/autonovel:shot-prompts` authors;
`/autonovel:teaser-critique` finds problems (read-only); **this command
acts on what the critique found and fixes the teaser in place** — so you
never hand-edit `teaser.json` and never lose good work.

The distinction that matters:

  - `/autonovel:shot-prompts --force` **regenerates from scratch** — a
    fresh author pass. Good for a clean restart, but it discards your
    current shots and may introduce *new* problems.
  - `/autonovel:teaser-revise` **edits the existing `teaser.json`** —
    it touches only what the critique flagged (a weak shot prompt, a
    missing spine field, thin dialogue, a missing card, a broken 4-act
    order or stakes ladder) and **leaves everything else exactly as it
    is**. This is the surgical fix loop.

It reads the critique's machine-readable flags *and* the prose suggestions
in `critique.md`, applies them, re-validates, and re-critiques until the
must-fix flags clear (or it reports what's left). No image/video tool is
called — it is free.
</purpose>

<workflow>
**Read-failure policy.** `books/{book}/teaser/teaser.json` is load-bearing
— stop if it is missing (run `/autonovel:shot-prompts` first). If
`books/{book}/teaser/critique.md` is missing, generate findings inline
(step 2) rather than failing. Treat `beats.md`, `treatment.md`, and
`chapters/*.md` as best-effort sources for filling gaps; note and proceed.

1. Parse `$ARGUMENTS`. Required: `--book <short-name>`. Optional:
   `--provider <name>` (default: the `provider` in `teaser.json`),
   `--max-rounds <n>` (default 3 — how many revise→re-critique passes
   before stopping). Confirm the book exists in `project.yaml`.

2. **Get the current findings.** `bash`:
   `autonovel mechanical teaser-critique books/{book}/teaser/teaser.json --provider <name> --format json`
   Parse the `findings` (each `{shot_id, code, message}`). Also `file_read`
   `books/{book}/teaser/critique.md` when it exists for the LLM critic's
   per-shot prose suggestions. If there are **no findings and the file is
   structurally valid**, report "already clean" and stop (nothing to do).

3. **Archive the current script** before editing it (so this revision is
   reversible): `bash`:
   `autonovel mechanical teaser-archive-script books/{book}/teaser/teaser.json`
   (copies it to `teaser/script-takes/teaser_<UTC>.json`).

4. **Apply each finding as a TARGETED edit** to `teaser.json` — `file_read`
   it, fix only what is flagged, `file_write` it back. **Preserve every
   shot/field the critique did not flag** (do not re-author the whole
   teaser, do not renumber shots, do not invent new ones unless a finding
   explicitly requires adding/cutting a beat). Map each flag to its fix:
   - `no-dramatic-question` / `no-logline` / `no-stakes` /
     `no-emotional-arc` / `no-genre` → fill the missing `spine` field,
     pulling it from `beats.md`'s `## Spine` block, else from
     `treatment.md` / canon. Do not overwrite a spine field that is
     already present and fine.
   - `thin-dialogue` → mine 1–3 more **loaded** lines from
     `treatment.md` / `chapters/*.md` (a threat, a vow, a cost named
     aloud) and add them to the most fitting shots' `audio.dialogue`;
     don't pad with filler.
   - `thin-text-cards` → add/strengthen `text_card`s that carry the
     premise (≥2 total; the `title` beat carries the logline).
   - `hook-not-first` / `multiple-hooks` / `no-title` / `button-not-last`
     / `title-after-button` → fix the `role`s / reorder so the 4-act
     shape holds (one `hook` first, one `title` ~2/3, one `button` last).
   - `no-stakes-ladder` / `stakes-not-rising` → set/repair each
     escalation shot's `stakes_level` so it strictly rises in order.
   - `cast-sprawl` → demote extra named faces to silhouettes/crowd
     (clear `subject.name`) so ≤3 named faces remain.
   - `appearance-drift` → reuse ONE appearance string for the subject
     across its shots.
   - `thin-prompt` / `no-palette` / `multi-action` / per-shot prose
     suggestions in `critique.md` → rewrite **only that shot's** prompt
     fields per teaser-craft §4/§5 (one action, palette anchors, concrete
     cinematography). Apply the critic's concrete suggestion when given.
   - `no-reference` → leave as-is here (references are developed in
     `/autonovel:teaser-refs`); note it in the summary.

5. **Validate (hard gate).** `bash`:
   `autonovel mechanical teaser-validate books/{book}/teaser/teaser.json --provider <name>`
   Fix any structural errors and re-run until valid.

6. **Re-critique and loop.** `bash`:
   `autonovel mechanical teaser-critique books/{book}/teaser/teaser.json --provider <name> --format json`
   If must-fix story-spine flags remain (`no-dramatic-question`,
   `no-logline`, `no-stakes`, `no-emotional-arc`, `no-genre`,
   `thin-dialogue`, `thin-text-cards`) and you have rounds left
   (`--max-rounds`), go back to step 4 for another targeted pass. Stop when
   the spine flags are clear or the round budget is spent (report any that
   remain and why).

7. **Re-render the per-shot files** so they match the revised JSON. `bash`:
   `autonovel mechanical teaser-render-prompt books/{book}/teaser/teaser.json --provider <name> --out-dir books/{book}/teaser/shots`

8. Print a one-screen summary — flags **before → after**, what changed
   (per shot / spine field), and the next step:

   ```
   🔧 Revised books/{book}/teaser/teaser.json — {before} flag(s) → {after}.
        Changed: {spine fields filled; shots rewritten; dialogue/cards added}.
        Render gate: {READY | still BLOCKED on: <codes>}.

   {If READY:}  Next: /autonovel:teaser-render --book {book} --provider stub
                (validate free), then a real backend.
   {If BLOCKED:} Re-run /autonovel:teaser-revise --book {book} (more rounds),
                or /autonovel:shot-prompts --book {book} --force for a clean
                re-author if the beats themselves are the problem.
   ```
</workflow>

<acceptance>
- `books/{book}/teaser/teaser.json` is edited IN PLACE: every shot/field the
  critique did NOT flag is byte-for-byte preserved; only flagged items
  change. The prior version is archived to `teaser/script-takes/` first.
- After the run, `autonovel mechanical teaser-critique` reports strictly
  fewer findings than before (and the must-fix story-spine flags are cleared,
  unless reported as un-fixable with a reason).
- `teaser.json` passes `autonovel mechanical teaser-validate`; the per-shot
  files in `books/{book}/teaser/shots/` are regenerated to match.
- No image/video provider is called; the command is free.
- It never regenerates the whole teaser from scratch (that is
  `/autonovel:shot-prompts --force`) — it is the surgical, critique-driven
  revise loop.
</acceptance>
