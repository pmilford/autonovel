# Future todos

Items that are out of PR-9 scope but worth recording so a future
session can pick them up. Companion to `ROADMAP.md` (PR sequence),
`STATE.md` (decisions log), and `docs/lessons-from-author-testing.md`
(narrative explanation of *why* certain defensive shapes exist).

The list is rough on purpose — each entry is a one-line reminder, not
a spec. Promote to `ROADMAP.md` (or a fresh PR plan) when one is ready
to start.

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
- **Cliché bigram/trigram scanner.** Current TIER1/2/3 are unigrams.
  Bigrams (`pale moonlight`, `gentle breeze`, `inexorable march`)
  carry more signal per regex hit.
- **Sensory-channel balance scanner.** A scene that's 90% visual is
  a known LLM tell. Score the per-scene channel mix
  (sight/sound/smell/touch/taste) and warn when one channel is >70%.
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

- **Pacing curve graph in `/autonovel:evaluate --full`.** Plot the
  per-chapter words / scenes / beats / dialogue ratio so the user can
  see the shape of the book. Today the only output is a number.
- **Tension-drop alarms.** Detect three-or-more consecutive chapters
  whose evaluator tension score moves down. Investigation-heavy plots
  like Bells often have one of these in act 2; the alarm prompts a
  sidequest before a full revision cycle is needed.
- **First-page hook check.** `/autonovel:evaluate --chapter 1` should
  separately score the first 250 words against an LLM judge tuned for
  hook strength (specific-image-in-line-1, stakes-implied-in-line-3).
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
