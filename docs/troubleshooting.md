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
`.autonovel/in-progress.lock`. Inside Claude Code:

```
/autonovel:resume
```

It will detect the stale lock, show you what command was running,
and offer to redo / keep partial / inspect.

If the runtime crashed and you want to clear the lock manually:

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
