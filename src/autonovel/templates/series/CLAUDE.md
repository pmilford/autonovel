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

- Run `/autonovel:next` to see the standard next step.
- Run `/autonovel:resume` if a previous command left an
  `.autonovel/in-progress.lock` behind.
- Run `/autonovel:sidequest` for the menu of non-standard operations
  (rename character, split chapter, deepen character, etc.).

## Where to find more

- README at the series-template repo (autonovel project) — install
  + per-OS guidance + the seed-writing template.
- `docs/commands.md` — every `/autonovel:*` command reference.
- `docs/multi-book.md` — story-time gating and event ledger details.
- `docs/writing-a-historical-series.md` — end-to-end walkthrough.
