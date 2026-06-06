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
| `/autonovel:research "<topic>" \| --from-seed [--book <name>] \| --query "<question>"` | heavy | Three modes. **Topic:** live web research, writes sourced notes to `shared/research/notes/<slug>.md`. **From-seed:** auto-derive 2–4 topics from `seed.txt` + `project.yaml :: period` and run topic mode for each. **Query:** read every existing `shared/research/notes/*.md` (no web search) and answer the question with `[shortname]` citations — cross-source synthesis without re-firing research. Pair with `autonovel mechanical research-index <series>` for the structural "what's even in there" view. |
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
| `/autonovel:talk --book <short-name> "<question or suggestion>" [--target <chapter>]` | heavy | Conversational query+suggest layer over the finished prose. Three modes the command picks from your prompt: **Q+A** (e.g. *"explain why Jakob opened the book of accounts"* — answers, cites chapter+line); **Suggest-and-stage** (e.g. *"add some details about the book of accounts being out of alignment"* — queues an edit in `books/{book}/briefs/conversation.md` for the next `/autonovel:revise <N>` to apply); **Mechanical+suggest** (e.g. *"how many cipher-diary entries are referred to later? Cut the orphans"* — runs `mechanical entity-track` first, then queues a structured cut-list). Each invocation appends one turn to `conversation.md`; revise marks queued turns `applied` after using them. |
| `/autonovel:impact-of [--book <short-name>] [--source promote-canon\|gen-canon\|voice-discovery\|add-character\|gen-characters\|gen-world\|add-source\|rename-character\|merge-chapters\|reorder\|remove-chapter\|research] [--with-llm] [--format markdown\|json]` | light | After a foundation mutation, list the chapters that reference the now-wrong fact and emit an action checklist of `/autonovel:revise --chapter N` calls. Five detection shapes: **canon-driven** (`promote-canon`, `gen-canon`) parses `## Superseded` blocks and greps tokens unique to each prior value; **mtime-driven** (`voice-discovery`, `add-character`, `gen-characters`, `gen-world`, `add-source`) lists chapters drafted before the relevant foundation file's last update; **rename-verify** (`rename-character`) reads the most recent rename from `.autonovel/command-log.jsonl` and word-boundary-greps every chapter for the OLD name (catches stragglers the rename's sed missed — possessives, hyphens, unicode look-alikes, HTML entities); **renumber-refs** (`merge-chapters`, `reorder`, `remove-chapter`) greps prose for chapter-number cross-references (`Chapter VII`, `chapter 7`, `ch. 12`) so a renumber doesn't leave silently-wrong navigational pointers; **research** reads notes newer than the last canon timestamp and (LLM by default) scans chapters for contradictions against the notes' candidate canon entries. With `--with-llm` on canon-driven sources, a Haiku-tier classifier labels each match HIGH/MEDIUM/LOW/FALSE_POSITIVE so the action checklist only includes HIGH+MEDIUM. Read-only by contract. |
| `/autonovel:dashboard [--book <short-name>] [--threshold <float>] [--format markdown\|json]` | light | Per-book at-a-glance dashboard. Re-renders the latest `<ts>_full.json` eval log (score / tension / beats-hit / irreversible_change) and augments with mechanical dimensions (cast size, scene count, dialogue density, motif density). Adds ASCII sparklines for the score and tension series, per-book aggregates (mean / median / range / longest sub-threshold streak), and re-runs the tension-drop alarm. Pure mechanical, no LLM call. |
| `/autonovel:summaries [--book <short-name>] [--where '<expr>'] [--format markdown\|json]` | light | Filter the per-chapter summary table by a small DSL — `pov == "Lucia"`, `score < 7.0 and word_count > 3000`, `cast contains Niccolò`, `story_time >= "1521-11"`, `chapter in 5..12`, etc. Distinct from `/autonovel:talk` (LLM-mediated semantic Q+A) and `/autonovel:chapter-summary` (whole-table dump): pure mechanical, free, scriptable, stable semantics. |
| `/autonovel:dialogue [--book <short-name>] [--summary-only] [--format markdown\|json]` | light | Pre-flight dialogue-mechanics scanner. Six detectors: adverb-heavy speech tags, said-bookisms, repeated-verb stutters, action-beat-tag clusters (3+ in 10 lines), softening qualifiers in short retorts (`"Maybe,"`), and unattributed-dialogue runs (≥3 untagged paragraphs). **Review list, not a gate** — LLM judge in `/autonovel:evaluate` scores; this surfaces candidates. |
| `/autonovel:period-register [--book <short-name>] [--summary-only] [--format markdown\|json]` | light | Roll the period-bans scanner across every chapter and emit a worst-offenders ranking + per-chapter hit table. Useful before a typeset / publish pass to confirm the book stays in period across the full run. |
| `/autonovel:syntax-drift [--book <short-name>] [--threshold <float>] [--format markdown\|json]` | light | Per-chapter Flesch-Kincaid grade vs the book's voice/seed baseline (or median fallback). Catches modern syntax in period-correct vocabulary. Pure math, no curated word-lists. Review list, not a quality gate — the LLM judge in `/autonovel:evaluate`'s `voice_adherence` dimension scores. |
| `/autonovel:pov-bleed [--book <short-name>] [--summary-only] [--format markdown\|json]` | light | Heuristic POV-bleed scan — flag lines where a non-POV character is named with an interiority verb (`thought`, `felt`, `knew`, `realised`, …) or possessive interiority (`Niccolò's mind raced`). Reads `shared/characters.md` for the cast. False positives are common — treat as a review list, not a gate. |
| `/autonovel:import-book --book <short-name> --from <path> [--split-on '<regex>'] [--start <N>] [--pov <name>] [--keep-mode] [--overwrite] [--reverse-engineer] [--dry-run]` | light | Import an externally-written manuscript into `books/{book}/chapters/`. Splits a directory of `*.md` files (one chapter per file) OR a single combined manuscript (split on `^# `, fallback `^## `, fallback whole file). Writes autonovel-shape frontmatter + flips `project.yaml :: books[].mode` to `edit-imported` so `/autonovel:draft` refuses to overwrite. With `--reverse-engineer`, scan the imported prose for candidate character names (capitalised single-word tokens above a frequency threshold; structural-English reject list) and write or append `shared/characters.md` with a "Candidate cast (auto-detected)" block. Pure mechanical, no LLM — voice / outline reverse-engineering route through follow-up LLM commands (`voice-discovery` / `summarize-chapter` / `gen-outline`). |
| `/autonovel:series-arc [--threshold <float>] [--format markdown\|json]` | light | Series-arc score across ≥2 books: per-book completion (summary / eval / above-threshold), cross-book cast (characters in ≥2 books), backwards story-time jumps (intentional flashbacks vs structure problems), unresolved threads (opened in one chapter, never closed in any later one), composite arc score 0–10. Pure mechanical. |
| `/autonovel:show-dont-tell [--book <short-name>] [--summary-only] [--format markdown\|json]` | light | Per-chapter pre-flight scanner for tell-candidate lines (emotion-state, interiority verbs, perception filters, narrator labels). Wider net than the existing slop scanner; surfaces line-level targets for revise. The LLM judge in `/autonovel:evaluate` does the show-vs-tell ratio scoring. |

