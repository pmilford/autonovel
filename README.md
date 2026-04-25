# autonovel

An autonomous novel-writing pipeline that drops a `/autonovel:*` command
suite into your AI CLI runtime — Claude Code, OpenAI Codex, or Gemini
CLI — and turns a seed concept into a finished novel: manuscript,
typeset PDF, ePub, cover art, audiobook, landing page.

The runtime owns the model, the auth, and the file I/O. autonovel just
ships markdown commands and a small Python housekeeping CLI.

Inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch):
the same modify → evaluate → keep/discard loop, applied to fiction.

**First novel produced:** *The Second Son of the House of Bells* — 19
chapters, 79,456 words. See the `autonovel/bells` branch.

---

## Install

You need:

1. **An AI CLI runtime** on `$PATH`. Any of:
   - [Claude Code](https://docs.claude.com/en/docs/claude-code) — `claude`
   - [OpenAI Codex CLI](https://github.com/openai/codex) — `codex`
   - [Gemini CLI](https://github.com/google-gemini/gemini-cli) — `gemini`

2. **Python ≥3.12** for the housekeeping CLI.

3. **Optional external tools** (only if you want PDF / SVG / m4b export):
   - `tectonic` (PDF), `pandoc` (ePub), `potrace` (SVG), `ffmpeg` (m4b),
     `rsvg-convert` (vector→PDF), `fontconfig` (font lookup).
   - `autonovel doctor` reports any missing as warnings.

4. **Optional API keys** for export (`.env`):
   - `FAL_KEY` for cover art and ornaments.
   - `ELEVENLABS_API_KEY` for audiobook generation.

### Install paths (pick one)

```bash
# Option A — npm install -g (recurring use)
npm install -g autonovel
autonovel install

# Option B — npx (one-off / pinned to a project)
npx autonovel install

# Option C — pip / pipx (no Node required)
pipx install autonovel
autonovel install
```

`autonovel install` auto-detects which AI CLIs you have and drops the
command files into each runtime's expected location. Pin one with
`autonovel install --only claude|codex|gemini`.

> The npm shim at `bin/autonovel.js` delegates to the Python CLI. If
> you used Option A or B, the shim runs the bundled Python source via
> `PYTHONPATH`. If you used Option C, the shim finds the system-installed
> module. Either way, `autonovel <subcommand>` is the one entry point.

---

## Quick start

```bash
# 1. Scaffold a series.
autonovel new-series renaissance-europe --genre historical-fiction
cd renaissance-europe
autonovel new-book the-inquisitor --pov Tommaso --story-time-range 1519-1523

# 2. Edit the seed.
$EDITOR books/the-inquisitor/seed.txt

# 3. Open the series in your runtime and run commands.
claude    # or `codex` or `gemini`

> /autonovel:gen-world
> /autonovel:gen-characters
> /autonovel:gen-canon
> /autonovel:voice-discovery --book the-inquisitor
> /autonovel:gen-outline --book the-inquisitor
> /autonovel:draft 1 --book the-inquisitor
> /autonovel:evaluate --chapter 1 --book the-inquisitor
> /autonovel:run-pipeline --books the-inquisitor
```

For an end-to-end walkthrough on a 3-book historical series, see
[`docs/writing-a-historical-series.md`](docs/writing-a-historical-series.md).

---

## How it works

A novel in autonovel is five co-evolving layers, plus a cross-cutting
canon:

```
Layer 5: voice.md          HOW we write
Layer 4: world.md          WHAT exists
Layer 3: characters.md     WHO acts
Layer 2: outline.md        WHAT HAPPENS
Layer 1: chapters/ch_NN.md THE ACTUAL PROSE
Cross:   canon.md          WHAT IS TRUE
```

Changes propagate both downward (lore change → outline → chapter
rewrite) and upward (writing reveals a gap → update lore → check
downstream). State for in-flight commands lives in `.autonovel/`.

### The `/autonovel:*` command suite

Every command is a markdown file under `commands/` with YAML
frontmatter declaring its model tier (heavy / standard / light), the
files it reads, the files it writes, and which generic tools it needs
(`file_read`, `file_write`, `bash`, `task`, `web_search`, `web_fetch`).
The adapter for your runtime translates these into the runtime's own
tool names and writes the command file into the runtime's expected
path.

Three categories:

- **Foundation:** `gen-world`, `gen-characters`, `gen-outline`,
  `voice-discovery`, `gen-canon`, `research`.
- **Drafting & revision:** `draft`, `evaluate`, `adversarial-edit`,
  `apply-cuts`, `reader-panel`, `review`, `brief`, `revise`,
  `check-anachronism`.
- **Export:** `art-*`, `cover-*`, `audiobook-*`, `typeset`, `landing`,
  `package`.

Plus 11 sidequests (`shorten`, `lengthen`, `revoice`,
`split-chapter`, `merge-chapters`, `reorder`, `remove-chapter`,
`deepen-character`, `add-subplot`, `foreshadow`, `rename-character`).

Full reference: [`docs/commands.md`](docs/commands.md).

### Multi-book series

A series shares world, characters, canon, and an inter-book event
ledger. Each book owns its outline, voice, chapters, and pending
canon. The context loader gates spoilers by `story_time` so a book set
in 1521 cannot leak content from a sibling book set in 1525 into its
draft prompt.

See [`docs/multi-book.md`](docs/multi-book.md).

### Two immune systems against AI slop

- **Mechanical** (`src/autonovel/mechanical/`): regex scanners for
  banned vocabulary (`delve`, `tapestry`, …), em-dash overuse,
  sentence-length uniformity, fiction clichés, period-bans.
- **LLM judge** (`/autonovel:evaluate`): a model distinct from the
  writer scores prose, voice, character, beat coverage. Tier mapping
  via `project.yaml`.

### Genre fixtures

Tier-3 smoke tests run against eight per-genre fixture series under
`tests/fixtures/`. Add your own with
`autonovel test-fixture new <genre>` — see
[`docs/adding-a-genre-fixture.md`](docs/adding-a-genre-fixture.md).

---

## Housekeeping CLI

```bash
autonovel new-series <name> [--genre <name>]
autonovel new-book <name> --series <path> [--pov <name>] [--story-time-range <START-END>]
autonovel status [--series <path>]
autonovel doctor [--series <path>] [--fix]
autonovel rollback [--series <path>] [--list | --to <timestamp>]
autonovel install [--only claude|codex|gemini] [--path <dir>]
autonovel uninstall [--only claude|codex|gemini]
autonovel test-fixture new <name> [--genre <name>]
autonovel test-fixture list
autonovel test-fixture run <name>
```

`autonovel doctor` checks Python deps + external CLI tools and reports
which `/autonovel:*` commands are unavailable as a result. Missing
external tools are warnings, not errors — a user who only drafts and
revises does not need `tectonic` or `pandoc`.

---

## Documentation

- [`docs/commands.md`](docs/commands.md) — every `/autonovel:*` command, per tier and context-mode.
- [`docs/series-layout.md`](docs/series-layout.md) — `shared/` vs `books/`, frontmatter contract.
- [`docs/multi-book.md`](docs/multi-book.md) — story-time gating, events ledger, promote-canon.
- [`docs/testing.md`](docs/testing.md) — the four test tiers and how to run them.
- [`docs/adding-a-genre-fixture.md`](docs/adding-a-genre-fixture.md) — extending the smoke matrix.
- [`docs/writing-a-historical-series.md`](docs/writing-a-historical-series.md) — end-to-end walkthrough.
- [`docs/chapter-frontmatter.md`](docs/chapter-frontmatter.md) — chapter file frontmatter schema.
- [`docs/pipeline-history.md`](docs/pipeline-history.md) — archived `PIPELINE.md` from the Bells production.

Reference docs consumed by writer/judge prompts:

- [`CRAFT.md`](CRAFT.md) — craft education (plot, character, world, prose).
- [`ANTI-SLOP.md`](ANTI-SLOP.md) — word-level AI-tell detection.
- [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) — structural AI-pattern detection.

The plan-of-record:

- [`REWRITE-PLAN.md`](REWRITE-PLAN.md) — full architecture + PR sequence.
- [`STATE.md`](STATE.md) — append-only decisions log + current test status.
- [`ROADMAP.md`](ROADMAP.md) — forward-looking todos.

---

## License

MIT.
