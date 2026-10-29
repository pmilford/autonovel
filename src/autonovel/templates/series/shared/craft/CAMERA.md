# CAMERA REFERENCE

How a scene of the screenplay becomes shots: what the camera shows, from
where, how it moves, how long it holds, and how a picture made by an image
model is checked against that intent. SCREEN.md says how a passage becomes
pages; this file is the director's and the director of photography's half,
read by `/autonovel:shot-list` (its critic scores against §10), by
`/autonovel:storyboard` (§8, §9) and by `/autonovel:animatic` (§6, §9). A
spec screenplay carries no camera directions (SCREEN.md §1), so none of
this belongs in the script.

**Precedence.** The script decides what happens and what is said. The
film's bible (`books/<book>/film/bible/`) decides how people, places and
objects look, and its `look.yaml` decides the format, lenses, camera rules,
palette and light; where this file and the look disagree, the look wins
for that film. The book's genre guide (`## On screen`) says what that
genre's audience must not lose; in historical fiction the period is the
payload, so a shot that shows it is never cut for pace.

**What is sourced and what is not.** Each rule names its source. A
quotation is given only where its wording was checked at the page cited;
otherwise the rule is a paraphrase of the book named. Thresholds the
sources don't give are marked `[pipeline heuristic]`.

---

## 0. The card

1. **Every shot has a job** (§2): it shows the audience something it needs,
   or makes it feel something the scene needs. Write the job down.
2. **Cover the scene so it can be cut** (§2): where we are and who is where
   first, then closer as it matters; the scene's turn gets the shot sized
   to carry it.
3. **Stay with the viewpoint** (§2.4): what he cannot see, we do not.
4. **A move answers to something** (§3): a person moving, a reveal the
   story needs. Otherwise the camera is still.
5. **Keep the line** (§4): the camera stays on one side of the people or
   the path, so left and right stay put on screen; cross it only on screen.
6. **Continuity is declared, then checked** (§5): the same words for the
   same coat in every shot; a change gets its reason.
7. **A shot lasts as long as what plays in it** (§6): the lines as
   recorded, the action, the time to read the frame. Computed, not typed.
8. **Light comes from somewhere** (§7): a source in the frame or just off
   it, and only what the period had.
9. **Prompt what you want to see** (§8): image models do not obey "no".
10. **Judge the picture against the shot** (§9), and the animatic against
    the scene: can a viewer tell what happens?

---

## 1. Shot grammar: size, angle, lens, height

**Sources.** Joseph V. Mascelli, *The Five C's of Cinematography* (1965):
camera angles, continuity, cutting, close-ups, composition. Blain Brown,
*Cinematography: Theory and Practice* (4th ed., 2022), ch. 5, "The Shots:
Building Blocks of a Scene". Steven D. Katz, *Film Directing Shot by Shot*
(1991).

