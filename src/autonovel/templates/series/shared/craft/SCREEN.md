# SCREEN REFERENCE

How a passage of a novel becomes pages of a screenplay that a director,
an actor and an audience who never read the book can all follow. This is
the screen companion to PROSE.md and DESIGN.md: they say how a book is
written and built; this says what changes when the same story has to be
photographed and spoken. Each rule names its source, so it can be checked
against the book or page it came from rather than argued about.

`/autonovel:screenplay` reads this file in full every run; its screen
critic scores against §8 and its cold reader works from §9. The later
film stages (`docs/film-pipeline-plan.md`) read the sections they name.

**Precedence.** `books/<book>/voice.md` decides the register of the
dialogue (§6 says how to carry it to the screen). The book's genre guide
(`shared/craft/genres/<genre>.md`, its `## On screen` section) says what
that genre's audience comes for and must not lose; in historical fiction
that is the period itself. The book's `canon.md` and `cast.md` decide the
facts and the people. This file decides the medium's craft.

**What is sourced and what is not.** Rules the sources support are
listed under each section. Where the pipeline adds a threshold the
sources do not give, it says so in square brackets: `[pipeline
heuristic]`. §10 lists screenwriting "rules" that turn out to be folklore.

---

## 0. The card

Read this before writing or judging any page.

1. **Fountain is the source; the page is a contract** (§1). Every scene
   heading `INT.`/`EXT.` + place + time; every speaker in the cast or
   under `Roles:`; `autonovel mechanical fountain-check` clean.
2. **Every scene turns** (§2). Its last moment differs from its first,
   and the synopsis line says how. Who wants what, what if they don't get
   it, why now.
3. **Write what the camera can see and the microphone can hear** (§3).
   An inner state gets an outward sign. Objects carry the story.
4. **Tell the audience what is at stake before the scene that spends it**
   (§3.4). Suspense needs information.
5. **A line of dialogue is a move** (§4): it tries to get something.
   Compress; no telling a listener what they know.
6. **Adapt, don't transcribe** (§5). Keep every cardinal event; carry
   what the narrator said by behaviour, object, line, invented scene, and
   only last by voice-over. Add no new named people. Record every change
   and its reason.
7. **The period speaks plainly** (§6): neither fake antique nor modern
   slang; texture from what people talk about.
8. **A page is about a minute; count it in eighths** (§7).
9. **A stranger must be able to follow it** (§9): who, where, when and
   what is at stake in every scene, from the page alone.

---

## 1. Format: the page is a contract

**Sources.** The Fountain syntax (fountain.io); the National Film
Institute's screenplay-format guide; the print profile of afterwriting,
the open-source Fountain tool; Christopher Riley, *The Hollywood
Standard* (2nd ed., 2009), the reference most format guides follow;
John August and Dave Trottier ("Dr. Format") on foreign-language
dialogue.

A screenplay's format is not decoration. It fixes the time a page takes
on screen (§7), lets a production break the script down by place, time
and cast, and lets a reader skim it at the speed a film plays. Fountain
is plain text with a small grammar: "A Character element is any line
entirely in uppercase, with one empty line before it and without an
empty line after it"; a scene heading begins `INT`, `EXT`, `EST`,
`INT./EXT`, `INT/EXT` or `I/E`; a line starting `=` is a synopsis and a
line starting `#` a section, both "omitted from formatted output"; notes
go in `[[ ]]` and discarded text in `/* */`; the title page is
`key: value` lines, and "unsupported keys are ignored" (Fountain).
The printed page is Courier 12 point with a 1.5-inch left margin and
1-inch right, about 55 lines; dialogue starts 2.5 inches from the left
edge, parentheticals 3.1, the character cue 3.7 (NFI). afterwriting's US
letter profile fits 61 characters to an action line, 36 to a dialogue
line, 26 to a parenthetical and 55 lines to a page.

