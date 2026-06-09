---
name: autonovel:teaser-assemble
description: Stitch the rendered teaser clips into one video via ffmpeg, then run a viewer-panel cut critique (does the hook land, does it accelerate, does the button withhold?). Builds an editable cut_list.json first.
argument-hint: "--book <short-name> [--kind image|video|mixed] [--audio <path>] [--audio-mode auto|duck|mix|clip-only|bed-only|none] [--no-clip-audio] [--no-transitions] [--burn-titles] [--font <path>] [--fps <n>] [--take <n>] [--force]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - books/{book}/teaser/teaser.json
  - books/{book}/teaser/cut_list.json
writes:
  - books/{book}/teaser/cut_list.json
  - books/{book}/teaser/assembly-report.md
context_mode: book
---

<purpose>
The last step: turn the per-shot clips in `books/{book}/teaser/clips/`
into **one teaser video**. It builds an editable `cut_list.json` (the
ordered clips + durations + optional audio bed), assembles it with
**ffmpeg**, and then runs a **viewer-panel cut critique** — the watch-it-
back judgement the per-clip critique can't make: does the hook land in
the first few seconds, does the escalation actually accelerate, does the
title land ~⅔ in, does the button withhold the ending, does the whole cut
hold together?

It can stitch a still-image slideshow (`--kind image` — each shot held for
its `duration_s`), real video clips (`--kind video`), or a **mixed** cut
(`--kind mixed`, Phase 8) that, per shot, uses the dynamic
`shot_<id>.mp4` when present (native audio, trimmed to `duration_s`) else
the static `shot_<id>.png` keyframe (held, silent) — the real-teaser shape
of a few motion shots woven through a keyframe slideshow, all normalized to
one WxH + stereo AAC so the concat works. Mostly **hard cuts** with
**fades** where they earn it, plus an optional ducked audio bed.

**Text cards.** By default the cut-list records each `text_card` as an
editor note (models garble type; `docs/teaser-craft.md` §4). `--burn-titles`
(opt-in, Phase 8) burns them in with ffmpeg `drawtext` — the `title`-role
card centered + large, others lower-third, each faded over its segment;
`--font <path>` picks a serif (e.g. EB Garamond). Use it for a quick
self-contained cut; prefer an editor for final polish.

