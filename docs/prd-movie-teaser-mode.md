# PRD — Movie-script mode + 1–3 minute AI-video teaser generator

> **Status:** Draft v0.3 — 2026-06-05. Author-prioritised.
> **Owner:** TBD. **Parent todo:** FUTURE-TODOS.md → "🎬 MOVIE-SCRIPT
> MODE FOR AI VIDEO + 1–3 MINUTE TEASER GENERATOR".
> **Relationship to other specs:** this is a *focused subset* of the
> combined "Movie script + theater play output formats" entry, and the
> *minimum viable slice* of the "🚀 ULTRA-LONG-TERM: Script → full
> video pipeline" entry. It deliberately stops at a teaser so a single
> author can run it end-to-end at real cost and iteration speed.
>
> **v0.2 adds the creative layer** (§§18–21): scene/shot-description
> craft, a "film-school-in-a-box" coaching layer for first-time video
> makers, concrete creative defaults (shot length, cast size, hook,
> ending reveal-vs-withhold), and two worked target projects (the
> Fugger book + the Future Vision X-Prize entry). §22 is the fully-free
> development tier (local 35B + free video/audio/speech stack). §23
> scopes a *thin, stateless* video-API render adapter that stops short
> of a full production system.
>
> **v0.3** reframes the free tier (§22) around **online tools the
> runtime drives itself** (Pollinations no-auth image+video+audio as the
> default free backend; local GPU demoted to optional fallback), and
> adds **§24 — testing the tool, its results, and the prompts**: a
> three-layer self-critique (prompts → clips → cut) that catches
> failures cheapest-first, before spending time or money.

### Reading order

- **§§1–3** — why, goals, users.
- **§§4–6** — command surface, data inputs, file layout.
- **§§7–11** — the technical prompting engine (providers, schema,
  cinematography vocabulary, consistency, teaser craft) — *research-grounded*.
- **§§12–17** — rubric, phasing, testing, doc-sync, risks, references.
- **§§18–21 — the creative / craft layer** ← start here if you've never
  made a video. Scene-vs-shot craft, coaching, creative defaults, and
  the Fugger + X-Prize worked examples.
- **§22** — fully-free dev tier: **online tools the runtime drives**
  (Pollinations-first) + optional local fallback.
- **§23** — open question: a thin video-API render adapter (vs a full
  production system).
- **§24** — testing the tool, its results, and the prompts: the
  three-layer self-critique loop.

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
- **Phase 3.5 (open question) — thin render adapter.** Optionally call
  a video API to turn one shot prompt into one clip on disk — *without*
  the full production system. See §23.
- **Phase 4+ — full API-driven production.** State tracking,
  stale-detection, coherence fine-tuning, auto-assembly. Folds into the
  ultra-long-term video-pipeline entry; out of scope for this PRD.

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

---

# The creative / craft layer (v0.2)

