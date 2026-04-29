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
- none — PR 9 landed. Tier 1+2 456/456 green. `npm publish` itself
  is parked behind a human gate. Post-PR-9 author testing on
  Chromebook + WSL on Claude Max $200 surfaced 12 onboarding /
  reliability issues; 11 are fixed (commits 9207a55, 405930b,
  d5ceebb, 56d7734, 3851ac0, 79ebb99, 34098d0, plus this entry's
  lesson-recording commit), 1 is open. Full narrative in
  `docs/lessons-from-author-testing.md`; remaining open items in
  `FUTURE-TODOS.md`.

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
- 2026-04-28 (research at the front of the foundation — final
  step; FUTURE-TODOS Research entry): the third sub-item closes
  out the multi-step shipment. `commands/gen-world.md` step 3a
  and `commands/gen-canon.md` step 2a now read every populated
  `shared/research/notes/*.md` as primary source of truth, cite
  slug provenance in the world bible's Sources section, surface
  a one-line nudge to run `/autonovel:research --from-seed`
  when a period project has no research notes, and (gen-canon)
  preserve the `[research:<slug>]` citation tag through to
  canon bullets so promote-canon's tagged-survives-untagged
  conflict resolution stays correct (research entries beat
  draft-derived contradictions). New `tests/deterministic/
  test_research_at_front.py` adds 7 regression locks covering
  reads-declarations, body mentions, recovery-path nudges, and
  tag preservation. Tier 1+2: 1049 → 1056.
- 2026-04-28 (show-don't-tell pre-flight scanner; FUTURE-TODOS
  show-dont-tell entry): new helper
  `src/autonovel/mechanical/show_dont_tell.py` + slash-command
  `/autonovel:show-dont-tell` cast a wider net than the existing
  slop regex. Four pattern families: emotion-state
  (`<X> was/felt/seemed <emotion>` against ~50-word curated
  emotion list), interiority verbs (`knew`/`realised`/`thought`
  /`believed`/`wondered`/`hoped`/`feared`/`wished`/…),
  perception filters (`<Y> looked/sounded <adverb>` against
  curated filter-adverb list), narrator labels (`It was
  <emotion>`, `There was <emotion>`). Per-chapter table + per-
  line hits with snippets + density-per-1000 column. CLI
  subcommand `autonovel mechanical show-dont-tell`. The LLM-
  judge ratio scoring upgrade (direct/indirect/hybrid
  classification) is queued separately as a follow-up. 18
  Tier-1 tests + 5 contract pickups. Tier 1+2: 1026 → 1049.
- 2026-04-28 (series-arc score; FUTURE-TODOS series-arc entry):
  new helper `src/autonovel/mechanical/series_arc.py` + slash-
  command `/autonovel:series-arc` cross-book scoreboard for
  series with ≥2 books. Per-book completion (summary / eval /
  above-threshold + earliest/latest story_time), cross-book
  cast (characters in ≥2 books), backwards story-time jumps
  (chapters where story_time regresses — legitimate for
  flashbacks), unresolved threads (Threads opened with no
  Threads closed substring match later), composite arc score
  0-10 blending coverage + above-threshold fraction +
  story-time discipline penalty + unresolved-thread penalty.
  CLI subcommand `autonovel mechanical series-arc
  <series_root>`. LLM-judge upgrade for arc *quality* still
  queued. 16 Tier-1 tests + 5 contract pickups. Tier 1+2:
  1005 → 1026.
- 2026-04-28 (edit-imported manuscript mode Phase 1; FUTURE-TODOS
  edit-imported entry): new `autonovel import-book <name> --from
  <path>` CLI subcommand and `/autonovel:import-book` slash-
  command. Splits a directory of `*.md` files (one chapter per
  file) OR a single combined manuscript (split on `^# `, fallback
  `^## `, fallback whole file). `--split-on '<regex>'` overrides.
  Strips pre-existing frontmatter, writes autonovel-shape
  `ch_NN.md` with `status: imported` + `imported_from:` for
  audit, flips `project.yaml :: books[].mode` to
  `edit-imported`. New `BookEntry.mode` field (default `draft`,
  omitted from YAML to keep existing files clean).
  `commands/draft.md` step 1a refuses to overwrite an
  edit-imported book without `--force`. Helper at
  `src/autonovel/import_book.py`. Phase 2 (foundation reverse-
  engineering from prose) still queued. 26 Tier-1 tests +
  contract pickups. Tier 1+2: 974 → 1005.
