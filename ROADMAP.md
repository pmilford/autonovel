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
- [ ] **PR 7 — export: art, covers, audiobook, typeset, landing** ← *next*
- [ ] PR 8 — Codex + Gemini adapters
- [ ] PR 9 — docs + full genre fixtures + publish

Each PR's full scope, acceptance, and human-gate policy lives in
`REWRITE-PLAN.md` §13.

## PR 7 — export: art, covers, audiobook, typeset, landing

Resume pointer — read first:
1. `REWRITE-PLAN.md` §13 PR 7.
2. `REWRITE-PLAN.md` §18 — deletion table: `gen_art.py`,
   `gen_art_directions.py`, `gen_cover_composite.py`,
   `gen_cover_print.py`, `gen_audiobook_script.py`, `gen_audiobook.py`,
   `typeset/build_tex.py`, `landing/index.html` all land in PR 7.

Work items:
1. `commands/art-style.md`, `art-directions.md`, `art-curate.md`,
   `art-pick.md`, `art-ornaments-all.md`, `art-vectorize.md` with
   multi-provider hooks (fal.ai default, adapter layer).
2. `commands/cover-composite.md` and `cover-print.md` with output
   matrix (KDP, Lulu, Amazon thumbnail, social cards) + spine-width
   auto-calculator.
3. `commands/audiobook-script.md`, `audiobook-voices.md`,
   `audiobook-generate.md`, `audiobook-assemble.md` — multi-take +
   best-take LLM listener pass; chapter marks; emotion/tone tags.
4. `commands/typeset.md` — PDF + ePub from one command; keeps
   `typeset/novel.tex` and `typeset/epub_*` as templates.
5. `commands/landing.md` — responsive default template, og:image,
   twitter:card, structured-data markup, multi-book series nav.
6. `commands/package.md` — end-to-end release builder.
7. Tier-1 tests for mechanical bits (spine-width calc, script parser,
   chapter-mark stitching).
8. Tier-3 smoke tests per command — expensive (image gen, TTS), so
   manual-invoke only, not CI.

## Carry-over from earlier PRs (not PR-7 scope)

- **Bells Tier-4 fixture populate** (from PR 4). The harness at
  `tests/fixtures/bells-reference/` is scaffolded but empty; skips
  until a human copies chapters from the `autonovel/bells` branch
  and freezes `scores.json`. Independent of PR 7 — can happen any
  time before PR 9 release-polish.
- **Token + usage-budget tracking** (from PR-5 session). User wants
  the app/dev workflow to surface how many tokens a Tier-3 run
  consumed and an estimated $ cost, so future runs are priced before
  they happen. Not yet in any PR's scope; candidate for PR 8 (adapter
  work) or PR 9 (release polish).
- **Legacy README / WORKFLOW / PIPELINE / CLAUDE.md references to
  `run_pipeline.py`** (noted during PR 6). Those files still describe
  the pre-rewrite Python orchestrator. REWRITE-PLAN §18 parks the
  `PIPELINE.md` rename for PR 8 and the README/CLAUDE rewrite for
  PR 9; PR 6 left them as relics on purpose to keep the diff small.
