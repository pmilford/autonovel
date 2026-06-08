---
name: autonovel:teaser-brief
description: Distill a sprawling treatment into a one-page TEASER brief — the single most filmable through-line, the 3 must-have dramatic moments, and the killer lines — so the beats are chosen from a sharp brief instead of the whole story. The teaser analogue of the book's brief.
argument-hint: "--book <short-name> [--length 30|60|90|120|180] [--audience xprize|general] [--force]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - books/{book}/treatment.md
  - books/{book}/brief.md
  - books/{book}/outline.md
  - books/{book}/chapters/*.md
  - books/{book}/teaser/brief.md
writes:
  - books/{book}/teaser/brief.md
context_mode: book
---

<purpose>
A treatment reveals the *whole* film; a teaser sells **one** sharp
through-line. Picking teaser beats straight from the sprawling treatment is
how a teaser ends up a flat tour of scenes (the "it's boring, nothing
happens" failure). This command is the **distillation step** (Phase 11,
mirroring the novel pipeline's `brief.md`): it reads the treatment and boils
it down to the single most filmable spine, the **3 must-have dramatic
moments**, the **killer lines**, and the **one reversal** — the raw material
`/autonovel:teaser-beats` then selects from.

It writes `books/{book}/teaser/brief.md` — short, opinionated, hand-editable.
It does NOT pick beats, author prompts, or call any image/video tool; it is
the cheap, free *focusing* step before beats.

Think of it as answering: *if you had 180 seconds and could keep only ONE
question, ONE reversal, THREE images, and a handful of lines from this whole
story — which would they be?*
</purpose>

<workflow>
**Read-failure policy.** `books/{book}/treatment.md` is the preferred
source; if it is missing, fall back to `books/{book}/brief.md` /
`books/{book}/outline.md` (stop only if none of the three exists — there is
no story to distill). Treat `chapters/*.md` as best-effort enrichment for
the concrete image / the exact killer line; note gaps and proceed.

1. Parse `$ARGUMENTS`. Required: `--book <short-name>`. Optional:
   `--length <seconds>` (default: `project.yaml :: teaser.length_s` if set,
   else `90`), `--audience <xprize|general>` (default `xprize` — shapes the
   through-line toward the competition's "future worth building" when set),
   `--force`. Confirm the book exists in `project.yaml`.

2. **Refusal-on-overwrite.** If `books/{book}/teaser/brief.md` already
   exists with author content and `--force` was not passed, stop with:
   "books/{book}/teaser/brief.md already exists; pass `--force` to
   regenerate or hand-edit it directly".

3. **Read the story.** `file_read` `books/{book}/treatment.md` (the
   film-shaped narrative, the best source); `books/{book}/brief.md` and
   `books/{book}/outline.md` for the spine; skim `books/{book}/chapters/*.md`
   only to lift the exact concrete image or the verbatim killer line
   (best-effort).

4. **Distill.** Decide, ruthlessly:
   - the **single through-line** — the one dramatic question this teaser
     poses and never answers, specific to THIS story (not "will they
     survive?");
   - the **one reversal** — the midpoint turn that flips the story (this
     becomes the spine `turn`);
   - the **3 must-have dramatic moments** — the images a viewer of this
     teaser must see (the most cinematic, highest-stakes, most legible
     turns), each one sentence, camera-visible;
   - the **killer lines** — 5-10 of the sharpest, most loaded quotes from
     the manuscript (subtext, voice, a threat/vow/cost named aloud), kept
     close to verbatim so `teaser-beats`/`shot-prompts` can place them;
   - the **want + cost** — what the protagonist wants and what pursuing it
     costs them (the character spine);
   - the **withheld ending** — name the resolution you must NOT show, so the
     button can withhold it deliberately.

5. **Write `books/{book}/teaser/brief.md`:**

   ```markdown
   # {Display Title} — Teaser brief ({length}s)

   <!-- The distilled through-line the teaser is built from. Edit freely.
        Then: /autonovel:teaser-beats --book {book}. -->

   **Through-line (dramatic question):** {the one unanswered question}

   **The reversal (turn):** {the midpoint flip}

   **Want → cost:** {what the protagonist wants} → {what it costs}

   **Genre / tone:** {what kind of story; the hook telegraphs it}

   ## Three must-have moments
   1. {camera-visible image — the hook candidate}
   2. {camera-visible image — the turn}
   3. {camera-visible image — the button candidate}

   ## Killer lines
   - "{loaded line}" — {speaker}
   - ... (5-10)

   **Withhold (do NOT show):** {the resolution the teaser must not reveal}
   ```

6. Print a one-screen summary and the next step:

   ```
   🎯 Wrote books/{book}/teaser/brief.md — through-line + turn + 3 moments
        + {k} killer lines (target {length}s).
        Question: "{the through-line}"

   Next: /autonovel:teaser-beats --book {book} --length {length}
         (selects the beats from this brief), then /autonovel:shot-prompts.
   Or run /autonovel:teaser --book {book} to do the whole pipeline.
   ```
</workflow>

<acceptance>
- `books/{book}/teaser/brief.md` exists, opens with a `# ... Teaser brief`
  heading, and contains a through-line (dramatic question), a named reversal
  (turn), a want→cost line, a `## Three must-have moments` list, and a
  `## Killer lines` list (≥3 lines).
- It is a *distillation* — materially shorter and sharper than
  `treatment.md`, not a copy.
- Refusal on overwrite without `--force`.
- No image/video tool is invoked; the command is free.
</acceptance>