### Evaluation and revision

| Command | Tier | Description |
|---|---|---|
| `/autonovel:evaluate --phase foundation --book <name>` | heavy | Score the foundation. |
| `/autonovel:evaluate --phase series` | heavy | Score arc *quality* across ≥2 books. Pairs with `/autonovel:series-arc` (structural scoreboard); this LLM judge scores `series_question`, `early_setup_late_payoff`, `cross_book_character_growth`, `world_evolution_consistency`, `tonal_continuity`. Output includes a `unresolved_thread_payoff_plan` array brief / revise can act on. Eval log lands at `.autonovel/eval_logs/<ts>_series.json`. |
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
| `/autonovel:art-curate --book <short-name> --surface <s> [--provider pollinations\|wikimedia\|fal\|replicate\|openai]` | standard | Generate image variants from saved directions. Provider precedence: `--provider` flag → `project.yaml :: image.provider` → `pollinations` (free, no key). |
| `/autonovel:art-pick --book <short-name> --surface <s> --variant <N>` | light | Select one variant as the final art. |
| `/autonovel:art-prompts --book <short-name> [--chapters <range>] [--surface ornament\|plate\|scene-break] [--style lineart\|full\|symbolic] [--force]` | light | Author per-chapter art prompt files (one `.md` per chapter+surface) under `books/{book}/art/prompts/`. Uses outline + summary + `visual_style.json` + world cues. No image generation; writes the prompt as markdown for hand-editing or a different generator. `art-ornaments-all` reads these files when present. |
| `/autonovel:art-ornaments-all --book <short-name> [--provider pollinations\|fal\|replicate\|openai] [--chapters <N,M,...>]` | standard | Generate a per-chapter ornament keyed to chapter content. Reads `books/{book}/art/prompts/ch{NN}_ornament.md` when authored (via `/autonovel:art-prompts`); falls back to inline derivation from prose otherwise. Provider precedence: `--provider` flag → `project.yaml :: image.provider` → `pollinations`. |
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