- 2026-04-28 (quality scanners — dialogue + period-register +
  pov-bleed): three pure-mechanical pre-flight scanners. All
  read-only, light-tier, run in milliseconds.
  (1) `mechanical/dialogue.py` flags adverb-heavy speech tags
  (`said quietly`), said-bookisms (`exclaimed`, `murmured`,
  `whispered`, …), and stutters (same non-said verb 3+ times in
  a 10-line window). Per-chapter counts + per-line snippets.
  Slash-command `/autonovel:dialogue`. 16 Tier-1 tests.
  (2) `mechanical/period_register.py` rolls the existing
  `slop.period_ban_hits` scanner across every chapter, emits
  per-chapter table + worst-offenders ranking. Slash-command
  `/autonovel:period-register`. 16 Tier-1 tests covering bans
  loading (comments / blanks), word-boundary matching,
  frontmatter strip, summary aggregation, render shapes, CLI.
  (3) `mechanical/pov_bleed.py` flags lines where a cast member
  who is NOT the chapter's POV is named with an interiority
  verb (`thought`, `felt`, `knew`, `realised`, `wondered`, …)
  or possessive interiority (`Niccolò's mind`, `Lucia's
  heart`). Reads `shared/characters.md` for cast (bullet or
  heading form). Output is a review list, not a gate. Slash-
  command `/autonovel:pov-bleed`. 19 Tier-1 tests.
  Doc sync in same commit per the keep-docs-in-sync rule:
  docs/commands.md (3 new rows), docs/operating-guide.md §0
  (3 new mechanical-helper rows), README.md (drafting/revision
  bucket gains the three pre-flight scanners), series-template
  CLAUDE.md "When in doubt" (3 new affordances). Tier 1+2:
  912 → 974.
- 2026-04-28 (reliability batch — drafter graceful-read +
  canon-vs-outline + `_begin` cwd banner + `--no-model-pin`):
  four small reliability fixes from the FUTURE-TODOS reliability
  group.
  (1) Drafter commands (draft / revise / draft-pass /
  revision-pass) gain explicit "Read-failure policy" preambles
  at the top of `<workflow>` — no retry on non-load-bearing
  reads, hard-stop only on revise's chapter-file read. Catches
  the 2026-04-25 retry-loop bug class.
  (2) `commands/evaluate.md` `--phase foundation` mode adds a
  new `canon_outline_consistency` dimension that emits a
  `canon_outline_conflicts` array naming every fact where canon
  and outline disagree.
  (3) `_cmd_begin` prints a `_begin: running from series root
  \`<name>\`` banner (or `(cwd: <relative>)` when launched from
  below the root) so wrong-cwd launches are visible up front.
  Two new Tier-1 tests.
  (4) New `autonovel install --no-model-pin` flag re-renders
  every command without the `model:` frontmatter field — recovery
  path for [1m]-session-model users whose per-command pin
  silently downshifts. ClaudeCodeAdapter.render gains
  `pin_model: bool = True`. Installer signature-inspects the
  adapter so Codex/Gemini stay no-op until they opt in. Three
  new Tier-1 tests. docs/troubleshooting.md gains both the
  "[1m] downshifting" entry and a tweak to the lock-flight
  recovery section. Tier 1+2: 907 → 912.
