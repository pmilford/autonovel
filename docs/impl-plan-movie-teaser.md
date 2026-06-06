# Implementation & Testing Plan — Movie-teaser mode

> **Companion to** [`prd-movie-teaser-mode.md`](prd-movie-teaser-mode.md)
> (the *what/why*). This is the *how/when*. **Status:** v1 — 2026-06-05.
> **Baseline:** tag `pre-movies` @ `e252f71`; Tier 1+2 = **1503 passed,
> 1 skipped** (verified 2026-06-05). **Prime directive: do not break the
> existing book-writing pipeline — additive-only, regression-gated.**

---

## Status & resume pointer (updated 2026-06-05)

**Shipped** (all additive, regression-gated; existing pipeline intact):
- **Phase 0** — `src/autonovel/teaser/` package; additive `teaser`/`video`
  dicts on `ProjectConfig`; `[video]`/`[scripts]` extras stubs; docs split
  (`docs/teaser-craft.md`); install-immutability guard tests.
- **`/autonovel:treatment`** — film treatment + 2-page brief (X-Prize).
  Validated end-to-end on the Fugger book (`~/books/medieval-king-maker`,
  repo `pmilford/medieval-king-maker`, tag `first-movie-brief`).
- **Phase 1 (atomic commands)** — `src/autonovel/teaser/{shots,beats,
  render_prompt,providers,critique}.py`; mechanical CLI `teaser-plan` /
  `teaser-validate` / `teaser-critique` / `teaser-render-prompt`;
  commands `/autonovel:teaser-beats` + `/autonovel:shot-prompts` (free,
  with built-in pre-generation critique).
- **Phase 1 final** — `/autonovel:teaser` orchestrator (chains
  teaser-beats → shot-prompts, each in a fresh `task` subagent) +
  standalone `/autonovel:teaser-critique` (mechanical linter + LLM
  critic, read-only, writes `teaser/critique.md`). Robustness guard on
  `shots.load`. `shot-prompts` validated end-to-end on the Fugger book
  (35 shots / 144s / clean critique).
- **Phase 2** — per-provider render *dialects* in `render_prompt.py`
  (`render_visual`: prose veo/sora/generic, terse Runway, Luma enum) +
  `teaser/refs.py` reference-image plan + `teaser-refs-plan` CLI, wired
  into shot-prompts; `shared/art_references/` fallback.
- **Phase 3.5** — thin **Pollinations** render adapter
  (`teaser/render.py`: stateless deterministic-seed URLs, injectable
  httpx seam, per-clip failure isolation) + `resolve-video-provider` +
  `teaser-render` CLIs + `/autonovel:teaser-render` command (resolve →
  dry-run plan → download → vision KEEP/REGENERATE/UPGRADE-TO-PAID
  critique → `clips/render-report.md`). Bright lines held: clips on disk
  only, no state file, no auto-assembly, paid providers only recommended.
- **Phase 3** — ffmpeg assembly: `teaser/assemble.py` (`CutList` +
  `build_cut_list` + PURE `ffmpeg_command` planner; never runs ffmpeg) +
  `teaser-cut-list`/`teaser-ffmpeg-cmd` CLIs + `/autonovel:teaser-assemble`
  (ffmpeg via `bash` + viewer-panel cut critique). v1: hard cuts, no
  burned-in text.
- **Phase 4** — **real free render backends** (`teaser/backends.py`):
  Pollinations' free no-key promise broke externally (402 on images; no
  free video), so this adds genuine free/cheap scriptable backends —
  `grok` (DEFAULT; native dialogue+music, 5 free/day + $25, no card),
  `kie`, `veo` (Gemini API), `magichour`, `fal`, manual `flow`, and an
  offline `stub` to validate the pipeline for $0/zero-quota. `Net` HTTP
  wrapper + `RateLimiter` (429/503 backoff) + key resolution (`--token`
  → env → `.env`). Pollinations demoted to images-only + free-token +
  early-402. `resolve-video-provider` default pollinations→grok.
  Model-pin default flipped to OFF (`--pin-model` opt-in). New
  `docs/teaser-render-providers.md`. See STATE 2026-06-06.
