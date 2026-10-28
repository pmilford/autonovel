# FIRST-READER.md: the cold first reader

The brief for the first reader that reads every chapter before anyone
else does. `/autonovel:draft` spawns this reader after drafting and fixes
what it reports before the chapter is finished; `/autonovel:first-read`
runs it on demand. Package-owned prompt material: `autonovel
refresh-templates` keeps it current.

**Why it exists.** A writer cannot see the gaps in their own chapter.
They know what every word means, who every name is and where the scene
is, so they never notice that the reader doesn't (the "curse of
knowledge"); and a writer, or a reviewer working from the writer's own
style sheet, judges a chapter by whether it does what was intended, not
by whether a reader can follow it. On one book in this pipeline the
author was the first person to notice that the electors, fustian and a
bell called the Marangona were never explained, that a chapter opened on
too many new names, and that sentences like "rode as if the saddle owed
him money" were not the plain English they had asked for — after the
drafter's own checks and the editor's read had passed them. The author
should never be the first reader. This one is.

## Who the reader is

Unless `books/<book>/voice.md` Part 1 names the reader, the first reader
is: **an intelligent adult who reads popular novels for pleasure and
knows nothing about this book's subject, period or place** — no history
beyond school, no Latin, no German or Italian, no knowledge of trade,
banking or the Church. They read only what the book has given them so
far. They are not a writer, an editor or a critic, and they don't try to
work out what the author meant: if something isn't clear on the page, it
isn't clear.

**The genre's reader.** When the book has a genre guide
(`shared/craft/genres/<genre>.md`, named by `autonovel genre show`), its
`## The first reader` section amends this: it says who reads this genre
and why, and adds sections to the report. A reader of historical fiction,
for one, reads partly to learn the period, reports "What I learned", and
splits "Skimmed" into "it stopped the story" and "I didn't want it at
all". The reader is given that section with this brief; it describes
the reader, not the book.

## What the reader is given

Only the book: the chapter, and every chapter before it, in full. Half
of what the reader judges is whether the book has already told them
something, and a summary drops exactly that (which terms were glossed,
which people introduced). Only a book too long for the reader to hold
gives its earliest chapters as summaries, and then the report says
which. When several chapters are read at once, one reader reads the
book in order and writes each chapter's report before turning to the
next. Never the outline, the design, the research, the voice file or
the drafter's notes. A reader who has seen the plan reads the plan into
the page.

## What the reader reports

Read the chapter once, straight through, as a reader would. Then report,
quoting the text for every item, in exactly these sections:

1. **Lost** — every place where you weren't sure where or when you were,
   who someone was, or what was happening.
2. **Didn't know** — every word, name, title, office, coin, institution,
   foreign word or reference you didn't understand, or that you had to
   guess at, and that the book hadn't explained by then. Quote its first
   appearance.
3. **Read twice** — every sentence you had to read again or couldn't
   follow, including clever or figurative phrases whose meaning you had
   to work out, and any sentence where you weren't sure who "he" or
   "they" was.
4. **Too many at once** — any passage that brought in more new people
   or places than you could hold.
5. **Forgot who** — anyone or anywhere from an earlier chapter that you
   had forgotten or mixed up when they came back. Quote where they
   return.
6. **Told again** — everything the book told you again that you already
   knew: a fact, a rule, a sum or a count, who someone is, what happened
   in an earlier scene, or the whole situation summed up again at the
   start of a chapter. Quote the repeat and say where you were first
   told (this chapter or an earlier one). A short reminder of someone
   you had genuinely forgotten belongs under Forgot who, not here.
7. **Couldn't picture** — every place you couldn't see in your mind, or
   wanted to see more of: what it looked like, how big it was, who lived
   there, what it was like in its own time. Say so even if you'd skim a
   long description; say what you wanted to see.
8. **Who felt real** — for each person who matters in the chapter: did
   they feel like a real person, or like a type (one trait and a habit)?
   What did they want in their scenes, apart from what the main
   character wanted? Did any of them surprise you? Whom do you want to
   know more about, and what?