> 📖 **Docs split (Phase 0, 2026-06-05):** the *user-facing* version of
> the creative layer (§§18–20) now lives in
> [`teaser-craft.md`](teaser-craft.md) — the canonical craft guide and
> **prompt material** (the CRAFT.md analogue the teaser commands read).
> §§18–20 below are retained as the **build spec** (what the generator
> must encode); `teaser-craft.md` is the readable guide a user opens.
> Keep the two in sync; when they drift, `teaser-craft.md` is canonical
> for *wording/coaching* and the PRD is canonical for *schema/behaviour*.
> (§21 worked-projects stays here — it's scoping, not craft.)

> §§7–11 are the *engine* — how to phrase prompts a video model obeys.
> §§18–21 are the *director's chair* — what to point that engine at. For
> a first-time video maker this is the more important half: a perfect
> prompt for the wrong shot still makes a bad teaser. The design
> principle for this whole layer: **autonovel already coaches prose
> craft (CRAFT.md, the explaining judge, the `💡 Maybe try` hints); the
> teaser path should coach film craft the same way — teach, don't just
> emit.**

## 18. Scriptwriting & scene/shot-description craft

### 18.1 The vocabulary, defined once (beat → scene → shot → clip)

A first-timer's biggest confusion is these four words. The tool should
use them consistently and define them in output:

- **Beat** — a single story turning point ("she discovers the ledger is
  forged"). A teaser is built from ~8–20 beats.
- **Scene** — a continuous dramatic unit in one place + time. One scene
  may contain several beats.
- **Shot** — one camera setup: one framing, one move. *This is the unit
  a video model renders.* One scene → many shots.
- **Clip** — the actual generated 4–10 s video file for one shot. Often
  2–4 takes per shot, best one kept.

The pipeline is therefore: **story → beats (teaser arc) → scenes →
shots (the schema in §8) → clips (generated) → cut (assembled).** The
v1 commands stop at *shots* (prompts); the user generates clips and
cuts.

### 18.2 The dual-audience problem (the core craft insight)

A scene description has to serve **two readers at once**, and they want
opposite things:

| Reader | Wants | Hates |
|---|---|---|
| **The human** (you, editing) | narrative meaning, emotion, why this beat matters | a dry list of nouns |
| **The video model** | concrete visible nouns, one action, present tense, what's literally in frame | interiority, abstraction, metaphor, backstory, "she realizes…" |

So every `shot_NN.md` should carry **both renderings**:
1. **Beat note** (1 line, human): *"Tommaso realizes the accounts don't
   balance — the moment the conspiracy becomes real to him."*
2. **Shot prompt** (the §8 schema, machine): *"Medium close-up,
   low-angle. TOMMASO (late 20s, ink-stained fingers, plain woollen
   doublet) snaps the ledger shut, jaw tightening, one slow exhale.
   Candlelit counting-house, ledgers stacked behind. Warm low-key
   light, amber/walnut palette. Slow push-in. 85mm, shallow depth of
   field. Shot on 35mm film. Tense."*

The translation between them is the load-bearing skill, and it's a skill
autonovel already has, inverted:

### 18.3 Externalizing interiority (reuse show-don't-tell, backwards)

Novels live in interiority ("she wondered if he'd betray her"). **Film
has no narrator — the camera can only show behavior.** The adapter must
convert interior states into *visible action*:

- *anxious* → grips the table edge, jaw tight, one hard swallow
- *suspicious* → eyes flick to the door, hand drifts off the cup
- *triumphant* → the smallest smile, shoulders drop

autonovel already ships `show-dont-tell` (a scanner for tell-candidate
interiority lines) and `pov-bleed`. The teaser adapter runs the **same
detection and inverts the fix**: every interiority line in the source
becomes a casting note for *visible behavior* in the shot. This is a
genuine reuse win and should be called out as a Phase-1 dependency.

### 18.4 Rules for an AI-legible shot description (the linter)

The shot-prompt generator (and a teaser-specific lint) should enforce:

- **One subject doing one thing; one camera move.** (Echoes §8.)
- **Present tense, active, concrete.** "Rain hammers the cobbles," not
  "it had been raining."
- **Only what's in frame.** No backstory, no off-screen causes, no
  "because."
- **No un-filmable abstraction/metaphor.** "Her world collapses" →
  pick the visible image that *means* that.
- **Period/wardrobe/props explicit** (pulled from `world.md` +
  `project.yaml :: period`).
- **No legible on-screen text** — render title/subtitle cards in the
  editor, not the model (§11).
- **No named real people / trademarked characters** (also a
  competition-rules concern; see §21).
- **Name the subject identically every time** (consistency; §10).

### 18.5 From a finished novel vs from scratch

- **Adapting the Fugger book:** the prose already has scenes, beats,
  dialogue, POV, and per-character voice (voice.md Part 4). Adaptation =
  *select + externalize + compress*, not invent. Read `eval_logs/`
  pacing + irreversible-change to find the shots that must survive.
- **From scratch (the X-Prize sci-fi entry):** the foundation
  (world/characters/outline) is medium-agnostic — generate it normally,
  then enter teaser mode. The drafter writes *shots*, not chapters.

## 19. Creative coaching — "film-school-in-a-box"

The user has never made a video and explicitly wants the system to
*teach* while it works. This is a first-class feature, not a docs
afterthought. Three coaching surfaces:

1. **Inline rationale in every command.** Like the existing `💡 Maybe
   try` hints, each teaser command explains *why* it made a choice:
   *"I gave the hook a 5 s wide establishing shot and cut the
   escalation to 1.5 s shots — slow-in, fast-middle is standard trailer
   rhythm. Change `--pace` to override."* Coaching rides on output the
   user already reads.

2. **A dedicated explainer:** `/autonovel:teaser-coach [--topic
   hook|pacing|cast|ending|shots|consistency|cost]` — a heavy-tier
   Socratic guide that answers the beginner questions in §20 *in the
   context of this book*, citing the user's own beats. Mirrors
   `/autonovel:explain`-style help.

3. **A "director's questions" pass.** Before generating, the beat-sheet
   command asks (and proposes answers to) the questions a director must
   settle: *What's the one image someone remembers? What question does
   this make the viewer ask? What are we deliberately NOT showing? Whose
   face carries it?* The user can accept the proposals or steer.

Coaching content lives in a reference doc consumed by the prompts —
**`docs/teaser-craft.md`** (a CRAFT.md analogue for film), so the
guidance is prompt material, versioned, and improvable, not hardcoded in
command bodies.

## 20. Creative defaults & first-timer answers

Concrete, opinionated defaults — the literal answers to "how long?",
"how many?", "how to hook?", "hint or surprise?". The tool ships these
as defaults *with the reasoning attached*, and every one is overridable.

### 20.1 Shot & scene length

| Question | Default | Why |
|---|---|---|
| How long is one **shot**? | **2–4 s** average | AI clips are 4–10 s native; trailers cut fast. Generate short, pick best (§5). |
| How long is the **hook**? | one **4–6 s** shot | The opening image needs room to land before you start cutting. |
| How fast does the **escalation** cut? | down to **1–2 s** | Accelerating cuts = rising tension. |
| How long is the **final image**? | **3–5 s** hold | Let the last beat breathe; leave them with it. |
| How many shots in a **30 s** teaser? | **~8–12** | Dev/debug size. (The X-Prize target is 3 min ≈ **35–60 shots**.) |

### 20.2 How many characters?

- **Teaser cast: 1 hero face, at most 2–3 named faces total.** More
  faces = more identity drift (§10) and less emotional clarity. A teaser
  sells *one* person's stakes. Crowds/silhouettes/backs-of-heads are
  free — they don't need consistency locking. **Default: foreground one
  protagonist; everyone else is atmosphere.**

### 20.3 How to hook (the first 5 seconds)

Pick **one** (the coach proposes based on the book):
- **Strongest single image** — the most striking visual in the world.
- **A dramatic question** — show a situation that demands "…what
  happens next?"
- **A provocative line** (text card or one spoken line) — *"They told us
  the war was over."*
- **Disorientation→orientation** — a strange close-up, then pull out to
  reveal the world.

Rule: **intrigue, don't explain.** No exposition in the first 5 s.

### 20.4 The ending: hint or surprise? (the question the user asked)

A teaser and a *full trailer* answer this differently, and the X-Prize
context tips the scale — so the tool makes it an explicit choice:

- **Default (teaser): tease the QUESTION, withhold the ANSWER.** Show
  the stakes and the world; never show the resolution. End on the
  unanswered question or a "button" (a final hook *after* the title)
  that deepens the mystery. This is the safe, standard move.
- **The X-Prize twist:** the brief asks you to *"show a future worth
  building."* For an optimistic-sci-fi entry, the **vision** (the hopeful
  future) is often the *point* — so you may **reveal the vision but
  withhold the cost/journey**: hint that humanity *earns* it through
  struggle, show the destination, hide the road. "Reveal the what,
  withhold the how."
- **Never** spoil a twist ending or the final emotional beat — that's
  what the film is for.

The `--ending hint|reveal-vision|withhold` flag (default `withhold`)
encodes this, and `/autonovel:teaser-coach --topic ending` explains the
tradeoff against *this* story.

### 20.5 Other sensible defaults

| Knob | Default | Note |
|---|---|---|
| Aspect ratio | **16:9** | Festival/competition standard; `9:16` for social. |
| Audio | temp **music bed + 1–2 dialogue stings + SFX** | Music carries a teaser; dialogue is sparing (§11). |
| Text cards | **2–4 short cards** | Carry narrative cheaply; dodge AI lipsync (§11). |
| Title card | at **~⅔** point | Brand beat before the button. |
| Palette | **3–5 colours**, fixed | Seamless edit + consistency (§9). |

## 21. Worked target projects

Two real sources drive development; they exercise different halves of
the system.

### 21.1 The Fugger book — pipeline shakedown (debug source)

Near-complete historical novel already in the autonovel pipeline. Role:
**prove adaptation end-to-end** on real, rich source material with a
full foundation (world, cast, voice.md Part 4, eval_logs). It is *not*
the competition entry (wrong genre — historical, not optimistic future),
but it's the ideal debug corpus: run `/autonovel:teaser --book fugger
--from script` on **free tools** (§22) to shake out the beat-sheet,
externalization, consistency anchors, and assembly before spending money
or time on the real entry.

### 21.2 The Future Vision X-Prize entry — the goal

> **Source:** futurevisionxprize.com (fetched 2026-06-05). **Re-verify
> rules before submitting.**

- **What:** XPRIZE Foundation global **sci-fi film competition** — show
  *"a future worth building."* Optimistic, technology-forward futures
  where *"humanity earns the future through struggle, ingenuity, and
  courage."* Presenting donor Jed McCaleb; sponsor Salesforce; partners
  incl. Google, Roddenberry Foundation, Republic Film.
- **Deliverables (this is decisive for the PRD):**
  1. **A 3-minute-maximum trailer** — *"any creation method
     acceptable… AI, traditional filming, animation — it's all fair
     game."* → maps directly to teaser mode at the **top** of the
     1–3 min range (≈35–60 shots).
  2. **An up-to-12-page treatment** + **a 2-page written brief with
     synopsis.** → **a prose deliverable autonovel is *already* built
     for.** This is a major fit and a reason to add a **competition
     mode** that emits the treatment + brief from the same foundation.
- **Judging:** technology solving real problems · optimistic (not
  dystopian) worldbuilding · compelling narrative with genuine **stakes
  + character arcs** · **visual ambition**. → the teaser must show
  *ambition* (scale, vfx-forward shots) *and* a real character arc, not
  just pretty plates.
- **AI policy:** AI-generated content explicitly **welcomed**.
- **Timeline:** creation Feb–Aug 2026 · **submission deadline
  2026-08-15** · finalists Aug 2026 · finals in LA 2026-09-25.
- **Prizes:** Grand $2.6M ($100K screenplay dev + $2.5M production
  equity); 4 runners-up $100K; top-10 $10K; pool $3.5M+.

**Implications for the PRD:**
1. **Add a competition/treatment deliverable** to scope: a
   `/autonovel:treatment --book <name> [--pages 12] [--brief]` that
   emits the ≤12-page treatment + 2-page synopsis brief from
   world/outline/characters. Low-risk (pure prose, autonovel's
   wheelhouse) and directly required by the entry. *Promote from
   "open question" to a v1 goal for competition mode.*
2. **Target length = 3:00** for the X-Prize teaser profile; ship a
   `--length 180` preset tuned for it.
3. **Optimistic-sci-fi framing** — the from-scratch foundation for the
   entry needs the "earned hopeful future" thesis baked into world +
   outline; the teaser's §20.4 ending defaults to `reveal-vision`.
4. **Deadline is real (~10 weeks from 2026-06-05).** Sequence work so a
   *rough, free* full 3-min cut exists early, then upgrade shots to paid
   generation where visual ambition needs it.
5. **Rights hygiene** — no trademarked/real-person likenesses in
   prompts (§18.4); confirm AI-content + music licensing terms before
   submission.

## 22. Fully-free development tier

> **⚠️ Superseded for the render backend (2026-06-06).** The
> Pollinations-first plan in this section broke externally: Pollinations
> now 402s anonymous image gen and has no free video. The shipped free
> tier is **Phase 4** — an offline `stub` backend to validate the
> pipeline for $0, then `grok` (free dialogue+music, no card) as the
> default real video backend, with `kie`/`veo`/`magichour`/`fal`/manual
> `flow` alternatives. Canonical map: `docs/teaser-render-providers.md`.
> The principles below (drive online free tools; watermarks/low-res OK
> for dev) still hold.

> Goal (user, 2026-06-05): do **free passes to debug the system and
> develop the script** before paying for premium generation. User can
> run a **~35B model locally** and has confirmed **watermarks + lower
> resolution are acceptable** for these dev passes. Research pass
> 2026-06-05; **all free-tier numbers are fast-moving — verify before
> relying.** Sources in §22.6.

### 22.1 Verdict

**Yes — a complete free 30 s / ~10-shot teaser with video + audio +
speech is realistic today**, at "rough-cut / animatic" quality (visible
artifacts, occasional identity drift, watermarks on some hosted tiers).
That is *exactly right* for debugging the pipeline and developing the
script. Plan to spend money only on the **final** X-Prize shots that
need visual ambition.

### 22.2 Principle: drive online free tools, don't make the user run local ones

> Author direction 2026-06-05: *"if we can only use online free tools
> that you drive it will go much smoother."* Correct, and it's the
> design default for the free tier.

A local Wan/LTX/ComfyUI rig gives unlimited, watermark-free, private
generation — but it makes the **human** the runtime: install CUDA, load
checkpoints, click through ComfyUI graphs, move files. That breaks
autonovel's core promise (the user should never have to leave the
runtime / touch shell plumbing — see `feedback_no_shell_in_user_workflow`).

So the free tier **leads with online tools the autonovel runtime can
*drive itself*** — no-auth or free-API endpoints the agent calls,
polls, and downloads from, exactly like the existing image path. Local
GPU drops to an **optional fallback** for users who want unlimited
no-watermark runs and don't mind running it (§22.4 Tier B).

The enabling find: **Pollinations** — already wired into autonovel for
images — is **no-auth, no-signup, free, URL-based**, and now exposes
**image + video (Seedance, Veo-alpha, Wan-Fast *with keyframe support*)
+ audio** through one endpoint. Keyframes = consistency anchors (§10);
audio = narration/SFX. That single backend can drive an entire free
teaser pass with zero keys, zero local install, and code autonovel
already has. This is what makes §23's thin render adapter shippable with
a **free default backend** rather than a paid one.

### 22.3 The local 35B is the brain, not the renderer

The single highest-value free asset. A ~32–35B local model
(**Qwen3-32B** is the current sweet spot for creative writing + reliable
structured output on ~24 GB VRAM; Gemma-3-27B, Mistral-Small-24B,
Yi-34B are alternates) runs the **entire LLM side for free**: script
writing, beat-sheet, scene→shot decomposition, the §8 prompt JSON, the
treatment + brief. Use **temp 0.8–1.1 for prose**, **0.2–0.4 for the
JSON shot schema**. Implication for autonovel: the teaser commands
should run cleanly on a **local-model runtime** (Codex/Gemini adapters
or an Ollama-style backend), not assume a paid frontier model — the
creative brain is free; only pixels cost money.

### 22.4 Free tool stack — Tier A (agent-driven online) first, Tier B (local) fallback

**Tier A — online, the runtime drives it (default).** No local install;
the agent submits → polls → downloads. Watermark/low-res fine for dev.

| Layer | Agent-drivable free endpoint | Drive method |
|---|---|---|
| **Reference images** (consistency anchors) | **Pollinations** (FLUX / GPT-Image / Seedream) — *already integrated* | no-auth URL `GET` |
| **Video** | **Pollinations video** (Seedance, Veo-alpha, **Wan-Fast + keyframes**) | no-auth URL |
| **Video (more credits)** | **ZSky** (1080p+audio, no card), **Magic Hour** (400 + 100/day), **fal.ai** ($10 ≈ 50–100 gens), **Replicate** (small free credits), **Leonardo** ($5) | free-key REST, async poll |
| **Speech / narration / dialogue** | **Pollinations audio**; **Edge-TTS** (free MS voices, no key) | no-auth / free lib |
| **Music** | **Pollinations audio**; CC libraries (YouTube Audio Library, Pixabay, FMA, Incompetech) | URL / static fetch |
| **SFX** | **freesound.org**, **Pixabay** | API (free key) |
| **Assembly** | **ffmpeg** (concat + crossfade + audio mux + burned text cards) | local binary the tool already shells (doctor checks it) |

> **Pollinations alone** (no-auth image + video + audio) can drive an
> entire free pass with zero keys and zero install — the smoothest
> possible debug loop, and it reuses autonovel's existing integration.
> Add ZSky/Magic Hour/fal free keys when you need more daily volume or
> higher quality on specific shots.

**Tier B — local, the user runs it (optional, unlimited + no watermark).**
Only for users who *want* to and have the GPU; never required.

| Layer | Local option | Note |
|---|---|---|
| **Script/shot brain** | **Local ~35B (Qwen3-32B)** — see §22.3 | The one local piece that's *high value even for non-GPU users*; runs the free LLM side. |
| **Video** | **Wan 2.1/2.2** (24 GB+), **LTX-Video** (~12 GB, fast), **HunyuanVideo 1.5** (~14 GB) via **ComfyUI** | Unlimited, watermark-free if you run it. |
| **Speech** | **Kokoro-82M** (CPU-OK), **Chatterbox** (cloning ~6 GB) | Mind non-commercial licenses (XTTS/F5) for the final cut. |
| **Music / lip-sync** | **MusicGen**; **SadTalker / LatentSync** | Prefer VO + text cards over on-screen talking (§11). |

### 22.5 Recommended free end-to-end pass (30 s, ~10 shots), fully agent-driven

1. **LLM brain** (local 35B *or* the runtime's own model) writes/loads
   script → beat-sheet → §8 shot JSON + treatment/brief. (free)
2. The tool drives **Pollinations** to make one **canonical reference
   image** per character + key location. (free, no key)
3. The tool drives **Pollinations video** (keyframes off the refs) for
   ~10 short clips, 2–3 takes each, auto-download; spill to
   **ZSky/Magic Hour/fal** free credits when daily volume runs out.
   (free; watermark/low-res OK)
4. The tool drives **Pollinations audio / Edge-TTS** for narration +
   sparse dialogue; CC music bed; freesound SFX. (free)
5. **ffmpeg** (already shelled by the tool) concat → music bed → 2–4
   text cards → export. (free)

Every step is something the autonovel runtime can invoke and poll
itself — **no leaving the chat, no ComfyUI, no manual file shuffling.**
Realistic quality: a watchable **animatic-grade** 30 s with sound —
perfect for proving the system and iterating the script. Artifacts and
identity drift are the signal to upgrade *those* shots to paid
Veo/Sora/Runway for the final entry. This pass is the §23 thin render
adapter pointed at its **free default backend (Pollinations)**.

### 22.6 Sources (free-tier research, 2026-06-05; fast-moving)

- **Agent-drivable free APIs** — Pollinations GitHub + docs
  (no-auth image/**video** (Seedance, Veo-alpha, Wan-Fast+keyframes)/
  **audio**); ZSky AI (free REST, 1080p+audio, no card); Magic Hour
  (400 + 100/day); fal.ai ($10 ≈ 50–100 gens); Replicate (small free
  credits); Leonardo ($5) — ZSky/VideoAI/Atlas Cloud/Eden AI roundups.
- Open video models / VRAM — WaveSpeed, Pixazo, Hyperstack, Digen
  roundups (Wan 2.2, LTX-Video, HunyuanVideo 1.5).
- Free hosted tiers — Atlas Cloud, Seedance, Veo3AI, Kensa roundups
  (Seedance ~100/day no-watermark, Kling ~66/day, Hailuo, Luma, Pika).
- Google Veo free access — Veo3AI / Google Developers (Flow free
  credits, AI Studio limits).
- Open TTS — CodeSOTA, PromptQuorum, Nerdynav (Kokoro, Chatterbox,
  XTTS-v2, F5-TTS, licenses).
- Local creative LLMs — PromptQuorum, SiliconFlow (Qwen3-32B best 32B).
- Music + lip-sync — Suno/Udio free tiers; SadTalker / LatentSync /
  lipsync.com open-source roundup.

> ⚠️ **Licensing caveat for the competition cut:** several free tools are
> *non-commercial* (XTTS, F5-TTS, Suno-free, Udio-free) or watermark
> output. Fine for dev passes; for the X-Prize submission, swap to
> commercially-licensed or properly-attributed assets and verify each
> tool's terms.

## 23. Open question — a thin "render this shot" tool vs a full production system

> Raised by the author 2026-06-05: *"can we add a tool that calls the
> video APIs? Not sure we can make that work without doing a full video
> production system…"* — exactly the right worry. This section draws the
> line so the feature can exist without swallowing the project.

**The fear is justified — but only if we let it scope-creep.** The thing
that turns "call an API" into "a full video production system" is *not*
the API call. It's everything *around* it: per-shot state tracking,
stale-vs-current detection, re-render-only-what-changed graphs,
cross-shot coherence fine-tuning, automated edit/assembly, and a preview
loop. Those are the ultra-long-term pipeline (§13 Phase 4+, and the
FUTURE-TODOS video-pipeline entry). They are big.

**The API call itself is small and well-bounded.** Every provider
(§§7–8) is the same async shape: `submit(prompt, params) → poll(job) →
download(clip)`. That's a ~stateless helper, and autonovel already has
the exact pattern for the image side: `resolve-image-provider` +
`art-curate` apply a CLI→project.yaml→default precedence and call an
image provider. A **thin render adapter is the video twin of that**, and
nothing more.

### 23.1 Proposed scope of the *thin* tool (deliberately minimal)

`/autonovel:teaser-render --book <name> [--shots <range>] [--provider
veo|runway|kling|luma|fal|replicate] [--takes N] [--dry-run]`, backed by
`autonovel mechanical resolve-video-provider` (precedence twin of the
image resolver). It does **exactly four things**:

1. Read `teaser.json` / `shot_NN.md`, render each shot to the chosen
   provider's request shape (reuse §8 per-provider render rules).
2. Submit, poll with backoff, download `--takes` clips per shot to
   `books/<name>/teaser/clips/<shot>_takeN.mp4`.
3. Pass through consistency anchors (reference image / first frame).
4. Print a cost estimate + a manifest; honour `--dry-run` (estimate +
   the exact requests, submit nothing) and the **fully-free §22 path**
   — default `--provider pollinations` (no-auth, image+video+audio, the
   smoothest agent-driven free backend), spilling to ZSky/Magic Hour/fal
   free credits; local Wan/LTX is the optional Tier-B fallback.

### 23.2 The bright lines that keep it thin (explicit non-goals)

The render tool **stops at "clips on disk."** It does **NOT**:
- track which clips are stale vs current (no `video-state.json`),
- decide *what* to re-render (the human picks `--shots`),
- assemble/edit (that's v1.5 `teaser-assemble`, already separate),
- do coherence fine-tuning / LoRA training,
- run a preview/iteration UI.

So the tool is **stateless per invocation**: prompts in → clips out. The
human (or the separate assembly step) is the state machine. That's the
whole trick — it's a *renderer*, not a *pipeline*. If a feature request
would add memory of prior runs or automatic re-render decisions, it
belongs in Phase 4+, not here.

### 23.3 Recommendation

**Defer to Phase 3.5, build it thin, and gate it behind an explicit
flag.** v1 still ships prompts-only (the durable value); the thin
renderer is a convenience that reuses the image-provider precedence
machinery and the §8 render rules. Because it's stateless and
provider-pluggable (incl. the free §22 backends), it does *not* commit
us to the full production system — and if it ever starts to, that's the
signal to stop and promote the work to the ultra-long-term entry.

**Update to §2 non-goals:** the "no API rendering in v1" non-goal stands
for v1, but is **softened** — a *thin, stateless, opt-in* render adapter
is an accepted **Phase 3.5** target, distinct from the excluded full
production system.

## 24. Testing the tool, its results, and the prompts (self-critique)

> Author direction 2026-06-05: add a section on *"testing the tool and
> the results and the prompts / criticising them."*

There are **two different kinds of testing** and the PRD needs both:
- **Code correctness** — does the software work? (repo Tiers 1–3, §16.)
- **Creative-output quality** — are the *prompts*, the *clips*, and the
  *cut* any good? That's this section. It follows autonovel's existing
  judge philosophy (`evaluate`, `adversarial-edit`, `reader-panel`,
  `review`): **the machine criticises its own output before the human
  spends time or money on it**, and quality is judged by an LLM/vision
  model, never by brittle regex (`feedback_avoid_brittle_python`).

### 24.1 Three things to critique — cheapest-to-fix first

A bad shot is cheapest to catch as *text*, more expensive as a *clip*,
most expensive in the *cut*. Critique gates run in that order:

| Layer | What | Cost to fix | Judge |
|---|---|---|---|
| **Prompts** | the §8 shot prompts (text) | ~free (no generation) | LLM critic |
| **Clips / frames** | the generated takes | a generation each | vision-LLM critic |
| **Assembled teaser** | the cut + audio | a full pass | "viewer panel" |

### 24.2 Prompt critique — the highest-ROI gate (free, pre-generation)

Before any pixels are generated, an LLM critic scores **every shot
prompt** and rewrites the weak ones. This is `adversarial-edit` for
shot prompts and it runs free (local 35B or the runtime model). It
checks each prompt against the rules already in this PRD:

- **AI-legibility linter (§18.4):** one subject + one action + one move?
  present tense? only what's in frame? no un-filmable abstraction? no
  on-screen text? subject named identically?
- **Schema completeness (§8):** all fields present; duration within the
  provider's native cap; negative-prompt + dialogue in separate fields.
- **Consistency (§10):** appearance phrasing identical to the
  character's other shots; palette/lighting on the global anchors;
  reference image assigned.
- **On-brief (§21):** does the shot serve the beat and the
  competition's judging criteria (stakes, character, *visual ambition*,
  optimism)?
- **Trailer craft (§11/§20):** right length/role for its slot; doesn't
  spoil the ending.

Output: per-shot `PASS / REWRITE / FLAG`, a one-line reason, and a
rewritten prompt for REWRITE. Surfaced as `/autonovel:teaser-critique
--book <name> [--layer prompts]`. **Catches most failures for $0** —
the single most valuable test in the system.

### 24.3 Clip / frame critique — a vision-LLM judge closes the loop

After generation, a **vision-capable model** looks at the actual
frames/clip (or extracted keyframes) and scores each take against *its
own prompt's intent*:

- Did it render the **intended subject, action, framing, camera move**?
- **Identity match** vs the character's reference image (drift?).
- **Artifacts:** extra/melting limbs, morphing, flicker, garbled text,
  physics breaks (§11 failure modes).
- **On-palette / on-style** vs the global anchors.

Output per take: a score + `KEEP / REGENERATE / UPGRADE-TO-PAID`
verdict, and **auto-selection of the best take** for the cut (replaces
manual review of N takes). The UPGRADE verdict is how the tool tells you
*which specific shots* are worth paid Veo/Sora generation for the final
entry — the rest stay on the free backend.

### 24.4 Assembled-teaser critique — a "viewer panel"

The `reader-panel` analogue for video. N personas (e.g. *festival
juror*, *sci-fi fan*, *first-time viewer*, *the X-Prize rubric itself*)
watch the assembled cut (storyboard+audio animatic is enough — no need
to finish render) and react:

- Does the **hook** grab in 5 s? Where does attention drop?
- Any **confusion** (who/where/when unclear)?
- Does it make you **want the film**? Does it **withhold** correctly?
- Against the **X-Prize criteria**: optimism, genuine stakes + arc,
  visual ambition — present and legible?

Output: ranked, specific fixes ("hook is a static wide — open on the
push-in from shot 4 instead"). Surfaced via `/autonovel:teaser-critique
--layer cut` or folded into the existing `reader-panel`.

### 24.5 The iteration loop (budget-capped)

`critique → regenerate the worst N → re-critique`, bounded by a round
cap and a spend cap. Free passes (Pollinations) run the loop at $0 to
develop the script and shot list; only after the cut works do you spend
on the shots the clip-critic flagged `UPGRADE-TO-PAID`. The loop logs
every verdict so you can see convergence.

### 24.6 Testing the generator itself (dev / regression methodology)

Building the *tool* (not just using it) needs its own tests:

- **Golden shot-set fixtures** — a few hand-blessed beats → expected
  schema shape; assert the generator still produces valid, complete,
  lint-passing prompts (Tier-1, mechanical).
- **Prompt-generation regression** — same beat in → stable, schema-valid
  out across releases (catches LLM-prompt drift, the same risk the Bells
  Tier-4 fixture guards for prose).
- **Provider A/B harness** — render the same critiqued prompt across
  providers (incl. free Pollinations) and log critic scores side by side
  — data for the `--provider` defaults and for "is the paid upgrade
  worth it?".
- **End-to-end on the Fugger book (§21.1)** — the full free pass is the
  integration test; a real Pollinations generate + critique is the
  Tier-3 smoke.
- **Results log** — persist `{prompt, provider, take, critic_score,
  verdict, cost}` under `books/<name>/teaser/critique_log.jsonl` so
  prompt-gen quality is *measured over time*, not vibes. (Mirrors
  `command-log.jsonl` / eval logs.)

### 24.7 Tier mapping & the no-brittle-python line

- **Tier 1 (deterministic):** critique-report JSON shape; the linter's
  *mechanical* checks (field presence, duration ≤ provider cap, separate
  negative/dialogue fields, identical-appearance-string check across a
  character's shots); results-log shape.
- **Tier 2 (contracts):** `reads:`/`writes:` for the new
  `teaser-critique` command.
- **Tier 3 (smoke):** one real free generate + prompt-critique +
  frame-critique end-to-end on a fixture.
- **Never regex-score quality.** "Is this prompt good / on-brief?" and
  "does this clip match intent?" are LLM/vision-judge calls. The
  mechanical layer only checks *structure*; the judge checks *quality*.
  Extends §12's rubric and §16's tiers.
