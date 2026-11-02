# Film pipeline: sets in 3D, the look from AI

> **Status:** recommendation for the author, 2026-10-30, after the first
> moving minute of kingmaker2 (`docs/film-pipeline-plan.md` M5 pilot). Research
> by three agents on 2026-10-30, with sources below; prices, licences and
> versions move monthly. Nothing is built yet.
>
> **Paused, 2026-11-02**, after round 8c: the 3D sets held the places and props, but no round
> was better than version 1, because the people drift and don't act. The post-mortem is
> [`film-postmortem.md`](film-postmortem.md).

## The problem

Version 1 of the first minute was drawn shot by shot as 2D images (FLUX 3
Klein) and animated by image-to-video (Wan 2.2). The author's sixteen notes
and the vision judge's findings are almost all one fault: **nothing persists
between shots.** A lantern changes design, one oar becomes two, the carter
leaves the barge, the water-gate changes shape and grows a basin behind it, a
leash appears, a tout ends up in the wrong boat, the bridge is drawn along the
canal, a moving camera invents what it reveals, and the light changes from
shot to shot. More rules, more takes and better prompts reduce these faults
but never end them, because each frame is invented afresh. That is the
author's point: the method doesn't converge.

A 3D set ends that class of fault by construction. The gate, the barge, the
lanterns and the people's marks are the same objects in every shot, and any
camera angle is free.

## Three ways to use 3D

**1. Full CG in Unreal Engine 5.8.** Build everything in 3D and render
the final frames in the engine: MetaHuman characters, Sequencer cameras, and
MegaLights so every lantern is a real light. It is free under $1M of
revenue, MetaHuman Animator drives faces from a webcam or from audio, and
Unreal 5.8 has an official MCP server through which Claude can drive the
editor. Its weaknesses for this film:
- faces in close-up read as a game cinematic rather than live action;
- MetaHuman has no fourteen-year-old;
- period costume has to be built in a cloth tool;
- the dog has to be animated by hand;
- it runs on Windows only, apart from the rest of the stack;
- for an expert, the first set takes weeks.

**2. Hybrid: the 3D set fixes layout, camera and light positions; AI
makes the photoreal look.** Build the location coarsely but exactly in
Blender, with props made once. Block the people as mannequins and put a
camera in the set for every shot. Then render passes from each camera: a lit
pass with the lanterns as real lights, depth, and line art. FLUX 3 Klein
draws the keyframe from the lit pass and the character sheets. A
depth-and-line-controlled video model (Wan2.2-VACE-Fun-A14B, Apache-2.0,
which fits 16 GB as a GGUF with block swap) animates it. Because the set
exists, a moving camera reveals real geometry instead of inventing it. For a
locked-off shot, the plate is kept and only the water, flames and figures are
regenerated (VACE masks). Its weaknesses:
- light and surface continuity still depend on reusing the same reference
  images;
- thin things (the gate's bars) sit below the model's 16-pixel grain, so
  frame them larger or composite the real 3D gate;
- faces in close-up stay the weakest link.

**3. AI-made worlds (Gaussian splats).** World Labs Marble, Tencent
HY-World 2.0 and Google Genie generate explorable scenes. **Not for this
film:** a splat carries the light it was made with and can't be relit for a
lantern-lit night, close range shows holes, and HY-World's panorama model is
far beyond 16 GB.

## What already exists (research, 2026-10-30)

No single product solves continuity across shots. The practice that has
settled in 2025–26 among AI filmmakers splits the problem in three. A rough 3D
set, or locked reference plates per location, holds where things are.
Reference images or a trained LoRA hold the people. The video model only
moves a first frame that is already right. The pure-AI platforms hold faces
better than geography; one creator's phrase for what they lack is "No set. No
there there."

The established pieces to use, not rebuild:
- **Blockout** (free, Apache-2.0, a Windows desktop app, early) is the
  staging tool this plan would otherwise have to build. It does grey-box sets
  with real sensors, focal lengths and camera moves, plus 194 character
  motions and marks. For every shot it exports a motion-reference video, a
  depth pass, first and last frames, a top-down diagram and a ComfyUI
  workflow for Wan 2.2. It hands scenes to Blender and is driven over MCP.
  Its kits are modern places, so the period set comes from Blender.
  https://github.com/wassermanproductions/blockout
- **Intangible** is the closest finished product: a browser studio where you
  build a 3D set, place the cast and cameras, and render through Luma, Kling
  or Seedance ("continuity held by the camera"). It costs $25–35 a month for
  about 40 s of video, and is cloud only. https://www.intangible.ai/enterprise/film
- **Kling 3.0 Omni** keeps characters and objects as "elements" and does a
  storyboard of up to 6 cuts, from $10 a month (about 110 s of 720p).
- **OpenArt** resells other companies' models (Kling 3.0 and Omni, Veo,
  Seedance and more) for credits, with "Characters" built from one to four
  pictures and reused across them; about $13–175 a month after an August
  2026 repricing, video costing many more credits than pictures. It is a
  painter like Kling through fal, not a set: it knows neither where the
  boat is nor how many people stand on it.
- **Genie 4** (Google DeepMind, research preview 27 October 2026, trusted
  testers only; Project Genie on the $100–200 a month AI Ultra plan and the
  Gemini API "coming soon") is a world you walk through in real time, not a
  set you direct. You steer the camera with the keyboard and change the scene
  by typed prompts; a world holds together for about two minutes before
  objects drift; it can start from a picture. Nothing published offers an
  exact camera position or lens, people on marks, a fixed head count, the
  same face from one session to the next, a return to the same world, or an
  export of depth or geometry, and Google says real places can't be
  simulated accurately. At most a scouting toy for looks and angles.
