---
name: autonovel:animatic
description: Cut a scene's storyboard to its table read — each keyframe held for its shot's duration (computed from the recorded lines and the action), with the shot list's camera moves done as slow pushes and pans, the lines where the shot list places them, and the place's sound under them — into film/animatic/<scene>.mp4 (and one joined film for several scenes); a viewer who sees only sampled frames and the transcript says what happens and where it drags.
argument-hint: "--scene <ID> [--scene <ID> ...] --book <short-name> [--join <name>]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
  - task
reads:
  - shared/craft/CAMERA.md
  - books/{book}/film/shots/*.json
  - books/{book}/film/storyboard/*.json
  - books/{book}/film/audio/table_read/manifest.json
  - books/{book}/film/audio/ambience/*.json
  - books/{book}/film/bible/locations/*.yaml
writes:
  - books/{book}/film/shots/*.json
  - books/{book}/film/audio/ambience/*.json
  - books/{book}/film/audio/ambience/*/*.flac
  - books/{book}/film/animatic/*.mp4
  - books/{book}/film/animatic/*.json
  - books/{book}/film/animatic/*/*.jpg
  - books/{book}/film/reviews/*_animatic_viewer.md
context_mode: book
---

<purpose>
The animatic is the cheapest place to judge a scene's pace and staging:
the storyboard's stills, timed to the spoken lines and the action, with
simple camera moves and the sound of the place (stage F4, milestone M4 of
`docs/film-pipeline-plan.md`). It is the author's main sign-off before
anything costly is rendered: they watch it and say what happens, what is
slow, what is unclear.

It writes, under `books/{book}/film/`:

- `animatic/<scene>.mp4`: the scene, 1280×720 at 24 fps, letterboxed to the
  look's 1.85:1, with each shot's ID small in the corner, the `SUPER:` text
  where the script has it and the dialogue as subtitles;
- `animatic/<scene>.json`: the cut list: each shot's in and out, each
  line's start, each sound's place, and the fingerprint of every source;
- `animatic/<name>.mp4` with `--join`: the scenes in order as one film;
- `animatic/<scene>_frames/`: one still per shot from the finished cut;
- `audio/ambience/<scene>.json` and its takes: the scene's sound beds and
  effects, made by a local sound model when one is available;
- `reviews/<scene>_animatic_viewer.md`: the viewer check.

`--scene`: the scene(s), in screen order. `--join <name>`: also join them
into `animatic/<name>.mp4`.
</purpose>

<workflow>
**Read-failure policy.** The shot list, the storyboard manifest and the
table read's manifest are load-bearing for each scene: stop and name the
command that makes the missing one (`/autonovel:shot-list`,
`/autonovel:storyboard`, `/autonovel:table-read`). `shared/craft/CAMERA.md`
and the location files are best-effort. Do not retry a failed `file_read`.

1. **Check every input is current.** For each scene, use `bash` from the
   series root:

   ```
   autonovel mechanical shot-check books/{book}/film/shots/<ID>.json --retime --format markdown
   autonovel mechanical keyframe-status books/{book}/film/storyboard/<ID>.json
   ```

   The first must exit 0, report "line times from: table read" (every line
   recorded in `books/{book}/film/audio/table_read/manifest.json` and current;
   otherwise run `/autonovel:table-read`) and say
   nothing changed in the script or the look since the shot list was made;
   `--retime` writes each shot's duration from the recordings. The second
   must show every frame `keep` or `author` (a frame marked `author` is
   shown, and named in the report).

2. **Study** `shared/craft/CAMERA.md` §6 (how long a shot runs) and §9 (the
   animatic and its viewer check).

3. **The scene's sound.** If `books/{book}/film/audio/ambience/<ID>.json`
   is missing, write it with `file_write` (schema `autonovel-film-frames/1`,
   `kind: sound`, `scene_id`): one bed per place in the scene, from the
   `sounds` list of its file in `books/{book}/film/bible/locations/` (what is
   heard there at that hour: water, work, animals, bells, voices), placed
   under a run of shots (`place: {shots: [...], gain_db: -20, fade_s: 1}`);
   and one cue for each sound the action names (a dog's barking, a bell),
   placed at a moment in a shot (`place: {shot, at_s, gain_db}`). Each cue
   has a `prompt` describing the sound plainly and positively, as a field
   recording ("water lapping against stone steps at night, a fire crackling
   through an open door"), `seconds` and a `seed`. Render it on the local
   ComfyUI server (Stable Audio 3; one GPU job at a time):

   ```
   autonovel mechanical keyframe-render books/{book}/film/audio/ambience/<ID>.json --ram-limit <GB>
   ```

   With no sound model available, skip this step: the animatic plays the
   lines over silence, and the report says so.

4. **Build** with `bash`:

   ```
   autonovel mechanical animatic books/{book}/film/shots/<ID>.json [books/{book}/film/shots/<ID2>.json ...] --frames [--join <name>] --format markdown
   ```

   It prints each scene's length against its page time and any problem (a
   shot with no keyframe is shown as a card with its action).

5. **The viewer check.** Use `task` to spawn a viewer in a **fresh
   subagent** conversation who knows nothing of the book or the script.
   Give it only the frames in `books/{book}/film/animatic/<ID>_frames/` in
   order with each shot's in and out times, and the transcript (each line's
   start time and words, from the cut list `books/{book}/film/animatic/<ID>.json`
   `lines`); tell it not to open the shot list, the script or anything else.
   Ask it, per CAMERA.md §9: where are we and when; who is who; what happens
   and what has changed by the end; where would it drag or rush at these
   lengths; which frame could not be read in its time; and what it would
   ask the director. It writes the answers to
   `books/{book}/film/reviews/<ID>_animatic_viewer.md`. Then judge each
   point: a pace problem is fixed in the shot list (`timing.hold_s`,
   `action_s`, a line's lead or tail) and re-checked with `shot-check
   --retime --stamp`; a frame that can't be read goes back to
   `/autonovel:storyboard`; rebuild (step 4) and record under `## Response`
   what changed for each point.

6. **Length.** Read the length against the page time. Within ±10% is the
   milestone's target; outside it, say which shots carry the difference and
   why (CAMERA.md §6.4).

7. **Report to the author**, in plain sentences: the file to watch and its
   length against the page time; what the viewer understood and where they
   were lost or bored; what was changed for it; every frame marked for the
   author; whether the sound is a model's or none. Then **Next:**
   1. Watch `books/{book}/film/animatic/<ID>.mp4` (or the joined film) and
      say what happens, what is slow and what is unclear.
   2. After changes: `/autonovel:shot-list --scene <ID> --book {book} --force`
      or `/autonovel:storyboard --scene <ID> --book {book}`, then this
      command again.
</workflow>

<acceptance>
- `books/{book}/film/animatic/<ID>.mp4` exists for every scene, with its cut
  list `books/{book}/film/animatic/<ID>.json`; each shot is held for its
  computed duration and each line starts where the shot list places it.
- Every line heard is a current table-read recording; every still is the
  storyboard's select.
- `books/{book}/film/reviews/<ID>_animatic_viewer.md` holds a viewer's
  answers from the frames and the transcript alone, and a response per point.
- The report gives the length against the page time.
- No script, storyboard image or book file is written.
</acceptance>
