# Commands reference

Every `/autonovel:*` command, grouped by `context_mode`. Each row lists
the invocation hint, the model tier the adapter pins for the runtime,
and a one-line description.

The model tier maps to a concrete model per runtime — see
[`REWRITE-PLAN.md` §17](../REWRITE-PLAN.md#17-model-selection-per-command-frontmatter-model_tier).
Defaults on Claude Code are Opus 4.7 (heavy), Sonnet 4.6 (standard),
Haiku 4.5 (light); `project.yaml` can override per-series.

## Series-level commands

These read or write `shared/*` files and apply to the series as a whole.

| Command | Tier | Description |
|---|---|---|
| `/autonovel:add-character --name <name> [--role <role>] [--book <short-name>]` | standard | Add one character to the series cast; update `shared/characters.md`. |
| `/autonovel:add-source <url-or-doi> [--shortname <key>] [--weight primary|secondary] [--title "<title>"] [--research <topic>]` | standard | Add a URL or DOI to the bibliography and `shared/research/sources.yaml`; optionally re-run research. |
| `/autonovel:gen-canon` | standard | Seed `shared/canon.md` with hard facts derived from world, characters, and outlines. |
| `/autonovel:gen-characters` | heavy | Generate `shared/characters.md` from the world and the books' seeds. |
| `/autonovel:gen-world` | heavy | Generate `shared/world.md` from `project.yaml` and the books' seeds. |
| `/autonovel:promote-canon [--book <short-name>] [--dry-run]` | standard | Promote pending canon entries from every book's `pending_canon.md` into `shared/canon.md`. |
| `/autonovel:rename-character --old <old-name> --new <new-name> [--book <short-name>]` | standard | Globally rename a character with word-boundary safety (script-based, never LLM rename). |
| `/autonovel:research "<topic>"` | heavy | Research a real-world topic with live web search and write sourced notes into `shared/research/notes/`. |
| `/autonovel:run-pipeline --books <name[,name...]> [--phase <phase>] [--max-cycles <N>]` | light | Drive the full pipeline across one or more books. Advisory orchestrator — every mutation goes through a sibling `/autonovel:*` command. |

## Book-level commands

These read or write files under `books/{book}/`. The `--book <short-name>`
argument is required when more than one book exists in the series.

> **If you're confused about which command to run when** —
> specifically how `draft`, `draft-pass`, `revise`, `revision-pass`,
> `brief`, `review`, and `reader-panel` relate to each other —
> read [`operating-guide.md` §0](operating-guide.md#0-how-the-editing-commands-relate)
> before this reference. The roles (atomic / sweep / whole-book
> reviewer / mechanical helper) and the call graph (which command
> automatically invokes which) are explained there. This file is
> a per-command reference; the relationships are in the operating
> guide.

### Drafting

| Command | Tier | Description |
|---|---|---|
| `/autonovel:gen-outline --book <short-name>` | standard | Generate the outline from seed, world, and characters. |
| `/autonovel:voice-discovery --book <short-name> [--force \| --upgrade]` | heavy | Fill the book-specific fingerprint in Part 2 of `voice.md`, draft per-character voice fingerprints into Part 4 when the cast count is ≥3, and append the Part 3 (Custom rubric) placeholder if missing. `--upgrade` is the safe path for existing books — preserves Parts 1 and 2 verbatim while adding Parts 3 and 4. `--force` regenerates everything. |
| `/autonovel:draft <chapter-number> --book <short-name>` | standard | Draft one chapter as full prose. |
| `/autonovel:draft-pass --chapters <range> [--book <name>] [--retry-below <score>] [--no-revise-low] [--no-anachronism] [--no-promote] [--skip-eval] [--deep]` | heavy | "Write the rest of the book." Per chapter: draft → anachronism check → evaluate → if score < threshold (default 7.0), brief + revise + re-eval (keep best). At sweep end: promote-canon. With `--deep`: also run reader-panel + Opus review on the whole book and surface the flagged-chapter list. Sequential only. Same per-chapter quality as `/autonovel:draft` plus immediate-fix-on-low-score, end-of-sweep canon coherence, and (in deep mode) the whole-book passes. |
| `/autonovel:summarize-chapter <chapter> [--book <short-name>] [--force]` | standard | Backfill the 150–250-word continuity summary for a chapter drafted before summaries shipped. |
| `/autonovel:chapter-summary [--book <short-name>] [--format markdown\|json]` | light | Print a one-line-per-chapter overview — Date / POV / Score / Words / Cast / Plot — for the active book. Pure mechanical (no LLM), pulls already-structured fields from chapter frontmatter, summary.md, and the latest eval log. The right tool for "which chapters happen in <date range>?" or "where does <character> appear?" or "which chapter scored lowest?" — scan the relevant column. `--format json` for piping. |
| `/autonovel:motifs [--book <short-name>] [--format markdown\|json]` | light | Per-chapter motif density tracker. Reads `books/{book}/motifs.md` (one bullet per motif: `- slug: keyword1, keyword2`), counts word-boundary matches in each `ch_NN.md`, and emits a markdown table. Flags motifs that drop to zero in the back half of the book if they were established in the front half — catches "set up an image, never paid it off" without scoring it. Pure mechanical. |

### Evaluation and revision

| Command | Tier | Description |
|---|---|---|
| `/autonovel:evaluate --phase foundation --book <name>` | heavy | Score the foundation. |
| `/autonovel:evaluate --chapter <N> --book <name>` | heavy | Score one chapter against the standard rubric plus `irreversible_change` (Stability Trap antidote), `beat_coverage` (per-scene goal/conflict/disaster-or-decision/consequence; surfaces `weakest_scenes` by index), and any criteria in `voice.md` Part 3 (Custom rubric). For chapter 1, also scores `hook_strength` over the first 250 words. |
| `/autonovel:evaluate --full --book <name>` | heavy | Score the whole book — adds `irreversible_change_arc` (walks every (N→N+1) chapter pair, surfaces `cuttable_chapters`), `book_beat_coverage_score`, and `weak_beat_coverage_chapters`. Emits the per-chapter pacing-curve table + tension-drop alarms. |
| `/autonovel:evaluate --compare <N>,<M> --book <name>` | heavy | Head-to-head chapter pair. |
| `/autonovel:adversarial-edit <chapter> --book <short-name>` | heavy | Find 10–20 cut/rewrite candidates in one chapter. |
| `/autonovel:apply-cuts <chapter> --book <short-name> [--types OVER-EXPLAIN REDUNDANT] [--dry-run]` | light | Deterministically remove quotes flagged by adversarial-edit. |
| `/autonovel:reader-panel --book <short-name>` | heavy | Four-persona reader-panel review of a book's complete arc. |
| `/autonovel:review --book <short-name>` | heavy | Deep dual-persona manuscript review — literary critic + professor of fiction. |
| `/autonovel:brief <chapter> --book <short-name> [--from cuts\|eval\|panel\|auto] [--enrich-with <research-notes-path>]` | standard | Generate a revision brief from cuts, eval, or panel feedback. Surfaces a `## Weak scenes` section (when the eval log's `beat_coverage.weakest_scenes` is non-empty), a `## Stability check` section (when the eval log's `irreversible_change` score is below 7), and a `## Custom-rubric findings` section (when voice.md Part 3 criteria were flagged). With `--enrich-with`, also surfaces `## Enrichment from research` — light-touch period detail from the named research notes file, 1–2 details per relevant scene, no plot/dialogue/structure change. Omitted when no scenes warrant the research. |
| `/autonovel:revise <chapter> --book <short-name>` | heavy | Rewrite one chapter from a brief, preserving voice and continuity. |
| `/autonovel:revision-pass --chapters <range> [--book <name>] [--skip-anachronism] [--skip-eval] [--no-promote] [--enrich-with <research-notes-path>] [--parallel [N]]` | heavy | Sweep check-anachronism + brief + revise + evaluate + promote-canon across a range of chapters. Per-chapter promote-canon (added 2026-04-25) lands each revision's discoveries in `shared/canon.md` before the next chapter's revise reads canon — without it, an early-chapter revise that clarifies a fact would re-introduce the inconsistency in the next chapter. Sequential by default; `--parallel [N]` (default N=3) fans out via `Task` subagents at the cost of one revision-pass of summary-staleness. Per-chapter line shows score delta (`prev → new (Δ ±X.X)`) and canon promotion count. Final end-of-sweep promote-canon catches anything pending. `--no-promote` skips the canon merge if you want to inspect `pending_canon.md` before promoting. |
| `/autonovel:compare-models --chapter <N> [--book <name>] [--models <a>,<b>]` | heavy | A/B-draft the same chapter with two models in parallel, judge head-to-head, write verdict + both candidate drafts to `eval_logs/`. Live chapter file is unchanged. |

### Period guardrails (historical / period fantasy)

| Command | Tier | Description |
|---|---|---|
| `/autonovel:check-anachronism <chapter> --book <short-name>` | standard | Flag anachronistic vocabulary (regex) and semantic anachronism (LLM). |

### Sidequests

These are non-standard-path operations. Each lands as a single
checkpoint so `autonovel rollback` undoes the full operation.

| Command | Tier | Description |
|---|---|---|
| `/autonovel:shorten --chapter <N> --book <short-name> --target-words <W>` | heavy | Compress one chapter (never below 1800 words). |
| `/autonovel:lengthen --chapter <N> --book <short-name> --target-words <W>` | heavy | Expand one chapter via physical accumulation, not filler. |
| `/autonovel:revoice <chapter> --book <short-name> [--pov <name>] [--register <label>]` | heavy | Apply a voice shift — different POV or register. |
| `/autonovel:split-chapter --chapter <N> --book <short-name>` | heavy | Split one chapter into two; renumber subsequent chapters. |
| `/autonovel:merge-chapters --chapters <N>,<M> --book <short-name>` | heavy | Merge two adjacent chapters; renumber subsequent. |
| `/autonovel:reorder --from <A> --to <B> --book <short-name>` | heavy | Move a chapter to a new position; renumber neighbours. |
| `/autonovel:remove-chapter <chapter> --book <short-name>` | heavy | Delete a chapter; renumber subsequent; patch continuity. |
| `/autonovel:deepen-character <name> [--chapter <N>] [--book <short-name>]` | heavy | Revise to add an unguarded moment for a named character. |
| `/autonovel:add-subplot --thread "<one-sentence>" --plant <N> --payoff <M> --book <short-name>` | heavy | Plant a subplot in chapter N, pay off in chapter M. |
| `/autonovel:foreshadow --plant <N> --payoff <M> --thread "<one-sentence>" --book <short-name>` | heavy | Plant a detail in chapter N and pay it off in chapter M; update the thread ledger. |

### Export — art

| Command | Tier | Description |
|---|---|---|
| `/autonovel:art-style --book <short-name>` | heavy | Derive a per-book visual style from world + voice. Writes `visual_style.json`. |
| `/autonovel:art-directions --book <short-name> --surface cover\|ornament\|map\|scene-break [--n 4]` | heavy | Generate N radically different art-direction prompts. |
| `/autonovel:art-curate --book <short-name> --surface <s> [--provider fal\|replicate\|openai]` | standard | Generate image variants from saved directions. |
| `/autonovel:art-pick --book <short-name> --surface <s> --variant <N>` | light | Select one variant as the final art. |
| `/autonovel:art-prompts --book <short-name> [--chapters <range>] [--surface ornament\|plate\|scene-break] [--style lineart\|full\|symbolic] [--force]` | light | Author per-chapter art prompt files (one `.md` per chapter+surface) under `books/{book}/art/prompts/`. Uses outline + summary + `visual_style.json` + world cues. No image generation; writes the prompt as markdown for hand-editing or a different generator. `art-ornaments-all` reads these files when present. |
| `/autonovel:art-ornaments-all --book <short-name> [--provider fal] [--chapters <N,M,...>]` | standard | Generate a per-chapter ornament keyed to chapter content. Reads `books/{book}/art/prompts/ch{NN}_ornament.md` when authored (via `/autonovel:art-prompts`); falls back to inline derivation from prose otherwise. |
| `/autonovel:art-vectorize --book <short-name> [--target <stem>]` | light | Convert ornament + scene-break PNGs to SVG via potrace. |

### Export — cover, audiobook, typeset, landing, package

| Command | Tier | Description |
|---|---|---|
| `/autonovel:cover-composite --book <short-name> [--preset auto\|dark\|light] [--title X] [--author Y]` | light | Composite title + author text over the picked cover art (front only). |
| `/autonovel:cover-print --book <short-name> --pages <N> [--paper cream\|white] [--trim-w 5.5] [--trim-h 8.5]` | light | Print-ready wraparound cover + thumbnail matrix. |
| `/autonovel:audiobook-voices --book <short-name> [--list \| --set SPEAKER=voice-id ...]` | light | Configure or list ElevenLabs voice IDs. |
| `/autonovel:audiobook-script --book <short-name> [--chapters <N,M,...>]` | standard | Parse chapters into speaker-attributed audiobook scripts. |
| `/autonovel:audiobook-generate --book <short-name> --chapter <N> [--takes 3] [--test]` | standard | Render one chapter's audio via ElevenLabs with multi-take + best-take selection. |
| `/autonovel:audiobook-assemble --book <short-name> [--format mp3\|m4b] [--pause 2.0]` | light | Stitch chapter MP3s into a single audiobook with chapter marks. |
| `/autonovel:title --book <short-name> [--set "<title>" --author "<name>" --subtitle "<text>"] [--pick N] [--pick-author M]` | light | Propose / pick / set the book's display title, subtitle, and author for typeset. With no flags: writes 5 title candidates + 3 author candidates to `books/<book>/title_proposals.md` for review. With `--pick N`: commits the Nth proposal to `project.yaml`. With `--set/--author/--subtitle`: writes explicit values directly. Optional — `typeset` falls back to series_name + "Anonymous" when unset. |
| `/autonovel:introduction --book <short-name> [--from auto\|user\|both] [--force]` | heavy | Generate front-matter content for the typeset PDF and ePub. `--from user` (default) scaffolds `books/<book>/preface.md` for the writer to fill in. `--from auto` AI-generates `books/<book>/introduction.md` (~600–1200 words, essay-form, grounded in the book's themes; never reveals plot past the inciting incident). `--from both` does both. typeset auto-includes whichever exist, in order Preface → Introduction, as `\chapter*{}` blocks before chapter 1. `--force` overwrites existing files. |
| `/autonovel:typeset --book <short-name> [--pdf-only \| --epub-only] [--convert-vectors]` | light | Build PDF + ePub from chapters and typeset templates. Outputs `<book>_<YYYYMMDD>_<HHMM>.pdf` (per build, kept) plus `<book>_latest.pdf` (overwritten each successful build); same shape for `.epub`. Title and author come from `project.yaml :: books[<name>]` (set via `/autonovel:title`); falls back to `series_name` and "Anonymous". |
| `/autonovel:landing --book <short-name> [--template <path>] [--url <canonical-url>]` | standard | Render a responsive landing page with og:image + structured data. |
| `/autonovel:package --book <short-name> [--skip <t,t,...>] [--out <path>]` | light | End-to-end release bundle — PDF + ePub + covers + landing + audiobook, zipped. |

## Navigation commands

These don't read or write a book — they show the user what to do next.

| Command | Tier | Description |
|---|---|---|
| `/autonovel:next [--book <short-name>]` | light | State-aware action list — pending conflicts, regressions, stale review reports, backup status, missing front matter — plus the canonical pipeline next step at the bottom. |
| `/autonovel:resume [--book <short-name>]` | light | Detect an in-flight command; offer redo / keep-partial / inspect. |
| `/autonovel:sidequest` | light | Dispatcher menu for non-standard-path operations. |

## Frontmatter contract

Every command file under `commands/*.md` carries YAML frontmatter the
adapters parse and the contract tests verify:

```yaml
---
name: autonovel:<stem>
description: <one-line description>
argument-hint: "<argument-hint string>"
model_tier: heavy | standard | light
allowed-tools:
  - file_read
  - file_write
  - bash
  - task
  - web_search
  - web_fetch
reads:
  - <path>
writes:
  - <path>
context_mode: series | book | none
---
```

Tier-2 contract tests verify every `reads:` entry is mentioned in the
body, every `writes:` entry is described in the body, and every path
placeholder (`{book}`, `{chapter}`) resolves from `argument-hint`.
