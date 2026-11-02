# Film project post-mortem and progress report (2026-10-28 to 2026-11-02)

> **Status:** the film work is paused at the author's decision, 2 November 2026: "this film
> project is not working out well. write a post mortem with a progress report for the film
> project and suggestions for improvements in the future. … we will later continue with the
> book itself and other books." The plans this reviews are
> [`film-pipeline-plan.md`](film-pipeline-plan.md) (the whole pipeline, M1–M8) and
> [`film-3d-plan.md`](film-3d-plan.md) (sets in 3D, rounds 1–8). The book is kingmaker2; its
> film folder is `books/kingmaker2/film/` in the series.

## The short version

**The worst of it.** In five days the first minute of kingmaker2 was rendered as moving film
fourteen times: version 1 and thirteen rounds after it. None is good enough to show anyone. No
round after version 1 was judged better than it overall, by the author or by the cold critic,
and version 1 itself "has some random changes or incorrect items" in almost every shot. The
author's last three verdicts were "overall the progress is very poor" (1 November, morning),
"why do I have to find the problems" (1 November, night) and "not working out well"
(2 November).

**What failed** is the part the plan itself called the risk. A moving film, made with free
models on local GPUs, can't yet keep the same people, costumes, props and places from shot to
shot, or make people act a scene. The 3D sets solved the places and props in round 8, but not
the people.

**What works and is worth keeping** is the writing half. These ship as tested autonovel
commands and turn a chapter into a script a reader can follow, a shot list a crew could
shoot, character sheets, a voiced table read and an animatic:
- `/autonovel:screenplay`;
- `/autonovel:shot-list`;
- `/autonovel:storyboard`;
- `/autonovel:table-read`;
- `/autonovel:animatic`.

