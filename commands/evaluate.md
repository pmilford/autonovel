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
   (both parts) and `books/{book}/outline.md`.

5. Mode `--phase foundation`: evaluate the planning layer only. Use a
   literary-critic system prompt calibrated to the SCORING CALIBRATION
   block below. Score the dimensions: `magic_system` (or
   `world_rule_consistency` for non-fantasy genres — use whichever the
   `project.yaml :: genre` dictates), `world_history`,
   `geography_and_culture`, `lore_interconnection`, `iceberg_depth`,
   `character_depth`, `character_distinctiveness`, `character_secrets`,
   `outline_completeness`, `foreshadowing_balance`,
   `internal_consistency`, `voice_clarity`, `canon_coverage`. For each
   dimension emit `{score, gap, fix, note}`. Weighting: lore 40%,
   character 30%, structure 20%, craft 10%. Include `overall_score`,
   `lore_score`, `weakest_dimension`, `top_3_improvements`.

6. Mode `--chapter <N>`: use `file_read` on
   `books/{book}/chapters/ch_{chapter}.md`. If the file is missing or
   empty, emit `{"error": "...", "overall_score": 0.0}` and stop. Also
   load the outline entry for this chapter and the last ~1500 words of
   `books/{book}/chapters/ch_{prev}.md` (where `{prev}` = chapter - 1,
   zero-padded). Score the dimensions: `voice_adherence`, `beat_coverage`,
   `character_voice`, `plants_seeded`, `prose_quality`, `continuity`,
   `canon_compliance`, `lore_integration`, `engagement`. Each emits
   `{score, weakest_moment, fix, note}`. Include
   `three_weakest_sentences`, `three_strongest_sentences`,
   `ai_patterns_detected`, `overall_score`, `weakest_dimension`,
   `top_3_revisions`, `new_canon_entries`.

7. Mode `--full`: glob `books/{book}/chapters/*.md` in order. Build a
   compact chapter-by-chapter summary (opening 500 chars, closing 500
   chars, word count, any outline beats marked rendered) and score novel
   dimensions: `arc_completion`, `pacing_curve`, `theme_coherence`,
   `foreshadowing_resolution`, `world_consistency`, `voice_consistency`,
   `overall_engagement`. Include `novel_score`, `weakest_dimension`,
   `weakest_chapter`, `top_suggestion`.

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

11. Use `file_write` to save the eval log to
    `books/{book}/eval_logs/<timestamp>_<mode>.json` where `<timestamp>`
    is `YYYYMMDD_HHMMSS` and `<mode>` is one of `foundation`,
    `ch{chapter:02d}`, `full`, `compare_{N}_vs_{M}`.

12. Print a one-screen summary to stdout: the headline score, the
    weakest dimension, and top suggestions.
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
