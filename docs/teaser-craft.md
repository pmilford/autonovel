# Teaser craft — how to make a 1–3 minute AI-video teaser

> **Who this is for:** anyone using autonovel's movie-teaser mode —
> especially if you've **never made a video before.** It's the film-craft
> companion to [`CRAFT.md`](../CRAFT.md) (prose craft) and
> [`ANTI-SLOP.md`](../ANTI-SLOP.md). The teaser commands read this file
> the way the writing commands read CRAFT.md — it's *prompt material*,
> not just documentation. The build spec lives in
> [`prd-movie-teaser-mode.md`](prd-movie-teaser-mode.md).

A teaser sells a **tone and a question**, not the plot. Done right, a
90-second teaser made of cheap AI clips can feel like a real film. This
guide is the opinionated craft autonovel applies — every default here is
overridable, and `/autonovel:teaser-coach` will explain any of it in the
context of *your* story.

---

## 1. The words: beat → scene → shot → clip

Four terms, used consistently:

- **Beat** — one story turning point ("she discovers the ledger is
  forged"). A teaser is built from ~8–20 beats.
- **Scene** — a continuous unit in one place + time. A scene may hold
  several beats.
- **Shot** — one camera setup: one framing, one move. *This is the unit
  a video model renders.* One scene → many shots.
- **Clip** — the actual generated 4–10-second video for one shot.
  Usually 2–4 takes per shot; keep the best.

The pipeline: **story → beats → scenes → shots → clips → cut.**

## 2. The dual-audience problem (the one big idea)

A scene description has to satisfy two readers who want opposite things:

| Reader | Wants | Hates |
|---|---|---|
| **You** (editing) | meaning, emotion, why the beat matters | a dry list of nouns |
| **The video model** | concrete visible nouns, one action, present tense, what's literally in frame | interiority, abstraction, metaphor, backstory |

So each shot is written **twice**: a one-line *beat note* you understand,
and a *shot prompt* the model obeys. Example:

- **Beat note:** *Tommaso realises the accounts don't balance — the
  moment the conspiracy becomes real to him.*
- **Shot prompt:** *Medium close-up, low-angle. TOMMASO (late 20s,
  ink-stained fingers, plain woollen doublet) snaps the ledger shut, jaw
  tightening, one slow exhale. Candlelit counting-house, ledgers stacked
  behind. Warm low-key light, amber/walnut palette. Slow push-in. 85mm,
  shallow depth of field. Shot on 35mm film. Tense.*

## 3. Externalise interiority (film shows; it can't narrate)

Novels live in thought ("she wondered if he'd betray her"). A camera can
only show **behaviour**. Convert every interior state into a visible
action:

- *anxious* → grips the table edge, jaw tight, one hard swallow
- *suspicious* → eyes flick to the door, hand drifts off the cup
- *triumphant* → the smallest smile, shoulders drop

(This is the same show-don't-tell discipline the writing pipeline uses —
run forward: interiority → action.)

## 4. Rules for a shot description the model will obey

- **One subject doing one thing; one camera move.** Multi-action clips
  fall apart.
- **Present tense, active, concrete.** "Rain hammers the cobbles," not
  "it had been raining."
- **Only what's in frame.** No backstory, no off-screen cause, no
  "because."
- **No un-filmable abstraction.** "Her world collapses" → pick the
  visible image that *means* that.
- **Name the subject identically every time** — reusing the exact
  appearance words keeps the character consistent across clips.
- **No legible on-screen text** — make title/subtitle cards in the
  editor, not the model (models garble text).
- **No real people or trademarked characters** (also a competition-rules
  issue).

## 5. Cinematography words that actually work

Use *these* terms — the models are trained on them:

- **Shot sizes:** extreme close-up · close-up · medium · wide /
  establishing · over-the-shoulder · POV · two-shot.
- **Angles:** eye-level · low-angle · high-angle · bird's-eye · dutch.
- **Camera moves:** static · pan · tilt · dolly in/out · truck · zoom
  in/out · crane · aerial/drone · handheld · orbit · push-in / pull-out
  · dolly-zoom (vertigo).
- **Lens/optical:** wide-angle · telephoto · shallow depth of field /
  bokeh · rack focus · lens flare · "85mm" / "35mm handheld".
- **Lighting:** golden hour · moonlight · firelight · neon · low-key ·
  high-key · Rembrandt · film-noir shadows · volumetric rays ·
  backlight/silhouette.
- **Look / film stock:** "shot on 35mm film" · anamorphic · "cinematic
  film look" · era looks ("1980s vaporwave", "1920s sepia + grain").
- **Palette:** name **3–5 colour anchors** ("amber, cream, walnut") and
  hold them across every shot — this is what makes the edit seamless.
- **Temporal:** slow-motion · time-lapse.

autonovel pulls the era look from your `project.yaml` period/region and
the palette/grade from `art/visual_style.json`, so you don't type these
by hand.

## 6. Keeping a character consistent across clips

The hardest part. The workflow that works:

1. Generate a **canonical reference image** of each character and key
   location first.
2. Feed that image as the **reference / first frame** of every clip with
   that subject.
3. **Reuse the exact appearance description** in every prompt.
4. Hold **lighting logic + the 3–5 colour palette** identical.
5. Chain **last frame of one clip → first frame of the next** for
   continuous action.

Honest caveat: identity still drifts sometimes. Reference images reduce
it; they don't perfect it. Lean on them and pick the best takes.

## 7. Creative defaults — your first-timer questions, answered

Opinionated starting points (all overridable; `/autonovel:teaser-coach`
explains each against your story).

### How long is a shot? a scene? the teaser?

| | Default | Why |
|---|---|---|
| One **shot** | **2–4 s** | Clips are short; trailers cut fast. Over-generate, pick best. |
| The **hook** | one **4–6 s** shot | The opening image needs room to land. |
| **Escalation** cuts | down to **1–2 s** | Accelerating cuts = rising tension. |
| **Final image** | **3–5 s** hold | Let the last beat breathe. |
| **30 s** teaser | **~8–12 shots** | Good debug size. |
| **3:00** teaser (X-Prize) | **~35–60 shots** | The competition target. |

### How many characters?

**One hero face; at most 2–3 named faces total.** More faces = more
identity drift and less emotional clarity. A teaser sells *one* person's
stakes. Crowds, silhouettes, and backs-of-heads are free — they don't
need consistency locking.

### How do I hook people in the first 5 seconds?

Pick one — and **intrigue, don't explain** (no exposition up front):

- the **strongest single image** in your world;
- a **dramatic question** — a situation that demands "…what happens
  next?";
- a **provocative line** (text card or one spoken line) — *"They told us
  the war was over."*;
- **disorientation → orientation** — a strange close-up, then pull out
  to reveal the world.

### The ending — do I hint at it or keep it a surprise?

- **Default: tease the *question*, withhold the *answer*.** Show the
  stakes and the world; never show the resolution. End on the unanswered
  question, or a "button" (a final hook *after* the title card) that
  deepens the mystery.
- **For the X-Prize:** the brief asks you to "show a future worth
  building," so the **vision** is often the point — **reveal the vision,
  withhold the journey.** Show the hopeful destination; hint that
  humanity *earns* it through struggle; hide the road.
- **Never** spoil a twist or the final emotional beat — that's what the
  film is for.

### Other sensible defaults

| Knob | Default | Note |
|---|---|---|
| Aspect ratio | **16:9** | Festival/competition standard; `9:16` for social. |
| Audio | music bed + 1–2 dialogue stings + SFX | Music carries a teaser; dialogue is sparing. |
| Text cards | **2–4 short cards** | Carry narrative cheaply; dodge AI lipsync. |
| Title card | at **~⅔** point | Brand beat before the button. |

## 8. Teaser structure (the shape of the 60–180 s)

1. **Cold hook (0–10 s)** — one arresting image or line.
2. **Escalation montage (10–60 s)** — accelerating shots, rising stakes,
   intercut with text cards; pacing tightens.
3. **Title card** (mid or ~⅔ in).
4. **Button / stinger (final 5–10 s)** — a last shock or unanswered
   question after the title.

**Music and sound design carry a teaser.** Build to a drop on the title
card; let text cards do narrative work; ramp from longer opening shots to
quick escalation cuts, then hold the final image.

## 9. When the model misbehaves

Common failures: morphing/identity drift, flicker, extra/melting limbs,
garbled text, physics breaks, unwanted camera drift.

Fixes that reliably help: use reference/first-frame images; one action +
one camera move + a short clip; render text in the editor not the model;
higher resolution; change one thing at a time; and a **negative prompt**
written as content words — `blurry, distorted hands, extra limbs,
watermark, text, subtitles, flicker, morphing`. **Never** write "no
walls" / "don't show…" — the model reads the content words, so negation
backfires.

---

*See [`prd-movie-teaser-mode.md`](prd-movie-teaser-mode.md) for the
provider landscape, the machine prompt schema, the free
agent-driven toolchain, and the self-critique testing loop.*
