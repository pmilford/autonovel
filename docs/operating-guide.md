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

## 0. How the editing commands relate

The single most-asked question after a first-pass draft. **Read
this section first if you're confused about which of `draft`,
`draft-pass`, `revise`, `revision-pass`, `brief`, `evaluate`,
`review`, or `reader-panel` to run when.** Everything else in this
doc assumes you've internalised this layout.

### The four roles

Every editing command falls into one of four roles:

| Role | What it does | Scope | Modifies prose? |
|---|---|---|---|
| **Atomic** | Operate on ONE chapter at a time. | 1 chapter | Some yes, some no |
| **Sweep** | Loop the atomic commands across MANY chapters in one shot. | N chapters | Yes (delegates to atomic) |
| **Whole-book reviewer** | Read the whole book and write a REPORT. Never modifies prose. | Whole book | **No** |
| **Mechanical helper** | Deterministic regex / scanner / file-mover. Feeds evidence into other commands. | Varies | Sometimes |

### The commands by role

| Command | Role | One-line summary |
|---|---|---|
| `/autonovel:draft N` | Atomic | Write chapter N from outline + voice + canon. |
| `/autonovel:evaluate --chapter N` | Atomic | Score chapter N. Writes `eval_logs/chNN_eval.json`. |
| `/autonovel:brief N` | Atomic | Synthesise a per-chapter revision plan from whatever evidence is on disk (eval, cuts, panel, review). Writes `briefs/chNN.md`. **Does NOT rewrite prose** — just plans. |
| `/autonovel:revise N` | Atomic | Rewrite chapter N **per the brief at `briefs/chNN.md`**. Refuses if the brief is missing. |
| `/autonovel:adversarial-edit N` | Atomic helper | Find 10–20 cut/rewrite candidates in chapter N. Writes `edit_logs/chNN_cuts.json`. |
| `/autonovel:apply-cuts N` | Atomic helper | Deterministically remove flagged passages (no LLM). |
| `/autonovel:check-anachronism N` | Atomic helper | Period-vocabulary + LLM semantic anachronism scan. Writes `edit_logs/chNN_anachronism.md`. |
| `/autonovel:draft-pass` | Sweep | "Write the rest of the book." Per chapter: draft → anachronism → evaluate → if low, brief + revise + re-eval → promote-canon. With `--deep`: also runs reader-panel + review at end. |
| `/autonovel:revision-pass` | Sweep | "Improve these chapters." Per chapter: anachronism → brief → revise → evaluate → promote-canon. |
| `/autonovel:reader-panel` | Whole-book reviewer | Four-persona panel (Editor / Genre Reader / Writer / First Reader). Writes `edit_logs/reader_panel.json`. **Does NOT modify chapters.** |
| `/autonovel:review` | Whole-book reviewer | Opus dual-persona deep review (literary critic + professor of fiction). Writes `edit_logs/opus_review.md`. **Does NOT modify chapters.** |
| `/autonovel:chapter-summary` | Mechanical helper | One-line-per-chapter overview table — Date / POV / Score / Words / Cast / Plot (with location prefix). Pure mechanical, no LLM. The right tool for "which chapters happen in <date range>?" or "where does <character> appear?" before a revision pass. **Does NOT modify chapters.** |

### The crucial insight: `brief` is the synthesiser

`brief` is the bridge between **evidence on disk** (eval logs,
cuts, anachronism reports, reader-panel findings, review findings,
custom-rubric flags from `voice.md` Part 3) and **a plan the
rewrite can act on**. It reads everything available, picks the
load-bearing items, and writes one focused per-chapter `briefs/chNN.md`.

`revise` then reads `briefs/chNN.md` and rewrites the chapter to
match. **`revise` won't run without a brief** — that's deliberate;
it's the reason rewrites stay targeted instead of drifting.

You almost never call `brief` and `revise` directly. You call a
sweep that calls them for you.

### Who calls whom (the automation graph)