**Figure-identify lower-thirds (Phase 12 — legibility).** Any shot with an
`identify` field (a key figure's first appearance, e.g. *"Jakob Fugger — the
richest man in Europe"*) gets a small name label burned at the very bottom
for its first ~2.5 s — so a first-time viewer knows WHO they're watching.
This is **always burned** (independent of `--burn-titles`): it is load-bearing
legibility, not an optional story card. It carries through `cut_list.json` as
the entry's `identify`.

**The voiceover spine (Phase 13 — short mode).** In a `short`, the shots'
`voiceover` lines (the protagonist's first-person narration) are the spine
that makes the cut cohere — they run as ONE continuous track laid over the
whole teaser (like the music bed, ducked the same way). Record/synthesize the
narration from the in-order `voiceover` lines and lay it over the cut; the
in-scene `audio.dialogue` stays as accents. **The viewer-panel cut critique
must watch the assembled cut COLD** (as a stranger) and judge whether the VO
+ pictures tell ONE legible story — not rubber-stamp it. (Actual VO-audio
synthesis is the open follow-up; the lines + the cohesion judgement land now.)

**Transitions (Phase 5.7).** The build applies safe defaults: the teaser
**fades in** from black on the first shot, **fades out** on the last, and
**fades** title cards; everything else is a hard cut (`--no-transitions`
disables this). For *where else* a transition earns its place, run
`teaser-transitions` — it flags candidates from structured signals (big
`story_year` jumps, `setting`/location changes, fast→slow `duration_s`
shifts, beat changes) — then **you** (the LLM) make the artistic call and
set `transition: fade|dissolve` / `fade_out: true` on the relevant
`cut_list.json` entries. (`dissolve` renders as a fade for now; true
cross-dissolve needs the xfade overlap pass — FUTURE-TODOS.)

**Audio (Phase 5.4).** Video clips from grok/veo/kie carry **native
dialogue + SFX + ambience**, so assembly **keeps the clip audio** — it is
no longer dropped. With `--audio <bed>` the music bed **ducks under the
dialogue** by default (sidechain compression) instead of replacing it.
`--audio-mode` overrides: `duck` (default when clips have audio + a bed),
`mix` (equal levels), `clip-only` (native audio, no bed), `bed-only`
(ignore clip audio), `none` (silent), `auto`. Image slideshows have no
clip audio, so a bed is simply the track. If your video clips are silent
(e.g. magichour), pass `--no-clip-audio` so a bed becomes the track.

**Music / score (Phase 5.9 + 9).** A trailer wants *one continuous* score.
Two paths: (a) render with `teaser-render --score bed`, then supply one
music file here (`--audio track.mp3`) — it's ducked under the dialogue and
carries the whole teaser (the pro-trailer path). The bed can be your own
royalty-free file **or generated** with `bash`: `autonovel mechanical
teaser-music books/{book}/teaser/teaser.json [--provider stub|musicgen|
elevenlabs] [--duration <s>]` — it scores from the teaser spine's
`score_direction` and writes a versioned `teaser/music/<title>_bed_*.{wav,
flac,mp3}` (the `stub` provider is an offline silent WAV to rehearse the
chain for $0); pass that path to `--audio`. (b) render with `--score
native` (the model scores each clip) — the music won't flow across cuts,
so pass `--audio-seam-fade 0.2` to fade each clip's audio in/out at the
cuts so it doesn't *pop*. (A true overlapping cross-fade is the deferred
xfade work, 5.7b.)

Like `/autonovel:audiobook-assemble`, the heavy lifting (ffmpeg) runs in
this command via `bash`; the Python helper only *plans* the command.
ffmpeg is required — if it is missing, the command stops with an install
hint and does not fail silently.
</purpose>

<workflow>
**Read-failure policy.** `books/{book}/teaser/teaser.json` and the clips
in `books/{book}/teaser/clips/` are load-bearing — stop if the teaser is
missing (run `/autonovel:shot-prompts`) or no clips exist yet (run
`/autonovel:teaser-render`). An existing `books/{book}/teaser/cut_list.json`
is reused when present (so your hand-edits survive); regenerate with
`--force`.

1. Parse `$ARGUMENTS`. Required: `--book <short-name>`. Optional:
   `--kind image|video|mixed` (default `image`; `mixed` = video clip per
   shot when present, else the still keyframe — Phase 8), `--audio <path>`
   (a music-bed file), `--audio-mode auto|duck|mix|clip-only|bed-only|none`
   (default `auto` — duck the bed under native dialogue), `--no-clip-audio`
   (the video clips are silent, e.g. magichour), `--no-transitions` (keep
   every cut hard — disables the open/close/title fade defaults),
   `--burn-titles` (burn the text cards in with ffmpeg drawtext — Phase 8),
   `--font <path>` (serif font file for burned titles, e.g. EB Garamond),
   `--audio-seam-fade <s>` (fade each clip's audio at cuts so native
   per-clip music doesn't pop — for the `--score native` path), `--fps <n>`
   (default 30), `--take <n>` (which take per shot, default 1), `--force`.
   Confirm the book exists in `project.yaml`.

2. **ffmpeg check.** `bash`: `ffmpeg -version` (or `command -v ffmpeg`).
   If absent, stop with: "ffmpeg is required for assembly — `apt install
   ffmpeg` / `brew install ffmpeg`, or run `autonovel install-export-tools`."

3. **Build / reuse the cut-list.** If `books/{book}/teaser/cut_list.json`
   exists and `--force` was not passed, reuse it. Otherwise `bash`:
   `autonovel mechanical teaser-cut-list books/{book}/teaser/teaser.json --kind <kind> [--audio <path>] [--audio-mode <mode>] [--no-clip-audio] [--burn-titles] [--font <path>] --fps <n> --take <n> --format json`
   — this writes `books/{book}/teaser/cut_list.json` (ordered clips +
   per-entry `media` for a `mixed` cut + per-shot `duration_s` + any
   `text_card` notes + `burn_titles`/`font_file` + the audio policy) and
   reports any shots with no clip on disk. With `--kind mixed` each shot
   resolves to its `shot_<id>.mp4` (video) else `shot_<id>.png` (still). For `--kind video` from
   grok/veo/kie the clips carry native audio, so the bed ducks under it by
   default; pass `--no-clip-audio` only if the video backend was silent
   (magichour). If clips are missing, tell the user to render them
   (`/autonovel:teaser-render`) and proceed with what exists. The build
   applies the safe transition defaults (open fade-in / close fade-out /
   title fade); `--no-transitions` keeps everything a hard cut.

3b. **Consider scene transitions.** `bash`:
   `autonovel mechanical teaser-transitions books/{book}/teaser/teaser.json --format json`
   Read the advisory `suggestions` (time jumps, location changes, pace
   shifts, open/close). Decide — as the editor — which earn a transition,
   then `file_write` the chosen `transition: fade|dissolve` / `fade_out:
   true` onto the matching `cut_list.json` entries (hand-edits survive
   reuse). Keep it sparing: a trailer is mostly hard cuts; fades mark real
   shifts. Skip silently if there are no meaningful candidates.

4. **Plan the ffmpeg command.** `bash`:
   `autonovel mechanical teaser-ffmpeg-cmd books/{book}/teaser/cut_list.json --versioned --format json`
   Read the `command` (a shell-ready ffmpeg invocation), `out` (the
   timestamped target mp4, e.g.
   `books/{book}/teaser/<title>_teaser_<UTC>.mp4`), and `latest` (the
   `<title>_teaser_latest.mp4` pointer). `--versioned` keeps every cut so a
   re-assemble never clobbers one you preferred.

5. **Assemble.** `bash`: run the `command` from step 4 verbatim, then
   `cp <out> <latest>` so `<title>_teaser_latest.mp4` always points at the
   newest cut (prior timestamped cuts are kept). Confirm the output mp4
   exists and report its size/duration. If ffmpeg errors, surface the tail
   of its stderr — do not retry blindly.

6. **Viewer-panel cut critique.** Review the assembled cut against
   `docs/teaser-craft.md` §8 (the shape of the 60–180 s):
   - **Hook (0–10 s):** does the opening image/line grab in the first few
     seconds without explaining?
   - **Escalation:** do the cuts accelerate and the stakes rise?
   - **Title (~⅔ in):** does the brand beat land in the right place?
   - **Button (final 5–10 s):** does it deepen the question and **withhold
     the resolution**?
   - **Whole:** pacing, rhythm, cast clarity (one hero face), and whether
     music/silence carries it. (For an image slideshow, judge from the
     keyframes + their durations; note that motion/audio are approximated.)
   For each weak point, give a concrete re-cut suggestion (reorder, trim a
   beat's `duration_s`, drop/add a clip, move the title) — edits the user
   applies by hand-editing `cut_list.json` and re-running.

7. **Write `books/{book}/teaser/assembly-report.md`** — advisory:

   ```markdown
   # {Display Title} — Teaser assembly report

   *Output:* books/{book}/teaser/<title>_teaser.mp4 · *Clips:* {n} ·
   *Runtime:* {total}s · *Kind:* {kind} · *Audio bed:* {yes|no}

   ## Verdict
   {2-3 sentences: does the cut work? top 1-3 re-cuts.}

   ## Beat-by-beat
   {hook / escalation / title / button notes, each KEEP or RE-CUT + why.}

   ## Text cards to add in an editor
   {the text_card notes from cut_list.json, in order — burn these in your
   editor, not the model.}
   ```

8. Print a one-screen summary: output path, runtime, clip count, the top
   re-cut, and the next step:

   ```
   🎬 Assembled books/{book}/teaser/<title>_teaser.mp4 — {n} clips, {total}s.
        Verdict: {one line}.

   Re-cut by editing books/{book}/teaser/cut_list.json (reorder, trim
   durations, swap clips), then re-run /autonovel:teaser-assemble --force.
   Add the title/subtitle cards in your editor (see the report).
   ```
</workflow>

<acceptance>
- `books/{book}/teaser/cut_list.json` exists (ordered clips + durations +
  any text_card notes + optional audio bed); hand-edits to it survive a
  re-run unless `--force`.
- ffmpeg presence is checked first; absence stops the command with an
  install hint (never a silent failure).
- The output mp4 is produced under `books/{book}/teaser/` by running the
  planned ffmpeg command via `bash` (Python only plans it, never runs it).
- `books/{book}/teaser/assembly-report.md` exists with a verdict, a
  beat-by-beat hook/escalation/title/button critique, and the list of
  text cards to add in an editor.
- A `mixed` cut resolves each shot to its video clip when present else its
  still keyframe, normalized to one WxH + stereo AAC (silence for stills);
  a shot with no clip on disk is skipped (and reported), never a hard
  failure.
- No model-rendered type ever; text cards are editor notes by default and
  only burned in (ffmpeg `drawtext`, title centered / stingers lower-third,
  faded) when `--burn-titles` is passed.
</acceptance>
