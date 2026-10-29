---
name: autonovel:screenplay
description: Adapt a passage of the book (a chapter or a range, optionally from one quoted line to another) into a screenplay sequence in Fountain, with its scene list (film/scenes.json), an adaptation note giving every change from the book and its reason, and a PDF and Final Draft FDX; a screen critic scores it against SCREEN.md and it is revised until it passes, and a cold reader who hasn't read the book checks it can be followed.
argument-hint: "--chapters <range> [--from \"<quote>\"] [--to \"<quote>\"] --book <short-name> [--seq <NN>] [--pages <n>] [--rounds <n>] [--force]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
  - task
reads:
  - project.yaml
  - shared/craft/SCREEN.md
  - shared/craft/genres/*.md
  - shared/genres/*.md
  - shared/canon.md
  - shared/characters.md
  - books/{book}/chapters/ch_*.md
  - books/{book}/design.md
  - books/{book}/cast.md
  - books/{book}/voice.md
  - books/{book}/canon.md
  - books/{book}/film/adaptation.md
  - books/{book}/film/scenes.json
  - books/{book}/film/screenplay/seq_*.fountain
writes:
  - books/{book}/film/screenplay/seq_*.fountain
  - books/{book}/film/screenplay/seq_*_adaptation.md
  - books/{book}/film/scenes.json
  - books/{book}/film/export/*.pdf
  - books/{book}/film/export/*.fdx
  - books/{book}/film/reviews/seq_*_critic.md
  - books/{book}/film/reviews/seq_*_cold_read.md
context_mode: book
---

<purpose>
Turn one passage of a finished book into a sequence of a screenplay that
a director could shoot and a stranger could follow: stage F1 of the film
pipeline (`docs/film-pipeline-plan.md`, milestone M1). The author is not
expected to know how a script is written; this command is the
screenwriter, and `shared/craft/SCREEN.md` is its craft.

It writes, under `books/{book}/film/`:

- `screenplay/seq_NN.fountain`: the sequence in Fountain, the plain-text
  screenplay format. It is the source; everything else is built from it.
- `screenplay/seq_NN_adaptation.md`: the adaptation note. What the
  passage is, the sequence's question, and every change from the book
  (cut, merged, moved, given to someone else, invented, or a thought made
  visible), each quoting the book, pointing to the scene and giving the
  reason, in plain words the author can check against the chapter.
- `scenes.json`: every scene's ID, heading, characters, the book lines it
  comes from, its turn and its length in eighths of a page, plus the
  scene marked as the best first minute to render. `autonovel mechanical
  fountain-check` writes it from the script, so it never disagrees with
  the script.
- `export/seq_NN.pdf` and `export/seq_NN.fdx`: the script in standard
  format (Courier 12, the spec page) and as a Final Draft file.
- `reviews/seq_NN_critic.md` and `reviews/seq_NN_cold_read.md`: the screen
  critic's scores and notes, the cold reader's report, and what was
  changed for each.

Adaptation changes the book on purpose: thought becomes behaviour or
image, scenes merge or move, dialogue is compressed. The book's rules
still bind the film: its facts (canon), its people (no new named person),
its register (`voice.md`), and its genre's payload (in historical fiction,
the period itself is what the audience comes for, so it is carried on
screen, not cut). Every change is written down with its reason.

`--chapters <range>`: the chapter or chapters the passage comes from
(`2`, `4-5`). `--from "<quote>"`: the passage starts at the line holding
this text (default: the chapter's first line). `--to "<quote>"`: it ends
at the line holding this text (default: the last chapter's end).
`--seq <NN>`: the sequence number (default: the next free one in
`film/screenplay/`). `--pages <n>`: the page budget (default: the
sequence's entry in `film/adaptation.md` when there is one; otherwise
SCREEN.md §5.8's heuristic). `--rounds <n>`: the most critic rounds
(default 3). `--force`: replace an existing sequence of that number.
</purpose>

<workflow>
**Read-failure policy.** The chapters of the passage and
`shared/craft/SCREEN.md` are load-bearing: stop if either is missing (for
SCREEN.md, run `autonovel refresh-templates` from the series root first;
it restores the craft documents). `books/{book}/cast.md`,
`books/{book}/design.md`, `books/{book}/voice.md`, `books/{book}/canon.md`,
`shared/canon.md`, `shared/characters.md`, `books/{book}/film/adaptation.md`
and the genre guide are best-effort: if a read fails, note the gap in the
adaptation note and go on; do not retry a failed `file_read`.

1. **Parse `$ARGUMENTS`.** `--book` and `--chapters` are required. Find
   the sequence number: `--seq`, or one more than the highest
   `books/{book}/film/screenplay/seq_NN.fountain` (01 when there is none).
   If that file exists and `--force` is absent, stop and say so in one
   line (offer `--force`, or a new `--seq`).

2. **Study the craft.** Use `file_read` on `shared/craft/SCREEN.md` in
   full. Read the book's genre guide (the file `_begin`'s `genre:` line
   names; `autonovel genre show --book {book}` prints it when no preamble
   ran; it is `shared/craft/genres/<genre>.md` or the series' own
   `shared/genres/<genre>.md`): `## The promise` and `## On screen`. Read
   `books/{book}/voice.md` Parts 1 and 2 (the register the dialogue
   keeps) and Part 4 for the people who speak in the passage.

3. **Read the passage and who is in it.** Use `file_read` on each chapter
   in `--chapters` in full (`books/{book}/chapters/ch_NN.md`), and the
   chapter before the first one, best-effort, for who these people are.
   Find the passage's first and last lines (`--from`, `--to`) and keep
   their **line numbers in the chapter file**: every scene's source is
   given as `ch_NN:first-last` in those numbers. Then read:
   - `project.yaml`: the book's title and author (for the title page's
     `Source:` and `Credit:`) and its genre and subgenres;
   - `books/{book}/cast.md`: the entry for every person in the passage,
     its "called by a role" list and its bit parts (who is named on the
     page and who is a role);
   - `books/{book}/design.md`: `## Places` and `## Terms` for the places
     and words the passage turns on, with their period traps, and the
     `## Cast` entries for the people in it;
   - the canon entries the chapter fixed: use `bash` to run `grep -n
     "ch_NN" books/{book}/canon.md` for each chapter, and read those
     entries (and any `shared/canon.md` fact the passage relies on);
   - `books/{book}/film/adaptation.md` when it exists (the whole film's
     plan: what this sequence must carry, what merges, its page budget),
     and `books/{book}/film/scenes.json` for the IDs other sequences use.

4. **Break the passage down before writing a line of script.** Write the
   working parts of the adaptation note (step 6 gives its shape):
   a. **Cardinal events** (SCREEN.md §5.1): the events without which the
      story would not go on, each with its `ch_NN:line`.
   b. **Interior life the audience must grasp** (§3, §5.2): each thought,
      memory, plan, feeling or piece of narration the passage needs, and
      how the script will carry it: behaviour, object or insert, a line to
      someone with a reason to hear it, a small invented scene, or (last)
      voice-over.
   c. **The period payload** (the genre guide's `## On screen`): every
      fact of time and place the passage gives (a law, a coin, a custom,
      a building, how a thing was done), and how it reaches the screen.
      Nothing here is cut for pace.
   d. **What the audience must know before each turn** (§3.4), and where
      the script shows it. A fact the book gives in hindsight may need to
      be planted first.
   e. **Who speaks**: each speaking person, their cast entry, or a role
      (no new named people, §5.4); one cue per person.
   f. **The sequence's question** (what the audience waits to learn) and
      how its last scene turns it; then the **scene list**, each scene
      with its place, time and turn (`before -> after`), and a page
      budget that adds up to `--pages`.

5. **Write the script** with `file_write` to
   `books/{book}/film/screenplay/seq_NN.fountain`, to SCREEN.md §1:
   - a title page: `Title:` (the sequence's title), `Credit:`, `Source:`
     (the book and chapter), `Draft date:`, `Roles:` with each speaking
     role on an indented line under the empty key, and `First minute:
     S<NN><nn> — <why, one sentence>` (step 8);
   - a `SUPER:` for place and date at the start, and at each jump;
   - every scene heading `INT.`/`EXT.` + place + ` - ` + time of day, a
     blank line after it, then the scene line `= S<NN><nn> |
     ch_NN:first-last | before -> after` (`invented` for a scene the book
     doesn't have, naming in brackets what it carries);
   - people introduced in capitals with an age and one detail; action in
     the present tense, blocks of four lines or fewer; dialogue in the
     book's register, compressed, each line a move; the book's best lines
     kept word for word where they play aloud; other languages marked
     `(in <language>; subtitled)` or `(in <language>; not subtitled)`;
     voice-over within §4.7.
   Keep every fact true to the canon; invent only in its gaps.

6. **Write the adaptation note** with `file_write` to
   `books/{book}/film/screenplay/seq_NN_adaptation.md`, for the author,
   in plain sentences (introduce every person and term at first mention;
   no screen jargon without a gloss):

   ```markdown
   # Sequence NN: <title> — adaptation note

   ## The passage
   <chapter, first and last lines quoted, line numbers, word count; what happens in it, in three sentences>

   ## The sequence
   <its question, how it turns, the scene list with lengths>

   ## Cardinal events
   | Event | Book | Scene |

   ## Thought made visible
   | What the reader is told | Book | How the film carries it | Scene |

   ## The period on screen
   | Fact | Book | How it reaches the screen | Scene |

   ## Speaking parts
   | Cue | Who | Cast entry or role |

   ## Every change from the book
   | # | Change | Book (quote, ch_NN:line) | Script | Why |
   (Change is one of CUT, CONDENSE, COMPRESS, DISPLACE, ALTER, INVENT,
   EXTERNALISE, SCREEN.md §5.3; every cut says why the film can do
   without it, and pace alone is never the reason for cutting a period
   fact)

   ## The first minute to render
   <the scene, and why: what it shows of the period, how few speaking
   faces it needs, what it asks the audience>

   ## Questions for the author
   <each choice the author may want to overrule, as a question>
   ```

7. **Check it.** Use `bash` from the series root:

   ```
   autonovel mechanical fountain-check books/{book}/film/screenplay/seq_NN.fountain --stamp --format markdown
   ```

   `--stamp` records the fingerprint of each cited chapter, so a later
   edit to the book shows this sequence as out of date. Fix every error
   and re-run until it reports OK. Read each warning and advisory: fix it
   or say in the adaptation note why it stands. The report's length in
   eighths is the page count; compare it with the budget.

8. **The first minute.** Choose the scene that is the best first minute
   to render (film stages F4–F6): it shows the genre's payload in pictures,
   needs few speaking faces and little lip-sync, holds one face the
   audience will follow, and poses a question in about a page. Name it in
   the title page's `First minute:` key and explain the choice in the
   note; `fountain-check` copies it into `scenes.json`.

9. **The screen critic, in rounds.** Use `task` to spawn a heavy-tier
   critic in a **fresh subagent** conversation that has not seen your
   reasoning. Give it the paths of `shared/craft/SCREEN.md` (§8 is its
   rubric), the genre guide's `## On screen`, `books/{book}/voice.md`
   Parts 1–2, the chapter file with the passage's line numbers, the
   script, the adaptation note, and the latest `fountain-check` report.
   Ask it to: score the ten dimensions of §8 from 1 to 10, each with the
   lines that justify it, worst first; run SC1–SC12 (pass, fail or n/a,
   one line of evidence each); list its notes ranked must-fix, should-fix
   and polish, each pointing to a scene and saying what to change; and
   write all of it under `## Round N` in
   `books/{book}/film/reviews/seq_NN_critic.md` (appending to earlier
   rounds). Then judge every note yourself: make each change that holds
   in the script and, where it changes the adaptation, in the note; under
   the round write `### Response`, one line per note: done (what
   changed), or declined (why). Re-run step 7. The gate is SCREEN.md §8's:
   no dimension below 7 and every test passing or `n/a` with a reason.
   Until it passes, run another round with a new fresh critic, up to
   `--rounds`; a new critic also checks the last round's fixes in the
   script, not only the response lines.

10. **The cold reader.** Use `task` to spawn a reader in a **fresh
    subagent** conversation who knows nothing of the book: give it only
    the path of the script (`books/{book}/film/screenplay/seq_NN.fountain`)
    and the questions of SCREEN.md §9, written into the prompt, and tell it
    not to open any other file (not the chapters, the adaptation note,
    the critic's report, the cast, the design or SCREEN.md). Ask it to
    answer each question, end with its must-fix list, and write the
    report to `books/{book}/film/reviews/seq_NN_cold_read.md`. Then fix
    every must-fix item (or write why it is not a fault) and record what
    changed under `## Response` in that file. **If the fixes changed a
    scene materially** (a scene added, cut or reordered, a person
    introduced differently), spawn a second fresh cold reader on the
    revised script with the same questions, append its report as `##
    Second read`, and fix what it finds. A cold read that still has a
    must-fix item open means the sequence is not ready.

11. **Build the exports and the scene list.** Run step 7's command once
    more on the final script: it writes `books/{book}/film/export/seq_NN.pdf`
    and `books/{book}/film/export/seq_NN.fdx` and updates
    `books/{book}/film/scenes.json`. If it prints that screenplain is not
    installed, tell the author the one command that adds it (`pip install
    'autonovel[export]'`, or `pipx inject autonovel screenplain` under
    pipx) and that the Fountain file is complete without it. Confirm the
    report's FDX check is `ok` and that the PDF's page count is close to
    the eighths count (title page aside). Then bring the adaptation note
    up to date with the script as it now stands: copy every scene's
    length and the total from this report into its tables (a hand-kept
    length goes stale with every revision), and check that its scene IDs,
    period table and change list still match the script.

12. **Report to the author**, in plain sentences, worst news first:
    - what the sequence covers (chapter, first and last lines) and its
      question, in two sentences;
    - the scenes, one line each: heading, length in eighths, what happens;
    - the main adaptation choices and why (the biggest changes from the
      book, quoting the book where it helps);
    - what the critic scored (the lowest dimension first) and the cold
      reader's verdict, and what was changed for each; anything still
      open;
    - the first minute to render, and why;
    - the paths: the PDF, the Fountain file, the adaptation note, the two
      reviews;
    - the questions for the author.
    Then **Next:**
    1. Read the PDF beside the chapter, with the adaptation note open.
    2. `/autonovel:screenplay --chapters <next passage> --book {book}` for
       the next sequence, or `--force` with this one after any change to
       the passage.
</workflow>

<acceptance>
- `books/{book}/film/screenplay/seq_NN.fountain` exists and `autonovel
  mechanical fountain-check` on it exits 0: every heading has
  `INT.`/`EXT.`, a place and a time; every speaker is in the cast or under
  `Roles:`; every scene has a scene line with an ID, a source in the
  chapter's line numbers (or `invented`) and a turn; `First minute:` names
  a scene.
- `books/{book}/film/screenplay/seq_NN_adaptation.md` lists the cardinal
  events, the interior life and how it is carried, the period facts and
  how they reach the screen, the speaking parts, and every change from the
  book with its reason.
- `books/{book}/film/scenes.json` has the sequence and its scenes, with
  `adapted_from` fingerprints for the cited chapters.
- `books/{book}/film/reviews/seq_NN_critic.md` has at least one round with
  the ten scores, SC1–SC12 and a response line per note; the last round
  passes SCREEN.md §8's gate, or the report says plainly what is left.
- `books/{book}/film/reviews/seq_NN_cold_read.md` holds a report from a
  reader who saw only the script, and a response for every must-fix item.
- With screenplain installed, `books/{book}/film/export/seq_NN.pdf` and
  `.fdx` exist and the FDX check is ok.
- No chapter, canon, cast, design or outline file is written.
</acceptance>
