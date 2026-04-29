# Series conventions

You (the AI) are running inside an **autonovel series**. This file is
auto-loaded by Claude Code (and read on demand by Codex / Gemini) so
you have shared context regardless of which command the user invokes.

A "series" here is the unit of co-evolving lore. A standalone novel
is a series with one book — same layout, same rules.

## Layout

```
project.yaml             # series config: genre, period, llm tier mapping
shared/
  world.md               # universe-level rules
  characters.md          # cast registry (every named character)
  canon.md               # hard-fact database — append-only via /autonovel:promote-canon
  events.md              # inter-book event ledger (story_time + rendered_in)
  timeline.md
  period_bans.txt        # forbidden vocabulary (period fiction)
  sources.bib            # research bibliography
  research/
    sources.yaml         # forced URLs that /autonovel:research must consult
    notes/               # per-topic research notes (one .md per topic)
    seed/                # source PDFs / images the user dropped in
books/<book>/
  seed.txt               # the user's pitch — authoritative input
  voice.md               # Part 1: generic guardrails. Part 2: book-specific fingerprint
  outline.md             # generated; structure across chapters
  pending_canon.md       # candidate canon — flushed into shared/canon.md by promote-canon
  chapters/ch_NN.md      # the prose
  briefs/                # generated revision briefs
  edit_logs/             # adversarial-edit + check-anachronism reports
  eval_logs/             # /autonovel:evaluate scoreboards
  audiobook/             # voices.yaml + voices.yaml.example + scripts + audio
  typeset/               # PDF/ePub build artefacts
.autonovel/
  state.json             # series-wide phase + scores
  in-progress.lock       # PID lock; do not edit
  checkpoints/           # rollback targets, written by every command's preamble
  command-log.jsonl      # one line per command run
```

## Operating rules

1. **Use the `/autonovel:*` commands.** Do not edit chapter prose,
   outlines, voice files, or canon directly except when explicitly
   acting *as* one of those commands. Each command owns a lock,
   checkpoint, and log entry; freelance edits skip all three.

2. **`shared/canon.md` is append-only via `/autonovel:promote-canon`.**
   Drafting and revision append observations to
   `books/<book>/pending_canon.md`. Promotion is single-threaded
   across the series and parks contradictions under a `# Conflicts`
   header for human resolution. Never optimistically merge.

3. **Chapter renumbering** after `/autonovel:merge-chapters`,
   `/autonovel:remove-chapter`, or `/autonovel:reorder` runs by
   shell script (collision-safe `mv` / `git mv`). Never rename
   chapters in an LLM rename loop. Same discipline applies to
   `/autonovel:rename-character`.

4. **Story-time gating** is a spoiler control. When drafting a
   chapter, only sibling chapters with `story_time` upper-bound ≤
   the target chapter's `story_time` lower-bound are legal context.
   The context loader at `python -m autonovel.context_loader`
   enforces this; trust it over your own reasoning.

5. **The Stability Trap.** AI defaults to safe, round-edged endings.
   Push toward irreversible change, real cost, and one mystery the
   next chapter can pull on.

## Where per-book guidance lives

If the user wants you to behave differently for one book in the
series (e.g. "Book Two is first-person; never head-hop"), that
guidance belongs in `books/<book>/voice.md` Part 1 — every drafting
and revision command reads it automatically. Don't add a per-book
`CLAUDE.md`; it would not auto-load.

## Production gotchas (learned in the Bells production)

These are real — they're not style preferences. The Bells team hit
each of these and the workaround is in the codebase:

- **Don't compress chapters below ~1800 words.** They become the
  new weakest. Sweet spot for compressed chapters is 2200–3000w.
- **`/autonovel:revise` overshoots target word count by ~30%.**
  Brief 3200w, expect 3800–4200w.
- **Pacing ≈ 7 is a likely ceiling** for investigation-heavy plots.
  Stop after two rotations of "weakest chapter".
- **OVER-EXPLAIN (~32%) and REDUNDANT (~26%)** dominate adversarial
  cuts. Prioritise these in `/autonovel:apply-cuts`.

## When in doubt

- Run `/autonovel:next` to see the prioritised state-aware action
  list (pending conflicts, regressions, stale review reports,
  backup status, plus the canonical pipeline next step).
- Run `/autonovel:resume` if a previous command left an
  `.autonovel/in-progress.lock` behind.
- Run `/autonovel:sidequest` for the menu of non-standard operations
  (rename character, split chapter, deepen character, etc.).
- Run `/autonovel:talk --book <name> "<question>"` to ask the book
  questions or queue edits. Three modes (Q+A / Suggest-and-stage
  / Mechanical+suggest); queued edits get folded into the brief
  by the next `/autonovel:revise <chapter>` automatically.
- Run `/autonovel:motifs --book <name>` for a per-chapter motif
  density table (configure `books/<name>/motifs.md` first).
- Run `/autonovel:chapter-summary --book <name>` for the
  one-line-per-chapter overview.
- Run `/autonovel:dashboard --book <name>` for the at-a-glance
  shape — score / tension sparklines, aggregates, and tension-
  drop alarms re-rendered from the latest eval log without
  firing another evaluate.
- Run `/autonovel:summaries --book <name> --where '<expr>'` to
  filter the chapter-summary index. Pure mechanical query DSL
  (no LLM): `pov == "Lucia"`, `cast contains Niccolò`,
  `story_time >= "1521-11"`, `chapter in 5..12`,
  `score < 7.0 and word_count > 3000`. Distinct from
  `/autonovel:talk` (LLM Q+A) by being free + scriptable.
- Run `/autonovel:dialogue --book <name>` for the dialogue-
  mechanics linter (adverb tags, said-bookisms, stutters).
- Run `/autonovel:period-register --book <name>` for a roll-up
  of period-bans hits across every chapter — useful before
  typeset.
- Run `/autonovel:pov-bleed --book <name>` for a heuristic POV-
  bleed scan. Suggestion list, not a gate — false positives are
  common.
- Run `/autonovel:import-book --book <name> --from <path>` to
  import an externally-written manuscript. Flips the book to
  `mode: edit-imported`; the rest of the pipeline (evaluate /
  revise / panel / review / typeset) is unchanged. After
  importing, run `/autonovel:summarize-chapter --all --book
  <name>` so revise/brief have continuity summaries to read.

## If you (the agent) hit `API Error: Extra usage is required for 1M context`

This is a Claude Code billing-gate, not an autonovel bug. Surface
this to the user verbatim and stop, do not retry:

> Your Claude Code session model is a 1M-context variant (e.g.
> `claude-opus-4-7[1m]`) and 1M billing is not yet enabled on your
> account. autonovel benefits from 1M context, especially in
> reader-panel and review. Two paths:
>
> 1. **Recommended:** run `/extra-usage` to enable 1M billing —
>    this is the path the error message itself suggests.
> 2. **Mechanical workaround:** run `/model` and pick a non-`[1m]`
>    variant (Sonnet 4.6 is the default tier for standard-tier
>    autonovel commands).
>
> Then re-run the command that just failed.

## Where to find more

- README at the series-template repo (autonovel project) — install
  + per-OS guidance + the seed-writing template.
- `docs/commands.md` — every `/autonovel:*` command reference.
- `docs/multi-book.md` — story-time gating and event ledger details.
- `docs/writing-a-historical-series.md` — end-to-end walkthrough.
