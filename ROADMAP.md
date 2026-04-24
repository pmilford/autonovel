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
- [ ] **PR 6 — orchestrator + multi-book wiring** ← *next*
- [ ] PR 7 — export: art, covers, audiobook, typeset, landing
- [ ] PR 8 — Codex + Gemini adapters
- [ ] PR 9 — docs + full genre fixtures + publish

Each PR's full scope, acceptance, and human-gate policy lives in
`REWRITE-PLAN.md` §13.

## PR 6 — orchestrator and multi-book wiring

Resume pointer — read first:
1. `REWRITE-PLAN.md` §13 PR 6.
2. `REWRITE-PLAN.md` §8 (`shared/events.md` format).
3. `REWRITE-PLAN.md` §21.8 — `reorder` and `remove-chapter`
   sidequests fold in here because they need the multi-book / story-
   time machinery.

Work items:
1. `commands/run-pipeline.md` — the /autonovel:run-pipeline entry
   that replaces `run_pipeline.py`.
2. `src/autonovel/context_loader.py` — helper that, given a
   `(book, chapter)` pair, returns the right files respecting
   `story_time` (no spoilers from chapters the POV has not yet
   lived through).
3. `shared/events.md` schema + validator under
   `src/autonovel/validators/`.
4. Sidequests: `/autonovel:reorder` and `/autonovel:remove-chapter`;
   update `commands/sidequest.md`.
5. Tier-3 multi-book smoke test: two books with interleaved story
   times draft both and verify no contradiction of canonical
   events.
6. Delete `run_pipeline.py` and `run_drafts.py`; the dangling
   references from PRs 3 and 4 get removed here (§18).

## Carry-over from earlier PRs (not PR-6 scope)

- **Bells Tier-4 fixture populate** (from PR 4). The harness at
  `tests/fixtures/bells-reference/` is scaffolded but empty; skips
  until a human copies chapters from the `autonovel/bells` branch
  and freezes `scores.json`. Independent of PR 6 — can happen any
  time before PR 9 release-polish.
- **Token + usage-budget tracking** (from PR-5 session). User wants
  the app/dev workflow to surface how many tokens a Tier-3 run
  consumed and an estimated $ cost, so future runs are priced before
  they happen. Not yet in any PR's scope; candidate for PR 8 (adapter
  work) or PR 9 (release polish). File under open-questions below
  until planned.
