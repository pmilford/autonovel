---
name: autonovel:title
description: Propose / set a book's display title, subtitle, and author for typeset.
argument-hint: "--book <short-name> [--set \"<title>\" --author \"<name>\" --subtitle \"<text>\"] [--pick N] [--pick-author M]"
model_tier: light
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - books/{book}/seed.txt
  - books/{book}/outline.md
  - shared/characters.md
  - books/{book}/title_proposals.md
writes:
  - project.yaml
  - books/{book}/title_proposals.md
context_mode: book
---

<purpose>
Author-facing helper for the book metadata `/autonovel:typeset` reads
to fill the title page, ePub metadata, and the running header. Three
modes:

  - **Propose** (default): read the seed + outline + cast and propose
    5 candidate titles plus 3 candidate author pen names. Writes the
    proposals to `books/{book}/title_proposals.md` so a follow-up
    `--pick N` invocation can commit one without re-deriving. Does
    NOT touch `project.yaml`.

  - **Pick**: `--pick N [--pick-author M]` reads the prior proposals
    file and commits proposal N as the title (and proposal M as the
    author). Writes to `project.yaml :: books[<name>]`.

  - **Set explicitly**: `--set "<title>" [--author "<name>"]
    [--subtitle "<text>"]` skips the propose step and writes the
    given values directly. Useful when the writer already knows
    what they want.

Running this command is optional — `typeset` falls back to
`series_name` for the title and "Anonymous" for the author when a
book has no explicit values. Set them when you want a real title page
and proper ePub metadata.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Required: `--book <short-name>`. Optional:
   `--set "<title>"`, `--author "<name>"`, `--subtitle "<text>"`,
   `--pick N`, `--pick-author M`.

   Mode resolution:
   - Any of `--set / --author / --subtitle` → **set mode**.
   - `--pick` (with optional `--pick-author`) → **pick mode**.
   - Neither → **propose mode**.

   `--set` and `--pick` are mutually exclusive — passing both is a
   usage error.

2. **Set mode** (any of `--set / --author / --subtitle` given):
   read `project.yaml`, find `books[<name>]`. Update its `title` /
   `subtitle` / `author` fields with the given values (only the
   fields actually passed are touched). Write `project.yaml` back.
   Skip the propose step entirely. Print the resulting display
   metadata.

3. **Pick mode** (`--pick N` given):
   a. `file_read` `books/{book}/title_proposals.md`. If missing,
      stop with: "no proposals on disk; run `/autonovel:title --book
      {book}` (no flags) first to generate them, or use `--set` to
      set explicitly".
   b. Parse the numbered title proposals (1-indexed) and the
      numbered author proposals. Validate that `N` is in range; if
      not, stop with the available range.
   c. Commit proposal N as the book's `title` and (if `--pick-author
      M` given) proposal M as the book's `author`. Same write
      mechanic as set mode.

4. **Propose mode** (no flags beyond `--book`):
   a. `file_read` `books/{book}/seed.txt` — the writer's pitch is the
      single richest source for title direction. `file_read`
      `books/{book}/outline.md` — chapter beats reveal the book's
      shape (mystery? coming-of-age? confrontation?). `file_read`
      `shared/characters.md` — POV character names occasionally
      belong in titles ("The Inquisitor" derives from POV
      "Tommaso").
   b. Generate **5 title candidates** spanning a deliberate range:
      - **Literal** — names the book's central object/event/place.
      - **Evocative** — image-driven, no proper nouns ("The
        Apothecary's Mortar").
      - **Character-anchored** — names or implies the POV.
      - **Thematic** — names what's at stake.
      - **Wildcard** — ignores the obvious; a phrase or single word
        the LLM judges has hook power.

      Each candidate gets one line of rationale ("why this title").
      Aim for 2–6 words each; avoid clauses, avoid colons unless
      the subtitle does work the title can't.

   c. Generate **3 author pen-name candidates** (only if the book
      has no `author` set in `project.yaml` and the series has no
      series-level `author`):
      - **Real-feeling** — first + last, period/region appropriate.
      - **Initials** — first-initial + last (P. M. James-style).
      - **Single name or unusual** — a one-word or distinctive form.

      Each gets one line of rationale.

   d. Use `file_write` to save the proposals to
      `books/{book}/title_proposals.md` in this exact format (so
      the pick mode parser can find them):

      ```markdown
      # Title proposals for {book}

      Generated <UTC-date>. Re-run `/autonovel:title --book {book} --pick <N>`
      to commit proposal N as the book's title (and `--pick-author <M>`
      to commit author proposal M).

      ## Title candidates

      1. **The Inquisitor's Coin** — literal: names the book's central object.
      2. **Salt and Saltpeter** — evocative: the apothecary motif vs. the burn.
      3. **What Tommaso Knew** — character-anchored to the POV.
      4. **The Weight of a Ledger** — thematic: cost of bookkeeping.
      5. **Carnival Hours** — wildcard: shifts genre signal toward literary.

      ## Author candidates

      1. **Renata Calvi** — real-feeling, Italian, period-appropriate.
      2. **R. M. Calvi** — initials form; reads as 20th-century literary.
      3. **Renata** — single-name; reads as memoir or autofiction.
      ```

   e. Print the proposals verbatim to stdout so the user sees them
      in the chat without opening the file. Tell the user the next
      step: `/autonovel:title --book {book} --pick N [--pick-author M]`
      to commit, or `--set "<title>" --author "<name>"` to bypass
      the proposals.

5. The bash side does the actual project.yaml edit when a value is
   committed. Use the `Bash` tool to run a one-shot Python helper:

   ```
   python -c '
   from pathlib import Path
   from autonovel import project as p
   from autonovel.paths import find_series_root, SeriesLayout
   series = SeriesLayout(root=find_series_root())
   cfg = p.load(series.project_file)
   book = cfg.book_by_name("{book}")
   if "{title_value}":
       book.title = "{title_value}"
   # … same for subtitle, author …
   p.dump(cfg, series.project_file)
   '
   ```

   (escape the values for shell safely; avoid embedding raw quotes
   in the title/author values).
</workflow>

<acceptance>
- **Propose mode** writes `books/{book}/title_proposals.md` with at
  least 5 numbered title candidates under `## Title candidates` and
  (when no author was already set) at least 3 numbered author
  candidates under `## Author candidates`. `project.yaml` is
  unchanged.
- **Pick mode** writes the chosen `title` / `author` into
  `project.yaml :: books[<name>]` (and leaves other fields
  untouched). Re-running pick with the same N is idempotent.
- **Set mode** writes the explicit `--set` / `--author` /
  `--subtitle` values into `project.yaml :: books[<name>]` without
  generating or reading proposals.
- Subsequent `/autonovel:typeset --book {book}` runs use the new
  values for the title page, ePub metadata, and the running header.
</acceptance>
