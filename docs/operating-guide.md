# Operating guide

Day-to-day operation of autonovel: where human input matters and why,
how long each stage takes, concrete workflows for common tasks
(first-pass draft, minor revision, factual fix, major restructure,
adding a plot point), and the boring-but-essential mechanics
(updating tools, recovering from a crash, starting a new book or
series).

This is the doc to read **after** you've finished the install
walkthrough in [`README.md`](../README.md) and **before** you start
your second novel.

---

## 1. Where human input matters, and how much

The pipeline is autonomous in execution but you decide the shape.
Per stage, the minimum-viable input + the recommended-for-quality
input + how long each takes:

| Stage | Minimum input | Recommended input | Your time | Computer time |
|---|---|---|---|---|
| **Seed** (`books/<book>/seed.txt`) | 1 paragraph: pitch + POV + obstacle + change | 6-section guided template (pitch, POV, obstacles, change, period/place, notes) | 5 min minimum, **20–30 min recommended** | – |
| **Foundation review** (world, characters, canon, outline) | Read the produced files; rerun if a stage looks wrong | Skim each generated file; check canon dates and event ledger; rerun the offending stage | 10 min minimum, **30–60 min recommended** | 1–3 min per `gen-*` cycle |
| **Voice discovery** | Accept the AI's pick | Read all 5 trial passages; pick one; optionally rerun for fresh trials | 2 min minimum, **5–10 min recommended** | 2–4 min per run |
| **Per-chapter draft review** | Skim eval score; let pipeline advance if ≥ threshold | Read the chapter; if it surprised you (good or bad) note why | 1 min minimum, **3–5 min recommended** | 2–5 min per chapter draft (Sonnet) |
| **Reader-panel feedback** | Run it; read the headline | Read each persona's full report; mark which complaints you agree with before running revise | 5 min minimum, **15–30 min recommended** | 5–10 min for whole book |
| **Opus review** | Run it once near the end | Iterate review → revise loops until the items become hedged ("perhaps could do") | 5 min minimum, **15–60 min** per round | 5–15 min per pass on whole book |
| **Major decisions** (cut a chapter, add a character, change ending) | Decide; type the sidequest | Decide deliberately; consider impact on canon, outline, downstream chapters | 5–60 min depending on scope | 2–10 min for the sidequest itself |
| **Export** (PDF, ePub, audiobook, cover) | `/autonovel:package` and walk away | Inspect the typeset PDF for orphan/widow lines; tweak `typeset/novel.tex` | 5 min minimum, **30 min recommended** | 30–60 sec PDF; 5–60 min audiobook depending on length |

**Total for a 70k-word novel:** the computer does roughly 4–8 hours
of paid work spread across the run; you spend roughly 4–8 hours of
attention spread across days. Bells took ~a week of part-time
attention.

The single highest-leverage place to invest your time is **the
seed.** A vague seed → a vague book. A specific seed → the AI fills
in confidently, the eval is meaningful, and revisions stay
targeted.

---

## 2. Workflow patterns with concrete examples

For every example below, assume you're in your series root (the
folder containing `project.yaml`) and have launched `claude` /
`codex` / `gemini` from there.

### 2a. First-pass draft (mostly automated)

You've finished the foundation. The eval scored ≥ 7.5. You want
the whole book drafted unattended.

```text
/autonovel:next                        # confirms the next step
/autonovel:draft-pass --chapters 1-19  # walk away — does the full per-chapter loop
                                       # plus the end-of-sweep canon promote
```

For each chapter the sweep runs: **draft → anachronism check →
evaluate → if score < threshold (default 7.0), brief + revise +
re-eval (keeps best) → promote-canon** (so each chapter's
discoveries land in `shared/canon.md` before the next chapter
drafts and reads it). A final `promote-canon` sweep also runs
after the last chapter to catch anything still pending. Disable
either with `--no-promote`.