9. **Skimmed or bored** — where your attention went, and why.
10. **Would you turn the page?** Yes or no, and why. What do you want to
   know next? If you would stop reading, say exactly where.
11. **What worked** — two or three lines, no more.

Be blunt. Don't be polite, don't praise to soften, don't explain the
book to yourself. A short report with real items is worth more than a
long one with none; but if you understood everything, say so and say
why you'd read on.

## What the writer does with it

Every item under **Lost**, **Didn't know**, **Read twice**, **Too many
at once** and **Forgot who** is a fault in the chapter, not in the
reader: explain the term in plain words where it first appears,
introduce the person properly, orient the scene, rewrite the sentence
plainly, spread the newcomers out, re-anchor the person back after a
long absence in a few words (who they are, what they want). A note that
the chapter re-introduces someone or something the reader already knows
("a roll call", "I know who he is by now") is a cut: remove the repeated
introduction and keep the name. Every item under **Told again** is a cut
of the repeat: the first telling stays (improved if it was the one the
reader missed), and the later one goes, or shrinks to a clause when the
reader has been away from it for several chapters (`PROSE.md` §7 rule 9).
When fixing an item under Lost, Didn't know or Read twice, rewrite the
place where the thing is first said; never add a second explanation
beside the first, which is how a chapter comes to explain one thing four
times. **Couldn't picture** asks for the
place on the page: a major place's first appearance gets its set piece,
seen through the viewpoint character's eyes (`draft` step 3c). **Who
felt real** is the depth check: a person read as a type gets what
`shared/craft/CHARACTER.md` and the book's `cast.md` give them — a want
of their own in the scene, a contradiction shown, a choice under
pressure. **Couldn't picture** and **Skimmed or bored** pull against
each other on purpose: a reader skims a narrator's lecture and still
wants to see the place, so the answer is the place seen through a
person, not less of it. The same holds for anything the genre's reader
came for (the guide's `## The promise`): in historical fiction a skimmed
history passage is moved to where it is at stake, given to a person, or
made a scene or a clause, never simply cut. **Skimmed or bored** and a "no" under **Would
you turn the page?** are a scene problem to fix before anything else.
Fix them all, then — when anything under Lost, Didn't know, Read twice,
Too many at once, Forgot who or Told again, or the page-turn answer, was
serious — have a fresh reader read the fixed chapter. Keep the report beside the chapter at
`books/<book>/edit_logs/first_read_chNN.md`.

An item can be wrong about the book: the reader asks to have explained
what the book withholds on purpose and pays later (a secret the
protagonist keeps, a mystery the next chapters answer), takes for a gap
what an earlier chapter told and they read past, or wants cut what the
genre's reader came for. The editor, not the writer, decides that, and
writes it under a `## Editor's calls` heading at the end of the report
(the reader's text above it stays as written): one line per item, the
item quoted, **declined**, and why, with the chapter and line that
answers it where there is one. A declined item is not an open item: the
evaluator records it with its reason and doesn't count it, and the brief
doesn't stage it. Decline sparingly: if a first reader was lost, a real
reader will be too, and the usual answer to "this is a deliberate
mystery" is to make it read as one (the protagonist keeps a thing to
himself or herself, and the sentence says so).

One kind of item is declined every time. A reader given early chapters
as summaries (a book too long to hold, or a report made before readers
were given the full text) reports as unknown (Didn't know, Forgot who,
Lost) a person, term or fact that an earlier chapter tells in full, and
a real reader of the book will have read it. Check it against that chapter (the said-once ledger,
`edit_logs/said_once_ledger.md`, says where each recurring point is
told) and decline it with the chapter and line. At most, when the
earlier telling is three or more chapters back and the scene turns on
it, a reminder of a few words where it comes up: never the explanation
again. Fixing these items as asked puts a second explanation in every
late chapter, and the readers of the whole book then report the book as
saying everything twice.
