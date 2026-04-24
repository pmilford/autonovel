# autonovel rewrite state

**Last updated:** 2026-04-24 by PR 1

## Completed
- [x] PR 1: layout + housekeeping
- [ ] PR 2: first command + Claude adapter
- [ ] PR 3: foundation commands
- [ ] PR 4: evaluation + revision commands
- [ ] PR 5: research + period guardrails
- [ ] PR 6: orchestrator + multi-book wiring
- [ ] PR 7: art, covers, audiobook, typeset, landing
- [ ] PR 8: Codex + Gemini adapters
- [ ] PR 9: docs + full genre fixtures + publish

## In progress
- none — PR 1 landed, awaiting human gate before PR 2.

## Blockers
- none

## Decisions log (append-only)
- 2026-04-24: Use `/autonovel:` namespace (REWRITE-PLAN.md §4; avoids `/gpd:` conflict).
- 2026-04-24: Model tiers abstract over provider; adapters pick specific models (§17).
- 2026-04-24: Installed in PR 1: series/book scaffolder, `.autonovel/` lifecycle
  (lock / checkpoints / command-log / last-action), next-step decision table,
  chapter frontmatter validator, `autonovel` CLI (`new-series`, `new-book`,
  `status`, `doctor`, `rollback`, `version`; `install`/`uninstall` are stubbed
  until PR 2).
- 2026-04-24: Templates ship inside the wheel under
  `src/autonovel/templates/{series,book}/`; scaffolder copies verbatim and then
  overlays `project.yaml` (via `project.dump`) and per-book `state.json`.
- 2026-04-24: Existing Python generators (`gen_world.py`, `draft_chapter.py`,
  `run_pipeline.py`, etc.) are **untouched** in PR 1. They continue to work on
  the old flat layout; deletion begins in PR 2 (`draft_chapter.py`) and PRs 3-7.

## Tests last known green
- Tier 1 (deterministic): 2026-04-24 — 49 passing (`pytest tests/deterministic`)
- Tier 2 (command contracts): n/a — introduced in PR 2
- Tier 3 (smoke): n/a — introduced in PR 2
- Tier 4 (Bells regression): n/a — introduced in PR 4

## Open questions
- none at the PR 1 level.

## Resume pointer for PR 2
1. Read `REWRITE-PLAN.md` §13 "PR 2" and §11 (adapter matrix) and §21.2 (preamble/postamble).
2. Write `commands/draft.md` with full frontmatter per §5.
3. Write `src/autonovel/adapters/base.py` + `claude_code.py` (Claude Code translation).
4. Implement `autonovel install --only claude` (replace the stub in
   `src/autonovel/cli.py::_cmd_install_stub`).
5. Add Tier-2 contract tests and a Tier-3 smoke test for `/autonovel:draft`.
6. Delete `draft_chapter.py`.
