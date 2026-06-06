# PRD — Movie-script mode + 1–3 minute AI-video teaser generator

> **Status:** Draft v0.1 — 2026-06-05. Author-prioritised.
> **Owner:** TBD. **Parent todo:** FUTURE-TODOS.md → "🎬 MOVIE-SCRIPT
> MODE FOR AI VIDEO + 1–3 MINUTE TEASER GENERATOR".
> **Relationship to other specs:** this is a *focused subset* of the
> combined "Movie script + theater play output formats" entry, and the
> *minimum viable slice* of the "🚀 ULTRA-LONG-TERM: Script → full
> video pipeline" entry. It deliberately stops at a teaser so a single
> author can run it end-to-end at real cost and iteration speed.
>
> Sections marked **⏳ RESEARCH-PENDING** are being filled from a live
> web-research pass on 2025–2026 AI-video prompting (see References).
> Do not hand-author those from memory — reconcile against the report.

---

## 1. Problem & motivation

autonovel produces novels (PDF + ePub + audiobook) from a shared
foundation (world / characters / outline / canon / per-character voice
fingerprints). The author wants a **movie** path — specifically, the
ability to turn a story into a **richly-described 1–3 minute
teaser/preview** whose shots are emitted as prompts ready to paste into
(or, later, drive via API) an AI video generator.

Two facts shape the whole design:

1. **Teaser-first is the right wedge.** A full AI-generated film is a
   200–300 hr research problem (see the ultra-long-term todo). A
   teaser is the *same machinery at 1/30th the scale*: shot
   decomposition, descriptive prompting, and character/style
   consistency across many short clips — but cheap and fast enough that
   one author can iterate on it tonight.
2. **Every current video model emits short clips.** Native clip length
   across providers is roughly 4–10 s. A 1–3 minute teaser is therefore
   **an assembled montage of ~15–40 generated clips**, not one long
   generation. The teaser already exercises the assembly + consistency
   problems the full pipeline needs.

The autonovel-shaped insight: the author should *never* have to
hand-write 30 cinematography prompts or manually track which character
looks like what across clips. The foundation already knows the cast's
appearance (`shared/characters.md`, voice.md Part 4), the settings
(`shared/world.md`), the period (`project.yaml`), and the load-bearing
scenes (`eval_logs/` pacing + irreversible-change dimensions). The tool
turns that into provider-ready, heavily-descriptive shot prompts.

## 2. Goals / non-goals

### Goals (v1)
- Produce a **teaser beat-sheet** (8–20 beats, trailer-craft-aware)
  from a movie script *or* directly from a book's outline + key scenes.
- Generate, per beat, one or more **provider-targeted descriptive shot
  prompts** using a structured field schema, pulling subject/appearance/
  setting/period from the foundation.
- Emit **consistency anchors** (reference-image / first-frame /
  character-reference guidance) so the same character & location read
  consistently across the assembled clips.
- Output both **hand-edit-friendly markdown** (one file per shot) and a
  **machine `teaser.json`** describing the full teaser.
- Be **provider-aware**: a `--provider` profile tunes prompt phrasing,
  length, and which fields are emitted (e.g. audio cues only for
  audio-capable models).

### Goals (v1.5, optional)
- **Assembly spec**: a `cut_list.json` + ffmpeg concat that stitches
  user-generated clips into the finished teaser with a music bed and
  text cards.

### Non-goals (explicitly out of scope here)
- Calling video-generation APIs and rendering clips automatically
  (that's the ultra-long-term pipeline; v1 emits prompts the user
  pastes/feeds themselves — though the schema is API-ready).
- Full-length film generation, shot-by-shot for an entire screenplay.
- Stage-play / theater output (lives in the parent combined entry).
- The full screenplay typesetting path (Fountain/`.fdx`/Courier PDF) —
  inherited from the parent entry; the teaser only needs *enough*
  script structure to decompose into shots, not industry-perfect
  typeset. If a screenplay already exists, we read it; if not, we work
  from the outline.

## 3. Users & primary stories

- *"I have a finished autonovel book and want a teaser to share."* →
  `/autonovel:teaser --book <name>` works from outline + key chapters;
  no screenplay required.
- *"I wrote/adapted a movie script and want a teaser from it."* →
  teaser reads the script's scene headings + action + dialogue.