Add `--deep` and the sweep also runs `reader-panel` and `review`
on the whole book at the end — produces reports (does not
auto-revise from them) and surfaces a flagged-chapters list:

```text
/autonovel:draft-pass --chapters 1-19 --deep   # adds ~10–25 min for the deep passes
```

Realistic time budget on a 19-chapter / 70k-word book:
- Plain `draft-pass`: 2–3 hours unattended.
- `draft-pass --deep`: 2.5–3.5 hours unattended.

Postamble prints a summary table:

```
chapter | draft (words) | anach | eval v1 | eval v2 | final | revised?
--------|---------------|-------|---------|---------|-------|----------
     1  | 3100          | 0     | 7.4     | —       | 7.4   | no
     2  | 2950          | 2     | 6.8     | 7.3     | 7.3   | yes
   …
```

With `--deep`: append a "panel + review flagged chapters X, Y, Z"
block. Your move next is `/autonovel:revision-pass --chapters
X,Y,Z` against the flagged list, or done if nothing was flagged.
**Time you spent watching this happen: zero.** Time skimming the
summary: 5 min.

### 2b. Minor revision (a single chapter feels off)

Chapter 7 came back at 5.8 and reads as flat. You don't want to
revise the whole book — just chapter 7.

```text
/autonovel:adversarial-edit 7          # judge finds 10–20 cuts/rewrites
/autonovel:apply-cuts 7 --types OVER-EXPLAIN REDUNDANT
                                       # mechanical cuts (no LLM)
/autonovel:brief 7 --from auto         # synthesize revision brief
/autonovel:revise 7                    # rewrite per the brief
/autonovel:evaluate --chapter 7        # re-score
```

Time: ~10–15 min of compute, ~5 min reading the brief between
steps to see if you disagree with anything. If you do, edit
`books/<book>/briefs/ch07.md` before running `revise`.

### 2c. Minor factual error (a date is wrong, a name is misspelled)

Research found that Jakob Fugger arrived in Venice in 1478, but
your canon says 1471 and chapter 3 references the 1471 date. Two
fixes:

**For the canon (one source of truth across all books):**

```text
/autonovel:research --from-seed       # writes notes with citations
/autonovel:promote-canon              # research-tagged entries win conflicts
                                      # (the [research:slug] tag does this automatically)
```

`shared/canon.md` now has the corrected fact plus a
`## Superseded <UTC-date>` block recording what changed.

**For the affected chapters:**

```text
/autonovel:check-anachronism 3         # report into edit_logs/
                                       # — does the chapter actually reference the wrong date,
                                       #   or is the contradiction only in canon?
/autonovel:brief 3 --from auto         # if the chapter needs revision
/autonovel:revise 3                    # rewrites chapter 3 with the corrected date
```

For a misspelled character name across the whole book:

```text
/autonovel:rename-character --old Niccolo --new Niccolò
```

