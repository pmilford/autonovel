---
name: autonovel:first-read
description: A cold first reader — someone who knows nothing about the subject and has read the earlier chapters in full — reports every word, name or sentence they didn't understand, what they were told again, where they got lost, crowded or bored, and whether they'd turn the page. One chapter, or with --chapters one reader reads the book in order and reports on each chapter as it reaches it. Draft runs it on every new chapter; run it yourself on any chapter you've changed.
argument-hint: "<chapter-number> | --chapters <N,M,…|all> --book <short-name>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - task
  - bash
reads:
  - shared/craft/FIRST-READER.md
  - books/{book}/voice.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_*.md
  - books/{book}/chapters/ch_*.summary.md
  - shared/craft/genres/*.md
  - shared/genres/*.md
writes:
  - books/{book}/edit_logs/first_read_ch{chapter}.md
  - books/{book}/edit_logs/first_read_ch*.md
  - books/{book}/edit_logs/first_read_archive/*.md
context_mode: book
---

<purpose>
Find, before the author does, what a reader can't follow: the
unexplained word, the name with no introduction, the scene that never
says where or when it is, the clever sentence that has to be read
twice, the opening that crowds in six new people, the point the
chapter makes for the third time, the page where the reader stops. The writer can't see these in their own chapter (they
know what everything means), and a reviewer judging against the
writer's style sheet doesn't look. On one book the author found all of
them themselves, after every check had passed. The author should never be
the first reader.

The reader is a separate agent that sees only the book — the chapter
and what came before it — never the outline, design, research or voice
file. `shared/craft/FIRST-READER.md` is its brief.

The reader is given the earlier chapters **in full**, not as summaries,
whenever they fit. Half of what it judges is whether the book has
already told it something: a term glossed, a person introduced, a fact
explained. A 250-word summary keeps the plot and drops exactly those, so
a reader given summaries reports as unknown what the book told in full.
On one book a review round answered those items, and the next reader
panel found the book saying everything twice. A 120,000-word book is
about 180,000 tokens, which a heavy-tier reader holds.

`--chapters` is the cheaper way to read many chapters: **one** reader
reads the book from chapter 1 in order and writes each listed chapter's
report before turning to the next. It reads the opening chapters once
instead of once per chapter (a separate full-text reader of a late
chapter costs 250,000–300,000 tokens), but it reports less. Measured on
one book, on the same text: for two late chapters, a separate reader
with the full text found 15 and 13 points told again where the one
reader found 8 and 4, and the one reader's Lost, Couldn't picture and
Skimmed fell to none after the first few chapters (it settles into the
book). A reader given summaries did worst both ways: 8 of its 9
"didn't know" items were told plainly in chapters it saw only as
summaries, and it found 4 told-again points where the full-text reader
found 15. So the default is a separate reader per chapter, with the
full text; `--chapters` when the cost matters more than the last repeats.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`: `<chapter-number>`, or `--chapters <N,M,…|all>`
   (`all` is every drafted chapter), and `--book`. Missing a chapter or
   the book → stop with a one-line usage reminder. One chapter follows
   steps 3–5; `--chapters` follows step 4a instead.

2. Use `file_read` on `shared/craft/FIRST-READER.md` and on
   `books/{book}/voice.md` (Part 1's **Reader** line, if present, names
   the reader; otherwise use the brief's default reader). Then read the
   `## The first reader` section of the book's genre guide: the file
   `_begin`'s `genre:` line names (`autonovel genre show --book {book}`
   prints it when no preamble ran; it is
   `shared/craft/genres/<genre>.md`, or the series' own
   `shared/genres/<genre>.md`), when the book has one: it
   says who this genre's reader is (a reader of historical fiction reads
   partly to learn the period) and adds report sections. The voice
   file's Reader line still wins.

3. Gather what the reader may see: `books/{book}/chapters/ch_{chapter}.md`
   and every chapter before it, **in full**. Only when the earlier
   chapters together run over about 150,000 words (about 200,000 tokens)
   give the earliest ones as `books/{book}/chapters/ch_*.summary.md`,
   keeping in full as many of the nearest as fit, and head the report
   (step 5) with a line naming the chapters the reader had only as
   summaries: its "didn't know" items about those chapters are the
   context's, not the book's, and the editor declines them
   (`shared/craft/FIRST-READER.md`, the Editor's calls). Strip YAML
   frontmatter except each chapter's title and `dateline`.

4. Use `task` to spawn **one** fresh heavy-tier reader. Its prompt is
   the brief's "Who the reader is", "What the reader reports" sections
   (verbatim), the genre guide's `## The first reader` section
   (verbatim) when there is one, the reader line from voice.md if any, then the earlier
   chapters and the chapter. It must not be given anything else, and
   it must answer in the brief's eleven sections, quoting the text.

4a. **`--chapters`: one reader for the book.** First use `bash` to run
   `autonovel _archive-first-read --book {book} --chapter N` for each
   listed chapter (step 5's archive). Then use `task` to spawn **one**
   fresh heavy-tier reader with the same brief sections, genre section
   and reader line as step 4, and these instructions: read the book in
   order, from `books/{book}/chapters/ch_01.md` to the last listed
   chapter, one chapter at a time with `file_read`, ignoring each
   chapter's YAML frontmatter except its title and `dateline`, and open
   nothing else (no summary, outline, design, research, voice file, edit
   log or earlier report); after reading each listed chapter, and before
   opening the next, use `file_write` to save that chapter's report at
   `books/{book}/edit_logs/first_read_chNN.md` in the eleven sections,
   quoting the text, headed as step 5 says plus the line `Read as one
   reader of the whole book, in order.`; report on what it knew at that
   page and never go back to change an earlier report. A chapter not
   listed is read but not reported on. When the book up to the last
   listed chapter runs over about 150,000 words, run step 4 per chapter
   instead. When the reader has finished, check each report has the
   count line and the eleven sections, then use `bash` to run
   `autonovel _stamp-report --book {book} --report first_read --chapter
   N`, with one `--chapter N` for every listed chapter, and go to step
   6.

5. Use `bash` to run `autonovel _archive-first-read --book {book}
   --chapter {chapter}`, which moves the chapter's earlier reports (and a
   second reader's `_2` report on an older text, which evaluate would
   otherwise read as the latest) into
   `books/{book}/edit_logs/first_read_archive/*.md`, dated. Then use
   `file_write` to save the new report, unedited, at
   `books/{book}/edit_logs/first_read_ch{chapter}.md`, headed with the
   date and one count line: `lost N · didn't know N · read twice N ·
   too many N · forgot N · told again N · couldn't picture N · types N ·
   skimmed N · turn the page: yes|no` (types = the people it read as a
   type), plus
   `learned N` when the genre guide added "What I learned". Then use
   `bash` to run `autonovel _stamp-report --book {book} --report
   first_read --chapter {chapter}`, which records the text the reader
   read: `autonovel mechanical release-check` counts the report only
   while the chapter is that text or within a light fix of it, so a
   report on an older version never stands in for a reader of this one.

6. Report the count line (one per chapter with `--chapters`), the three most serious items (quoted), and
   **Next:** when there are items under Lost, Didn't know, Read twice,
   Too many at once, Forgot who, Told again, Couldn't picture or Who
   felt real, a
   "no" to the page turn, or an empty "What I learned" in a genre that
   adds it,
   `/autonovel:revise {chapter} --book {book}` with the report as the
   brief (or fix them by hand); otherwise "the chapter reads clean to a
   first reader". Do not edit the chapter here.
</workflow>

<acceptance>
- `books/{book}/edit_logs/first_read_ch{chapter}.md` exists with the
  eleven sections and the count line (with `--chapters`, one for every
  listed chapter, each stamped).
- The reader was given the earlier chapters in full (summaries only for
  the earliest chapters of a book over about 150,000 words, named in the
  report's header) and never the outline, design, research or voice
  file.
- The chapter is unchanged.
</acceptance>
