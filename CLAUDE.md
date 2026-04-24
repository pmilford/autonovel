# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`autonovel` is an autonomous pipeline that turns a seed concept into a finished novel (manuscript, typeset PDF, ePub, cover art, audiobook, landing page). It is inspired by `karpathy/autoresearch`: a modify → evaluate → keep/discard loop applied to fiction. All 27 scripts are standalone Python tools orchestrated by `run_pipeline.py`; the agent's job is to call tools and steer the loop, not to write prose inline.

Canonical specs — read these before making non-trivial changes:
- `PIPELINE.md` — full technical spec for phases, thresholds, learned patterns from the "Bells" production run.
- `program.md` — per-phase agent instructions, propagation rules, the Stability Trap.
- `WORKFLOW.md` — user-facing step-by-step.
- `CRAFT.md`, `ANTI-SLOP.md`, `ANTI-PATTERNS.md` — craft reference and AI-tell detection; consumed by writer/judge prompts.

## Common commands

Dependency management is `uv` (see `pyproject.toml`, Python ≥3.12). Always prefix Python invocations with `uv run`:

```bash
uv sync                                   # install deps
uv run python run_pipeline.py --from-scratch   # full pipeline from seed.txt
uv run python run_pipeline.py --phase foundation|drafting|revision|export
uv run python run_pipeline.py --max-cycles 5   # cap revision cycles

# Evaluation (tune what "good" means here)
uv run python evaluate.py --phase=foundation
uv run python evaluate.py --chapter=5
uv run python evaluate.py --full

# Manual revision tools
uv run python adversarial_edit.py all
uv run python apply_cuts.py all --types OVER-EXPLAIN REDUNDANT
uv run python reader_panel.py
uv run python review.py                        # Opus dual-persona review (Phase 3b)
uv run python gen_brief.py --auto
uv run python gen_revision.py 5 briefs/ch05.md

# Typeset to PDF
uv run python typeset/build_tex.py && (cd typeset && tectonic novel.tex)
```

There is no test suite, linter, or build system beyond `uv sync`. Correctness is judged by `evaluate.py` scores and git history (every keep/discard is a commit + a row in `results.tsv`).

## Architecture

### Branch model (important)

- **`master`** holds the reusable framework: tools, docs, and *empty* template shells (`world.md`, `characters.md`, `outline.md`, `canon.md`, `voice.md` Part 2, `MYSTERY.md`, `state.json`).
- **`autonovel/<tag>`** branches hold one novel's filled-in artifacts (`seed.txt`, populated templates, `chapters/ch_NN.md`, `edit_logs/`, `eval_logs/`, `briefs/`, `results.tsv`, `typeset/novel.pdf`). Do not commit novel-specific content to `master`.

### The five co-evolving layers

```
Layer 5:  voice.md          HOW we write
Layer 4:  world.md          WHAT exists
Layer 3:  characters.md     WHO acts
Layer 2:  outline.md        WHAT HAPPENS
Layer 1:  chapters/ch_NN.md THE ACTUAL PROSE
Cross-cut: canon.md         WHAT IS TRUE (hard-fact DB)
```

Changes propagate both downward (lore change → outline → chapter rewrite) and upward (a chapter reveals a gap → update lore → check downstream). `state.json` tracks phase, scores, iteration count, and pending propagation debts.

### Pipeline phases (driven by `run_pipeline.py`)

1. **Foundation** — loop `gen_world` → `gen_characters` → `gen_outline`(+`_part2`) → voice discovery → `gen_canon` → `evaluate.py --phase=foundation`. Keep if score improved (git commit), else `git reset --hard HEAD~1`. Exits when `foundation_score > 7.5 AND lore_score > 7.0`.
2. **Drafting** — for each chapter in outline order, `draft_chapter.py` then `evaluate.py --chapter=N`; keep if `> 6.0`, up to 5 retries. New facts get appended to `canon.md`. Forward progress over perfection.
3. **Revision** — cycles of `adversarial_edit.py` → `apply_cuts.py` (OVER-EXPLAIN + REDUNDANT dominate) → `reader_panel.py` (4 personas) → briefs → `gen_revision.py`. Stop when score delta `< 0.3` across two consecutive cycles (`PLATEAU_DELTA` in `run_pipeline.py`), capped at `MAX_REVISION_CYCLES = 6`.
4. **Phase 3b — Opus review loop** — `review.py` sends the whole manuscript to Opus for a literary-critic + professor-of-fiction pass, parses actionable items, iterates until items are mostly qualified hedges.
5. **Export** — `build_outline.py`/`build_arc_summary.py` rebuild docs from chapters, `typeset/build_tex.py` emits `chapters_content.tex`, `tectonic` produces the PDF; ePub uses the `typeset/epub_*` files; landing page is `landing/index.html`.

### Two immune systems in `evaluate.py`

- **Mechanical** — regex scanners for tier-1 banned words (`delve`, `tapestry`, …), em-dash overuse, sentence-length uniformity, fiction clichés. No LLM.
- **LLM judge** — a separate model from the writer (`AUTONOVEL_JUDGE_MODEL` vs `AUTONOVEL_WRITER_MODEL`) to avoid self-congratulation bias. Uses the `context-1m-2025-08-07` beta header for 1M-token context.

`evaluate.py` is treated as **read-only during autonomous runs** — the human tunes it to change what "good" means; the agent treats it as a black box.

### Models and API

Configured via `.env` (see `.env.example`):
- `AUTONOVEL_WRITER_MODEL` — drafting/revision (default Sonnet)
- `AUTONOVEL_JUDGE_MODEL` — evaluation (default Opus; must differ from writer)
- `AUTONOVEL_REVIEW_MODEL` — Phase 3b Opus review
- `ANTHROPIC_API_KEY` required; `FAL_KEY` (art) and `ELEVENLABS_API_KEY` (audiobook) are optional.

Tools talk to the API via `httpx` directly — there is no Anthropic SDK dependency.

### Orchestrator conventions (`run_pipeline.py`)

- Tools are invoked as subprocesses (`uv run python <script>`); do not import them as modules.
- Every keep/discard is a git commit; `results.tsv` mirrors commits with columns `commit / phase / score / word_count / status / description`.
- Thresholds and caps live as module constants at the top: `FOUNDATION_THRESHOLD`, `CHAPTER_THRESHOLD`, `MAX_FOUNDATION_ITERS`, `MAX_CHAPTER_ATTEMPTS`, `MIN_REVISION_CYCLES`, `MAX_REVISION_CYCLES`, `PLATEAU_DELTA`. Tune there, not inline.
- State lives in `state.json`; `load_state()` / `save_state()` / `default_state()` are the only correct entry points.

## Gotchas (learned in the Bells production)

- **Don't over-compress.** Any chapter below ~1800 words becomes the new weakest. Sweet spot for compressed chapters is 2200–3000w.
- **`gen_revision.py` overshoots** by ~30% — brief 3200w, expect 3800–4200w.
- **Pacing ≈ 7 is a likely ceiling** for investigation-heavy plots; fixing one stretch just exposes the next. Stop after two rotations of "weakest chapter."
- **OVER-EXPLAIN (~32%) and REDUNDANT (~26%)** dominate adversarial cuts — prioritize these filters in `apply_cuts.py`.
- **Chapter renumbering** after merges/deletes must be done by script, never hand-edited.
- **The Stability Trap** (see `program.md`) — AI defaults to safe, round-edged endings; revisions should actively push toward irreversible change, cost, and mystery.
