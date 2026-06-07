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

  - **`books/{book}/teaser/teaser.json`** — the machine-readable teaser:
    the **`spine`** (dramatic question, logline, want, opposing force,
    emotional arc, score direction — copied from `beats.md` so it flows to
    render + critique), then the ordered list of shots in the structured
    schema (PRD §8): framing, subject + verbatim appearance, one action,
    setting, lighting, palette, camera move, lens, style, mood, separate
    negative prompt, separate **dialogue** (loaded lines mined from the
    manuscript), **text cards** (carrying the premise), consistency anchors.
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

2. **Refusal-on-overwrite, then archive.** If
   `books/{book}/teaser/teaser.json` exists and `--force` was not passed,
   stop with a message pointing the user to `--force` or hand-editing. When
   `--force` **was** passed, preserve the prior script first — `bash`:
   `autonovel mechanical teaser-archive-script books/{book}/teaser/teaser.json`
   (copies it to `teaser/script-takes/teaser_<UTC>.json`; no-op if absent).
   Reference originals in `teaser/refs/` are untouched, so a full re-run
   keeps every prior script and reuses the approved portraits/plates.

3. **Budget.** `bash`:
   `autonovel mechanical teaser-plan --length <seconds> --provider <name> --format human`
   — note the shot target and the provider's clip cap + native-audio flag
   (only emit `audio`/`dialogue` when the provider supports audio).

4. **Load the spine + foundation for description:**
   - `books/{book}/teaser/beats.md` `## Spine` block — the dramatic
     question, logline, want, opposing force, emotional arc, score
     direction, **genre**. Copy all of it verbatim into the teaser's
     `spine` object (below). It is load-bearing: render + critique read it,
     and the **narrative gate** in `teaser-render` refuses a real render
     when the spine/payload is thin (bp 12).
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

5b. **Mine the dialogue + write the text cards** (Phase 6 — the fix for
   "not enough dialogue to know anything"). A teaser must let the viewer
   *hear* the story and read its premise:
   - **Dialogue (bp 5).** Read `books/{book}/treatment.md` +
     `books/{book}/chapters/*.md` and pull **3-6 of the highest-voltage
     lines** — the ones that reveal a stake, a relationship, or the genre
     in one breath (a threat, a vow, a cost named aloud). Adapt each to a
     short trailer line and assign it to the shot it belongs to as
     `audio.dialogue: [{speaker, line}]`. These are *loaded* lines, not
     ambient chatter; spread them across the arc (one near the hook, the
     sharpest just before the title/button). **Provider gate:** only emit
     spoken `dialogue` when the provider has native audio (check
     `teaser-plan`); if it does not, carry those lines as **text cards**
     instead (below) so the meaning still lands.
   - **Text cards (bp 6).** Author **2-4 short `text_card`s** that carry
     the premise/logline cheaply (they dodge AI lipsync): typically a
     premise card near the open, an escalation stinger, and the
     logline/title beat (`role: title`) card. Keep them short and
     declarative — they do the narrative work the images can't.

6. **Author the shots.** Build the full `books/{book}/teaser/teaser.json`
   as `{title, length_s, provider, spine:{dramatic_question, logline,
   want, opposing_force, emotional_arc, score_direction, genre},
   shots:[…]}` — the `spine` copied from `beats.md` (step 4). For each
   beat, write 1+ shots that obey teaser-craft §4: one subject + one
   action + one camera move; present tense; only what's in frame; concrete
   cinematography vocabulary (teaser-craft §5); `duration_s` ≤ the provider
   clip cap; a content-word `negative_prompt` (e.g. `blurry, distorted
   hands, extra limbs, watermark, text, subtitles, flicker, morphing` —
   never "no …"); the beat's `role`; the human `beat_note`; and the mined
   `audio.dialogue` / `text_card` from step 5b. Enforce the craft gates:
   - **4-act order (bp 2):** exactly one `role: hook` as the first shot
     (and it signals the **genre**, bp 9), one `role: title` ~2/3 in, one
     `role: button` as the last shot, escalation shots between.
   - **Stakes ladder (bp 3):** give every `role: escalation` shot a
     `stakes_level` integer that **strictly rises** in shot order (1, 2,
     3, …) — the cut must escalate, not idle.
   - **Restraint (bp 10):** do NOT emit a shot that is merely "the
     character standing where/when they are" — every shot turns the
     question or implies a larger world. Cut filler.
   - **One hero face (bp 11):** ≤3 distinct `subject.name`s; the rest are
     silhouettes/crowd (no name, no consistency lock).
   Pace the cut to the **emotional arc** — the hook holds, escalation cuts
   tighten, the button breathes.

7. **Validate (hard gate).** `bash`:
   `autonovel mechanical teaser-validate books/{book}/teaser/teaser.json --provider <name>`
   If it reports problems, fix the JSON and re-run until valid.

8. **Critique (free, pre-generation — PRD §24.2).**
   a. `bash`: `autonovel mechanical teaser-critique books/{book}/teaser/teaser.json --provider <name>`
      — read the advisory flags. **Story-spine flags are must-fix**
      (`no-dramatic-question`, `no-logline`, `no-stakes`,
      `no-emotional-arc`, `thin-dialogue`, `thin-text-cards`): clear them
      by filling the spine / mining more lines / adding cards, not by
      ignoring them. Plus the prompt flags (appearance-drift, thin-prompt,
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
- `teaser.json` carries a `spine` object with a non-empty dramatic
  question, logline, want, opposing force, and emotional arc (copied from
  `beats.md`) — `teaser-critique` reports no `no-dramatic-question` /
  `no-logline` / `no-stakes` / `no-emotional-arc`.
- The teaser carries **≥2 spoken dialogue lines** (audio providers) or the
  equivalent as text cards, and **2-4 text cards** carrying the premise —
  no `thin-dialogue` / `thin-text-cards` flag remains for the provider.
- The teaser has exactly one `hook` and at least one `button`, and the
  button does not reveal the resolution.
- No image/video provider is called; the command is free.
- Refusal on overwrite without `--force`; with `--force`, the prior
  `teaser.json` is archived to `teaser/script-takes/` before regenerating.
</acceptance>
