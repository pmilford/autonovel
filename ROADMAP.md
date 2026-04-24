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
- [ ] **PR 9 — docs + full genre fixtures + publish** ← *next*

Each PR's full scope, acceptance, and human-gate policy lives in
`REWRITE-PLAN.md` §13.

## PR 9 — documentation, full genre fixture suite, publish

Resume pointer — read first:
1. `REWRITE-PLAN.md` §13 PR 9.
2. `REWRITE-PLAN.md` §12a — user-extensible genre fixtures.
3. `STATE.md` — the PR-8 decisions log entries explain what shipped
   and what each adapter still owes.

Carry-over notes from PR 8:
- Codex adapter targets `~/.codex/skills/autonovel/<stem>/SKILL.md`.
  REWRITE-PLAN §11 originally said `~/.codex/commands/`; the PR-8
  session updated it to match Codex CLI 0.125, which uses skills.
  PR 9 docs should reflect the current convention, not the original
  matrix.
- Gemini Tier-3 spot-check ships skipped (no `gemini` binary on the
  test box). The smoke test at `tests/smoke/test_gemini_smoke.py`
  follows the Codex shape; PR 9 should run it once on a Gemini-CLI
  box and either confirm the convention or adjust the adapter.
- PDF / ePub build path still depends on `tectonic` and `pandoc`
  being on PATH (carried from PR 7). PR 9 docs should add these to
  the install-requirements checklist.
- Art / cover / audiobook Tier-3 smoke tests are still not shipped —
  they require paid third-party APIs (fal.ai / ElevenLabs). Document
  the manual invocation path in PR 9.
- Token + usage-budget tracking is still not plumbed through. Natural
  home is PR 9 release polish.

Work items (per REWRITE-PLAN §13 PR 9):
1. Complete the eight shipped genre fixtures under `tests/fixtures/`
   with their per-genre smoke tests (§12).
2. `autonovel test-fixture new|list|run` housekeeping commands (§12a).
3. `docs/commands.md`, `docs/multi-book.md`, `docs/testing.md`,
   `docs/adding-a-genre-fixture.md`,
   `docs/writing-a-historical-series.md`.
4. Rewrite `README.md` with both install paths (npm -g and npx).
   Update `CLAUDE.md`; symlink `AGENTS.md` and `GEMINI.md`.
5. Delete any remaining Python legacy (`audiobook_voices.json` at
   repo root, etc. — see §18).
6. Tag `v0.1.0` and publish.

## Carry-over from earlier PRs (not PR-9 scope)

- **Bells Tier-4 fixture populate** (from PR 4). The harness at
  `tests/fixtures/bells-reference/` is scaffolded but empty; skips
  until a human copies chapters from the `autonovel/bells` branch
  and freezes `scores.json`. Should happen as part of PR 9
  release-polish if not before.
- **Token + usage-budget tracking** (from PR-5 session, deferred
  through PR 8). User wants the app/dev workflow to surface how many
  tokens a Tier-3 run consumed and an estimated $ cost, so future
  runs are priced before they happen. Natural home is PR 9 release
  polish.
- **Legacy README / WORKFLOW / CLAUDE.md references to
  `run_pipeline.py`** (noted during PR 6). Those files still describe
  the pre-rewrite Python orchestrator. PR 8 moved `PIPELINE.md` to
  `docs/pipeline-history.md` per §18. README/CLAUDE rewrite is still
  parked for PR 9 to keep diffs small.
- **Art / cover / audiobook Tier-3 smoke tests** (from PR 7). Only
  `test_typeset_smoke.py` shipped — the others need paid third-party
  APIs (fal.ai / ElevenLabs). PR 9 should document the manual
  invocation path rather than adding them to CI.
- **Spine-width for non-US trim sizes** (from PR 7). The mechanical
  spine calculator supports four paper stocks; `A5` / European
  royal-octavo trim is just a different `--trim-w` / `--trim-h`.
  PR 9 docs should enumerate the common presets.
