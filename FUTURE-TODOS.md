# Future todos

Items that are out of PR-9 scope but worth recording so a future
session can pick them up. Companion to `ROADMAP.md` (PR sequence),
`STATE.md` (decisions log), and `docs/lessons-from-author-testing.md`
(narrative explanation of *why* certain defensive shapes exist).

The list is rough on purpose — each entry is a one-line reminder, not
a spec. Promote to `ROADMAP.md` (or a fresh PR plan) when one is ready
to start.

## Near-term — pull into the next PR

- **Per-book rubric extensions via `voice.md`.** Today, adding a
  book/genre-specific scoring rule (e.g. "at most 2 financial
  transactions per chapter" for a mercantile historical) means
  editing `commands/evaluate.md` — wrong layer, since `commands/`
  is repo-shared and installed into every runtime. Evolve the
  contract: `books/{book}/voice.md` gains an optional
  `## Custom rubric` section (bulleted criteria, prose). Update
  `commands/evaluate.md` and `commands/reader-panel.md` to read
  voice.md, locate that heading if present, and instruct the judge
  to score and flag each criterion explicitly in the eval log.
  `commands/brief.md` already reads voice.md and the eval log, so
  the flag propagates to revise without further wiring. For
  recurring patterns, ship optional snippets under
  `src/autonovel/templates/rubrics/<name>.md` that voice.md can
  paste-in or reference. Cost: ~1 hr for the contract change plus a
  Tier-2 contract test asserting evaluate/reader-panel/brief still
  declare voice.md under `reads:`, plus a fixture chapter under
  `tests/fixtures/` whose voice.md carries a `## Custom rubric`
  block to lock the parsing.

- ~~**Long-sweep context exhaustion in draft-pass / revision-pass.**~~
  **Partly fixed 2026-04-25 evening.** draft-pass and revision-pass
  per-chapter sequences now run inside `task` subagents — each
  chapter's full workflow lives in a fresh subagent conversation
  and only a one-line summary returns to the parent. The parent's
  context grows by one short string per chapter instead of one
  full chapter's prose + tool output. Sweeps that previously
  stalled around chapter 8-10 should now run end-to-end.
  Still open: a sweep checkpoint file
  (`.autonovel/sweep-progress.json`) that `/autonovel:resume`
  reads to offer "continue from chapter N" recovery, so the user
  doesn't have to figure out `--chapters <remaining>` after an
  interruption.


- **Test-coverage gaps surfaced 2026-04-25.** The session's bug
  pattern revealed three structural test gaps that let
  late-stage / multi-stage / install-time bugs slip past Tier 1+2:

  1. **Realistic late-stage fixtures.** The `late_stage_book`
     conftest fixture (committed today) is one example — book with
     5 chapters, paired summaries, eval logs, briefs, edit logs,
     pending canon. Extend this pattern: every test of state-machine
     or filesystem-counting code should have a matching test
     against the realistic shape, not just the synthetic 0–2-chapter
     case. Convert existing tests opportunistically.

  2. **Multi-stage integration tests** (deterministic, no LLM).
     Today each command has a unit test in isolation. Real bugs hit
     the *seams between commands*: draft writes a summary file →
     count rolls forward → next-step decides → evaluate runs →
     score lands → next-step decides again. Add a Tier-1 integration
     suite that stitches these by simulating the on-disk state each
     command would have produced (no actual LLM call), and asserts
     the next-step recommendation at each seam. Prevents the kind
     of "evaluate kept recommending evaluate" bug we hit today.

  3. **pipx-isolated install test (Tier-3).** Spin up a clean tmp
     pipx home, `pipx install <repo>`, then verify
     `autonovel mechanical slop <file>` and
     `autonovel _tail-chapter --book ...` work from a shell whose
     `python` is the system python (not the project venv). This
     catches the `python -m autonovel.mechanical doesn't import`
     class of bug we hit today. ~30 min of work; opt-in marker
     so it doesn't run on every commit.

- **Bells Tier-4 fixture populate.** Still parked since PR 4. The
  harness is built; the chapters from `autonovel/bells` branch
  need copying in. Once populated, this is the canonical
  full-pipeline regression — gates LLM-prompt drift across an
  entire 19-chapter manuscript. Today's work would have benefited:
  a regression run on Bells chapters with summaries + evals + briefs
  would have caught at least the chapter-count and next-step bugs
  before they shipped.

- **Property-based tests for invariants.** Use `hypothesis` to
  generate random book layouts (varying chapter counts, presence/
  absence of summaries / eval logs / briefs / etc.) and assert
  invariants like "chapter count == count of `ch_NN.md` files only",
  "next-step is one of {evaluate, revise, draft, promote-canon,
  reader-panel} given drafting phase", "no chapter file is also a
  summary file". Catches the long tail of glob/inference bugs
  before they hit production.

