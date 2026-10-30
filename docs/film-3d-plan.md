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