- 2026-04-28 (property-based tests via hypothesis; FUTURE-TODOS
  Property-Based-Tests entry): new
  `tests/deterministic/test_property_based.py` uses `hypothesis`
  (added under `[test]` extras in pyproject.toml) to generate
  random book layouts (chapter count 0-12, random POV/status/
  prose/score, summary/eval/motif/entity/pending-canon presence)
  and assert invariants across them: `iter_chapter_files` count
  equals chapter-count exactly (no `.summary.md` collisions),
  `_infer_phase` returns a known phase, `_next_step_for` always
  returns non-empty command + rationale with no unsubstituted
  placeholders, `enumerate_actions` priorities valid, summary /
  dashboard / entity-track / motif builders never crash on
  arbitrary layouts. Decision table tested independently of
  disk via PipelineState strategy. 10 properties × 25 examples
  = ~250 random layouts per run. docs/testing.md Tier-1 row
  updated. Tier 1+2: 897 → 907.
- 2026-04-28 (verify-writes auditor; FUTURE-TODOS Verify-Writes
  entry): postamble's `--wrote` flags are LLM self-reports — LLM
  can claim a write without invoking Write/Edit. New
  `checkpoints.verify_writes(cp, series_root, claimed)` returns
  a `WriteVerificationReport` with one item per claim and
  statuses created / modified / deleted / unchanged / missing /
  outside-checkpoint. `lifecycle.end` invokes it after lock
  release, surfaces `unchanged` and `missing` as warnings in
  the postamble footer (`⚠️ verify-writes:`) and records a
  one-line summary on the command-log entry's `note` field for
  audit. Paths with unresolved `{book}` placeholders or paths
  outside the checkpoint are classified `outside-checkpoint`
  (informational, not warnings). Doc sync in
  docs/troubleshooting.md. 13 new Tier-1 tests covering each
  status path + lifecycle integration + command-log audit
  trail. Tier 1+2: 884 → 897.
- 2026-04-28 (postamble compliance watchdog; FUTURE-TODOS
  Postamble Watchdog entry): `lock.acquire_with_takeover` gains
  `expire_after_seconds` parameter (default 30 min via
  `DEFAULT_LOCK_EXPIRE_SECONDS`). Any lock older than threshold
  is silently taken over at the next `_begin`, with the
  abandoned LockInfo surfaced via the existing
  `BeginResult.abandoned_lock` channel. Independent of PID
  liveness — catches the same-Claude-Code-session case where
  the LLM skipped `_end` (PID is still alive but the lock is
  stale anyway). Lock age comes from `started_at` ISO timestamp
  in the lock JSON, with mtime fallback when corrupted. New
  `is_expired(lock_path, max_age_seconds)` predicate.
  `expire_after_seconds=None` or `0` reverts to pre-2026-04-28
  PID-only behaviour. Doc sync in docs/troubleshooting.md
  "another command is already in flight" entry. 7 new Tier-1
  tests including end-to-end through `lifecycle.begin`. Tier
  1+2: 877 → 884.
- 2026-04-28 (structured summary queries; FUTURE-TODOS Summary
  Queries entry): new light-tier command `/autonovel:summaries
  [--book <name>] [--where '<expr>'] [--format markdown|json]`
  over a small mechanical query DSL. Supports `==/!=/<=/>=/</>`
  numeric/lexical compare on `pov`, `score`, `story_time`,
  `word_count`, `cast`, `plot`, `location`, `chapter`, `status`,
  plus `<field> contains <literal>`, `<field> in <num>..<num>`,
  and `and` / `or` / `not` / parenthesisation. Hand-written
  tokeniser + recursive-descent parser (no `eval()` — safer +
  user-friendly error messages naming the offending token).
  Helper at `src/autonovel/mechanical/summary_query.py` + CLI
  subcommand `autonovel mechanical summary-query <book_root>`.
  Distinct from `/autonovel:talk` by being free, scriptable,
  stable. 32 Tier-1 tests + 5 contract pickups. Tier 1+2:
  840 → 877.
- 2026-04-28 (per-book pacing/tension dashboard; FUTURE-TODOS
  Dashboard entry): new light-tier command `/autonovel:dashboard
  [--book <name>] [--threshold <float>] [--format markdown|json]`
  re-renders the latest `<ts>_full.json` eval log without firing
  another LLM evaluate. Augments with mechanical dimensions
  (cast size from summary, scene count from `***`/`---` markers,
  dialogue density from paragraph-opening `"`, motif density
  from motifs.md when present), ASCII sparklines (▁ to █) for
  score + tension, per-book aggregates (mean / median / range /
  stdev, longest sub-threshold streak), tension-drop alarms
  (≥3 consecutive declines) re-run from existing data. Helper
  at `src/autonovel/mechanical/dashboard.py` + CLI subcommand
  `autonovel mechanical dashboard <book_root>`. Output footer
  names per-column provenance. 32 Tier-1 tests + 4 contract
  auto-pickups. Tier 1+2: 803 → 840.
