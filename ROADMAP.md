# autonovel rewrite roadmap

Forward-looking todos and the next-PR resume pointer. Companion to
`STATE.md` (append-only decisions log + test status) and
`REWRITE-PLAN.md` (the full technical spec).

## PR sequence — status at a glance

- [x] PR 1 — foundation: repo layout, project.yaml, housekeeping CLI
- [x] PR 2 — first command + installer adapter (Claude Code only)
- [x] PR 3 — foundation commands
- [x] PR 4 — evaluation + revision commands
- [x] PR 5 — research + period guardrails
- [x] PR 6 — orchestrator + multi-book wiring
- [x] PR 7 — export: art, covers, audiobook, typeset, landing
- [x] PR 8 — Codex + Gemini adapters
- [x] PR 9 — docs + full genre fixtures + publish prep
- [ ] **publish: tag v0.1.0 + `npm publish` + `pipx install` from PyPI** ← *human gate*

Each PR's full scope, acceptance, and human-gate policy lives in
`REWRITE-PLAN.md` §13.

## What landed in PR 9

- Eight genre fixtures complete under `tests/fixtures/tiny-series-*/`
  (historical from PR 5; scifi, literary, mystery, thriller, romance,
  fantasy, horror added in PR 9), each with a paired `tests/smoke/`
  test asserting one §12 genre-characteristic property.
- `autonovel test-fixture new|list|run` shipped with 11 new Tier-1
  tests; total Tier-1+2 went 440 → 451.
- Docs: `docs/commands.md`, `docs/multi-book.md`, `docs/testing.md`,
  `docs/adding-a-genre-fixture.md`,
  `docs/writing-a-historical-series.md`. Pre-rewrite `program.md`
  moved to `docs/program-history.md`.
- README rewritten for npm + npx + pipx install paths. CLAUDE.md
  rewritten as the agent-side conventions file; AGENTS.md and
  GEMINI.md symlink to it.
- npm shape scaffolded — `package.json` + `bin/autonovel.js` shim
  forwards to `python -m autonovel.cli`. Real `npm publish` is a
  separate human gate.
- Legacy root files deleted: `WORKFLOW.md`, `audiobook_voices.json`,
  `main.py`, repo-root `world.md` / `characters.md` / `outline.md` /
  `canon.md` / `voice.md` / `MYSTERY.md` / `state.json` /
  `results.tsv` / `chapters/`. `.env.example` cleaned of
  legacy-Python language.

## What is NOT in PR 9 (publish gate)

The actual `npm publish` and `pipx install autonovel` from PyPI
require:

1. A human verifying `npx autonovel install` works on a clean box
   (no pre-existing pipx env).
2. Choosing the `autonovel` PyPI / npm names (squat-checked).
3. Tagging `v0.1.0`, running `python -m build`, `twine upload`,
   and `npm publish`.

These are reversible only by yanking; do them once, do them right.
See FUTURE-TODOS.md "Real `npm publish` flow".

## Forward-looking todos

Promoted from this file to its own home so a freshly cleared session
has one obvious place to look:

→ [`FUTURE-TODOS.md`](FUTURE-TODOS.md) — output writing quality,
reader interest, maintenance, portability, testing.