```
                ┌───────────────────────────────────────────────────┐
                │  draft-pass (sweep over N chapters, default sequential)
                │      ├─ per chapter:
                │      │    draft → anachronism → evaluate
                │      │    if score < threshold:
                │      │        brief + revise + re-eval (keep best)
                │      │    promote-canon (per chapter)
                │      └─ with --deep:
                │            reader-panel + review on whole book at END
                └───────────────────────────────────────────────────┘

                ┌───────────────────────────────────────────────────┐
                │  revision-pass (sweep over N chapters)
                │      └─ per chapter:
                │            anachronism → brief → revise → evaluate
                │            promote-canon (per chapter)
                └───────────────────────────────────────────────────┘

                ┌───────────────────────────────────────────────────┐
                │  reader-panel  (whole book → REPORT, no rewrites)
                │  review        (whole book → REPORT, no rewrites)
                └───────────────────────────────────────────────────┘
                        │
                        │  reports land in edit_logs/
                        ▼
                 You then run revision-pass
                 (which calls brief → revise → evaluate per chapter,
                  with brief picking up the panel + review evidence
                  along with the existing eval + cuts).
```

### "I ran draft-pass --all, then review, then reader-panel — did I need to run brief?"

**Short answer: no, but you're not done.**

`draft-pass` already ran `brief` + `revise` for any chapter whose
draft scored below threshold. Every chapter ended at a score above
threshold (or marked low, with a recorded brief) by the time the
sweep finished.

`review` and `reader-panel` then produced **reports**. They wrote
findings to `edit_logs/reader_panel.json` and
`edit_logs/opus_review.md`. **They did not touch any chapter.**

To act on those reports — to actually rewrite the chapters they
flagged — your next move is:

```text
/autonovel:revision-pass --chapters <flagged>
```

Pass the chapter list the panel + review surfaced (the `--deep`
postamble names them). `revision-pass` walks each one and calls
`brief` (which now sees the new panel + review evidence on disk
and folds it in), then `revise` (which rewrites against the
brief), then `evaluate` (re-scores). One sweep — no manual
`brief` calls needed.

If you want surgical control over a single chapter (you read the
panel report and disagree with most of it but agree on chapter
12), use the per-chapter atomic flow:

```text
/autonovel:brief 12 --from auto      # write the brief; hand-edit briefs/ch12.md if needed
/autonovel:revise 12                 # rewrite per the brief
/autonovel:evaluate --chapter 12     # re-score
```

### The minimal end-to-end flow on a fresh book

```text
# Foundation (run /autonovel:next; do each step it suggests)
/autonovel:gen-world
/autonovel:gen-characters
/autonovel:voice-discovery --book <book>
/autonovel:gen-canon
/autonovel:gen-outline --book <book>
/autonovel:evaluate --phase foundation --book <book>

# First-pass draft (one command, walks away)
/autonovel:draft-pass --chapters 1-19 --deep    # --deep adds review + reader-panel at end

# Act on the deep-pass reports
/autonovel:revision-pass --chapters <flagged-from-deep-pass>

# (Repeat the previous two steps until reports are clean.)

# Set the title, write the front matter, typeset
/autonovel:title --book <book>           # propose / pick / set title + author
/autonovel:introduction --book <book> --from both   # preface (you write) + intro (AI drafts)
/autonovel:typeset --book <book>         # PDF + ePub
```

That's the whole story. `draft` and `revise` and `brief` and
`evaluate` exist for surgical work; `draft-pass` and
`revision-pass` exist because you almost always want the loop, not
the atoms.

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

