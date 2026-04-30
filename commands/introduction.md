---
name: autonovel:introduction
description: Generate or scaffold a preface (user-authored) and/or introduction (AI-generated) for the typeset front matter.
argument-hint: "--book <short-name> [--from auto|user|both] [--force]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/world.md
  - shared/characters.md
  - books/{book}/seed.txt
  - books/{book}/outline.md
  - books/{book}/voice.md
  - books/{book}/preface.md
  - books/{book}/introduction.md
writes:
  - books/{book}/preface.md
  - books/{book}/introduction.md
context_mode: book
---

<purpose>
Create the front-matter content `/autonovel:typeset` weaves into the
PDF and ePub. Two surfaces, written to two distinct files so they
can coexist (a real book often has both an Author's preface and a
separate Introduction or Foreword):

  - **`books/{book}/preface.md`** — hand-authored. The command
    scaffolds a starter template the user fills in (or leaves
    empty). Typical content: why the writer wrote the book, an
    acknowledgement of sources, a personal frame around the
    story.

  - **`books/{book}/introduction.md`** — AI-generated. The command
    drafts an essay-style introduction grounded in the book's
    actual themes (drawn from outline + seed + voice + canon).
    Typical content: positioning the work in its genre, naming
    the questions it asks, what kind of reader it expects. Always
    a draft to be edited — the writer reviews and revises before
    typeset.

Both files are optional. typeset's front-matter builder includes
whichever exist; novel.tex's `\IfFileExists{front_matter.tex}{...}{}`
guard skips inclusion entirely when neither was created.

Three modes selected by `--from`:

  - `--from user` (default): scaffold preface.md only.
  - `--from auto`: AI-generate introduction.md only.
  - `--from both`: do both.

`--force` permits overwriting an existing file (otherwise the
command refuses to clobber author content).
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Required: `--book <short-name>`. Optional:
   `--from <user|auto|both>` (default `user`), `--force`.

2. **Refusal-on-overwrite check.** For each file the chosen mode
   would write, check whether it already exists with substantive
   content (more than the template scaffold). If yes and `--force`
   was not supplied, stop with: "books/{book}/<file>.md already has
   content; pass `--force` to overwrite or hand-edit the existing
   file directly".

3. **Preface scaffold** (when `--from` is `user` or `both`). Use
   `file_read` on `project.yaml` to pull the book's display title
   for the heading. Write `books/{book}/preface.md` with this
   exact starter shape (the user replaces the bracketed
   placeholders) — note the inline HOW-TO-EDIT comments next to
   each section:

   ```markdown
   # Preface

   <!-- ============================================================
        HOW TO EDIT THIS FILE
        ============================================================
        Hand-authored. Speak as the author, in your voice. Typeset
        renders this as \chapter*{Preface} in the PDF and as a
        front-matter section in the ePub.

        - Replace each [bracketed placeholder] with real prose.
        - Delete sections you don't want; nothing here is required.
        - Total length: 200-700 words is typical. Two short pages.
        - DON'T summarise the plot — the cover blurb does that.
        - DON'T explain themes; let the book do that.
        - DO write in your natural voice (this is YOU, not the
          narrator).
        - The thanks paragraph goes LAST. Keep it generous but
          tight; long thanks lists exhaust the reader before
          chapter one.

        Delete this comment block when the prose is ready.
        ============================================================
   -->

   <!-- Section 1: Why this book exists.
        Concrete is better than abstract: a moment that started it,
        a problem that wouldn't go away, a question that needed
        twenty thousand words to answer. One paragraph, sometimes
        two. Personal. Not "this novel explores…" — that reads as
        marketing copy. Closer to "I started this book on a train
        from Lyon to Frankfurt in 2024 because…" -->

   [Why I wrote this book — one or two paragraphs. Personal. Not
   plot summary.]

   <!-- Section 2: Reader-orientation note (optional).
        Use IF the book needs framing the cover blurb can't carry.
        Examples:
          - "This book contains depictions of [content note].
            Skip pages 41-44 if you'd rather not."
          - "The dates use the Julian calendar; February 1492 here
            is March 1492 in modern reckoning."
          - "Read the chapters in order; the timeline is not
            chronological but the revelations depend on sequence."
        Skip this whole paragraph if you have nothing to add. -->

   [What the reader needs to know going in — a content note, a
   period framing, a recommendation about reading order. Optional.
   Skip this paragraph if you have nothing to add.]

   <!-- Section 3: The thanks paragraph.
        Comes LAST. People, places, sources. Keep it tight — two
        or three sentences each, not a list. Cite primary sources
        if research drove the work; name the human friends who read
        drafts. If Autonovel was substantively involved in
        drafting, this is the place to acknowledge that openly
        (e.g. "First drafted with the help of Anthropic's Claude
        via Autonovel; substantially revised by hand.").
        A paragraph or two at most. -->

   [The thanks paragraph: people, places, the long history of the
   book. Last; a paragraph or two at most.]

   <!-- Sign-off: town + year is conventional. Drop it if you'd
        rather sign just the name. -->

   — [Author], [City], [Year]
   ```

   This is a stub. The user's job is to make it real prose. Do
   NOT have the AI fill in the bracketed placeholders — the
   preface is the one piece of front matter that has to come from
   the writer.

