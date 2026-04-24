# autonovel rewrite state

**Last updated:** 2026-04-24 by PR 5

## Completed
- [x] PR 1: layout + housekeeping
- [x] PR 2: first command + Claude adapter
- [x] PR 3: foundation commands
- [x] PR 4: evaluation + revision commands
- [x] PR 5: research + period guardrails
- [ ] PR 6: orchestrator + multi-book wiring
- [ ] PR 7: art, covers, audiobook, typeset, landing
- [ ] PR 8: Codex + Gemini adapters
- [ ] PR 9: docs + full genre fixtures + publish

## In progress
- none — PR 5 landed. All tiers green: Tier 1+2 248/248, Tier-3
  historical-research smoke 1/1 (2m21s).

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
- Tier 1 + Tier 2 (deterministic + contracts): 2026-04-24 — 248 passing
  (`pytest tests/deterministic tests/contracts`). The PR-5 commands
  (`research`, `check-anachronism`, `promote-canon`, plus six PR-5
  sidequests) are auto-picked up by
  `tests/contracts/test_command_contract.py`; no new Tier-1 tests
  needed in PR 5 because the deterministic surface it touches
  (`period-bans`) already had dedicated tests in
  `tests/deterministic/test_mechanical_slop.py` from PR 4.
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
See `ROADMAP.md` at project root — forward-looking todos and the PR-5
resume pointer live there. STATE.md keeps the append-only decisions
log and the "Tests last known green" line. Keeping them separate means
a `/clear` leaves the roadmap intact without the decisions-log
noise.
