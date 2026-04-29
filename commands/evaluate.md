---
name: autonovel:evaluate
description: Score the foundation, a chapter, the whole book, or a head-to-head chapter pair.
argument-hint: "--phase foundation --book <name> | --chapter <N> --book <name> | --full --book <name> | --compare <N>,<M> --book <name>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - shared/world.md
  - shared/characters.md
  - shared/canon.md
  - shared/events.md
  - shared/period_bans.txt
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/*.md
writes:
  - books/{book}/eval_logs/*.json
context_mode: book
---

<purpose>
Judge model scores, subtracts a deterministic AI-slop penalty, and writes
an eval log the rest of the pipeline consumes. This command is the
successor to the old `evaluate.py` — the mechanical half lives in
`src/autonovel/mechanical/` and is invoked via `bash`; the LLM-judgement
half is this command's body. Four modes:

  --phase foundation   score the planning layer for one book
  --chapter <N>        score a single chapter
  --full               score the whole book holistically
  --compare <N>,<M>    pick a winner between two chapters (successor to
                       the deleted `compare_chapters.py`)

Eval logs are JSON and land under `books/{book}/eval_logs/<timestamp>_<mode>.json`.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Exactly one of `--phase`, `--chapter`, `--full`, or
   `--compare` must be present; `--book <short-name>` is required in every
   mode. Anything else is a usage error — print a one-line reminder and
   stop.

2. Use `file_read` on `project.yaml` to resolve the book entry, its `pov`,
   and `defaults.chapter_target_words` / `defaults.chapter_threshold`. The
   defaults drive two calibration rules that follow.

3. Load the shared layer with `file_read`: `shared/world.md`,
   `shared/characters.md`, `shared/canon.md`, `shared/events.md`. Load
   `shared/period_bans.txt` if it exists; treat missing as empty.

4. Load the per-book layer with `file_read`: `books/{book}/voice.md`
   (Parts 1, 2, AND 3) and `books/{book}/outline.md`.

4a. **Parse Part 3 (Custom rubric) from voice.md.** Look for a
    heading exactly matching `## Part 3 — Custom rubric` (em-dash)
    or `## Custom rubric`. Treat each top-level bullet under that
    heading as one rubric criterion. Strip the HTML comment
    placeholder (the `<!-- … -->` block from the template) — only
    real bullets count. Empty or comment-only sections mean "no
    custom rubric for this book"; proceed normally without flagging
    a missing surface (this is the expected state for many books).

4b. **Parse Part 4 (Per-character voice fingerprints) from
    voice.md.** Look for `## Part 4 — Per-character voice
    fingerprints`. Treat every `### Name (...)` block under that
    heading as one character fingerprint. Strip the HTML comment
    placeholder; only real `###` blocks count. Empty or comment-
    only Part 4 means "use Part 2 alone for character_voice
    scoring"; proceed normally. When Part 4 has fingerprints, the
    `character_voice` dimension scored in step 6 changes from
    "do characters sound distinct?" (Part 2 only) to "does each
    character honour their Part 4 block?" — verify per-line that
    Tommaso's dialogue obeys Tommaso's Speech / Verbal tics /
    Refuses, etc. Quote the strongest violation in
    `weakest_moment` for the dimension.

5. Mode `--phase foundation`: evaluate the planning layer only. Use a
   literary-critic system prompt calibrated to the SCORING CALIBRATION
   block below. Score the dimensions: `magic_system` (or
   `world_rule_consistency` for non-fantasy genres — use whichever the
   `project.yaml :: genre` dictates), `world_history`,
   `geography_and_culture`, `lore_interconnection`, `iceberg_depth`,
   `character_depth`, `character_distinctiveness`, `character_secrets`,
   `outline_completeness`, `foreshadowing_balance`,
   `internal_consistency`, `voice_clarity`, `canon_coverage`,
   `canon_outline_consistency`. For each dimension emit `{score,
   gap, fix, note}`. Weighting: lore 40%, character 30%, structure
   20%, craft 10%. Include `overall_score`, `lore_score`,
   `weakest_dimension`, `top_3_improvements`.

   **`canon_outline_consistency` — cross-check canon.md against
   outline.md.** Read both files. Find every fact that appears in
   BOTH (a date, a character name, a location, an event). When
   the canon and outline disagree on the value (e.g. canon says
   `[Anselmo arrived] 1473` but outline ch 4 says "Anselmo
   arrives in 1471"), score this dimension low and emit a
   `canon_outline_conflicts` array with one entry per conflict:
   `{fact, canon_value, outline_value, recommendation}`. The
   recommendation says which side is authoritative for this
   project — usually canon (since `/autonovel:promote-canon` is
   the process by which facts harden), so the outline is the
   side that should change. When canon and outline agree on
   every fact mentioned in both, score the dimension 9-10 and
   emit `canon_outline_conflicts: []`. This catches the bug
   class where an outline plant in chapter 4 contradicts a
   canon entry that hardened from a different chapter's
   research, leaving downstream chapters drafted against a
   silently-wrong date or name.

6. Mode `--chapter <N>`: use `file_read` on
   `books/{book}/chapters/ch_{chapter}.md`. If the file is missing or
   empty, emit `{"error": "...", "overall_score": 0.0}` and stop. Also
   load the outline entry for this chapter and the last ~1500 words of
   `books/{book}/chapters/ch_{prev}.md` (where `{prev}` = chapter - 1,
   zero-padded). Score the dimensions: `voice_adherence`, `beat_coverage`,
   `character_voice`, `plants_seeded`, `prose_quality`, `continuity`,
   `canon_compliance`, `lore_integration`, `engagement`,
   `irreversible_change`. Each emits `{score, weakest_moment, fix,
   note}`. Include `three_weakest_sentences`,
   `three_strongest_sentences`, `ai_patterns_detected`,
   `overall_score`, `weakest_dimension`, `top_3_revisions`,
   `new_canon_entries`.

   **`irreversible_change` (Stability Trap antidote).** This is
   the named ceiling failure from the Bells production: AI
   defaults to safe, round-edged chapter endings — the board
   resets between chapters, tension can't compound, the book
   plateaus around pacing 7. The score classifies the chapter's
   ending and trajectory:

     9-10: At least one specific, named, irreversible change
           (death, public revelation, broken oath, signed
           contract, opened door that can't be closed). The
           character or world cannot return to the chapter's
           opening state.
     7-8:  Irreversible change happened, but it's softened
           (deferred consequence, off-page, not the chapter's
           main beat). Still moves the story forward.
     5-6:  Reversible change: something happened that *could*
           be undone, walked back, or revealed as misunderstanding
           in a later chapter. The chapter "advances" but commits
           to nothing.
     3-4:  Status-quo restored: the board ends the chapter where
           it started. The events of the chapter could be cut
           without affecting later chapters.
     1-2:  Pure setup or pure stasis: nothing of consequence
           happened. The chapter exists to fill space.

   Required: `weakest_moment` quotes the chapter's final scene
   when the score is below 7, naming what reverted; `fix`
   prescribes ONE specific irreversible commitment the rewrite
   should make (a line, a death, a refusal, a destroyed object —
   not vague "raise stakes"). Below 6 is added to
   `top_3_revisions` automatically.

   For chapter 1 specifically, additionally check whether the
   ending makes the protagonist incapable of refusing the call
   to action — chapter 1 endings that leave the door open for the
   protagonist to walk away score capped at 7.

7. Mode `--full`: glob `books/{book}/chapters/*.md` in order. Build a
   compact chapter-by-chapter summary (opening 500 chars, closing 500
   chars, word count, any outline beats marked rendered) and score novel
   dimensions: `arc_completion`, `pacing_curve`, `theme_coherence`,
   `foreshadowing_resolution`, `world_consistency`, `voice_consistency`,
   `overall_engagement`, `irreversible_change_arc`. Include
   `novel_score`, `weakest_dimension`, `weakest_chapter`, `top_suggestion`.

   **`irreversible_change_arc` (whole-book Stability Trap check).**
   Walk every chapter pair (N → N+1) and ask: "Could chapter N+1
   have started from chapter N's *opening* state instead of its
   *closing* state?" Every "yes" is a chapter that didn't change
   the world. Score the book on the ratio:

     9-10: Every chapter's closing state is load-bearing for the
           next chapter (or the climax). No chapter could be cut
           without breaking later chapters' premises.
     7-8:  ≤2 chapters could be cut without breaking later
           chapters; book commits to its consequences.
     5-6:  3-5 chapters are essentially reversible / cuttable; the
           middle sags because the board keeps resetting.
     3-4:  Half the book leaves the world unchanged; suspect a
           series of "filler" chapters in the middle act.
     1-2:  Only the climax commits to anything; the rest is stalling.

   Required when the score is below 8: a `cuttable_chapters` list
   naming each chapter that fails the "could chapter N+1 have
   started from N's opening state?" test, with one line of
   evidence per chapter. This is the load-bearing surface for
   the user's revision plan.

8. Mode `--compare <N>,<M>`: use `file_read` on
   `books/{book}/chapters/ch_{chapter}.md` for each of N and M (truncate
   to ~3000 words each if longer). Pick the better one — no ties
   allowed. Emit `{winner, winner_chapter, margin, decisive_moment,
   winner_strength, loser_weakness, best_sentence_a, best_sentence_b}`.

9. Mechanical slop penalty. For `--chapter` and `--full`, before writing
   the log, use `bash` to run
   `autonovel mechanical slop <chapter-path>` for each chapter
   under evaluation and parse its JSON. Record the per-chapter
   `slop_penalty` under `result["slop"]` (for single-chapter) or
   `result["slop_per_chapter"][N]` (for full). Subtract `slop_penalty`
   from the judge's score to produce `overall_score` (or `novel_score`),
   keeping the unadjusted value as `raw_judge_score` /
   `raw_novel_score`. Do NOT run the slop scanner for `--phase` or
   `--compare`.

10. Period bans. If `shared/period_bans.txt` exists and is non-empty,
    also run `bash: autonovel mechanical period-bans
    <chapter-path> shared/period_bans.txt` for each chapter under
    evaluation. Record the `hits` list under `result["period_ban_hits"]`.
    A single period-ban violation caps `canon_compliance` at 6; three or
    more caps it at 4.

10a. Bigram cliché scan. For `--chapter` and `--full`, run
    `bash: autonovel mechanical cliches <chapter-path>` for each
    chapter and parse its JSON. Record under
    `result["cliches"]` (for single-chapter) or
    `result["cliches_per_chapter"][N]` (for full). The scanner's
    `density_per_1000_words` field adds to the slop penalty:
    every full unit of density above 2.0 subtracts 0.1 from
    `overall_score`, capped at 0.5 total. (Empirically, well-edited
    prose runs <2 cliché-bigram hits per 1000 words; >5 reads
    AI-tinged.)

10b. Sensory-channel balance. For `--chapter` and `--full`, run
    `bash: autonovel mechanical sensory <chapter-path>` for each
    chapter and parse its JSON. Record under
    `result["sensory"]` / `result["sensory_per_chapter"][N]`. If a
    chapter has a `dominant_channel` (one channel >70% of all
    sensory hits), call it out in the `weakest_moment` field for
    that chapter — visual dominance is the most common AI tell;
    it reads as a film-script camera move rather than a scene with
    a body in it. Do not subtract from the score automatically; the
    judge weighs it as one signal among many.

10e. **Per-scene beat coverage.** For `--chapter` and `--full`,
    run `bash: autonovel mechanical scenes <chapter-path>` for each
    chapter and parse its JSON. The output gives a stable per-scene
    index (`scene_count`, then a `scenes` list with `index`,
    `word_count`, `opening_line`, `closing_line` for each).

    For each scene in each chapter, score the **four story beats**
    on a 0/1 binary (present / absent):

      - **goal** — does someone in the scene want something
        specific (not just emotional valence)?
      - **conflict** — is there resistance to that want (another
        character, the world, the POV's own contradiction)?
      - **disaster_or_decision** — does the scene turn (the want
        is denied / a bad result, OR the POV makes a choice they
        can't unmake)?
      - **consequence** — does the scene's end change something
        going forward (knowledge, relationship, position, stakes)?

    Aggregate per chapter into `beat_coverage` block:

    ```json
    "beat_coverage": {
      "score": 7.5,
      "scenes": [
        {"index": 1, "beats_hit": ["goal", "conflict", "consequence"],
         "beats_missed": ["disaster_or_decision"]},
        {"index": 2, "beats_hit": ["goal", "conflict",
         "disaster_or_decision", "consequence"], "beats_missed": []}
      ],
      "weakest_scenes": [
        {"index": 1, "missed_count": 1,
         "fix": "scene 1 ends without anyone changing — give Tommaso a "
                "decision he can't take back before the break"}
      ]
    }
    ```

    Scoring: every beat is worth 2.5 points; per-chapter score is
    the average across scenes. **A scene missing 2 or more beats
    goes into `weakest_scenes`** with a one-sentence prescription
    naming the missing beat and what to add. brief.md walks
    `weakest_scenes` and names them by index — that's the load-
    bearing surface that turns "tighten chapter 8" into "scene 8.2
    needs a decision before the break". Single-scene chapters
    (no `***` breaks) are scored as one scene; the prescription
    might be "split into two scenes around the midpoint
    decision".

    For `--full` mode, record `beat_coverage_per_chapter[N]` and
    surface a top-line `book_beat_coverage_score` averaging the
    per-chapter scores. Chapters whose score is below 6 go into
    a `weak_beat_coverage_chapters` list at the top level —
    these are the chapters whose middles drift, which is the
    "drifting middle" Bells failure mode.

10d. **Custom-rubric scoring.** When step 4a parsed at least one
    bullet criterion, score each one in addition to the standard
    rubric. For each criterion:
      - Apply the rule to the chapter (or, in `--full` mode, to
        every chapter and aggregate).
      - Score 0–10 (10 = chapter fully respects the rule; 0 = the
        rule is grossly violated). Use the same calibration as the
        standard rubric.
      - Surface a one-sentence finding: what the chapter did vs.
        what the rule asked for. Quote a passage when violated.
    Record under `result["custom_rubric"]` as a list of
    `{criterion, score, finding}` objects (single-chapter mode) or
    `result["custom_rubric_per_chapter"][N]` (full mode). Any
    criterion with a score below 6 is also added to the
    `top_3_revisions` list so brief picks it up. Do NOT subtract
    from `overall_score` automatically — the judge weighs custom
    rubric findings as one signal among many; the visible flag in
    the eval log + the brief is the load-bearing surface.

10c. First-page hook (for `--chapter 1` only). Read the first
    250 words of the chapter and score them on a separate
    `hook_strength` dimension (0–10) covering: specific image in
    line 1, stakes implied by line 3, voice signature visible
    early, no info-dump preamble. Record the score under
    `result["hook_strength"]` alongside the regular dimensions.
    Don't subtract from the overall score; it surfaces as its own
    line in the summary table so the user can see whether chapter
    1 is doing the work it needs to.

11. Use `file_write` to save the eval log to
    `books/{book}/eval_logs/<timestamp>_<mode>.json` where `<timestamp>`
    is `YYYYMMDD_HHMMSS` and `<mode>` is one of `foundation`,
    `ch{chapter:02d}`, `full`, `compare_{N}_vs_{M}`.

12. Print a one-screen summary to stdout. **Render the per-dimension
    scores as a real markdown table** so the user gets a visually
    aligned grid, not a wall of `dimension: 6.5` text. The exact
    shape varies by mode but the table format is mandatory:

    For `--chapter` mode:

    ```markdown
    | Dimension | Score | Weakest moment / Note |
    |---|---|---|
    | voice_adherence | 7.2 | "She felt the chill" — telling not showing |
    | beat_coverage | 6.5 | midpoint reversal landed flat |
    | character_voice | 7.8 | — |
    | prose_quality | 6.9 | three "she did not" patterns in 2400w |
    | engagement | 7.0 | — |
    | internal_consistency | 8.0 | — |

    **Overall:** 7.1 (raw 7.4 − slop 0.3)
    **Weakest:** beat_coverage (6.5)
    **Top fixes:** … (one bullet each)
    ```

    For `--phase foundation` and `--full` use the same table shape
    with the dimensions appropriate to the mode (lore /
    character / structure / craft for foundation;
    arc_completion / pacing_curve / etc. for full).

    Render every dimension on its own row. Missing values get an
    em-dash, never a blank cell. Do not skip the table because the
    text list "felt enough"; per author testing 2026-04-25 the
    table is what makes the score block scannable.

    **For `--full` mode, also emit a pacing-curve table** showing
    the shape of the book chapter-by-chapter. This is the
    reader-interest signal — flat curves bore, curves with a
    consistent rise into the climax engage. The shape:

    ```markdown
    | Ch | Words | Score | Tension | Dialogue % | Scenes | Beats hit |
    |---|---|---|---|---|---|---|
    |  1 | 3100  | 7.4 | 6.5 | 22% | 2 | 4/4 |
    |  2 | 2950  | 6.8 | 7.0 | 35% | 3 | 3/4 |
    |  3 | 3200  | 7.1 | 7.5 | 18% | 2 | 4/4 |
    | …  | …     | …   | …   | …   | … | …   |
    ```

    Pull `Words` from each chapter's frontmatter or recompute,
    `Score` from the latest eval log, `Tension` from the per-chapter
    judge pass (1-10 scale; how taut the chapter feels), `Dialogue %`
    by counting lines between paragraph breaks that begin with `"`,
    `Scenes` by `***` or scene-break markers, `Beats hit` against
    the outline entry's beats list.

    **Tension-drop alarm for `--full`.** After the table, scan the
    Tension column for any window of three or more consecutive
    chapters where each chapter's tension is lower than the
    previous one's. Surface each such window:

    ```
    ⚠️  Tension drop detected: chapters 7→8→9 trend down (7.5 → 6.8 → 6.0).
        Recommend /autonovel:revision-pass --chapters 7-9 with
        focus on stakes-escalation.
    ```

    These warnings are reader-interest signals — a 3-chapter
    decline is the kind of mid-book sag readers DNF on. Even when
    individual chapter scores are above threshold, the *trend*
    matters.

    **First-page hook line for `--chapter 1` mode.** When the
    invoked chapter is chapter 1, also surface the
    `hook_strength` score from step 10c on its own line under
    the dimension table:

    ```
    **First-page hook (first 250 words):** 7.0
    ```

    Below 6.0 is a real concern — chapter 1's opening is what
    decides whether a reader continues. Suggest
    `/autonovel:revise 1 --from auto` and call out the hook
    weakness in the brief.

    **Custom-rubric findings table** (when step 10d ran with at
    least one criterion). Render under the dimension table as its
    own block:

    ```markdown
    **Custom rubric (book-specific):**

    | Criterion (first 60 chars) | Score | Finding |
    |---|---|---|
    | At most 2 financial transactions per chapter | 5.0 | 4 ledger entries on p.3; arithmetic crowds out scene |
    | Ending must commit to one irreversible thing | 7.0 | — |
    ```

    Use the criterion's leading text (truncated to 60 chars +
    ellipsis) as the row label. Render `—` when there's no finding
    to report. This is the load-bearing surface for per-book
    rules; do not collapse it into a single line.
</workflow>

<scoring-calibration>
  9-10: Could not improve with a month of editorial work. Name a specific
        published work it competes with, or do not give 9+.
  7-8:  Strong. Skilled author could draft from this with minimal invention.
  5-6:  Functional but thin. Writer would have to invent on the fly.
  3-4:  Sketchy. More questions than answers.
  1-2:  Placeholder.
  0:    Empty or missing.

  Median chapter score is 6. An 8 is exceptional. A 9 is rare. A 10 does
  not exist for a first draft. Err toward lower scores. For EVERY
  dimension, identify the biggest gap and a concrete improvement.
</scoring-calibration>

<acceptance>
- A JSON eval log is written under `books/{book}/eval_logs/`.
- The log contains a numeric top-line score
  (`overall_score` / `novel_score` / `winner`).
- For chapter and full modes the log contains a `slop` block with
  numeric `slop_penalty`, and `overall_score` equals
  `raw_judge_score - slop_penalty` rounded to 2dp.
- For compare mode the log contains a non-null `winner_chapter` equal
  to one of the two compared chapter numbers.
</acceptance>