- 2026-04-28 (talk-with-the-book mode + named-entity tracker;
  FUTURE-TODOS Talk-mode entry): new heavy-tier command
  `/autonovel:talk --book <name> "<question or suggestion>"
  [--target <chapter>]`. Three modes classified from the user's
  prompt — **Q+A** (cites chapter+line, no edit pending),
  **Suggest-and-stage** (queues a structured turn in
  `books/{book}/briefs/conversation.md` for the next revise),
  **Mechanical+suggest** (calls `autonovel mechanical
  entity-track` first, then queues a cut-list grounded in the
  scan). The conversation log is append-only — each invocation
  reads the existing log + processes one new turn + appends a
  six-field block (`Question / suggestion`, `Mode`, `Target`,
  `Answer / suggestion`, `Status`). `commands/revise.md` step 3a
  reads the log and folds every queued turn with
  `Target: chapter <N>` into the brief; step 11 flips them to
  `Status: applied`. `commands/revision-pass.md` declares the
  same files in reads/writes so sweeps inherit the contract.
  New helper `src/autonovel/mechanical/entity_track.py` (the
  named-entity generalisation of `motifs.py`): per-book
  `entities.md` config first, fallback to `[shortname]` heads
  in `shared/canon.md`. CLI subcommand `autonovel mechanical
  entity-track <book_root>` and 13 Tier-1 tests covering the
  parse/scan/build/CLI paths. Tier 1+2: 785 → 803.
- 2026-04-28 (PDF page-header regression — two-bug fix; FUTURE-TODOS
  PDF entry): **Bug A**: `mechanical/latex.py::build_chapters_tex`
  read `lines[0]` of the post-frontmatter body as the chapter title;
  real chapter files (per `commands/draft.md`) have no `# Heading`
  line so `lines[0]` was the first sentence of prose, which became
  `\chapter{<sentence>}` and rendered as a large italic block at
  every chapter title page. Fix: new `_extract_chapter_title()`
  honours an optional `title:` frontmatter field, falls back to a
  real `# Heading` if present, otherwise emits empty `\chapter{}`
  so `\titleformat` prints `chapter <Roman>` alone. **Bug B**:
  even with the latex fix, in-flight series carry a stale
  `<series-root>/typeset/novel.tex` from before the 2026-04-25
  running-header fix (`autonovel install` doesn't refresh typeset
  templates). New `autonovel refresh-templates [--only typeset]
  [--dry-run]` housekeeping subcommand re-copies package templates
  over the live series, preserves local-only files, reports
  updated / unchanged / preserved-extra. Default is `typeset/`
  only. Operating-guide §3b updated. 11 new Tier-1 tests (2
  latex regression + 9 refresh-templates); Tier 1+2: 774 → 785.
