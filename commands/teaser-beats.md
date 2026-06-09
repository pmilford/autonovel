---
name: autonovel:teaser-beats
description: Select the 8-20 teaser-worthy beats (hook → escalation → title → button) from a book's story, honouring trailer craft. Writes the hand-editable beat-sheet that shot-prompts turns into shot prompts.
argument-hint: "--book <short-name> [--mode short|trailer] [--length 30|45|60|90] [--provider generic|veo|sora|runway|kling|luma|pollinations] [--force]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - books/{book}/treatment.md
  - books/{book}/teaser/brief.md
  - books/{book}/outline.md
  - books/{book}/eval_logs/*.json
  - books/{book}/chapters/*.md
  - books/{book}/teaser/beats.md
writes:
  - books/{book}/teaser/beats.md
context_mode: book
---

<purpose>
Pick the moments a teaser is built from — **and the story spine that makes
them mean something.** A teaser sells a **tone and a question**, not the
plot (see `docs/teaser-craft.md`). This command reads the story, fixes a
**spine** (the one dramatic question, the logline, the protagonist's want
vs. the opposing force, the emotional arc), then selects 8-20 **beats**
arranged on the teaser arc — **hook → escalation → title → button** — each
chosen because it *advances or complicates the dramatic question* and
*raises the stakes* over the beat before it. It writes a hand-editable
beat-sheet at `books/{book}/teaser/beats.md`. The next command,
`/autonovel:shot-prompts`, turns the spine + beats into provider-ready shot
prompts.

**Why the spine (Phase 6).** Without it, a teaser comes out as a set of
disconnected clips of the same characters standing where/when they are — it
goes nowhere and means nothing. The spine is the throughline every beat
must serve, and `teaser-critique` checks it is present and answered by the
beats. See `docs/teaser-craft.md` §0.

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
   **`--mode short|trailer`** (default `short` — Phase 13: a 45–60s, ≤12-beat
   micro-story carried by a first-person voiceover spine; `trailer` = the
   older longer montage). `--length <seconds>` (default: `project.yaml ::
   teaser.length_s` if set, else `60` for short / `90` for trailer),
   `--provider <name>` (default `generic`), `--force`. **Read `project.yaml ::
   genre` carefully** and build the beat-sheet in *that* genre's idiom
   (historical **fiction** = a character-and-stakes drama, not a documentary,
   not a generic moody montage) — genre-blind selection is a root cause of a
   flat teaser (Phase 12).

2. **Refusal-on-overwrite, then archive.** If `books/{book}/teaser/beats.md`
   already exists with author edits and `--force` was not passed, stop with:
   "books/{book}/teaser/beats.md already exists; pass `--force` to
   regenerate or hand-edit it directly". When `--force` **was** passed,
   first preserve the old script so a re-run never destroys it — `bash`:
   `autonovel mechanical teaser-archive-script books/{book}/teaser/beats.md`
   (copies it to `teaser/script-takes/beats_<UTC>.md`; no-op if absent).
   The character/location reference originals in `teaser/refs/` are **not**
   touched — re-running the whole pipeline keeps every prior script *and*
   reuses the approved portraits/plates.

3. **Get the budget.** Use the `bash` tool:
   `autonovel mechanical teaser-plan --length <seconds> --provider <name> --mode <mode> --format human`
   This prints the recommended beat count, shot count, and per-role
   timing (hook 4-6s, escalation 1.5-2.5s cuts, title ~2/3 in, button
   3-5s) plus the Phase-11 storytelling targets: **`movements`** (how many
   escalation mini-builds to group beats into) and **`dialogue_target`**
   (how many loaded lines this length should carry). Aim for the printed
   `beat_target`, `movements`, and `dialogue_target`.

4. **Read the story.** Prefer `books/{book}/teaser/brief.md` when it exists
   — it is the *distilled* through-line (the single most filmable spine, the
   3 must-have dramatic moments, the killer lines) written by
   `/autonovel:teaser-brief`, and it is the sharpest beat source. Else use
   `books/{book}/treatment.md` (already a film-shaped narrative); else read
   `books/{book}/outline.md` for the spine. Use
   `books/{book}/eval_logs/*.json` to find the load-bearing /
   highest-tension scenes (the `pacing` and `irreversible_change`
   signals) — those earn teaser beats. Skim `books/{book}/chapters/*.md`
   only for the concrete image of a chosen beat (best-effort).

5. **Fix the story spine FIRST** (Phase 6 — `docs/teaser-craft.md` §0).
   Before picking a single beat, decide the throughline from the treatment
   / outline / canon. This is what stops the teaser being a tour of scenes:
   - **Dramatic question** (bp 1): the ONE question the teaser poses and
     **never answers** ("Can a clerk outlast the bank that owns his
     country?"). Every beat must advance or complicate it; if a candidate
     beat doesn't touch the question, cut it.
   - **Logline** (bp 6): the one-sentence premise the text cards will
     carry.
   - **Want vs. opposing force** (bp 4): what the protagonist wants and the
     concrete force standing in the way. Pull both from the story; no
     conflict → no intrigue.
   - **Emotional arc** (bp 8): the tonal journey, e.g. *"quiet unease →
     mounting dread → defiant hope."* The beats should *move* along it.
   - **Score direction** (bp 8): one line on the musical spine the whole
     cut rides (a single building cue, not per-shot music).
   - **Genre/tone** (bp 9): name what *kind* of story this is (historical
     thriller, gothic romance, …) so the **hook telegraphs it in the first
     ~10 s** — the viewer should know the genre before they know the plot.
   - **Turn / reversal** (Phase 11): name the ONE midpoint reversal that
     flips the story — the moment the viewer's read of the situation turns
     over (the ally is the enemy; the rescue is a trap; the win costs
     everything). A teaser **without** a turn is a flat montage; this single
     beat is what makes it a micro-story. Pull the real reversal from the
     brief/treatment, not a generic "twist."
   - **Narrator (Phase 13 — short mode)**: name WHO speaks the first-person
     **voiceover spine** that carries the short over its disjoint shots (e.g.
     *"Jakob in old age, looking back"*). First person, one voice — this is
     the single biggest coherence device for an AI-video short. Each beat
     should imply a VO line; `shot-prompts` writes the actual lines.

6. **Select the beats** on the teaser arc so they *serve the spine*, in the
   strict **4-act order** (bp 2), applying `docs/teaser-craft.md` craft:
   - **hook** (EXACTLY one, FIRST beat): the single most arresting image or
     the dramatic question, made visible — and it must signal the **genre**
     (bp 9). Intrigue, don't explain.
   - **escalation** (most beats): a **rising stakes ladder** (bp 3) — each
     beat's cost/danger/irreversibility exceeds the one before (not a
     montage of equals); each a visible turn, not exposition. Order them so
     the stakes only rise. **Group them into the `movements` the plan prints
     (Phase 11)** — for a longer teaser (120-180 s) do NOT write 30+ equal
     micro-beats; build 3-4 *movements* that each rise to a small peak, with
     the overall stakes climbing across them, and let the key beats (hook,
     **the turn**, button) hold longer. Place the **turn** at roughly the
     midpoint — the escalation before it sets up the situation the turn
     overturns.
   - **character** (Phase 11): make sure ≥1 beat shows the protagonist's
     **want** and ≥1 shows its **cost/change** — a flicker of who they are,
     not just a recurring face. Mark these in the beat note.
   - **title** (1 beat): where the title card lands (~2/3 in, after the
     escalation, before the button).
   - **button** (1 beat, LAST): a final beat AFTER the title that deepens
     the question. **Withhold the ending** (bp 7) — for `--audience`-style
     optimism (X-Prize) you may reveal the *vision* but never the
     *resolution*.
   **Restraint** (bp 10): cut any candidate beat that is merely "the
   character standing where/when they are" — keep only beats that imply a
   larger world or turn the question. **One hero face** (bp 11): build the
   teaser around ONE protagonist's stakes; ≤3 named faces total, the rest
   silhouettes/crowd (cast discipline, teaser-craft §7.2).
   **Drama over mechanism** (Phase 12): every beat must be a **named person
   making a visible choice**, not an instrument of the plot. "Jakob decides
   to buy the next emperor" is a beat; "a wax seal is pressed," "a riderless
   horse," "a ledger entry," "seven seals on a map" are NOT — a stranger
   can't read them. If the real history is about an instrument (a ledger, a
   courier network), find the human moment that dramatizes it. Build from the
   astonishing TRUE turns (he bought an emperor; he broke his debtors; his
   almshouse still stands), each shown through a person, not narrated by an
   object.

7. **Write `books/{book}/teaser/beats.md`** in this shape (hand-editable;
   shot-prompts reads back the spine AND the beats):

   ```markdown
   # {Display Title} — Teaser beat-sheet

   *Length:* {seconds}s · *Provider target:* {provider} · *Beats:* {n}

   <!-- Edit freely: reorder, rewrite, add/cut beats. The spine below is
        load-bearing — shot-prompts copies it into teaser.json and
        teaser-critique checks the beats answer it. Then run
        /autonovel:shot-prompts --book {book}. -->

   ## Spine
   - **Dramatic question:** {the one unanswered question}
   - **Logline:** {one-sentence premise}
   - **Want:** {what the protagonist wants}
   - **Opposing force:** {what stands in the way}
   - **Turn:** {the midpoint reversal that flips the story}
   - **Narrator:** {short mode — who speaks the first-person VO spine}
   - **Emotional arc:** {start tone → … → end tone}
   - **Score direction:** {the one building musical cue}
   - **Genre:** {what kind of story — the hook must telegraph it}

   ## B01 — hook
   *Source:* {outline beat / eval peak / chapter N}
   *Advances:* {how this beat touches the dramatic question}
   {One-line beat note: the visible moment + why it hooks + the genre it signals.}

   ## B02 — escalation (movement 1)
   *Stakes:* {what's now at risk — strictly higher than B01}
   *Character:* {want | cost — if this beat shows the protagonist's want or its cost}
   ...

   ## B{m} — escalation (THE TURN, ~midpoint)
   *Reverses:* {what the viewer believed → what is now true}
   {The midpoint reversal from the spine `Turn`, made visible. Hold it. This
   is still an `escalation`-role beat — the reversal is marked here and named
   in the spine, not a new role.}

   ## B{n} — button
   {The final after-title beat. Withhold the resolution.}
   ```

8. Print a one-screen summary: the dramatic question, beat count by role,
   target length, and the next step:

   ```
   🎬 Wrote books/{book}/teaser/beats.md — {n} beats
        (hook {h} · escalation {e} · title {t} · button {b}), target {seconds}s.
        Question: "{the dramatic question}"

   Edit the beats if you like, then:
     /autonovel:shot-prompts --book {book} --provider {provider}
   ```
</workflow>

<acceptance>
- `books/{book}/teaser/beats.md` exists, opens with a
  `# ... Teaser beat-sheet` heading, carries a `## Spine` block (dramatic
  question, logline, want, opposing force, **turn**, emotional arc, score
  direction, **genre** — all non-empty), and lists beats with
  `## B<NN> — <role>` headings where role ∈ {hook, escalation, title, button}.
- The spine names a **turn** (midpoint reversal) and ≥1 escalation beat
  stages it; ≥1 beat is marked as the protagonist's **want** and ≥1 as the
  **cost/change** (Phase 11 character + reversal).
- Beat count is within the range printed by `teaser-plan` (≥6, ≤20), in
  **4-act order**: exactly one `hook` (first), ≥1 `escalation` with a
  rising stakes ladder grouped into the printed `movements`, one `title`
  (~2/3 in), one `button` (last). ≤3 named faces.
- The button beat does not reveal the story's resolution (withholding).
- Refusal on overwrite without `--force`; with `--force`, the prior
  `beats.md` is archived to `teaser/script-takes/` before regenerating.
- No image/video tool is invoked; the command is free.
</acceptance>