**The main lessons, worst first:**
1. The tools couldn't do what the goal needed, and the plan's own stop point ("decide at M5
   whether a feature is worth it, or whether screenplay, animatic and trailer are the
   product") was passed without stopping.
2. The method changed almost every round, so nothing converged and every round broke
   something that had worked.
3. Each round rendered the whole minute instead of getting one shot right first.
4. The author was the quality gate: the critic came late and missed things, and bugs in the
   pipeline's own output hid for days.

## Progress report

### What was built

| Stage | State | Where |
|---|---|---|
| Screenplay (M1) | Shipped and tested. kingmaker2 chapter 2's Venice sequence in Fountain, PDF and FDX, with an adaptation note, a screen critic and a cold reader. | `commands/screenplay.md`, `shared/craft/SCREEN.md`, `autonovel mechanical fountain-check` |
| Shot list (M3) | Shipped and tested. Coverage, lenses, the 180° line, eyelines, continuity and computed durations, checked mechanically and by a director/DP critic. | `commands/shot-list.md`, `shared/craft/CAMERA.md`, `autonovel mechanical shot-check` |
| Storyboard, table read, animatic (M4) | Shipped and tested. Character sheets and keyframes on a local image model (FLUX 3 Klein) with a vision check; voices designed from descriptions (VoxCPM2) and checked by Whisper; an animatic timed to the read. | `commands/storyboard.md`, `table-read.md`, `animatic.md` |
| Moving film, version 1 (M5 pilot) | One 59-second cut of the first minute: painted keyframes animated by Wan 2.2, picked by a vision judge. Not good enough. | `film/cut/seq_01_first_minute_v1.mp4`; scripts in `~/film-stack/scripts` |
| 3D pilot (rounds 1–8c) | A Blender set of the side canal, the gate and the inn steps; Blockout staging; approved 3D people and props; VACE motion; plates composited with painted people and water. The set and the geography hold; the look and the people don't. | `film/sets/`, `film/blocking/`, `film/assets/`; about 40 scripts in `~/film-stack/scripts` |
| Film bible and sheets | Characters, locations, props and the look. Approved sheets: Jakob, the carter, the boatman, the innkeeper, the dog, the water-gate, the bow lantern. An asset register with versions and approvals. | `film/bible/`, `film/assets/register.yaml` |
| The critic | A packet builder: strips, figure crops, the best earlier version over the same seconds, the plans, the sheets. Cold critic briefs. A benchmark scoring the critic against the author's own notes. | `~/film-stack/scripts/critic_packet.py`, `film/reviews/` |
| The local stack | ComfyUI on two cards (5060 Ti 16 GB, 3060 12 GB) under WSL, about 114 GB of open models, a runbook of measured timings and house rules. | `~/film-stack`, `~/film-stack/RUNBOOK.md` |

In the autonovel repository, about 40 of the 69 commits between 27 October and 2 November were
film work.

### The rounds and their verdicts

| Round | Date | Method | The author | The critic |
|---|---|---|---|---|
| Version 1 | 30 Oct | Keyframes painted per shot, Wan 2.2 image-to-video, 720p, 59 s | "Almost every scene has some random changes or incorrect items"; Venice "looks almost deserted"; the inn scene doesn't tell the story | — |
| 3D round 1 | 30 Oct | Blender set, Blockout staging, Klein over the set's render, VACE along its depth (19 s) | Too pristine, still water, identical lit windows | — |
| Round 2 | 30 Oct | The same, with dirt, washing, debris | The boat looks motorised; the bridge changes; clothing varies | — |
| Round 3 | 30 Oct | The same, more takes | "The general appearance isn't as good as previous" | — |
| Round 4 | 31 Oct | Approved 3D models only; the whole minute | "Overall the 1 minute is pretty bad … Aren't these 3D models and static?" | Introduced after this round; scored 6 of the author's 7 findings |
| Round 5, 5b | 31 Oct | LTX rendered from the set | "The r4 version had a nicer feel to it … I don't like it when we regress" | Not ready |
| Round 5c, 5d | 1 Nov | Back to Wan from painted frames, graded to round 4 | "Overall the progress is very poor" | 23 high findings; not ready |
| Round 6 | 1 Nov | Version 1's method again (19 s) | "Overall much better looking," but the gate changes again | About level with version 1 |
| Round 7 | 1 Nov | 480p, one approved sheet per recurring thing | (the gate and the lantern designed and approved; the barge sheet: "why do I have to find the problems") | Worse than version 1 |
| Round 8, 8b, 8c | 1–2 Nov | The plate method: every rigid thing rendered from the set, people and water composited in masks; the whole minute | "This film project is not working out well" | Worse than version 1 every time |

The cuts are in `film/cut/`, the author's notes in `film/reviews/author_notes_v1.md` and
`author_notes_pilot3d.md`, the critic's reports in `film/reviews/critic_r*.md`.

### Where it stands

- **Approved by the author:** the character sheets, the water-gate design and plan, and the bow
  lantern. The screenplay sequence, shot lists, storyboard and animatic were shown to the author
  and used as the brief for every round.
- **Built but not approved:** barge v4.
- **Never good enough:** any moving minute.
- **Decisions left open** (at the end of `author_notes_pilot3d.md`): which method to keep;
  Jakob's 3D model v2; barge v4; staging in which people act.

## What went wrong, worst first

1. **The goal outran the tools, and the plan's own stop point was passed.**
   - *The gap:* the best open image model (FLUX 3 Klein, Elo 1043) sat about 180 points below
     the best closed ones. The best open video model a US user may run (LTX-2.5, 917) sat
     about 200 below the closed leader (H3, 1126).
   - *What no tool here offered:* none of the local tools holds a person's identity and costume
     across shots, or animates a person to a script's action. The plan named both as "the
     quality ceiling" on 28 October, and said to decide at M5 whether screenplay, animatic and
     trailer were the product.
   - *What happened instead:* after version 1 the work moved on to the 3D method, and then to
     thirteen rounds of it. Each round improved what the last one had broken.
2. **The method changed nearly every round, so nothing converged.** The sequence ran: painted
   keyframes; 3D sets painted over; LTX from the set; back to Wan from painted frames; back to
   version 1's method; 480p with sheets; plates with composited people. Each change fixed some
   faults and undid things that had worked: round 4's warmth, life and moving water were lost
   in round 5. The author: "I don't like it when we regress rather than improving everything."
   No round changed one thing and held everything else.
3. **Every round rendered the whole minute instead of proving one shot.**
   - Thirteen shots a round meant every fault appeared thirteen times, and every round cost a
     night of both GPUs and a morning of the author's attention.
   - No shot was ever brought to the author's approval and then frozen as the standard the
     rest had to meet.
4. **The author was the quality gate.**
   - *The critic came late:* a cold critic with a packet of frames was added only after round 4.
   - *It missed things:* its benchmark against the author's notes shows it missing the
     flicker, the inn on the wrong side, a cast too big (it asked for more people when the
     author found too many), and regressions until the packet carried the best earlier
     version beside each shot.
   - *Sheets went unchecked:* they went to the author before any critic had compared their
     views. The author: "why do I have to find the problems - I can't specify and study every
     artifact in every shot."
5. **Bugs in the pipeline's own output hid for days, because nothing tested it.**
   - *The lanterns:* no lantern in any 3D set ever gave light. Its light sat inside horn panes
     the renderer treated as solid. Every 3D round was darker and bluer than the paintings
     beside it for that reason, and it was found only in round 8.
   - *Other faults found by eye, late:*
     - the set's map labels showed in the masks and the depth;
     - a colour grade turned the inn's black dog blue;
     - a colour hold turned Jakob's coat green;
     - S0104-07's staging still held round 2's camera, days after its shot list had changed.
6. **The documents disagreed with each other.** The shot list, the 3D staging, the prompts and
   the geography notes were each written by hand and drifted apart. The inn was on the wrong
   side of the gate in the plan and the shot list (the author found it), and the carter, Jakob
   and the gate change sides between documents in five shots.
7. **The people were left to the models.**
   - *Acting:* the 3D stand-ins stand still, so the video model, following their depth, makes
     statues. The tout never leans out, the dog never lunges, the innkeeper never takes the
     collar.
   - *Faces and costumes:* the image model copies the 3D people's faces and clothes (Jakob's
     model is girlish and has no cape), and the video model drifts costumes within seconds.
   - *Nothing was built to hold a face:* no per-person model (LoRA), no posed animation, no
     face check against the sheets.
