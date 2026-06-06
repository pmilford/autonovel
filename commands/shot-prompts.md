---
name: autonovel:shot-prompts
description: Turn a teaser beat-sheet into provider-ready, heavily-described shot prompts (the core deliverable). Fills the structured shot schema, runs a free pre-generation critique, and writes teaser.json + per-shot markdown.
argument-hint: "--book <short-name> [--provider generic|veo|sora|runway|kling|luma|pollinations] [--length <seconds>] [--force]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - books/{book}/teaser/beats.md
  - shared/world.md
  - shared/characters.md
  - books/{book}/voice.md
  - books/{book}/art/visual_style.json
  - books/{book}/treatment.md
  - books/{book}/chapters/*.md
  - books/{book}/teaser/teaser.json
writes:
  - books/{book}/teaser/teaser.json
  - books/{book}/teaser/shots/shot_*.md
context_mode: book
---

<purpose>
The core deliverable of teaser mode: turn each beat in
`books/{book}/teaser/beats.md` into one or more **richly-described shot
prompts** a video model will obey. Output is two things:

  - **`books/{book}/teaser/teaser.json`** — the machine-readable, ordered
    list of shots in the structured schema (PRD §8): framing, subject +
    verbatim appearance, one action, setting, lighting, palette, camera
    move, lens, style, mood, separate negative prompt, separate dialogue,
    consistency anchors.
  - **`books/{book}/teaser/shots/shot_<id>.md`** — hand-editable,
    copy-paste-ready prompt files, rendered deterministically from the
    schema in canonical Veo/Sora order.

A **free, pre-generation critique** runs before you spend anything: the
mechanical linter plus an LLM critic pass that rewrites weak prompts —
catching most failures for $0 (PRD §24.2). No image/video tool is
called; you take these prompts to your generator (or, later,
`/autonovel:teaser-render`).

Craft rules are in `docs/teaser-craft.md` — read it; the discipline
below (one action per shot, verbatim appearance, palette lock, content-word
negatives) comes from there.
</purpose>

<workflow>
**Read-failure policy.** `books/{book}/teaser/beats.md` and
`shared/characters.md` are load-bearing — stop if the beat-sheet is
missing (run `/autonovel:teaser-beats` first). Treat `voice.md`,
`art/visual_style.json`, `treatment.md`, and `chapters/*.md` as
best-effort enrichment; note gaps and proceed. Do not retry failed reads
of best-effort inputs.

1. Parse `$ARGUMENTS`. Required: `--book <short-name>`. Optional:
   `--provider <name>` (default `generic`), `--length <seconds>`
   (default: `project.yaml :: teaser.length_s` if set, else `90`),
   `--force`.

2. **Refusal-on-overwrite.** If `books/{book}/teaser/teaser.json` exists
   and `--force` was not passed, stop with a message pointing the user to
   `--force` or hand-editing.

3. **Budget.** `bash`:
   `autonovel mechanical teaser-plan --length <seconds> --provider <name> --format human`
   — note the shot target and the provider's clip cap + native-audio flag
   (only emit `audio`/`dialogue` when the provider supports audio).

4. **Load the foundation for description:**
   - `shared/characters.md` — each character's **appearance**. Write ONE
     appearance string per character and reuse it **verbatim** in every
     shot (consistency; teaser-craft §6). Assign each a reference image
     path `refs/<name>.png` (the plan; generated later).
   - `shared/world.md` — settings/locations.
   - `project.yaml :: period` / `region` — wardrobe, props, era look.
   - `books/{book}/art/visual_style.json` — palette anchors (3-5),
     grade, lens look. Hold the palette identical across shots.
   - `books/{book}/voice.md` Part 4 — per-character beat density / how a
     character carries a moment.
   - `books/{book}/treatment.md` + `books/{book}/chapters/*.md` — the
     concrete image for each beat (best-effort).

5. **Externalize interiority** (teaser-craft §3). For beats drawn from
   prose, run `bash`: `autonovel mechanical show-dont-tell <chapter-file>`
   to surface interiority lines, and convert any interior state into
   **visible behaviour** in the shot's `action` (film shows; it cannot
   narrate thought). Best-effort.

6. **Author the shots.** For each beat, write 1+ shots that obey
   teaser-craft §4: one subject + one action + one camera move; present
   tense; only what's in frame; concrete cinematography vocabulary
   (teaser-craft §5); `duration_s` ≤ the provider clip cap; a content-word
   `negative_prompt` (e.g. `blurry, distorted hands, extra limbs,
   watermark, text, subtitles, flicker, morphing` — never "no …"); the
   beat's `role`; the human `beat_note`. Build the full
   `books/{book}/teaser/teaser.json` with `{title, length_s, provider,
   shots:[…]}`.

7. **Validate (hard gate).** `bash`:
   `autonovel mechanical teaser-validate books/{book}/teaser/teaser.json --provider <name>`
   If it reports problems, fix the JSON and re-run until valid.

8. **Critique (free, pre-generation — PRD §24.2).**
   a. `bash`: `autonovel mechanical teaser-critique books/{book}/teaser/teaser.json --provider <name>`
      — read the advisory flags (appearance-drift, thin-prompt,
      no-palette, no-reference, multi-action, audio-unsupported,
      missing hook/button, length-mismatch).
   b. **LLM critic pass:** for each shot, judge the prompt against
      teaser-craft §4 (legibility), the consistency rules, and whether it
      serves the beat + (for X-Prize) stakes / character / visual
      ambition. Rewrite weak prompts in the JSON. Then **re-run validate**
      (step 7) and confirm the mechanical flags you can fix are gone.

9. **Render the per-shot files.** `bash`:
   `autonovel mechanical teaser-render-prompt books/{book}/teaser/teaser.json --provider <name> --out-dir books/{book}/teaser/shots`
   — this writes `books/{book}/teaser/shots/shot_<id>.md` for every shot
   in the provider's **render dialect** (prose for veo/sora/generic/
   pollinations; terse comma-keywords for runway; concise + a Luma camera
   enum for luma) and deterministic canonical order. You don't pick the
   dialect — it follows `--provider`.

9a. **Reference-image plan (consistency anchors).** `bash`:
    `autonovel mechanical teaser-refs-plan books/{book}/teaser/teaser.json --art-references-dir shared/art_references`
    — lists the canonical reference image each recurring subject needs,
    which shots use it, and which already exist (in `books/{book}/teaser/refs/`
    or as a shared `shared/art_references/` plate). Reuse a shared plate
    when one is suggested; otherwise note the missing refs in the summary
    so the user can generate them (`/autonovel:art-curate`, or later
    `/autonovel:teaser-render`). This kills the "which refs do I still
    need?" `ls` workflow.

10. Print a one-screen summary: shot count, total seconds vs target,
    remaining advisory flags, missing reference images, estimated clip
    count incl. ~3× takes, and the next step:

    ```
    🎬 Wrote books/{book}/teaser/teaser.json + N shot files in
         books/{book}/teaser/shots/. {valid}; {k} advisory flags left.

    Next: generate the clips from these prompts in your video tool
    (free dev pass: Pollinations — see docs/teaser-craft.md / PRD §22),
    or wait for /autonovel:teaser-render (Phase 3.5).
    Re-run with --force to regenerate.
    ```
</workflow>

<acceptance>
- `books/{book}/teaser/teaser.json` exists and passes
  `autonovel mechanical teaser-validate` for the chosen provider (no shot
  exceeds the provider clip cap; every shot has a named subject, a
  verbatim appearance, and one action; negative/dialogue are separate
  fields).
- `books/{book}/teaser/shots/shot_<id>.md` exists for every shot, each
  with a `## Shot <id>`, a `**Prompt**` block in canonical order, and the
  separate negative/dialogue/reference sections.
- Each character uses ONE appearance string across all shots
  (`teaser-critique` reports no `appearance-drift`).
- The teaser has exactly one `hook` and at least one `button`, and the
  button does not reveal the resolution.
- No image/video provider is called; the command is free.
- Refusal on overwrite without `--force` is the default.
</acceptance>