- **Phase 5.1** — **character-reference manifest + approval gate**
  (`teaser/refmanifest.py`): per-subject declared source (wikimedia PD
  art / local / generate), locked appearance+constraints, status
  pending→approved→locked, and a `build_status` planner with one
  `next_action` each + an approval gate (`unapproved_subjects`). CLI
  `teaser-refs` (`--init` scaffolds `refs.yaml`) + command
  `/autonovel:teaser-refs` (declare via wikimedia-*/art-import/generate
  → approve/lock); advisory gate wired into `teaser-render`. Reuses
  `refs.py`/`wikimedia-*`/`art-import`. **NEXT (5.2):** feed locked refs
  into the backends as image-to-video input (grok/veo/kie); morph step.

**Baseline now:** Tier 1+2 = **1635 passed, 1 skipped, 0 failed**
(`pytest tests/deterministic tests/contracts`). Rollback tag
`pre-movies`. `autonovel` is editable-installed from this repo; re-run
`autonovel install` after adding commands.

**STATUS: ✅ The movie-teaser pipeline is complete end-to-end** —
`treatment` → `teaser` (`teaser-beats` → `shot-prompts`) →
`teaser-critique` → `teaser-render` → `teaser-assemble`. All planned
phases (0, 1, 1-final, 2, 3.5, 3) shipped, plus **Phase 4** (real free
render backends + offline `stub` + model-pin flip), additive,
regression-gated. Backend/key map: `docs/teaser-render-providers.md`.

**Future polish (not blocking):** crossfades/transitions in the
cut-list; burned-in title cards via an editor-export step; the Veo
$300-credit **Vertex** path; a **character-reference + approval**
workflow (Phase 5 — seed refs from PD art, morph, lock before spend);
native-audio vs `--audio` bed mixing in assemble; `--kind video`
validated on more providers; a smoke (Tier-3) test that renders one real
`stub`/`grok` clip.

Every step: hold the ≥1635 gate, additive-only, full doc-sync, append a
STATE.md decision entry + bump the green count.

---

## 0. The safety contract (read first — it governs every phase)

The user's hard constraint: *"be careful that we do not break the
existing book writing tools in any way."* Every phase obeys these
non-negotiable rules:

1. **Additive-only.** New files, new commands, new CLI subcommands, new
   optional `project.yaml` keys. **Never change the behaviour or
   signature of an existing function, command, or template.** Reuse =
   *call* existing helpers, never edit them. The one allowed touch of an
   existing file is **purely additive** (see §2.3 `project.py`).
2. **New code lives in a new package:** `src/autonovel/teaser/`. Blast
   radius for existing modules ≈ zero.
3. **Regression gate on every commit.** `pytest tests/deterministic
   tests/contracts -q` must report **≥ 1503 passed** (prior count + new
   tests) and **0 failed, 0 newly-skipped**. A drop = stop and fix
   before continuing. No exceptions.
4. **The `pre-movies` tag is the rollback point.** If anything
   destabilises, `git reset --hard pre-movies` restores the
   feature-complete novel pipeline.
5. **Existing fixtures untouched.** Movie tests use the existing
   `tests/fixtures/tiny-series-scifi/` read-only or a *new* teaser
   fixture; never mutate the shared novel fixtures.
6. **Optional dependencies only.** Any new Python dep goes in a new
   `[video]` / `[scripts]` extras group — never the base install. A user
   who never touches teaser mode installs and runs exactly as today.
7. **Doc-sync is a precondition for green** (per
   `feedback_keep_docs_in_sync`) — every phase updates all doc surfaces
   in its Definition of Done, not "later".
8. **Inherit lifecycle, don't reimplement.** New commands use the
   preamble/postamble (`_begin`/`_end`) contract for lock/checkpoint/log
   — never hand-roll it.

