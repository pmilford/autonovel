# autonovel rewrite state

**Last updated:** 2026-04-24 by PR 3

## Completed
- [x] PR 1: layout + housekeeping
- [x] PR 2: first command + Claude adapter
- [x] PR 3: foundation commands
- [ ] PR 4: evaluation + revision commands
- [ ] PR 5: research + period guardrails
- [ ] PR 6: orchestrator + multi-book wiring
- [ ] PR 7: art, covers, audiobook, typeset, landing
- [ ] PR 8: Codex + Gemini adapters
- [ ] PR 9: docs + full genre fixtures + publish

## In progress
- none — PR 3 landed, auto-merge on green per §13 PR 3 (optional human gate).

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

## Tests last known green
- Tier 1 + Tier 2 (deterministic + contracts): 2026-04-24 — 124 passing
  (`pytest tests/deterministic tests/contracts`). The new foundation
  commands are auto-picked up by the parametrized contract tests in
  `tests/contracts/test_command_contract.py`, so no per-command test
  code was needed at that tier.
- Tier 3 (smoke): 2026-04-24 — `tests/smoke/test_foundation_smoke.py`
  adds six new smoke tests (`gen_world`, `gen_characters`, `gen_outline`,
  `voice_discovery`, `gen_canon`, `sidequest_menu_is_read_only`). All
  gated on `claude` on PATH; subscription auth is primary. Not yet
  exercised end-to-end in CI; manual run recommended once before PR 4.
- Tier 4 (Bells regression): n/a — introduced in PR 4.

## Running the smoke test manually

```bash
# One-time: log in once on your subscription (Claude Max / Team / Pro).
claude login

# Run all smoke tests. Uses your subscription auth — "free" against your plan.
pytest tests/smoke -q -m smoke

# Run just one (cheap iteration).
pytest tests/smoke -q -m smoke -k gen_world

# Optional: exercise the API-key path instead (pay-per-token).
AUTONOVEL_SMOKE_USE_API_KEY=1 ANTHROPIC_API_KEY=sk-ant-... \
  pytest tests/smoke -q -m smoke
```

Each smoke test copies `tests/fixtures/tiny-series-historical/` to a
temp dir, installs the commands into `.claude/commands/` under that copy,
resets the relevant write target to the template placeholder, and invokes
`claude -p "/autonovel:<command> ..."`. Acceptance keys live in the
`<acceptance>` block of each command file.

## Open questions
- none at the PR 3 level.

## Resume pointer for PR 4
1. Read `REWRITE-PLAN.md` §13 PR 4 and §18 (deletion table).
2. Extract mechanical-only regex logic from `evaluate.py` into
   `src/autonovel/mechanical/` as a pure Python module, with its own
   Tier-1 deterministic tests. The LLM-powered parts become the
   `/autonovel:evaluate` command.
3. Write `commands/evaluate.md`, `adversarial-edit.md`, `apply-cuts.md`,
   `reader-panel.md`, `review.md`, `brief.md`, `revise.md`,
   `compare-chapters.md`.
4. Add the §21.10 PR 4 sidequest commands: `shorten`, `lengthen`,
   `split-chapter`, `merge-chapters`, `revoice`. Update
   `commands/sidequest.md` to surface the new entries.
5. Add the Tier-4 "Bells regression" harness (§12 item 4) — compare
   `/autonovel:evaluate` scores against frozen reference scores from the
   Bells production run; fail if any chapter drifts more than 0.5 points.
6. Add Tier-2 contracts + Tier-3 smoke tests for each new command; reuse
   the `tests/smoke/test_foundation_smoke.py` pattern (reset target,
   run command, assert acceptance block).
7. Delete `evaluate.py`, `adversarial_edit.py`, `apply_cuts.py`,
   `reader_panel.py`, `review.py`, `gen_brief.py`, `gen_revision.py`,
   `compare_chapters.py` per §18.
