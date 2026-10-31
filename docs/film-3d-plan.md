# Film pipeline: sets in 3D, the look from AI

> **Status:** recommendation for the author, 2026-10-30, after the first
> moving minute of kingmaker2 (`docs/film-pipeline-plan.md` M5 pilot). Research
> by three agents on 2026-10-30, with sources below; prices, licences and
> versions move monthly. Nothing is built yet.

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

**Still to do before adoption:** sharper takes (720p, then RIFE and SeedVR2,
as for version 1); several takes per shot with a vision pick; the S0105 inn
sequence re-staged to the author's beat order (notes 1 and 3); a cold viewer
and the author's verdict; then fold the scripts into autonovel commands
(`set`, blocking in `shot-list`, the keyframe and motion stages).

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

## Sources (checked 2026-10-30)

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
