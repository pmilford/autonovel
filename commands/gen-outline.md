---
name: autonovel:gen-outline
description: Generate the outline for one book from its seed, world, and characters.
argument-hint: "--book <short-name>"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/world.md
  - shared/characters.md
  - shared/events.md
  - books/{book}/seed.txt
  - books/{book}/voice.md
  - books/{book}/outline.md
writes:
  - books/{book}/outline.md
context_mode: book
---

<purpose>
Produce `books/{book}/outline.md`: a chapter-by-chapter plan (Layer-2) for
one book. Each chapter entry names its story_time, any series events it
renders (`E-###` ids from `shared/events.md`), and its beats — the
concrete moves, not the abstract theme. Drafting reads this file for every
chapter, so specificity now saves revision later.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `--book <short-name>`. If missing, stop and
   surface a one-line usage reminder. `--force` permits overwriting a
   populated outline.

2. Use `file_read` on `project.yaml`. Resolve the book entry. Capture
   `pov`, `story_time_range`, and `defaults.chapter_target_words` — the
   outline's chapter count should roughly match
   `seed.txt target length ÷ chapter_target_words`, honoring any chapter
   count already implied by the seed.

3. Use `file_read` on `books/{book}/seed.txt`. This is the authorial
   intent. If the seed states a chapter count or length, honor it.

4. Use `file_read` on `shared/world.md`, `shared/characters.md`, and
   `shared/events.md`. Any chapter whose story_time overlaps a registered
   event's `canonical` window must either render that event (list the
   `E-###` id) or step deliberately around it.

5. Use `file_read` on `books/{book}/voice.md`. Part 1 (series voice)
   constrains the kinds of scenes that belong in this book.

6. Use `file_read` on `books/{book}/outline.md`. If it contains more than
   the template placeholder and `--force` was not supplied, stop.

7. Draft the outline. For each chapter:
   - `## Chapter N — <title>`
   - `- story_time: <ISO date or date range within the book's story_time_range>`
   - `- events: [E-001, ...]` (may be empty)
   - `- beats:` followed by 3–6 concrete beat lines. A beat names what
     changes in the scene; a theme is not a beat.
   Structure across chapters: stable rising action, a midpoint reversal,
   a costly climax. Never end on a round-edged resolution (see
   `program.md` on the Stability Trap).

8. Use `file_write` to replace `books/{book}/outline.md`. Start with
   `# Outline`. No frontmatter.
</workflow>

<acceptance>
- `books/{book}/outline.md` exists and begins with `# Outline`.
- At least three `## Chapter N` headings, each with `story_time`,
  `events`, and `beats` sub-items.
- Every `story_time` falls within the book's `story_time_range` from
  `project.yaml`.
- Every `E-###` id referenced in `events:` exists in
  `shared/events.md`.
</acceptance>