- 2026-04-28 (per-chapter art prompts as first-class artifacts;
  FUTURE-TODOS #3): new light-tier command `/autonovel:art-prompts
  --book <name> [--chapters <range>] [--surface
  ornament|plate|scene-break] [--style lineart|full|symbolic]
  [--force]` writes one markdown prompt file per chapter at
  `books/{book}/art/prompts/ch{NN:02d}_{surface}.md` (sections:
  Motif, Rationale, Prompt, Universal constraints, Style, Source
  inputs). Built from outline + summary + visual_style.json +
  world cues — outline + summary name the turning point, which
  is a richer motif source than the first 400 words of prose.
  No image provider call. `commands/art-ornaments-all.md`
  updated: declares the prompts dir under `reads:`, prefers the
  authored `## Prompt` body verbatim when present, falls back to
  inline derivation when missing. Hand-edit target for the
  prompts; also the right input for a different generator
  (Midjourney, ComfyUI, a commissioned artist). 5 contract test
  auto-pickups for the new command; Tier 1+2: 769 → 774.
- 2026-04-28 (per-chapter motif tracker; FUTURE-TODOS #22): new
  mechanical helper `src/autonovel/mechanical/motifs.py` reads
  per-book `motifs.md` (bullet shape `- slug: kw1, kw2, kw3`),
  strips YAML frontmatter from each chapter before counting,
  matches keywords on word boundaries case-insensitively, emits
  a per-chapter markdown table (zero-hit cells `·`). Back-half
  drop warnings fire only when the motif was used at least once
  in the front half — silent for declared-but-never-used motifs
  (avoids noise). Books under 4 chapters skip warning logic.
  CLI subcommand `autonovel mechanical motifs <book_root>` and
  slash-command `/autonovel:motifs` (light tier, pure mechanical).
  17 new Tier-1 tests + 5 contract auto-pickups for the new
  command. Tier 1+2: 747 → 769.
- 2026-04-28 (pipx-isolated install Tier-3 test; FUTURE-TODOS #5.3):
  new file `tests/smoke/test_pipx_install.py` builds a wheel via
  `pipx install <repo>` against an isolated `PIPX_HOME` /
  `PIPX_BIN_DIR`, falling back to `python -m pipx` when the binary
  isn't on `$PATH`. Exercises the CLI surfaces that historically
  break under wheel packaging — `--help`, `_next-actions --help`,
  `mechanical slop --help`, `_promote-canon --help`, plus an
  end-to-end `new-series` + `doctor` round-trip (the strongest
  check for `templates/` packaging). Marked `smoke +
  pipx_install` so it can be excluded with
  `-m "smoke and not pipx_install"`. Adds a `pipx_install`
  marker registration to `pyproject.toml`.
- 2026-04-28 (multi-stage pipeline integration tests; FUTURE-TODOS
  #5.2): new file
  `tests/deterministic/test_integration_pipeline.py` walks the
  seams that unit-tested-in-isolation commands miss — foundation
  chain → first-draft → evaluate → advance/revise; low-score →
  revise → re-eval → advance; pending-canon gate (real
  `promote_canon.promote` round-trip releases the gate); situational
  `next_actions.enumerate_actions` shifts across pipeline stages;
  canonical pipeline action surfaces at the bottom of the
  `/autonovel:next` output; eval-score indexer resolves all three
  production naming conventions in a single test. 7 new Tier-1
  tests; Tier 1+2: 740 → 747.
- 2026-04-28 (realistic late-stage fixtures + lifecycle bug fix;
  FUTURE-TODOS #5.1): two new conftest fixtures —
  `mid_revision_book` (8 chapters, ch02+ch03 below threshold with
  briefs written, deliberately stale panel report) and
  `review_phase_book` (10 chapters above threshold, panel +
  review newer than every chapter). New test file
  `tests/deterministic/test_state_machine_realistic.py` runs
  `iter_chapter_files`, `_infer_phase`, `_next_step_for`, and
  `next_actions.enumerate_actions` against each shape (parametrised
  where invariants apply across all three). The realistic-fixture
  pass found a real bug in `lifecycle._last_eval_score`: glob
  `ch{NN}*.json` only matched plain `chNN_eval.json`, missing the
  timestamped `<ts>_chNN.json` form `evaluate.md` writes — so
  after `/autonovel:evaluate --chapter N` the next-step inference
  saw no score and looped on evaluate. Helper now delegates to
  `mechanical.chapter_summary._index_latest_per_chapter_eval` which
  already handles all three production naming conventions. 17 new
  Tier-1 tests. Tier 1+2: 723 → 740.
- 2026-04-28 (`/autonovel:next` made dynamic; FUTURE-TODOS #2):
  state-aware action enumerator at
  `src/autonovel/housekeeping/next_actions.py`. Inspects live
  filesystem for HIGH (pending-canon conflicts, chapter
  regressions ≥0.3 below prior best across timestamped /
  non-timestamped eval-log naming), MEDIUM (reader-panel +
  Opus-review staleness vs chapter mtimes; git backup state —
  no repo / no remote / uncommitted / unpushed), LOW (typeset
  `<book>_latest.pdf` staleness, missing book title or author,
  missing preface/introduction once ≥3 chapters drafted).
  Hidden subcommand `autonovel _next-actions [--book <name>]
  [--format human|json]` invokes it; `commands/next.md`
  rewrites the body to call the helper and print verbatim.
  Last-action.json's `next_standard_step` still surfaces — but
  as the lowest-priority "canonical pipeline next step" line at
  the bottom, so situational state always wins. 27 new Tier-1
  tests (`tests/deterministic/test_next_actions.py`) cover each
  per-book check, three git-backup states, canonical-action
  lookup with book filtering, the human render's priority
  grouping, and CLI round-trips. Tier 1+2: 696 → 723.
- 2026-04-26 (live-novel session, second wave): a long author-test
  day on the live novel surfaced concrete gaps; everything below
  shipped on master between 2026-04-25 PM and 2026-04-26 PM.
  Tier 1+2: 451 → 674.
  - **Quality dimensions for the brief→revise loop.** Four named
    ceiling fixes from CLAUDE.md's "production gotchas" list ship
    as a stack: (1) per-book Custom rubric in voice.md Part 3,
    read by evaluate / reader-panel / brief / draft / revise so
    book-specific scoring rules don't have to live in repo-shared
    command files; (2) per-character voice fingerprints in
    voice.md Part 4, auto-drafted by voice-discovery when the
    cast is ≥3, applied at every dialogue line and POV interiority;
    (3) `irreversible_change` evaluate dimension (per chapter) +
    `irreversible_change_arc` (whole book, with `cuttable_chapters`
    list), with brief.md's new `## Stability check` section
    forbidden from vague "raise stakes" prescriptions; (4) per-
    scene `beat_coverage` (goal / conflict / disaster-or-decision
    / consequence) backed by a new `autonovel mechanical scenes`
    helper, with brief.md's new `## Weak scenes` section naming
    the scene by index + opening line.
  - **voice.md upgrade path.** voice-discovery gains a `--upgrade`
    flag: preserves Parts 1+2 verbatim while appending Part 3
    placeholder and drafting Part 4. Safe rollout for existing
    books without re-running foundation.
  - **Late research → light integration.** Both /autonovel:brief
    and /autonovel:revision-pass gain `--enrich-with <research-
    notes-path>`. The brief reads the research notes,
    identifies which scenes the research is relevant to, adds an
    `## Enrichment from research` block with 1–2 specific period
    details per relevant scene and explicit "do NOT change plot,
    dialogue, voice, structure" guards. Chapters where the
    research doesn't fit get briefs without the block — the
    research is a brush, not a chisel.
  - **Per-chapter promote-canon in revision-pass.** Mirrors the
    aea1511 fix from draft-pass: each chapter's revise discoveries
    land in shared/canon.md before the next chapter's revise
    reads canon. Without it, an early-chapter revise that
    clarified a fact would re-introduce the inconsistency in
    chapter N+1.
  - **promote-canon postamble + conflict-block clarity.** Two
    user-confusion fixes shipped together. Conflict blocks
    written back to `pending_canon.md` now carry a mandatory
    HTML-comment instruction block at the top with three
    labelled resolution paths (accept / reject / both wrong),
    and each `## Conflict N` block names the file path the
    contradicting line lives in. Postamble names the next
    command explicitly per case (supersedure → revision-pass on
    the affected chapter; conflicts → open the pending file's
    instruction block; plain success → /autonovel:next).
    revision-pass is the default recommendation even for a
    single chapter — `revision-pass --chapters NN` does the
    whole loop in one command.
  - **Typeset bug-cluster fix.** Three bugs reported against
    the live PDF/ePub build: (1) ePub contaminated with summary
    file content (`ch_*.md` glob matched both prose and
    `ch_NN.summary.md`) — fixed by new `build_epub_md` helper
    enumerating via `iter_chapter_files()`; (2) PDF leaked YAML
    frontmatter into chapter prose because `latex.py` parsed
    `lines[0]` as the title — fixed by shared
    `strip_yaml_frontmatter()` helper; (3) running header
    cascaded into italicised chapter-prose-looking content —
    fixed by switching recto to `\textsc{Chapter \thechapter}`
    (Roman numeral, no chapter-title state). Plus replaced
    fragile `sed -i 's/@TITLE@/.../'` with Python helper
    `render_novel_tex` (sed silently breaks on titles
    containing `/`, `&`, `\`).
  - **Dated typeset filenames.** PDF/ePub now write
    `<book>_<YYYYMMDD>_<HHMM>.{pdf,epub}` per build (kept) plus
    `<book>_latest.{pdf,epub}` overwritten on each successful
    build. Failed tectonic runs leave the partial novel.pdf in
    place but do NOT update the timestamped or latest names.
  - **Title + author management.** New `/autonovel:title`
    command (light) with three modes: propose (5 title + 3
    author candidates from outline/seed), pick (commits a
    proposal), set (explicit values). `BookEntry` schema gains
    optional `title` / `subtitle` / `author` fields; series-
    level `author` field also added (book inherits from series).
    Display-resolution helpers `BookEntry.display_title()` /
    `display_author()` codify the fallback chain. Backwards-
    compatible: existing project.yaml files load cleanly.
  - **Front matter (preface + introduction).** New
    `/autonovel:introduction` command (heavy) with `--from
    user|auto|both`. Scaffolds `books/<book>/preface.md`
    (hand-authored — the AI explicitly does NOT fill the
    bracketed placeholders) and/or AI-generates
    `books/<book>/introduction.md` (~600–1200 words, essay-form,
    grounded in the book's themes; never reveals plot past the
    inciting incident). Both auto-included in typeset's PDF
    front matter (via new `build_front_matter_tex` helper +
    `\IfFileExists{front_matter.tex}` guard in novel.tex) and
    ePub front matter (pandoc invocation gains optional preface +
    introduction args).
  - **`/autonovel:chapter-summary` command.** Pure-mechanical
    one-line-per-chapter overview table: Ch | Date | POV | Sco |
    Words | Cast | Plot (with `**Location** —` prefix when the
    summary carries the new Location field). Pulls structured
    fields from chapter frontmatter, summary.md, and the latest
    eval log. The right tool for "which chapters happen in
    <date range>?" or "where does <character> appear?" — scan
    the relevant column instead of grepping prose.
  - **Chapter summary template gains `**Location:**`** as the
    first field, paired with Plot. Updated in draft.md step 12
    and summarize-chapter.md step 6. revise.md step 9 was the
    one path that drifted (had a stale inline list); commit
    3ba469a fixed it by replacing the inline list with a real
    DRY reference to draft step 12.
  - **Score-delta surfacing in revision-pass.** Per-chapter line
    now ends with `eval: <prev> → <new> (Δ ±X.X) | canon: +<P>`
    so writers see whether a revise actually moved the chapter
    or regressed it. End-of-sweep summary table column is
    `prev → new (Δ)`; headline assessment is required to call
    out regressions explicitly.
  - **Statusline: context-% from `data["context_window"]`.**
    Reads the nested object Claude Code sends (where the value
    is **remaining** %, converted to used at the read site).
    Five new schema paths covered (remaining_pct +
    percentage_remaining + percent_remaining + remaining_percentage
    + the legacy `usage.context_pct`). Plus an opt-in debug
    dump under `AUTONOVEL_STATUSLINE_DEBUG=1` writing
    `~/.autonovel-statusline-debug.log` for diagnosing future
    schema drift.
  - **Comprehensive series .gitignore + GitHub backup
    walkthrough** (operating-guide §3e.1). Excludes `.autonovel/
    checkpoints/`, audiobook MP3s, timestamped typeset builds;
    KEEPS `<book>_latest.{pdf,epub}` so a fresh `git clone` of
    a backup carries usable artefacts. Doc walkthrough explicitly
    notes that the autonovel codebase being on GitHub does NOT
    back up the user's book — the two are separate dirs.
  - **`requires-python` lowered 3.12 → 3.11.** Conservative pick
    at PR-1 time; audit confirmed no 3.12-only features in
    runtime source. Matches Debian 12 / WSL Ubuntu 22.04+ system
    Python. README install step gains a `pipx install '.[export]'
    --python python3.13` callout for users whose default `python3`
    is older.
  - **Operating-guide §0 "How the editing commands relate".**
    Single-most-asked confusion after a first-pass draft. Four-
    role table (atomic / sweep / whole-book reviewer /
    mechanical helper), per-command table, ASCII call-graph,
    explicit Q&A for the "I ran draft-pass --all then review
    then reader-panel — did I need to run brief?" case (no, but
    you're not done — your next move is revision-pass --chapters
    <flagged>). README's command list also gained the new
    commands (`chapter-summary`, `title`, `introduction`).
- 2026-04-25 (PR 9 author-testing follow-ups): twelve onboarding /
  reliability issues surfaced during a real first-run on Chromebook
  + WSL on Claude Max $200/month. Eleven fixed across commits
  `9207a55` (README rewrite), `405930b` (seed.txt template +
  time/effort guidance), `d5ceebb` (series-root callout),
  `56d7734` (series CLAUDE.md + AGENTS/GEMINI symlinks),
  `3851ac0` and `79ebb99` (1M-context docs and reframed to
  recommend `/extra-usage`), `79ebb99` again (next-step phase
  inferred from filesystem; postamble strengthened to **Mandatory**),
  `34098d0` (foundation chained in canonical order via
  `_foundation_gap`; populated-marker list extended to cover
  Seeded by / Filled by / Leave empty until then), and the present
  commit (lessons doc + cross-links). Open: per-command `model:`
  override on `[1m]` session models — see FUTURE-TODOS.md and the
  open question in `docs/lessons-from-author-testing.md` §8.
  Tier 1+2: 451 → 456.
- 2026-04-24 (PR 9 fixup): `audiobook_voices.json` had a second job
  beyond being a deletion target — it was the **shape reference** a
  user comparing against `voices.yaml` would consult. Restored as
  `src/autonovel/templates/book/audiobook/voices.yaml.example` so
  `autonovel new-book` ships an example next to where
  `/autonovel:audiobook-voices` writes the live file. The Bells voice
  metadata (`description`, `why` audit fields) is preserved verbatim;
  only the format changed JSON → YAML. `commands/audiobook-voices.md`
  now declares the example file under `reads:` and the body explains
  the shape contract for round-tripping.
- 2026-04-24 (PR 9): legacy root files deleted —
  `WORKFLOW.md` (replaced by `docs/writing-a-historical-series.md`),
  `audiobook_voices.json` (functional replacement: per-book
  `books/{book}/audiobook/voices.yaml` written by
  `/autonovel:audiobook-voices`; reference shape: see fixup entry
  above for `voices.yaml.example`),
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
- Tier 1 + Tier 2 (deterministic + contracts): 2026-04-28 — **1056
  passing** (`pytest tests/deterministic tests/contracts`).
  FUTURE-TODOS #1 added 22; #2 added 27; #5.1 added 17 (and fixed
  a real lifecycle._last_eval_score glob bug along the way); #5.2
  added 7; #22 (per-chapter motif tracker) added 17 + 5 contract
  pickups; #3 (`/autonovel:art-prompts`) added 5 contract pickups
  for the new slash-command. PDF page-header regression fix added
  2 latex regression tests + 9 `autonovel refresh-templates`
  tests. Talk-mode added 13 entity-track tests + 5 contract
  pickups for `/autonovel:talk`.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-04-26 — **674
  passing** (`pytest tests/deterministic tests/contracts`). The
  2026-04-25 PM and 2026-04-26 waves added 223 tests across the
  scene splitter (14), shared frontmatter helper (6), ePub
  combiner (12), front-matter builder (12), typeset helpers (16),
  per-book metadata (9), chapter-summary helper (16 + 5 contract),
  statusline debug-capture + context-% paths (5), plus the
  Tier-2 contract auto-pickups for the new commands
  (`title`, `introduction`, `chapter-summary`).
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