> If you're unclear how `draft-pass` relates to `draft`, `revise`,
> `brief`, `revision-pass`, `review`, and `reader-panel`, **read
> [§0 first](#0-how-the-editing-commands-relate)** — that section
> is the conceptual map for everything below.

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

### 2b.1. Late research, woven lightly into existing chapters

You finished a revision pass. Then you realised you wanted deeper
research on a specific topic — Venice politics + trade in the
1479-1500 window when Jakob Fugger was there, say. You don't want
to redraft anything; you want the chapters where Fugger appears
to carry richer period detail, but their plot, dialogue, scene
shapes, and voice should stay exactly as they are.

Three commands, in order:

```text
# 1. Targeted research (writes notes to shared/research/notes/<slug>.md)
/autonovel:research "Venice politics and trade 1479-1500"
```

The notes file lands at
`shared/research/notes/venice-politics-and-trade-1479-1500.md`
with `## Material detail`, `## People and institutions`, and a
`## Sources` block carrying `[shortname]` citations. Read it once;
make sure it actually says what you wanted.

```text
# 2. Identify chapters where the research is relevant.
#    Easiest path: grep your chapter files for the topic's main names.
ls books/<book>/chapters/ch_*.md | xargs grep -l Fugger
# →  books/<book>/chapters/ch_05.md
#    books/<book>/chapters/ch_08.md
#    books/<book>/chapters/ch_12.md
```

Or scan the outline if your chapter files don't quote the names
verbatim yet. Aim for the ≤6 chapters where the research naturally
belongs — forcing it elsewhere just produces tone shifts.

```text
# 3. Sweep those chapters with --enrich-with pointing at the notes.
/autonovel:revision-pass --chapters 5,8,12 \
    --enrich-with shared/research/notes/venice-politics-and-trade-1479-1500.md
```

For each chapter, `revision-pass` runs the standard loop
(anachronism → brief → revise → evaluate → promote-canon). The
`--enrich-with` flag passes through to each chapter's brief. The
brief considers whether the research is relevant to *this*
chapter; when it is, it adds an `## Enrichment from research`
block with **1-2 specific period details per relevant scene**
(named scene index, named detail, the `[shortname]` citation,
plus an explicit "do NOT change plot, dialogue, voice, scene
structure" guard). Chapters where the research doesn't fit (the
research is a brush, not a chisel) get briefs without the
enrichment block — they pass through with whatever revisions the
standard loop wanted.

Why this works:
- The brief is the bridge — it decides which scenes get
  enriched and which stay alone, based on the chapter's actual
  content, not blanket find-and-replace.
- The "do NOT change" guards in the enrichment block keep the
  rewrite light. Without them, `revise` would re-write the whole
  chapter, which is the opposite of what you want post-revision.
- The research notes also carry their own `## Candidate Canon
  Entries` section — concrete dated facts (e.g. "Fugger arrived
  in Venice 1478 [bib]") that the per-chapter `promote-canon`
  step folds into `shared/canon.md` at the end of each chapter's
  loop. So the research's *facts* land in canon (and supersede
  any contradictory entries because of the `[research:slug]` tag)
  while the research's *texture* lands in prose.

Surgical alternative for a single chapter: same flag works on
`brief` directly:

```text
/autonovel:brief 8 --from auto \
    --enrich-with shared/research/notes/venice-politics-and-trade-1479-1500.md
/autonovel:revise 8
/autonovel:evaluate --chapter 8
```

When NOT to use this:
- For sweeping period research at the start of a project, use
  `/autonovel:research --from-seed` instead — it auto-derives
  topics from the seed and auto-pipes facts into pending_canon.
  `--enrich-with` is for *late* research on chapters that are
  already revised.
- For a wrong fact (canon says 1471, research says 1478), the
  fact lands in canon via promote-canon; you don't need
  `--enrich-with` for that. Use it when you want *texture* —
  named officials, building details, period vocabulary, the
  weight of a coin in the right currency — that the original
  draft generalised.

Time: ~2-3 min per affected chapter (the standard revision-pass
budget). The light-touch constraint keeps it predictable.

#### After the sweep — the closer

A multi-chapter revision pass (with or without `--enrich-with`)
substantively changes the manuscript and the canon. Don't stop at
"the sweep finished" — there's a short, named verify-then-review
sequence that catches the things a sweep can silently break:

1. **Read the score deltas in the postamble** *(2 min, attention)*.
   Per-chapter line ends in `eval: <prev> → <new> (Δ ±X.X) |
   canon: +<P>`. Two flags worth acting on:
   - **Negative Δ** on any chapter = the rewrite made it worse.
     Re-run *that one chapter* without the enrichment flag:
     `/autonovel:revision-pass --chapters <NN>`. The brief drops
     the enrichment block and reconsiders the rewrite from
     cuts/eval evidence alone.
   - **canon: +P where P > 0** = research-derived facts landed
     in `shared/canon.md`. End-of-sweep promote-canon also ran;
     anything *still* in `pending_canon.md` is a conflict that
     needs human resolution — see §2c below.

2. **Check `books/<book>/pending_canon.md`** *(2 min if any conflicts)*.
   If the file says `no new facts`, you're done with canon. If
   it has `# Conflicts — resolve before next promote-canon`,
   open it and follow the HTML-comment instruction block at the
   top (three labelled paths). Re-run `/autonovel:promote-canon`
   after editing.

3. **Re-run reader-panel + review on the revised book**
   *(15-30 min compute, 30 min reading)*.
   You changed many chapters; any prior `reader_panel.json` and
   `opus_review.md` describe the pre-revision book and are now
   stale. Re-running gives you a fresh flagged-chapter list:

   ```text
   /autonovel:reader-panel --book <book>
   /autonovel:review --book <book>
   ```

   Both are whole-book reviewers (see §0) — they write reports,
   don't modify chapters. The chapters you just revised should
   now be stronger; chapters that *weren't* revised may look
   weaker by comparison, which is itself a useful signal pointing
   at next round's targets.

4. **Commit to your GitHub backup** *(1 min)*. A substantive
   revision is the right cadence for a snapshot:

   ```bash
   cd ~/<series-root>
   git add . && git commit -m "Research enrichment pass: chapters <list>" && git push
   ```

   Recipe + `.gitignore` template in §3e.1. Skip if your novel
   isn't yet backed up — set up the private repo first.

5. **(Optional) Typeset and read a few chapters in PDF form**
   *(1 min compute, 5-15 min reading)*.

   ```text
   /autonovel:typeset --book <book>
   ```

   Open `books/<book>/typeset/<book>_latest.pdf` and read 2–3
   of the chapters you just enriched end-to-end. Reading on the
   page catches texture problems the LLM judges miss — a name
   that came in too heavy, a period detail that breaks voice, a
   citation that reads as didactic. Cheap, safe, read-only
   against chapter prose.

6. **Decide: another revision pass on the panel/review flagged
   chapters?**

   ```text
   /autonovel:revision-pass --chapters <flagged-list>
   ```

   No `--enrich-with` this time *unless* you have new research.
   If nothing was flagged, you're done with this round — move
   on to `/autonovel:title`, `/autonovel:introduction`,
   `/autonovel:typeset`, `/autonovel:package`.

The same closer applies to a non-`--enrich-with` revision-pass —
the verify → panel-review → backup → decide loop is what closes
*every* multi-chapter rewrite, not just enrichment ones. §2a's
first-pass recipe already names this implicitly ("Your move next
is `/autonovel:revision-pass --chapters X,Y,Z` against the flagged
list, or done if nothing was flagged"); this section names it
explicitly because §2b.1 readers come here from a different
mental model (they were doing a research integration, not a
quality pass) and shouldn't have to chase the closer through §2a.

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

#### What if `/autonovel:promote-canon` reports conflicts?

When the same `pending_canon.md` entry contradicts an existing
line in `shared/canon.md` (or `world.md` / `characters.md`),
`/autonovel:promote-canon` does NOT silently merge. It writes the
contradicting entries back to `books/<book>/pending_canon.md`
under a `# Conflicts — resolve before next promote-canon`
header, and each conflict gets its own `## Conflict N` block.

Open `books/<book>/pending_canon.md` and read the HTML-comment
block at the top — it contains step-by-step instructions for the
three resolution paths (accept the new fact / reject it / both
are wrong). Each `## Conflict N` block tells you exactly which
file the contradicting line lives in, so you know where to edit.

The short version:

- **Accept the new fact** (research-derived dates are usually
  this case): edit the file named in `Existing canon (in: ...)`,
  replace the old line with the new one, delete the `## Conflict
  N` block from `pending_canon.md`, re-run `/autonovel:promote-canon`.
- **Reject the new fact** (a chapter hallucinated something the
  canon already settles): delete the `## Conflict N` block; the
  candidate is dropped. Optionally `/autonovel:revise` the chapter
  named under `Source` so the wrong fact stops coming back.
- **Both wrong**: edit the canonical file to the correct value,
  delete the `## Conflict N` block.

Re-run `/autonovel:promote-canon` after editing. Resolved
conflicts disappear; unresolved ones come back flagged with the
same instructions. There is no `--force-merge` mode by design —
the human decision lives in this loop.

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

**Important:** `autonovel install` only overwrites command files in
your runtime's directory (e.g. `~/.claude/commands/autonovel/`). It
**does not touch your book content** — your `books/<book>/voice.md`,
`books/<book>/chapters/`, `shared/canon.md`, eval logs, briefs, and
everything else under your series root are completely safe across
upgrades. Re-installing the commands is how you *pick up* new
features (e.g. the per-book Custom rubric, per-character voice
fingerprints, irreversible-change scorer, scene-beat coverage that
shipped 2026-04-25); your novel never gets clobbered.

**Typeset templates need a separate refresh.** `autonovel install`
does not touch `<series-root>/typeset/novel.tex` (or other typeset
template files), because those were copied into your series at
`autonovel new-series` time and you might have hand-edited them.
When a fix lands in the package's typeset templates — e.g. the
2026-04-25 PDF running-header fix and the 2026-04-28 chapter-title
fix that together stop the first sentence of each chapter being
used as an "alternating page header" — pull it into your series with:

```bash
autonovel refresh-templates              # default: only typeset/
autonovel refresh-templates --dry-run    # preview; writes nothing
```

The command only touches files that exist in the package template;
your local-only files (custom macros, hand-tuned overrides) are
preserved and listed under `local-only (preserved)` in the report.
Pass `--only typeset --only shared` to also pull research seeds /
shared template updates.

### 3b.1. Upgrading an existing book to use new voice.md sections

When autonovel ships new voice.md surfaces (Parts 3 and 4 shipped
2026-04-25 — Custom rubric and Per-character voice fingerprints),
your existing book's `voice.md` won't have them yet. The safe
upgrade path:

```bash
# 1. Pull the new autonovel and reinstall commands (see §3b above).
( cd ~/autonovel && git pull && pipx reinstall . )  &&  autonovel install

# 2. Inside Claude Code, in your series root:
/autonovel:voice-discovery --book <book> --upgrade
```

`--upgrade` is the load-bearing flag here. It:

- **Preserves Parts 1 and 2 verbatim** — your hand-tuned voice
  fingerprint is never overwritten.
- **Appends the Part 3 placeholder** (Custom rubric) if it isn't
  already present. You then hand-edit Part 3 to add book-specific
  scoring rules — see the placeholder comment for examples.
- **Drafts Part 4** (Per-character voice fingerprints) from
  `shared/characters.md` if the cast count is ≥3.

Without `--upgrade`, voice-discovery refuses to re-run on a
populated voice.md (because it would otherwise regenerate Part 2
and lose your work). Use `--force` only when the prior voice.md is
junk and you genuinely want a clean re-derive.

### 3b.2. Generating a PDF and ePub

The fastest "I want to see the book typeset" sequence, after the
tools in §5a/§5b are installed:

```bash
# 1. Inside Claude Code, in your series root:
/autonovel:typeset --book <book>
```

That single command produces:

- `books/<book>/typeset/<book>.pdf` (via tectonic)
- `books/<book>/typeset/<book>.epub` (via pandoc, when pandoc is
  installed; silently skipped if not)

If you only want one or the other:

```text
/autonovel:typeset --book <book> --pdf-only
/autonovel:typeset --book <book> --epub-only
```

Pre-flight: run `autonovel doctor` (in the series root) first.
Missing `tectonic` or `pandoc` show as **WARNING** lines with the
fix command — install whatever you need, re-run `doctor` until the
warning for your target tool is gone, then run typeset.

You can run typeset between revision passes purely as a "what does
the book look like right now?" check — it doesn't modify the
chapters, only writes typeset artifacts under
`books/<book>/typeset/`. Safe to interrupt and re-run.

For cover art (`/autonovel:cover-print`), audiobook
(`/autonovel:audiobook-*`), and chapter ornaments
(`/autonovel:art-vectorize`), see §5c–§5d for the tool prerequisites
and the per-command help inside Claude Code.

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

### 3e.1. Backing up your novel to GitHub (private repo)

**Important:** your novel data — `~/<series-root>` — is NOT
backed up anywhere unless you explicitly set up a backup. The
autonovel codebase being on GitHub does not back up your book; the
two live in separate directory trees. A Chromebook crash, an
accidental `rm -rf`, or a corrupted Linux container loses your
book if the only copy is local.

The recommended backup is a private GitHub repo. Free for personal
use, version history of every revision, restorable to any new
machine in one `git clone`.

**One-time setup** (run from your series root):

```bash
cd ~/<series-root>            # the folder with project.yaml

# Quick sanity check — is this already a git repo backed up somewhere?
git remote -v 2>/dev/null
# If `origin  https://github.com/...` prints, you're already backed up.
# If nothing prints, continue below.

# Initialise a git repo at the series root (idempotent — safe to
# re-run on an already-initialised tree).
git init
git branch -M main

# Copy autonovel's recommended .gitignore template if your series
# doesn't have one yet (or has the older minimal version).
# The template excludes the bulk regenerables (checkpoints,
# typeset artefacts, audiobook MP3s, LaTeX intermediates) but
# commits everything that costs work to recreate (chapters,
# briefs, eval logs, voice, canon, cover art, project.yaml).
cp ~/code/autonovel/src/autonovel/templates/series/.gitignore .gitignore
# Or if you installed via pipx and don't have the source clone:
# pipx-install path:
# cp ~/.local/share/pipx/venvs/autonovel/lib/python*/site-packages/autonovel/templates/series/.gitignore .gitignore

# First snapshot.
git add .
git commit -m "Initial backup $(date +%Y-%m-%d)"

# Push to a NEW PRIVATE GitHub repo. You need the `gh` CLI for
# this one-shot creation (`sudo apt install gh` on Chromebook /
# Debian; `brew install gh` on macOS). One-time `gh auth login`
# first if you haven't.
gh repo create my-novel-backup --private --source=. --remote=origin --push
```

After this, your novel lives at `https://github.com/<you>/my-novel-backup`
as a private repo — only you can see it.

**Daily / per-session use** (after the one-time setup):

```bash
cd ~/<series-root>
git add .
git commit -m "End of session $(date +%Y-%m-%d)"
git push
```

Or wrap that in a shell function in `~/.bashrc` so you can just
type `novel-save`:

```bash
novel-save() {
  ( cd ~/<series-root> && git add . && git commit -m "Snapshot $(date +%Y-%m-%d_%H%M)" && git push )
}
```

**What gets committed (the things that cost real work):**

- `project.yaml`, `shared/world.md`, `shared/canon.md`,
  `shared/characters.md`, `shared/events.md`, `shared/research/`,
  `shared/sources.bib`
- `books/<book>/seed.txt`, `voice.md`, `outline.md`,
  `pending_canon.md`
- `books/<book>/chapters/ch_NN.md` (the prose) and
  `books/<book>/chapters/ch_NN.summary.md` (continuity handoffs)
- `books/<book>/briefs/`, `eval_logs/`, `edit_logs/` (the decision
  trail — losing these means re-running expensive evaluations)
- `books/<book>/preface.md`, `introduction.md` if you've made them
- `books/<book>/title_proposals.md` if you've used `/autonovel:title`
- `books/<book>/art/cover.png`, `ornament_chNN.png` (regenerating
  these costs fal.ai credit)
- `books/<book>/audiobook/voices.yaml` and the parsed scripts

**What's deliberately NOT committed:**

- `.autonovel/checkpoints/` (large; per-command snapshots, only
  useful within one session)
- `.autonovel/in-progress.lock` (PID-bound, useless on another
  machine)
- `books/<book>/typeset/<book>_<YYYYMMDD>_<HHMM>.pdf` and `.epub`
  (the per-build timestamped copies — excluded so the repo
  doesn't balloon with one new file per rebuild)
- `books/<book>/typeset/novel.tex`, `chapters_combined.md`,
  `front_matter.tex`, `chapters_content.tex`, `metadata.yaml`
  (intermediate build inputs, regenerated by `/autonovel:typeset`)
- BUT `books/<book>/typeset/<book>_latest.pdf` and
  `<book>_latest.epub` ARE committed — these are the convenience
  pointers `/autonovel:typeset` overwrites on every successful
  build, so a `git clone` of your backup gives you a usable PDF
  and ePub on a fresh machine without rebuilding. Delete the two
  `!` lines from `.gitignore` if you'd rather not commit any
  binary outputs at all.
- `books/<book>/audiobook/*.mp3`, `*.wav`, `*.m4b` (large; ~50–500 MB
  for a full novel; regenerable via `/autonovel:audiobook-generate`,
  though that DOES cost ElevenLabs credit on each rebuild — so if
  you've finished the audiobook and want to commit the audio, just
  remove that line from `.gitignore`)

If you only have an existing novel set up before this `.gitignore`
was improved, you can apply the new version retroactively — it's
just a copy. Re-running `git add .` after copying picks up any
files newly excluded (and skips them) and any files newly tracked.

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
sudo apt install -y librsvg2-bin
# tectonic — try apt first; if doctor still flags it, see below.
sudo apt install -y tectonic

# macOS (with Homebrew):
brew install tectonic librsvg

# Verify:
tectonic --version          # should print the version
rsvg-convert --version
```

**Chromebook / Debian — when apt's `tectonic` doesn't work:**
Author testing 2026-04-25 hit the case where the Debian apt
`tectonic` package was either missing on the user's channel or
too old for autonovel's templates (the failure mode looks like
"needs a static-library compiled version"). If `tectonic` is
absent or `autonovel doctor` keeps complaining, grab the
prebuilt static binary from the official quick-install:

  <https://tectonic-typesetting.github.io/book/latest/installation/index.html>

The Linux instructions there drop one self-contained binary into
`~/.local/bin/`. No Rust toolchain or system libraries needed.
Re-run `tectonic --version` and `autonovel doctor` to confirm.

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

# Python image library (one-time, only if you ran the bare
# `pipx install .` rather than `pipx install '.[export]'`):
pipx inject autonovel Pillow
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

# Python audio library (one-time, only if you ran the bare
# `pipx install .` rather than `pipx install '.[export]'`):
pipx inject autonovel pydub

# ElevenLabs key — paste into <series-root>/.env
echo 'ELEVENLABS_API_KEY=sk_...' >> .env

# Verify:
ffmpeg -version
```

### 5e. All-at-once for the impatient

```bash
# Linux / WSL / Chromebook (one shot):
sudo apt update && sudo apt install -y pandoc potrace ffmpeg \
    librsvg2-bin fontconfig fonts-ebgaramond fonts-bebas-neue
sudo apt install -y tectonic   # may fail or be too old; if so, see §5a fallback
pipx inject autonovel Pillow pydub  # skip if you already used `pipx install '.[export]'`

# macOS (one shot):
brew install tectonic pandoc potrace ffmpeg librsvg fontconfig
pipx inject autonovel Pillow pydub  # skip if you already used `pipx install '.[export]'`
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
