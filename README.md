# autonovel

An autonomous novel-writing pipeline that drops a `/autonovel:*` command
suite into your AI CLI runtime — Claude Code, OpenAI Codex, or Gemini
CLI — and turns a seed concept into a finished novel: manuscript,
typeset PDF, ePub, cover art, audiobook, landing page.

The runtime owns the model, the auth, and the file I/O. autonovel just
ships markdown commands and a small Python housekeeping CLI.

## Acknowledgements

This repository is a **fork and complete re-architecting** of two
upstream projects:

- **[NousResearch/autonovel](https://github.com/NousResearch/autonovel)** — the original autonomous-fiction
  pipeline, including the production framework that wrote the novel
  *The Second Son of the House of Bells* (see the [Bells production](#the-bells-production)
  section below). Every craft principle, every prompt heuristic,
  every gotcha learned from a real production run came from there.
- **[karpathy/autoresearch](https://github.com/karpathy/autoresearch)** — the modify → evaluate →
  keep/discard loop applied to research, which we apply here to
  fiction.

What changed in this re-architecture: the original was a set of
~27 Python scripts that called the Anthropic API directly. This
version replaces them with markdown commands installed into your
existing AI CLI runtime, so the runtime owns the model and auth, and
the same pipeline runs on Claude Code, Codex CLI, or Gemini CLI
without changes to the prompts. See [`REWRITE-PLAN.md`](REWRITE-PLAN.md)
for the full architecture write-up.

---

## Install

> Pick the section for your machine. Each one assumes you have
> **never set up programming tools on this machine before**. If you
> already have `git` and `pipx`, jump to "Get the source".

The current install path is from a git clone. Once we publish `v0.1.0`
to npm and PyPI, `npx autonovel install` and `pipx install autonovel`
will work without a clone — but for now you need the clone.

### Chromebook (ChromeOS Linux)

1. **Enable the Linux development environment.** This is a one-time
   ChromeOS setting. Open *Settings → Advanced → Developers → Linux
   development environment* and click *Turn on*. ChromeOS will
   download a small Linux container; this takes a few minutes.

2. **Open the Terminal app.** It appears in your launcher after
   step 1. When it opens you'll see a prompt like:

   ```
   yourname@penguin:~$
   ```

   The `~` means you're sitting in your Linux home folder. That
   folder lives at `/home/yourname/` and starts empty.

3. **Install `git` and `pipx`.** Copy and paste these two lines, one
   at a time, pressing Enter after each:

   ```bash
   sudo apt update
   sudo apt install -y git pipx
   ```

   The first time you use `sudo` it will ask for your password.

4. **Tell pipx to put installed tools on your PATH:**

   ```bash
   pipx ensurepath
   ```

   Then **close the Terminal window and open a fresh one** so the
   PATH change takes effect. (This is annoying but unavoidable —
   pipx is updating a shell configuration file that only fresh
   terminals re-read.)

5. **Get the source.** Continue at "Get the source" below.

### Windows (WSL)

1. **Enable Windows Subsystem for Linux** if you haven't. In a
   PowerShell window run `wsl --install` and follow the prompts;
   reboot when asked. Microsoft's full guide:
   <https://learn.microsoft.com/en-us/windows/wsl/install>.

2. **Open your WSL distribution** (it shows up as "Ubuntu" or
   similar in the Start menu). You'll see a prompt like:

   ```
   yourname@machine:~$
   ```

   Same as the Chromebook — `~` is your Linux home folder.

3. **Install `git` and `pipx`** with the same two `apt` commands as
   the Chromebook step 3 above, followed by `pipx ensurepath` and
   a fresh terminal window (Chromebook step 4).

4. **Get the source.** Continue below.

### macOS

1. Open the **Terminal** app (Applications → Utilities → Terminal).

2. Install [Homebrew](https://brew.sh/) if you don't have it.

3. Install `git` and `pipx`:

   ```bash
   brew install git pipx
   pipx ensurepath
   ```

   Open a fresh Terminal window after `pipx ensurepath`.

4. **Get the source.** Continue below.

### Linux desktop

You almost certainly know what to do. `apt`/`dnf`/`pacman` install
`git` and `pipx`, run `pipx ensurepath`, open a fresh terminal,
continue.

---

### Get the source

These steps are the same on every operating system once a fresh
terminal is open with `git` and `pipx` available.

1. **Clone the repository.** This downloads the autonovel source
   into a new folder named `autonovel` next to whatever folder you
   were already in:

   ```bash
   git clone https://github.com/pmilford/autonovel.git
   ```

   Before this command: your terminal sits in `/home/yourname/`
   (an empty folder).
   After this command: there's a new folder at
   `/home/yourname/autonovel/` holding the source. Your terminal
   is **still** sitting in `/home/yourname/` — cloning a repo does
   not move you into it.

2. **Step into the folder and install:**

   ```bash
   cd autonovel
   pipx install .
   ```

   `cd` ("change directory") moves you into the cloned folder.
   `pipx install .` reads the `pyproject.toml` here, installs
   autonovel as a tool you can run from anywhere, and shows you
   where the `autonovel` command was placed.

3. **Confirm it worked:**

   ```bash
   autonovel --version
   ```

   You should see `autonovel 0.1.0`. If you see "command not found",
   the most common cause is that you didn't open a fresh terminal
   after `pipx ensurepath` — close this terminal, open a new one,
   try again.

4. **Install your AI CLI runtime.** Pick at least one:

   - [Claude Code](https://docs.claude.com/en/docs/claude-code) — the original target. After install, run `claude login`
     once. Most users want this one.
   - [OpenAI Codex CLI](https://github.com/openai/codex)
   - [Google Gemini CLI](https://github.com/google-gemini/gemini-cli)

5. **Install the autonovel commands into your runtime:**

   ```bash
   autonovel install
   ```

   This auto-detects which runtimes you installed in step 4 and
   drops the `/autonovel:*` command files into each one. You can pin
   a single runtime with `--only claude` (or `codex` / `gemini`).

6. **(Claude Code only) Pick a standard-context model.** Launch
   `claude` once and run `/model`. Pick a model **without** the
   `[1m]` suffix — for example `claude-sonnet-4-6`, not
   `claude-sonnet-4-6[1m]`. The 1M-context variants require a
   separate paid usage tier; the autonovel commands all fit
   comfortably inside the 200k standard context, and the runtime
   will otherwise fail mid-pipeline with `API Error: Extra usage is
   required for 1M context`. (This is a Claude Code default
   choice, not an autonovel choice.)

You're done with installation. The next section is for using it.

---

## For users — writing a novel

You don't open the autonovel folder when you write. autonovel is a
**tool you installed**; your novel lives in its own folder somewhere
else. (Same way you don't write a book inside your word processor's
install folder.)

### 1. Make a folder for your novel

Pick somewhere convenient:

```bash
mkdir -p ~/novels
cd ~/novels
```

### 2. Scaffold a series

A "series" in autonovel is the unit of co-evolving lore. A standalone
novel is a series with one book.

```bash
autonovel new-series renaissance-europe --genre historical-fiction
cd renaissance-europe
autonovel new-book the-inquisitor --pov Tommaso --story-time-range 1519-1523
```

This creates:

```
renaissance-europe/
  project.yaml             # series config
  shared/
    world.md               # filled in later by /autonovel:gen-world
    characters.md
    canon.md               # the hard-fact database
    events.md              # inter-book event ledger
    period_bans.txt        # period-anachronism word list (pre-seeded for 1400-1600)
    research/              # forced URLs and notes
  books/
    the-inquisitor/
      seed.txt             # ← you edit this first
      voice.md
      outline.md
      chapters/            # generated by /autonovel:draft
      …
```

### 3. Write the seed

The seed file is the **one piece of writing autonovel needs from
you**. Everything else (world, characters, outline, prose) is built
from it. The new book template ships a guided template with six
prompts — the pitch, your POV character, the obstacles, what
changes by the end, period and place, and anything else you want
the AI to know. There's an example answer under each prompt so you
can see the depth expected.

You're currently in `~/novels/renaissance-europe/`. The seed lives
one folder down at `books/the-inquisitor/seed.txt`. Open it in any
text editor — pick whichever you have:

- **Chromebook:** the *Text* app from your launcher works. Or, in
  the terminal: `nano books/the-inquisitor/seed.txt`.
- **Windows / WSL:** type `notepad.exe books/the-inquisitor/seed.txt`
  (Notepad opens on the Windows side, editing the WSL file). Or in
  the terminal: `nano books/the-inquisitor/seed.txt`.
- **macOS:** `open -e books/the-inquisitor/seed.txt` opens it in
  TextEdit. Or in the terminal: `nano books/the-inquisitor/seed.txt`.
- **VS Code on any OS** (if installed): `code books/the-inquisitor/seed.txt`.

If you've never used `nano` before, it shows the keyboard shortcuts
along the bottom of the window: `Ctrl-O` saves, `Ctrl-X` quits.

Plan to spend **20–30 minutes** on the seed. You don't need to
write elegantly — bullet points are fine; the AI will turn them
into prose.

### 4. Open the series in your runtime and run commands

**Be in the series root** — the folder that contains `project.yaml`.
For our example that's `~/novels/renaissance-europe/`. The
`/autonovel:*` commands resolve paths like `shared/world.md` and
`books/the-inquisitor/seed.txt` relative to wherever you launch the
runtime, so being one folder too deep produces "file not found"
errors that look mysterious.

Sanity-check your location first:

```bash
pwd                       # should end in /renaissance-europe
ls project.yaml           # should print "project.yaml" with no error
```

If `ls project.yaml` errors, you're in the wrong place. The fastest
fix is `cd ~/novels/renaissance-europe`. (If you `cd`-ed into the
book directory to edit the seed, `cd ..` once is enough.)

Then launch your runtime:

```bash
claude            # or `codex`, or `gemini`
```

Inside the runtime, type these commands one at a time (each takes
seconds to minutes depending on tier):

```text
/autonovel:gen-world
/autonovel:gen-characters
/autonovel:gen-canon
/autonovel:voice-discovery --book the-inquisitor
/autonovel:gen-outline --book the-inquisitor
/autonovel:draft 1 --book the-inquisitor
/autonovel:evaluate --chapter 1 --book the-inquisitor
```

Or run the full pipeline end-to-end (foundation → drafting →
revision → export):

```text
/autonovel:run-pipeline --books the-inquisitor
```

### 5. Read the worked example

For a 12-step end-to-end walkthrough on a 3-book historical series
— including research, period guardrails, cross-book events, and
publishing to PDF/ePub/audiobook — see
[`docs/writing-a-historical-series.md`](docs/writing-a-historical-series.md).

### How much do you write, and when?

You write the seed (~20–30 minutes). After that, your job is to
**read what the AI produces and steer**, not to write prose. Rough
expectations for a single ~70,000-word novel:

| Phase | What you do | Realistic time |
|---|---|---|
| Seed | Answer the six prompts in `seed.txt`. | 20–30 min |
| Foundation review | Read `shared/world.md`, `shared/characters.md`, the outline. Re-run any of `/autonovel:gen-world`, `/autonovel:gen-characters`, `/autonovel:gen-outline` if something is off — they reference your seed each time. | 30–90 min total, spread across 1–3 cycles |
| Voice discovery | `/autonovel:voice-discovery` produces five trial passages; you pick one (or rerun for new trials). | 5–15 min |
| Drafting | The runtime drafts chapters one at a time. You can let it run unattended; later, glance at chapters that scored low in `/autonovel:evaluate` and decide whether to retry. | 5–30 min of attention per chapter, mostly skimming |
| Revision | Read the briefs from `/autonovel:reader-panel` and `/autonovel:review`. Override anything you disagree with before running `/autonovel:revise`. | 30–90 min per book per cycle; usually 2–3 cycles |
| Export | `/autonovel:typeset`, `/autonovel:cover-print`, `/autonovel:audiobook-*` are mostly pushbutton if you have the tools and keys. | 1–2 hours, mostly waiting |

**Total wall-clock time** for a tiny 3-chapter book (like the smoke
fixtures): an afternoon. For a 70k-word novel: **a few full days of
on-and-off attention**, with the AI doing the heavy lifting and you
reading + steering. The Bells production took about a week of part-time
work spread across several months.

**Where to invest the most thought, in order:**

1. **The seed** — every downstream layer derives from it. A vague seed
   produces a vague book.
2. **The outline review** — fixing a structural issue in the outline
   takes minutes; fixing it after eight chapters are drafted takes
   hours.
3. **The first chapter eval** — voice problems caught in chapter 1
   compound across the book. Read `/autonovel:evaluate --chapter 1`
   carefully and rerun voice-discovery if needed before drafting more.
4. **Reader-panel / review feedback** in the revision phase — you'll
   want to override some items and prioritise others. The AI will
   otherwise try to address every comment, even ones that conflict.

### What the commands do

Three categories. Full reference: [`docs/commands.md`](docs/commands.md).

- **Foundation:** `gen-world`, `gen-characters`, `gen-outline`,
  `voice-discovery`, `gen-canon`, `research`.
- **Drafting & revision:** `draft`, `evaluate`, `adversarial-edit`,
  `apply-cuts`, `reader-panel`, `review`, `brief`, `revise`,
  `check-anachronism`.
- **Export:** `art-*`, `cover-*`, `audiobook-*`, `typeset`,
  `landing`, `package`.

Plus 11 sidequests for non-standard operations (`shorten`, `lengthen`,
`revoice`, `split-chapter`, `merge-chapters`, `reorder`,
`remove-chapter`, `deepen-character`, `add-subplot`, `foreshadow`,
`rename-character`).

### Two immune systems against AI slop

- **Mechanical:** regex scanners for banned vocabulary
  (`delve`, `tapestry`, …), em-dash overuse, sentence-length
  uniformity, fiction clichés, period-bans.
- **LLM judge:** a model distinct from the writer scores prose,
  voice, character, beat coverage. Tiers configurable in
  `project.yaml`.

### User-relevant docs

- [`docs/commands.md`](docs/commands.md) — every `/autonovel:*` command.
- [`docs/multi-book.md`](docs/multi-book.md) — coordinating multiple books in one series.
- [`docs/writing-a-historical-series.md`](docs/writing-a-historical-series.md) — end-to-end walkthrough.
- [`docs/series-layout.md`](docs/series-layout.md) — `shared/` vs `books/`.
- [`docs/chapter-frontmatter.md`](docs/chapter-frontmatter.md) — chapter file frontmatter schema.

### Optional API keys (for export only)

The pipeline does not need any keys for ordinary drafting and
revision — your AI CLI's session auth handles everything. Only the
*export* commands need third-party services:

| Service | Env var | Used by |
|---|---|---|
| fal.ai | `FAL_KEY` | cover art, ornament generation |
| ElevenLabs | `ELEVENLABS_API_KEY` | audiobook generation |

Drop a `.env` file at the root of your series folder — see
[`.env.example`](.env.example) for the shape.

### Optional external tools (for export only)

`autonovel doctor` reports any of these as missing **warnings**, not
errors. You only need them if you want the matching export:

```bash
# Linux / WSL / Chromebook:
sudo apt install tectonic pandoc potrace ffmpeg librsvg2-bin fontconfig

# macOS:
brew install tectonic pandoc potrace ffmpeg librsvg fontconfig
```

| Tool | Used for |
|---|---|
| `tectonic` | PDF typesetting |
| `pandoc` | ePub generation |
| `potrace` | PNG → SVG ornament vectorisation |
| `ffmpeg` | m4b audiobook output |
| `rsvg-convert` | SVG → PDF for print-quality ornaments |
| `fontconfig` | EB Garamond / Bebas Neue lookup |

---

## For developers — working on autonovel itself

This section is only relevant if you want to **modify the autonovel
pipeline**, not just use it to write a novel.

### Repo layout

```
autonovel/
  package.json              # npm shim (forwards to the Python CLI)
  pyproject.toml            # the actual Python package
  bin/autonovel.js          # node wrapper that runs `python -m autonovel.cli`
  commands/                 # /autonovel:* command source — one md per command
  src/autonovel/            # housekeeping Python (CLI, adapters, validators, mechanical, templates)
  docs/                     # user-facing documentation
  tests/
    deterministic/          # Tier 1 — frontmatter, mechanical, adapters, CLI
    contracts/              # Tier 2 — every reads:/writes: backed by command body
    smoke/                  # Tier 3 — opt-in, real runtime invocation, costs money
    fixtures/
      tiny-series-{historical,scifi,literary,mystery,thriller,romance,fantasy,horror}/
      bells-reference/      # Tier-4 regression — populated from the autonovel/bells branch
  CRAFT.md, ANTI-SLOP.md, ANTI-PATTERNS.md   # prompt material consumed by writer/judge
  CLAUDE.md, AGENTS.md, GEMINI.md            # AGENTS/GEMINI symlink to CLAUDE.md
```

### Editable install

```bash
git clone https://github.com/pmilford/autonovel.git
cd autonovel
pip install -e .[test,export]
pytest tests/deterministic tests/contracts -q   # Tier 1 + 2 — fast, free
```

### Project memory and conventions

- [`REWRITE-PLAN.md`](REWRITE-PLAN.md) — the architecture and PR sequence.
- [`STATE.md`](STATE.md) — append-only decisions log + current Tier-1+2
  green count.
- [`ROADMAP.md`](ROADMAP.md) — PR sequence status.
- [`FUTURE-TODOS.md`](FUTURE-TODOS.md) — output-quality / portability /
  testing items deferred past v0.1.0.
- [`CLAUDE.md`](CLAUDE.md) — agent-side conventions (auth policy, tool-name
  translation, preamble/postamble contract). `AGENTS.md` and
  `GEMINI.md` symlink here.

### Test tiers

| Tier | Cost | Run when |
|---|---|---|
| 1 — deterministic | free | every commit |
| 2 — command contracts | free | every commit |
| 3 — smoke | costs (or subscription auth) | manual / pre-merge |
| 4 — Bells regression | costs | manual; gates prompt changes |

See [`docs/testing.md`](docs/testing.md).

### Adding a genre fixture

```bash
autonovel test-fixture new my-western
# Edit the produced fixture + smoke-test stub.
autonovel test-fixture run my-western
```

See [`docs/adding-a-genre-fixture.md`](docs/adding-a-genre-fixture.md).

---

## The Bells production

The **first novel produced through this pipeline**, by NousResearch:

> *The Second Son of the House of Bells*
> 19 chapters · 79,456 words · 6 automated revision cycles ·
> 6 Opus dual-persona review rounds · 24 → 19 chapters through 4
> structural merges · linocut cover (fal.ai Nano Banana 2) · 19
> woodcut chapter ornaments (vectorised) · audiobook with 4,179
> speaker-attributed segments via ElevenLabs.

The Bells production lives on the [`autonovel/bells` branch](https://github.com/pmilford/autonovel/tree/autonovel/bells)
of this repo and is the source of every "gotcha learned in
production" line in [`CLAUDE.md`](CLAUDE.md):

- Don't compress chapters below ~1800 words — they become the new weakest.
- `revise` overshoots brief targets by ~30%.
- Pacing ≈ 7 is a likely ceiling for investigation-heavy plots.
- OVER-EXPLAIN (~32%) and REDUNDANT (~26%) dominate adversarial cuts.
- Chapter renumbering must be by script, never hand-edit.
- The Stability Trap — AI defaults to safe, round-edged endings;
  push toward irreversible change, real cost, mystery.

The voice metadata for every Bells character (NARRATOR through MINOR)
is preserved verbatim in
[`src/autonovel/templates/book/audiobook/voices.yaml.example`](src/autonovel/templates/book/audiobook/voices.yaml.example) — it ships
into every new book scaffolded with `autonovel new-book` so you have
a real production reference next to your own `voices.yaml`.

The Tier-4 regression harness at `tests/fixtures/bells-reference/`
tests changes to `/autonovel:evaluate` against the frozen Bells
chapter scores so prompt drift can't silently degrade what was once
known to work.

---

## License

MIT. The original `NousResearch/autonovel` and `karpathy/autoresearch`
upstreams retain their respective licenses; see those repositories
for terms.
