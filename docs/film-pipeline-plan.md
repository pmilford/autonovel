# Film pipeline plan — from a finished novel to a screenplay and a film

> **Status:** draft for the author's review, 2026-10-28. Not committed.
> Research only; no code, command or book file was changed to write it.
> Prices and licences were checked on the web on 2026-10-28 and move
> monthly; each one carries its source in §8. Parent entries:
> FUTURE-TODOS "Movie script + theater play output formats" and
> "ULTRA-LONG-TERM: Script → full video pipeline"; the teaser PRD is
> [`prd-movie-teaser-mode.md`](prd-movie-teaser-mode.md).

## 1. Where we are

### What a person can do today

autonovel has a working **teaser** path and nothing beyond it. From a
finished book a person can run:

| Step | Command | Writes (under `books/<book>/`) |
|---|---|---|
| Treatment | `/autonovel:treatment` | `treatment.md` (≤12 pages, present tense, reveals the ending), `brief.md` (2 pages) |
| Plan the teaser | `/autonovel:teaser` (chains `teaser-brief` → `teaser-beats` → `shot-prompts` → `teaser-critique` ⟳ `teaser-revise`) | `teaser/brief.md`, `teaser/beats.md`, `teaser/teaser.json`, `teaser/shots/shot_NN.md`, `teaser/critique.md`, `teaser/quality.json` |
| References | `/autonovel:teaser-refs` | `teaser/refs.yaml` (per character and location: source, locked appearance, voice descriptor, age ladder, approval status), `teaser/refs/*.png` |
| Render | `/autonovel:teaser-render` | `teaser/clips/shot_<id>.{png,mp4}`, `clips/takes/` (never overwritten), `clips/render-report.{md,json}` (KEEP / REGENERATE / UPGRADE-TO-PAID) |
| Voice-over, music | `autonovel mechanical teaser-vo`, `teaser-music` | `teaser/vo/*.mp3`, `teaser/music/*` |
| Assemble | `/autonovel:teaser-assemble` | `teaser/cut_list.json`, an ffmpeg `.mp4`, `teaser/assembly-report.md` |

Two gates stop a real render: the story gate (the `spine` has a dramatic
question, logline, stakes, arc and genre) and the quality gate (an LLM
scores eight dimensions plus a viewer-blind legibility read; overall ≥ 7,
none below 5). Planning is free; only rendering spends.

### The shot schema

`src/autonovel/teaser/shots.py :: Shot` holds, per shot: `id`, `role`
(`hook | escalation | title | button`), `duration_s`, `aspect_ratio`,
`shot_size`, `camera_angle`, `camera_movement`, `lens`, `style`, `mood`,
`subject {name, appearance}`, `action`, `setting`, `lighting`, `palette[]`,
`audio {ambience, sfx, dialogue[]}`, `negative_prompt`, `reference_image`,
`last_frame`, `seed`, `text_card`, `story_year`, `stakes_level`,
`character_beat`, `identify`, `voiceover`, `beat_note`. The camera fields
are **free text** (a real shot reads `"lens": "50mm, shallow depth of
field"`, `"camera_movement": "slow push-in"`). There is no numeric focal
length, aperture, frame rate, shutter, camera height or camera path; no
scene ID, blocking, screen direction or eyeline; and no continuity state
(costume, props, injuries, time of day). Validation is structural only.

### Render backends (`src/autonovel/teaser/providers.py`, `backends.py`)