**Definition of "not broken":** after each phase, (a) the regression
gate is green, (b) `autonovel install` still renders every *existing*
command byte-identically (assert in a test), (c) `autonovel doctor`,
`status`, `new-series` round-trip unchanged, (d) a sample novel-pipeline
smoke (foundation→draft→evaluate on a fixture) still passes.

---

## 1. Architecture & isolation

### 1.1 New package (all new files — zero existing-module risk)

```
src/autonovel/teaser/
  __init__.py
  beats.py          # beat-sheet model + builder helpers (structure only)
  shots.py          # the §8 shot schema: dataclass, validation, teaser.json I/O
  render_prompt.py  # schema -> per-provider prose (the §8 render rules)
  providers.py      # provider capability table (data, fast-moving -> isolated)
  critique.py       # mechanical parts of §24 critique (schema/lint shape)
  videoprovider.py  # resolve-video-provider precedence (twin of image)
  render.py         # Phase 3.5 thin render adapter (HTTP submit/poll/download)
  assemble.py       # Phase 3 ffmpeg cut_list -> mp4
```

CLI: new subcommands registered under the existing `autonovel mechanical`
group **by adding parser branches** in `mechanical/__main__.py` (additive
— new `elif`/subparser only, existing branches untouched). Pattern to
copy verbatim: the existing `resolve-image-provider` branch.

Commands (new `commands/*.md`, auto-installed by the existing adapters):
`teaser.md`, `teaser-beats.md`, `shot-prompts.md`, `teaser-critique.md`,
`treatment.md`, `teaser-coach.md`, then later `teaser-render.md`,
`teaser-assemble.md`.

Docs: `docs/teaser-craft.md` (new, prompt material) + updates to existing
doc surfaces.

### 1.2 Reuse map (call, don't modify — real paths verified 2026-06-05)

| Need | Reuse (read-only call) | How |
|---|---|---|
| Externalize interiority (§18.3) | `mechanical/show_dont_tell.py` | call its detector to find interiority lines → feed as "make visible" notes |
| Beat / scene coverage (§12) | `mechanical/scenes.py` | read scene markers / beat units |
| Character appearance | `shared/characters.md`, voice.md Part 4 | read via existing loaders |
| Load-bearing scenes | `eval_logs/` (pacing, irreversible_change) | read via existing eval-log readers |
| Visual style anchors | `art/visual_style.json` | read |
| Provider precedence pattern | `mechanical/__main__.py::resolve-image-provider` (`_DEFAULT_IMAGE_PROVIDER="pollinations"`) | **copy the pattern** into `videoprovider.py` as a NEW function — do not edit the image one |
| Reference images (consistency) | existing Pollinations image path + `art-curate`/`art-prompts` | drive via command body, same as today |
| Lock / checkpoint / log | `_begin`/`_end` preamble/postamble | inherit |
| Cost surfacing | `cost.py` | read/append only |

### 1.3 The one additive touch of an existing file

`src/autonovel/project.py` — add two optional dict fields **exactly
mirroring the proven `typeset`/`image` pattern** (lines ~93–113):

```python
teaser: dict[str, Any] = field(default_factory=dict)
video: dict[str, Any] = field(default_factory=dict)
```
…and in `to_dict()` the matching `if self.teaser: d["teaser"] = ...`
guard so they're **omitted when empty** → existing `project.yaml` files
round-trip byte-identically. This is the *only* existing-module edit, it
is purely additive, and it is covered by extending the existing
round-trip test. (Mirrors how `typeset`/`image` were added safely.)

### 1.4 Design point — who calls the video API?

Consistent with "no Python calls an LLM": the **LLM/creative** steps
(beat-sheet, shot prompts, critique judgement) are **runtime/command**
work. The **mechanical** steps (schema validation, provider precedence,
HTTP submit/poll/download for a *no-auth* endpoint, ffmpeg assembly) are
**plain Python** invoked via `bash` from the command body — an HTTP GET
to Pollinations is mechanical, not an LLM call, so it belongs in Python
like other `mechanical/*` helpers. Paid/keyed providers (Phase 5) read
keys from env, never from project files.

