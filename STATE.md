# autonovel rewrite state

**Last updated:** 2026-04-24 by PR 9

## Completed
- [x] PR 1: layout + housekeeping
- [x] PR 2: first command + Claude adapter
- [x] PR 3: foundation commands
- [x] PR 4: evaluation + revision commands
- [x] PR 5: research + period guardrails
- [x] PR 6: orchestrator + multi-book wiring
- [x] PR 7: art, covers, audiobook, typeset, landing
- [x] PR 8: Codex + Gemini adapters
- [x] PR 9: docs + full genre fixtures + publish prep

## In progress
- none — PR 9 landed. Tier 1+2 451/451 green. `npm publish` itself
  is parked behind a human gate (see FUTURE-TODOS.md).

## Blockers
- none

## Decisions log (append-only)
- 2026-04-24: Use `/autonovel:` namespace (REWRITE-PLAN.md §4; avoids `/gpd:`).
- 2026-04-24: Model tiers abstract over provider; adapters pick specific models (§17).
- 2026-04-24 (PR 1): series/book scaffolder, `.autonovel/` lifecycle primitives,
  next-step decision table, chapter frontmatter validator, `autonovel` CLI.
- 2026-04-24 (PR 2): generic commands live under `commands/` at repo root and
  ship inside the wheel via `autonovel/commands/`. Adapter translates
  generic tool names (`file_read`, `file_write`, `task`, `web_search`,
  `web_fetch`, `bash`) to runtime-specific names. Claude Code adapter writes
  to `~/.claude/commands/autonovel/<stem>.md` by default; `--path` overrides.
- 2026-04-24 (PR 2): preamble/postamble injected by the adapter invokes two
  hidden housekeeping subcommands — `autonovel _begin` and `autonovel _end` —
  so command authors never reimplement lock / checkpoint / last-action / log.
  This is the one-place-to-change contract for the whole pipeline.
- 2026-04-24 (PR 2): `/autonovel:next` and `/autonovel:resume` shipped with
  the first command so the state-file formats (last-action.json,
  in-progress.lock) get exercised by real commands from day one.
- 2026-04-24 (PR 2): `draft_chapter.py` deleted (§18). `run_pipeline.py` and
  `run_drafts.py` still reference it by subprocess, which is accepted — both
  delete in PR 6.
- 2026-04-24 (PR 2 polish): smoke test gate relaxed to `claude`-on-PATH
  only; word-count window widened to [1800, 5000]; retry-once policy live
  via `tests/conftest.py` + `pytest-rerunfailures`. Pattern for PR 3+:
  future smoke tests just add `@pytest.mark.smoke` to inherit the retry.