- **Read-only TUI / web dashboard for series state.** Author noted
  2026-04-25 that NousResearch's earlier autonovel had a richer
  read-only console showing file artifacts and live progress; the
  rewrite ships only `autonovel status` (one-shot CLI),
  `autonovel statusline` (Claude Code status bar), and
  `.autonovel/command-log.jsonl` (append-only JSON log). A
  long-running TUI (e.g. via `textual`) or a tiny web server (FastAPI
  + websockets) that streams the lock state, last-action, recent
  command-log entries, per-book phase + chapter scores, and the
  `pending_canon.md` queue would be a real onboarding win for
  authors not at home in `cat .autonovel/*.json`. Roughly 1–2 days
  of work for a TUI; a basic web dashboard ~3 days. Hold for now —
  current tools cover the same data, just less prettily.


- **Research-from-seed auto-merges into canon (no manual editing).**
  ~~Open~~ **Fixed 2026-04-25.** `/autonovel:research --from-seed`
  now appends every research-derived candidate to the active book's
  `pending_canon.md` with a `[research:<slug>]` tag.
  `/autonovel:promote-canon` honours that tag: research-tagged
  entries win contradictions against the prior canon, and the
  supersedure is recorded in a `## Superseded <UTC-date>` block in
  `shared/canon.md` with the citation. Net effect: a user runs
  research-from-seed, then promote-canon, and `shared/canon.md`
  reflects cited primary-source facts without hand edits — date
  corrections like "Fugger arrived 1478 not 1473" propagate
  automatically and visibly.


- **Drafter must degrade gracefully when reading prior chapter
  context fails.** ~~Open~~ **Fixed 2026-04-25.** `commands/draft.md`
  step 7 and `commands/revise.md` step 6 now mark the prior-chapter
  read as best-effort with explicit "do not retry on failure"
  wording, and call out per-chapter summaries (step 8) as the
  load-bearing continuity surface. Author can no longer stall on
  Read retries when ch_{prev} hits a Claude-Code-internal hiccup.
  Carry-over: a *time-based* watchdog on `_begin` (live PID + lock
  older than N minutes → mark abandoned) is still open as a more
  general defence — the no-retry wording fixes this specific case
  but not the broader "LLM is wedged but PID is alive" failure.

- **Cross-provider `/autonovel:compare-models`.** V1 (shipped
  2026-04-25) is single-provider — it compares two Claude models
  within the active runtime. The natural extension is Opus vs GPT
  vs Gemini head-to-head, since model providers ship updates every
  few months and the user shouldn't have to migrate to evaluate.
  Implementation hint: add a `--runtimes claude,codex,gemini`
  argument; the parent runtime spawns a draft per (runtime, model)
  pair via the adapter layer (likely a new `autonovel _spawn-draft`
  CLI subcommand that knows how to invoke each runtime's headless
  mode and copy the result back into `eval_logs/`). The judge stays
  on whichever runtime the parent is in. ~3-5 hours of work.

- **Research belongs at the front of the foundation, not as a manual
  step.** A historical / period-fantasy / alternate-history project
  needs research *before* gen-world, gen-characters, and gen-canon
  generate from the LLM's general knowledge — otherwise you get
  invented dates that contradict each other (Fugger 1473 in canon,
  1471 in outline; surfaced during 2026-04-25 author testing).
  Concrete fix:
    1. Add `--from-seed` mode to `/autonovel:research` that reads
       `seed.txt` + `project.yaml :: period` and auto-derives 2–4
       research topics (period overview, specific people / places /
       events the seed names, period vocabulary). Each topic gets a
       sourced notes file in `shared/research/notes/`.
    2. Add a `_foundation_gap` check in `lifecycle.py` that
       recommends `/autonovel:research --book <book> --from-seed`
       *before* gen-world, but only when `project.yaml :: period.start`
       is set. Contemporary-literary projects skip cleanly.
    3. Wire `/autonovel:gen-world` and `/autonovel:gen-canon` to read
       any populated `shared/research/notes/*.md` files as context so
       the foundation is built on cited dates rather than memory.
  Cost: ~30 min of work; adds 1 command-mode + foundation-gap check
  + Tier-1 tests + README/lessons-doc updates. Shifts the foundation
  order, so anyone with an in-flight series will see `/autonovel:next`
  start recommending the new step.

## From live author testing (post-PR-9)

These surfaced during a real first-run on a Chromebook + WSL on Claude
Max $200/month. Full narrative + rationale in
`docs/lessons-from-author-testing.md`.