### Movie / teaser

Build spec: [`prd-movie-teaser-mode.md`](prd-movie-teaser-mode.md). Creative guide: [`teaser-craft.md`](teaser-craft.md). Backend map + free-tier/key setup: [`teaser-render-providers.md`](teaser-render-providers.md). Full pipeline shipped: `treatment` → `teaser` (orchestrator: `teaser-beats` → `shot-prompts`) → `teaser-critique` → `teaser-refs` (develop + approve character references) → `teaser-render` (offline `stub` to validate free, then `grok` real clips + vision critique) → `teaser-assemble` (ffmpeg stitch + viewer-panel cut critique). The planning commands (treatment → shot-prompts, critique) are **free, no generation**; `teaser-render` validates the whole chain for $0 via the offline `stub` backend before spending a real one; `teaser-assemble` runs ffmpeg locally.

| Command | Tier | Purpose |
|---|---|---|
| `/autonovel:treatment --book <short-name> [--pages <n>] [--audience xprize\|general] [--no-brief] [--force]` | heavy | Generate a film **treatment** (≤`--pages`, default 12) + a 2-page **brief/synopsis** from the book's foundation (outline + world + characters + canon, enriched by `chapters/*.md` when present). Present-tense; reveals the ending (a treatment hides nothing — unlike a teaser). `--audience xprize` (default) frames both for the Future Vision X-Prize: optimistic future, technology solving a real problem, genuine stakes + arc, visual ambition. Writes `books/<book>/treatment.md` + `books/<book>/brief.md`; `--force` to overwrite. |
| `/autonovel:teaser --book <short-name> [--length 30\|60\|90\|120\|180] [--provider <name>] [--with-treatment] [--force]` | standard | **The one-command teaser pipeline.** Chains `teaser-beats` → `shot-prompts`, each in a fresh `task` subagent (context hygiene), and prints one combined summary. `--with-treatment` runs `/autonovel:treatment` first when none exists. Produces `beats.md` + `teaser.json` + per-shot files. Free; no generation. |
| `/autonovel:teaser-beats --book <short-name> [--length 30\|60\|90\|120\|180] [--provider generic\|veo\|sora\|runway\|kling\|luma\|pollinations] [--force]` | standard | Select 8–20 teaser beats on the hook → escalation → title → button arc from the treatment/outline + eval_logs, to a budget from `teaser-plan`. Writes the hand-editable `books/<book>/teaser/beats.md`. Free; no generation. |
| `/autonovel:shot-prompts --book <short-name> [--provider <name>] [--length <s>] [--force]` | heavy | Turn the beat-sheet into provider-ready, heavily-described shot prompts. Fills the structured shot schema (verbatim character appearance, palette lock, one action/one move, content-word negative prompt, consistency anchors), runs a **free pre-generation critique** (mechanical `teaser-critique` + an LLM rewrite pass), then writes `books/<book>/teaser/teaser.json` + per-shot `books/<book>/teaser/shots/shot_<id>.md`. No generation cost. |
| `/autonovel:teaser-critique --book <short-name> [--provider <name>]` | standard | Standalone, re-runnable **free pre-generation critique** of a (hand-edited) `teaser.json`: the mechanical linter + an LLM critic pass that scores each shot against trailer craft and the beat it serves. **Read-only** on `teaser.json`; writes an advisory `books/<book>/teaser/critique.md` with concrete rewrite suggestions. |
| `/autonovel:teaser-refs --book <short-name> [--init] [--subject <NAME>] [--approve <NAME>] [--force]` | standard | **Develop + approve character/location references before spending a real render.** Declares a source per recurring subject (public-domain art via `wikimedia-*`, a local image via `art-import`, or `generate`), locks the appearance + period/likeness constraints in `books/<book>/teaser/refs.yaml`, and **gates real generation behind approval** (the offline `stub` backend is exempt). See [`teaser-render-providers.md`](teaser-render-providers.md). |
| `/autonovel:teaser-render --book <short-name> [--provider stub\|gemini\|grok\|kie\|veo\|magichour\|fal\|flow\|pollinations] [--kind auto\|image\|video] [--refs] [--film-style <s>] [--takes <n>] [--shot <id>] [--height <px>] [--token <key>] [--delay <s>] [--dry-run]` | standard | Render the shot prompts into **actual clips/keyframes**. Validates the whole chain for **$0/zero-quota** via the offline **`stub`** backend before spending a real one; **`grok`** (free dialogue+music, no card — `XAI_API_KEY`) is the default real video backend; **`gemini`** generates **reference-conditioned photoreal keyframes** (Nano Banana). `--refs` feeds each shot's **approved** character references (from `teaser-refs`) so identity holds across shots (approval gate: pending subjects skipped); `--film-style` swaps the typeset art style for a film look. See [`teaser-render-providers.md`](teaser-render-providers.md). **Stateless** — clips land in `books/<book>/teaser/clips/`. `--dry-run` prints the plan + key status for $0; pacing/backoff automatic. Then a **vision clip critique** marks each KEEP / REGENERATE / UPGRADE-TO-PAID into `clips/render-report.md`; paid providers only ever *recommended*. |
| `/autonovel:teaser-assemble --book <short-name> [--kind image\|video] [--audio <path>] [--fps <n>] [--take <n>] [--force]` | standard | Stitch the rendered clips into **one teaser video** via ffmpeg. Builds an editable `cut_list.json` (ordered clips + durations + text-card notes + optional audio bed), runs ffmpeg (v1: hard cuts; image slideshow or video clips), then a **viewer-panel cut critique** (hook lands? accelerates? button withholds?) → `assembly-report.md`. No burned-in text (cards go in an editor); ffmpeg required. |