- 2026-04-24 (auth policy, project-wide): **subscription auth is primary.**
  The smoke test subprocess strips `ANTHROPIC_API_KEY` from the env before
  invoking `claude -p` (because Claude Code prefers API-key billing when
  both modes are present, which would defeat the "free against my
  subscription" goal). Escape hatch: `AUTONOVEL_SMOKE_USE_API_KEY=1` on
  the developer's env preserves the key. New runtime commands don't need
  to do anything — they run inside the user's Claude Code session, which
  is subscription-auth automatically. Legacy Python scripts
  (`evaluate.py`, `review.py`, …) still call `api.anthropic.com` directly
  with `ANTHROPIC_API_KEY` — that's the pre-rewrite path, tracked for
  deletion in §18 across PRs 4-7.
- 2026-04-24 (PR 3): five foundation commands shipped — `gen-world`,
  `gen-characters`, `gen-outline`, `voice-discovery`, `gen-canon`. Each
  uses the PR 2 preamble/postamble contract unmodified; no new adapter
  work required. Model tiers: `gen-world`, `gen-characters`,
  `voice-discovery` → heavy (Opus-class creative drafting); `gen-outline`,
  `gen-canon` → standard (structured extraction from already-written
  Layer-4/3 material).
- 2026-04-24 (PR 3): `/autonovel:sidequest` dispatcher shipped as a
  read-only menu that points at real commands rather than invoking them
  (§21.7). Routing via a separate slash-command invocation preserves the
  target's own lock/checkpoint guarantees; menu grows per §21.10 as later
  PRs land revision/research sidequests.
- 2026-04-24 (PR 3): nine Python generators deleted per §18 — `seed.py`,
  `gen_world.py`, `gen_characters.py`, `gen_outline.py`,
  `gen_outline_part2.py`, `voice_fingerprint.py`, `gen_canon.py`,
  `build_outline.py`, `build_arc_summary.py`. `run_pipeline.py` still
  shells out to the first six by name; those references are accepted as
  dangling and delete with `run_pipeline.py` itself in PR 6.
- 2026-04-24 (PR 4): mechanical regex logic extracted into
  `src/autonovel/mechanical/` (`slop.py`, `cuts.py`). Commands shell out
  via `python -m autonovel.mechanical <slop|period-bans|apply-cuts>` so
  the deterministic half is out of the prompt and Tier-1 testable. The
  scoring surface (TIER1/2/3 word lists, fiction-AI-tells,
  telling-patterns, em-dash density, sentence-length CV, structural
  tics, and the penalty weighting) is copied verbatim from
  pre-rewrite `evaluate.py` — do not tune the weights without
  re-freezing `tests/fixtures/bells-reference/scores.json`.
- 2026-04-24 (PR 4): eight evaluation/revision commands shipped —
  `evaluate`, `adversarial-edit`, `apply-cuts`, `reader-panel`,
  `review`, `brief`, `revise`, plus `compare` folded into
  `/autonovel:evaluate --compare`. Model tiers: `apply-cuts` → light
  (no LLM, shells out); `brief` → standard; all others (drafting-class
  judgement) → heavy.
- 2026-04-24 (PR 4): five sidequest commands shipped (§21.10) — `shorten`,
  `lengthen`, `split-chapter`, `merge-chapters`, `revoice`. Each lands
  changes as a single checkpoint so `autonovel rollback` undoes the
  full operation. Chapter renumber logic in `split-chapter` and
  `merge-chapters` runs via `bash` with `mv`/`git mv` in collision-safe
  order, never as an LLM rename loop (CLAUDE.md gotcha: "Chapter
  renumbering after merges/deletes must be done by script, never
  hand-edited"). The sidequest menu grew from 11 to 23 entries.
- 2026-04-24 (PR 4): path-placeholder convention unified on
  `ch{chapter}.md` / `ch_{chapter}.md` / `ch{chapter}_cuts.json` in both
  frontmatter and body. The zero-padding is applied at runtime by the
  runtime — commands describe the padding in words rather than using
  `{chapter:02d}`, because the contract test (`_path_stem in body`)
  needs a substring match.
- 2026-04-24 (PR 4): eight Python generators deleted per §18 —
  `evaluate.py`, `adversarial_edit.py`, `apply_cuts.py`,
  `reader_panel.py`, `review.py`, `gen_brief.py`, `gen_revision.py`,
  `compare_chapters.py`. `run_pipeline.py` and `run_drafts.py` still
  reference them by subprocess; those references are accepted as
  dangling and delete with their callers in PR 6 (same policy as PR 3).
- 2026-04-24 (PR 5): nine commands shipped — `research`,
  `check-anachronism`, `promote-canon`, plus the six §21.10 PR-5
  sidequests `add-character`, `deepen-character`, `rename-character`,
  `add-subplot`, `foreshadow`, `add-source`. Model tiers: `research`,
  `deepen-character`, `add-subplot`, `foreshadow` → heavy (drafting-
  class rewrites); `check-anachronism`, `promote-canon`,
  `add-character`, `rename-character`, `add-source` → standard
  (structured edits / mechanical sweeps with light LLM judgment).
- 2026-04-24 (PR 5): `/autonovel:research` uses the generic
  `web_search` + `web_fetch` tools (translated by the adapter to
  `WebSearch` / `WebFetch` for Claude Code). Primary URLs in
  `shared/research/sources.yaml` are mandatory stops; citations use
  BibTeX shortnames resolved against `shared/sources.bib`. The
  Venetian-apothecary smoke test in `tests/smoke/test_historical_research.py`
  asserts file shape (sources section, ≥2 distinct citations, primary
  URL hit, period-detail keyword floor, uncertainty hedge, candidate
  canon entries) — not factual content, per §12.4 flakiness policy.
- 2026-04-24 (PR 5): `/autonovel:check-anachronism` is the two-pass
  guardrail — deterministic half reuses `python -m autonovel.mechanical
  period-bans`; semantic half is LLM overlay for concepts / mental
  frames / metaphors the word list cannot catch. Writes a JSON report
  under `edit_logs/`, never touches the chapter.
- 2026-04-24 (PR 5): `/autonovel:promote-canon` is the single entry
  point to `shared/canon.md`. `.autonovel/in-progress.lock` (from the
  preamble) gives §19 cross-book race mitigation; contradictions are
  never merged optimistically — they park under a `# Conflicts` header
  in `books/{book}/pending_canon.md` for manual resolution.
- 2026-04-24 (PR 5): `shared/period_bans.txt` template seeded for
  1400-1600 Europe (~90 entries spanning modern register, 19-20th
  century technology metaphors, modern institutional concepts,
  forensics, and managerial idioms). The existing fixture's smaller
  list is preserved to keep the PR-4 revision smoke tests green —
  expanding the fixture would require re-checking every seed paragraph
  against the new bans.
- 2026-04-24 (PR 5): `/autonovel:rename-character` script-based, not
  LLM-rename (CLAUDE.md: "Chapter renumbering ... must be done by
  script, never hand-edited" — same discipline applies to global
  rename). Word-boundary `sed`, three casings (Title/lower/UPPER);
  refuses when any target overlaps a longer word (e.g. `Ana` vs
  `Anatolia`) to prevent silent mangling.
- 2026-04-24 (PR 5): sidequest dispatcher grew from 23 to 32 entries,
  adding the PR-5 research + cast/thread section.
- 2026-04-24 (PR 6): `src/autonovel/context_loader.py` is the
  multi-book context resolver. Given `(book, chapter)` it returns a
  typed `ContextBundle` with `shared`, `book_files`,
  `sibling_chapters`, `events`, and `excluded_spoilers`. Spoiler rule:
  a sibling chapter is readable only if its `story_time` upper bound
  is ≤ the target chapter's `story_time` lower bound. Event rendering
  (a chapter appearing under `rendered_in` for one of this chapter's
  events) surfaces *additional* sibling chapters, but spoiler gating
  still dominates — a chapter that fails the story_time check stays
  excluded even if it renders the same event. Also exposed as a CLI
  (`python -m autonovel.context_loader --book X --chapter N
  --series-root …`) so `/autonovel:run-pipeline` can shell out for
  a JSON manifest before routing to `/autonovel:draft`.
- 2026-04-24 (PR 6): `src/autonovel/validators/events.py` parses
  `shared/events.md` into typed `Event` records (§8: id, title,
  date, location, present, canonical, rendered_in, book_constraints).
  The parser is forgiving (it returns every event it could
  identify) and emits a problems list rather than raising — the
  validator's job is to surface issues in a single report, not to
  fail-fast on the first bad line. `check_cross_consistency(events,
  project_books)` flags `rendered_in` rows that name books missing
  from `project.yaml`.
- 2026-04-24 (PR 6): three commands shipped — `run-pipeline`,
  `reorder`, `remove-chapter`. `/autonovel:run-pipeline` is an
  advisory orchestrator (model_tier: light, context_mode: series);
  every content mutation still goes through a sibling `/autonovel:*`
  command that owns its own lock + checkpoint + footer. Snapshot
  before/after `/autonovel:run-pipeline` must be byte-identical
  apart from `.autonovel/` bookkeeping — that is the contract. The
  reorder + remove-chapter sidequests follow the §21.8 discipline:
  chapter renumber runs via `bash` + `mv` in collision-safe order,
  never an LLM rename loop. Sidequest dispatcher grew from 32 to 35
  entries.
- 2026-04-24 (PR 6): deleted `run_pipeline.py` and `run_drafts.py`
  per §18. Dangling references from PR 3 and PR 4 (gen_world,
  gen_characters, evaluate, adversarial_edit, apply_cuts, reader_panel,
  review, gen_brief, gen_revision, compare_chapters) were to these
  two orchestrators and now resolve. Legacy doc references in
  README.md, WORKFLOW.md, PIPELINE.md, and CLAUDE.md are left
  untouched on purpose — REWRITE-PLAN §18 parks PIPELINE.md for PR 8
  and the README/CLAUDE rewrite for PR 9; editing them in PR 6 would
  sprawl the diff.
- 2026-04-24 (PR 7): fifteen export commands shipped —
  `art-style`, `art-directions`, `art-curate`, `art-pick`,
  `art-ornaments-all`, `art-vectorize`, `cover-composite`,
  `cover-print`, `audiobook-script`, `audiobook-voices`,
  `audiobook-generate`, `audiobook-assemble`, `typeset`, `landing`,
  `package`. Model tiers: creative briefs (`art-style`,
  `art-directions`) → heavy; structured / judgement prose
  (`art-curate`, `art-ornaments-all`, `audiobook-script`,
  `audiobook-generate`, `landing`) → standard; mechanical / PIL-only
  (`art-pick`, `art-vectorize`, `cover-composite`, `cover-print`,
  `audiobook-voices`, `audiobook-assemble`, `typeset`, `package`) →
  light. Sidequest dispatcher grew from 35 to 50 entries.
- 2026-04-24 (PR 7): four new `python -m autonovel.mechanical`
  subcommands exported — `spine-width` (cover canvas + spine calc
  from pages + paper stock + trim + bleed), `audio-validate` (shape
  + speaker-coverage check on parsed chapter scripts), `audio-chunk`
  (pack script segments into ElevenLabs-budget chunks with fallback
  voice resolution), `audio-marks` (cumulative chapter timestamps;
  optional `ffmetadata` output for m4b embedding), and `build-tex`
  (chapters_content.tex builder ported verbatim from
  `typeset/build_tex.py`). Each is pure-Python, writes JSON on
  stdout, and is Tier-1 tested (61 new tests across
  `test_mechanical_spine.py`, `_audio.py`, `_latex.py`).
- 2026-04-24 (PR 7): PIL-heavy cover rendering factored into
  `src/autonovel/export/cover.py` — `composite_cover` (e-book text
  overlay), `print_cover` (KDP/Lulu/IngramSpark wraparound with
  spine from `mechanical.spine.cover_spec`), and `thumbnail_matrix`
  (Amazon full-size, 800×1200 web, 400×600 social, 800×800 square).
  Commands shell out via `python3 -c "from autonovel.export.cover
  import ..."` rather than inlining the ~200-line PIL script into
  command bodies. The landing HTML renderer lives alongside at
  `src/autonovel/export/landing.py` with `@KEY@` substitution so the
  template survives being inside CSS and JSON-LD blocks.
- 2026-04-24 (PR 7): typeset templates genericised. The pre-rewrite
  `typeset/novel.tex` (Bells-specific) now uses `@TITLE@`,
  `@AUTHOR@`, `@SERIES_NAME@`, `@YEAR@` placeholders; `epub_*`
  templates likewise. Moved from repo root to
  `src/autonovel/templates/series/typeset/` so every new series gets
  a local copy at scaffold time. `landing/index.html` gave up its
  Bells content and moved to
  `src/autonovel/templates/series/landing/template.html`. The
  `new-series` scaffolder picks them up via the existing `_copy_tree`
  path — no new code.
- 2026-04-24 (PR 7): deleted `gen_art.py`, `gen_art_directions.py`,
  `gen_cover_composite.py`, `gen_cover_print.py`,
  `gen_audiobook_script.py`, `gen_audiobook.py`,
  `typeset/build_tex.py`, and `landing/index.html` per §18. The
  `typeset/` and `landing/` directories at repo root are now empty
  and have been removed; their content lives under
  `src/autonovel/templates/series/`. Legacy doc references in
  README.md, WORKFLOW.md, PIPELINE.md, CLAUDE.md that still mention
  the deleted scripts are left untouched on purpose — REWRITE-PLAN
  §18 parks the README/CLAUDE rewrite for PR 9.
- 2026-04-24 (PR 7): `audiobook_voices.json` at repo root kept as
  the example voice map (the same file the Bells production used).
  It's not read by any new command — `/autonovel:audiobook-voices`
  writes per-book voices at `books/{book}/audiobook/voices.yaml`.
  The root file can be deleted in PR 9 along with the README rewrite;
  leaving it in place for now so tooling users have a reference
  shape to compare against.
- 2026-04-24 (PR 7): Tier-3 smoke coverage is intentionally
  **one test**, not fifteen. `tests/smoke/test_typeset_smoke.py`
  exercises `/autonovel:typeset --book tiny-inquisitor --pdf-only`
  and asserts `chapters_content.tex` exists with drop caps + every
  chapter title, the copied `novel.tex` has placeholders
  substituted, and (only if `tectonic` is installed) the produced
  `novel.pdf` is ≥ 4 KB. Art / cover / audiobook commands need paid
  APIs (fal.ai, ElevenLabs) and are left as manual-invoke only; PR 9
  will document the manual path.
- 2026-04-24 (PR 8): two new adapters shipped — `CodexAdapter` and
  `GeminiAdapter`. `installer.load_adapter` now dispatches on
  `claude` / `codex` / `gemini`; `detect._candidates()` surfaces all
  three for the auto-install path. Tier 1 added 24 golden-file tests
  (`tests/deterministic/test_adapter_codex.py`,
  `test_adapter_gemini.py`); Tier 2 contract tests parametrise over
  every command unchanged. Total Tier 1+2: **440 passing**.
- 2026-04-24 (PR 8): REWRITE-PLAN §11 went stale between writing and
  implementation. Codex CLI 0.125 retired the `~/.codex/prompts/`
  slash-command convention and now uses skills
  (`~/.codex/skills/<name>/SKILL.md` with YAML frontmatter, same
  shape as Claude skills). The adapter installs to
  `~/.codex/skills/autonovel/<stem>/SKILL.md` so a single install
  marker (`autonovel/`) cleanly covers uninstall. Skill name is
  prefixed `autonovel-<stem>` to avoid collisions with user-installed
  skills sharing a stem. Per-skill model pinning is not yet supported
  by Codex — the intended tier and a suggested model name go into
  the SKILL.md `metadata` block as documentation.
- 2026-04-24 (PR 8): Gemini adapter targets
  `~/.gemini/commands/autonovel/<stem>.toml` per §11. Prompt body
  uses TOML literal triple-quoted strings (`'''…'''`) rather than
  basic strings, because command bodies contain LaTeX backslashes
  (e.g. art-vectorize) that would otherwise need escaping. The
  adapter raises if a body ever contains `'''` so the literal-string
  delimiter stays unambiguous; nothing in the current 48 commands
  trips it. `description` and `arg_hint` go through a single-line
  basic-string escaper (`\\` and `"` only).
- 2026-04-24 (PR 8): tool-name translation in body is intentionally
  scoped to backticked tokens only (`` `task` `` → `` `spawn` `` for
  Codex, `` `task` `` → `` `run_agent` `` for Gemini, etc.). Word-
  boundary substitution would mangle prose like "is a creative task"
  or "bash your seed.txt"; the fixture commands contain both
  patterns so this matters. Generic names that already match the
  target runtime's verb (`file_read` for Codex) are kept as identity.
- 2026-04-24 (PR 8): Tier-3 spot-check smoke tests added —
  `tests/smoke/test_codex_smoke.py` and `tests/smoke/test_gemini_smoke.py`.
  Each runs a `gen-canon`-shaped invocation against the
  `tiny-series-historical` fixture. Both auto-skip when the runtime
  binary is absent. The Codex test redirects `CODEX_HOME` into the
  test's `tmp_path` and copies the user's real `auth.json` over so
  subscription auth survives without polluting the global install.
  Gemini test installs project-local under `<series>/.gemini/commands/`.
- 2026-04-24 (PR 8): `PIPELINE.md` moved to `docs/pipeline-history.md`
  per §18. Stale references in README.md / WORKFLOW.md / CLAUDE.md
  are left untouched on purpose — REWRITE-PLAN §18 parks the
  README/CLAUDE rewrite for PR 9 to keep diffs small.
- 2026-04-24 (PR 7): external-tool dependency check folded into
  `autonovel doctor`. New `EXPORT_TOOLS` table maps each command's
  external CLI dependency (tectonic, pandoc, potrace, ffmpeg,
  rsvg-convert, fontconfig) to the slash-command that needs it and
  the OS install hint. Surfaces as WARNINGS (never PROBLEMS) so a
  user who only drafts and revises is never told their setup is
  broken because they don't have tectonic. Three new tests in
  `tests/deterministic/test_doctor.py` lock the contract: every
  reported line includes purpose + install hint, missing tools are
  warnings not problems, and the `export_tools=False` flag silences
  the whole pass for callers that don't care. Python image/audio
  deps (Pillow, pydub) move to a new `[export]` extras-require
  group; `.env.example` documents both keys (FAL_KEY,
  ELEVENLABS_API_KEY) and the OS install hints (apt + brew).
- 2026-04-24 (PR 9): seven new genre fixtures shipped under
  `tests/fixtures/tiny-series-{scifi,literary,mystery,thriller,romance,fantasy,horror}/`
  with paired smoke tests at `tests/smoke/test_<genre>_smoke.py`.
  Each test asserts a §12 genre-characteristic property
  (sci-fi: ≥3 hard-limit bullets in world.md and no `[citation needed]`
  placeholders; literary: ≥5 distinct voice-discovery trials;
  mystery: ≥3 red herrings + clue-per-act ledger;
  thriller: stakes-escalation per chapter + ≥1 page-turn hook;
  romance: four-beat coverage + HEA/HFN named;
  fantasy: every magic-system bullet has a cost/limit clause;
  horror: dread keyword + sensory-specifics per chapter).
  All seven auto-skip cleanly when `claude` is not on `$PATH`.
- 2026-04-24 (PR 9): `autonovel test-fixture new|list|run` shipped.
  Scaffolds a fixture series + paired smoke-test stub by walking up
  from cwd to the repo root (a directory carrying both
  `tests/fixtures/` and `tests/smoke/`). 11 new Tier-1 tests in
  `tests/deterministic/test_test_fixture.py` cover the layout,
  rejection of bad names, idempotency-failure on existing fixtures,
  list/has-smoke-test marking, and missing-smoke detection. Total
  Tier 1+2: **451 passing** (440 → 451).
- 2026-04-24 (PR 9): npm shape scaffolded — `package.json` declares
  the `autonovel` bin, `bin/autonovel.js` is a thin Node shim that
  forwards to `python -m autonovel.cli`. The shim picks `python3`
  then `python` from `$PATH`, tries `import autonovel`, and falls
  back to running against the bundled `src/` via `PYTHONPATH` for
  `npx autonovel ...` against an unprovisioned Python (otherwise
  prints a `pipx install autonovel` hint). Actual `npm publish` is
  deferred to a human gate (FUTURE-TODOS.md "Real `npm publish`
  flow").
- 2026-04-24 (PR 9): docs landed under `docs/` —
  `commands.md` (every `/autonovel:*` per tier+context-mode),
  `multi-book.md` (story-time gating, events ledger, promote-canon),
  `testing.md` (four tiers, auth policy, flakiness),
  `adding-a-genre-fixture.md` (§12a walkthrough),
  `writing-a-historical-series.md` (12-step end-to-end). README
  rewritten for the rewrite (npm + npx + pipx install paths;
  install requirements; doc index; subscription-auth guidance).
  CLAUDE.md rewritten as the agent-side conventions file; AGENTS.md
  and GEMINI.md symlink to it.
- 2026-04-24 (PR 9): legacy root files deleted —
  `WORKFLOW.md` (replaced by `docs/writing-a-historical-series.md`),
  `audiobook_voices.json` (the example moved to
  `commands/audiobook-voices.md`'s docs;
  `/autonovel:audiobook-voices` writes per-book at
  `books/{book}/audiobook/voices.yaml`),
  `main.py`, repo-root `world.md` / `characters.md` / `outline.md` /
  `canon.md` / `voice.md` / `MYSTERY.md` / `state.json` /
  `results.tsv` / `chapters/.gitkeep` (all pre-rewrite per-novel
  templates, now under `src/autonovel/templates/`). `program.md`
  moved to `docs/program-history.md` (parallel to PR-8's
  `docs/pipeline-history.md`); the one inline reference in
  `commands/gen-outline.md` was replaced by an inline 4-line
  Stability-Trap explanation. `.env.example` cleaned of legacy-Python
  language.
- 2026-04-24 (PR 9): forward-looking todos consolidated into
  `FUTURE-TODOS.md` (output writing quality, reader interest,
  maintenance, portability, testing). ROADMAP.md no longer doubles as
  a future-todos sink — that role moves to FUTURE-TODOS.md so a
  freshly cleared session has one obvious place to look.
- 2026-04-24 (PR 4): Tier-4 Bells regression harness scaffolded at
  `tests/fixtures/bells-reference/` (empty chapters dir + empty
  scores.json + populate-instructions README) and
  `tests/smoke/test_bells_regression.py` (marked `@pytest.mark.smoke
  @pytest.mark.regression`). Skips cleanly until the fixture is
  populated from the `autonovel/bells` branch. Two guards: (a) a
  deterministic `slop_penalty` drift check tolerant to ±0.1, and (b) an
  LLM-judged `overall_score` drift check tolerant to ±0.5 per §12.4.
  The LLM half carries an inline TODO (Bells → series bridge) so the
  harness stays explicitly skipped rather than silently passing.

## Tests last known green
- Tier 1 + Tier 2 (deterministic + contracts): 2026-04-24 — **451
  passing** (`pytest tests/deterministic tests/contracts`). PR 9
  added 11 new Tier-1 tests in
  `tests/deterministic/test_test_fixture.py` covering the
  `autonovel test-fixture new|list|run` housekeeping shape: layout
  parity with `autonovel new-series`, smoke-test stub generation
  (markers + function name + fixture-name interpolation), name
  validation, idempotency-on-existing rejection, repo-root walk-up,
  and `list_fixtures` marking ✓ vs · for fixtures with/without a
  paired smoke test. The seven new fixture directories did not
  trigger any new contract tests; the existing contract suite is
  command-shape only.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-04-24 — 440
  passing (`pytest tests/deterministic tests/contracts`). PR 8
  added 24 new Tier-1 tests (12 in `test_adapter_codex.py`,
  12 in `test_adapter_gemini.py`) covering render, frontmatter
  shape, backticked tool-name translation, custom model maps,
  install round-trip, install-twice idempotency, and a
  `tomllib.loads` round-trip on every emitted Gemini `.toml`.
  Earlier PR-7 line:
- Tier 1 + Tier 2 (deterministic + contracts): 2026-04-24 — 416
  passing (`pytest tests/deterministic tests/contracts`). PR 7
  added 61 new Tier-1 tests and ~75 contract-test parametrisations
  (15 new commands × 5 parametrised checks per command):
  - `test_mechanical_spine.py` (14): spine-width by paper stock,
    cover-canvas arithmetic, pixel conversions, override precedence,
    CLI emits JSON.
  - `test_mechanical_audio.py` (24): `validate_script` shape rules,
    `chunk_segments` packing + tag-drop + fallback voice, overage
    split on sentence boundary, chapter marks cumulative + no
    trailing pause + ffmetadata format.
  - `test_mechanical_latex.py` (23): escape of the five LaTeX
    specials, scene-break / italic / dash / smart-quote conversion,
    drop-cap wrapping, multi-chapter build, ornament PDF-preferred-
    over-PNG wiring, CLI round-trip.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-04-24 — 280 passing
  (`pytest tests/deterministic tests/contracts`). PR 6 added 17 new
  Tier-1 tests: 8 for the events validator
  (`tests/deterministic/test_events_validator.py` — good ledger parse,
  duplicate id detection, missing required fields, bad ISO date,
  malformed `rendered_in` row, cross-consistency against project
  books, empty document, Path accepted) and 9 for the context loader
  (`tests/deterministic/test_context_loader.py` — shared+book path
  inclusion, sibling spoiler gating, event-rendering surfacing with
  spoiler dominance, unknown book/chapter errors, missing story_time
  error, CLI success + error paths). PR 6's three new commands
  (`run-pipeline`, `reorder`, `remove-chapter`) are auto-picked up by
  the contract test. `context_loader.py` lives at
  `src/autonovel/` top level (not under `validators/`) because it
  composes shared files, book files, outline parsing, and events —
  it is a context builder, not a pure validator.
- Tier 3 (smoke): 2026-04-24 — Claude Code under subscription auth.
  - `tests/smoke/test_foundation_smoke.py` — 6/6 green (4m41s from PR 3).
  - `tests/smoke/test_revision_smoke.py` — **6/6 green (10m32s)** on
    the first clean PR-4 run. Tests:
    `evaluate_chapter`, `adversarial_edit_produces_cuts`,
    `apply_cuts_reduces_word_count`, `brief_writes_structured_brief`,
    `revise_rewrites_chapter`, `shorten_compresses_chapter`.
  Two real bugs were caught by the first run and fixed before green:
    1. `ch{chapter:02d}` placeholder had been flattened to `ch{chapter}`
       during PR 4 to satisfy a contract test. That broke the
       zero-pad-to-two-digits convention the smoke tests assert
       (`ch01_cuts.json` etc.); reverting to `ch{chapter:02d}` both in
       frontmatter and body text keeps contract and smoke tests green
       simultaneously.
    2. `/autonovel:apply-cuts` step 4 was written as a multi-line
       bash command; bash parses newlines as statement separators,
       so the model's shell invocation ran the first fragment with
       no args and tried to execute path literals. Rewritten as a
       single-line call with an explicit "do not add --dry-run" note.
  One test-harness bug was also caught and fixed:
    3. The seeded chapter body repeated a paragraph 16 times, so the
       cut-quote appeared 16 times. The mechanical module correctly
       refuses ambiguous matches. Seed now has a unique marker
       paragraph; a collection-time assertion
       (`assert _SEED_BODY.count(SEED_UNIQUE_CUT_QUOTE) == 1`)
       fails fast if future seed edits break that invariant.
- Tier 3 (PR-5 live-research smoke): 2026-04-24 — **1/1 green (2m21s)**
  on the first clean PR-5 run. `tests/smoke/test_historical_research.py`
  ran under subscription auth against live web (WebSearch + WebFetch).
  Assertions that passed: sources section present, ≥2 distinct
  `[shortname]` citations, ≥1 primary URL from `sources.yaml` echoed in
  the notes, ≥2 period-specific keywords from the generous detail list,
  uncertainty hedge present, candidate-canon section present. §12.4
  flakiness policy says this test is allowed to flake; retry-once
  policy in `tests/conftest.py` covers ordinary drift but did not
  trigger this run.
- Tier 3 (PR-6 multi-book smoke): 2026-04-24 — **1/1 green (8m16s)**
  on the first clean PR-6 run under subscription auth.
  `tests/smoke/test_multi_book_smoke.py` seeds a second book
  (`tiny-apothecary`) alongside the fixture's `tiny-inquisitor`, adds
  a legal-earlier sibling chapter (1521-12-01) and an illegal-future
  sibling (1521-12-08) carrying a distinctive "SPOILER_MARKER"
  phrase, then runs `/autonovel:draft 1 --book tiny-inquisitor`
  (story_time 1521-12-04). Assertions: draft is valid, drafted
  chapter does NOT contain the SPOILER_MARKER phrase (exclusion
  honoured), and the chapter never names Tommaso or Lucia as the
  arsonist (E-001 canonical consistency). The sanity layer shells
  out to `python -m autonovel.context_loader` first and fail-fasts
  if the loader itself returns the wrong gating. Runs on subscription
  auth under `@pytest.mark.smoke`. The real drafter did honour the
  exclusion — "Giraldo's burns smelled of saltpeter" did not leak
  from `tiny-apothecary/ch_02` (1521-12-08) into
  `tiny-inquisitor/ch_01` (1521-12-04).
- Tier 3 (PR-8 codex spot-check): 2026-04-24 — **1/1 green (52.11s)**
  on the first clean PR-8 run. `tests/smoke/test_codex_smoke.py` ran
  under subscription auth via Codex CLI 0.125 against the
  `tiny-series-historical` fixture. The test redirects
  `CODEX_HOME=<tmp>/.codex`, copies the user's real
  `~/.codex/auth.json` into the redirected home so subscription auth
  survives, installs the autonovel skills under
  `<tmp>/.codex/skills/autonovel/<stem>/SKILL.md`, then asks
  `codex exec --full-auto -C <fixture>` to invoke the
  `autonovel-gen-canon` skill end-to-end. Codex discovered the
  skill, ran the autonovel preamble (`autonovel _begin`), wrote
  `shared/canon.md` (≥3 bullets, ≥80 words), and ran the postamble
  (`autonovel _end --status ok`). End-to-end on the first attempt;
  no adapter changes required.
- Tier 3 (PR-8 gemini spot-check): not run — `gemini` CLI is not on
  PATH on this box. `tests/smoke/test_gemini_smoke.py` skips
  cleanly. The adapter ships with full Tier-1 coverage including a
  `tomllib.loads` round-trip on every emitted `.toml`; Tier-3
  validation is parked for whenever a Gemini-CLI box is available
  (PR 9 release polish is a natural pairing).
- Tier 3 (PR-7 typeset smoke): 2026-04-24 — **1/1 green (72.65s)**
  on the first clean PR-7 run under subscription auth. `tectonic`
  was not installed on the test box, so the optional PDF assertion
  was skipped per the conditional in
  `tests/smoke/test_typeset_smoke.py`; the
  `chapters_content.tex` build (mechanical.latex inside a real
  Claude Code session) and the `@TITLE@` / `@AUTHOR@` substitution
  in the per-book `novel.tex` were both exercised end-to-end.
  Re-run with `tectonic` on PATH to extend coverage to the
  produced PDF: `pytest tests/smoke -q -m smoke -k typeset`.
- Tier 4 (Bells regression): 2026-04-24 — harness added and passing in
  "skip" mode. Activates once a human populates
  `tests/fixtures/bells-reference/` from the `autonovel/bells` branch.

## Running the smoke test manually

```bash
# One-time: log in once on your subscription (Claude Max / Team / Pro).
claude login

# Run all smoke tests. Uses your subscription auth — "free" against your plan.
pytest tests/smoke -q -m smoke

# Run just one (cheap iteration).
pytest tests/smoke -q -m smoke -k evaluate_chapter

# Run Tier-4 (Bells regression) only — skipped until fixture populated.
pytest tests/smoke -q -m "smoke and regression"

# Optional: exercise the API-key path instead (pay-per-token).
AUTONOVEL_SMOKE_USE_API_KEY=1 ANTHROPIC_API_KEY=sk-ant-... \
  pytest tests/smoke -q -m smoke
```

Each smoke test copies `tests/fixtures/tiny-series-historical/` to a
temp dir, installs the commands into `.claude/commands/` under that
copy, seeds whatever inputs the command needs (a drafted chapter, a
pre-written cuts file, a minimal brief), and invokes
`claude -p "/autonovel:<command> ..."`. Acceptance keys live in the
`<acceptance>` block of each command file.

## Open questions
- Tier-4 harness needs Bells chapters copied from the `autonovel/bells`
  branch before the LLM-judged drift check does useful work. Until
  then the harness passes trivially. Populating it is a standalone
  one-off, scoped to whenever a human next wants to gate the rewrite
  on Bells-parity.

## Resume pointer
See `ROADMAP.md` at project root — forward-looking todos and the PR-7
resume pointer live there. STATE.md keeps the append-only decisions
log and the "Tests last known green" line. Keeping them separate means
a `/clear` leaves the roadmap intact without the decisions-log
noise.