- **Per-command `model:` override on `[1m]` session models.** Verify
  whether Claude Code's session-level `[1m]` selection silently wins
  over the per-command `model:` field. If yes, decide between (i)
  leaving as-is, (ii) dropping the `model:` line, (iii) making it
  opt-out via `project.yaml :: llm.honor_session_model`.
- **Postamble compliance watchdog.** LLMs still occasionally skip
  `autonovel _end`. A wall-clock timeout in `_begin` that
  auto-marks the lock as `abandoned` after N minutes would catch
  this without needing the LLM to cooperate.
- **Verify `writes:` files were actually modified.** Postamble
  trusts `--wrote` paths; the LLM can claim it wrote a file without
  having invoked `Write`. Compare modification time / size against
  the checkpointed snapshot before declaring success.
- **Canon-vs-outline cross-consistency in `/autonovel:evaluate`.**
  When canon says X arrived in 1473 and the outline says 1471, the
  user shouldn't have to spot the contradiction manually. evaluate
  --phase foundation could date-compare references.
- **`autonovel install --dry-run`** so users can preview what would
  be written into `~/.claude/commands/` before mutating it.
- **`autonovel _begin` should echo a "running from `<dir>`" banner.**
  Wrong-cwd launches are the #1 silent-failure mode for the runtime;
  surfacing the cwd in the transcript would make the cause obvious.

## Output writing quality

These are things that would lift the prose ceiling beyond what the
current pipeline reliably produces (Bells topped out at pacing ≈ 7,
prose ≈ 8 / 10, with investigation-heavy plots).

- **Per-character voice fingerprints.** Today `voice.md` is a
  single fingerprint for the whole book (close-third or first). Adding
  a per-character voice fingerprint applied at dialogue + close-POV
  scenes catches the AI tell of "all characters sound the same".
  Implementation hint: extend `/autonovel:voice-discovery` to produce
  a per-character voice block when the cast has ≥3 named POVs.
- **Dialogue mechanics linter.** A new mechanical scanner that flags
  dialogue tics LLMs over-use: every line with an action beat (`she
  laughed`, `he frowned`), unattributed dialogue when ≥3 speakers, and
  the "softening qualifier" pattern (`maybe`, `kind of`, `a little`)
  inside short retorts where it neutralises tension. Lives in
  `src/autonovel/mechanical/dialogue.py`. Tier-1 testable.
- **Scene-level beat coverage in `evaluate.py`.** Score every scene
  against four beats (goal / conflict / disaster-or-decision /
  consequence) and surface scenes that are missing two or more.
  Catches the "drifting middle" failure mode the reader-panel test
  flagged in Bells.
- ~~**Cliché bigram/trigram scanner.**~~ **Shipped 2026-04-25** —
  `autonovel mechanical cliches <path>` returns a curated bigram
  scan; `evaluate.md` invokes it for `--chapter` and `--full`,
  feeding `density_per_1000_words` into the slop penalty (every
  full unit above 2.0 subtracts 0.1, capped at 0.5).
- ~~**Sensory-channel balance scanner.**~~ **Shipped 2026-04-25** —
  `autonovel mechanical sensory <path>` returns per-channel
  fractions (visual/auditory/olfactory/gustatory/tactile) and a
  `dominant_channel` flag when one channel >70%. `evaluate.md`
  surfaces dominance as a chapter `weakest_moment` callout.
- **Period register lock.** For period fiction, surface every
  sentence whose Flesch-Kincaid grade or syllable-per-word average
  drifts above the seed's 95th percentile — catches the "anachronistic
  register" failure that period-bans cannot (e.g. modern syntax in
  period-correct vocabulary).
- **POV bleed scanner.** Flag close-third sentences that name
  knowledge the POV cannot have at the moment of narration. Hard to
  do well; cheap version: search for "the woman / the man" referring
  to a named character the POV already knows.
- **Bell's "irreversible change" scorer.** Score each chapter on
  whether something that cannot be undone happens. The Stability Trap
  is a known AI failure; encode the antidote.