- *"I'll generate the clips in Sora/Veo/Runway myself — give me prompts
  I can paste."* → markdown shot files, copy-paste ready, provider-tuned.
- *"Keep my protagonist looking the same across every shot."* →
  consistency anchors + a reference-image plan per character.

## 4. Proposed command surface

Generic-tool / frontmatter conventions per CLAUDE.md. Tiers tentative.

| Command | Tier | Purpose |
|---|---|---|
| `/autonovel:teaser --book <name> [--from script\|outline] [--length 60\|90\|120\|180] [--provider sora\|veo\|runway\|kling\|generic]` | heavy | Top-level: beat-sheet → shots → prompts → teaser.json. Orchestrates the steps below. |
| `/autonovel:teaser-beats --book <name> [--length <sec>]` | standard | Just the beat-sheet (hook → escalation → title → button). Hand-edit target before prompt generation. |
| `/autonovel:shot-prompts --book <name> [--provider <p>] [--beats <range>]` | heavy | Beats → descriptive shot prompts. The core deliverable. |
| `autonovel mechanical teaser-assemble <book_root>` (+ `/autonovel:teaser-assemble`) | light/n-a | v1.5 — ffmpeg concat of user-provided clips per `cut_list.json` + music + text cards. |

Reuse, don't reinvent: shot-prompt generation should lean on the
existing `art-prompts` / `art-curate` machinery and the
`shared/art_references/` coherence library rather than a parallel
stack.

## 5. Data inputs (what the generator reads)

| Field | Source |
|---|---|
| Character appearance, age, distinguishing features | `shared/characters.md`, voice.md Part 4 |
| Setting / location look, architecture, environment | `shared/world.md` |
| Period / region (wardrobe, props, lighting era) | `project.yaml :: period`, `region` |
| Which scenes are load-bearing / high-tension | `eval_logs/` (pacing, irreversible_change dims) |
| Scene structure, dialogue, action (if a script exists) | `books/<name>/scripts/screenplay/` |
| Visual style anchors (palette, grade, lens look) | `art/visual_style.json` |
| Cross-clip character/location consistency refs | `shared/art_references/` |

## 6. File layout (proposed)

```
books/<name>/
  teaser/
    beats.md                 # the beat-sheet (hand-editable)
    teaser.json              # machine spec: ordered shots + timings + refs
    shots/
      shot_01.md             # one descriptive prompt per shot (hand-editable)
      shot_02.md
      ...
    cut_list.json            # v1.5 — assembly/edit spec
    refs/                    # v1.5 — reference frames per character/location
```

## 7. Provider landscape (research-grounded, 2025–2026)

> Synthesised from a 2026-06-05 web-research pass on primary provider
> docs. **Everything here is fast-moving** — versions, audio support,
> consistency features, and pricing all shifted within months. The
> generator must read capabilities from a **config table**, not
> hardcode them. Sources in §17.

| Provider / model | Max clip (native) | T2V / I2V | Native audio | Consistency feature | Camera control | API | Rough price |
|---|---|---|---|---|---|---|---|
| **OpenAI Sora 2 / Pro** | 16–20s native, extend to **120s** | ✅ / ✅ (`input_reference` first frame) | ✅ dialogue + SFX | **Characters API** (reusable from 2–4s ref clip; name verbatim in every prompt) | prompt-only | `POST /v1/videos` async. **⚠️ deprecated — API shutdown 2026-09-24** | $0.10–0.70/s; batch ~50% off |
| **Google Veo 3.1 / Fast / Lite / 3 / 2** | **4 / 6 / 8s** (+extend, 720p) | ✅ / ✅ | ✅ **always-on** (3.x) | **up to 3 reference images** + first/last-frame | rich via prompt vocab | Gemini API + Vertex, async poll | 3.1 video+audio $0.40/s; Fast $0.10–0.12; Lite $0.05; video-only $0.20 |
| **Runway Gen-4 / Turbo / Gen-3a** | **5 or 10s** | ✅ / ✅ (reference-driven) | ❌ (silent) | **Gen-4 References** — char/world lock from a *single* image, no fine-tune | prompt; Aleph for v2v | async tasks, SDK | credits @ $0.01 |
| **Kling v3 / 2.6 / 2.5-turbo** | **5 / 10s** | ✅ / ✅ + first/last-frame, reference-to-video, lipsync | ✅ in 2.5+ | face/char ref, lipsync avatars | director camera tokens | official (gated) + via fal/Replicate | per-video |
| **Luma Ray 2 / Flash** | 5s (+Extend) | ✅ / ✅ (keyframes) | via separate add-audio | keyframes (start/end), loop | **Camera Concepts enum** (explicit tokens) | Dream Machine API, async + callbacks | credits |
| **Hailuo / MiniMax (Hailuo-02)** | **6 / 10s** | ✅ / ✅ (first-frame) | partial | subject reference | "Director" camera tokens | official + fal/Replicate | per-video |
| **Pika / Adobe Firefly Video** | ~5–10s | ✅ / ✅ | partial / limited | ingredients / brand controls | UI camera params | limited / enterprise | low / enterprise |
| **Open local (SVD, Wan 2.x, LTX, Mochi, CogVideoX)** | SVD ≤4s; Wan 5s | Wan ✅ / SVD I2V-only | ❌ | **LoRA / fine-tune**, seed reuse | limited | self-host / Replicate / fal | Wan $0.09–0.25/s; SVD free weights |