Mascelli's first C is the camera angle, by which he means the whole set-up:
how much of the subject the frame takes in, from what height and side, and
from whose point of view. His three kinds are the **objective** angle (an
unseen observer), the **subjective** angle (the camera as someone's eyes)
and, between them, the **point-of-view** angle: "A point-of-view shot is as
close as an objective shot can approach a subjective shot—and still remain
objective" (Mascelli, p. 22, as quoted by Wikipedia's "Point-of-view
shot"). Brown builds a scene from a small vocabulary of shots: the wide and
establishing shots, the full shot, the two-shot, the medium shot, the
close-up, the over-the-shoulder, the cutaway, the reaction shot and the
insert.

**Rules the sources support.**

1. **Size** is one of `EWS` (the place, people small in it), `WS` (the
   whole action), `FS` (a person head to foot), `MS` (waist up), `MCU`
   (chest up), `CU` (the face), `ECU` (a detail: an eye, a seal). Size is
   emphasis: the closer the shot, the more it says "this matters now"
   (Mascelli's close-ups "point up story highlights", a phrase seen only in
   an excerpt).
2. **Angle** is `eye` (the default: level with the subject's eyes),
   `high` (looking down: the place, or a person made small), `low` (looking
   up), `overhead`, or `dutch` (tilted). A film's look may forbid some.
3. **Lens** changes perspective, not only size: a wide lens close in
   stretches depth and shows the room; a long lens farther back compresses
   it and isolates a face. Choose from the look's lens set by the job, not
   by habit.
4. **Height** is the subject's eye line unless the shot's job needs
   another; the look may fix it (a boy's eye line, a seated man's).
5. **Composition** keeps the subject where the eye lands, with room in the
   direction they look or move ("lead room"), and the frame's edges free of
   anything that pulls the eye away.

---

## 2. Coverage, the viewpoint and the cut

**Sources.** Mascelli (cutting, close-ups); Katz (staging, coverage; the
publisher describes his "A, I, and L patterns" for "the hundreds of staging
choices"); Brown ch. 4–5; Walter Murch, *In the Blink of an Eye* (2nd ed.,
2001); Edward Dmytryk, *On Film Editing* (1984), as summarised by Peter
Thompson.

**Coverage** is the set of shots made of one scene so that an editor can
cut it: classically a **master** (the whole action in one wide view), then
**singles**, **two-shots** and **over-the-shoulders** closer in, **inserts**
of the objects the story turns on, and **cutaways** to what the people are
looking at. Murch ranks what a cut must keep, in order: emotion (51%),
story (23%), rhythm (10%), eye-trace (7%), the two-dimensional plane of the
screen (5%) and the three-dimensional space of the action (4%); "If you
have to give up something, don't ever give up emotion before story." The
rule of the line (§4) is the last two, so it matters, but the scene's
feeling and its story come first.

**Rules the sources support.**

1. **Write each shot's job** (`purpose`): what the audience learns or
   feels. A shot whose job another shot already does is cut.
2. **Establish, then go closer.** Open on where we are and who is where
   (an establishing view or a master), unless withholding it is the point;
   then move in as the scene's stakes rise.
3. **The turn gets the shot.** The moment the scene's value changes
   (SCREEN.md §2) gets the closest, best-held shot of the scene, usually on
   the face or the hands or the object that carries the change.
4. **Point of view survives** (SCREEN.md §3.7). In a scene that belongs to
   one person, the camera is near him and sees what he sees; a shot that
   shows what he cannot know needs a reason.
5. **Inserts for the objects the story turns on**: a coin, a seal, a
   letter, iron bars. An insert of writing is held long enough to read it
   (§6).
6. **No cut between two near-identical framings.** Change the size or the
   angle by enough between consecutive shots of the same subject, or the
   cut "jumps"; Brown lists the 20% and 30-degree rules for this (ch. 4).
7. **Economy.** Setups in proportion to the scene's weight: a page of a
   boat arriving at night is five to ten shots, not thirty.
   [pipeline heuristic]

---

## 3. Moving the camera

**Sources.** Brown, ch. 16, "Motivated vs. Unmotivated Movement"; Katz;
look.yaml's camera rules.

Brown's principle (seen in a chapter abstract) is that a camera move
should be motivated, and the simplest motivated move is tracking with a
person who moves. A move the audience notices without a reason feels like
the film showing off.

**Rules the sources support.**

1. **A move answers to something in the scene**, written as its
   `motivation`: a person walks and the camera goes with them; a boat
   carries the camera; a reveal the story needs (we push in as he sees the
   bars); attention (we drift toward what he is staring at). Otherwise the
   camera is still (`static`).
2. **The speed matches the motive**: slow for a realisation, the pace of
   a walk for a walk.
3. **A camera on a moving vehicle moves with it** (`drift`): the motion
   is the vehicle's and needs no other motive.
4. **The look's "never" list is binding** (handheld shake, zooms, drone,
   whip pans, crane flourishes, orbiting, dutch angles in a film that
   forbids them). `shot-check` refuses those moves.

---

## 4. The line: axis, screen direction, eyelines

**Sources.** Mascelli (the action axis); Brown ch. 4, "The Action Axis",
"Screen Direction", "What Establishes the Line?", "Exceptions to the Rule",
"Neutral Axis to Exit Frame", "Cutaway Eyeline Continuity"; Daniel Arijon,
*Grammar of the Film Language* (1976), the line of interest and the
triangle of camera positions.

The **action axis** (Mascelli), the **line of interest** (Arijon), is an
imaginary line along a traveller's path or between two people facing each
other. While the camera stays on one side of it, a person who is on the
left stays on the left, two people looking at each other look in opposite
directions, and a traveller keeps moving the same way across the screen.
Crossing it between two shots swaps their sides and reverses the
direction: the audience sees the traveller turn back, or the two people
change places. Arijon's camera positions for two people form a triangle
whose base runs parallel to the line, all on one side of it.

**Rules the sources support.**

1. **Declare the axis** for each scene (`axis`): what it runs between, and
   which side is `A`. Every shot says its side (`line_side`: `A`, `B`, or
   `on_line` for a shot looking straight along the line).
2. **Stay on one side.** A cut from `A` to `B` is a cross. It is made
   legitimately in four ways (Brown's exceptions, paraphrased): a neutral
   shot on the line between the two; a cutaway to something else; the
   camera moving across the line within a shot; a person crossing it on
   screen. The shot that does it records how, in `crossing`.
3. **Screen direction** (`screen_direction`) is kept per mover: a traveller
   who leaves one shot frame right enters the next frame left. A shot
   toward or away from the camera is neutral and lets the next one go
   either way. A mover who turns round on screen, inside a shot (a dog
   hauled back up the steps it came down), may leave that shot the other
   way: the shot records the turn in `crossing`.
4. **Eyelines meet.** From one side of the line, a person looking at
   another looks the same way in every shot (`eyeline.looks` frame_left or
   frame_right), and two people looking at each other look opposite ways.
5. **Cut on action** where a movement carries across the cut (Mascelli;
   Dmytryk's rule "Cut on action whenever possible").

---

## 5. Continuity

**Sources.** Mascelli (continuity); Brown ch. 4 ("The Prime Directive");
the film bible's wardrobe by scene and props states.

Shots made separately must cut together as one continuous action: the same
coat buttoned the same way, the same object in the same hand, the same
hour and weather, the light from the same side. In a generated film every
shot is made separately, so continuity is a written contract checked
mechanically, not a script supervisor's memory.

**Rules the sources support.**

1. **Declare the state in every shot** (`continuity`): `wardrobe` per
   person, in the same words every time (copied from the bible's wardrobe
   for the scene), `props` with their state, `time`, `weather`, and the
   scene's `light` regime. `shot-check` compares each shot with the last
   one that named the same thing, and carries the state in from the scene
   before when this one is `CONTINUOUS`.
2. **A change has a reason** (`continuity_change`): the coat comes off on
   the steward's order; the cap is pushed back. A change without one is an
   error, however small.
3. **Match the bible.** The wardrobe is the bible's for that scene, and an
   object's state is the one `props.yaml` gives for that point in the story
   (a lining whole before the gate, slit after it).

---

## 6. How long a shot runs

**Sources.** David Bordwell, "Intensified Continuity" (*Film Quarterly*
55:3, 2002) and *The Way Hollywood Tells It* (2006); James Cutting, Kaitlin
Brunick and Jordan DeLong, "Quicker, faster, darker" (*i-Perception*, 2011);
Cutting and Ayse Candan Armstrong, "Facial expression, size, and clutter"
(*Attention, Perception & Psychophysics*, 2016); Dmytryk (via Thompson);
John August on page timing (SCREEN.md §7).

Average shot lengths in American films have fallen from "an ASL range of
8-11 seconds before 1960" to "a range of 4-6 seconds in recent years"
(Bordwell, 2006); Cutting's group measured "ASLs of about 10 s in the 1930s
and 1940s falling to below 4 s after 2000". Shot length follows size: from
"approximately 8 to 2.5 s from extreme long shots to extreme close-ups",
because "it takes time for the movie viewer to orient to a new shot and to
discern its content" (Cutting and Armstrong). Dmytryk's rule, as Thompson
summarises it: "Stay with a shot as long as that shot is the one which
best delivers the required information", and for an insert of text, "favor
the slow reader".

**Rules the sources support.**

1. **A shot runs as long as what plays in it**: its lines as spoken, with a
   breath before and a reaction after, or its action, whichever is longer,
   plus any deliberate hold. `shot-check --retime` computes it: lead
   (default 0.5 s) + the lines (with 0.3 s between them) + tail (0.7 s), or
   `timing.action_s`, plus `timing.hold_s`. [pipeline heuristic]
2. **Before a table read, a line is estimated** at about 150 words a
   minute with a quarter-second breath at each sentence end; the read
   replaces every estimate with the recorded length. An action paragraph is
   estimated at the page's rate (a printed line ≈ 1.1 s, a page ≈ a
   minute, SCREEN.md §7). [pipeline heuristic]
3. **A frame must be readable**: no insert or cutaway under 1.5 s, no
   establishing view under 3 s; a wide, busy frame needs longer than a face.
   [pipeline heuristic, after Cutting and Armstrong]
4. **The scene's total is checked against its page time.** Within ±10% is
   the target the milestone sets; a scene that runs longer gives its action
   room the page didn't (say so), or pads. A slow period drama's shots run
   4–10 s, nearer the classical norm than today's 3–6 s (Bordwell).

---

## 7. Light in the frame

**Sources.** Brown, ch. on "Practicals and Motivated Lighting" and
"Motivated Light" (4th ed.); Brown (1st ed., 2002): "the strong
directionality of the light guides the eye and unifies the composition.
What is unimportant falls into shadow and thus does not distract the eye";
John Alcott on *Barry Lyndon*, *American Cinematographer*, March 1976 (as
transcribed: scenes "lit entirely by the candles", shot on "50mm f/0.7
Zeiss still-camera lenses" with "hardly any depth of field"); look.yaml's
night and day lighting.

**Rules the sources support.**

1. **Every source is motivated**: a lantern, a candle, a hearth, a window,
   the sky, in the frame or plainly just off it. Write it in the shot's
   `light`.
2. **Light falls off.** A flame lights a face from one side and a few
   metres of wall; beyond that is dark. A night frame where whole façades
   are evenly lit reads as electric floodlight, the commonest error of a
   generated night (the inverse-square law; look.yaml's night rules).
3. **Only what the period had.** In a period film, every source is one
   the date allows; the look lists them and what they must never look like.
4. **Shadow is composition**: what is unimportant falls into it (Brown).

---

## 8. Keyframe prompts for an image model

**Sources.** Black Forest Labs, "Prompting" guide for FLUX 3 Image
(docs.bfl.ai): "FLUX 3 Image has no negative prompt field"; "If a negative
instruction gives an unwanted result, describe the intended scene
directly"; its example turns "no modern elements" into "traditional",
"historical", "period-accurate"; BFL's help article on FLUX.2 ("describe
exactly what you want to see"). Conwell, Tawiah-Quashie and Ullman (arXiv
2411.17066, 2024): "The negation probes and numbers (beyond 3) fail most
frequently."

**Rules the sources support.**

1. **Describe what is there, never what is not.** "No railings" draws
   railings. Write "a bare plank deck open at the edges"; for "no street
   lamps", write "the only light is the lantern at the bow". The bible's
   negative lists are for the critic and the vision check, not the prompt.
2. **One frame, one moment.** A keyframe is a still: the shot's key
   instant (the hand flat on the coat, the dog's head under the hand), not
   its whole action.
3. **Write the frame as the DP would**: size and angle, lens and depth of
   field, where each person stands in the frame and which way they face,
   the light's source and side and how fast it falls off, the palette for
   the hour, the film stock's texture; then the place as it stood at the
   date, from the location's file.
4. **People from their sheets.** Condition each person on their reference
   sheet (front, three-quarter, profile; the view nearest the shot's
   angle), and keep their identity lock in words too: the model holds
   faces better than clothes, so the costume is described every time.
5. **Few people, few numbers.** Models miscount past three and blur
   crowds; name the people the shot needs and let the rest be shapes.
6. **Faces that speak are expensive.** A face whose mouth must match a
   line is the costliest thing to render later (lip-sync); show speakers
   from behind, in silhouette or wide where the moment allows, and keep
   close-ups of speaking mouths for the moments that need them.
   [pipeline heuristic]

---

## 9. Storyboard, vision check and animatic

**Sources.** Katz (storyboards as the director's plan of every shot before
the shoot); Disney's Leica reel, which "filmed and edited storyboards to
the film soundtrack" (Wikipedia, "Previsualization"); the animatic as "a
sequence of still images (usually taken from a storyboard) displayed in
sync with rough dialogue" (Wikipedia, "Animatic", after Kelly Gordon
Brine, 2020); Pixar's story reels, which let a small team "iron out the
story problems so we don't discover, halfway through animation, that
things don't work" (Derek Thompson, story artist, interviewed by Rotten
Tomatoes).

**The vision check of every keyframe** reads the frame beside its shot and
the sheets of the people in it, and answers:

1. **Spec**: is it the shot's size and angle; are the people in `in_frame`
   there, where `blocking` puts them, facing the way it says; is the
   shot's action at its key instant; is the light from the stated source
   and side?
2. **Identity**: is each person the one on their sheet (face shape, nose,
   eyes, hair, build) in the scene's wardrobe? An animal too.
3. **Period**: nothing later than the date: the location's
   not-at-this-date list and the look's never lists (for a 15th-century
   street: railings where there were none, metal downpipes, glazed modern
   windows, electric or even light, later buildings, later boats, later
   dress, modern haircuts).
4. **Artefacts**: extra or missing fingers and limbs, doubled people,
   writing that isn't writing, warped architecture.

The verdict is `keep`, `regenerate` (with a revised, positive prompt or a
new seed) or `author`. A frame is regenerated at most twice; a third
failure goes to the author with the reason, because a fourth roll of the
same dice is not judgement. `keyframe-verdict` enforces the count.

**The animatic** cuts the keyframes to the table read: each still held for
its shot's duration, with the shot list's moves done as slow pushes and
pans on the still, the recorded lines placed where the shot list says
they fall, and the place's sound under them. It is the cheapest place to
judge pace and staging. Its viewer check, from sampled frames and the
transcript (not the cut list), asks: where are we and who is who; what
happens and what changed; where does it drag or rush; is any frame
unreadable at its length.

---

## 10. The director/DP rubric

The critic scores ten dimensions from 1 to 10 and runs the tests CT1–CT12.
Anchors for every dimension: **9–10** a shot list a crew could shoot from
tomorrow; **7–8** sound, the notes are polish; **5–6** it works but with a
fault the notes name; **4 or less** fails at what the dimension asks.

| Dimension | What it asks | Section |
|---|---|---|
| `coverage` | the scene can be cut: every line and action paragraph in a shot; an establishing view or master; inserts for what the story turns on | §2 |
| `storytelling` | every shot has a job; size follows the drama; the turn gets the shot sized to carry it | §1, §2 |
| `point_of_view` | the camera stays with the scene's viewpoint; what he can't see, we don't | §2.4 |
| `geography` | a viewer knows where everyone is; the line is held or crossed on screen | §4 |
| `motivated_movement` | every move answers to something in the scene; otherwise still | §3 |
| `rhythm` | sizes and angles vary; no jump between near-identical framings; durations fit what is read | §2.6, §6 |
| `continuity` | wardrobe, props, time and light match the bible and carry shot to shot | §5 |
| `light_and_period` | the look's lenses, heights and moves; every source motivated and of the period; nothing later than the date in frame | §7, look.yaml |
| `economy` | no shot without a job; setups in proportion to the scene's weight | §2.7 |
| `makeability` | each frame can be described to an image model; speaking faces few, close mouths only where needed | §8 |

**The tests.** Each is `pass`, `fail` or `n/a` with one line of evidence.

- **CT1** `shot-check` reports no errors.
- **CT2** Every line of the scene is heard in one shot, and every action
  paragraph is shown or its omission has a reason.
- **CT3** Every shot's `purpose` names what the audience learns or feels.
- **CT4** Every move's `motivation` names something in the scene.
- **CT5** The line is held, and any cross is made on screen and recorded.
- **CT6** The opening shots establish where we are and who is where, or the
  withholding is deliberate and said in `coverage_plan`.
- **CT7** The scene's turn is in a shot sized and held to carry it.
- **CT8** The viewpoint is kept.
- **CT9** The look is kept: lens set, stops, frame rate, camera height and
  moves; night lit only by the period's sources.
- **CT10** Continuity matches the bible's wardrobe and props for the scene
  and carries shot to shot.
- **CT11** Every duration is computed from the lines and the action, and
  the scene runs within ±10% of its page time or the notes say why.
- **CT12** The shots can be made: few speaking faces, close mouths only
  where the moment needs them, and no frame that asks an image model for a
  crowd it cannot count.

**The gate.** A shot list is ready for the storyboard when no dimension is
below 7 and every test passes or is `n/a` with a reason.
`/autonovel:shot-list` revises until it is, for at most three rounds, and
reports what is left.

---

## 11. Folklore: rules that aren't

- **"Never cross the line."** It is crossed on screen all the time; what
  breaks the audience's map is crossing it between two shots without one of
  the four legitimate moves (§4.2).
- **"Every scene needs a master."** A habit of coverage, not a law: a scene
  told entirely from one person's point of view may withhold the wide view
  on purpose (§2.2), and say so.
- **"Faster cutting is more exciting."** Average shot length tracks the
  era and the genre (§6); a period drama's held frame is its payload.
- **"Move the camera to keep it interesting."** Brown's rule is the
  opposite: an unmotivated move is noticed (§3).
- **"Add a negative prompt for everything wrong."** The model has no
  negative prompt; describe the right thing (§8).

---

## Sources

- Mascelli, Joseph V. *The Five C's of Cinematography: Motion Picture
  Filming Techniques Simplified*. Cine/Grafic Publications, 1965; reprint
  Silman-James Press. <https://silmanjamespress.com/the-five-cs-of-cinematography/>;
  the point-of-view passage (p. 22) as quoted at
  <https://en.wikipedia.org/wiki/Point-of-view_shot>.
- Katz, Steven D. *Film Directing Shot by Shot: Visualizing from Concept
  to Screen*. Michael Wiese Productions, 1991; 25th anniversary ed. 2019.
  <https://mwp.com/?p=3319>
- Brown, Blain. *Cinematography: Theory and Practice*. 4th ed. Routledge,
  2022 (contents: <https://urn.ub.unibe.ch/urn:ch:slsp:zbz:0367373459:ihv:pdf>);
  1st ed. Focal Press, 2002 (sample chapter:
  <https://booksite.elsevier.com/samplechapters/9780240805009/9780240805009.PDF>).
- Arijon, Daniel. *Grammar of the Film Language*. Focal Press, 1976;
  Silman-James, 1991. <https://archive.org/details/grammaroffilmlan00dani>
- Murch, Walter. *In the Blink of an Eye: A Perspective on Film Editing*.
  2nd ed. Silman-James Press, 2001 (the rule of six as quoted at
  <https://videoandfilmmaker.com/wp/?p=3459>).
- Dmytryk, Edward. *On Film Editing*. Focal Press, 1984 (rules as
  summarised by Peter Thompson:
  <https://www.mariamghani.com/docs/dmytryk_eisenstein.pdf>).
- Bordwell, David. "Intensified Continuity: Visual Style in Contemporary
  American Film." *Film Quarterly* 55, no. 3 (2002): 16–28; *The Way
  Hollywood Tells It* (2006), quoted at
  <https://cinemetrics.uchicago.edu/article/5dcb488e-0f5c-4a5c-824b-a052518861ba>.
- Cutting, James E., Kaitlin L. Brunick and Jordan E. DeLong. "Quicker,
  faster, darker: Changes in Hollywood film over 75 years." *i-Perception*
  2, no. 6 (2011): 569–576. <https://pmc.ncbi.nlm.nih.gov/articles/PMC3485803/>
- Cutting, James E., and Ayse Candan Armstrong. "Facial expression, size,
  and clutter: Inferences from movie structure to emotion judgments and
  back." *Attention, Perception & Psychophysics* 78 (2016): 891–901.
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC4819543/>
- Lightman, Herb A. "Photographing Stanley Kubrick's *Barry Lyndon*."
  *American Cinematographer*, March 1976 (interview with John Alcott;
  <https://theasc.com/articles/flashback-barry-lyndon>; the passages quoted
  as transcribed at <https://groups.google.com/g/alt.movies.kubrick/c/MRSijuYQFYU>).
- Black Forest Labs. "Prompting" (FLUX 3 Image).
  <https://docs.bfl.ai/guides/prompting_unified_technical>; "Does FLUX.2
  support negative prompting?"
  <https://help.bfl.ai/articles/7734566352-does-flux-2-support-negative-prompting>
- Conwell, Colin, Rupert Tawiah-Quashie and Tomer Ullman. "Relations,
  Negations, and Numbers: Looking for Logic in Generative Text-to-Image
  Models." arXiv:2411.17066, 2024. <https://arxiv.org/abs/2411.17066>
- "Previsualization" (Disney's Leica reel) and "Animatic." Wikipedia.
  <https://en.wikipedia.org/wiki/Previsualization>;
  <https://en.wikipedia.org/wiki/Animatic>
- Thompson, Derek (Pixar), on story reels. Rotten Tomatoes, "The
  storyboards of WALL-E."
  <https://editorial.rottentomatoes.com/article/exclusive-the-storyboards-of-walle/>