- **Per-chapter motif tracker.** Some books reward repetition of a
  central image (the bell, the apothecary's mortar). Track motif
  density per chapter and warn when one drops to zero in the back
  half.
- **Show-don't-tell judge upgrade.** Current rule is a regex sweep
  for "felt", "knew", "realised". A separate LLM pass that classifies
  every emotion line as direct / indirect / hybrid and scores the
  ratio per chapter is more accurate.

## Reader interest / reading experience

- ~~**Pacing curve graph in `/autonovel:evaluate --full`.**~~
  **Shipped 2026-04-25** — `--full` mode emits a markdown table
  with per-chapter words / score / tension / dialogue% / scenes /
  beats-hit so the user sees the shape of the book at a glance.
- ~~**Tension-drop alarms.**~~ **Shipped 2026-04-25** — `--full`
  scans the tension column for any window of three+ consecutive
  chapters trending down and surfaces a "⚠️  Tension drop
  detected: chapters X→Y→Z" callout with the recommended
  revision-pass invocation.
- ~~**First-page hook check.**~~ **Shipped 2026-04-25** —
  `/autonovel:evaluate --chapter 1` adds a separate
  `hook_strength` score over the first 250 words; surfaces it on
  its own line in the summary; flags below 6.0 as a real concern.
- **Series-arc score.** When `project.yaml` declares ≥2 books, score
  cross-book arcs (does the series have a question that resolves in
  the final book? do early-book setups pay off in late books?). Today
  the outline ledger tracks plants/payoffs per book only.

## Maintenance

- **Token + cost tracking.** Log per-command estimated input/output
  tokens to `.autonovel/command-log.jsonl` and surface a budget
  estimate in `autonovel status`. Carry-over from PRs 5–8.
- **Bells Tier-4 fixture populate.** Copy the final Bells chapters
  from the `autonovel/bells` branch into
  `tests/fixtures/bells-reference/` and freeze `scores.json`.
  Standalone one-off; the harness is already in place.
- **Codex Tier-3 spot-check on a Codex-equipped box.** Has run on
  the dev machine; rerun in CI once a Codex CLI runner is available.
- **Gemini Tier-3 spot-check on a Gemini-equipped box.** Skipped on
  the PR-8 dev box because `gemini` was not on `$PATH`. Adapter has
  full Tier-1 coverage; just needs an end-to-end run.
- **`autonovel doctor --fix` for missing external CLI tools.** Today
  the doctor reports them; could shell out to brew/apt to install on
  approval.
- **Drift on `commands/*.md` frontmatter schema.** When `argument-hint`
  or `model_tier` semantics change, the contract test catches usage
  but not field shape. Add a JSON-schema file at
  `src/autonovel/validators/command_schema.json` and a Tier-1 check.

## Portability

- **Real `npm publish` flow.** `package.json` and `bin/autonovel.js`
  are scaffolded but the package has not been published; verify
  `npm install -g autonovel` and `npx autonovel install` actually
  work on a clean box. Probably needs `prepublishOnly` to bundle the
  Python source via a build step, or a postinstall pipx hook.
- **`autonovel install --dry-run`.** Print what *would* be written
  without touching the runtime's directory. Useful for CI and for
  reviewing before letting npx mutate `~/.claude/`.
- **Per-runtime tool-name regression test.** Tier-1 already
  golden-files each adapter; add a fuzzer that random-generates
  command bodies and asserts no double-translation happens.
- **Windows path handling.** Adapters use `pathlib`, but the install
  destinations (`~/.claude/commands/...`) and the bash preamble assume
  POSIX semantics. Smoke once on a Windows runner before claiming
  cross-platform support.
- **`project.yaml :: image.provider`** is referenced in
  `commands/art-curate.md` but not yet read by any code. Either wire
  it through the adapter context or remove the documentation.
- **uv vs pip.** Repo currently has `uv.lock`; CLAUDE.md says
  `pip install -e .[test,export]`. Pick one canonical path or
  document both.

## Testing

- **Per-runtime smoke matrix in CI.** Today CI is Tier 1+2 only. A
  weekly cron that runs Tier-3 against Claude Code on a
  subscription-auth runner would catch runtime-version drift early.
- **Genre-fixture matrix runner.** `pytest --genre-matrix` (referenced
  in REWRITE-PLAN §12a) is not yet implemented. Today users run one
  fixture at a time via `autonovel test-fixture run <name>`.
- **`pytest -m 'genre("mystery")'` parameter selection.** The
  `genre(name)` marker is registered in `pyproject.toml` but pytest's
  `-m` parser doesn't filter by argument by default. Either add a
  pytest plugin/hook that reads the genre name out of the marker, or
  update docs to recommend `-k <genre>` instead.
- **Adapter round-trip test for the Codex `auth.json` rewriting.**
  The PR-8 smoke test redirects `CODEX_HOME` and copies the user's
  real `auth.json` into the redirected home — fragile. Add a Tier-1
  unit test that exercises the env-redirection path against a
  fake `auth.json`.
- **Mechanical-module pyproject extras smoke.** The `[export]` extras
  pin Pillow + pydub but no test imports them — a dependency drift
  in those packages would only surface at export time. Add a
  smoke import-only test gated on `[export]` being installed.
- **Flakiness budget.** `tests/flakiness.jsonl` is append-only with
  no rotation. Add `autonovel test-fixture trim-flakiness --keep N`
  or a `pytest --strict-flakiness` mode that fails when a test has
  flipped > N times in the last K runs.