4. **Introduction generation** (when `--from` is `auto` or `both`).
   Use `file_read` on `project.yaml` (genre, period), `seed.txt`
   (the writer's pitch), `outline.md` (chapter beats reveal what's
   actually at stake), `voice.md` (Parts 1 and 2 set the register
   the introduction must match), `shared/world.md` (the lore that
   the introduction can reference without spoiling), and
   `shared/characters.md` (the cast — the introduction can name
   the POV but should not name what happens to them).

   Draft an essay-form introduction, ~600-1200 words, opening
   with a question or observation that frames the book's central
   concern (NOT a plot summary; NEVER reveal the ending). Touch
   on:
     - the kind of book this is (what shelf it would sit on, what
       reading experience to expect)
     - the questions it sets out to ask, not the answers it gives
     - the period / world's most distinctive feature, framed as
       relevance rather than backstory
     - one image or motif from the book that recurs (a bell, a
       ledger, the weight of a coin) — used as a thematic anchor
       without spoiling its narrative role
     - what kind of reader the writer hopes will pick this up

   Match `voice.md` Part 1's register. Avoid:
     - "In this book…" / "This novel tells…" openings (workshop
       cliché; the introduction reads as marketing copy not
       essay)
     - any plot reveal beyond what a back-cover blurb would carry
     - any AI-tells from `ANTI-SLOP.md` (the introduction is the
       book's first impression in print — slop here is loud)

   Write to `books/{book}/introduction.md` with a `# Introduction`
   heading. Body is plain markdown paragraphs; keep it ≤1200
   words.

5. Print a one-screen summary: which files were written, their
   word counts, and (when the preface scaffold was created) an
   explicit edit-guide block so the user knows exactly what to do
   next without re-reading the file's inline comments:

   ```
   📄 Wrote books/{book}/preface.md (scaffold; ~150 words of
        bracketed placeholders + HOW-TO-EDIT block).

   To turn the scaffold into a real preface:

     1. Open books/{book}/preface.md in your editor.
     2. Read the HOW-TO-EDIT comment block at the top once.
     3. Replace each [bracketed placeholder] with real prose:
          - Section 1 (Why this book) — 1-2 paragraphs, personal,
            concrete. NOT "this novel explores…".
          - Section 2 (Reader note) — only if you have framing
            the cover blurb can't carry; otherwise delete the
            section.
          - Section 3 (Thanks) — last, tight; if Autonovel
            substantively drafted, acknowledge it openly.
          - Sign-off — Author, City, Year.
     4. Delete the HTML comment blocks once the prose is
        ready (they don't render in typeset, but cleaner without).
     5. Save. No further command needed — typeset picks up the
        file automatically.

   Typical length: 200-700 words (two short pages in print).

   When ready: /autonovel:typeset --book {book}
   ```

   For `--from auto` and `--from both`, also print the
   introduction.md word count and a one-line note that
   introduction.md is AI-drafted and YOU should re-read it before
   typeset (it's a draft, not a finished essay):

   ```
   📄 Wrote books/{book}/introduction.md (AI-drafted essay,
        N words).

   Open it before typeset; AI-drafted introductions tend to
   over-explain themes or slip into marketing-copy register
   ("In this book…"). Trim ruthlessly. Re-running with --force
   regenerates from scratch.
   ```
</workflow>

<acceptance>
- When `--from user` (or `both`): `books/{book}/preface.md` exists
  and contains the scaffold (or, if `--force`, was overwritten).
- When `--from auto` (or `both`): `books/{book}/introduction.md`
  exists, opens with `# Introduction`, is ≥400 words and ≤1500
  words, and does not name plot events past the inciting incident.
- Refusal on overwrite without `--force` is the default; the
  command never silently destroys hand-authored content.
- The next `/autonovel:typeset --book {book}` run picks up
  whichever file(s) exist via the front-matter builder; neither
  file existing is also fine (typeset still produces a clean
  book).
</acceptance>