## Navigation commands

These don't read or write a book — they show the user what to do next.

| Command | Tier | Description |
|---|---|---|
| `/autonovel:help [<topic>]` | light | Discoverability layer over every autonovel command. Zero-arg shows category-grouped overview. With a topic — `art / foundation / drafting / revising / typeset / research / front-matter / sweeps / tui / cli / next-steps` — shows an in-depth guide for that workflow with the exact command sequence. The `art` topic walks the four cover paths (typographic-only / pollinations / wikimedia / paid) so you don't have to remember the 10 art commands. |
| `/autonovel:extract-chapter-titles --book <short-name> [--chapters <range>] [--force]` | light | Backfill 2-6 word evocative chapter titles into frontmatter for chapters drafted before titles became standard. typeset's TOC reads the frontmatter `title:` field; without backfill, the TOC reads `Chapter I, II, …` instead of `Chapter VII — The Apothecary's Mortar`. Light tier (~$0.001/chapter). Pairs with `autonovel mechanical chapter-titles` (the mechanical inspector) and the LOW situational signal `/autonovel:next` surfaces. |
| `/autonovel:next [--book <short-name>]` | light | State-aware action list — pending conflicts, regressions, **briefs newer than their chapters** (the brief→revise pair, the most common situational signal), stale reader-panel/Opus review reports, backup status, missing front matter — plus the canonical pipeline next step at the bottom. **Past-end-of-book guard:** when the canonical line points to a draft chapter beyond what exists by more than 1, it gets demoted to "book appears complete — try evaluate --full / typeset". You'll also see a one-line `💡 Maybe try:` hint in every command's postamble drawn from the same enumerator, so most of the time you don't need to call `/autonovel:next` separately. |
| `/autonovel:resume [--book <short-name>]` | light | Detect an in-flight command; offer redo / keep-partial / inspect. Also reads `.autonovel/sweep-progress.json` (written per-chapter by `draft-pass` / `revision-pass`) and prints a precise "continue from chapter N" with the remaining chapter list when a sweep was interrupted — independent of the lock so a `/clear` mid-sweep still surfaces the remaining work. |
| `/autonovel:sidequest` | light | Dispatcher menu for non-standard-path operations. |

## CLI subcommands (run from the shell, not the runtime)

These run from a terminal in your series root, not as slash-commands.

| Command | Description |
|---|---|
| `autonovel status` | Phase, scores, last command, lock state. |
| `autonovel cost [--format markdown\|json]` | Roll up token + USD spend per book / per tier / per command from `.autonovel/command-log.jsonl`. Estimates only — what the runtime self-reported. |
| `autonovel doctor [--fix] [--install-missing] [--yes]` | Sanity-check the series — required dirs, project.yaml shape, missing external CLI tools (tectonic / pandoc / ffmpeg / Pillow / fontconfig / etc.), AND typeset fonts (`fc-match` lookup against the names `templates/series/typeset/novel.tex` references — currently `EB Garamond`). Pre-flight font check catches the case where tectonic would walk fontspec's noisy "stepping through fonts by name" fallback chain mid-build; you see a clean "install `fonts-ebgaramond`" warning before typeset instead. `--fix` recreates missing dirs. `--install-missing` hands off to `install-export-tools` for any missing tools — combines the report-and-act flows in one invocation. `--yes` skips the per-tool confirmation prompts under `--install-missing`. |
| `autonovel install-export-tools [--exports pdf,epub,cover,audiobook,art] [--apply] [--yes]` | Interactive installer for the external tools the export commands depend on (tectonic, pandoc, ffmpeg, Pillow, fontconfig, etc.). Detects OS + autonovel install method, prints the exact commands per tool with known-fragility fallbacks (e.g. apt-tectonic too old → upstream prebuilt). `--apply` runs them with per-tool confirmation. |
| `autonovel tui [--book <name>]` | Long-running read-only terminal UI — chapters / scores / research / foundation / front + back matter / reviews / commands / next actions / live help. Tabbed; auto-refreshes every 5 s. Never acquires the lock — safe to run alongside an active sweep. The Chapters tab shows a `⚠` next to the status column when a chapter's `.md` is newer than its `.summary.md` (continuity-critical: revise didn't refresh the rolling-context surface — fix with `/autonovel:summarize-chapter --stale --book <name>`). Requires `pip install 'autonovel[tui]'` (or `pipx inject autonovel textual`). Run in a *separate* terminal from your runtime. |
| `autonovel import-book <name> --from <path> [--reverse-engineer] [--dry-run]` | Import an externally-written manuscript into autonovel-shape ch_NN.md files. `--reverse-engineer` extracts candidate character names from the imported prose into a `shared/characters.md` stub (or appends a "Candidate cast (auto-detected)" block when one exists). |
| `autonovel install [--pin-model]` | Write `/autonovel:*` command files into every detected runtime's expected path (idempotent). **By default no `model:` is pinned** — the runtime's session model wins (avoids the `[1m]` billing-gate downshift). `--pin-model` opts back in to per-tier model pinning. (`--no-model-pin` is accepted as a deprecated no-op.) |
| `autonovel onboard <book> [--non-interactive]` | Interactive onboarding wizard — prompts for pitch / period / genre / working title / human author / attribution style, writes a structured `seed.txt`, and updates `project.yaml :: books[<book>]`. Every prompt has a (skip) option which lands an `## Onboarding TODO` block in seed.txt for `/autonovel:next` to surface. `--non-interactive` skips prompts and prints current state. |
| `autonovel test-fixture {new,list,run,trim-flakiness} ...` | Manage genre fixture smoke tests. |