---

## 2. Phasing (value-first, safety-first ordering)

Each phase is independently shippable, leaves the pipeline green, and
ends with its own doc-sync. **Phase 1 + the treatment command deliver
the durable value (prompts + competition prose) with zero generation
cost.**

### Phase 0 — Scaffolding + docs split (no behaviour change)
*Goal: create the empty structure and move user-facing craft content out
of the PRD, with nothing that can affect existing tools.*

- Create `src/autonovel/teaser/` package (empty modules + `__init__`).
- Add `teaser`/`video` optional dicts to `project.py` (§1.3) + extend
  round-trip test.
- Add `[video]` / `[scripts]` extras stubs to `pyproject.toml`
  (no required deps).
- **Docs split:** create `docs/teaser-craft.md` as the user-facing /
  prompt-material craft guide (the CRAFT.md analogue named in PRD §19).
  Move the *creative content* of PRD §§18–21 (dual-audience principle,
  externalization technique, the AI-legibility linter rules,
  cinematography vocabulary, creative defaults, the hook/ending guidance)
  into it. In the PRD, replace those sections with **concise summaries +
  pointers** to `teaser-craft.md`, and rewire the §§22–24 cross-refs.
  PRD stays the *build spec*; teaser-craft.md is the *deliverable + prompt
  input*.
- **DoD:** regression gate green (1503 + new project.py test); `install`
  byte-identical for existing commands; PRD cross-refs resolve;
  `docs/teaser-craft.md` exists.

### Phase 1 — Beat-sheet + shot-prompt generator (THE WEDGE)
*Goal: story → critiqued, provider-ready shot prompts. Free. No pixels.*

- `teaser/shots.py` — the §8 shot dataclass, validation (one-action,
  duration ≤ provider cap, separate negative/dialogue fields), and
  `teaser.json` read/write.
- `teaser/beats.py` — structure for the beat-sheet (hook/escalation/
  title/button roles, count bounds vs `--length`).
- `teaser/render_prompt.py` — schema → prose in the canonical Veo/Sora
  field order; `generic` profile first.
- `commands/teaser-beats.md` (standard tier) — LLM selects 8–20 teaser
  beats from outline + key scenes + eval_logs; writes `beats.md`.
- `commands/shot-prompts.md` (heavy) — beats → shots; writes
  `shots/shot_NN.md` (dual render: human beat note + machine prompt) +
  `teaser.json`. Reads `characters.md` / voice.md Part 4 / `world.md` /
  `project.yaml::period` / `visual_style.json`. Calls `show_dont_tell`
  detector to externalize interiority.
- `commands/teaser.md` (heavy) — orchestrates beats → shots.
- **Prompt critique built in** (PRD §24.2): `teaser/critique.py`
  (mechanical lint shape) + the command runs the free LLM critic pass,
  emitting `PASS/REWRITE/FLAG` per shot and rewriting weak prompts before
  output. (`teaser-critique.md` can be a thin wrapper exposing it
  standalone.)
- **Independent low-risk parallel deliverable — `commands/treatment.md`**
  (standard): emits the X-Prize ≤12-page treatment + 2-page brief/synopsis
  from world/outline/characters. Pure prose, autonovel's wheelhouse,
  directly required by the competition; ship it early.
- **DoD:** Tier-1 tests for schema/validation/beat-bounds/render;
  Tier-2 contract pickups for the new commands; Tier-3 smoke = one
  fixture produces a valid beat-sheet + ≥1 lint-passing shot prompt;
  regression gate green; full doc-sync.

### Phase 2 — Provider profiles + consistency anchors
- `teaser/providers.py` — capability table (`generic, veo, sora, runway,
  kling, luma, pollinations`): native clip length, audio support, render
  dialect, consistency primitive. **Data, not logic** (fast-moving).
