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
- [ ] **PR 8 — Codex + Gemini adapters** ← *next*
- [ ] PR 9 — docs + full genre fixtures + publish

Each PR's full scope, acceptance, and human-gate policy lives in
`REWRITE-PLAN.md` §13.

## PR 8 — Codex and Gemini adapters

Resume pointer — read first:
1. `REWRITE-PLAN.md` §13 PR 8.
2. `REWRITE-PLAN.md` §11 — the runtime adapter matrix.
3. `src/autonovel/adapters/claude_code.py` — the reference adapter.

Work items:
1. `src/autonovel/adapters/codex.py` — Codex (Open AI) adapter:
   tool-name map, target-path convention under `~/.codex/commands/`,
   render template.
2. `src/autonovel/adapters/gemini.py` — Gemini adapter:
   tool-name map, `~/.gemini/...` path, render template.
3. Update `installer.load_adapter` to dispatch on `codex` and
   `gemini`.
4. Per-runtime golden-file tests under `tests/deterministic/`.
5. Spot-check the `/autonovel:draft` smoke against each runtime and
   record the results (same pattern as PR 3's
   `test_foundation_smoke.py`).

Carry-over notes from PR 7:
- PDF / ePub build path depends on `tectonic` and `pandoc` being on
  PATH. Neither is bundled; Tier-3 smoke has a conditional PDF
  assertion. PR 9 docs should add these to the install-requirements
  checklist.
- Art / cover / audiobook Tier-3 smoke tests are *not* shipped —
  they require paid third-party APIs (fal.ai / ElevenLabs). Document
  the manual invocation path in PR 9.
- Token + usage-budget tracking is still not plumbed through. PR 7
  didn't change that; carried forward.

## Carry-over from earlier PRs (not PR-8 scope)

- **Bells Tier-4 fixture populate** (from PR 4). The harness at
  `tests/fixtures/bells-reference/` is scaffolded but empty; skips
  until a human copies chapters from the `autonovel/bells` branch
  and freezes `scores.json`. Independent of PR 8 — can happen any
  time before PR 9 release-polish.
- **Token + usage-budget tracking** (from PR-5 session). User wants
  the app/dev workflow to surface how many tokens a Tier-3 run
  consumed and an estimated $ cost, so future runs are priced before
  they happen. Not yet in any PR's scope; natural home is PR 8
  (adapter work) or PR 9 (release polish).
- **Legacy README / WORKFLOW / PIPELINE / CLAUDE.md references to
  `run_pipeline.py`** (noted during PR 6). Those files still describe
  the pre-rewrite Python orchestrator. REWRITE-PLAN §18 parks the
  `PIPELINE.md` rename for PR 8 and the README/CLAUDE rewrite for
  PR 9; PR 6 left them as relics on purpose to keep the diff small.
- **Art / cover / audiobook Tier-3 smoke tests** (from PR 7). Only
  `test_typeset_smoke.py` shipped — the others need paid third-party
  APIs (fal.ai / ElevenLabs). PR 9 should document the manual
  invocation path rather than adding them to CI.
- **Spine-width for non-US trim sizes** (from PR 7). The mechanical
  spine calculator supports four paper stocks; `A5` / European
  royal-octavo trim is just a different `--trim-w` / `--trim-h`.
  PR 9 docs should enumerate the common presets.