## Mechanical helpers (invoked from slash-command bodies via `bash`)

`autonovel mechanical <subcommand>` — pure-Python helpers that
slash-command bodies invoke to do deterministic work without an
LLM call. Most users never type these directly; they're listed
here so you know what each slash-command is doing under the hood
and can run them by hand for inspection / debugging.

| Subcommand | What it does |
|---|---|
| `slop <path>` | JSON slop-score of a prose file. |
| `period-bans <path> <bans>` | Hits of bans list against a prose file. |
| `apply-cuts <chapter> <cuts>` | Apply a cuts.json file to a chapter in place. |
| `scenes <path>` | Split a chapter into scenes by `***` / `---` / `* * *` breaks. |
| `motifs <book>` | Per-chapter motif density from `motifs.md`. |
| `chapter-summary <book>` | One-line-per-chapter overview (date / POV / score / cast / plot). |
| `chapter-titles <book>` | Inspect every chapter's `title:` frontmatter; reports which need backfill. Pairs with `/autonovel:extract-chapter-titles`. |
| `timeline-extract <book>` | Pull in-narrative dates from chapter summaries + frontmatter for the appendix timeline. The mechanical pre-pass before LLM-side merging of real-world events. |
| `summary-query <book> --where '<expr>'` | Filter chapter-summary by a small DSL (pov / score / story_time / cast / location / plot). |
| `dashboard <book>` | Re-render latest `<ts>_full.json` eval log + mechanical augmentations + sparklines. |
| `syntax-drift <book>` | Per-chapter Flesch-Kincaid grade vs voice/seed baseline. |
| `pov-bleed <book>` | Heuristic POV-bleed scan. |
| `dialogue <book>` | Dialogue-mechanics linter. |
| `period-register <book>` | Roll period-bans hits across every chapter. |
| `series-arc <series>` | Cross-book completion + cast + thread continuity. |
| `show-dont-tell <book>` | Pre-flight tell-candidate scanner. |
| `entity-track <book>` | Per-chapter named-entity tracker. |
| `cliches <path>` | Curated bigram/trigram cliché scan. |
| `sensory <path>` | Per-channel sensory-balance fractions. |
| `summary-query <book> --where ...` | Filter the chapter-summary table. |
| `impact-of <book> --source ...` | Token-grep chapters for changed canon facts (post promote-canon). |
| `research-index <series>` | Per-note metadata table for `shared/research/notes/`. |
| `wikimedia-search "<query>"` | Free public-domain art via Commons API. |
| `wikimedia-fetch "File:<title>"` | Download + center-crop one Commons image. |
| `build-front-matter-tex <book>` | Concatenate preface + introduction + glossary into front_matter.tex. |
| `build-back-matter-tex <book>` | Wrap appendix.md into back_matter.tex. |
| `build-tex <chapters_dir>` | Build chapters_content.tex from .md files. |
| `build-epub-md <chapters_dir>` | Concatenate ch_NN.md → one ePub-ready markdown. |
| `spine-width --pages N` | Cover canvas spec (spine + canvas + px). |
| `teaser-plan --length <s> [--provider <p>]` | Recommend a teaser beat/shot budget + per-role timing for a length (used by `teaser-beats` / `shot-prompts`). |
| `teaser-validate <teaser.json> [--provider <p>]` | Validate the shot schema (hard structural errors; clip-cap per provider). Nonzero exit when invalid. |
| `teaser-critique <teaser.json> [--provider <p>]` | Mechanical pre-generation critique (advisory flags: appearance-drift, thin-prompt, no-palette/-reference, multi-action, audio-unsupported, missing hook/button, length-mismatch). |
| `teaser-render-prompt <teaser.json> [--shot <id>] [--out-dir <dir>] [--provider <p>]` | Render shot prompt markdown in the provider's **render dialect** (prose for veo/sora/generic/pollinations; terse comma-keywords for runway; concise + Luma camera-enum for luma) and canonical order; `--out-dir` writes `shot_<id>.md` files. |
| `teaser-refs-plan <teaser.json> [--refs-dir <d>] [--art-references-dir <d>]` | Plan the canonical **reference image** per recurring subject (consistency anchor): which shots use each, which already exist (in `teaser/refs/` or a shared `art_references/` plate), which are still missing. |
| `teaser-refs <teaser.json> [--manifest <p>] [--art-references-dir <d>] [--init] [--force]` | **Character-reference manifest + approval status** (Phase 5). Merges the auto plan with a declared `refs.yaml` (per subject: `source` wikimedia\|local\|generate, locked `appearance`/`constraints`, `status` pending→approved→locked) and reports the one **next action** each (declare-source / fetch-source / generate / approve / ready) + the approval gate. `--init` scaffolds `refs.yaml` from the teaser. |
| `resolve-video-provider [--project-yaml <p>] [--cli-provider <X>]` | Resolve the active **video** provider: CLI override → `project.yaml :: video.provider` → `grok` (free default; needs `XAI_API_KEY`). Twin of `resolve-image-provider` (whose default stays `pollinations` for keyframe images). |
| `teaser-render <teaser.json> [--out-dir <d>] [--provider <p>] [--kind auto\|image\|video] [--refs] [--refs-manifest <p>] [--film-style <s>] [--takes <n>] [--shot <id>] [--height <px>] [--token <k>] [--delay <s>] [--max-retries <n>] [--dry-run]` | Render clips/keyframes. `stub` = offline placeholder keyframes (no network/key/quota); `gemini` = reference-conditioned photoreal image keyframes (Nano Banana); `grok` (default) / `kie` / `veo` / `magichour` / `fal` = async video backends; `flow` = manual; `pollinations` = free `flux` keyframe images. `--refs` threads each shot's **approved** references (`refs.yaml`) into reference-capable backends (gemini/fal/pollinations-kontext); only approved/locked subjects flow (approval gate). `--film-style` overrides the typeset art style. Key from `--token` → env → `.env`. `--dry-run` builds the plan + key status; pacing + 429/503 backoff automatic; a 402/auth wall stops the batch. No assembly. See [`teaser-render-providers.md`](teaser-render-providers.md). |
| `teaser-cut-list <teaser.json> [--clips-dir <d>] [--kind image\|video] [--audio <p>] [--fps <n>] [--take <n>]` | Build an editable `cut_list.json` from teaser.json + the clips on disk (ordered clips + durations + text-card notes). Plan only; reports shots with no clip. |
| `teaser-ffmpeg-cmd <cut_list.json> [--out <mp4>]` | Print the (shell-ready) ffmpeg command that stitches a cut-list into one mp4. The command body runs it via `bash`; Python never invokes ffmpeg. |

`autonovel mechanical <subcmd> --help` shows full flags for any
of them. Many emit JSON via `--format json` for piping.

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