- **Award practice:** Runway's AI Film Festival winners and the best-known
  creators lock a few reference plates per location and curate heavily; the
  ones who need spatial continuity start from a primitive Blender set
  (Flick's *Ser Loras*). Mickmumpitz's published workflow renders Blender
  depth and outline passes through ComfyUI into Wan VACE.
- **A risk for this film on hosted services:** developers report Google's
  Veo refusing reference images of a fictional 17-year-old, and Adobe
  Firefly blocks child keyframes. A 14-year-old lead is safest on the local
  stack.

## Recommendation: the hybrid, with Blockout for staging and Blender for the set

The hybrid fixes exactly what failed (layout, continuity, camera, reveals)
and keeps what worked (photoreal surfaces, the stack already installed and
measured). Full CG would trade the continuity faults for a game look on every
face, plus weeks of costume and animation work. Splats can't be relit.

**Blender rather than Unreal for the set,** for these reasons:
- It runs in the same Linux environment as the rest of the tools, or as
  `blender.exe` called from WSL; check this in the pilot.
- It scripts headless through `bpy`, so a set is a checked-in Python file a
  person can rerun: the human-runnable rule.
- It renders every pass the control models want (depth, normals, Freestyle
  line art, object masks, an EEVEE lit pass).
- It is free with no revenue limit, and Cycles can use both cards.
- Unreal stays the option for a full-CG shot later.

### The new stages (each one a command, as the rest of the pipeline is)

1. **Set** (`/autonovel:set <location>`). From the bible's location file and
   measured plans (canal widths, the bridge's span, the gate's size), an
   agent writes `film/sets/<location>.py`. The script builds the place from a
   small kit:
   - six to eight hand-made Venetian Gothic facade modules (ogee windows,
     string courses, funnel chimneys, water-doors), repeated by geometry
     nodes;
   - props made once, by TRELLIS.2 (MIT, local) from a cleaned reference
     image or bought, which replaces the prop sheets: the barge with its bales
     and one pole, the bow lantern, the touts' boats, the water-gate, the inn
     steps, mooring posts, washing lines and rubbish;
   - lanterns as real point lights;
   - a night-life layer (lit windows, figures on the quays).

   It renders a top view and a few angles, and a vision check reads them
   against the location file and the book. **Is the geography right?** What
   crosses what, where the turn is, which bank the house stands on. The author
   approves the set from those renders, as they approved the sheets.
2. **Blocking** (part of `shot-list`). Every shot gets a camera in the set
   (lens, height, path) and marks for each person and the dog as mannequins,
   with a move the 3D path defines exactly. A **layout animatic** of grey
   renders, timed to the table read, is the cheap check: the author sees
   the real geography and staging before any AI frame is drawn. The neighbour
   continuity check becomes geometric: three people in the barge, one tout per
   boat.
3. **Keyframes** (`storyboard`). FLUX 3 Klein draws from each camera's lit
   pass plus the character sheets and character LoRAs (trained once per
   principal on the 16 GB card), drawn at the start of the action.
4. **Motion** (`shot-render`, folding in today's `shot_render.py`).
   Wan2.2-VACE-Fun-A14B gets the keyframe as its start frame and the set's
   depth and line passes as control. A locked-off shot regenerates only
   masked regions. People acting are animated by Wan-Animate-2 driven from
   mannequin or library motion. Faces in close-up use the keyframe with the
   LoRA, image-to-video, and InfiniteTalk lip-sync.
5. **Cut** as now, from picks, with the neighbour check before the author
   sees it.

## Pilot before committing

Stage in **Blockout** first (free, and its exports already target Wan 2.2), with the period set built in Blender and brought in. Optionally, run the same shots through **Intangible** for one month ($25–35) as the finished-product benchmark; the author would open the account, and the 14-year-old must pass its providers' filters.


Rebuild **one location**: the side canal by the Germans' house, the
water-gate and the inn steps, which covers shots S0104-07 to S0105-04. Then
render those shots both ways and compare them against the author's sixteen
notes. The pilot must show, before the method is adopted:
- an agent-written Blender set whose renders a vision check and the author
  accept;
- Blender's passes rendered from WSL on this machine;
- Wan2.2-VACE-Fun-A14B with depth and line control at 480p, then 720p, on the
  5060 Ti, holding the gate, the barge and its three people across a camera
  move;
- a locked-off shot that stays locked;
- the gate's bars intact, or composited.

The research's effort estimates are for a human expert: about 4–5 weeks for
the first set. Most of that becomes agent time here, with the author's
approvals at the set and the layout animatic. The estimate after the sets
exist is 2–4 days per finished minute, mostly machine time. Those are
estimates, not measurements; the pilot measures them.

## Pilot results (2026-10-30)

The author said to run the pilot locally with Blockout and Blender. It ran the
same day on this machine, all inside WSL, and nothing was installed or changed
on Windows. The scripts are in `~/film-stack/scripts`, and the series holds the set,
the staging, the prompts and the keyframes.

**What was built, stage by stage:**
1. **Set.** `film/sets/fondaco-side-canal.py` is one Blender script, using a
   small kit (`setkit.py`: boxes, arched openings with stone surrounds, hipped
   roofs, funnel chimneys, water, stairs, horn lanterns as real lights, boats,
   stand-in figures). It builds the side canal, the Germans' house round two
   courtyards, the water-gate, the inn steps, the wooden bridge and both banks
   in about 15 seconds. A fresh vision reviewer checked the renders against the
   book and the location files. The geography held: the turn left 42 m short
   of the bridge, the house on the corner, the inn next door. The reviewer's
   faults were fixed: the water now runs in under the gate's arch, the grille
   has two leaves with a chain and padlock, the turn has markers, and there are
   people, washing, rubbish and dimmer candle-lit windows.
2. **Staging.** `staging.json` gives each shot's cast, marks and camera in the
   set's own metres. `blockout_stage.mjs` drives the real Blockout app through
   Playwright and exports Blockout's Blender handoff per shot. Blockout's
   handoff carried only each figure's path, so a small patch (recorded in its
   `MODIFICATIONS.md`) now bakes limb motion and riders too. Blockout has no
   period assets and cannot show a custom set (only scans), so its role is the
   figures, their gaits and the camera; the set is seen in Blender.
3. **Guides.** `shot_layout.py` opens the set, imports the shot and replaces the
   stand-in boat with the set's barge. It renders 81 frames at 16 fps of a lit
   pass (the set's own lanterns and windows, figures in costume colours), an
   inverse-depth pass and a normal pass. `layout_lines.py` adds outlines and
   videos. Two fixes made it fast enough: merging the set's thousands of
   objects into one per collection, and keeping render data between frames
   (0.6 s per frame per pass, from 12 s).
4. **Keyframes.** `keyframe_from_layout.py` runs FLUX 3 Klein as an
   image-to-image pass (denoise 0.75–0.78) over the lit first frame, with the
   character sheets as references. Each take took 33–63 s.
5. **Motion.** `vace_render.py` runs Wan2.2-VACE-Fun-A14B (Q5_K_M GGUF) with
   the Wan 2.2 T2V Lightning 4-step LoRAs. The control video is the keyframe
   as frame 0, kept, then the depth frames, generated. One 81-frame take at
   832×480 took 240–310 s on the 5060 Ti, with system RAM peaking at 22.6 GB.

**What it showed (first takes, 480p):**
- **Continuity holds.** The gate, its bars, the barred window above it, the
  Germans' house and its lit windows, the steps, the door and the lantern stay
  the same through every frame of every shot, including a camera push-in and a
  barge turning across the frame. That is what version 1 could not do.
- **People follow the staging.** The carter turns and climbs the steps, Jakob
  follows, the boatman waits with the bags, the dog holds the landing, and
  Jakob's head lifts to the bars.
- **The staged pose must match the keyframe.** In S0104-09 the painted
  keyframe pressed Jakob's hand to his coat, but the stand-in's arm hung at
  his side, and the hand dropped to follow the depth. Klein likewise painted
  the stand-in's raised arm when the pose was wrong. Pose the stand-ins as the
  shot needs and check them before painting.
- **Use depth control, not outline control.** Outline control alone turned
  the gate shot into a flat cartoon.
- **Joint signs:** in Blockout's figures a positive `headX` tilts the face up.
- **Shot angles are found in the set.** Reframing in the set took minutes and
  exposed what a written shot list cannot know. For example, a face looking
  at the gate can only be seen from between the face and the wall.

**The author's first notes on the pilot** (the series'
`film/reviews/author_notes_pilot3d.md`):
- The barge started too close to a building.
- The house's lit windows all looked alike, each with a figure in it.
- The water was too still and clean.
- The whole place was too pristine.

So a set is never new. The set kit now has an age-and-dirt layer that every
location script should call:
- a weed band and tide stain along every wall standing in water;
- streaks, rust, missing bricks and fallen plaster;
- worn and broken steps;
- scum, floating rubbish and rubbish heaps;
- laundry where people live.

The water's ripples move with the frame. Repeated windows vary their light, and
no prompt puts a figure in every window. Every keyframe prompt carries a
"worn and dirty" clause.

**The author's second notes, and what round 3 changed:**
- *The boat looked motorised and never turned.* A shot's subject decides the
  angle: a turn is shown from across the water, square to the side canal's
  mouth, the boat on a smooth curve at a walking pace with its oar sweeping
  (`shot_layout.py --row`). Boats are modelled as boats: an open hull with
  freeboard and separate bales, not a raft with one block of cargo, which
  the image model paints as a floating platform of crates.
- *The water-gate read as open water.* What lies behind an opening is built
  and lit (here an unloading room with goods, a hoist and a lamp), or the
  painter fills the dark with whatever it likes.
- *The people changed between shots.* The image model invents costumes it is
  not given. Each shot names the wardrobe scene every person wears, and their
  words come from the character bible, the prompt_core then
  `wardrobe.by_scene[scene]` (`film_prompt.py`). Clothes change through a
  film, so the costume belongs to the bible's scene, never to the shot.
  Props seen in several shots (the barge) have one shared description.
- *The lights were steady.* The video model paints flame as steady lamps, so
  a pass after it (`flicker.py`) gives each region of the frame its own flame
  rhythm, with about four lights in ten nearly steady.
- *Found on the way:* Blockout's notes give its arm sign the wrong way round: in the exported
  figure a negative shoulder angle raises the arm toward the back. Misreading that, the
  pilot once "turned standing people round", which made them face the opposite way from
  walkers and sent a rigged model up the inn steps backwards. Standing and walking figures
  share one yaw (checked against walkers' roots in the export). A pose is checked by reading
  the exported limb positions, and a rigged model by looking at it moving, not by eye in a
  render of round-headed stand-ins. An arm the painter is to read must be on the camera's side.
- *People are 3D models.* The author: "why don't they use already decided 3D models,
  including hats?" Each person in each costume is a model made from the approved character
  sheet (TRELLIS.2, native in ComfyUI; `character_model.py`), frozen with a turnaround in the
  film's `assets/register.yaml` (`asset.py`), approved by the author, then rigged to Blockout's
  figure (`rig_character.py`) so the staging moves it at the person's own height. Every
  recurring model (sets, the barge, people) is used only in the version the author approved;
  an improvement is a new version shown before and after.

**Round 4, the night of 30 October: approved models only, and the whole first minute.**
The author approved the barge (v3) and a 3D model of each person in their arrival costume, then
asked for the 19 seconds again and the minute after it, overnight, without them. What changed:
- *Sets load approved files.* `setkit.approved_asset` places the register's approved version
  (`asset.py path <name>`) at its home in the set; the kit's builder code is used only to freeze
  a new version. The side-canal set and a new lagoon set (`film/sets/lagoon.py`: open water, the
  channel's bricole, Venice as a low line of lights) both load barge v3 this way.
- *Animals are rigged too.* `rig_character.py` builds a dog's bones on Blockout's `animal.dog`
  (a body bone on the figure's own root, the legs, neck, head and tail) and fits the model by
  its feet, not its height (`asset.py rig <name> --figure dog`).
- *New things are proposals, flagged.* A thing first needed by a new shot (the touts' skiffs) is
  frozen as a proposed version and loaded onto Blockout's stand-in (`"model"` on the staging's
  cast entry); the cut's notes name it for the author's approval. A recurring thing the author
  has approved is never replaced by a proposal.
- *Riders keep seats.* Each person on the barge has one fixed place in every shot (Jakob at the
  bow, the carter on the cargo's front edge to port of the mast, the boatman at the stern), so a
  cut never moves them. Over-the-shoulder cameras are placed by measuring angles to the mast,
  which otherwise fills the frame.
- *Joint signs in the export, measured:* shoulder X positive brings the arm forward; shoulder Z
  positive brings it in toward the body; a negative elbow folds the forearm forward; hips and
  knees at +1.5 seat a figure. Blockout drops the "sit" gait for a figure riding a boat, so a
  seated rider is posed with those joints.
- *Blockout's elbow is a hinge with no twist,* so a forearm across the chest cannot be posed. A
  hand on the chest seen edge-on reads to the image model as a reach (it painted a hand on the
  wall, praying hands, a raised palm). Check a gesture from the shot's own camera, and say in
  the prompt what the hands do not do; with that, the close-up's keyframe put the hand flat high
  on the coat.
- *Character sheets can multiply people.* With the layout carrying the real models, the sheet of
  someone seen from behind made the image model add a second, front-facing copy of him on the
  steps. Give only the sheets of faces the camera sees, and paint over a layout that carries the
  models more lightly (denoise 0.65 rather than 0.75).
- *A keyframe prompt describes frame 0, not the shot's key moment.* The inn shot's prompt
  described the innkeeper already holding the dog; at frame 0 he is still in the doorway, so the
  image model painted him twice (and a second dog). The motion prompt carries what happens next.
- *What the image model may read wrongly from an angle:* a mastiff's ears seen from above and
  behind read as a cap, and every take put a hat on the dog; the cure was a side-on angle, not
  more words. A thin oar 30 m off barely shows in the depth guide, and a burchio's two blunt ends
  look alike from above, so the video model can row from either end.
- *The depth guide must stay at full strength.* At half strength the close-up drifted away from
  its keyframe entirely (a tartan coat, bright light, new railings).
- *A boat's own lantern blocks shots from its deck.* Cameras on the barge looking at the inn
  steps put the bow lantern in front of the climbers; such shots are framed so the lantern sits
  low at one side, or taken from the water beside the barge.
- *720p costs three times 480p:* at 1280×720 the VACE experts' activations fill the 16 GB card
  and the 14B weights stream from system RAM, about 14 minutes a take against 5; SeedVR2 7B to
  1080p and RIFE to 32 fps add about 8 minutes a shot.

**Still to do before adoption:** several takes per shot with a vision pick; the S0105 inn
sequence re-staged to the author's beat order (notes 1 and 3); models for the touts and the
author's approval of their skiff; a cold viewer and the author's verdict; then fold the scripts
into autonovel commands (`set`, blocking in `shot-list`, the keyframe and motion stages).

## The author on round 4, and the tools reconsidered (2026-10-31)

The author on the minute: "pretty bad". Three rowers in the opening, the touts' boats crashing,
the Fondaco and the bridge changing between shots, "aren't these 3D models and static?", the
people wrong, washing out at night, the streets empty; and above all: "I am the one finding these
issues - the system should be finding almost all of them".

**Why it happened.** The picture was never a render of the 3D. The image model painted each first
frame over a near-black night render, and the video model invented whatever the depth guide did
not pin down (anything beyond about 40 m, anything the camera turned onto). The touts' crash was
in the staging itself: nothing checked it.

**Rendering from the set** (`vace_render.py --init`: the video model starts from the set's own
frames and only repaints): everything stays as built (one oar, the same house through the turn),
but it looks like a plain 3D model, and a painted first frame does not carry through (by the
third frame the look is the set's again). Photographed CC0 surfaces (`fetch_textures.py`,
`setkit.dress_surfaces`, set once per material name), haze and depth of field help, not enough.

**Automatic in the tools now:** `blockout_stage.mjs` refuses to stage or export while two boats
come within 1 m (`staging_check.py`); surfaces are set once per material name for every set.

**The critic, measured.** `critic_packet.py` gives a cold reviewer per shot a 12-frame strip,
every staged person and boat cropped at full size (`shot_layout.py --passes boxes`,
`figure_sheet.py`) and what the shot must show (staging, counts, the bible's people in this
scene's dress, props, the look bible's rules, the screenplay's period notes). On round 4's
minute it found 6 of the author's 7 faults unseen, and 50 more; the miss was our own
instruction (the night style asked for washing). The author's notes are kept as its answer key
(`film/reviews/critic_benchmark.yaml`); no round goes to the author before it has run and its
high findings are fixed.

**Unreal reconsidered** (research 2026-10-31): it would hold every building and person (one
scene), with real face rigs and many lanterns (MegaLights). But MetaHuman still has no
14-year-old (paid teen MetaHumans on Fab, Daz Genesis 9 teens or Reallusion child morphs
instead); keyframed boats ignore collision there too; our TRELLIS figures import with a body rig
(AccuRIG, Mixamo) but no face, and Mesh to MetaHuman would swap their faces for MetaHuman
look-alikes; the wooden Rialto, 1473 boats, period costume (a cloth tool) and a cinematic
mastiff are not to be had; it runs on Windows, not in WSL (no GPU Vulkan); Megascans are no
longer free; estimate 6–10 weeks of part-time hand work. Not recommended now.

**The missing piece, new in 2026:** "render-to-real" adapters for the open LTX video model
(22B, community licence free under $10M revenue): fal's **3DREAL** IC-LoRA for LTX-2.3
(June 2026; light and strong) and Lightricks' **Layout-to-Render** IC-LoRA for LTX-2.5 (October
2026; gated licence click), which take a grey or plain 3D render for camera and object placement
and a painted first (and optional mid and last) frame for the look. That is exactly the failure
above. Risks: 16 GB VRAM (community Q4_K_M GGUFs of 13.6 GB; one 12 GB user saw 45 GB of system
RAM), and users report Layout-to-Render's reference taking hold only near the end of a clip.
Next: test both on S0104-06 and S0104-01 from the existing set renders. Hosted alternatives
(Runway Aleph 2, Luma Ray3 Modify) may refuse a 14-year-old; Sora 2 is discontinued; Google's
Flow model does not take images of minors in the UK and EEA.

## Round 5: rendered from the set with LTX, and what the critic and the author found (2026-10-31)

**The method.** Each shot is rendered from the Blender set at 24 fps (`shot_layout.py --fps 24
--surfaces 1 --film 1`, with the boxes pass). Its first frame is painted over that render with the
shot's reference sheets (`keyframe_from_layout.py`). LTX-2.3 with fal's 3DREAL IC-LoRA then
renders the shot, holding the set render as its guide and the painted frame as its look
(`ltx_render.py --ref ... --match-ref`). Geometry now holds through every shot: one oar, the same
house and bridge, the passers-by where they are staged. Without the painted frame, LTX only
copies the plain render.

**The first pass.** The cold critic found 10 high faults, 15 medium and 17 low. The author's
notes added six, and the critic had missed two of them:
- **The carter looked small** (missed). His approved height was 1.70 m beside Jakob's 1.64 m.
- **Round 4 had "a nicer feel, with debris and activity"** (missed): "I don't like it when we
  regress rather than improving everything". The packet had no frames of the previous round to
  compare with.

Each fault was traced to a general cause, and the fix went into the tools, not the shot:
- **Boats face their path.** The staging tool turns every moving thing to face where it's going.
  A barge staged to drift sideways swung 90°, carrying the seated carter into frame standing.
  Straight legs meeting at a mark turned a barge 17–22° in one frame. `staging_check.py` now
  fails a sideways leg (over 30°) and a corner at a mark (over 10°). Turns are staged as one leg
  bent through `via` points, which `blockout_stage.mjs` passes to Blockout as a Catmull-Rom
  curve.
- **Nobody rowed.** `--row` swept the oar of the set's own moored barge, which is hidden whenever
  the approved barge model is in the shot. The boatman is now staged at the approved barge's
  oar, with his hand on its loom; the pose is measured in Blender before rendering. In the
  export, joint signs run opposite to Blockout's own notes for hips and shoulders, and a rider's
  mark heading is not to be trusted.
- **Grime floated in the air.** Wall-grime decals were placed across openings, so two slabs of
  brick hung over the water-gate. `setkit.stains` and `damage` now take `skip` spans.
- **The quay was hidden.** The waterline band stood 1.3 m above the edge of the Fondaco's quay.
  `waterline(cap=...)` stops it at the quay's top.
- **A grey stand-in read as "a white person".** A moored ferry with an unstaged grey ferryman
  read as "a sunk boat with a white person". Sets hold no standing figures; people are staged,
  with approved models.
- **The water was a mirror.** The ripples were sized to the water plane, so on the 500 m Grand
  Canal they were 55 m across. They are now sized in metres: a faint chop over a swell. A strong
  chop seen from afar shatters every reflection into dark noise. Moving boats get a V-shaped wake
  with foam.
- **The lantern read as a garden light.** The approved barge (v3) carries an older plain horn
  tube, and at the render's exposure it bleached to cold white. Its glow is now dim, deep amber
  at render time. Fitting the new lantern needs a new barge version, for the author to approve.
- **The dog changed colour.** Firelight on the black approved dog was painted as brown fur, then
  turned black a second into the shot. `shot_layout.py --passes matte` and `fix_figure.py` put
  the painted dog back to its model's colour inside its outline.
- **The bible described actions, not looks.** The boatman's look said "carrying travel bags",
  and the carter's dress said "sitting on the bales". Both were written into every shot's prompt.
  A look describes the person; what they do is staged per shot.
- **The light had been pushed too dark.** After the critic's "dusk, not night" the light went
  darker, and the author preferred round 4's warmth. The starlight stays at 8, and the warmth
  comes from motivated light: lanterns at the Fondaco's land gate, with goods and porters on
  its quay.
- **The critic's packet now:**
  - counts only who is in frame;
  - gives each person's approved height;
  - lists what each person carries;
  - shows the previous round's cut beside this one for every shot (`<shot>_vs_previous.jpg`),
    with "what got worse" as a pass of its own. A regression is a high finding.
- **The cut** (`cut_3d.py --head 3`) drops the painted frame's lead-in flash, and interpolates a
  slowed 24 fps take to 32 fps instead of repeating frames.

**Heights.** The author chose the carter at 1.76 m and Jakob at 1.55 m. These are new approved
versions of the same models (carter v2, Jakob v4).

**Still to do.** The look is not yet Venetian enough ("the scene doesn't look particularly
venitian"). What makes Carpaccio's Grand Canal of 1494 read as Venice is boats with boatmen
everywhere, Gothic tracery, roof terraces and the Rialto's shape. The boats and boatmen need
approved models first. The travel bags the boatman carries in the book are a proposed prop,
awaiting approval.

**LTX copies the set's light, so round 5c goes back to Wan** (measured on S0104-07, the wide
shot, against round 4 frame by frame):
- *Why every round-5 shot was darker and colder than round 4.* LTX settles on its guide's own
  colours within about a second. The painted first frames were as bright as round 4's (mean
  red 40 against 36), but the set render they guide is dark and blue (22, 22, 31), and the shot
  ends up looking like the render. Per-channel gains on the guide (`ltx_render.py --match-ref`)
  and a histogram match of the guide to the painted frame (`--match-tones`) warmed it a little,
  not enough.
- *Wan VACE reading only the set's depth* (`vace_render.py --control depth`, round 4's route)
  takes its colour from the painted frame and its geometry from the current set. From the same
  painted frame, the wide shot is warm and lamp-lit again, with porters on the quay and people
  on the bridge, and keeps round 5's fixes: the barge's curved turn, the boatman at the oar, no
  ferry. LTX stays for shots whose look is the set's own.
- *A depth guide must be ranged to its shot.* The depth pass maps 0.6–80 m, made for close
  shots. From the high window, the barge 50 m off and the water around it came out within one
  grey level of each other, in round 4 as now. So the guide showed no boat, and Wan invented one:
  in both takes the barge's bow curled up into a gondola's. A shot's `depth_range` in the staging
  (here 10–200 m) passes `--depth-near/--depth-far`. The barge, its mast, its awning and its
  people then stand out, and nothing near the camera clips to white.
- `vace_render.py --res 704` takes frames painted at LTX's 1280×704, and a layout pass in a
  subfolder (`layout/<shot>/r5c`) names its takes after the shot.
- *A prompt must name what the set holds.* The quay's bales and porters were painted as grey
  blocks and statues until the first-frame prompt said what they are.
- *Negative prompts do nothing here.* Wan with its 4-step Lightning LoRAs runs at cfg 1, where
  the sampler never reads the negative prompt (the distilled Klein and LTX run the same way). So
  every "gondola, upswept prow" in a shot's `negative` was ignored. The gate's padlock, which
  the depth guide is too fine to carry and the motion prompt never named, vanished after the
  first frame, and a black boat appeared at a wall the guide shows bare. What must stay, and what
  must not appear, is said in the prompt itself: "held shut by a chain and padlock the whole
  time", "nothing moored at the wall". `vace_render.py` now says so when given a negative.
- *The cut drops the painted frame* (`cut_3d.py --head 2` at 32 fps). Wan keeps the keyframe as
  frame 0 and moves away from it at once: the close-up's face, cap and background jumped between
  frames 0 and 1 (a frame difference of 18.6, against about 1 after it).
- *A match grade to the round the author preferred* (`grade_match.py`: per-channel tone curves
  mapped onto the previous round's same shot, one fixed curve per shot so it cannot flicker)
  brings back the warmth a new route loses. It cannot move light that was never there: round
  4's painter lit the Fondaco's front, and no grade does that.
- *The critic's packet shows only what the cut uses.* The inn shot's take runs 5 s, but the cut
  uses 2.5 s; the critic's worst findings there (the boatman leaving the bow, the dog hidden)
  came after the cut ends. The packet's takes are now graded like the cut and trimmed to it.
- *Where retakes stop helping.* The cold critic read the cut four times overnight, each after
  fixes (5c, its grade, the padlock and boots retakes, 5d's repainted frames). Each pass fixed
  several faults, and the video model invented a few new ones in its fresh takes (a cloudy sky in
  the water, a lamp post on the quay, a second oar). What remains needs decisions that are the
  author's: the night level against their preference for round 4's warmth; new versions of
  approved models (the barge's cover, awning, mast and lantern; Jakob's hair and cap; the
  boatman's cap; the dog's build); the bridge rebuilt in the set; restaging. The critic's last
  list, with what each fault needs, is the series' `film/reviews/critic_r5d.md`.
- *Jakob's hair paints blond from behind,* in the gate and inn shots, though the set renders his
  model's hair auburn, the prompt says "not blond", and painting more lightly (0.68) changes
  nothing. A colour correction inside his outline also caught his cap and coat, which share the
  hair's hues in lamplight. Open.

## The author on round 5d, and round 6: back to version 1's method (2026-11-01)

The author on round 5d: "overall the progress is very poor. grand canal water is still. there are
now too many people around. most of the assets are worse looking. the start are too bright. the
lights don't flicker. the bridge shops are too uniform." Then, after rewatching version 1: "we seem
to have only regressed since then ... Almost everything looks worse."

**Why.** In version 1 the image model painted each shot as a whole picture from its description
and the character sheets, and Wan animated that picture freely (image to video). It drew Venice
from everything it knows: Gothic palaces with tracery, true night, close and cinematic framing,
people with character, water and flames that move. The 3D rounds made every shot from a model of
the place, to stop the changes version 1's notes named (the gate morphing, one oar then two, the
carter missing). The painter had to keep the model's shapes and the video model its depth, so the
look came from the model too: box buildings with identical windows, small doll-like people, flat
water, dusk light (the set is lit to be painted over), and no room for the video model to add
life. Round 5 added photographed textures that read as CG, too many people and too much rubbish,
and dropped the flicker pass (`flicker.py`), which round 4's cut had used. Each round was checked
only against the one before it, so the slide from version 1 never showed: the comparison is now
against the best version so far.

**Round 6** is version 1's method with the checks built since, in its own workspace (`film/r6/`,
symlinking the shot list, bible, animatic and audio; its own `storyboard/` and `render/`):
- *Storyboard frames from the description and the sheets,* through the storyboard tool
  (`autonovel mechanical keyframe-render`, `keyframe-verdict --take N`), with the author's notes
  written in: the wide shot from the side canal's bank as asked in version 1's note 12 (the
  barge turning in off the lit Grand Canal, the wooden Rialto with its shops, the Germans' house's
  flank with merchants at supper); the gate chained and padlocked, with a landing behind it; one
  hand on Jakob's chest; the boatman waiting on the bow, hands empty; the dog sniffing the carter
  first. Several takes per frame, picked by eye against the notes: of fifteen wide-shot takes,
  three drew the later stone Rialto, three put lamp posts on the quays, three lost Jakob.
- *Image to video* (`shot_render.py --film film/r6`), with the motion prompts edited for the
  notes. `keyframe_for` now resolves a select written relative to the book's `film/` folder
  when the round has its own workspace.
- *Static shots hold.* Three takes of the close-up turned Jakob away to walk to the gate beside
  him, whatever the prompt said. `shots.<id>.hold: true` in the render manifest renders
  first-and-last-frame (`WanFirstLastFrameToVideo`, the keyframe at both ends), so the shot ends
  where it began; the held take keeps him at the bars, face up, one hand on his chest.
- *Finishing* as version 1 and round 4: SeedVR2 to 1080p, RIFE to 32 fps, then `flicker.py`.
- *The critic* compares with version 1 (`critic_packet.py --previous cut/v1_first_minute_30-49s.mp4
  --boxes none --prompts-from film/r6`): no 3D boxes, and what each frame and motion were asked to
  be comes from the round's own storyboard and render manifests.
- *The look bible* now asks for a few faint stars and a few people at work, not a crowd.

The author on round 6: "overall much better looking", so version 1's method stays. Their one
note was that the inside of the water-gate "looks different again - we should design it". Behind
the bars, every version had drawn a different place. The gate is now designed as the author
chose, a covered dock you unload in. It has a location file that separates what the record shows
from what is design, a `kind: sheet` manifest rendered by `keyframe-render` like a character's
(views by day and at the scene's hour), and a plan in the set's coordinates. The author approved
it, then found the inn on the wrong side of the gate in its first plan. The 3D set had the
geography right: down the Grand Canal, left into the side canal short of the bridge, the Germans'
house on the right, and the inn past it. But the shot list's inn shots, written before the set,
were mirrored, so versions 1 and 6 drew the inn shot mirrored too, and no critic noticed. The set
now carries the approved dock. The shot list and the location files are corrected to the set, and
round 7's frame descriptions follow it. Two lessons for the commands: a recurring place gets a
sheet and a plan like a person, and the critic must check which side each landmark is on against
the set's plan, not only what is in the frame.

## Round 7: one sheet per recurring thing, developed at 480p (2026-11-01, evening)

The author's rules for this stage:
- "Consistency is the most important point, once it is consistent, it is easier to correct or change as well." Every recurring person, prop and place has one approved sheet, and every frame it appears in references that sheet. Round 7's frames reference Jakob's sheet (his arrival clothes were already on it; round 6's wide shot had simply not referenced it), the water-gate's sheet and the new bow-lantern sheet. A change becomes a new version of the sheet, applied everywhere at once.
- "We are iterating too slowly." The faults are consistency, geography, models and moving water, none of which depend on resolution, so development rounds render at 480p with no AI upscaling (`shot_render.py --res 480`, now the default; finishing is RIFE and the flicker only) and spend the time on more takes.

Measured, a 5-second take: at 720p, 20 minutes on the 3060 and about 11 on the 5060 Ti, with SeedVR2 adding 19 and 7 minutes; at 480p, 5.2–5.8 minutes on the 3060 and 3.2 on the 5060 Ti, finished with RIFE in 4 seconds. Round 7, thirteen 480p takes and the cut, took about 80 minutes on the 3060, where four hours would have been needed at 720p with upscaling. It all stays on the 3060, which keeps the 5060 Ti, the card that drives the monitor, free for the author's desktop. Two video servers can't run at once inside WSL's 40 GB, because each holds about 26 GB of RAM. "Both cards" therefore means video on one and storyboard frames on the other.

Round 7 also fixes the geography, as above. The wide shot now looks back from the gate down the side canal to the Grand Canal, with no bridge, because from inside the side canal the Rialto is hidden behind the Germans' house.

## Design once: the method reconsidered after the barge sheet (2026-11-01, night)

The author on the barge sheet painted from the approved model:

> the barge looks mostly good. in the side day shot, the squared front of the barge looks missing/transparent. the oar in the back is floating and no in anytype of oarlock - your critic/you should see both. the night view and day view have different masts, lanterns and canvas deck covers. why can't they be consistent? why do I have to find the problems - I can't specify and study every artifact in every shot. we should be design once and they stay constant. review again unreal and unity and similar tools.

**Two failures.**

The first is a process failure. Sheets went to the author without the cold critic, so nobody compared one view with another or asked whether each part could work. Now every sheet goes through the critic first. It checks every view against every other part by part, checks that each part is physically real (attached, supported, solid, working), and checks the sheet against the approved model. Only then does the author see it.

The second is the method. An image model redraws every object from scratch every time, so two drawings of one barge drift, however good the reference. All of the author's recent findings are about rigid things that must not change: the gate, the lantern, the barge, the bridge, the Germans' house, the inn steps, and the costume. In a renderer those are the same objects every time, by construction.

**Why the 3D rounds still looked worse.** Two causes, both avoidable:
- The models were untextured blockouts.
- The AI pass (LTX, then Wan from depth) redrew every surface, so the look changed from shot to shot and fell below the paintings.

**The method that keeps a design constant.**

1. **A rigid thing is a 3D model, with its look designed once.** The approved painting is projected and baked onto the model as its texture. Tools for this: StableGen in Blender, through ComfyUI; Hunyuan3D-Paint's multiview bake; plain camera projection for fronts. The critic checks it from several angles, the author approves it, and it is frozen. A change is a new version.
2. **The plate is rendered and never redrawn.** The set and props come from the renderer, with lanterns as real lights.
3. **The AI only adds what 3D does badly:** people, moving water and flame. These are generated inside masks and composited back onto the plate, so every pixel outside a mask is the renderer's. VACE's masked inpainting alone won't keep the rest of the frame untouched; users report it redraws more than the mask. So the composite, not the model, guarantees it.
4. **People stay consistent through a LoRA** trained on the approved sheet, with every frame referencing the hooded views. They are composited like water and flame.

**The engine.** The method matters more than the engine:

- **Blender** (in use) runs in WSL. Its sets are scripts a person can rerun. It renders with Cycles or EEVEE on both cards and can make water ripples and wakes (ocean modifier, dynamic paint). It already holds the barge v3 model and the side-canal set. Weaknesses: no MetaHumans, and many-light night scenes are slow in Cycles.
- **Unreal Engine 5.8** (the last UE5; UE6 previews late 2027) has the strongest real-time realism: Lumen, MegaLights now production-ready, a water system and the path tracer. It has an official MCP server and Fab's asset market. Costs:
  - it is Windows only, so an install the author would have to make;
  - there are no 1473 Venice assets (the scanned Venice kits show the modern city);
  - MetaHuman still has no 14-year-old, and close-ups read as a game;
  - Megascans are no longer free;
  - it takes weeks to learn.
  It is free under $1M of revenue.
- **Unity 6 (HDRP)** renders about as well, with weaker film tools and fewer high-end assets. Its official AI MCP needs a paid Unity AI subscription; community MCPs (Coplay) are free. No advantage here.
- **Godot** is not film-grade. **Omniverse** is heavy and built around USD; too much for this.

**The author's decision:** "we will compact then do the barge in blender and proceed - the problem is not individual objects - we should be able to change them trivially and have the scene rerender corrected. it is the process, the constant changing and morphing of objects, the incorrect geometries." So the goal is a process, not one better asset:
- Every shot is rendered from one 3D scene per location, which references versioned assets (`film/assets/register.yaml`) with their approved looks baked on.
- Changing an asset is one edit, a new version, and a script re-renders every shot that contains it, corrected.
- An image model never draws rigid geometry.

**Recommendation.** Keep Blender and change the method. Prove it first on the barge: bake the approved painting onto the v3 model, fix the model's bow end and give the oar an oarlock (v4), then render it by day and at night from the angles of S0104-07 and S0105-01. If it holds its look and stays identical, do the same for the lantern and the gate. Then render round 8's plates with people, water and flame composited in. Unreal stays the fallback if Blender's night light can't reach the look; the assets move to it as FBX or USD.

Sources:
- Unreal Engine 5.8: https://gamefromscratch.com/unreal-engine-5-8-released/ and https://www.guru3d.com/story/unreal-engine-58-debuts-lumen-lite-and-productionready-megalights/
- MegaLights: https://dev.epicgames.com/documentation/unreal-engine/megalights-in-unreal-engine
- Unity AI MCP: https://gamedev.net/news/4376-unity-ai-open-beta-how-to-get-started-with-mcp/
- Coplay's MCP for Unity: https://docsearch.algolia.com/mcp/docs/repo/coplaydev/unity-mcp
- VACE inpainting and its limits: https://comfyai.run/documentation/WanVACEInpaint and https://reddit.sentinel-team.org/posts/1sglz7b/snapshots/2026-04-09T15%3A42%3A50.429038Z
- Texture baking: https://www.runcomfy.com/comfyui-nodes/ComfyUI-Hunyuan3DWrapper/hy3-d-bake-from-multiview and https://redlib.hbubli.cc/r/comfyui/comments/1kpwnx0/stablegen_released_use_comfyui_to_texture_3d/mt25uke/?context=3

## Round 8: the whole first minute by the new method (2026-11-01 to 02, overnight)

The author: "do a full minute with the new approach with your best object models." Every shot's plate was rendered from the 3D set: the side canal with photographed surfaces, barge v4 (unapproved, used on the author's instruction), the approved dock gate, and lanterns as real lights. The image model painted only the people over each plate's lit first frame. The video model (Wan VACE, guided by the set's depth) moved the people and the water, and `composite_plate.py` kept the plate everywhere outside the people and water mattes. Thirteen shots, cut to the minute's slots: `film/cut/seq_01_first_minute_r8.mp4`.

**What the night found in the method, each fixed once for every shot:**
- *No lantern in any set had ever lit anything.* Each lantern's light sits inside its horn panes, and the panes stopped shadow rays. The gate rendered black on black, the barge read as a black toy, and every 3D round was darker and bluer than the paintings it was compared with. `shot_layout.py` now makes the horn and flame materials transparent to shadow rays only. Once the lanterns lit their walls and water, the plates came close to the night the look bible describes.
- *The set's map labels* ("GRAND CANAL", "RIALTO BRIDGE") came out white in the mattes and the depth; they are hidden in every pass.
- *The video model's water* was a bright, cloudy sky reflection. The composite now levels it to the plate's own water.
- *Its people drift to white* within two seconds. The composite holds each person's colour to their first frame, inside their own matte. One hold over all the people turned Jakob green as the boatman's red jacket grew in frame.
- *The painter copies the 3D people models* at the usual strength (denoise 0.72). Jakob's model has a soft face, curls and an open coat with no cape, so he came out girlish and capeless. At 0.82 the painting follows his approved sheet instead.
- *Running two kinds of job on one GPU server* breaks things. The finishing step's memory watchdog interrupts whatever the server is running. A painting run that failed left its old takes to be composited as if new. On the 3060, three reference pictures at full size exhaust its memory, and the error reads "device not ready". Each now has a guard (`keyframe_from_layout.py --ref-mp`, old takes cleared, finishing only after the motion).

**The critic: worse than version 1** (`film/reviews/critic_r8.md`). The rigid things finally held: the Fondaco, the gate, the steps and the barge are the same objects in every shot, and the barge is the square-ended burchio throughout. But version 1's painted frames are warmer, richer and more alive in nearly every shot. In round 8:
- Jakob changed costume between shots;
- the story's actions didn't happen (the tout, the dog and the innkeeper only stand);
- one shot still had round 2's camera.
The people are where this method is weakest: they are painted once per shot and then moved by a model that sees only depth.

**Round 8b and 8c, the same night.** Round 8b fixed:
- the sky: blue-black, not a blue wash;
- the gate: the white stone arch of its approved sheet;
- the inn shots: a lower exposure;
- S0104-07: restaged from the inn steps, as its shot list says;
- Jakob: repainted at the higher denoise;
- colour: each person's held separately.

The critic still found it much worse than version 1 and level with round 8 (`film/reviews/critic_r8b.md`). Four shots were better: S0104-07, Jakob in S0104-09, his colour in S0105-01, and the sky. Three regressed. Its worst findings are in the people:
- Jakob, the carter and the dog change from shot to shot;
- nobody acts;
- the touts are dressed wrong;
- the bow lantern on the barge model is a box, not the approved horn lantern;
- the bridge reads as a modern footbridge.

One fault was the finishing's: the grade toward version 1 turned the inn shots' black dog and Jakob's coat blue, because those plates are warm now that their lanterns work. Round 8c keeps the inn plates' own colour at round 8b's brightness and grades the lagoon harder toward a neutral night (`film/reviews/critic_r8c_check.md`).

**What the method still needs**, in order:
1. A new version of Jakob's 3D model with his sheet's face, hair and cape, since the painter follows the model.
2. Staging that acts: the tout leaning, the dog pushing under the hand, the innkeeper taking the collar, posed in Blockout so the depth guide carries the move.
3. A per-person LoRA from the approved sheets, so a face holds across shots.

## What doesn't change

The screenplay, the shot lists' craft (CAMERA.md), the table read, the
vision judges, the author's approvals and the overnight runs all stay. The 2D
stack stays installed: the hybrid uses FLUX 3 Klein, Wan 2.2, SeedVR2 and RIFE
as it does today.

## Risks

- The agent may not build fine architecture well. Mitigation: model only
  simple modules and let the kit and geometry nodes repeat them.
- VACE-Fun at 720p on 16 GB may be too slow for a nightly minute. Fallback:
  480p plus SeedVR2.
- Night light may still drift between shots. Mitigation: use the lit pass as
  the keyframe reference and grade.
- Faces in close-up remain presentable rather than seamless.

## Sources (checked 2026-10-30; 2026-10-31 additions at the end)

- Unreal 5.8: https://www.unrealengine.com/news/unreal-engine-5-8-is-now-available
- Unreal licence: https://www.unrealengine.com/en-US/blog/we-are-updating-unreal-engine-twinmotion-and-realitycapture-pricing-in-late-april
- MetaHuman licence: https://www.cgchannel.com/2025/06/you-can-now-sell-metahumans-or-use-them-in-unity-or-godot/
- MetaHuman teen question: https://forums.unrealengine.com/t/createing-a-teen-metahuman/1265729
- Unreal MCP: https://byteiota.com/unreal-engine-5-8-ships-mcp-server-ai-agents-can-now-drive-the-editor/ and https://github.com/EpicGames/unreal-engine-skills-for-claude-code-plugin
- A Claude cabin rebuilt in Unreal: https://www.mindstudio.ai/blog/claude-rebuild-ai-video-unreal-engine
- Blender 5.2 LTS: https://80.lv/articles/blender-5-2-lts-has-been-released
- Blender MCP: https://www.blender.org/lab/mcp-server/ and https://github.com/ahujasid/blender-mcp
- Blender 5.3 splats: https://radiancefields.com/blender-5.3-will-bring-native-3d-gaussian-splat-import-and-rendering
- TRELLIS.2: https://github.com/microsoft/TRELLIS.2
- Hunyuan3D 2.1: https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1
- SPAR3D: https://github.com/Stability-AI/stable-point-aware-3d
- World Labs Marble export: https://docs.worldlabs.ai/marble/export/gaussian-splat
- HY-World 2.0: https://github.com/Tencent-Hunyuan/HY-World-2.0
- Splats can't be relit: https://garagefarm.net/blog/3d-gaussian-splatting-what-is-it
- Venice kits: https://digitalproduction.com/2025/12/03/venice-in-unreal-scans-factorys-ue5-7-demo-goes-public/
- Wan2.2-VACE-Fun-A14B: https://huggingface.co/alibaba-pai/Wan2.2-VACE-Fun-A14B
- The ComfyUI wrapper: https://github.com/kijai/ComfyUI-WanVideoWrapper
- Uni3C: https://arxiv.org/abs/2504.14899
- Wan-Animate-2: https://blog.comfy.org/p/wan-animate-2-is-now-available-in
- SCAIL-2: https://github.com/zai-org/SCAIL-2
- Blender to ComfyUI renderer: https://www.runcomfy.com/comfyui-workflows/blender-to-comfyui-ai-renderer-2-0-workflow-cinematic-video-output
- Blockout: https://github.com/wassermanproductions/blockout
- StoryBlender: https://arxiv.org/html/2604.03315v1
- BlenderGym: https://arxiv.org/abs/2504.01786
- InfiniteTalk: https://comfyui-wiki.com/en/news/2025-08-20-infinitetalk-audio-driven-video-generation
- Existing solutions: https://intangible.ai/pricing, https://kling.ai/blog/kling-video-3-multi-shot-guide, https://flick.art/blog/behind-ser-loras, https://pjace.beehiiv.com/p/gossip-goblin-s-crazy-workflow-for-building-original-worlds-200m-views, https://aif.runway.com/, https://discuss.ai.google.dev/t/human-review-requested-veo-3-1-reference-images-and-allow-adult-for-a-fictional-17-year-old-character/179169
- De' Barbari's view (the old Fondaco): `bible/refs/venice-views/barbari-1500_detail_rialto-bridge-and-fondaco.jpg` in the series
- LTX-2.3 3DREAL IC-LoRA (fal): https://huggingface.co/fal/LTX-2.3-3DREAL-LoRA
- LTX-2.5 Layout-to-Render IC-LoRA: https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Layout-To-Render (reference-frame reports: discussions/5)
- LTX-2.5 GGUFs: https://huggingface.co/unsloth/LTX-2.5-GGUF
- Unreal MCP (5.8 docs): https://dev.epicgames.com/documentation/unreal-engine/unreal-mcp-in-unreal-editor
- No teen MetaHuman: https://forums.unrealengine.com/t/kid-metahuman-body/2446660 ; teen MetaHuman on Fab: https://forums.unrealengine.com/t/inex-m-b-kirill-metahuman-boy-editable-character-with-groom/2731981
- Daz teen figure: https://www.daz3d.com/teen-tyler-for-genesis-9
- Megascans no longer free: https://80.lv/articles/megascans-no-longer-free-after-2024/
- WSL2 Vulkan: https://forums.developer.nvidia.com/t/vulkan-fails-to-detect-nvidia-gpu-on-wsl2-ubuntu-24-04-dzn-driver-files-missing-tested-on-multiple-systems/342142