| Backend | Makes | Cost model | Key | Run for real? |
|---|---|---|---|---|
| `stub` | placeholder stills (Pillow) | free, offline | none | yes, often |
| `gemini` (Nano Banana) | reference-conditioned stills | paid per image | `GEMINI_API_KEY` | **yes** — faces held across shots |
| `veo` (Veo 3.1 Fast, Gemini API) | video with native audio | paid per second | `GEMINI_API_KEY` | **yes** — see below; **now broken**: Google shut the model id it calls (`veo-3.1-fast-generate-preview`) on 2026-10-22 |
| `grok` (documented default, called "free") | video with audio | **paid**: xAI lists $0.02–0.08/s and no free API tier | `XAI_API_KEY` | **failed live** (403 on the author's key) |
| `kie`, `magichour`, `fal` | video (resellers) | free credits, then paid | each its own | written and unit-tested, never run live |
| `pollinations` | stills only (free video ended) | free token | token | not since the token change |
| `flow` | manual (Google Flow GUI) | subscription | none | manual only |
| `sora`, `runway`, `kling`, `luma` | — | — | — | capability rows only, no backend code |
| VO: `edge`, `elevenlabs`, `stub` | narration | free / paid / free | — | `edge` **yes** (a 54.9 s narration) |
| Music: `musicgen`, `elevenlabs`, `stub` | a bed | free / paid / free | — | not run; `musicgen` calls the retired `api-inference.huggingface.co` host |

### What has been tested for real

- **Real, on the Fugger book (June 2026):** treatment and brief; the whole
  planning chain, several times (Phases 6, 11, 12 and 13 were each driven
  by a real run that came out flat or illegible); Gemini reference
  keyframes; edge-tts narration; ffmpeg assembly. **Veo 3.1 Fast rendered
  85 distinct clips, about 522 seconds of video, across three runs** (the
  series' `teaser/reset-archive/`). The cut that stands today
  (`what_the_ledger_shows_teaser_music.mp4`, 58 s) is **nine stills** with
  the edge narration and a hand-written ffmpeg sine-wave drone as the
  music; none of those Veo clips is in it.
- **Written but never run live:** kie, magichour, fal, pollinations since
  its token change, both music generators, and every lip-sync, Foley or
  local-model path (there are none).
- **Missing safety rails:** `--dry-run` reports whether a key is present
  but prints **no dollar estimate**; there is **no spend ledger**, so what
  the 522 seconds cost is not recorded anywhere; the vision critique is
  manual for video (`teaser-render` step 7) and the cut critique judges
  the cut list, not the pictures (it passed a bad cut as "KEEP").
- **Out of date in the repo** (to fix separately): the `veo` model id and
  the "free" `grok` default above; `edge-tts` as the free narration voice
  (see §7); the retired Hugging Face host in `music.py`; `art-curate`
  still calls Pollinations "no-API-key".
- **Audio elsewhere:** the audiobook path is ElevenLabs only in the repo.
  Kokoro is proven outside it (FUTURE-TODOS), and this week's bake-off
  found VoxCPM2 the most human of the free engines: about 1.1× real time
  on the 5060 Ti (0.7× on the 3060), Chatterbox about 2×, Chatterbox
  Turbo about 4×, Kokoro about 60×. VoxCPM2 sometimes says words that
  are not in the script (`"Wool."` came out as "thank you"), so the
  bake-off added a Whisper check that re-takes any line whose transcript
  differs; a 43-minute chapter needed 7 re-takes of 240 lines.

### The gaps between a teaser and a film

1. **No screenplay.** No adaptation command, no Fountain, Final Draft or
   PDF output, no sluglines, no screen rubric; the `[scripts]` extra in
   `pyproject.toml` is empty. The treatment is the nearest thing.
2. **The unit is a trailer shot, not a scene.** Roles are trailer roles;
   shots have no scene, no coverage and no relation to each other.
3. **Camera specs are prose,** with no path a camera-control model could
   follow, and no blocking.
4. **Continuity stops at faces and places.** References, approval and age
   ladders work; costume by scene, props, wounds, weather and time of day
   are not tracked or checked, and there is no per-character model.
5. **Performance is left to the video model.** Dialogue is either spoken
   by Veo inside the clip or laid over as narration; there is no per-line
   recording, voice casting for film, or lip-sync stage.
6. **Sound is a bed.** No Foley or effects, no working score generator,
   no stems, no loudness targets.
7. **Edit is ffmpeg concat.** No timeline (OpenTimelineIO, EDL, FCPXML)
   to finish in DaVinci Resolve.
8. **No state.** The teaser is stateless by design; a film needs to know
   which shots a script edit made stale.
9. **No cost control and no provenance.** No estimate, cap or ledger; no
   record of which model, licence and seed made each asset; no consent
   records for voices or likenesses.
10. **No local backends.** Every real backend is a cloud API; the two
    GPUs on this machine are unused for pictures.
11. **Scale.** A teaser is 9–35 shots. A 110-minute feature at a 4-second
    average shot is about 1,650 shots, and with three takes each about
    5,000 clips.

## 2. What a film needs that a book doesn't

| Need | In the book | In the film |
|---|---|---|
| Adaptation | 120,000 words, 20+ chapters, interiority | 100–120 pages, ~1 page a minute; most chapters merge or go; thought becomes behaviour or voice-over; minor people merge (count people, not names) |
| Screenplay | prose | Fountain source, sluglines (`INT. COUNTING HOUSE — NIGHT`), action, dialogue, parentheticals, transitions; PDF in Courier 12 pt; `.fdx` for professionals |
| Shot design | the narrator chooses what to show | every scene is covered by shots: size, angle, lens, movement, blocking, screen direction, duration |
| Continuity | canon.md keeps facts straight | the same face, costume, prop, wound, weather and light across hundreds of shots made separately |
| Performance | the reader hears the voices | each line is acted: a cast voice, a reading, timing, lips that match |
| Sound | none | dialogue, Foley, ambience, score, mixed to a loudness target |
| Edit | chapter order | a timeline; rhythm; the cut decides what the scene means |
| Rights | the author's text | every model, voice, face, font and music cue needs a licence that allows the use |

## 3. The pipeline

Everything lives under `books/<book>/film/`, keyed by **scene ID** and
**shot ID**. Each stage is a markdown command with a `reads:`/`writes:`
contract, does its deterministic work through `autonovel mechanical …`,
is judged by an LLM (or a vision model) with a critique → revise loop,
and stops at a human checkpoint. Every output carries a **fingerprint of
its inputs** (the summary-fingerprint pattern), so
`autonovel mechanical film-status` can list exactly which shots and clips
a script edit made stale; nothing derived may be stale at a release.

| # | Stage and command | Reads | Writes | Mechanical | Judge | Human checkpoint |
|---|---|---|---|---|---|---|
| F0 | **Adaptation plan** `/autonovel:adapt` | `design.md`, `outline.md`, `cast.md`, summaries, said-once ledger, eval logs, `treatment.md` | `film/adaptation.md` (format, runtime, the spine, what merges, what goes, how interiority is carried), `film/scene_plan.json` (scene, source chapters, purpose, page budget) | page budget sums to the target ±10%; every principal's arc has scenes | screen structure review (DESIGN.md tests applied to the film), plus a "what did we lose?" critic | **author approves the cuts**: merged people, dropped subplots, the ending |
| F1 | **Screenplay** `/autonovel:screenplay`, `/autonovel:screen-revise` | F0, chapters, `voice.md`, `cast.md` | `film/screenplay/seq_NN.fountain` → `film/screenplay.fountain`, `film/scenes.json` (slugline parts, characters, line IDs, length in eighths of a page), `film/export/<title>.pdf`, `.fdx` | Fountain parse, page count, slugline and character-name checks against the cast, PDF/FDX export | screen evaluate (visual storytelling, dialogue as action, scene as a unit of change, economy); cold first reader; said-once; a **table read** with local TTS | **author reads the PDF and the diff**; `screenplay-check` must pass |
| F2 | **Production bible** `/autonovel:film-bible` (grows `teaser-refs`) | F1, `cast.md`, `world.md`, art style | `film/bible/look.yaml` (aspect, 24 fps, lens set, palette, grade); `bible/characters/<slug>.yaml` (canonical appearance text, wardrobe by scene range, age ladder, voice, source, consent); `bible/locations/`, `bible/props.yaml`; reference sheets (front, three-quarter, profile, full body; location from two sides) | wardrobe and age resolved per scene; every speaking character has a voice and a sheet | vision judge: the sheet is one person; period check | **approve each sheet** (the existing approval gate) |
| F3 | **Shot list** `/autonovel:shot-list --scene N` | F1 scene, F2 | `film/shots/scene_NNN.json` (schema below) | schema; every line covered; durations ≈ the scene's page time; 180° rule from screen direction; continuity diff between consecutive shots | a director/DP critic: coverage, motivation for each move, variety | read with F4 |
| F4 | **Storyboard and animatic** `/autonovel:storyboard`, `/autonovel:table-read`, `/autonovel:animatic` | F3, F2 sheets | `film/storyboard/<shot>.png` (reference-conditioned keyframe), `film/audio/table_read/<line>.wav`, `film/animatic/scene_NNN.mp4` (stills timed to the read, simple pans) | timing from real line lengths; ffmpeg build | vision judge per keyframe (spec, identity); viewer panel on the animatic | **author watches the animatic** — the main creative sign-off before anything costs money |
| F5 | **Voices and dialogue** `/autonovel:film-voices`, `/autonovel:dialogue` | F1 lines and parentheticals, F2 voices | `film/audio/dialogue/<line>/take_NN.wav` + `manifest.json` | Whisper transcript must match the line; duration fits the shot | listening is the author's; the LLM checks direction against the parenthetical | **approve the cast voices**; consent record for any cloned voice |
| F6 | **Shot render** `/autonovel:film-render --scene N --backend … [--dry-run] [--budget $]` | F3, F4 keyframe, F2 refs | `film/clips/<shot>/take_NN.mp4` + `render.json` (backend, model version, seed, licence, cost, input fingerprints) | **cost table before any spend**, hard budget cap, `film/spend.jsonl` ledger, versioned takes | vision judge on sampled frames: spec, identity against the sheet, artefacts → KEEP / REGENERATE / UPGRADE | **approve each scene's selects** |
| F7 | **Lip-sync** `/autonovel:lipsync` (only where F6 rendered silent) | F6 selects, F5 takes | `film/clips/<shot>/take_NN_sync.mp4` | a sync-confidence score as a candidate filter | vision judge on mouth close-ups | spot-check |
| F8 | **Sound** `/autonovel:film-sound` | F6/F7 selects, F5, `look.yaml` | `film/sound/scene_NNN/{dialogue,fx,ambience,music}.wav` stems + mix | loudness (EBU R128 via ffmpeg `loudnorm`), stem alignment | listening notes from the author; LLM checks the cue sheet against the scene's tone | approve score cues |
| F9 | **Edit** `/autonovel:film-cut` | all selects, stems | `film/edit/timeline.otio`, FCPXML/EDL export, `film/cuts/<title>_vN.mp4` | ffmpeg conform; cut diff between versions | viewer panel judging **sampled frames and the transcript**, not the cut list | **author watches the cut** |
| F10 | **Release** `film-release-check` | everything | `film/release/<title>_vN/`, `provenance.jsonl`, `licences.md`, `consent/` | nothing stale; every shot KEEP; continuity report clean; every asset's licence allows the intended use; spend summary | — | the author's go |

### The shot schema, extended

The film shot keeps the teaser fields and adds a scene layer and a
structured camera. The **intent** (what a director of photography would
write) is kept apart from the **render hints** each backend can use,
because a video model reads "85mm, f/2" as a style hint, not a setting;
only camera-control models take a path.

```yaml
id: "S014-05"            # scene 14, shot 5
scene_id: "S014"
coverage: single          # master | single | two-shot | over-shoulder | insert | cutaway | pov
shot_size: MCU            # enum: EWS WS FS MS MCU CU ECU
angle: eye                # enum: eye low high overhead dutch
camera: {height_m: 1.5, lens_mm: 50, t_stop: 2.0, focus: "Jakob", fps: 24, shutter_deg: 180}
move: {type: dolly_in, speed: slow, path: [[0, 0, 0], [0, 0, 0.6]]}   # metres, for camera-control backends
blocking: {Jakob: "desk, facing window", Kötzler: "door, frame left"}
screen_direction: left_to_right
eyeline: "Kötzler, off frame left"
lines: ["S014-L03", "S014-L04"]
continuity: {wardrobe: {Jakob: "black wool, 1519"}, props: ["courier book"], time: night, weather: snow}
duration_s: 5.2           # from the recorded lines, not guessed
refs: ["bible/characters/jakob/three_quarter.png", "bible/locations/counting-house/a.png"]
render_hints: {veo: "...", wan: "...", camera_lora: "dolly_in"}
```

### How it fits what exists

- **The teaser becomes a cut of the film**, not a separate pipeline: a
  trailer picks scenes and shots from `film/` and reuses the teaser's
  story and quality gates. The current teaser commands keep working.
- **Free first, paid by opt-in:** every stage has a `stub` and a local
  backend; a keyed backend runs only after the cost table, under a
  budget, and every call lands in `spend.jsonl`.
- **The author sees changes as a diff** (`/autonovel:diff` for the
  screenplay; a shot-level diff for cuts).
- **Generic across genres:** the screen rubric, coverage critic and sound
  defaults read the genre guide (`genres/<genre>.md` gains a "On screen"
  section), never a named book.

## 4. Recommended stack

Local first, because no free web endpoint is reliable enough to build on
(§7) and this machine can run every stage. Paid models go through one
aggregator (fal) so a model swap is one line of data. "Commercial" below
means the outputs may go into a film that is sold or entered for a prize.

### Tier 1 — free and local (RTX 5060 Ti 16 GB + RTX 3060 12 GB, WSL2)

| Job | Pick | Licence of the outputs | Hardware notes |
|---|---|---|---|
| Runner | ComfyUI headless (`POST /prompt` with workflow JSON) or Wan2GP's queue; **one server per card** | the tool is GPL-3.0; outputs unaffected | the two cards do not pool memory: video on the 5060 Ti; voices, music and lip touch-ups on the 3060. Needs a cu128/cu130 PyTorch (Blackwell); WSL sees 30 GB of RAM today, raise it in `.wslconfig` for offloading |
| Keyframes, character sheets | Qwen-Image-Edit-2511 or -2509; FLUX.2 [klein] 4B | Apache-2.0: commercial | klein ≈ 13 GB; Qwen in GGUF/fp8 |
| Character lock | a Wan 2.2 LoRA per principal (musubi-tuner, image-only); Stand-In or Phantom when a LoRA isn't worth it | Apache-2.0 | musubi suggests 64 GB of RAM; hours on 16 GB unverified |
| Image-to-video | Wan 2.2 A14B I2V, GGUF Q4/Q5 + 4-step LoRA, first-and-last-frame template; Wan 2.2 5B for previews | Apache-2.0 | one report: ~4 min per ~5 s clip at 576×768 on a 5060 Ti |
| Video with its own sound | LTX-2.x | free under $10M revenue; outputs must be disclosed as AI | NVFP4 on the 5060 Ti; frames can be pinned at any index |
| Camera moves | Wan2.2-Fun-Control-Camera presets; LTX dolly/jib LoRAs; Uni3C for a numeric path | Apache-2.0 | Uni3C needs ~50 GB officially, so numeric paths are an experiment |
| Lip-sync, talking | InfiniteTalk (multi-person, dubs an existing clip); LatentSync 1.5 (8 GB); MuseTalk 1.5 | Apache / OpenRAIL++ / MIT | LatentSync loads InsightFace models (non-commercial): swap the detector before a sale |
| Voices | VoxCPM2 (best); Chatterbox (MIT, watermarked); Kokoro for narration; MOSS-TTSD for whole scenes | Apache-2.0 / MIT / Apache / Apache | bake-off: VoxCPM2 ≈ 1.1× real time on the 5060 Ti; keep the Whisper re-take loop |
| Score | ACE-Step 1.5 | MIT, outputs commercial | < 4 GB, on the 3060 |
| Effects, Foley | Stable Audio Open; HunyuanVideo-Foley | free under $1M revenue; Hunyuan not licensed in the EU, UK or South Korea | MMAudio is non-commercial |
| Screenplay | screenplain (Fountain → PDF and FDX); afterwriting for page counts | MIT | CPU |
| Edit | ffmpeg + OpenTimelineIO, finished in DaVinci Resolve (free) | — | — |

### Tier 2 — paid but cheap (opt-in, after a cost table)

| Job | Pick | Price on 2026-10-28 | Notes |
|---|---|---|---|
| Keyframes | FLUX.2 [dev] on fal or Replicate; Gemini image (already wired) | $0.012 per megapixel; ~$0.04 an image | hosted outputs are commercial |
| Video | Kling v3 Standard on fal, with `elements` character references | $0.084/s silent, $0.126/s with audio | Pro is $0.112 / $0.168 |
| Video, cheapest | grok-imagine-video-1.5-lite | $0.02/s | quality untested by us |
| Video, best | Veo 3.1 on fal | Fast $0.10–0.15/s; Standard $0.20–0.40/s | fal's Veo endpoints end 2026-11-17 |
| Lip-sync | Kling lip-sync on fal; sync.so | $0.014/s (5 s minimum); plan + $0.05/s | |
| Voices | ElevenLabs Creator; Azure Neural TTS | $22/month for 121k credits; $15 per 1M characters | ElevenLabs clones only **your own** voice; Azure is the licensed home of the voices edge-tts borrows |
| Effects | ElevenLabs sound effects | in a paid plan | commercial on paid plans |
| Music | **not** Eleven Music on a self-serve plan (its terms exclude film and TV); use ACE-Step or a licensed library | — | Suno Pro grants commercial rights, but the output may not be copyrightable |

### What it costs

Three takes per shot, 5-second takes (Veo bills 6 s, its nearest
length). Keyframes, voices and music add under $200 at feature length.

| Output | Generated | Local | grok lite | Kling 2.5 Turbo | Kling v3 Std + lip-sync | Veo 3.1 Fast, audio | Veo 3.1 Std, audio |
|---|---|---|---|---|---|---|---|
| 60 s trailer, 12 shots | 180 s | $0; ~2.5 GPU-hours | $3.60 | $12.60 | ~$16 | $32 | $86 |
| 110 min feature, 1,500 shots | 22,500 s | $0 cash; ~300 GPU-hours (~2 weeks non-stop) at 576p, more at 720p | $450 | $1,575 | $2,205 | $4,050 | $10,800 |

Three takes is optimistic. The June teaser generated 522 seconds of Veo
for a 58-second cut, nine times its length. Every estimate above should be
printed by `--dry-run` from a price table kept as data, and a budget cap
should stop the run.

## 5. Milestones

Each one is worth having even if the next is never built. Effort is
building time (agent plus author review); cost is cash.

| # | Milestone | Useful on its own because | Effort | Cost | Acceptance check |
|---|---|---|---|---|---|
| M1 | **Screenplay pilot**: one sequence (3–5 scenes from one chapter) to Fountain, PDF and FDX; Fountain parse, validate and page count in `autonovel mechanical` | a scene can be read, pitched and table-read; it proves the format and the adaptation voice | ~2–3 days | $0 | screenplain renders PDF and FDX with no errors and the FDX opens in a screenwriting app; Tier-1 tests for parse, page count and the slugline and character checks; the author compares the scene with the chapter; a cold reader can follow it |
| M2 | **Feature screenplay**: `adapt` + `screenplay` + screen evaluate ⟳ revise + `screenplay-check` + a local-TTS table read | a complete, revisable script; the spec every later stage keys on | ~2 weeks | $0 | 100–120 pages in the PDF; every scene traces to its chapters; the author signs off `adaptation.md`; the release gate passes; drafts are shown as a diff |
| M3 | **Shot list and bible for one scene**: extended schema, 180° and continuity checks, the DP critic, reference sheets for that scene's people and place | a shot list a human crew could shoot from | ~1 week | $0 | schema validates; a planted crossing of the line and a planted costume change are both caught; the author agrees the coverage |
| M4 | **One-scene animatic**: keyframes, a VoxCPM2 read per character with the Whisper check, an ffmpeg animatic | the cheapest place to judge pacing and staging | ~1 week | $0 | the animatic runs within ±10% of the scene's page time; the vision judge catches a planted wrong face; the author can say what happens |
| M5 | **One-scene full render, local**: ComfyUI on the 5060 Ti, Wan 2.2 I2V, InfiniteTalk, ACE-Step cue, loudness mix, OTIO timeline; plus the same scene on Kling via fal under a $10 cap as a comparison | shows what the stack can and cannot do before anything bigger | ~3 weeks (WSL and Blackwell setup included) | $0 local; ≤ $10 optional | a 2–3 minute scene; `spend.jsonl` matches the provider's invoice; `provenance.jsonl` names model, version, seed and licence for every asset; every shot KEEP; the author decides whether to go on |
| M6 | **Trailer from the film**: the teaser rebuilt as a cut of `film/` assets | replaces today's stills teaser with real scenes | ~1 week | $0 local; $15–90 paid | the existing story and quality gates pass on it; dialogue shots are lip-synced |
| M7 | **A short or one episode** (10–20 min, 150–300 shots): fingerprint staleness, `film-status`, budget caps, both GPUs batching, Resolve export | a finished film that can go to festivals | ~4–6 weeks | $0 local (~30–60 GPU-hours); ~$200–450 paid | editing one scene marks exactly its shots stale; `film-release-check` passes, including the licence and consent checks |
| M8 | **Feature** (100–120 min, ~1,500 shots) | the goal | 2–3 months, mostly review | $0 cash and ~300+ GPU-hours locally, or $2,000–11,000 of video | as M7, plus an outside viewer watches it through |

## 6. Risks and open questions

- **Rights hide in dependencies.** A model can be Apache-2.0 while the
  face detector it loads (InsightFace) or the face model (Basel) is
  non-commercial; licences also carry revenue ceilings ($1M Stable Audio
  Open, $5M FLUX 3 Klein, $10M LTX-2) and territory holes (Hunyuan
  excludes the EU, UK and South Korea). Licences are kept as data, every
  asset is logged in `provenance.jsonl`, and the release gate checks
  the film's intended use against them.
- **Consent and likeness.** Clone a voice only with written consent, kept
  in `film/consent/`; ElevenLabs will not clone anyone else's voice even
  with consent. Never render a living person. Real historical figures
  are built from public-domain portraits, as the teaser does; the
  author's lawyer, not this plan, settles personality rights in each
  market.
- **Disclosure and ownership.** The EU AI Act's labelling duty for
  synthetic video has applied since 2 August 2026 (lighter for evidently
  fictional works), and LTX-2 and FLUX require disclosure by licence. The
  US Copyright Office's position is that purely generated material is not
  copyrightable; the author's protectable work is the novel, the
  screenplay and the selection and arrangement of the cut.
- **Cost blow-ups.** Takes, not prices, drive cost (9× in June). The
  defences are local first, a dry-run cost table, a hard budget, a spend
  ledger, the animatic sign-off before any render, and paying only for
  shots the vision judge marks UPGRADE.
- **Model churn.** In two months: Sora's API removed (2026-09-24), the
  Veo 3.1 preview models shut (2026-10-22, breaking our `veo` backend),
  fal's Veo endpoints ending (2026-11-17), Pollinations' free video gone,
  grok no longer free. Backends stay thin and data-driven, intent stays
  apart from render hints, and the shot list outlives any model.
- **The quality ceiling.** No open or paid system holds a cast through a
  feature yet; the research systems (MovieAgent, HoloCine, Captain
  Cinema) all reduce to keyframes, short clips and a critic. Expect
  animatic-plus quality at M5 and decide then whether a feature is worth
  it, or whether the screenplay, an animatic and a trailer are the
  product.
- **Hardware.** WSL2 cannot filter GPUs by index reliably and limits pinned
  memory; Blackwell needs current PyTorch builds; 30 GB of visible RAM is
  thin for offloading 14B models. Test one server per card at M5 before
  planning on two.
- **The author's time.** Approving 1,500 shots one by one is impossible;
  checkpoints are per scene (the animatic, then the selects), with the
  judges filtering first.
- **Open questions for the author.** Feature, limited series, or a radio
  drama (screenplay plus voices, nearly free)? A shot list for a
  human crew (`--actors human`) as a product in itself? Personal project
  or commercial release (it decides which licences are acceptable)? Which
  country's rules apply? Should `treatment` drop its X-Prize default now
  that the 2026-08-15 deadline has passed?

## 7. What to keep from the pasted answer

| The answer proposed | Verdict | Why (sources in §8) |
|---|---|---|
| Stage split: voice, visuals, animate, lip-sync, FFmpeg | **keep** | sound; the repo already works this way |
| Portrait first, then image-to-video | **keep, extend** | right idea, but one portrait does not hold costume, props or place across hundreds of shots; add sheets, LoRAs and a continuity check |
| edge-tts | **replace** with VoxCPM2 / Chatterbox / Kokoro locally, or Azure Neural TTS paid | not an official API; a Microsoft answer warns commercial use without Azure may breach its terms; 403 breakages in 2026; no emotion styles |
| FLUX.1 [dev] on free Spaces | **replace** with Qwen-Image-Edit or FLUX.2 [klein] 4B, local | self-hosted [dev] is non-commercial; ZeroGPU gives 5 GPU-minutes a day |
| Wan 2.1 / Hunyuan on free credits | **keep Wan (2.2), run it locally**; drop Hunyuan in the EU or UK | Replicate states no free credit; Hunyuan's licence excludes the EU, UK and South Korea |
| Wav2Lip / SadTalker | **replace** with InfiniteTalk, LatentSync, MuseTalk | Wav2Lip forbids commercial use; SadTalker needs the non-commercial Basel Face Model |
| ElevenLabs | **keep for paid voices** | but $22 buys 121k credits, and it clones only your own voice |
| Flux schnell via Replicate | **keep as an option** | Apache-2.0, $0.003 an image; FLUX.2 handles references better |
| Kling API | **keep via fal** | but $0.35–0.84 per 5 s, not $0.10–0.20 |
| Hedra | **optional** | ~2.5–6 ¢/s, roughly as stated; per-second rate unverified |
| Cloudinary | **drop** | ffmpeg and OpenTimelineIO cover assembly |
| "$1.50–2.50 for a 60 s trailer" | **wrong** | $3.60–86 at three takes, before keyframes, voices or lip-sync |
| A parser reading `[Character: John]` cues from the chapter | **replace** with adaptation (F0) and a screenplay (F1) | novels carry no such cues; the work is compressing 120,000 words into 110 pages |

What it leaves out entirely: screenplay format, shot grammar and camera
control, continuity across hundreds of shots, any review loop or human
checkpoint, cost at feature length, and rights and consent.

## 8. Sources

TODO-SOURCES