8. **The hardware made every round slow and fragile.**
   - *Memory:* two cards under WSL's 40 GB of RAM, and room for only one video server at a time.
   - *Speed:* takes of 5 to 20 minutes; overnight runs.
   - *Errors and collisions:* "device not ready" errors under load, and one job's memory
     watchdog killing another job's take.
   - *Wasted renders:* the speed-up to 480p came only in round 7, and it was the right call.
9. **Too much of the craft and too many reports were put to the author.** The author has no film
   training, yet was asked for design decisions and handed long reports between rounds, in a
   project meant to need little of them.

## What worked

- **The writing stages.** Screenplay, shot list, storyboard, table read and animatic all ship as
  commands with tests, and the animatic is the cheapest way to judge a scene's staging and
  pace.
- **One approved design per recurring thing.** Where a sheet existed and every frame used it
  (the water-gate, the bow lantern, Jakob's hooded view), drift fell.
- **The 3D set for rigid things.** In round 8 the Germans' house, the gate, the inn steps and
  the barge stayed the same objects in every shot, and the geography held from the Grand Canal
  into the side canal. This is the one thing the 3D method clearly did better than version 1.
- **The critic once it compared.** Packets with the best earlier version, the plans and the
  sheets beside each shot let it find regressions and wrong sides. The benchmark gives a
  standard for judging the critic itself.
- **Measuring instead of guessing.** Measured timings, RAM and colour figures settled
  questions (which card, which exposure, whether a grade added a cast) that opinion did not.
- **The lessons are written down:** the runbook's house rules, the 3D plan's round sections,
  the critic reports.

## Suggestions for the future

### Decide the product first

1. **Treat the writing half as the film product for now.** The pitch package is the
   screenplay, shot list, character and location sheets, table read and animatic, and a
   trailer cut from storyboard frames with the table read's voices. It is cheap, it is good
   enough to show, and a human crew or a better model could shoot from it.
2. **Re-test moving film on a schedule, not continuously.** Keep one benchmark shot: S0104-08,
   Jakob at the gate. Every few months, render it with the newest open models and compare it
   with the last benchmark. Resume rendering only when a model holds a face and a costume
   through a cut without help.
3. **Ask before paying.** The author has ruled out keyed and paid providers. If that changes,
   the plan's paid tier (Kling and others, under a hard budget cap) is the fastest way to
   actors who act. It is the author's decision, not a default.

### If rendering resumes

4. **Prove one shot, then a scene, then a minute.**
   - Before anything else is rendered, write an acceptance check for one shot.
   - Bring that shot to the author's approval.
   - Freeze it as the standard. A scene starts only after its first shot is approved, and a
     minute only after a scene.
5. **Change one thing per round and keep a frozen baseline.** Every round names the one change
   it tests. It is compared automatically with the best version so far, shot by shot, before
   anyone watches it. A round that isn't better is reverted, not built on.
6. **Make the pipeline test itself before a person sees it.** Checks that fail a round:
   - every light lights what is around it;
   - no text or stray object in a mask;
   - colour and brightness measured per shot against the shot before it;
   - each painted face compared with its sheet by a face-similarity model;
   - every landmark on the side the staging puts it.
   Bugs like the lanterns should be caught on the first render, not the fortieth.
7. **People first.**
   - *A per-person LoRA* trained on each approved sheet.
   - *3D people models that wear the sheets*: Jakob's v2 with his face, hair and cape.
   - *Acting posed in the 3D staging* (or taken from a short phone-camera performance), so the
     video model follows a move instead of inventing one.
   - *A talking-head model* for dialogue close-ups.
   - *Make or break:* until a face holds across three shots, nothing else matters.
8. **One source of truth for geography.** The 3D staging should write each shot's sides,
   screen directions and landmark positions. The shot list, the prompts and the critic's
   geography should all read them, never restate them, so they can't disagree.
9. **Version everything a render depends on.** About 40 film scripts live in `~/film-stack/scripts`
   under a local git history with no remote. Push them to a repository, or fold the
   proven ones into autonovel, so a change to an asset or a script re-renders the same way on
   any machine.
10. **Budget and stop rules.** Give each round a budget in GPU-hours and author time. After two
    rounds that are not better than the best version, stop and put the choice to the author,
    rather than trying a new method overnight.
11. **Spare the author.**
    - One decision at a time, each with a before-and-after picture.
    - Short reports that lead with the worst item.
    - Sheets and rounds that reach the author only after the critic has checked them against
      their approved designs and the previous round.

## Where everything is

- **Plans:** [`film-pipeline-plan.md`](film-pipeline-plan.md) (the stages, the stack, M1–M8),
  [`film-3d-plan.md`](film-3d-plan.md) (the 3D method, rounds 1–8c and what each taught).
- **Commands:** `commands/screenplay.md`, `shot-list.md`, `storyboard.md`, `table-read.md`,
  `animatic.md`; craft references `shared/craft/SCREEN.md` and `CAMERA.md`.
- **The book's film folder** (`books/kingmaker2/film/`):
  - the screenplay, shot lists and storyboard;
  - the bible and approved sheets;
  - the sets, blocking and assets;
  - the cuts of every round (`cut/`);
  - the author's notes, the critic reports and the benchmark (`reviews/`).
- **The local stack:** `~/film-stack` (models, ComfyUI, `RUNBOOK.md` with the house rules,
  `scripts/` with the render and critic tools).
- **Open work**, if film resumes: FUTURE-TODOS, the film sections ("Film 3D: round 8" lists the
  model, staging, lantern, bridge and geography fixes).