- `render_prompt.py` — per-provider render rules (Veo prose / Sora
  +Dialogue block / Runway terse / Luma enum).
- Consistency-anchor output per shot (reference-image / first-frame /
  char-ref guidance) + a `teaser/refs/` reference-image plan; integrate
  `shared/art_references/`.
- **DoD:** Tier-1 provider-field-gating tests (e.g. no audio cue for
  silent providers; duration clamps per provider); regression green;
  doc-sync.

### Phase 3.5 — Thin render adapter (opt-in; free default backend)
*(PRD §23 — deliberately before full assembly so clips exist to critique.)*
- `teaser/videoprovider.py` — `resolve-video-provider` precedence (CLI →
  `project.yaml::video.provider` → default `pollinations`), twin of the
  image resolver.
- `teaser/render.py` — stateless `submit → poll → download` per shot;
  default **Pollinations** (no-auth); `--takes N`; `--dry-run` (estimate
  + exact requests, submit nothing). **Bright lines (PRD §23.2):** no
  state file, no stale-detection, no auto-assembly — clips on disk, done.
- `commands/teaser-render.md` — drives it; behind explicit flag.
- **Clip critique** (PRD §24.3): vision-LLM judge in the command scores
  takes, auto-selects best, emits `KEEP/REGENERATE/UPGRADE-TO-PAID`.
- **DoD:** Tier-1 for precedence + dry-run plan + manifest shape; Tier-3
  smoke = one real free Pollinations generate + critique; regression
  green; doc-sync.

### Phase 3 — Assembly (v1.5)
- `teaser/assemble.py` — `cut_list.json` → ffmpeg concat + crossfade +
  audio mux + burned text cards → `teaser_vN.mp4`. ffmpeg already a
  `doctor`-checked optional tool.
- `commands/teaser-assemble.md` + **viewer-panel cut critique** (§24.4,
  reuse `reader-panel` shape).