Spec scripts (the ones read before anyone is hired) carry no scene
numbers and almost no camera directions: "Spec scripts generally omit
camera directions" and "avoid unnecessary transitions like CUT TO"; a
new scene heading is enough (NFI). Parentheticals are used "sparingly",
only when a line "could otherwise be read in a way that contradicts the
scene", or for a small action or the person addressed (NFI). Action
blocks longer than three or four lines are broken up (NFI). Speech in a
language the audience doesn't share is written in the reader's language
with a parenthetical such as `(in Italian)`, or set off by a note at the
first instance, so the reader gets the experience the audience will
(Trottier; the practitioners' consensus). When the viewpoint character
does not understand a language, the audience shouldn't either: mark it
`(in Venetian; not subtitled)` and let the scene show what he makes of
it.

**Rules the sources support.**

1. The Fountain file is the source. The PDF (Courier 12 pt, the margins
   above) and the Final Draft `.fdx` are built from it by `autonovel
   mechanical fountain-check`; nobody edits the exports.
2. A **scene heading** for every change of place or of continuous time:
   `INT.` or `EXT.`, the place, ` - `, the time of day (`DAY`, `NIGHT`,
   `DAWN`, `DUSK`, `MORNING`, `EVENING`, `CONTINUOUS`, `LATER`). Name a
   place the same way every time, broad to narrow (`INT. FONDACO - LONG
   HALL - NIGHT`): the breakdown and every later stage key on it.
3. **Action** in the present tense, only what can be seen and heard, in
   paragraphs of no more than four lines. A new paragraph for each new
   image: each one reads as a shot.
4. A **character** is introduced in capitals at their first appearance,
   with an age and one concrete detail that says who they are, not an
   inventory of features. Their **cue** is the same every time, and one
   person has one cue (the screen form of `cast.md`'s one-label rule).
5. **Extensions:** `(V.O.)` for a voice not in the scene's space (a
   remembered voice, a letter in its writer's voice, narration);
   `(O.S.)` for someone in the space but off screen.
6. **On-screen text:** `SUPER:` for a date and place (the book's
   dateline); `INSERT` for a document the audience must read, then `BACK
   TO SCENE`. These are the two camera directions a spec may use, because
   the story depends on them.
7. **Languages:** the script's language stands for the characters' own
   (German characters speak English on the page). Any other language is
   marked at the line with a parenthetical saying which and whether it
   is subtitled. A few period words stay in their own language when the
   scene makes them clear (§6.4).
8. **autonovel's conventions**, all legal Fountain and all left off the
   printed page:
   - title page keys `Title:`, `Credit:`, `Author:`, `Source:`, `Draft
     date:`; `Roles:` with nothing after the colon and, on the indented
     lines under it, the speaking parts that are roles, not named people
     (`CARTER`, `INNKEEPER`); and `First minute: <scene ID> — <why>`, the
     scene to render first. A key with its value on the same line takes
     no lines under it, or the title page prints as action;
   - under each scene heading, one synopsis line
     `= <ID> | <source> | <turn>`: the scene ID (`S` + two-digit
     sequence + two-digit scene, `S0103`), where it comes from in the
     book (`ch_02:141-147`, several joined by commas, or `invented`), and
     what changes in it (`hidden coins -> owes the steward 31 ducats`).
     `fountain-check` builds `film/scenes.json` from these lines.

**Checks.** `autonovel mechanical fountain-check <file>` reports every
heading without `INT.`/`EXT.` or a time of day, every speaker in neither
the cast nor `Roles:`, one person under two cues, scene IDs missing or
repeated, action blocks over four lines, and the length of each scene in
eighths of a page.

---

## 2. The scene is a unit of change

**Sources.** Robert McKee, *Story* (1997); David Mamet, memo to the
writers of *The Unit* (19 October 2005); William Goldman, *Adventures in
the Screen Trade* (1983); Billy Wilder's ten tips, in Cameron Crowe,
*Conversations with Wilder* (1999).

McKee: "A scene is an action through conflict in more or less
continuous time and space that turns the value-charged condition of a
character's life on at least one value with a degree of perceptible
significance" (*Story*, p. 35). If the value at the end of a scene is
the value it opened with, nothing happened: the scene is a "nonevent"
that exists to deliver exposition. A sequence is a run of scenes,
usually two to five, that ends in a greater change than any one of them.

Mamet put the same test as three questions: "WHO WANTS WHAT? WHAT
HAPPENS IF [THEY] DON'T GET IT? WHY NOW?" "EVERY SCENE MUST BE DRAMATIC.
THAT MEANS: THE MAIN CHARACTER MUST HAVE A SIMPLE, STRAIGHTFORWARD,
PRESSING NEED WHICH IMPELS HIM OR HER TO SHOW UP IN THE SCENE." And:
"THE AUDIENCE WILL NOT TUNE IN TO WATCH INFORMATION."

Goldman's advice, much repeated, is to come into a scene as late as you
can, with the action already going, and leave as soon as it has turned.
Wilder (after Lubitsch): "Let the audience add up two plus two. They'll
love you forever."

**Rules the sources support.**

1. Every scene turns. The synopsis line names the value at its start and
   at its end; if they are the same, merge the scene into a neighbour or
   cut it.
2. For the scene's main character (often not the one with the most
   lines) you can say who wants what, what it costs them to fail, and
   why it has to be now.
3. Enter late, leave on the turn. No arrivals, greetings or goodbyes
   unless they are the scene.
4. A sequence asks its own question in its first scenes and turns it in
   its last; its scenes build, each one changing the situation the next
   one starts in.
5. Information comes out under pressure, from someone who needs to tell
   it or is trying to hide it, never because the audience needs it.
6. Leave out the explanation the action already gives (Wilder's two plus
   two).

**Checks.** Read each synopsis turn: is the second half different from
the first? Cover the dialogue: is the change still visible?

---

## 3. Visual storytelling: write what the camera can see

**Sources.** Mamet's memo; François Truffaut, *Hitchcock* (1967), the
bomb under the table; George Bluestone, *Novels into Film* (1957);
Alexander Mackendrick, *On Film-making* (2004), recounting Clifford
Odets.

Mamet: "THE CAMERA CAN DO THE EXPLAINING FOR YOU. *LET* IT." "IF YOU
PRETEND THE CHARACTERS CANT SPEAK, AND WRITE A SILENT MOVIE, YOU WILL BE
WRITING GREAT DRAMA." Bluestone set out the difference the adapter
works against: he read "the novel as a conceptual and discursive form,
the film as a perceptual and presentational form" (as quoted in reviews
of the 2003 reprint). A novel can say what a man thinks; a film can only
show what he does, and let the audience infer the thought.

