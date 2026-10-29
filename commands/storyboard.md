---
name: autonovel:storyboard
description: Draw one keyframe for every shot of a scene's shot list on a local image model (FLUX 3 Klein through ComfyUI), after first locking each principal's look with a character sheet (front, three-quarter, profile); a vision check in a fresh conversation reads every frame against its shot, the sheets and the period, and a failed frame is regenerated with a revised prompt at most twice before it goes to the author.
argument-hint: "--scene <ID> --book <short-name> [--url <comfyui-url>] [--ram-limit <GB>] [--force]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
  - task
reads:
  - shared/craft/CAMERA.md
  - books/{book}/film/shots/*.json
  - books/{book}/film/bible/look.yaml
  - books/{book}/film/bible/characters/*.yaml
  - books/{book}/film/bible/locations/*.yaml
  - books/{book}/film/bible/props.yaml
  - books/{book}/film/bible/sheets/*.json
  - books/{book}/film/storyboard/*.json
writes:
  - books/{book}/film/bible/sheets/*.json
  - books/{book}/film/bible/sheets/*/*.png
  - books/{book}/film/storyboard/*.json
  - books/{book}/film/storyboard/*/*.png
  - books/{book}/film/reviews/*_storyboard_vision.md
context_mode: book
---

<purpose>
Draw the shot list: stage F4's storyboard (`docs/film-pipeline-plan.md`,
milestone M4). One still per shot, made on the user's own GPU by a free
local image model, so the author can see the scene's look and staging
before anything costly is rendered, and the animatic can time it.

It writes, under `books/{book}/film/`:

- `bible/sheets/<slug>.json` and `bible/sheets/<slug>/{front,three_quarter,profile}.png`
  for each person (and animal) the scene's frames must hold steady: the
  character sheet every frame of them is conditioned on. A sheet stays
  `approved: false` until the author approves it.
- `storyboard/<scene>.json`: the frame manifest: each shot's prompt, its
  reference images, seed, takes, select and the vision check's verdicts.
- `storyboard/<scene>/<shot>.png`: the select for each shot (takes are kept
  in `storyboard/<scene>/takes/` and never overwritten).
- `reviews/<scene>_storyboard_vision.md`: the vision check, pass by pass.

The local backend is a ComfyUI server running FLUX 3 Image Klein (its
licence, FLUX Kommunity, allows non-commercial use freely and commercial use
of outputs under US$5M revenue with disclosure; the manifest records it).
No paid or keyed service is used.

`--url`: the ComfyUI server (default `$AUTONOVEL_COMFY_URL`, else
`http://127.0.0.1:8188`). `--ram-limit <GB>`: stop a job when system RAM in
use passes this (default 24). `--force`: write a new manifest over an
existing one (its takes stay on disk).
</purpose>

<workflow>
**Read-failure policy.** `books/{book}/film/shots/<ID>.json`,
`shared/craft/CAMERA.md` and `books/{book}/film/bible/look.yaml` are
load-bearing: stop if any is missing (`/autonovel:shot-list --scene <ID>`
makes the first; `autonovel refresh-templates` restores CAMERA.md). The
bible's character, location and props files are best-effort: a frame with
no bible file for someone in it is drawn from the shot list alone, and the
report says so. Do not retry a failed `file_read`.

1. **Parse `$ARGUMENTS`** and check the shot list is current. Use `bash`
   from the series root:

   ```
   autonovel mechanical shot-check books/{book}/film/shots/<ID>.json --format markdown
   ```

   Stop if it reports errors or says the scene or the look changed since
   the shot list was made: the storyboard draws the shot list, so the shot
   list comes first. If `books/{book}/film/storyboard/<ID>.json` exists and
   `--force` is absent, skip to step 6 with the frames still pending or
   marked `regenerate`.

2. **Study.** Use `file_read` on `shared/craft/CAMERA.md` §7 (light), §8
   (prompts) and §9 (the vision check); on
   `books/{book}/film/bible/look.yaml` (the palette for this place and hour,
   the night or day lighting rules, texture, the prompt suffixes); on each
   file the shot list's `cast_refs` and `locations` name in
   `books/{book}/film/bible/characters/` and
   `books/{book}/film/bible/locations/`; and on the entries of
   `books/{book}/film/bible/props.yaml` for the objects in the shots.
   Rewrite every negation you find there ("no street lamps", "not the stone
   bridge") as what is there instead ("the only light is the lantern at the
   bow", "a humped timber bridge on timber piers"): the image model has no
   negative prompt and draws what a prompt names (CAMERA.md §8.1). The
   bible's lists of what must not show are for step 7's check.

3. **The server.** The ComfyUI server must be running on one free GPU,
   started under WSL with `--disable-pinned-memory`, with nothing else on
   that card. One GPU job at a time: check no other render (voices, video,
   another server) is running on it before you start. `keyframe-render`
   asks the server to unload its models when each batch ends; stop the
   server when the storyboard is done.

4. **Character sheets first** (CAMERA.md §8.4). For each person or animal
   in the shots' `in_frame` who has a bible file and appears in two shots or
   more, or whose face is seen: if `books/{book}/film/bible/sheets/<slug>.json`
   is missing, write it with `file_write` (schema `autonovel-film-frames/1`,
   `kind: sheet`, `subject`, `bible`, `wardrobe` (the bible's wardrobe for
   this scene), `approved: false`, `size` [1024, 1280]) with frames
   `front` (no references: the bible's prompt core and identity lock in
   full, the scene's wardrobe, a plain backdrop and soft daylight, knees-up),
   then `three_quarter` and `profile` (and `back` when the shots show the
   person from behind), each referencing
   `bible/sheets/<slug>/front.png` and naming everything that must stay the
   same. An animal gets `side` and `three_quarter`. Render:

   ```
   autonovel mechanical keyframe-render books/{book}/film/bible/sheets/<slug>.json --ram-limit <GB>
   ```

   and run step 7's check on the sheet (one person in every view; dressed
   for the date) before any storyboard frame is drawn from it. A sheet the
   author has not approved is still used; the report says so.

5. **Write the frames** with `file_write` to
   `books/{book}/film/storyboard/<ID>.json` (schema `autonovel-film-frames/1`,
   `kind: storyboard`, `scene_id`, `shots_sha`: the shot list's
   fingerprint from `shot-check`'s report, `size` [1280, 720] or the look's
   generation size). One frame per shot, its `id` the shot's ID, in shot
   order, each with:
   - `prompt`: one paragraph, positive only (CAMERA.md §8): the shot's
     key instant (`action`), its size, angle, lens and depth of field,
     where each person in `in_frame` stands and faces (`blocking`), the
     light's sources, side and fall-off (`light`, the look's rules), the
     palette for the hour, the place as it stood at the date (the
     location's file), each person's identity lock and the scene's
     wardrobe in words, and the look's film texture;
   - `refs`: the sheet views of the people whose identity the frame must
     hold (at most three; the view nearest the shot: `back` for a back to
     camera, `profile` for a profile, else `three_quarter`), as paths
     under `film/`;
   - `seed` (any fixed number) and `status: pending`.

6. **Render** with `bash`:

   ```
   autonovel mechanical keyframe-render books/{book}/film/storyboard/<ID>.json --ram-limit <GB>
   ```

   It renders every pending or `regenerate` frame, writes each take to
   `storyboard/<ID>/takes/` and the select to `storyboard/<ID>/<shot>.png`,
   saves the manifest after every frame and frees the server's models at
   the end. Exit 3 means it stopped at the RAM limit: stop and tell the
   author rather than retrying.

7. **The vision check.** Use `task` to spawn a vision judge in a **fresh
   subagent** conversation that has not seen your prompts' reasoning. Give
   it CAMERA.md §9, the shot list, the bible files and the location's
   not-at-this-date list, the look's night or day rules, the sheets'
   images, and every frame rendered in this pass (the select paths). Ask it
   to open each image and answer §9's four questions (spec, identity,
   period, artefacts) with what it sees, then give a verdict, `keep` or
   `regenerate` with a revised positive prompt, or `author` when the model
   plainly cannot draw what the shot asks; and to write it all under
   `## Pass N` in `books/{book}/film/reviews/<ID>_storyboard_vision.md`.
   Then look at every frame yourself and judge the judge: record each
   verdict with

   ```
   autonovel mechanical keyframe-verdict books/{book}/film/storyboard/<ID>.json --frame <shot> --verdict keep|regenerate|author --note "<what was seen>" [--prompt-file <revised prompt>] [--seed <n>]
   ```

   and write under the pass `### Response`, one line per frame: the
   verdict recorded, and where you overruled the judge, why.

8. **Regenerate** the frames marked `regenerate` (step 6 again), then
   check the new takes (step 7, a new fresh judge). A frame is regenerated
   at most twice (`keyframe-verdict` turns a third `regenerate` into
   `author`); it then goes to the author with the reason, and the best take
   so far stays its select.

9. **Done when every frame has a verdict.** Use `bash`:

   ```
   autonovel mechanical keyframe-status books/{book}/film/storyboard/<ID>.json --format markdown
   ```

   Every frame is `keep` or `author`. Stop the ComfyUI server if no other
   storyboard is about to run.

10. **Report to the author**, in plain sentences, worst news first:
    - each frame in one line: what it shows, and how good it is honestly
      (what the model got wrong as well as right);
    - what the vision check caught and what was regenerated, and every
      frame marked for the author, with the reason;
    - the sheets made, and that they await the author's approval;
    - GPU time (the manifest's `render_log`) and the highest RAM seen;
    - the paths: the frames folder, the manifest, the review.
    Then **Next:**
    1. Look through `books/{book}/film/storyboard/<ID>/` beside the shot
       list's page (`books/{book}/film/shots/<ID>.md`).
    2. `/autonovel:table-read --scene <ID> --book {book}` to voice the
       lines, then `/autonovel:animatic --scene <ID> --book {book}`.
</workflow>

<acceptance>
- `books/{book}/film/storyboard/<ID>.json` has one frame per shot of the
  scene's shot list, each with a positive prompt, its references and a
  select image, and `keyframe-status` shows every frame `keep` or `author`.
- Every principal seen in two shots or more has a sheet in
  `books/{book}/film/bible/sheets/`, and the frames of them reference it.
- `books/{book}/film/reviews/<ID>_storyboard_vision.md` has a pass for every
  render, with the four questions answered per frame and a response line
  per frame; no frame was regenerated more than twice.
- No paid or keyed service was called; the ComfyUI server's models were
  freed after each batch.
- No script, shot list, bible text or book file is written (the sheets'
  manifests and images are the only bible files this command adds).
</acceptance>
