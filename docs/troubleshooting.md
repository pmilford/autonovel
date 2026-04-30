# Troubleshooting

Common errors and what to do about them. If your error isn't listed,
open an issue with the exact error text and the output of
`autonovel doctor`.

---

## `API Error: Extra usage is required for 1M context`

**Full error text seen on Claude Code:**

```
API Error: Extra usage is required for 1M context - run /extra-usage
to enable or /model to switch to standard context
```

**What it means.** Claude Code's currently-selected session model is
a 1M-context variant (e.g. `claude-opus-4-7[1m]`), and Anthropic's
1M-context billing tier is not enabled on your account.

**Recommended fix — enable 1M.** autonovel benefits from 1M context;
`/autonovel:reader-panel` and `/autonovel:review` both read entire
manuscripts, and multi-book review can blow through 200k. Inside
Claude Code:

```
/extra-usage
```

This is the path the error message itself points you at, and on a
Claude Max $200/month plan it is the right default.

**Workaround — drop `[1m]`.** If `/extra-usage` doesn't unlock 1M for
your account (verified to happen on Claude Max $200/month during PR-9
author testing — the `/extra-usage` toggle didn't lift the gate), the
mechanical workaround is to run `/model` and pick a model without the
`[1m]` suffix:

- Opus 4.7 (no [1M]) — best quality.
- Sonnet 4.6 (no [1M]) — what every `/autonovel:*` standard-tier
  command targets.
- Haiku 4.5 (no [1M]) — fastest / cheapest, fine for
  `/autonovel:apply-cuts` and other light-tier commands.

Then re-run the command that failed. Foundation, drafting, and
per-chapter eval all fit comfortably in 200k; you only feel the loss
in whole-book review and multi-book series work.

**Open question.** The autonovel command files all declare specific
model names in their YAML frontmatter (`claude-sonnet-4-6` etc., none
with `[1m]`). Claude Code is *supposed* to honour those as
per-command overrides, but on at least one Claude Code version (PR-9
testing on Claude Max), the session-level `[1m]` selection silently
wins. If that's reproducible, the right fix may be to make
autonovel's model-pinning opt-in via `project.yaml` so users on
1M-by-default plans aren't downshifted at all. Open issue, not yet
resolved — see `FUTURE-TODOS.md`.

**Why does Max not unlock /extra-usage automatically?** Don't know.
That's between you and Anthropic billing. The two paths above both
work regardless.

---

## `claude: command not found` after `pipx install`

You installed `pipx` but never opened a fresh terminal after
`pipx ensurepath`. Close the current terminal window, open a new
one, and try `autonovel --version` again.

If that doesn't fix it, check whether pipx put the install root on
your PATH:

```bash
pipx ensurepath --force
echo "$PATH" | tr : '\n' | grep -i pipx
```

Expected output includes a line ending in `.local/bin` or similar.

---

## `error: No project.yaml found walking upward from <path>`

You launched `claude` (or a housekeeping subcommand) from a directory
that isn't an autonovel series. `cd` into the directory created by
`autonovel new-series` (the one containing `project.yaml`) and try
again. The README's "Be in the series root" callout under §4
diagnoses this with `pwd` and `ls project.yaml`.

---

## `error: another command is already in flight` from `autonovel _begin`

A previous command exited without releasing
`.autonovel/in-progress.lock`. There are three recovery paths
depending on how stuck you are.

**Recommended (Claude Code):**

```
/autonovel:resume
```

It will detect the stale lock, show you what command was running,
and offer to redo / keep partial / inspect.

**Wait for the watchdog (since 2026-04-28):** locks older than
30 minutes are automatically taken over by the next command's
`_begin`. So if you ran a command, it errored without `_end`,
and you wait half an hour, the next command runs cleanly with
a one-line "took over expired lock from <prior command>" note.
This catches the bug class where an LLM skips the postamble in
the same Claude Code session.

**Manual clear (runtime crashed, no resume available):**

```bash
cat .autonovel/in-progress.lock        # see what was running
rm .autonovel/in-progress.lock         # only after confirming no `claude` is running
```

---

## A `/autonovel:*` command runs but writes nothing

Most often: you launched `claude` from inside a book directory
(`books/<book>/`) instead of the series root. The commands resolve
paths like `shared/world.md` relative to the runtime's cwd, so a
book-directory launch makes those paths look one folder too deep
and the commands silently fall through.

Quit Claude Code, `cd` to the series root (where `project.yaml`
lives), launch `claude` again, retry.

---

## My session model is `[1m]` and per-command pinning silently downshifts me

When you select a `[1m]`-context model in Claude Code (e.g.
`claude-opus-4-7[1m]`), each `/autonovel:*` command's frontmatter
`model: claude-opus-4-7` (no `[1m]`) appears to win — silently
downshifting your session out of 1M context. Recovery path:

```bash
autonovel install --no-model-pin
```

This re-renders every command file *without* the `model:` field,
so the runtime's session model wins on every invocation. You give
up per-command tier intent (e.g. cheap Haiku for light commands,
expensive Opus for heavy ones) in exchange for never losing 1M
context. If you want to switch back, run `autonovel install` (no
flag — the default re-pins).

The lessons-from-author-testing doc §8 has the longer narrative
on why the interaction is non-obvious. FUTURE-TODOS continues to
track a more granular fix where pinning is per-tier opt-out via
project.yaml.

---

## A `/autonovel:*` command's postamble shows a `🔴 VERIFY-WRITES` banner

The postamble caught a self-report mismatch. The LLM passed
`--wrote <path>` to `autonovel _end` for one or more files, but
the on-disk state doesn't match the claim. As of 2026-04-30 the
warning leads the postamble (rather than trailing it) so it can't
get buried under a long sweep closer.

- `claimed created but file does not exist` — the LLM said it
  created a file but never invoked the `Write` tool. Re-run the
  command; if it fails twice, look at the command body for a
  step that should be writing the file.
- `claimed modified but bytes match the checkpoint` — the LLM
  said it edited a file but the bytes are identical to the
  begin-time backup. **For chapter files specifically, this is
  almost always the silent-revise-failure bug class** — the
  per-chapter task subagent in a `revision-pass` / `draft-pass`
  sweep reported success without invoking Write/Edit. The fix is
  to re-run the sweep targeting just those chapters; the banner
  now lists them by path. For non-chapter paths, the command may
  have legitimately decided no edits were needed (e.g.
  `pending_canon.md` only grows when new facts surface) — review
  before re-running.

The banner is informational — the command exited `ok` and the
lock has been released. Decide whether to re-run based on the
command's contract: if the command is *required* to produce a
specific file (e.g. `/autonovel:gen-world` writes
`shared/world.md`), re-run when it shows up missing. The
chapter-file specific call-out is the load-bearing case for
sweep commands — the situational `/autonovel:next` will also
flag those chapters via the brief→revise signal, since the
brief is fresh while the chapter file is unchanged.

The same warnings get logged to
`.autonovel/command-log.jsonl`'s `note` field so an audit trail
outlives the postamble print.

---

## PDF shows the first sentence of each chapter as a page header / alternating heading

Two distinct bugs combined to produce this — both fixed 2026-04-28
but the typeset half is invisible to in-flight series unless you
refresh the templates explicitly.

What you should see in a clean PDF: each chapter opens with
"chapter <Roman>" as the heading, no further chapter text in the
running header. Verso (left) page header is the book title, recto
(right) is "Chapter <Roman>". The first sentence of the chapter
is plain prose with a drop cap on the first letter, NOT a large
italic block at the chapter title page.

If yours doesn't look like that:

```bash
# 1. Pull the latest autonovel and reinstall.
( cd ~/autonovel && git pull && pipx reinstall . ) && autonovel install

# 2. Refresh the typeset template in your series.
cd ~/<your-series-root>
autonovel refresh-templates              # default refreshes typeset/ only
                                          # add `--dry-run` to preview

# 3. Rebuild the PDF.
/autonovel:typeset --book <your-book>
```

The two underlying causes (for the curious / for future
debugging):

1. `mechanical/latex.py::build_chapters_tex` was using the first
   prose line as the chapter title argument when chapters had no
   `# Heading` after the YAML frontmatter (the production shape).
   The fix emits an empty `\chapter{}` so `\titleformat` prints
   "chapter <Roman>" alone.

2. The shared `<series-root>/typeset/novel.tex` template is
   copied at `autonovel new-series` time and never updated by
   `autonovel install`. The 2026-04-25 fix that switched the
   running header from `\textit{\leftmark}` (which renders the
   chapter title arg from #1) to `\fancyhead[RO]{Chapter
   \thechapter}` only takes effect after `autonovel
   refresh-templates`.

If `refresh-templates` reports your `novel.tex` under "local-only
(preserved)" instead of "updated", you've hand-edited the file —
diff your version against the package template at
`<autonovel-repo>/src/autonovel/templates/series/typeset/novel.tex`
and re-apply your customisations on top of the new shape.

---

## `tectonic: command not found` (or `pandoc`, `potrace`, `ffmpeg`)

You're trying to run an export command (`/autonovel:typeset`,
`/autonovel:audiobook-assemble`, etc.) without the matching external
CLI tool installed. `autonovel doctor` reports these as warnings;
install just the one(s) you need:

```bash
# Linux / WSL / Chromebook:
sudo apt install -y tectonic pandoc potrace ffmpeg librsvg2-bin fontconfig

# macOS:
brew install tectonic pandoc potrace ffmpeg librsvg fontconfig
```

You only need these for the matching export commands — drafting and
revision don't.

---

## Fal.ai / ElevenLabs API errors during export

These are paid third-party services. autonovel doesn't ship API keys
— you provide them in `.env` at the series root:

```bash
FAL_KEY=fal-...
ELEVENLABS_API_KEY=...
```

`autonovel doctor` warns when these are missing.

---

## Smoke tests skip with `claude CLI not on $PATH`

Tier-3 smoke tests need a real runtime. Either install Claude Code
(or Codex CLI / Gemini CLI) and add it to `$PATH`, or accept the
skip — Tier 1+2 (deterministic + contract) are the gates that run
on every commit and don't need a runtime.

```bash
which claude        # should print a path; if blank, install Claude Code
```
