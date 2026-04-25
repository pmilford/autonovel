# Writing a multi-book series

A `series` in autonovel is a single git-versioned directory that holds
a `project.yaml`, a `shared/` lore directory, and one or more `books/`.
Books share the world, characters, canon, events, and research; each
owns its own outline, voice, chapters, and pending canon.

## Layout

```
my-series/
  project.yaml
  shared/
    world.md
    characters.md
    canon.md
    events.md
    timeline.md
    period_bans.txt          # historical / period fantasy only
    sources.bib              # bibtex
    research/
      sources.yaml           # forced-URL list for /autonovel:research
      notes/                 # per-topic notes files
      seed/                  # source PDFs/images you've dropped in
  books/
    book-one/
      seed.txt
      voice.md               # Part 1 generic guardrails + Part 2 fingerprint
      outline.md
      pending_canon.md       # parked here; promote-canon merges to shared/
      chapters/ch_01.md … ch_NN.md
      briefs/                # generated revision briefs
      edit_logs/             # adversarial-edit reports
      eval_logs/             # evaluate scoreboards
      typeset/               # PDF/ePub build artefacts
      audiobook/             # voices.yaml, scripts, audio segments
    book-two/
      …
```

`autonovel new-series <name>` creates the series tree;
`autonovel new-book <name> --series <path>` adds a book and registers
it in `project.yaml`.

## What goes where: shared vs book

The rule of thumb: anything that is true *for the universe of the
series* belongs in `shared/`. Anything that is unique to one book —
its voice, its outline, its chapter prose — belongs in `books/<name>/`.

| File | Lives in | Updated by |
|---|---|---|
| World rules, technology limits, magic costs | `shared/world.md` | `/autonovel:gen-world`, `/autonovel:add-source` |
| Cast registry (every named character) | `shared/characters.md` | `/autonovel:gen-characters`, `/autonovel:add-character`, `/autonovel:rename-character` |
| Hard facts confirmed across the series | `shared/canon.md` | `/autonovel:gen-canon`, `/autonovel:promote-canon` |
| Inter-book event ledger (what happened when) | `shared/events.md` | hand-edited; validated by `src/autonovel/validators/events.py` |
| Per-book outline | `books/<name>/outline.md` | `/autonovel:gen-outline` |
| Per-book voice fingerprint | `books/<name>/voice.md` | `/autonovel:voice-discovery` |
| Per-book chapters | `books/<name>/chapters/ch_NN.md` | `/autonovel:draft`, `/autonovel:revise` |
| Per-book candidate canon | `books/<name>/pending_canon.md` | drafting commands append; `/autonovel:promote-canon` merges |

## Story time and spoiler gating

Every chapter carries a `story_time` ISO date in its frontmatter. The
context loader at `src/autonovel/context_loader.py` reads `story_time`
plus `events.md` to decide which sibling chapters are *legal context*
when drafting a target chapter.

The rule (see PR-6 decisions log in `STATE.md`):

> A sibling chapter is readable only if its `story_time` upper bound
> is ≤ the target chapter's `story_time` lower bound.

Event rendering (a chapter listed under `rendered_in` for one of this
chapter's events) surfaces *additional* sibling chapters, but the
spoiler check still dominates: a future chapter that renders the same
event stays excluded.

This means a writer can draft `tiny-inquisitor/ch_05` (story-time
1521-12-04) with full visibility into `tiny-apothecary/ch_02`
(story-time 1521-12-01) but never the reverse.

## The events ledger

`shared/events.md` is the inter-book continuity ledger. Schema (parsed
by `src/autonovel/validators/events.py`):

```markdown
## E-001 — Mint fire

- date: 1521-11-04
- location: Zecca, Venice
- present: Tommaso, Alvaro
- canonical: yes
- rendered_in:
  - tiny-inquisitor/ch_03
  - tiny-apothecary/ch_05
- book_constraints:
  - tiny-inquisitor: must reference, not narrate
  - tiny-apothecary: narrate in real time
```

Validator runs cleanly on parse; cross-consistency check
(`check_cross_consistency(events, project_books)`) flags
`rendered_in` rows that name a book missing from `project.yaml`.

## Promoting canon

Drafting commands append observations to
`books/<name>/pending_canon.md`. They never write `shared/canon.md`
directly — that's `/autonovel:promote-canon`'s job.

Promotion handles three classes:

1. **Compatible.** Pending entry doesn't contradict anything in canon
   → merged.
2. **Duplicate.** Already in canon, possibly worded differently →
   dropped (logged to `edit_logs/`).
3. **Contradiction.** Pending entry conflicts with canon → parked
   under a `# Conflicts` header in
   `books/<name>/pending_canon.md` for human resolution. Never
   merged optimistically.

The `.autonovel/in-progress.lock` written by every command's preamble
is the cross-book race mitigation: two terminals can draft different
chapters in different books in parallel, but only one
`/autonovel:promote-canon` runs at a time.

## Coordinating revisions across books

When a shared-file change should propagate to multiple books, the
recipe is:

1. Edit `shared/world.md` (or `shared/characters.md` etc.).
2. For each affected book, run `/autonovel:evaluate --full --book <name>`
   to surface chapters that contradict the new lore.
3. For each flagged chapter, run `/autonovel:brief <chapter> --book <name>
   --from auto` followed by `/autonovel:revise <chapter> --book <name>`.

Steps 2–3 can run book-by-book; the spoiler gate keeps the revisions
from leaking future-book information into past-book chapters.

## Multi-book pipeline runs

`/autonovel:run-pipeline --books book-one,book-two,book-three` walks
the books in declaration order:

- For each book, runs the foundation phase (if not already done) →
  drafting → revision → export.
- The orchestrator is *advisory*: it never mutates content directly.
  Every content change goes through a sibling `/autonovel:*` command
  that owns its own lock + checkpoint + footer. The contract is that
  a snapshot taken before and after `/autonovel:run-pipeline` is
  byte-identical apart from `.autonovel/` bookkeeping.

For a worked walkthrough on a 3-book historical series, see
[`writing-a-historical-series.md`](writing-a-historical-series.md).
