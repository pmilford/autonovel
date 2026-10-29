---
name: autonovel:shot-list
description: Break one scene of the screenplay into shots, as a director and director of photography would — coverage, size, angle, lens, camera height, each move with its motivation, blocking, the line and screen direction, eyelines, which lines and action each shot carries, continuity, and a duration computed from the lines and the action — into film/shots/<scene>.json, checked mechanically (coverage, the 180° line, eyelines, continuity, timing, the film's look) and by a director/DP critic in rounds until it passes.
argument-hint: "--scene <ID> --book <short-name> [--rounds <n>] [--force]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
  - task
reads:
  - shared/craft/CAMERA.md
  - shared/craft/SCREEN.md
  - shared/craft/genres/*.md
  - shared/genres/*.md
  - books/{book}/film/screenplay/seq_*.fountain
  - books/{book}/film/screenplay/seq_*_adaptation.md
  - books/{book}/film/scenes.json
  - books/{book}/film/bible/look.yaml
  - books/{book}/film/bible/characters/*.yaml
  - books/{book}/film/bible/locations/*.yaml
  - books/{book}/film/bible/props.yaml
  - books/{book}/film/shots/*.json
writes:
  - books/{book}/film/shots/*.json
  - books/{book}/film/shots/*.md
  - books/{book}/film/reviews/*_shots_critic.md
context_mode: book
---

<purpose>
Turn one scene of the screenplay into a shot list a crew could shoot from
and the storyboard can draw: stage F3 of the film pipeline
(`docs/film-pipeline-plan.md`, milestone M3). The author is not expected
to know how a scene is covered; this command is the director and the
director of photography, and `shared/craft/CAMERA.md` is their craft.

It writes, under `books/{book}/film/`:

- `shots/<scene>.json`: the shot list in the plan's extended schema, one
  entry per shot: coverage, size, angle, camera (height, lens, stop,
  focus, frame rate, shutter), move with its motivation, who is in the
  frame and where (blocking), screen direction, the camera's side of the
  line, eyeline, the scene's lines and action paragraphs it carries,
  continuity (wardrobe, props, time, weather, light), timing and a
  duration. Every later stage (storyboard, table read, animatic, render)
  keys on its shot IDs.
- `shots/<scene>.md`: the same list as a page the author can read: what
  each shot shows and why, how it is framed, why the camera moves, which
  lines play in it and for how long.
- `reviews/<scene>_shots_critic.md`: the director/DP critic's scores,
  tests and notes, round by round, and what was changed for each.

The shot list designs how the scene is seen; it does not change what
happens in it. The script decides the events and the lines; the bible
(`film/bible/`) decides how people, places and objects look and how the
film is lit; the shot list decides what the camera shows, from where,
and for how long.

`--scene <ID>`: the scene, e.g. `S0104` (its ID in `film/scenes.json`).
`--rounds <n>`: the most critic rounds (default 3). `--force`: replace an
existing shot list for the scene.
</purpose>

<workflow>
**Read-failure policy.** The scene's sequence file
(`books/{book}/film/screenplay/seq_NN.fountain`), `shared/craft/CAMERA.md`
and `books/{book}/film/bible/look.yaml` are load-bearing: stop if any is
missing (for CAMERA.md, run `autonovel refresh-templates` from the series
root first; for look.yaml, the film bible comes first). The bible's
character, location and props files, the adaptation note, the genre guide
and `shared/craft/SCREEN.md` are best-effort: note a gap in the shot list's
`notes` and go on; do not retry a failed `file_read`.

1. **Parse `$ARGUMENTS`.** `--scene` and `--book` are required. Find the
   scene's sequence in `books/{book}/film/scenes.json` (its `seq`). If
   `books/{book}/film/shots/<scene>.json` exists and `--force` is absent,
   stop and say so in one line (offer `--force`).

2. **Study the craft.** Use `file_read` on `shared/craft/CAMERA.md` in
   full, and on `shared/craft/SCREEN.md` §3 (visual storytelling: what
   the scene must show without words). Read the book's genre guide (the
   file `_begin`'s `genre:` line names, `shared/craft/genres/<genre>.md` or
   the series' own `shared/genres/<genre>.md`): `## On screen`. Read
   `books/{book}/film/bible/look.yaml` in full: the format, camera height
   and movement rules, the lens set and stops, the palette for this time
   and place, the night or day lighting rules and what they forbid.

3. **Read the scene.** Use `bash` from the series root:

   ```
   autonovel mechanical scene-lines books/{book}/film/screenplay/seq_NN.fountain --scene <ID> --format markdown
   ```

   It prints every speech numbered `<ID>-L01…` and every action paragraph
   `<ID>-A01…` with an estimated screen time, the scene's length in eighths
   and its page time in seconds, and the scenes before and after. These IDs
   are the shot list's vocabulary. Then `file_read` the sequence file and
   read the scene itself, the scene before it and the scene after (how we
   come in and how we leave), and the scene's rows in
   `books/{book}/film/screenplay/seq_NN_adaptation.md` (what the scene must
   carry, its period facts, its first-minute note).

4. **Read the bible for everything in the scene.** For each person,
   animal, place and object the scene shows: the file in
   `books/{book}/film/bible/characters/` (identity lock, wardrobe for this
   scene, posture, how the book has them move), the place's file in
   `books/{book}/film/bible/locations/` (what stood at the date and what
   must not show, the light at this hour, the sounds) and the objects'
   entries in `books/{book}/film/bible/props.yaml` (their state in this
   scene). If the scene runs on from the one before (`CONTINUOUS`) and
   `books/{book}/film/shots/<previous>.json` exists, read its last shots:
   wardrobe, props, light and screen direction carry in.

5. **Design before writing a shot** (CAMERA.md §0, §2–§4). Write, for the
   shot list's top-level fields:
   a. `intent`: the scene's turn in one sentence, whose scene it is (the
      viewpoint), and the one moment the coverage builds to (CAMERA.md
      §2: the turn gets the shot sized to carry it).
   b. `geography`: where everyone and everything is, as a floor plan in
      words, and how it changes (who moves where).
   c. `axis`: the line: what it runs between (two people talking, or a
      traveller's path), and which side is `A` (the side most shots take).
   d. `coverage_plan`: how the scene is covered (the establishing view or
      master, then what is singled out, inserts of what the story turns
      on), and what is withheld and why.
   e. `cast_refs`: each person or animal on screen, mapped to their bible
      file (`bible/characters/<slug>.yaml`).

6. **Write the shots** with `file_write` to
   `books/{book}/film/shots/<ID>.json` (schema `autonovel-film-shots/1`,
   `scene_id`, `slugline`, `script`: the sequence file relative to
   `film/`, plus step 5's fields). For each shot, in screen order, ID
   `<ID>-NN`:
   - `coverage` (establishing, master, single, two-shot, group,
     over-shoulder, insert, cutaway, pov, reaction), `shot_size` (EWS, WS,
     FS, MS, MCU, CU, ECU), `angle` (eye, low, high, overhead; dutch only
     if the look allows it);
   - `camera`: `height_m`, `lens_mm` from the look's set, `t_stop` from its
     stops for the hour, `focus` (who or what), `fps` and `shutter_deg` from
     the look;
   - `move`: `type` (static, pan, tilt, push_in, pull_out, track, follow,
     drift, crane, …), `speed`, and its `motivation`: what in the scene the
     move answers to (CAMERA.md §3); `static` needs none;
   - `in_frame` (who and what is seen), `blocking` (each one's place and
     facing in the frame: "back to camera, frame left"), `action` (what
     happens in the shot, in the present tense), `purpose` (what the
     audience learns or feels from it);
   - `screen_direction` (left_to_right, right_to_left, toward, away,
     neutral, static) of the shot's `mover` (who it describes; leave it out
     for the scene's traveller) and `line_side` (`A`, `B` or `on_line`);
     `crossing` when the camera or a person carries the view across the
     line inside the shot; `eyeline` as `{who, looks, at}` with `looks` one
     of frame_left, frame_right, camera, up, down, neutral, off;
   - `light`: the sources that light this frame and where they are (in
     frame or just off it), from the look's rules for the hour;
   - `lines`: the line IDs heard in this shot (each line in exactly one
     shot: the one it is heard in); `beats`: the action paragraphs it shows;
     any paragraph left out goes in the top-level `omitted_beats` with the
     reason;
   - `continuity`: `wardrobe` per person (the same words every shot, from
     the bible's wardrobe for this scene), `props` with their state, `time`,
     `weather`, and `light` as the scene's light regime (the same words every
     shot: "moonless; lantern and candle flame only"); a change goes in
     `continuity_change` with its reason;
   - `timing`: `action_s` for what the action needs without words, and only
     where the shot is held for its own sake, `hold_s` with the reason in
     `purpose`. Leave `duration_s` to the check: it is computed from the
     lines and the action (CAMERA.md §6), never typed in.
   Keep the faces that must speak few, and show a speaker's mouth in a
   close shot only where the moment needs it (CAMERA.md §8: lip-sync is the
   costliest thing to render). Leave `render_hints` empty; the storyboard
   and render stages fill their own files.

7. **Check it.** Use `bash` from the series root:

   ```
   autonovel mechanical shot-check books/{book}/film/shots/<ID>.json --retime --stamp --sheet books/{book}/film/shots/<ID>.md --format markdown
   ```

   `--retime` writes each shot's duration from its lines (the table read's
   recordings when they exist and still match the script, estimates
   otherwise) and its action; `--stamp` records the fingerprints of the
   scene and the look, so a later script edit shows the shot list as out of
   date; `--sheet` writes the author's page. Fix every error and re-run
   until it exits 0. Read every warning and advisory: fix it, or say in the
   top-level `notes` why it stands (a scene that runs well past its page
   time is either padding or giving the action room the page didn't; say
   which).

8. **The director/DP critic, in rounds.** Use `task` to spawn a heavy-tier
   critic in a **fresh subagent** conversation that has not seen your
   reasoning. Give it the paths of `shared/craft/CAMERA.md` (§10 is its
   rubric), `books/{book}/film/bible/look.yaml`, the sequence file with the
   scene's ID (and the scene before and after), the bible files in
   `cast_refs` and the location's file, the shot list, the author's page and
   the latest `shot-check` report. Ask it to: score the ten dimensions of
   §10 from 1 to 10, each with the shots that justify it, worst first; run
   CT1–CT12 (pass, fail or n/a, one line of evidence each); list its notes
   ranked must-fix, should-fix and polish, each naming a shot and saying
   what to change; and write all of it under `## Round N` in
   `books/{book}/film/reviews/<ID>_shots_critic.md` (appending to earlier
   rounds). Then judge every note yourself: make each change that holds in
   the shot list; under the round write `### Response`, one line per note:
   done (what changed), or declined (why). Re-run step 7. The gate is
   CAMERA.md §10's: no dimension below 7 and every test passing or `n/a`
   with a reason. Until it passes, run another round with a new fresh
   critic, up to `--rounds`; a new critic also checks the last round's
   fixes in the shot list, not only the response lines.

9. **Report to the author**, in plain sentences (introduce every film
   term at first use: a "master" is the one shot that holds the whole
   action, the "line" is the imaginary line between two people that the
   camera stays on one side of, so left and right stay put on screen),
   worst news first:
   - the scene in one sentence and what the coverage builds to;
   - each shot in one line: what we see, how close, whether the camera
     moves and why, how long it runs;
   - the total against the scene's page time, and why it differs;
   - the critic's lowest scores first, what was changed, anything open;
   - the paths: the author's page (`shots/<ID>.md`), the JSON, the review.
   Then **Next:**
   1. Read `books/{book}/film/shots/<ID>.md` beside the scene.
   2. `/autonovel:storyboard --scene <ID> --book {book}` to draw a keyframe
      for every shot.
</workflow>

<acceptance>
- `books/{book}/film/shots/<ID>.json` exists and `autonovel mechanical
  shot-check` on it exits 0: every line of the scene is heard in a shot,
  every action paragraph is shown or its omission has a reason, every move
  has a motivation, the camera keeps its side of the line (or crosses it
  legitimately), eyelines meet, continuity carries shot to shot, every
  duration is computed, and the look's frame rate, lenses and forbidden
  moves are kept.
- The shot list is stamped with the scene's and the look's fingerprints.
- `books/{book}/film/shots/<ID>.md` reads as a plain shot list for the
  author.
- `books/{book}/film/reviews/<ID>_shots_critic.md` has at least one round
  with the ten scores, CT1–CT12 and a response line per note; the last
  round passes CAMERA.md §10's gate, or the report says plainly what is left.
- No script, scene list, bible or book file is written.
</acceptance>