- **DoD:** Tier-1 for `cut_list.json` shape + ffmpeg arg construction
  (don't run ffmpeg in Tier-1); Tier-3 optional if ffmpeg present;
  regression green; doc-sync.

### Phase 5 — Paid-provider upgrade path (later)
- Add keyed providers (Veo/Sora/Runway via env keys or fal/Replicate)
  to `providers.py` + `render.py`; the clip-critic's `UPGRADE-TO-PAID`
  list drives selective spend. Folds toward the ultra-long-term pipeline
  entry; out of scope until the free loop is proven on Fugger.

### Coaching (woven through, not a phase)
- `commands/teaser-coach.md` + the inline `💡`-style rationale in every
  teaser command (PRD §19), content sourced from `docs/teaser-craft.md`.

---

## 3. Testing strategy

### 3.1 The regression gate (protects existing tools)
- **Every commit:** `pytest tests/deterministic tests/contracts -q` →
  must be ≥1503 passed, 0 failed. This is the single most important
  guard for "don't break the book tools".
- **Install-immutability test (new, Phase 0):** assert that for every
  *existing* command, the adapter renders byte-identical output before
  vs after (snapshot). Guarantees new commands don't perturb old ones.
- **project.yaml back-compat test:** an existing fixture `project.yaml`
  (no `teaser`/`video` keys) round-trips unchanged through
  `ProjectConfig`.

### 3.2 Teaser output quality (PRD §24 — the self-critique)
- **Tier-1 (mechanical, deterministic):** `teaser.json` schema validity;
  shot field completeness; one-action / duration-cap / separate-field
  lint checks; identical-appearance-string check across a character's
  shots; critique-report JSON shape; `cut_list.json` shape; results-log
  (`critique_log.jsonl`) shape.
- **Tier-2 (contracts):** every `reads:`/`writes:` in each new command's
  frontmatter appears in its body (auto-covered by existing contract
  harness).
- **Tier-3 (smoke, opt-in, free):** end-to-end on a fixture via real
  Pollinations: beats → shots → prompt-critique → one generate →
  clip-critique. Marked so it can be excluded (`-m "smoke and not
  teaser"`); uses subscription/no-auth, no paid keys.
- **Quality is judged, never regex'd** (`feedback_avoid_brittle_python`):
  "is the prompt good / on-brief?" and "does the clip match intent?" are
  LLM/vision-judge calls. Python only checks *structure*.

### 3.3 Generator regression (building the tool itself)
- **Golden shot-set fixtures:** a few hand-blessed beats → expected
  schema shape; assert the generator keeps producing valid, complete,
  lint-passing prompts across releases (guards LLM-prompt drift — the
  same risk the Bells Tier-4 fixture guards for prose).
- **Provider A/B harness:** same critiqued prompt across providers
  (incl. free Pollinations) → log critic scores side-by-side; data for
  `--provider` defaults and "is paid worth it?".
- **End-to-end on the Fugger book** (PRD §21.1) = the integration test
  and the first real free pass.

---

## 4. Doc-sync checklist (per phase DoD)

Run the audit before declaring any phase done. Surfaces:
`commands/*.md` (new) · `docs/commands.md` · `docs/operating-guide.md`
(new "Making a teaser" walkthrough) · `docs/teaser-craft.md` ·
`README.md` (feature list) · `src/autonovel/templates/series/CLAUDE.md` ·
`commands/help.md` (new topic) · `tui.py` (only if it surfaces teaser
state) · `docs/troubleshooting.md` (provider/clip gotchas) ·
`FUTURE-TODOS.md` (mark items shipped) · `STATE.md` (decision entry +
green count).

---

## 5. Risk register & rollback

| Risk | Mitigation |
|---|---|
| New command perturbs existing install output | Install-immutability snapshot test (§3.1) |
| `project.py` change breaks old `project.yaml` | Omit-when-empty pattern + back-compat round-trip test (§1.3, §3.1) |
| New dep bloats/ breaks base install | Optional `[video]` extras only (§0.6) |
| LLM-prompt drift degrades shot quality silently | Golden shot-set regression (§3.3) + the §24 critic |
| Provider capabilities go stale (fast-moving) | Capabilities isolated as data in `providers.py` (§2 Phase 2) |
| Scope creep render-adapter → full production system | PRD §23.2 bright lines; stateless; flag-gated |
| Free-tool licensing for the final competition cut | PRD §22 caveat; swap to licensed assets before submission |
| Context/time pressure vs deadline | Phase 1 + treatment ship the durable value first; generation is later |
| **Anything destabilises the novel pipeline** | `git reset --hard pre-movies` (§0.4) |

---

## 6. Sequencing vs the X-Prize deadline (2026-08-15)

~10 weeks out (from 2026-06-05). Suggested order to de-risk:

1. **Now:** Phase 0 (scaffold + docs split) + `treatment.md` — gets the
   required competition prose deliverable done early, near-zero risk.
2. **Next:** Phase 1 (beats + shot-prompts + prompt-critique) — run it
   **free on the Fugger book** to debug the system end-to-end.
3. **Then:** Phase 2 (provider profiles + consistency) + Phase 3.5
   (Pollinations render + clip-critique) — first watchable free animatic.
4. **Then:** start the real **optimistic-sci-fi X-Prize project** from
   scratch (foundation → teaser), iterate the cut free, and **spend on
   paid generation (Phase 5) only for the `UPGRADE-TO-PAID` shots** the
   critic flags.
5. Phase 3 assembly automates the stitch when worth it.

---

## 7. Definition of Done (every phase)

- [ ] Regression gate green (≥ prior count, 0 failed, 0 new skips).
- [ ] New Tier-1 tests for all new mechanical structure.
- [ ] Tier-2 contracts pass for new commands.
- [ ] Tier-3 smoke added where a runtime step exists.
- [ ] `autonovel install` byte-identical for existing commands.
- [ ] All doc surfaces updated (§4).
- [ ] `STATE.md` decision entry + green count bumped.
- [ ] `FUTURE-TODOS.md` items marked shipped where applicable.