Hitchcock's distinction between surprise and suspense: a bomb that goes
off under a table gives the audience "fifteen seconds of surprise"; a
bomb the audience has been shown, ticking under the same dull
conversation, gives them "fifteen minutes of suspense". In an adaptation
the novel's narrator used to decide what the reader knew and when; on
screen that choice is the writer's main structural tool.

**Rules the sources support.**

1. **The silent-film test.** With the dialogue taken out, a viewer can
   still tell who wants what in each scene and what changed (Mamet).
2. **An inner state gets an outward sign:** what the hands do, where the
   eyes go, an object picked up or hidden, a choice made, a pause before
   a lie. "He realises" cannot be filmed; what he does because he
   realises can.
3. **Objects carry the story.** Show an object the plot will use before
   it is used (a coat's lining, a seal, a board of knives). An `INSERT`
   is how a screenplay makes the audience read a line of writing.
4. **Suspense needs information.** The audience knows what is at stake,
   and what the character is hiding, before the scene that spends it
   (Hitchcock). Decide, scene by scene, what the audience knows that the
   other characters don't.
5. **Places by what is done in them.** A city without wells is a man
   paying for a jug of water; a city whose money moves on paper is a
   banker writing while no coin changes hands. Orientation that can be
   seen needs no line of dialogue.
6. **Sound is half the picture.** Write the sound that carries story: a
   bell that opens a gate, water under a floor, a whispered count.
7. **Point of view survives.** A close-third novel becomes a film that
   stays with its viewpoint character: we are in the rooms he is in, and
   what he cannot understand (a language, a look between others) stays
   unexplained for the audience too.

**Checks.** List each piece of interior life the passage needs the
audience to grasp; for each, name the image, act or line that carries
it on the page. A blank is a fault.

---

## 4. Dialogue on screen

**Sources.** Mackendrick, *On Film-making* (Odets: play "the
situations, not the words"); Mamet's memo; Wilder's tips; Sarah Kozloff,
*Invisible Storytellers: Voice-Over Narration in American Fiction Film*
(1988).

Mackendrick took from Odets that a spoken line works best when the
actors play "not the words and their literal meaning but … the actions
that underlie them": dialogue is a form of action. Mamet: "ANY TIME TWO
CHARACTERS ARE TALKING ABOUT A THIRD, THE SCENE IS A CROCK OF S***." Wilder
warned that voice-over must add to what the audience is seeing, never
describe it. Kozloff argues against the idea that showing is always
better than telling: voice-over can give a film intimacy and irony. The
sources agree on economy, not on a ban.

**Rules the sources support.**

1. **A line is a move.** Each speech tries to get something from its
   listener: a fact, a favour, a reaction, silence. An exchange where
   nobody wants anything is cut or given a want.
2. **Compress.** A screen line is shorter than the book's; a speech of
   more than four lines is broken by action or cut. Keep the book's best
   lines word for word when they play aloud: read them aloud.
3. **No telling the listener what the listener knows**, and no two
   people discussing a third who could be on screen (Mamet).
4. **Subtext.** People say less than they mean; the action and the cut
   carry the rest.
5. **Each person sounds like themselves** (the book's `voice.md` Part 4,
   `cast.md` "Perception and voice"). Cover the cues: you can still tell
   who is speaking.
6. **Parentheticals** only to prevent a misreading, for a small action,
   or to say who is addressed (§1).
7. **Voice-over is the last resort for interior life** (§5.2), and in an
   adaptation preferably words a person in the story said, wrote or
   heard (a remembered line, a letter) rather than a narrator explaining.
   It never describes what is on screen (Wilder). [pipeline heuristic:
   at most one voice-over line per two pages of a sequence; none is
   better.]

**Checks.** Read every speech asking "what does the speaker want from
the listener with this line?" Mark lines whose answer is "to inform the
audience".

---

## 5. Adapting prose

**Sources.** Bluestone, *Novels into Film*; Brian McFarlane, *Novel to
Film: An Introduction to the Theory of Adaptation* (1996); Linda Seger,
*The Art of Adaptation: Turning Fact and Fiction into Film* (1992);
Robert A. Rosenstone, *History on Film/Film on History* (2006); Wilder;
Kozloff.

McFarlane separated what can be **transferred** from book to film from
what needs **adaptation proper**. Following Barthes, the story's
*cardinal functions*, the events "crucial to the working out of the
plot", and its *catalysers* (the small acts that fill the time between)
can be carried across; the novel's *enunciation*, the narrator's voice
and the viewpoint's inner life, cannot, and must be re-made in the
film's own means. Seger's work on condensing a book is the same advice
from the practitioner's side: drop secondary plotlines, merge or remove
characters, find a clear beginning, middle and end, and accept losing
scenes and people you like; and, where the book only implies a scene,
write the implied scene. Rosenstone, writing on historical films, named
the moves every such film makes: **compression** (several characters
become one), **condensation** (several events conflated),
**displacement** (an incident moved in time or place), **alteration** (a
character given another's words or sentiments) and **invention**. He
argues these are the legitimate means of history on film, provided they
serve what the record shows.

**Rules the sources support.**

1. **List the cardinal events** of the passage before writing. Every
   one reaches the screen, or its cut is recorded with the reason.
   Catalysers may go for length.
2. **Re-make the enunciation.** What the narrator explains or the
   viewpoint thinks is carried, in this order of preference: (a)
   behaviour; (b) an object or an insert; (c) a line to someone with a
   reason to hear it; (d) a small invented scene that dramatises it
   (Seger's implied scene); (e) voice-over (§4.7). The adaptation note
   says which.
3. **The change ledger** uses Rosenstone's moves. Each change is one of:
   `KEEP` (as in the book, said here only when it is a choice), `CUT`,
   `CONDENSE` (events merged), `COMPRESS` (people merged: count people
   on stage, not names), `DISPLACE` (moved in time or place), `ALTER` (a
   line or act given to another person), `INVENT` (a scene, line or
   object the book doesn't have) or `EXTERNALISE` (thought or narration
   made visible or audible). Every entry quotes the book, points to the
   scene, and gives the reason. An invention must carry something the
   prose told; it may not add a fact the canon lacks.
4. **Add no new named people.** A person the film needs who is not in
   the book's cast is a role (`Roles:`), described by what they do;
   roles with lines are few.
5. **Facts stay true to the book's canon**; invent only in its gaps,
   the same rule as the novel.
6. **Reorder only when cause and effect survive,** and plant before the
   payoff: if the book reveals a fact in hindsight, the film may need to
   show it first (§3.4).
7. **Orientation for a stranger.** The audience knows nothing; each place,
   office, coin or custom the scene turns on is made clear once, inside
   the action (§3.5), by a `SUPER:` for date and place, or by a guide
   character with a reason to explain.
8. **Length.** Budget pages from the adaptation plan (`film/adaptation.md`)
   when there is one; otherwise by the passage's share of the book.
   [pipeline heuristic: a scene-rich passage runs about a page of script
   per 500–700 words of prose; a reflective one far less.]

**Checks.** Lay the cardinal-event list beside the scene list: every
event has a scene or a `CUT` entry. Lay the adaptation note beside the
script: every difference a reader of both would notice has an entry.

---

## 6. Period dialogue register

**Sources.** Mark Liberman, "Period speech", *Language Log* (15 August
2010), quoting David Mitchell (*Fresh Air*, 5 August 2010) and recalling
Robert Louis Stevenson's word "tushery" and "Wardour Street English";
Ursula K. Le Guin, "From Elfland to Poughkeepsie" (1973); the book's
`voice.md`; the genre guide's `## Drafting` on people of their time.

Period dialogue is a made thing. Mitchell, as Liberman reports, steered
between speech that "could have been from a sitcom" and an accurate
reconstruction that turns into pastiche; what matters is the
impression of authenticity, held consistently, with characters of
different origins sounding different. Stevenson's "tushery" and
"Wardour Street English" name the fake-antique failure: *prithee*,
*forsooth*, *'tis*. Le Guin showed how a handful of modern words turns
a high scene into an office memo; the reverse failure.

**Rules the sources support.**

1. **The book's register governs.** If `voice.md` says plain modern
   English, the dialogue is plain modern English with contractions.
2. **Neither tushery nor sitcom.** No fake antique; no modern idiom,
   slang or psychology (*okay*, *deal with it*, *process this*).
3. **Texture from substance:** what people of the period talk about
   (prices, coins, saints' days, offices, the road), and how they address
   each other, not archaic grammar.
4. **A few period words stay**, when the scene makes them clear: a coin,
   an office, an insult, a form of address. The rest is translated.
5. **Voices differ by origin, rank and trade** (a carter is not a
   steward); one style, held throughout.
6. **Recorded words of real people,** when short and playable, are the
   best lines a historical script has.

---

## 7. A page is about a minute

**Sources.** John August, "Ratio of pages to screen time" (10 September
2003); NFI; afterwriting's print profile; production practice on
eighths (MasterClass; Filmustage).

August: "The very general rule is that a page in the script should
equal a minute of screen time"; "a page full of action would likely take
longer than a minute", and "a page of rapid-fire dialogue would be a lot
faster." Productions measure scenes in eighths of a page, each about an
inch of the page; fractions are not reduced (4/8, not 1/2), and eleven
eighths is written 1 3/8.

**Rules the sources support.**

1. **Count, don't guess.** `fountain-check` lays the Fountain out on the
   standard page (55 lines; 61 characters to an action line, 36 to
   dialogue, 26 to a parenthetical) and gives each scene's length in
   eighths. No scene is shorter than 1/8. The PDF's own page count is
   reported beside it.
2. **About a minute a page, on average;** action runs long, quick
   dialogue short (August).
3. **Budgets.** A sequence from one chapter's passage: about 5–12 pages.
   A feature: 100–120 pages (`docs/film-pipeline-plan.md` §2).
   [pipeline heuristic, from the plan.]
4. **Proportion.** A scene's length matches its weight in the story;
   a scene over three pages turns more than once or is split.

---

## 8. The screen rubric

The critic scores ten dimensions from 1 to 10 and runs the tests SC1–SC12.
Anchors for every dimension: **9–10** a professional script, ready to
shoot; **7–8** sound, the notes are polish; **5–6** works but with a
structural fault the notes name; **4 or less** fails at what the
dimension asks.

| Dimension | What it asks | Section |
|---|---|---|
| `format` | `fountain-check` clean; headings, cues, extensions, supers and languages as §1 | §1 |
| `scene_turns` | every scene turns, with a want, a cost and a now | §2 |
| `visual_storytelling` | the silent-film test; inner life shown; objects planted | §3 |
| `dialogue` | lines are moves; compressed; subtext; distinct voices; voice-over rare | §4 |
| `clarity` | a stranger knows who, where, when and what is at stake in every scene | §3.7, §5.7, §9 |
| `fidelity` | every cardinal event, true to canon, no new named people, every change recorded with a reason | §5 |
| `history_on_screen` | the genre's payload carried as action and image, nothing lost to pace (the genre guide's `## On screen`) | §5.7, genre guide |
| `period_register` | the book's register; neither tushery nor sitcom | §6 |
| `pace_and_length` | late in, early out; pages within budget; length matches weight | §2.3, §7 |
| `sequence_arc` | the sequence poses its question and turns it; scenes build | §2.4 |

**The tests.** Each is `pass`, `fail` or `n/a` with one line of evidence.

- **SC1** `fountain-check` reports no errors.
- **SC2** Every scene's synopsis turn names a change, and the page shows it.
- **SC3** Every scene answers Mamet's three questions for its main character.
- **SC4** With the dialogue covered, each scene's change is still visible.
- **SC5** Every piece of interior life the passage needs is carried
  (§5.2), and voice-over is within §4.7.
- **SC6** What the audience must know before each turn is on screen
  before it (§3.4).
- **SC7** No speech exists only to inform the audience; no "as you know".
- **SC8** Every cardinal event of the passage is on screen or recorded as
  `CUT` with a reason.
- **SC9** No new named person; every speaking role is in the cast or
  under `Roles:`; one cue per person.
- **SC10** Every place, office, coin and custom a scene turns on is clear
  once, inside the action; none of the period's payload was cut for pace.
- **SC11** The dialogue keeps the book's register (§6).
- **SC12** The adaptation note has an entry, with a reason, for every
  change a reader of both would notice.

**The gate.** A sequence is ready for the author when no dimension is
below 7, every test passes or is `n/a` with a reason, and the cold
reader's must-fix list (§9) is empty. `/autonovel:screenplay` revises
until it is, for at most three rounds, and reports what is left.

---

## 9. The cold reader of a script

**Sources.** Studio practice: script coverage, where a reader who knows
nothing of the project writes a logline, a synopsis, comments and a
verdict of pass, consider or recommend (*Script coverage*, Wikipedia);
the pipeline's own `FIRST-READER.md`.

The critic knows the book and SCREEN.md; the cold reader knows neither.
They read the script as an audience would meet the film, with nothing
else: not the book, not the adaptation note, not the critic's report.
The cold reader reports:

1. **The story in three sentences**, and the question the sequence
   leaves open.
2. **Scene by scene:** where and when we are; who each person on screen
   is and what they want; what changed. "I don't know" is an answer.
3. **Lost:** every word, name, place or custom they didn't understand,
   and every moment they couldn't tell who was speaking or why someone
   acted.
4. **Told twice or told too much:** what they already knew when the
   script told them again.
5. **Bored or crowded:** where they would look at their phone; where
   there were too many people at once.
6. **Would they watch the next sequence?** Yes or no, and why.
7. **Must-fix:** the items that stop a viewer following the story. The
   writer fixes every one, or says why it isn't a fault.

---

## 10. Folklore: rules that aren't

- **"Never use voice-over."** Kozloff's study and Wilder's own films
  (*Double Indemnity*, *Sunset Boulevard*) answer it. The rule is
  economy (§4.7).
- **"Never write *we see*."** A style preference. Prefer the plain
  image; the phrase is not a fault.
- **"Exactly a minute a page."** An average over a whole script (§7).
- **"Never use parentheticals."** They are for misreadings, small
  actions and addressees (§1).
- **"Cut everything that isn't plot."** In a genre whose audience comes
  for the world (the history, in historical fiction), the world is the
  payload. Move it into action; don't cut it (the genre guide's
  `## On screen`).

---

## Sources

- Fountain. "Syntax." <https://fountain.io/syntax/>
- National Film Institute. "Screenplay format."
  <https://www.nfi.edu/screenplay-format>
- afterwriting (Piotr Jamróz and contributors). Print profiles.
  <https://github.com/ifrost/afterwriting-labs/blob/master/js/utils/print-profiles.js>
- Riley, Christopher. *The Hollywood Standard: The Complete and
  Authoritative Guide to Script Format and Style*. 2nd ed. Michael Wiese
  Productions, 2009.
- Trottier, Dave. "Ask Dr. Format: Foreign Language and Subtitles."
  <https://screenplay.com/pages/ask-dr-format-foreign-language-and-subtitles>;
  August, John, on subtitled dialogue. <https://johnaugust.com/?p=201>
- August, John. "Ratio of pages to screen time." 10 September 2003.
  <https://johnaugust.com/?p=242>
- MasterClass. "How to break down a script."
  <https://www.masterclass.com/articles/how-to-break-down-a-script>;
  Filmustage. "What are eighths in a script?"
  <https://filmustage.com/blog/what-are-eighths-in-a-script-and-how-do-they-help-plan-production/>
- McKee, Robert. *Story: Substance, Structure, Style and the Principles
  of Screenwriting*. ReganBooks, 1997 (the scene definition as quoted by
  McKee's own site, <https://mckeestory.com/do-your-scenes-turn/>, and
  the Narrative Transformation Lab,
  <https://tntlab.carterschool.gmu.edu/learn/narrative-transformation-resources/narrative-themography/scene/>).
- Mamet, David. Memo to the writers of *The Unit*, 19 October 2005.
  <https://www.slashfilm.com/a-letter-from-david-mamet-to-the-writers-of-the-unit/>
- Goldman, William. *Adventures in the Screen Trade*. Warner Books, 1983.
- Crowe, Cameron. *Conversations with Wilder*. Knopf, 1999 (the ten
  tips: <https://openculture.com/2013/08/10-tips-from-billy-wilder-on-how-to-write-a-good-screenplay.html>).
- Truffaut, François. *Hitchcock*. Simon & Schuster, 1967 (the bomb:
  <https://nofilmschool.com/alfred-hitchcock-and-francois-truffaut-explain-surprise-vs-suspense>;
  David Bordwell on its history,
  <https://www.davidbordwell.net/blog/2013/11/29/hitchcock-lessing-and-the-bomb-under-the-table/>).
- Bluestone, George. *Novels into Film*. University of California
  Press, 1957; Johns Hopkins reprint, 2003 (review quoting p. ix:
  <https://www.screeningthepast.com/?p=6209>).
- Mackendrick, Alexander. *On Film-making: An Introduction to the Craft
  of the Director*. Ed. Paul Cronin. Faber, 2004 (the Odets passage:
  <https://www.criterion.com/current/posts/1762-mackendrick-and-odets>).
- Kozloff, Sarah. *Invisible Storytellers: Voice-Over Narration in
  American Fiction Film*. University of California Press, 1988.
  <https://muse.jhu.edu/book/26012>
- McFarlane, Brian. *Novel to Film: An Introduction to the Theory of
  Adaptation*. Clarendon Press, 1996 (reviewed in *Links & Letters* 6,
  1999, <https://ddd.uab.cat/pub/lal/11337397n6/11337397n6p145.pdf>; the
  cardinal functions: <https://www.screeningthepast.com/?p=6790>).
- Seger, Linda. *The Art of Adaptation: Turning Fact and Fiction into
  Film*. Henry Holt, 1992 (summary:
  <https://thescriptblog.com/how-to-make-film-adaptations-according-to-linda-seger/>).
- Rosenstone, Robert A. *History on Film/Film on History*. Pearson, 2006
  (its fictive techniques as used by filmmakers:
  <https://www.qub.ac.uk/sites/frankryan/Archivaldialogues>).
- Liberman, Mark. "Period speech." *Language Log*, 15 August 2010.
  <https://languagelog.ldc.upenn.edu/nll/?p=2554>
- Le Guin, Ursula K. "From Elfland to Poughkeepsie" (1973), in *The
  Language of the Night* (1979).
- "Script coverage." Wikipedia.
  <https://en.wikipedia.org/wiki/Script_coverage>
