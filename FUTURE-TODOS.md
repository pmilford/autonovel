# Future todos

Items that are out of PR-9 scope but worth recording so a future
session can pick them up. Companion to `ROADMAP.md` (PR sequence),
`STATE.md` (decisions log), and `docs/lessons-from-author-testing.md`
(narrative explanation of *why* certain defensive shapes exist).

The list is rough on purpose — each entry is a one-line reminder, not
a spec. Promote to `ROADMAP.md` (or a fresh PR plan) when one is ready
to start.

## Near-term — pull into the next PR

- ~~**Edit-and-revise mode for an externally-written manuscript —
  Phase 1 (import + mode flip).**~~ **Shipped 2026-04-28.** New
  `autonovel import-book <name> --from <path>` CLI subcommand and
  `/autonovel:import-book` slash-command. Splits a directory of
  `*.md` files (one chapter per file) OR a single combined
  manuscript (split on `^# `, fallback `^## `, fallback whole
  file) — `--split-on '<regex>'` overrides with a custom pattern.
  Strips pre-existing YAML frontmatter from each section, writes
  autonovel-shape `ch_NN.md` with `status: imported` and
  `imported_from: <source>` for audit, and flips
  `project.yaml :: books[].mode` to `edit-imported`. New
  `BookEntry.mode` field (default `draft`, omitted from YAML to
  keep existing files clean). `commands/draft.md` step 1a refuses
  to overwrite an edit-imported book without `--force`. New
  helper at `src/autonovel/import_book.py`. 26 Tier-1 tests
  covering directory + single-file splits, frontmatter stripping,
  custom regex split, fallback titles, writer skip-existing,
  dry-run, append-after-existing chapter numbering, BookEntry
  YAML round-trip, CLI happy path / dry-run / unknown-book. Tier
  1+2: 974 → 1005. Phase 2 (reverse-engineered foundation) is
  still queued: see follow-up entry below.

- ~~**Edit-and-revise mode — Phase 2 (foundation reverse-engineering).**~~
  **Shipped 2026-04-29 PM** as commit `a636c70` (mechanical v1).
  `autonovel import-book ... --reverse-engineer` extracts
  candidate character names from imported prose (capitalised
  single-word tokens above a frequency threshold; structural-
  English reject list of ~70 sentence-starters / month / weekday
  / honorific tokens) and writes a stub `shared/characters.md`
  when missing OR appends a "Candidate cast (auto-detected)"
  block when present (idempotent — re-runs detect the sentinel
  heading). Numbered next-steps printed: voice-discovery,
  summarize-chapter, gen-outline, evaluate. New helper
  `src/autonovel/import_foundation.py`. 14 new Tier-1 tests.
  Tier 1+2: 1193 → 1207. Doc sync: commands/import-book.md,
  docs/commands.md, series-template CLAUDE.md.
  Open follow-ups (deliberately deferred per
  feedback_avoid_brittle_python.md): voice.md Part 2 derivation
  from prose register (mechanical heuristics drift; voice-discovery
  is the right LLM-side tool), outline.md derivation from
  per-chapter summaries (needs LLM via summarize-chapter first).
  Original entry follows for context:

- **Edit-and-revise mode — Phase 2 (foundation reverse-engineering).** The
  pipeline today assumes autonovel drafted the book itself. New use
  case 2026-04-28: a user has a finished or partial manuscript
  (their own, an estate's, a public-domain text they're modernising)
  and wants to use the eval / revise / panel / review / typeset
  surfaces against it without re-drafting from scratch. Two
  sub-modes that share most of the import pipeline:

  1. **Book-only**: user drops a directory of chapter files (any
     of `.md`, `.txt`, `.docx` via pandoc, `.epub` via pandoc, a
     single combined manuscript, or a folder of one-file-per-
     chapter). The new `/autonovel:import --book <name> --from
     <path>` command:
      - splits the manuscript into chapters (heading detection,
        scene-break detection, or explicit `--split-on <regex>`),
      - writes `books/<name>/chapters/ch_NN.md` with autonovel-
        shape YAML frontmatter (chapter number + word count,
        `pov`/`status`/`story_time` left as `inferred` placeholders
        for the user to fill or for a follow-up
        `/autonovel:summarize-chapter` LLM pass to backfill),
      - reverse-engineers a stub foundation by sampling prose
        across chapters: a draft `voice.md` (Part 1 generic, Part
        2 derived from prose register), a stub `characters.md`
        with every named entity that appears more than N times,
        a stub `outline.md` listing chapter beats inferred from
        the chapter-summary helper running across the imported
        prose. None of these are authoritative — they exist so
        evaluate / revise have something to read against.

  2. **Book + foundation**: user supplies the manuscript AND a
     seed/voice/world/canon (e.g. they wrote the book against an
     existing series' conventions). Same import command with
     `--keep-foundation` skips the reverse-engineering and trusts
     the user's existing `shared/*` and `books/<name>/voice.md`.

  Cross-cutting:
  - `project.yaml :: books[].mode = edit-imported` so downstream
    commands know not to draft new chapters (forbid
    `/autonovel:draft N` in this mode by default; allow with
    `--force` for the case where the user wants to add a new
    chapter to an existing book).
  - The summary backfill step needs to be cheap; a sweep wrapper
    `/autonovel:summarize-chapter --all --book <name>` already
    exists or is one CLI flag away.
  - Tier-1 tests for the splitter (markdown headings, scene
    breaks, explicit `--split-on`), frontmatter-stub generation,
    and reverse-engineered foundation shape.
  - docs/operating-guide.md gets a §2g "Editing an externally-
    written book" walkthrough.

  Cost: ~6-10 hr (one new command, one helper file, frontmatter
  stub generator, reverse-engineering heuristics, Tier-1 tests,
  walkthrough). Opens up a meaningful adjacent use case without
  changing the rest of the pipeline.

- ~~**`/autonovel:next` — brief-newer-than-chapter signal + full
  audit of situational gaps.**~~ **Shipped 2026-04-29 PM** as
  commit `b7abadd`. Brief→revise HIGH situational signal in
  `housekeeping/next_actions.py::_brief_newer_than_chapter_actions`;
  past-end-of-book guard in `canonical_pipeline_action` that
  demotes draft commands targeting chapter N where N >
  existing_chapters + 1 to a "book appears complete" INFO
  pointing at evaluate --full / typeset. 7 new Tier-1 tests
  (single + multiple briefs, conversation.md non-trigger,
  past-end and next-sequential cases). Tier 1+2: 1123 → 1130.
  Doc sync: commands/next.md, docs/operating-guide.md, series-
  template CLAUDE.md.
  Original entry follows for context:

- **`/autonovel:next` — brief-newer-than-chapter signal + full
  audit of situational gaps.** Surfaced 2026-04-29 by author
  testing: ran `/autonovel:brief` for chapters 1, 2, 3, 5, 10 of
  an active book; `/autonovel:next` then said "draft chapter 25"
  (past end of book) instead of "revise chapters with fresh
  briefs." The canonical-pipeline default ("draft the next
  chapter") wins because no situational signal fires for the
  brief→revise pair. Concrete gaps:
   1. **brief newer than chapter → revise.** When
      `books/<book>/briefs/ch{NN}_brief.md` mtime > the
      corresponding `chapters/ch_{NN}.md` mtime, surface a HIGH
      situational action recommending `/autonovel:revise
      --chapter {NN}` (or `revision-pass --chapters {range}` for
      contiguous runs). Same shape as the existing regression /
      pending-canon checks in
      `housekeeping/next_actions.py::enumerate_actions`.
   2. **Audit every other situational case.** Walk each branch
      in `enumerate_actions` and confirm: (a) the trigger fires
      reliably on the realistic fixtures, (b) the recommended
      command's `argument-hint` matches what the action prints,
      (c) the priority is right (HIGH for data integrity,
      MEDIUM for staleness, LOW for polish). Property-based
      tests (`test_property_based.py`) verify shape but not
      semantic correctness of every branch.
   3. **Past-end-of-book guard on the canonical next step.**
      When the canonical pipeline says `draft <N>` and `N >
      planned_chapter_count + 1` (or > a configured ceiling),
      demote the line to INFO and surface a "book appears
      complete — try `/autonovel:evaluate --full` or
      `/autonovel:typeset`" suggestion instead.
  Add Tier-1 tests under
  `tests/deterministic/test_next_actions_situational.py`. Cost:
  ~3-4 hr (signal + audit + guard + tests).

- ~~**Situational-aware help hints in command output.**~~
  **Shipped 2026-04-29 PM** as commit `f1d12d7`. Every
  successful postamble now ends with a one-line `💡 Maybe try:`
  hint pulled from `next_actions.top_hint(series, just_ran=...)`
  — picks the highest-priority situational action with a runnable
  command that doesn't point back at the just-ran command, falls
  back to a 6-entry rotating "Did you know?" pool indexed by
  hash(just_ran) for deterministic-yet-varied general hints.
  Wrapped in try/except so a hint-path crash never fails the
  command. Suppressed on status=error. 6 new Tier-1 tests. Tier
  1+2: 1130 → 1136. Doc sync: docs/operating-guide.md.
  Original entry follows for context:

- **Situational-aware help hints in command output.** Surfaced
  2026-04-29 by author testing: "I'm generally lost on next
  steps, especially when the software is giving incorrect
  guidance." Today the postamble's `next_standard_step` is the
  only hint, and `/autonovel:next` is a separate call.
  Proposal: every command postamble appends a "💡 Maybe try:"
  line inferred from the same `next_actions` enumerator that
  powers `/autonovel:next`, with a max of 1-2 suggestions
  ranked by priority. Examples:
   - After `brief` → "💡 Maybe try: `/autonovel:revise
     --chapter <N>` (brief is fresher than the chapter)."
   - After `evaluate --chapter N` with score < threshold →
     "💡 Maybe try: `/autonovel:brief --chapter N` then
     `/autonovel:revise --chapter N`."
   - After `promote-canon` if conflicts remain → "💡 Maybe try:
     resolve `## Conflict` blocks in
     `shared/canon.md`, then re-run `/autonovel:promote-canon`."
  Prefer situational; fall back to a small randomised pool of
  general "did you know" hints (e.g. "💡 Did you know? `/autonovel:
  summaries --where 'score < 7'` filters chapters") only when
  no situational hint applies. Implementation: extend
  `next_actions.enumerate_actions` to expose a `top_hint(state,
  just_ran=<command>)` API; postamble in `_end` calls it and
  prints the line. Suppress when `--quiet` or when the command
  itself errored. Cost: ~3 hr (API + postamble wiring + Tier-1
  tests + the small general-hints pool).

- ~~**`/autonovel:impact-of <command>` — answer "what should I
  revise now?" without ls/grep.**~~ **Shipped 2026-04-29 PM** in
  two commits. Mechanical first pass (`347ed61`):
  `src/autonovel/mechanical/impact.py` parses `## Superseded`
  blocks in `shared/canon.md`, computes tokens unique to each
  prior_value, greps every chapter (frontmatter-stripped) for
  them, emits a per-chapter checklist of `/autonovel:revise
  --chapter N` calls with line-snippet evidence. CLI subcommand
  `autonovel mechanical impact-of` and slash-command
  `/autonovel:impact-of`. 21 new Tier-1 tests + 5 contract
  pickups. Tier 1+2: 1136 → 1162.
  LLM follow-up (`54ac17c`): slash-command extended with
  `--with-llm` (Haiku-tier classifier labels each match
  HIGH/MEDIUM/LOW/FALSE_POSITIVE so the action checklist only
  includes HIGH+MEDIUM) and `--source research` mode (LLM by
  default; reads notes newer than the last canon timestamp,
  scans each chapter against the notes' Candidate Canon
  Entries). 4 new Tier-1 regression locks. Tier 1+2: 1223 →
  1227.
  Open follow-up: extending `--source` to `voice-discovery`,
  `gen-canon`, `add-character`, `rename-character`,
  `merge-chapters`, `reorder`, `remove-chapter`, `add-source`
  remains future work; today only `promote-canon` and `research`
  are supported.
  Original entry follows for context:

- **`/autonovel:impact-of <command>` — answer "what should I
  revise now?" without ls/grep.** Surfaced 2026-04-29: after
  `/autonovel:promote-canon` the author asked "what's the next
  step?" and the only correct answer required (a) reading
  `## Superseded` blocks in `shared/canon.md`, (b) `grep -ril`
  for each flipped fact across `books/<book>/chapters/`, (c)
  cross-referencing the chapter list, (d) running
  `/autonovel:evaluate --full`, and (e) building a targeted
  revise list. That is exactly the workflow autonovel exists to
  collapse — the user said "I should never have to use ls or
  grep." Same shape recurs after `research`, `add-source`,
  `voice-discovery`, `gen-canon`, `add-character`,
  `rename-character`, `merge-chapters`, `reorder`,
  `remove-chapter`. Each of those mutates a foundation file
  and downstream chapters may need to be revised; today the
  user has to do the impact analysis by hand.
  Proposed command: `/autonovel:impact-of <command>
  [--book <name>] [--since <git-ref>]` — a light-tier
  command that:
   1. Reads what changed (Superseded blocks for promote-canon;
      `git diff <ref>..HEAD shared/` for the others; new
      `shared/research/notes/<slug>.md` files for research).
   2. Walks `books/<book>/chapters/` and finds chapters that
      reference the changed surfaces — by literal grep for
      flipped names/dates and by per-chapter LLM scan for
      semantic dependencies (the cheap `chapter-summary` index
      already names cast + locations + facts).
   3. Emits a targeted action plan: a markdown checklist of
      `/autonovel:revise --chapter N (because <fact>
      changed)`, ranked by impact (number of references,
      severity of contradiction).
   4. Exposes the same plan via `autonovel _impact-of` for
      `/autonovel:next` to consume — so after `promote-canon`,
      `next` can lead with the targeted revise list instead of
      the canonical "draft chapter N+1" line.
  Generalises the brief→revise signal entry above. The
  situational-hints entry adds *one-line nudges*; this entry
  adds *the actionable list with rationale* the user actually
  needs. Cost: ~5-7 hr (analyzer per command type + LLM per-
  chapter scan + Tier-1 tests + slash-command + `_impact-of`
  CLI).
  Bigger principle: any time the help-flow forces the user
  into shell commands (`ls`, `grep`, `cat`) to figure out
  which of N chapters to act on, that's a missing autonovel
  surface — file an issue.

- ~~**Query/grep helper for `shared/research/notes/`.**~~
  **Shipped 2026-04-29 PM** as commit `54a0bd2`. Two
  complementary surfaces: `autonovel mechanical research-index
  <series>` emits a per-note metadata table (slug / title /
  updated / words / sources / body citations / candidate canon
  entries / uncertainties), with `--grep <pattern>` (full-body)
  and `--cites <URL-or-DOI>` (Sources block only) filters; and
  `/autonovel:research --query "<question>"` reads every note
  and answers with inline `[shortname]` citations — no web
  search, pure synthesis. 13 new Tier-1 tests. Tier 1+2: 1162 →
  1175. Doc sync: docs/commands.md research row, series-template
  CLAUDE.md.
  Original entry follows for context:

- **Query/grep helper for `shared/research/notes/`.** Surfaced
  2026-04-29: author has research notes for Jakob Fugger,
  Maximilian I, Charles V and wants a structured way to
  recall what's there + ask follow-up cross-character questions
  ("how did Fugger and Maximilian's relationship evolve?")
  without reading every file. Today the only paths are
  `Read shared/research/notes/<slug>.md` (one at a time) or
  `grep -r '<term>'`. Two complementary surfaces:
   1. **`autonovel mechanical research-index <series_root>`**
      (free, mechanical) — emits a markdown table: slug,
      title, source count, citation count, word count,
      last-updated. Optional `--grep '<pattern>'` filters by
      keyword across notes. Optional `--cites '<URL-or-DOI>'`
      shows which notes cite a given source.
   2. **`/autonovel:research --query "<question>"`** (LLM,
      cheap) — reads every file under `shared/research/notes/`,
      answers the question with inline citations to the source
      slugs, and writes nothing (read-only Q+A). Distinct from
      `/autonovel:talk` by querying *research* rather than
      *prose*. Distinct from `/autonovel:research "<topic>"`
      by NOT firing live web search — pure synthesis over
      what's already in `notes/`.
  The mechanical surface is the cheap "what's even in there"
  view; the LLM surface answers cross-character questions
  that need synthesis. Cost: ~4-5 hr for both.
  Open question: does adding new notes from a `--query`
  follow-up belong here too, or stay in
  `/autonovel:research "<topic>"` as today?



- ~~**PDF page-header still leaks chapter prose (regression of the
  2026-04-25 fix).**~~ **Shipped 2026-04-28.** Two distinct bugs,
  both fixed:
   1. `mechanical/latex.py::build_chapters_tex` was reading
      `lines[0]` of the post-frontmatter body as the chapter title.
      Real chapter files (per `commands/draft.md`) are YAML
      frontmatter + prose only — no `# Title` heading after the
      frontmatter. So `lines[0]` = first sentence of prose, which
      became `\chapter{<sentence>}` and rendered as a large italic
      block at every chapter title page. Fixed: new
      `_extract_chapter_title()` honours an optional
      `title:` frontmatter field, falls back to a real `# Heading`
      if present, otherwise emits empty `\chapter{}` so
      `\titleformat{\chapter}` prints `chapter <Roman>` alone.
      The empty-title case is the production shape and is now
      Tier-1 locked.
   2. Even with the new `mechanical/latex.py`, users with
      in-flight series carry a stale `<series-root>/typeset/novel.tex`
      from before the 2026-04-25 fix (`autonovel install` doesn't
      refresh typeset templates). New housekeeping subcommand
      `autonovel refresh-templates [--only typeset] [--dry-run]`
      re-copies package-shipped templates over the live series,
      preserves local-only files (custom macros etc.), and reports
      which files were updated vs unchanged vs preserved as
      local-only. Default is `typeset/` only — minimal blast
      radius. Operating-guide §3b includes the new section
      "Typeset templates need a separate refresh".
  Tier 1+2: 774 → 785.

- ~~**Talk-with-the-book mode.**~~ **Shipped 2026-04-28.** New
  heavy-tier command `/autonovel:talk --book <name>
  "<question-or-suggestion>" [--target <chapter>]`. Three modes
  it classifies from the prompt:
   - **Q+A** — *"explain why Jakob opened the book of accounts"*
     → answers with chapter+line citations.
   - **Suggest-and-stage** — *"add some details about the book of
     accounts being out of alignment"* → writes a structured
     turn to `books/{book}/briefs/conversation.md` with `Status:
     queued`.
   - **Mechanical+suggest** — *"how many cipher-diary entries
     are referred to later? Cut the orphans"* → first calls
     `autonovel mechanical entity-track`, surfaces the per-
     chapter table, performs the semantic added-vs-referred
     pairing, queues a structured cut-list.
  `commands/revise.md` reads `briefs/conversation.md`, folds
  every queued turn with `Target: chapter <N>` into the brief,
  flips them to `Status: applied` after the rewrite. The same
  conversation-fold contract is exposed in
  `commands/revision-pass.md` so sweeps pick up queued turns
  for every chapter in range automatically. New mechanical
  helper `src/autonovel/mechanical/entity_track.py` is the
  reusable named-entity tracker the Mechanical+suggest mode
  drives; it's a generalisation of `motifs.py` that resolves
  entities from `books/<book>/entities.md` first, falls back
  to `[shortname]` heads in `shared/canon.md`. Tier 1+2:
  785 → 803 (13 entity-track tests + 5 contract auto-pickups
  for `/autonovel:talk`).

- ~~**Per-book tension/pacing visualisation — beyond the existing
  `--full` table.**~~ **Shipped 2026-04-28.** New light-tier
  command `/autonovel:dashboard [--book <name>] [--threshold
  <float>] [--format markdown|json]` re-renders the latest
  `<ts>_full.json` eval log without firing another LLM evaluate.
  Augments with mechanical dimensions (cast size from summary,
  scene count from `***`/`---` markers, dialogue density from
  paragraph-opening `"`, motif density from `motifs.md` when
  present), ASCII sparklines (▁ to █) for the score and tension
  series, per-book aggregates (mean / median / range / stdev,
  longest sub-threshold streak), and the tension-drop alarm
  (≥3 consecutive declines) re-run from the existing data.
  Output ends with a `_sources_` provenance footer naming where
  each column came from. New helper
  `src/autonovel/mechanical/dashboard.py` + CLI subcommand
  `autonovel mechanical dashboard <book_root>`. 32 Tier-1 tests
  + 4 contract auto-pickups for the new command. Tier 1+2:
  803 → 840.

- ~~**Easy way to interact and query the chapter summaries.**~~
  **Shipped 2026-04-28.** New light-tier command
  `/autonovel:summaries [--book <name>] [--where '<expr>']
  [--format markdown|json]` filters the structured chapter-
  summary index via a small DSL. Supports comparison operators
  (`==`, `!=`, `<`, `<=`, `>`, `>=`) on `pov`, `score`,
  `story_time`, `word_count`, `cast`, `plot`, `location`,
  `chapter`, `status`, plus `<field> contains <literal>`,
  `<field> in <num>..<num>`, and `and` / `or` / `not` /
  parenthesisation. Numeric on numeric fields; lexicographic on
  the rest (works for ISO dates). New helper
  `src/autonovel/mechanical/summary_query.py` with a hand-
  written tokeniser + recursive-descent parser (deliberately
  not `eval()` — safer and more user-friendly errors). CLI
  subcommand `autonovel mechanical summary-query <book_root>`.
  Distinct from `/autonovel:talk` (LLM-mediated Q+A) by being
  free, scriptable, and stable — no LLM drift. 32 Tier-1 tests
  + 5 contract pickups. Tier 1+2: 840 → 877.



- ~~**`autonovel _promote-canon` Python helper for safe in-sweep
  canon promotion.**~~ **Shipped 2026-04-26.** Hidden CLI
  subcommand `autonovel _promote-canon --book <name>
  [--no-lock] [--dry-run] [--format json|human]` ships at
  `src/autonovel/promote_canon.py`. Engine implements the full
  pipeline: parse pending entries (handles bullet shape,
  `[shortname]` citations, `[research:slug]` tags, `(from ...)`
  provenance, skips `no new facts` and HTML-comment instruction
  blocks, dedupes within file); classify Duplicate (case-
  insensitive substring with 60% length floor) / Contradiction
  (year-mismatch with shared-token threshold 2; negation-flip
  with threshold 3 — conservative, won't drop facts on a
  heuristic) / Survivor; research-tagged entries beat
  contradictions and emit `## Superseded` blocks with citation;
  conflict-block format matches `commands/promote-canon.md`
  step 8 verbatim (mandatory HTML instruction block at top,
  `## Conflict N` numbered blocks naming the contradicting
  file path). The lock-collision bug class is structurally
  impossible: sub-agents invoke `autonovel _promote-canon
  --no-lock` via the `Bash` tool — no slash-command, no preamble,
  no lock check. `commands/promote-canon.md` body, `revision-pass.md`
  step 3f, and `draft-pass.md` step 5 all wired to call the
  helper as the single source of truth. 22 Tier-1 tests cover
  parsing, classification, supersedure, conflict-block format,
  mutual exclusion (file with conflicts never also has `no new
  facts`), dry-run, lock refusal without `--no-lock`, and CLI
  round-trips in human + json formats.

- ~~**Make `/autonovel:next` dynamic instead of static.**~~
  **Shipped 2026-04-28.** New helper module
  `src/autonovel/housekeeping/next_actions.py` enumerates
  filesystem state directly (no last-action.json replay) and
  returns a prioritised list of `NextAction` records: HIGH for
  data-integrity (pending-canon conflict blocks, chapter
  regressions ≥0.3 below prior best), MEDIUM for review
  staleness (reader-panel / Opus review reports older than any
  chapter file) and git backup (no repo / no remote /
  uncommitted / unpushed), LOW for polish (stale typeset PDF,
  missing book title or author, missing preface / introduction
  once ≥3 chapters drafted). Hidden subcommand `autonovel
  _next-actions [--book <name>] [--format human|json]` invokes
  the enumerator. The frozen `next_standard_step` from
  last-action.json is still surfaced — but as the lowest-
  priority "canonical pipeline next step" line at the bottom,
  so situational state always wins. `commands/next.md`
  rewritten to call the helper via the `bash` tool and print
  its output verbatim. 27 Tier-1 tests cover each per-book
  check, the three git-backup states, the canonical-action
  lookup with book filtering, the human render's priority
  grouping, and CLI round-trips in human + json. Stopgap
  postamble multi-line `next_standard_step` values from the
  sweep commands are still useful (they produce the canonical-
  pipeline line) but no longer the only source of truth.



- ~~**Per-chapter art prompts as first-class artifacts.**~~
  **Shipped 2026-04-28.** New light-tier command
  `/autonovel:art-prompts --book <name> [--chapters <range>]
  [--surface ornament|plate|scene-break] [--style lineart|full|
  symbolic] [--force]` reads outline + per-chapter summary +
  `art/visual_style.json` + `shared/world.md`, picks one
  symbolic motif per chapter via a light-tier model call, and
  writes a markdown prompt file at
  `books/{book}/art/prompts/ch{NN:02d}_{surface}.md` — six
  sections (Motif, Rationale, Prompt, Universal constraints,
  Style, Source inputs). `--force` required to overwrite an
  existing prompt file. No image provider is called.
  `commands/art-ornaments-all.md` updated to read the prompt
  file's `## Prompt` body verbatim when present, falling back to
  inline derivation otherwise. The prompt files are the right
  hand-edit target before generation, the right input for a
  non-default generator (Midjourney, ComfyUI, a commissioned
  artist), and richer than the first 400 words of prose because
  outline + summary name the chapter's turning point.

- ~~**Per-book rubric extensions via `voice.md`.**~~ **Shipped
  2026-04-25.** voice.md template now includes a `## Part 3 —
  Custom rubric` section. evaluate.md (step 4a + 10d), reader-panel
  (step 2 + 5), brief (step 5 — `## Custom-rubric findings`
  section), draft (step 6) and revise (step 5) all read it. eval
  logs gain `custom_rubric` / `custom_rubric_per_chapter` arrays;
  panel logs gain a `custom_rubric` block keyed per reader. Brief
  is required to surface flagged criteria so revise propagates
  fixes. voice-discovery preserves Part 3 verbatim. Carry-over: a
  rubric-snippet library at `src/autonovel/templates/rubrics/`
  (so common patterns like "financial discipline" or "stability-
  trap antidote" are paste-in templates) is still open as a
  follow-up.

- ~~**Long-sweep context exhaustion in draft-pass / revision-pass.**~~
  **Partly fixed 2026-04-25 evening.** draft-pass and revision-pass
  per-chapter sequences now run inside `task` subagents — each
  chapter's full workflow lives in a fresh subagent conversation
  and only a one-line summary returns to the parent. The parent's
  context grows by one short string per chapter instead of one
  full chapter's prose + tool output. Sweeps that previously
  stalled around chapter 8-10 should now run end-to-end.
  Still open: a sweep checkpoint file
  (`.autonovel/sweep-progress.json`) that `/autonovel:resume`
  reads to offer "continue from chapter N" recovery, so the user
  doesn't have to figure out `--chapters <remaining>` after an
  interruption.


- **Test-coverage gaps surfaced 2026-04-25.** The session's bug
  pattern revealed three structural test gaps that let
  late-stage / multi-stage / install-time bugs slip past Tier 1+2:

  1. ~~**Realistic late-stage fixtures.**~~ **Shipped 2026-04-28.**
     Two new conftest fixtures join `late_stage_book`:
     `mid_revision_book` (8 chapters, all evaluated, ch02+ch03
     below threshold with briefs written, panel report deliberately
     stale) and `review_phase_book` (10 chapters, all above
     threshold, panel + Opus review newer than every chapter — the
     shape right before typeset). New test file
     `tests/deterministic/test_state_machine_realistic.py`
     parametrises across all three fixtures and asserts shape
     invariants (chapter count, phase rolls forward, no foundation
     regression, situational action coverage). The realistic-fixture
     pass surfaced and fixed a real bug in
     `lifecycle._last_eval_score`: its glob `ch{NN}*.json` matched
     only the plain `chNN_eval.json` shape, missing the timestamped
     `<ts>_chNN.json` form `evaluate.md` writes — so after running
     `/autonovel:evaluate --chapter N` the next-step inference saw
     no score and looped recommending evaluate again. Helper now
     delegates to `mechanical.chapter_summary._index_latest_per_chapter_eval`
     which already handles all three naming conventions.
     Tier 1+2: 723 → 740.

  2. ~~**Multi-stage integration tests** (deterministic, no LLM).~~
     **Shipped 2026-04-28.** New file
     `tests/deterministic/test_integration_pipeline.py` walks the
     real seams: foundation chain (world → characters → voice →
     canon → outline → drafting); first-draft → evaluate → advance
     vs revise (with the timestamped eval shape that #5.1 fixed);
     low-score → revise → re-eval → advance; pending-canon gate
     (draft → pending entry appears → next-step says
     promote-canon → run real `promote_canon.promote` →
     pending file rewritten → gate releases → advance);
     situational `next_actions` shifts as state evolves; canonical
     pipeline action surfaced at the bottom; eval-score indexer
     resolves all three production naming conventions. 7 new
     Tier-1 tests; Tier 1+2: 740 → 747.

  3. ~~**pipx-isolated install test (Tier-3).**~~
     **Shipped 2026-04-28.** New file
     `tests/smoke/test_pipx_install.py` builds a wheel via
     `pipx install <repo>` against an isolated `PIPX_HOME` /
     `PIPX_BIN_DIR` (so the install never touches the user's real
     pipx state). Falls back to `python -m pipx` when `pipx` isn't
     on `$PATH`, skips cleanly when neither works. Then exercises
     the CLI surfaces that have historically broken under wheel
     packaging: `autonovel --help`, `_next-actions --help`,
     `mechanical slop --help`, `_promote-canon --help`, and an
     end-to-end `new-series` + `doctor` round-trip — the last is
     the strongest check for `templates/` packaging since
     `new-series` writes from `src/autonovel/templates/` and a
     missing force-include in pyproject would fail there. Marked
     `smoke + pipx_install` so it can be excluded independently
     (`-m "smoke and not pipx_install"`). Runs in ~6s on the
     dev box.

- **Bells Tier-4 fixture populate.** Still parked since PR 4. The
  harness is built; the chapters from `autonovel/bells` branch
  need copying in. Once populated, this is the canonical
  full-pipeline regression — gates LLM-prompt drift across an
  entire 19-chapter manuscript. Today's work would have benefited:
  a regression run on Bells chapters with summaries + evals + briefs
  would have caught at least the chapter-count and next-step bugs
  before they shipped.

- ~~**Property-based tests for invariants.**~~
  **Shipped 2026-04-28.** New file
  `tests/deterministic/test_property_based.py` uses
  `hypothesis` (added under `[test]` extras) to generate random
  book layouts (chapter count 0-12, random POV, status, prose,
  scores, summary/eval-log/motif/entity/pending-canon presence)
  and assert invariants:

  - `iter_chapter_files` count equals the chapter-count exactly
    (catches the `.summary.md` glob regression).
  - `_infer_phase` returns a known phase name for every layout.
  - `lifecycle._next_step_for` always returns a non-empty
    command + rationale, namespace `/autonovel:` or `autonovel`,
    no unsubstituted `{...}` placeholders.
  - `enumerate_actions` priorities are in {HIGH, MEDIUM, LOW,
    INFO} with non-empty title + rationale.
  - `summarize_chapters` row-count matches chapter file count.
  - `build_dashboard`, `build_entity_report`, `build_motif_report`
    do not crash on arbitrary layouts.
  - `next_step.next_step()` decision table returns valid
    command + rationale for every legal `PipelineState`.

  10 properties × 25 examples each = ~250 random layouts per
  CI run. Tier 1+2: 897 → 907.

- ~~**Read-only TUI for series state — terminal only, NOT a web
  server.**~~ **Shipped 2026-04-29 PM** as commit `597d308`. New
  CLI subcommand `autonovel tui [--book <name>]` launches a
  textual-based read-only browser with seven tabs: Help (live —
  for each suggested next command, shows rationale + reads/
  writes from frontmatter), Chapters (DataTable + side detail
  + score sparkline), Research (notes list + preview), Foundation
  (status of each shared/ + per-book file), Front matter
  (title/author/preface/introduction), Reviews (reader-panel +
  Opus review presence + mtimes), Commands (last 15 + situational
  next-actions + canonical step). Header bar: series name · book
  selector · lock state · sweep progress live · cost today +
  total. Polls FS every 5 s; press `r` to refresh; `b` to switch
  books; `0-6` to jump to tabs; `q` to quit. Read-only by
  contract — never acquires the lock; safe to run alongside an
  active sweep. New optional extra `[tui]` (`textual>=0.70`); the
  CLI prints a clear pip / pipx install hint when textual isn't
  importable. New helper `src/autonovel/tui.py`. 16 new Tier-1
  tests covering sparkline edge cases, slash-command extraction,
  command-index cache, state-load shape on minimal + late-stage
  fixtures, graceful CLI degradation. Tier 1+2: 1227 → 1243. Doc
  sync: docs/operating-guide.md, README.md, docs/commands.md
  (new CLI subcommands section).
  Original entry follows for context:

- **Read-only TUI for series state — terminal only, NOT a web
  server.** Author noted 2026-04-25 that NousResearch's earlier
  autonovel had a richer read-only console showing file artifacts
  and live progress; the rewrite ships only `autonovel status`
  (one-shot CLI), `autonovel statusline` (Claude Code status bar),
  `.autonovel/command-log.jsonl` (append-only JSON log), and
  `/autonovel:dashboard` (markdown table — shipped 2026-04-28).

  The next step is a long-running terminal UI via `textual` or
  `urwid` that streams the lock state, last-action, recent
  command-log entries, per-book phase + chapter scores, and the
  `pending_canon.md` queue.

  **Constraint clarified 2026-04-28: must be terminal-native
  (TUI), not a web server.** Author runs autonovel on
  WSL / Linux on Chromebook, where a localhost web server is
  awkward (no direct browser access from the WSL filesystem
  context; the user has to do port-forwarding gymnastics that
  defeat the "trivial to start" goal). Same constraint applies
  to `/autonovel:dashboard`'s output today — markdown table in
  the runtime's chat is the right surface, NOT a generated HTML
  file the user is supposed to open. Future enhancements to the
  dashboard (sparklines per dimension, expandable rows, filter
  controls) should keep the same shape: print to stdout, render
  in the terminal, no browser dependency.

  Roughly 1–2 days for a textual TUI. Hold for now — current
  tools cover the same data and the dashboard fills the
  highest-value visualisation gap. Pick this up when CLI
  output becomes the bottleneck.


- **Research-from-seed auto-merges into canon (no manual editing).**
  ~~Open~~ **Fixed 2026-04-25.** `/autonovel:research --from-seed`
  now appends every research-derived candidate to the active book's
  `pending_canon.md` with a `[research:<slug>]` tag.
  `/autonovel:promote-canon` honours that tag: research-tagged
  entries win contradictions against the prior canon, and the
  supersedure is recorded in a `## Superseded <UTC-date>` block in
  `shared/canon.md` with the citation. Net effect: a user runs
  research-from-seed, then promote-canon, and `shared/canon.md`
  reflects cited primary-source facts without hand edits — date
  corrections like "Fugger arrived 1478 not 1473" propagate
  automatically and visibly.


- ~~**Drafter must degrade gracefully when reading prior chapter
  files.**~~ **Shipped 2026-04-28.** Each drafter command body
  (`commands/draft.md`, `commands/revise.md`,
  `commands/draft-pass.md`, `commands/revision-pass.md`) gains an
  explicit **Read-failure policy** preamble at the top of its
  `<workflow>`: do NOT retry on `file_read` errors for non-load-
  bearing inputs (prior summaries, eval logs, prior-chapter
  quotes); note the gap and proceed. The single hard-stop is the
  chapter file at `revise` step 6 — that's the load-bearing input
  we're rewriting. Catches the 2026-04-25 retry-loop bug class
  that stalled long sweeps around chapter 8-10 when a single
  summary file was missing or had a different shape than expected.

  context fails.** ~~Open~~ **Fixed 2026-04-25.** `commands/draft.md`
  step 7 and `commands/revise.md` step 6 now mark the prior-chapter
  read as best-effort with explicit "do not retry on failure"
  wording, and call out per-chapter summaries (step 8) as the
  load-bearing continuity surface. Author can no longer stall on
  Read retries when ch_{prev} hits a Claude-Code-internal hiccup.
  Carry-over: a *time-based* watchdog on `_begin` (live PID + lock
  older than N minutes → mark abandoned) is still open as a more
  general defence — the no-retry wording fixes this specific case
  but not the broader "LLM is wedged but PID is alive" failure.

- **Cross-provider `/autonovel:compare-models`.** V1 (shipped
  2026-04-25) is single-provider — it compares two Claude models
  within the active runtime. The natural extension is Opus vs GPT
  vs Gemini head-to-head, since model providers ship updates every
  few months and the user shouldn't have to migrate to evaluate.
  Implementation hint: add a `--runtimes claude,codex,gemini`
  argument; the parent runtime spawns a draft per (runtime, model)
  pair via the adapter layer (likely a new `autonovel _spawn-draft`
  CLI subcommand that knows how to invoke each runtime's headless
  mode and copy the result back into `eval_logs/`). The judge stays
  on whichever runtime the parent is in. ~3-5 hours of work.

- ~~**Research belongs at the front of the foundation, not as a
  manual step.**~~ **Shipped 2026-04-28.** All three sub-items
  are now live:
    1. `/autonovel:research --from-seed` mode (shipped earlier)
       reads `seed.txt` + `project.yaml :: period` and writes
       sourced notes per topic.
    2. `_foundation_gap` recommends `/autonovel:research
       --from-seed` before gen-world when
       `project.yaml :: period.start` is set and
       `shared/research/notes/` is empty (lifecycle.py lines
       ~504-514). Three Tier-1 tests around the gap behaviour.
    3. **(2026-04-28)** `commands/gen-world.md` step 3a and
       `commands/gen-canon.md` step 2a now read every populated
       `shared/research/notes/*.md` as primary source of truth,
       cite slug provenance in the world bible's Sources
       section, surface a one-line nudge when a period project
       has no research notes, and (gen-canon) preserve the
       `[research:<slug>]` tag through to canon bullets so
       promote-canon's tagged-survives-untagged conflict
       resolution stays correct. 7 new Tier-1 regression locks
       in `tests/deterministic/test_research_at_front.py`. Tier
       1+2: 1049 → 1056.

## From live author testing (post-PR-9)

These surfaced during a real first-run on a Chromebook + WSL on Claude
Max $200/month. Full narrative + rationale in
`docs/lessons-from-author-testing.md`.

- ~~**Per-command `model:` override on `[1m]` session models —
  recovery path.**~~ **Shipped 2026-04-28.** New CLI flag
  `autonovel install --no-model-pin` re-renders every command
  file with the `model:` frontmatter field omitted, so the
  runtime's session model wins on every invocation. Recovery
  path for users on a `[1m]` session model whose per-command pin
  silently downshifts them to the non-`[1m]` variant. Adapter
  signature gains `pin_model: bool = True` parameter; installer
  inspects the adapter signature and only forwards the flag to
  adapters that accept it (so Codex/Gemini stay no-op until they
  opt in). Doc sync in docs/troubleshooting.md "My session
  model is `[1m]`" section. The longer-term fix
  (`project.yaml :: llm.honor_session_model` to make pinning
  per-project opt-out) is still tracked but not blocking now
  that the recovery flag exists.

- **Per-command `model:` override — per-project opt-out.** The
  `--no-model-pin` install flag (shipped 2026-04-28 above) is the
  recovery path; the long-term fix is per-project opt-out via
  `project.yaml :: llm.honor_session_model = true` so users can
  pick the policy per-series rather than at install time. Lower
  priority now that the recovery path exists.
- ~~**Postamble compliance watchdog.**~~ **Shipped 2026-04-28.**
  `lock.acquire_with_takeover` gains an `expire_after_seconds`
  parameter (default 30 min via `DEFAULT_LOCK_EXPIRE_SECONDS`).
  Any lock older than the threshold is silently taken over at
  the next `_begin`, with the abandoned LockInfo surfaced via
  the existing `BeginResult.abandoned_lock` channel so the
  postamble can warn the user. Independent of PID liveness —
  catches the same-Claude-Code-session case where the LLM
  skipped `_end`. Lock age comes from the `started_at` ISO
  timestamp in the lock JSON, with mtime fallback when that
  field is corrupted. Pass `expire_after_seconds=None` or `0`
  to disable for callers that explicitly want the
  pre-2026-04-28 PID-only semantics. New `is_expired(lock_path,
  max_age_seconds)` predicate. 7 new Tier-1 tests including
  end-to-end through `lifecycle.begin`. Tier 1+2: 877 → 884.
- ~~**Verify `writes:` files were actually modified.**~~
  **Shipped 2026-04-28.** New
  `checkpoints.verify_writes(cp, series_root, claimed)` returns a
  `WriteVerificationReport` with one item per claim and statuses
  `created` / `modified` / `deleted` / `unchanged` / `missing` /
  `outside-checkpoint`. `lifecycle.end` invokes it after release,
  surfaces `unchanged` and `missing` as warnings in the
  postamble footer (`⚠️ verify-writes:`) and records a one-line
  summary on the command-log entry's `note` field for audit
  trail. Catches the bug class where the LLM passes `--wrote
  <path>` without invoking Write/Edit. Paths still containing
  `{book}` placeholders or paths outside the checkpoint are
  classified `outside-checkpoint` (informational, not warnings).
  Doc sync in docs/troubleshooting.md. 13 new Tier-1 tests
  covering each status path + lifecycle integration. Tier 1+2:
  884 → 897.
- ~~**Canon-vs-outline cross-consistency in `/autonovel:evaluate`.**~~
  **Shipped 2026-04-28.** `commands/evaluate.md` `--phase
  foundation` mode gains a new `canon_outline_consistency`
  dimension. The judge reads both `shared/canon.md` and
  `books/<book>/outline.md`, finds every fact mentioned in
  BOTH, and emits a `canon_outline_conflicts` array with one
  entry per disagreement (canon says ch4 is in 1473, outline
  ch4 says 1471 → flagged). Recommendation defaults to "canon
  wins; revise the outline" since `/autonovel:promote-canon`
  is the process by which facts harden. Catches the bug class
  where outline plants contradict canon entries that hardened
  from a different chapter's research, leaving downstream
  chapters drafted against silently-wrong dates or names.

- **Canon-vs-outline cross-consistency — Python-side helper.** Today
  When canon says X arrived in 1473 and the outline says 1471, the
  user shouldn't have to spot the contradiction manually. evaluate
  --phase foundation could date-compare references.
- **`autonovel install --dry-run`** so users can preview what would
  be written into `~/.claude/commands/` before mutating it.
- ~~**`autonovel _begin` should echo a "running from `<dir>`" banner.**~~
  **Shipped 2026-04-28.** `_cmd_begin` prints a one-line
  banner `_begin: running from series root \`<name>\`` (or
  `... (cwd: <relative-path>)` when the user launched the
  runtime from below the series root). Catches the
  wrong-cwd-launch failure mode before the command silently
  misroutes paths. Two new Tier-1 tests cover the at-root and
  below-root cases. Tier 1+2: 907 → 912.


## Output writing quality

These are things that would lift the prose ceiling beyond what the
current pipeline reliably produces (Bells topped out at pacing ≈ 7,
prose ≈ 8 / 10, with investigation-heavy plots).

- ~~**Per-character voice fingerprints.**~~ **Shipped 2026-04-25.**
  voice.md template now includes a `## Part 4 — Per-character voice
  fingerprints` section. voice-discovery (step 6a) auto-drafts it
  when shared/characters.md has ≥3 named principals — one ~5-bullet
  block per character (Speech / Verbal tics / Refuses / Body during
  dialogue / Interiority [POV only]); cap 6 characters. Step 7b
  preserves hand-edited Part 4 verbatim across re-runs (`--force`
  overrides). draft.md (step 6) and revise.md (step 5) both apply
  Part 4 at every dialogue line + every interiority sentence.
  evaluate.md (step 4b) shifts the `character_voice` dimension from
  "do characters sound distinct?" to "does each character honour
  their Part 4 block?" when Part 4 is populated, with the strongest
  violation quoted in `weakest_moment`. Solo-cast / single-speaker
  books fall back to Part 2 cleanly (the threshold rule skips Part
  4 generation; the placeholder comment stays).
- ~~**Dialogue mechanics linter.**~~ **Shipped 2026-04-28.** New
  mechanical helper `src/autonovel/mechanical/dialogue.py` flags
  adverb-heavy speech tags (`said quietly`, `murmured softly`),
  said-bookisms (`exclaimed`, `murmured`, `whispered`,
  `growled`, …), and repeated-speech-verb stutters (the same
  non-`said` verb 3+ times within a 10-line window). Per-chapter
  counts + per-line hits with snippets. New CLI subcommand
  `autonovel mechanical dialogue <book_root>` and slash-command
  `/autonovel:dialogue`. 16 Tier-1 tests covering each pattern,
  edge cases (frontmatter strip, plain-said unflagged, stutter
  window boundaries), render shapes, and CLI round-trip.

- ~~**Dialogue mechanics — extension follow-ups.**~~
  **Shipped 2026-04-29** with the brittle parts deliberately
  scoped down (see feedback_avoid_brittle_python.md). Three new
  detectors in `mechanical/dialogue.py`:
  - **action-beat-as-tag clusters** — 3+ action-beat tags
    (`she laughed, "..."`) within a 10-line window.
  - **softening qualifiers in short retorts** — `maybe / kind
    of / a little / I think / I guess` inside dialogue lines
    under 80 chars.
  - **unattributed-dialogue clusters** — ≥3 consecutive un-tagged
    dialogue paragraphs. Reported as a review list, not a gate;
    the cast-count gate that 2026-04-29 testing tried to add
    was reverted because it relied on a brittle proper-noun-
    counting proxy that broke on Unicode names. The LLM
    judge's `voice_adherence` dimension is the right place to
    score this.
  Word lists kept short and curated (`ACTION_BEAT_VERBS` ~25
  entries, `SOFTENING_QUALIFIERS` ~13). 11 new Tier-1 tests +
  command-body disclaimer update. Tier 1+2: 1081 → 1092.
- ~~**Scene-level beat coverage in `evaluate.py`.**~~ **Shipped
  2026-04-25.** New `autonovel mechanical scenes <chapter>` helper
  splits a chapter into scenes by `***` / `---` / `* * *` breaks
  (Tier-1 testable; 14 tests covering frontmatter strip, surrounding
  whitespace tolerance, phantom-empty-scene drops, opening/closing
  edge cases, CLI round-trip with and without `--full`). evaluate.md
  step 10e walks the per-scene index and scores each scene 0/1 on
  goal / conflict / disaster_or_decision / consequence; aggregates
  to per-chapter `beat_coverage` block with `weakest_scenes` list
  (any scene missing 2+ beats), each entry carrying a one-sentence
  prescription naming the missed beat and what to add. Single-scene
  chapters get the "split into two scenes around the midpoint
  decision" suggestion. `--full` mode aggregates to
  `book_beat_coverage_score` + `weak_beat_coverage_chapters` list,
  which catches the "drifting middle" Bells failure mode. brief.md
  walks `weakest_scenes` and turns "tighten chapter 8" into "scene
  8.2 needs a decision before the break" with the scene's
  `opening_line` quoted for surgical targeting.
- ~~**Cliché bigram/trigram scanner.**~~ **Shipped 2026-04-25** —
  `autonovel mechanical cliches <path>` returns a curated bigram
  scan; `evaluate.md` invokes it for `--chapter` and `--full`,
  feeding `density_per_1000_words` into the slop penalty (every
  full unit above 2.0 subtracts 0.1, capped at 0.5).
- ~~**Sensory-channel balance scanner.**~~ **Shipped 2026-04-25** —
  `autonovel mechanical sensory <path>` returns per-channel
  fractions (visual/auditory/olfactory/gustatory/tactile) and a
  `dominant_channel` flag when one channel >70%. `evaluate.md`
  surfaces dominance as a chapter `weakest_moment` callout.
- ~~**Period register lock.**~~ **Shipped 2026-04-28.** New
  helper `src/autonovel/mechanical/period_register.py` rolls
  the existing `slop.period_ban_hits` scanner across every
  chapter and emits a per-chapter hit table + a worst-offenders
  ranking by total occurrences. Useful before typeset to confirm
  the manuscript stays in period across the full run. CLI
  subcommand `autonovel mechanical period-register <book_root>`
  and slash-command `/autonovel:period-register`. 16 Tier-1
  tests covering bans loading (comments + blanks), word-boundary
  case-insensitive matching, frontmatter stripping, summary
  aggregation, render shapes (with/without `--summary-only`,
  no-bans message, no-chapters message), and CLI round-trip.

- ~~**Period register — extension follow-up.**~~
  **Shipped 2026-04-29.** Per-chapter Flesch-Kincaid grade
  computed against a voice/seed/median baseline; chapters
  whose absolute delta exceeds `--threshold` (default 1.0
  grade level) are flagged. Pure math — no curated word-lists,
  no register dictionaries — so this scanner doesn't drift
  with vocabulary. New helper functions in
  `src/autonovel/mechanical/period_register.py`
  (`flesch_kincaid_grade`, `_syllables_in_word`,
  `build_syntax_drift_report`, `render_syntax_drift_markdown`),
  CLI subcommand `autonovel mechanical syntax-drift
  <book_root>`, slash-command `/autonovel:syntax-drift`.
  Reported as a review list — real chapter drift can be
  intentional register shift (action sequences, dialogue-
  heavy, modernism homage); the LLM judge in
  `/autonovel:evaluate`'s `voice_adherence` dimension scores.
  18 Tier-1 tests + 5 contract pickups. Tier 1+2: 1092 →
  1115.
- ~~**POV bleed scanner.**~~ **Shipped 2026-04-28.** New helper
  `src/autonovel/mechanical/pov_bleed.py` flags lines where a
  cast member who is NOT the chapter's POV is named with an
  interiority verb (`thought`, `felt`, `knew`, `realised`,
  `wondered`, `remembered`, `hoped`, `feared`, `believed`, …)
  or possessive interiority (`Niccolò's mind`, `Lucia's heart`).
  Cast comes from `shared/characters.md` (parsed in `**Name**`
  bullet form OR `## Name` heading form); chapter POV from the
  YAML frontmatter `pov:` field. False-positive caveat is
  documented inline in the rendered report — non-POV characters
  CAN have their interiority legitimately reported by another
  character, so output is a review list not a gate. CLI
  subcommand `autonovel mechanical pov-bleed <book_root>` and
  slash-command `/autonovel:pov-bleed`. 19 Tier-1 tests covering
  cast parsing (both shapes + missing file), verb / possessive
  patterns, POV-self-exclusion, no-cast / no-cast-override
  paths, render shapes, and CLI round-trip.

- **POV bleed — knowledge-edge follow-up.** The 2026-04-28 scanner
  catches interiority (`Niccolò thought`, `Lucia's mind raced`).
  Knowledge edges (POV references a fact they couldn't have)
  needs cross-chapter tracking and is best done as an LLM-judge
  dimension, not a mechanical scanner — the cheap "the woman /
  the man" version was considered 2026-04-29 and rejected per
  `feedback_avoid_brittle_python.md`: the de-anonymising-drift
  detector would need a brittle proper-noun heuristic that
  drifts on Unicode names + sentence-initial caps. Right shape
  is a future LLM-judge dimension that consumes the existing
  pov-bleed scanner output and adds knowledge-edge reasoning;
  hold for now.
- ~~**Bell's "irreversible change" scorer.**~~ **Shipped 2026-04-25.**
  evaluate.md gains an `irreversible_change` dimension on
  `--chapter` mode and `irreversible_change_arc` on `--full` mode.
  Per-chapter calibration runs from 9-10 (specific named irreversible
  change at the chapter's main beat) down to 1-2 (pure setup or
  stasis); chapter 1 specifically caps at 7 if the ending leaves the
  protagonist able to refuse the call to action. Whole-book mode
  walks every (N→N+1) chapter pair asking "could chapter N+1 have
  started from N's *opening* state?" — every "yes" is a chapter that
  failed to commit, surfaced in `cuttable_chapters`. Below 6 on the
  per-chapter score is added to `top_3_revisions` automatically.
  brief.md adds a `## Stability check` section (only when the eval
  log's score is <7) that names the reversion and prescribes ONE
  specific irreversible commitment — never falls back to vague
  "raise stakes" because that's exactly what the Stability Trap
  produces. The named ceiling failure from CLAUDE.md ("AI defaults
  to safe, round-edged endings; pacing ≈ 7 plateau on
  investigation-heavy plots") now has a measurement and a
  prescription.
- ~~**Per-chapter motif tracker.**~~ **Shipped 2026-04-28.**
  New mechanical helper `src/autonovel/mechanical/motifs.py` reads
  `books/<book>/motifs.md` (one bullet per motif: `- slug:
  keyword1, keyword2, keyword3`), strips YAML frontmatter from each
  chapter before counting (so `events: [bell-toll]` doesn't inflate
  the bell density), and matches keywords on word boundaries
  case-insensitively. Emits a markdown table with one row per
  chapter and one column per motif (zero-hit cells render as `·`).
  Back-half drop warnings fire only when the motif was used at
  least once in the front half — silent when a declared motif was
  never used (avoids noise). Books under 4 chapters skip warning
  logic entirely. CLI subcommand `autonovel mechanical motifs
  <book_root> [--format markdown|json]`. New slash-command
  `/autonovel:motifs` wraps it. 17 Tier-1 tests + 5 contract
  pickups; Tier 1+2: 747 → 769.
- ~~**Show-don't-tell — pre-flight scanner.**~~ **Shipped 2026-04-28.**
  New helper `src/autonovel/mechanical/show_dont_tell.py` casts a
  wider net than the existing slop regex. Four pattern families:
  emotion-state (`<X> was/felt/seemed <emotion>` against a curated
  ~50-word emotion list), interiority verbs (`knew`, `realised`,
  `understood`, `recognised`, `decided`, `thought`, `believed`,
  `wondered`, `hoped`, `feared`, `wished`, …), perception filters
  (`<Y> looked/sounded <adverb>` against a curated filter-adverb
  list), narrator labels (`It was <emotion>`, `There was
  <emotion>`). Per-chapter table + per-line hits with snippets;
  density-per-1000-words column for normalisation. Slash-command
  `/autonovel:show-dont-tell`. The LLM-judge ratio scoring
  upgrade (direct/indirect/hybrid classification + per-chapter
  ratio) is queued separately. 18 Tier-1 tests + 5 contract
  pickups. Tier 1+2: 1026 → 1049.

- ~~**Show-don't-tell — LLM-judge ratio upgrade follow-up.**~~
  **Shipped 2026-04-29.** `commands/evaluate.md` `--chapter`
  mode gains the `show_dont_tell_ratio` dimension; `--full`
  mode gains `show_dont_tell_arc`. Both invoke the mechanical
  pre-flight scanner via `bash`, classify each candidate
  line as **direct** (bare proposition, no anchor),
  **indirect** (anchored by sensory / behavioural evidence),
  or **hybrid** (legitimate direct telling — interior
  summary, time compression, register-mark in close-third).
  Per-chapter ratio = `(indirect + hybrid) / total`; mapped
  linearly to 0-10 with a penalty when raw `direct_count`
  exceeds `chapter_word_count / 500`. `worst_offenders` array
  surfaces the top-5 direct-classified lines with one-line
  embodiment suggestions for brief / revise. `--full`
  aggregates a `tell_heavy_chapters` list (ratio < 0.6) so a
  sweep brief can target them. Zero-candidates chapters score
  9.0 (not 10.0) to flag the suspicious case where the
  scanner found nothing. 7 Tier-1 regression locks lock the
  contract surfaces in `evaluate.md`. Tier 1+2: 1074 → 1081.

## Reader interest / reading experience

- ~~**Pacing curve graph in `/autonovel:evaluate --full`.**~~
  **Shipped 2026-04-25** — `--full` mode emits a markdown table
  with per-chapter words / score / tension / dialogue% / scenes /
  beats-hit so the user sees the shape of the book at a glance.
- ~~**Tension-drop alarms.**~~ **Shipped 2026-04-25** — `--full`
  scans the tension column for any window of three+ consecutive
  chapters trending down and surfaces a "⚠️  Tension drop
  detected: chapters X→Y→Z" callout with the recommended
  revision-pass invocation.
- ~~**First-page hook check.**~~ **Shipped 2026-04-25** —
  `/autonovel:evaluate --chapter 1` adds a separate
  `hook_strength` score over the first 250 words; surfaces it on
  its own line in the summary; flags below 6.0 as a real concern.
- ~~**Series-arc score.**~~ **Shipped 2026-04-28.** New helper
  `src/autonovel/mechanical/series_arc.py` and slash-command
  `/autonovel:series-arc` deliver a cross-book scoreboard:
  per-book completion (summary / eval / above-threshold counts
  + earliest/latest story_time), cross-book cast (characters
  appearing in ≥2 books, ranked by spread), backwards story-
  time jumps (chapter where `story_time` regresses from prior
  — legitimate for flashbacks but worth surfacing), unresolved
  threads (chapter `Threads opened:` with no later
  `Threads closed:` substring match), and a composite 0-10 arc
  score blending completion + above-threshold fraction +
  story-time discipline penalty + unresolved-thread penalty.
  CLI subcommand `autonovel mechanical series-arc <series_root>`
  + slash-command. 16 Tier-1 tests + 5 contract pickups. Tier
  1+2: 1005 → 1026.

- ~~**Series-arc — LLM-judge upgrade follow-up.**~~
  **Shipped 2026-04-29.** New `--phase series` mode in
  `commands/evaluate.md` scores arc *quality* across ≥2 books.
  Pairs with the structural scoreboard
  (`/autonovel:series-arc`): the helper provides evidence
  (cross-book cast, backwards story-time jumps, unresolved
  threads, structural arc score); the LLM judges quality
  (does the series open a load-bearing question and resolve
  it? do early-book setups pay off late? does each cross-book
  character earn their state changes? does world evolution
  stay consistent? does tone carry across books?). Five
  dimensions: `series_question`, `early_setup_late_payoff`,
  `cross_book_character_growth`, `world_evolution_consistency`,
  `tonal_continuity`. Top-level outputs include
  `series_score`, `weakest_book`, `top_3_arc_revisions`, and
  the load-bearing `unresolved_thread_payoff_plan` array
  (one entry per `series-arc` thread the LLM rates as a real
  payoff debt, with a one-sentence "where this should pay
  off" note that brief / revise can act on). Eval log lands
  at `.autonovel/eval_logs/<ts>_series.json` (series-level,
  not per-book). 8 Tier-1 regression locks pin the contract
  surface. Tier 1+2: 1115 → 1123.

## Maintenance

- ~~**Token + cost tracking.**~~ **Shipped 2026-04-28.**
  `command_log.LogEntry` gains optional fields: `book`, `model`,
  `tier`, `input_tokens`, `output_tokens`, `cache_read_tokens`,
  `cache_creation_tokens`, `cost_usd`. All optional — emitted
  to JSON only when populated so historical entries stay
  readable. `autonovel _end` accepts matching CLI flags
  (`--tier`, `--input-tokens`, `--output-tokens`,
  `--cache-read-tokens`, `--cache-creation-tokens`,
  `--cost-usd`); the postamble template instructs the runtime
  to forward whatever the session's usage report exposes.
  `lifecycle.end` now accepts a `usage` dict and threads it
  through to `command_log.append`. New `autonovel cost` CLI
  subcommand + `src/autonovel/cost.py` helper roll up
  per-book / per-tier / per-command totals with markdown +
  JSON output. Mechanical-only commands count as $0 runs and
  are surfaced separately from heavy / standard / light. 18
  Tier-1 tests covering log round-trip, partial telemetry
  (tokens but no cost), aggregation by book / tier / command,
  unknown-cost runs, error-runs, mechanical-runs, render
  shapes, lifecycle wiring, CLI happy paths. Tier 1+2: 1056 →
  1074.

- **Token + cost tracking — pricing table follow-up.** The 2026-04-28
  shipment surfaces whatever the runtime reports. Not yet
  done: an in-repo pricing table that maps (model, tier) →
  USD/1Mtok so a postamble can compute `--cost-usd` even
  when the runtime omits it. Hold for now — manual cost
  estimation is brittle and varies across plans
  (subscription vs API; with vs without prompt caching);
  better to display exactly what the runtime reports.

- **Token + cost tracking — `autonovel status` budget surface
  follow-up.** The 2026-04-28 shipment delivers `autonovel cost`
  (separate command). A natural extension is a one-line cost
  summary in `autonovel status` so the daily-checkpoint flow
  surfaces it without a second invocation. Cheap (~30 min):
  call `cost.build_report` from inside `_cmd_status` and add a
  one-liner like "spent $X.XX across N runs (M today)".
- **Bells Tier-4 fixture populate.** Copy the final Bells chapters
  from the `autonovel/bells` branch into
  `tests/fixtures/bells-reference/` and freeze `scores.json`.
  Standalone one-off; the harness is already in place.
- **Codex Tier-3 spot-check on a Codex-equipped box.** Has run on
  the dev machine; rerun in CI once a Codex CLI runner is available.
- **Gemini Tier-3 spot-check on a Gemini-equipped box.** Skipped on
  the PR-8 dev box because `gemini` was not on `$PATH`. Adapter has
  full Tier-1 coverage; just needs an end-to-end run.
- **`autonovel doctor --fix` for missing external CLI tools.** Today
  the doctor reports them; could shell out to brew/apt to install on
  approval. **Caveat from author testing 2026-04-25:** naïve `apt
  install` of `tectonic` on Chromebook/Debian frequently fails or
  installs a too-old version that autonovel can't use. A real
  `--fix` mode would need (a) per-OS install command tables, (b) a
  per-tool fallback chain when the package-manager version is broken
  (tectonic → apt → prebuilt static binary), and (c) post-install
  re-verification (run the binary, confirm version) rather than just
  checking `which`. Probably better as a separate `autonovel
  install-export-tools` subcommand than a `doctor` flag, since the
  scope is "set up an environment" not "diagnose a series".

- ~~**`autonovel install-export-tools` interactive helper.**~~
  **Shipped 2026-04-29 PM** as commit `1baae2c`. New CLI
  subcommand `autonovel install-export-tools [--exports
  pdf,epub,cover,audiobook,art] [--apply] [--yes]`. Detects OS
  (macos/debian/fedora/arch/other from /etc/os-release) and
  install method (pipx/pip/editable). Maps user-facing exports
  to per-tool install plans, deduping shared tools. Each tool
  has a per-OS install command list, optional notes (e.g.
  apt-tectonic too old → upstream prebuilt), and a `verify`
  command run after install to catch too-old binaries that
  `which` would falsely report as OK. Python pkg installs
  (Pillow / pydub) emit `pipx inject autonovel <pkg>` when
  pipx-installed, else `pip install <pkg>`. Default mode prints
  the plan; `--apply` runs with per-tool confirmation. New
  helper `src/autonovel/install_export_tools.py`. 16 new Tier-1
  tests. Tier 1+2: 1207 → 1223. Doc sync in operating-guide §3b.
  Original entry follows for context:

- **`autonovel install-export-tools` interactive helper.** Surfaced
  by 2026-04-25 author testing: writers hit real pain getting
  tectonic + Pillow + ffmpeg installed on Chromebook ("for a writer
  this stuff is too hard"). New subcommand asks the user which
  exports they want (PDF? cover? audiobook?), detects the OS,
  prints the exact commands they need (or runs them with
  confirmation), and handles the known special cases (tectonic
  fallback to prebuilt binary on Linux; `pipx inject` for `Pillow`
  / `pydub` when autonovel was installed without `[export]`
  extras; per-OS font install hints for cover rendering). Goal:
  zero shell debugging for the export path — the writer answers
  three questions and gets working tools. Cost: ~2-3 hrs.
- **Drift on `commands/*.md` frontmatter schema.** When `argument-hint`
  or `model_tier` semantics change, the contract test catches usage
  but not field shape. Add a JSON-schema file at
  `src/autonovel/validators/command_schema.json` and a Tier-1 check.

## Portability

- **Real `npm publish` flow.** `package.json` and `bin/autonovel.js`
  are scaffolded but the package has not been published; verify
  `npm install -g autonovel` and `npx autonovel install` actually
  work on a clean box. Probably needs `prepublishOnly` to bundle the
  Python source via a build step, or a postinstall pipx hook.
- **`autonovel install --dry-run`.** Print what *would* be written
  without touching the runtime's directory. Useful for CI and for
  reviewing before letting npx mutate `~/.claude/`.
- **Per-runtime tool-name regression test.** Tier-1 already
  golden-files each adapter; add a fuzzer that random-generates
  command bodies and asserts no double-translation happens.
- **Windows path handling.** Adapters use `pathlib`, but the install
  destinations (`~/.claude/commands/...`) and the bash preamble assume
  POSIX semantics. Smoke once on a Windows runner before claiming
  cross-platform support.
- **`project.yaml :: image.provider`** is referenced in
  `commands/art-curate.md` but not yet read by any code. Either wire
  it through the adapter context or remove the documentation.
- **uv vs pip.** Repo currently has `uv.lock`; CLAUDE.md says
  `pip install -e .[test,export]`. Pick one canonical path or
  document both.

## Testing

- **Per-runtime smoke matrix in CI.** Today CI is Tier 1+2 only. A
  weekly cron that runs Tier-3 against Claude Code on a
  subscription-auth runner would catch runtime-version drift early.
- **Genre-fixture matrix runner.** `pytest --genre-matrix` (referenced
  in REWRITE-PLAN §12a) is not yet implemented. Today users run one
  fixture at a time via `autonovel test-fixture run <name>`.
- **`pytest -m 'genre("mystery")'` parameter selection.** The
  `genre(name)` marker is registered in `pyproject.toml` but pytest's
  `-m` parser doesn't filter by argument by default. Either add a
  pytest plugin/hook that reads the genre name out of the marker, or
  update docs to recommend `-k <genre>` instead.
- **Adapter round-trip test for the Codex `auth.json` rewriting.**
  The PR-8 smoke test redirects `CODEX_HOME` and copies the user's
  real `auth.json` into the redirected home — fragile. Add a Tier-1
  unit test that exercises the env-redirection path against a
  fake `auth.json`.
- **Mechanical-module pyproject extras smoke.** The `[export]` extras
  pin Pillow + pydub but no test imports them — a dependency drift
  in those packages would only surface at export time. Add a
  smoke import-only test gated on `[export]` being installed.
- **Flakiness budget.** `tests/flakiness.jsonl` is append-only with
  no rotation. Add `autonovel test-fixture trim-flakiness --keep N`
  or a `pytest --strict-flakiness` mode that fails when a test has
  flipped > N times in the last K runs.