**Strategic conclusions that shape the design:**
- **Only Veo 3.x and Sora 2 generate synchronised native audio (dialogue + SFX).** Decisive for a teaser that wants temp dialogue stings — but ~2× the cost. Everything else is effectively silent → score in post.
- **Consistency mechanisms differ sharply** (Runway single-ref lock vs Sora reusable Characters vs Veo 3-ref vs Luma keyframes vs open-model LoRA), so the consistency-anchor output (§10) must be *provider-shaped*.
- **For an automated backend, target an aggregator** — **fal.ai** (broadest: Veo, Kling, Hailuo, Wan, Seedance, LTX) or **Replicate** (per-second billing, Cog) — so we can swap model per shot/per budget. Treat the **Sora 2 API as time-boxed** (shutdown 2026-09-24); don't hard-couple.
- **`--provider` profiles to ship in v1:** `generic`, `veo`, `sora`, `runway`, `kling`, `luma`. Each is a small config record (native clip length, audio support, field-render dialect, consistency primitive).

## 8. Prompt field schema & anatomy (the core deliverable)

The providers converge on one skeleton (most explicit in Veo's "anatomy
of a prompt" and Sora 2's "prompt anatomy"). **Canonical field order**
(Veo/Sora): **Subject → Action → Scene/context → Camera angle → Camera
movement → Lens & optical → Visual style (lighting / tone / palette) →
Temporal → Audio**, with **negative prompt and dialogue as *separate*
fields**, not prose.

Key cross-provider rules the generator must encode:
- **One subject action + one camera move per clip** — the single most
  repeated rule (Veo + Sora). Multi-action clips degrade.
- **Reuse the character's appearance phrasing *verbatim* across every
  shot** — small phrasing changes alter identity (Sora).
- **Name a 3–5 colour palette + a fixed lighting logic globally** —
  what makes cut-together clips read as one film.
- **Separate API-parameter fields from prose** — duration, resolution,
  aspect, seed, references, negative prompt, dialogue block are params,
  never "make it 8 seconds" inside the prose.
- **Length tradeoff:** longer prompts give control but *restrict
  creativity* (Sora); Runway/Luma reward terser, camera-move-first
  phrasing. Provider profiles tune verbosity.

**Model-agnostic per-shot schema we implement** (stored in
`teaser.json`; rendered to `shot_NN.md` and, later, to each provider's
request shape):

```yaml
shot:
  id: "S07"
  role: "escalation"            # hook | escalation | title | button
  duration_s: 4                 # clamp to provider native (Veo 4/6/8; Runway 5/10; Luma 5)
  aspect_ratio: "16:9"
  # visual prose (rendered in Veo/Sora order) ---
  shot_size: "medium close-up"
  camera_angle: "low-angle"
  subject:
    name: "ELENA"               # verbatim every shot (consistency)
    appearance: "early 30s, rain-soaked auburn hair, scarred left brow, charcoal trench coat"
  action: "She lifts her eyes from the letter; her jaw tightens."   # ONE action, in beats
  setting: "abandoned tram depot, midnight, thin fog"
  lighting: "low-key, single sodium-vapour practical, cool door rim"
  palette: ["amber", "slate blue", "rust"]    # 3-5 anchors, identical across shots
  camera_movement: "slow push_in"             # Luma-enum token where applicable
  lens: "85mm, shallow depth of field, soft bokeh"
  style: "cinematic, shot on 35mm film, subtle grain, teal-and-orange grade"
  mood: "tense, foreboding"
  # audio (separate block; only emitted for Veo 3.x / Sora) ---
  audio:
    ambience: "distant tram hum, dripping water"
    sfx: "a single metallic clang off-screen"
    dialogue: [{speaker: "ELENA", line: "They were never coming back."}]  # 1-2 short lines / 4s
  # separate negative field (Veo / Kling) ---
  negative_prompt: "blurry, distorted hands, extra limbs, watermark, text, subtitles, flicker, morphing"
  # consistency anchors ---
  reference_image: "refs/elena_canonical.png"  # → first_frame / input_reference / Gen-4 ref
  last_frame: null                             # chain → next shot's first_frame
  seed: 12345                                  # weak determinism only
  # assembly metadata ---
  text_card: null                              # render in NLE, NOT in the model
```

**Per-provider render rules** (the `--provider` profile's job):
- **Veo** — one rich prose paragraph in canonical order; `negative_prompt`,
  `seed`, `aspectRatio`, `resolution`, `duration`, up to 3 reference
  images go in config.
- **Sora 2** — prose storyboard paragraph + separate `Dialogue:` block;
  `size`/`seconds`/`characters`/`input_reference` are params; prefer
  **2×4s over 1×8s**.
- **Runway** — terser; lead with the camera move, attach the reference
  image, drop long style prose.
- **Luma** — map `camera_movement` to the **concept enum** token; use
  `keyframes` for first/last; add-audio separately.

## 9. Cinematography vocabulary (terms that reliably steer the models)

The generator must emit *these* terms (from Veo's guide + Sora examples
+ Luma's literal camera-concept API enum — the strongest signal, since
those are accepted parameter values), not arbitrary prose.

- **Shot sizes:** extreme close-up · close-up · medium close-up ·
  medium · full/long · **wide / establishing** · over-the-shoulder ·
  **POV** · two-shot.
- **Angles:** eye-level · low-angle · high-angle · **bird's-eye /
  top-down** · worm's-eye · **dutch / canted**.
- **Camera moves (Luma enum tokens):** static · pan · tilt · **dolly
  in/out** · `truck_left/right` · `pedestal_up/down` · `zoom_in/out` ·
  `crane_up/down` · aerial/drone · handheld · whip pan ·
  `orbit_left/right` · `push_in` / `pull_out` · `dolly_zoom` (vertigo).
- **Lens / optical:** wide-angle · telephoto · **shallow DoF / bokeh** ·
  deep focus · lens flare · rack focus · fisheye · literal focal
  lengths ("85mm", "35mm handheld", "vintage 16mm").
- **Lighting:** soft morning sun · moonlight · firelight · candlelight ·
  **neon** · **Rembrandt** · **film-noir deep shadows** · high-key ·
  low-key · **volumetric rays** · backlight/silhouette · **golden hour**.
- **Style / film stock / era:** "shot on **35mm film**" · anamorphic ·
  "cinematic film look" · era looks (1950s Americana, 1980s vaporwave,
  1920s sepia + grain) · animation styles · artist styles. Naming
  "90s documentary" lets the model auto-pick lens/grade/colour.
- **Palette:** name **3–5 colour anchors** ("amber, cream, walnut") and
  hold them across shots — keeps the edit seamless.
- **Temporal:** slow-motion · fast-paced · time-lapse.
- **Editing terms (sequence prompts):** match cut · jump cut · montage ·
  establishing-shot sequence · split-diopter.

These map directly to `project.yaml :: period`/`region` (era look) and
`art/visual_style.json` (palette, grade, lens look) so the foundation
drives the vocabulary rather than the user typing it.

## 10. Cross-shot consistency (the load-bearing problem)

Stitching 15–40 clips into one coherent teaser only works if character,
location, and style hold across clips. Provider mechanisms:

| Mechanism | Provider |
|---|---|
| Single reference image → character/world lock (no fine-tune) | **Runway Gen-4 References** |
| Reusable **Character** asset from a 2–4s ref clip (name verbatim each prompt) | **Sora 2 Characters API** |
| `input_reference` first frame conditions the opening frame | **Sora 2** + most I2V |
| **Up to 3 reference images** (person/product) | **Veo 3.1** |
| **First + last frame interpolation** (pin both endpoints) | **Veo 3.1, Kling, Luma keyframes** |
| Extend / continue using prior clip as context | **Sora extend→120s, Veo, Luma, Kling** |
| Face/char ref + lipsync | **Kling, Hailuo** |
| Seed reuse (improves, never guarantees) | most diffusion models |
| LoRA / fine-tune | open models (Wan, SVD) |

**The workflow the tool automates** (corroborated across Sora + Veo
guides):
1. Generate a **canonical reference image per character + key location**
   first (consistent image model) → store under `teaser/refs/`.
2. Feed that image as **reference / first frame** into every clip with
   that subject.
3. **Reuse the exact appearance phrasing** across prompts (the schema's
   `subject.appearance` is written once and copied verbatim).
4. Hold **lighting logic + 3–5 colour palette** identical across clips.
5. Chain **last-frame-of-N → first-frame-of-N+1** for continuous action.

This is exactly where `shared/art_references/` (cross-book illustration
coherence) and `art/visual_style.json` plug in. **Honest limitation:**
identity drift on long prompts, reference features are partly gated, and
seeds aren't deterministic anywhere — v1 must set expectations and lean
on reference-image workflows rather than promise frame-perfect identity.

## 11. Teaser craft, failure modes & negative prompts

**Teaser structure (60–180s)** — sells tone + a question, not plot:
1. **Cold hook (0–10s)** — one arresting image/line; strongest single shot.
2. **Escalation montage (10–60s)** — accelerating shots, rising stakes,
   intercut with **text cards**; pacing tightens.
3. **Title card (mid or ~⅔ in).**
4. **Button / stinger (final 5–10s)** — a last shock or unanswered
   question after the title.

Craft levers the beat-sheet command encodes: **music + sound design
carry it** (build to a drop on the title card); **withhold** (fragments,
not resolutions); **text cards do narrative heavy lifting cheaply and
dodge AI lipsync weakness**; **rhythm** ramps from 4–6s opening shots to
1–2s in the escalation, then holds the final image.

**Failure modes** (all diffusion video): morphing/identity drift,
flicker, extra/melting limbs, garbled in-frame text, physics
violations, unwanted camera drift, slow/no motion.

**Negative prompts — the critical syntax rule (Veo, authoritative):**
- ✅ describe what you don't want as **content words**: `blurry, low
  quality, distorted hands, extra fingers, extra limbs, mutated,
  watermark, text, subtitles, jpeg artifacts, flickering, morphing`.
- ❌ **never** use `"no walls"` / `"don't show…"` — the model parses the
  content words, so negation backfires.

Negative prompt is a **separate field** (Veo, Kling); Sora/Runway lean
on positive prompting + references + single-change `edits`. **Reliable
artifact reducers** (baked into the generator's defaults): use
image/first-frame references; one action + one camera move + short clip;
**render text cards in the editor, never ask the model for legible
text**; higher resolution; iterate with single-change edits; ship the
standard negative bank above.

**Cost transparency (surface in the teaser footer):** standard
cinematic ≈ $0.05–0.25/s, audio/premium ≈ $0.30–0.70/s; multiply by
total generated seconds **including ~3× rejected takes**. A 90s teaser
(~30 shots × ~5s × 3 takes ≈ 450s) ≈ **~$90** at $0.20/s, more with
Veo-audio/Sora-Pro, less with Fast/Lite/open models.

## 12. Evaluator rubric (teaser-specific)

A novel's "interiority" dimension is meaningless for a teaser. New
light rubric dimensions (LLM-judged, per the candidate-generator
discipline — no brittle regex): shot variety, pacing variation,
hook strength, withholding (does it spoil the ending?), visual
specificity of each prompt, character-consistency-anchor coverage. Scene
beat coverage carries over from `scenes.py`.

## 13. Phasing

- **Phase 1 — beat-sheet + shot-prompt generator (the wedge).**
  `/autonovel:teaser-beats` + `/autonovel:shot-prompts`, generic
  (`--provider generic`) prompt schema, markdown + `teaser.json`
  output, reading the foundation. No assembly, no API calls.
- **Phase 2 — provider profiles + consistency anchors.** Per-provider
  phrasing tuning; reference-image/first-frame guidance per shot;
  `shared/art_references/` integration.
- **Phase 3 (v1.5) — assembly.** `cut_list.json` + ffmpeg concat +
  music bed + text cards → finished `.mp4` from user-supplied clips.
- **Phase 4+ — API rendering.** Folds into the ultra-long-term
  video-pipeline entry; out of scope for this PRD.

## 14. Testing (per repo tiers)

- **Tier 1 (deterministic):** `teaser.json` schema validity; shot-file
  field completeness; provider-profile field gating (e.g. no audio cue
  for non-audio providers); beat-count bounds vs `--length`; foundation
  inputs parsed correctly; ffmpeg `cut_list.json` shape (v1.5).
- **Tier 2 (contracts):** every `reads:`/`writes:` path in each new
  command's frontmatter appears in its body.
- **Tier 3 (smoke):** one fixture generates a beat-sheet + ≥1 shot
  prompt end-to-end under subscription auth.
- Keep brittle Python out of quality gates (per
  `feedback_avoid_brittle_python.md`): the *structure* is mechanical
  and testable; *quality* of prompts is the LLM judge's job.

## 15. Doc-sync surfaces (PRECONDITION FOR GREEN)

Per `feedback_keep_docs_in_sync.md`, EVERY surface updates with the
feature: `commands/*.md` (new commands), `docs/commands.md`,
`docs/operating-guide.md` (new "Making a teaser" walkthrough),
`README.md` (feature list), `src/autonovel/templates/series/CLAUDE.md`,
`commands/help.md` (new topic), the TUI (`tui.py` help/tabs if it
surfaces teaser state), `docs/troubleshooting.md` (provider/clip
gotchas), `FUTURE-TODOS.md` (mark shipped), `STATE.md` (decision log +
green count). Run the doc-sync audit grep before declaring done.

## 16. Risks & open questions

- **Model quality is the gating variable.** Output usefulness tracks
  provider quality, which moves monthly. Mitigation: we emit *prompts*,
  not renders — value survives even as the best target model changes.
  The `--provider` profile set must be cheap to extend.
- **Consistency across clips is genuinely hard** and partly unsolved at
  the provider level. v1 may have to accept visible drift and lean on
  reference-image workflows; set expectations honestly.
- **Where does the screenplay come from?** Open: does the teaser require
  a full screenplay first (parent entry's typeset work), or is
  outline-driven teaser generation enough for v1? Leaning
  outline-driven for v1 to decouple from the heavy screenplay-typeset
  work.
- **Provider API churn** — keep API mapping out of v1; emit
  provider-agnostic structured fields + provider-tuned prose.
- **Cost transparency** — the user pays per clip-second at the
  generator; surface an estimated clip count + rough cost range in the
  teaser output footer.

## 17. References

Web-research pass on 2025–2026 AI-video prompting (2026-06-05) —
primary provider documentation synthesised into §§7–11. **Fast-moving:**
versions/audio/consistency/pricing all shifted within months; re-verify
before implementation.

- **Google Veo** — docs: `ai.google.dev/gemini-api/docs/video`; prompt
  guide: `cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide`
  (negative-prompt syntax rule, camera/lighting vocabulary); Vertex
  pricing page.
- **OpenAI Sora 2** — `platform.openai.com/docs/guides/video-generation`;
  Sora 2 Prompting Guide `cookbook.openai.com/examples/sora/sora2_prompting_guide`
  (prompt anatomy, 2×4s advice, Characters); OpenAI pricing.
  ⚠️ API deprecation: shutdown 2026-09-24.
- **Runway** — `runwayml.com/research/introducing-runway-gen-4` (Gen-4
  References); `docs.dev.runwayml.com/api/`.
- **Luma** — `docs.lumalabs.ai` (video-generation.md;
  changelog/concepts.md — the camera-concept enum tokens).
- **Aggregators** — `replicate.com/pricing` (per-second / GPU-time);
  `fal.ai/models` (Veo, Kling, Hailuo, Wan, Seedance, LTX catalog).
- **Open models** — Stable Video Diffusion HuggingFace model card.

Parent todos: FUTURE-TODOS.md "Movie script + theater play output
formats" and "🚀 ULTRA-LONG-TERM: Script → full video pipeline".
