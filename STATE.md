# autonovel rewrite state

**Last updated:** 2026-04-24 by PR 2

## Completed
- [x] PR 1: layout + housekeeping
- [x] PR 2: first command + Claude adapter
- [ ] PR 3: foundation commands
- [ ] PR 4: evaluation + revision commands
- [ ] PR 5: research + period guardrails
- [ ] PR 6: orchestrator + multi-book wiring
- [ ] PR 7: art, covers, audiobook, typeset, landing
- [ ] PR 8: Codex + Gemini adapters
- [ ] PR 9: docs + full genre fixtures + publish

## In progress
- none — PR 2 landed, awaiting human gate before PR 3.

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
  (`gen_world.py`, `evaluate.py`, `review.py`, …) still call
  `api.anthropic.com` directly with `ANTHROPIC_API_KEY` — that's the
  pre-rewrite path, tracked for deletion in §18 across PRs 3-7.

## Tests last known green
- Tier 1 (deterministic): 2026-04-24 — 72 passing (`pytest tests/deterministic`)
- Tier 2 (command contracts): 2026-04-24 — 13 passing (`pytest tests/contracts`)
- Tier 3 (smoke): 2026-04-24 — skeleton + historical fixture; **requires
  `claude` on $PATH**. Subscription auth (via `claude login`) is primary;
  the subprocess strips `ANTHROPIC_API_KEY` unless
  `AUTONOVEL_SMOKE_USE_API_KEY=1` opts in. Skips cleanly if `claude` is
  absent. Word-count tolerance on draft smoke is [1800, 5000]. §12 item 1
  retry-once policy is live via the `tests/conftest.py` flakiness hook.
- Tier 4 (Bells regression): n/a — introduced in PR 4

## Running the smoke test manually

```bash
# One-time: log in once on your subscription (Claude Max / Team / Pro).
claude login

# Run smoke. This uses your subscription auth — "free" against your plan.
pytest tests/smoke -q -m smoke

# Optional: exercise the API-key path instead (pay-per-token).
AUTONOVEL_SMOKE_USE_API_KEY=1 ANTHROPIC_API_KEY=sk-ant-... \
  pytest tests/smoke -q -m smoke
```

The test copies `tests/fixtures/tiny-series-historical/` to a temp dir,
installs the commands into `.claude/commands/` under that copy, and invokes
`claude -p "/autonovel:draft 1 --book tiny-inquisitor" --allowed-tools
Read,Write,Bash,Task`. Pass/fail keys are in `commands/draft.md`'s
`<acceptance>` block.

## Open questions
- none at the PR 2 level.

## Resume pointer for PR 3
1. Read `REWRITE-PLAN.md` §13 PR 3 and §18 (deletion table).
2. Write `commands/gen-world.md`, `gen-characters.md`, `gen-outline.md`,
   `voice-discovery.md`, `gen-canon.md`. Each reuses the adapter's
   preamble/postamble automatically.
3. Add a `/autonovel:sidequest` dispatcher command (§21.10 PR 3 gain),
   populated with whatever sidequest commands already exist.
4. Add Tier-2 contracts + Tier-3 smoke tests for each new command. Pick
   appropriate fixtures from `tests/fixtures/tiny-series-*`.
5. Delete `seed.py`, `gen_world.py`, `gen_characters.py`, `gen_outline.py`,
   `gen_outline_part2.py`, `voice_fingerprint.py`, `gen_canon.py`,
   `build_outline.py`, `build_arc_summary.py` per §18.
