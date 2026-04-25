# Lessons from author testing (post-PR-9)

A real first-time-author run on a Chromebook + WSL exposed several
real onboarding bugs that Tier 1+2 tests cannot catch. This file
records what we learned, what we fixed, and what's still open. It is
intentionally written for the next maintainer (human or AI) so that
"why is this code shaped this way" is recoverable from one place.

The author was the project owner, deliberately driving a fresh series
end-to-end on a Claude Max $200/month subscription. Every issue
listed here surfaced during that single live run.

## What we fixed

### 1. The `npx autonovel install` claim was a lie

**Symptom:** the README told the user to run `npx autonovel install`
on a Chromebook. It failed because `autonovel` is not yet published
to the npm registry.

**Lesson:** documenting an install path that doesn't work yet is
worse than documenting only the paths that do. Users assume the
README is reality, not aspiration.

**Fix:** README now leads with `pipx install .` from a clone. `npx`
and `npm install -g` are listed as planned post-publish paths.

### 2. The seed.txt template was a 3-line stub

**Symptom:** the user opened `books/<book>/seed.txt` and saw three
lines of generic prompt ("one to three paragraphs describing what
this book is about"). They had no idea how deep to go.

**Lesson:** if a file is supposed to be the *one piece of writing the
human contributes*, the default template needs to walk them through
the answer with prompts and worked examples — not be a stub.

**Fix:** `src/autonovel/templates/book/seed.txt` is now a guided
6-section template (pitch, POV, obstacles, change, period/place,
notes), each section shipping a paragraph of `#`-commented
explanation and a worked Renaissance-Venice example. README §3
quotes the expected time investment (20–30 min).

### 3. The README hand-waved the install for non-programmers

**Symptom:** the user enabled ChromeOS Linux, opened Terminal,
discovered `git` was missing, then `pipx`, then realised
`pipx ensurepath` doesn't take effect until a fresh terminal opens.
Each step broke the install flow without explanation.

**Lesson:** "install dev tools" is invisible scaffolding for
programmers and a series of cliffs for everyone else. Per-OS
step-by-step matters.

**Fix:** README install section now has explicit Chromebook, WSL,
macOS, and Linux-desktop subsections, each spelling out:
- enable the Linux container (Chromebook only),
- `apt install -y git pipx` / `brew install git pipx`,
- `pipx ensurepath`,
- **open a fresh terminal** (called out as the #1 trip),
- exact directory state before and after `git clone`.

### 4. `$EDITOR` was programmer shorthand

**Symptom:** the README told the user to "edit `seed.txt` with
`$EDITOR`". They did not know what `$EDITOR` was.

**Lesson:** instructions for authors must use named tools, not shell
conventions. Authors should not have to learn what an environment
variable is to write a novel.

**Fix:** README now lists concrete editors per OS (ChromeOS Text app,
Notepad via WSL, TextEdit via `open -e`, VS Code, `nano` everywhere)
plus a one-line nano cheat sheet (`Ctrl-O` saves, `Ctrl-X` quits).

### 5. Series-root vs book-subdirectory was ambiguous

**Symptom:** after editing `books/<book>/seed.txt`, the user wasn't
sure whether to launch `claude` from the series root or the book
directory. Launching from the wrong place would silently break
commands (paths in command bodies are relative to runtime cwd, but
the housekeeping CLI walks up looking for `project.yaml`, masking
the issue from `_begin` while the actual workflow fails on relative
paths).

**Lesson:** any tool that uses cwd-relative paths must front-load a
"how to verify you're in the right place" check.

**Fix:** README §4 now opens with a sanity-check (`pwd`,
`ls project.yaml`) and a one-line `cd ..` recovery. Future
improvement: `autonovel _begin` could echo a "running from `<dir>`"
banner so a wrong-cwd run is obvious in the Claude Code transcript.

### 6. Foundation commands ran out of order; the user didn't know

**Symptom:** the README listed the five foundation commands as a
code block. The user read it as a list of options and ran only three
(world, characters, outline). `evaluate --phase foundation` returned
5.9 and complained about missing voice and canon. The pipeline never
flagged the gap.

**Lesson:** the user should never have to discover skipped pipeline
steps from a low evaluation score. Required ordering must be
enforced by `/autonovel:next`, not encoded in prose.

**Fix:** `lifecycle._next_step_for` now checks the foundation gap
(world → characters → voice → canon → outline) before delegating to
the generic next-step decision tree. A user running `/autonovel:next`
after each command walks the canonical order without having to
remember it. README §4 reframed: the foundation is now described as
five required steps with `/autonovel:next` as the canonical loop.

### 7. The `(empty)` marker test was incomplete

**Symptom:** while building the foundation gap detector, the obvious
"is this file empty / still a template stub?" check failed for
canon.md ("Seeded by …") and voice.md ("Filled by …"). The earlier
exclude-marker list only knew about "Generated by".

**Lesson:** every template that ships with a placeholder comment
needs a recognisable marker, and the populated-content detector must
know all of them. Adding a new template type requires updating the
marker list.

**Fix:** `_is_populated`'s exclude-marker list now covers
`Generated by`, `Seeded by`, `Filled by`, `(empty`, and
`Leave empty until then`. Testing populated/unpopulated is locked by
two new Tier-1 regression tests.

### 8. The 1M-context billing gate

**Symptom:** mid-pipeline, `/autonovel:gen-outline` failed with
`API Error: Extra usage is required for 1M context - run /extra-usage
to enable or /model to switch to standard context`. The user was on
Claude Max $200/month and reasonably expected 1M to be in scope.
Running `/extra-usage` did not unlock 1M; `/model` to a non-`[1m]`
variant did.

**Lesson:** Claude Code's session model interacts with autonovel's
per-command `model:` frontmatter in non-obvious ways. A 1M-context
session model can hit a billing gate even on premium plans, even with
`/extra-usage` enabled. The autonovel pipeline does not control this.

**Fix:** README §6 documents the gate and its workaround
(`/extra-usage` recommended, `/model` to non-`[1m]` as fallback).
`docs/troubleshooting.md` carries the verbatim error text + diagnosis
so a search lands the next user there. The series-template CLAUDE.md
instructs the agent to surface this verbatim and stop, rather than
retry.

**Open question:** every command file's frontmatter pins a specific
model name (`claude-sonnet-4-6` for standard, `claude-opus-4-7` for
heavy, `claude-haiku-4-5-20251001` for light). On at least one
Claude Code version, a session-level `[1m]` selection appears to win
over the per-command override, which silently downshifts premium-plan
users from their chosen variant. Three options for the next
maintainer to evaluate: (i) leave as-is and document; (ii) drop the
`model:` line entirely so the session model always wins; (iii)
make pinning opt-out via `project.yaml :: llm.honor_session_model`.
Tracked in FUTURE-TODOS.md.

### 9. The next-step footer didn't appear after gen-outline

**Symptom:** `gen-outline` completed but no `**Next:**` line was
emitted. The user had to ask the agent.

**Root cause:** `_next_step_for` looked up `book.status` in
`project.yaml`, which is set to `"seed"` at scaffold time and never
advanced. So `next_step()` returned `/autonovel:gen-world` — which
the user had already run. The footer rendered but with the wrong
suggestion. **And** in some runs the LLM skipped the postamble
entirely, producing no footer at all.

**Lesson:** project.yaml's `book.status` field was a poor
authority — it wasn't actually maintained. The filesystem is.

**Fix:** filesystem-inferred phase replaces `book.status` lookup. The
postamble was strengthened to **Mandatory** with explicit "echo the
footer verbatim as your closing reply; do not stop after the bash
call" wording. Two new regression tests.

### 10. autonovel doesn't install Claude Code hooks

**Symptom:** the user observed `autonovel _begin` running in the
status line and asked whether autonovel had installed a Claude Code
hook that was interfering with their custom statusline.

**Lesson:** the line between "Bash subprocess inside a command body"
and "Claude Code hook" is not obvious to users. Both show up in the
status line; only the latter is registered globally.

**Fix:** none required — autonovel installs zero Claude Code hooks
(verified by grep). `bash` invocations inside a command body are
one-shot subprocesses, not registered events. Documented at the time.
Worth keeping clear in future docs.

### 11. The audiobook_voices.json deletion lost a reference example

**Symptom:** PR-9 deleted `audiobook_voices.json` from the repo root
(its functional role was replaced by per-book
`books/<book>/audiobook/voices.yaml`). But the file also served as a
**shape reference** showing the YAML keys, the optional `description`
and `why` audit fields, and the conventions for speaker naming. That
reference role was unfilled.

**Lesson:** before deleting a file, audit *all* its roles, not just
the most obvious one. A reference example is a different artefact
from a live data file.

**Fix:** restored as
`src/autonovel/templates/book/audiobook/voices.yaml.example`,
scaffolded into every new book by `autonovel new-book`. Bells voice
metadata preserved verbatim; format converted JSON → YAML.

### 12. Canon ↔ outline drift after partial foundation runs

**Symptom:** a user who ran `gen-outline` before `gen-canon` (and
`voice-discovery`) ended up with an outline whose dates contradicted
canon. Concretely: canon said Jakob Fugger arrived in Venice in
1473; outline said 1471.

**Lesson:** the foundation order isn't only "you might miss a step";
it's "running them out of order can produce *contradictory*
artefacts that need a regenerate-with-`--force` pass to fix."

**Fix:** the foundation-chaining in `/autonovel:next` (issue 6)
prevents the original mistake. For users already in this state, the
recovery is `/autonovel:gen-outline --book <book> --force` after canon
is in place. Future improvement: `/autonovel:evaluate --phase
foundation` could explicitly cross-check canon-vs-outline date
consistency rather than leaving the user to spot it manually.

## Open questions / future work

These are recorded in `FUTURE-TODOS.md` as well; cross-listed here so
the rationale lives next to the lesson that prompted it.

- **Per-command `model:` override semantics on Claude Code with `[1m]`
  session models.** See issue 8.
- **Postamble compliance verification.** The LLM still sometimes
  skips `autonovel _end`. The lock state tells us a missing _end
  happened on the *next* run, but reactive. A lightweight watchdog —
  maybe a wall-clock timeout in `_begin` that auto-marks lock as
  abandoned — would catch this.
- **`writes:` content verification.** Today the postamble trusts
  `--wrote` paths. A user can run a command, get an "ok" footer, and
  the file is empty because the LLM never invoked `Write`. Verify
  modification time / size delta from the checkpointed snapshot
  before declaring success.
- **Canon-vs-outline cross-consistency in evaluate.** The outline
  references events whose dates are in canon. evaluate should flag
  drift.
- **`autonovel install --dry-run`** so users can see what gets
  written into `~/.claude/commands/` before it happens.
- **Real `npm publish` flow.** Until done, the README's npm/npx
  paths remain aspirational.

## How to read this file

When you find a piece of code or doc structure that seems
defensively-written, search for the keyword in this file. The
"lesson" entries explain *why* the defensive shape exists, so a
future refactor doesn't accidentally remove the protection.

When you fix something author-testing surfaces, add it here. The
lessons compound: every entry above started as someone hitting a
wall on a real machine, and the fix is only durable if the next
maintainer can find why the wall was where it was.