**Script-based**, not LLM rename. Word-boundary `sed` across every
chapter, outline, and shared file. Refuses if the change would
overlap a longer word (e.g. won't rename `Ana` if `Anatolia` exists).

### 2d. Adding pictorial plates (maps, paintings, photographs)

Historical fiction (and some non-fiction) wants real images in the
typeset PDF — a period map, a portrait, a trade-route diagram.
`/autonovel:art-import` handles each:

```text
/autonovel:art-import --file ~/Downloads/de_barbari_venice_1500.png \
  --chapter 1 --placement before-chapter \
  --caption "Jacopo de' Barbari, View of Venice, 1500." \
  --attribution "Public domain, via Wikimedia Commons."

/autonovel:art-import --file ~/Downloads/durer_jakob_fugger.jpg \
  --chapter 5 --placement before-chapter \
  --caption "Albrecht Dürer, Portrait of Jakob Fugger the Rich, c. 1518." \
  --attribution "Bayerische Staatsgemäldesammlungen."

/autonovel:art-import --file ~/maps/hanseatic_routes.svg \
  --chapter 9 --placement before-chapter \
  --caption "Principal Venetian–Hanseatic trade routes, late 15th century."

/autonovel:typeset                     # rebuild the PDF with the plates woven in
```

Each invocation copies your image into
`books/<book>/typeset/plates/<slug>.<ext>` and registers it in
`books/<book>/typeset/plates.yaml` with the chapter, placement,
caption, and attribution. Three placements:

- `--placement before-chapter` (default) — **dedicated full-page**
  plate facing the chapter heading. Best for full maps, portraits,
  full paintings.
- `--placement chapter-start` — **inline centered** image just below
  the chapter title. Smaller; no page break. Best for atmospheric
  inserts (a sketch of bagged spices, a small woodcut).
- `--placement after-chapter` — full-page plate after the chapter
  body. Less common.

For a small monochrome insert that should *replace* the AI-generated
chapter ornament rather than add a new page:

```text
/autonovel:art-import --file ~/Downloads/austere_church_woodcut.png \
  --chapter 7 --as ornament
```

`--as ornament` mode drops the file at `books/<book>/art/ornaments/
ch_07.png` (overriding whatever ornament-pipeline produced).

`books/<book>/typeset/plates.yaml` is human-readable; you can edit
it directly to tweak captions, reorder, or remove plates. Re-running
`art-import` with the same `--slug` overwrites the prior entry only
if you pass `--force`.

### 2e. Major change (cut a chapter, change the ending)

Halfway through revision you decide chapter 12 should be cut — its
beats are folded into chapters 11 and 13.

```text
/autonovel:remove-chapter 12          # deletes ch_12.md; renumbers 13→12, 14→13, etc.
                                      # — chapter renumbering is by script, not LLM rename
/autonovel:revision-pass --chapters 11,12   # the new 11 and 12 (formerly 11 and 13)
                                            # need fresh briefs + revises
/autonovel:evaluate --full            # confirm the whole book still scores
```

Or two adjacent chapters that should be one:

```text
/autonovel:merge-chapters --chapters 14,15
```

For a structural ending change — different kind of resolution, not
just a tweak — the cleanest path is:

1. Edit `books/<book>/outline.md` directly to change the final
   chapters' beats.
2. `/autonovel:revise <last-chapter>` — picks up the new beats.
3. `/autonovel:check-anachronism` and `/autonovel:reader-panel`
   to confirm continuity hasn't broken.
4. Address any chapters where the new ending changes what was set
   up — for instance, if the new ending requires a key foreshadowed
   detail in chapter 5, run `/autonovel:foreshadow --plant 5
   --payoff <last>`.

Time: 20–60 min of human thinking, 30–90 min of compute.

### 2f. Adding a plot point retroactively

You've drafted 10 chapters and realise you want to add a subplot —
a minor character secretly poisoning the well — that needs setup
in chapter 2 and payoff in chapter 9.

```text
/autonovel:add-subplot \
  --thread "Eduardo poisons the speziale's well over jealousy" \
  --plant 2 --payoff 9
```

This:
- Edits `books/<book>/outline.md` to add a plant beat in 2 and a
  payoff beat in 9.
- Writes a `## Threads` ledger entry tracking the plant→payoff.
- Does **not** rewrite chapters 2 or 9 — that's the next step.

Then:

```text
/autonovel:revise 2     # incorporate the plant
/autonovel:revise 9     # incorporate the payoff
/autonovel:revision-pass --chapters 3-8    # propagate ripples through middle chapters
```

For a single foreshadow detail (rather than a full subplot):

```text
/autonovel:foreshadow --plant 2 --payoff 9 \
  --thread "the Fugger ledger entry that Tommaso misreads"
```

Same shape, simpler thread.

For a brand-new character mid-book:

```text
/autonovel:add-character --name Eduardo --role apothecary's apprentice
```

…then either let downstream chapters pick him up via
`/autonovel:revise`, or use `/autonovel:deepen-character Eduardo`
to add an unguarded moment that makes him real.

---

## 3. Day-to-day mechanics

### 3a. Updating Claude Code itself

Claude Code self-updates when you invoke it; just relaunch.
Verify the version:

```bash
claude --version
```

If you ever need to manually upgrade (e.g. a release that fixes
something you're hitting), see Anthropic's
[Claude Code install guide](https://docs.claude.com/en/docs/claude-code) — the install method depends on
how you originally installed it (npm, native installer, etc.).

**Where Claude Code keeps state on your machine:**

| Path | What lives there |
|---|---|
| `~/.claude/settings.json` | Your global Claude Code config (model preference, theme, hooks) |
| `~/.claude/commands/autonovel/` | The `/autonovel:*` command files (written by `autonovel install`) |
| `~/.claude/projects/` | Per-project conversation history |
| `<your-series-root>/.claude/settings.json` | Project-local overrides (statusline + permissions, written by `autonovel statusline-setup`) |
| `<your-series-root>/.claude/commands/` | Project-local commands (only used by autonovel's smoke tests; you can ignore) |

If a Claude Code update changes its tool API or settings shape,
re-run `autonovel install` to refresh the command files into the
new shape.

### 3b. Updating autonovel

```bash
cd ~/autonovel              # the autonovel source clone
git pull                    # latest commits
pipx reinstall .            # rebuild the installed package from local source
cd ~/<your-series-root>
autonovel install           # re-render /autonovel:* commands into ~/.claude/commands/autonovel/
                            # — needed any time we ship new commands or change a body
```

Three-line variant when you remember the gist but not the order:

```bash
( cd ~/autonovel && git pull && pipx reinstall . )  &&  autonovel install
```

### 3c. Restarting after a crash, power loss, or kernel reboot

Power off mid-draft → boot back up → continue. autonovel is
designed for this.

```bash
cd ~/<your-series-root>     # whichever folder has project.yaml
ls .autonovel/in-progress.lock 2>/dev/null && echo "lock exists"
```

Then in Claude Code, in the series root:

```text
/autonovel:resume
```

It detects the stale lock from the interrupted command, shows you
what was running, and offers three options:

- **Redo**: re-run the command from scratch (safe; the prior
  attempt's checkpoint is still there).
- **Keep partial**: take whatever the prior attempt actually wrote
  to disk and move on. Useful when a 3,200-word draft made it
  before the crash and you'd rather edit it than redraft.
- **Inspect**: print the prior command, its arguments, and which
  files were partially written, then let you decide.

If `/autonovel:resume` fails or you want to be sure, you can
manually `autonovel rollback` to a checkpoint before the crashed
command:

```bash
autonovel rollback --list           # show recent checkpoints
autonovel rollback --to 2026-04-25T18:32:00Z   # restore a specific one
```

Each `/autonovel:*` command takes a checkpoint at its preamble, so
rolling back to the most recent one undoes only the most recent
command.

### 3d. Starting a new book in the same series

Your series shares world, characters, canon, and the events ledger
across books. Adding a second book reuses all of that:

```bash
cd ~/<series-root>
autonovel new-book the-cartographer --pov Lucia --story-time-range 1492-1502
```

That creates `books/the-cartographer/` with empty seed, voice,
outline, etc. Edit the seed:

```bash
nano books/the-cartographer/seed.txt
```

Then in Claude Code (in the series root):

```text
/autonovel:next        # walks you through voice-discovery + gen-outline for the new book
                       # (gen-world / gen-characters / gen-canon are already done from book one)
/autonovel:draft-pass --chapters 1-12 --book the-cartographer
```

Cross-book continuity is enforced automatically:

- Chapters in `the-cartographer` (1492–1502) cannot leak content
  from `the-inquisitor` chapters (1519–1523) into their drafts —
  story-time gating prevents it.
- Conversely, when you draft `the-inquisitor` chapter 5, the
  drafter has access to `the-cartographer` chapters whose
  story_time is ≤ chapter 5's story_time.
- Inter-book canonical events live in `shared/events.md` — see
  [`docs/multi-book.md`](multi-book.md) for the schema.

### 3e. Starting a new series

A series is the unit of co-evolving lore. A standalone novel is a
series with one book. Choose a series root somewhere outside the
autonovel source clone (a clean parent dir for novel projects):

```bash
mkdir -p ~/novels
cd ~/novels
autonovel new-series the-low-countries --genre historical-fiction
cd the-low-countries
autonovel new-book amsterdam --pov Wolfaert --story-time-range 1648-1652
nano books/amsterdam/seed.txt
autonovel statusline-setup    # wire the per-project statusline + tool permissions
claude                         # launch your runtime in the new series root
```

Then in Claude Code:

```text
/autonovel:next               # foundation gap detector picks up from seed
```

Walks you through `gen-world → gen-characters → voice-discovery →
gen-canon → gen-outline → evaluate-foundation → draft 1`. If
`project.yaml` has a `period` set, the chain prepends
`/autonovel:research --from-seed`.

### 3f. Daily checkpoint: where am I?

Anywhere in your series root:

```bash
autonovel status                    # CLI: phase, scores, last command, lock state
```

Or in Claude Code:

```text
/autonovel:next                     # what to type next
```

Or in your status bar (if you ran `autonovel statusline-setup`):

```
medieval-king-maker · drafting · ch03 · idle  │  sonnet-4-6 · 12% · $0.42
```

These are your three sources of truth. They never disagree.

---

## 4. Is there a web console / GUI?

**Today: no.** autonovel is CLI + the runtime's chat UI. Status
visibility lives in:

- `autonovel status` — full report (phase, scores, lock, log tail).
- `autonovel statusline` — one-line summary in the runtime's status
  bar (after `autonovel statusline-setup`). Updates only when Claude
  Code re-renders the bar, which it does on user input — not on a
  timer. During a long sweep the chapter count therefore *appears*
  frozen between prompts; the bar tags the active command name as
  `◍ <command>` while the lock is held so you can tell what's
  actually running. If the context-percentage half is missing on
  your Claude Code version (the JSON schema has changed across
  releases), enable a one-shot diagnostic dump: set
  `AUTONOVEL_STATUSLINE_DEBUG=1` in your shell, hit Enter once
  inside Claude Code, then read
  `~/.autonovel-statusline-debug.log` — it captures the raw stdin
  payload Claude Code is sending so a missing schema path can be
  added.
- `cat .autonovel/command-log.jsonl` — append-only log of every
  command that ran, with timestamps and write-paths.
- `git log --oneline` — every successful command's
  preamble/postamble takes a checkpoint, so the git history is the
  paper trail for the project.

If you remember NousResearch's earlier autonovel having a richer
read-only console (file artifact browser + live progress), that
piece did not port to this rewrite — autonovel here is the
markdown-commands-into-AI-CLI architecture; the runtime's chat is
the user surface. A read-only TUI / web dashboard for "what's the
state of every book in every series" is in
[`FUTURE-TODOS.md`](../FUTURE-TODOS.md) as a near-term item but
not yet implemented.

---

## 5. Installing PDF / ePub / audiobook tools

The autonovel package itself doesn't include the typesetting,
SVG-vectorisation, or audio-conversion tools — those are
language-agnostic OS-level binaries you install via your package
manager. Default installs (npm / pipx) bring nothing in this
section; you add only what you need.

`autonovel doctor` reports anything missing as a **warning** (not
an error). You can drift through drafting and revision without any
of these. Install only what you need, when you need it.

### 5a. PDF typesetting (`/autonovel:typeset`)

Required: **`tectonic`** (TeX engine that auto-fetches packages).
Optional: **`rsvg-convert`** (for vector ornaments at print quality).

```bash
# Linux / WSL Ubuntu / Chromebook Linux container:
sudo apt update
sudo apt install -y tectonic librsvg2-bin

# macOS (with Homebrew):
brew install tectonic librsvg

# Verify:
tectonic --version          # should print the version
rsvg-convert --version
```

Note for ChromeOS users specifically: tectonic is in the standard
Debian repos, so the `apt install` path works inside the Linux
development environment.

### 5b. ePub generation (`/autonovel:typeset --epub-only`)

Required: **`pandoc`** (universal document converter).

```bash
# Linux / WSL Ubuntu / Chromebook:
sudo apt install -y pandoc

# macOS:
brew install pandoc

# Verify:
pandoc --version
```

### 5c. Cover and ornament rendering (`/autonovel:cover-*`, `/autonovel:art-vectorize`)

Required: **`fontconfig`** (font lookup), **`potrace`** (PNG → SVG).
Plus the Python `Pillow` package (in the autonovel `[export]`
extra).

```bash
# Linux / WSL / Chromebook:
sudo apt install -y fontconfig potrace

# macOS:
brew install fontconfig potrace

# Python image library (one-time):
pipx inject autonovel pillow
```

EB Garamond and Bebas Neue are the cover fonts the templates
reference. Install them too:

```bash
# Linux / WSL / Chromebook:
sudo apt install -y fonts-ebgaramond fonts-bebas-neue

# macOS (download manually from Google Fonts):
# Open https://fonts.google.com/specimen/EB+Garamond → Download
# Open https://fonts.google.com/specimen/Bebas+Neue → Download
# Double-click each .ttf to install.
```

### 5d. Audiobook generation (`/autonovel:audiobook-*`)

Required: **`ffmpeg`** (audio assembly + m4b output). Plus the
Python `pydub` package and an ElevenLabs API key
(`ELEVENLABS_API_KEY` in `.env`).

```bash
# Linux / WSL / Chromebook:
sudo apt install -y ffmpeg

# macOS:
brew install ffmpeg

# Python audio library:
pipx inject autonovel pydub

# ElevenLabs key — paste into <series-root>/.env
echo 'ELEVENLABS_API_KEY=sk_...' >> .env

# Verify:
ffmpeg -version
```

### 5e. All-at-once for the impatient

```bash
# Linux / WSL / Chromebook (one shot):
sudo apt update && sudo apt install -y tectonic pandoc potrace ffmpeg \
    librsvg2-bin fontconfig fonts-ebgaramond fonts-bebas-neue
pipx inject autonovel pillow pydub

# macOS (one shot):
brew install tectonic pandoc potrace ffmpeg librsvg fontconfig
pipx inject autonovel pillow pydub
# (then download EB Garamond + Bebas Neue from Google Fonts manually)
```

After install, verify:

```bash
autonovel doctor
```

The export-tools section should now report no warnings for the
tools you just installed.

### 5f. None of this for "just write the book" mode

If you only want to draft and revise — no PDF, no cover, no
audiobook — you don't need any of section 5. autonovel is fully
usable on a fresh pipx install for the entire writing pipeline up
to and including `/autonovel:reader-panel` and
`/autonovel:review`. Export tools are a separate decision you make
when you're ready to publish.

---

## See also

- [`README.md`](../README.md) — install + quickstart.
- [`docs/commands.md`](commands.md) — every `/autonovel:*` command.
- [`docs/multi-book.md`](multi-book.md) — coordinating books in one series.
- [`docs/writing-a-historical-series.md`](writing-a-historical-series.md) — 12-step end-to-end on a Renaissance series.
- [`docs/troubleshooting.md`](troubleshooting.md) — common errors and fixes.
- [`docs/lessons-from-author-testing.md`](lessons-from-author-testing.md) — defensive code rationale: why certain decisions were made.
