---
name: autonovel:gen-canon
description: Seed shared/canon.md with hard facts derived from world, characters, and outlines.
argument-hint: ""
model_tier: standard
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/world.md
  - shared/characters.md
  - shared/events.md
  - books/*/outline.md
  - shared/canon.md
writes:
  - shared/canon.md
context_mode: series
---

<purpose>
Seed `shared/canon.md` with the hard facts that every book in the series
must respect — names, dates, physical constraints, named events. Canon is
append-only going forward; `/autonovel:promote-canon` grows it from
drafted chapters. This command sets the initial state.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--force` permits overwriting an already-populated
   `shared/canon.md`; otherwise no arguments are expected. Any other
   argument is a usage error — stop with a one-line reminder.

2. Use `file_read` on `project.yaml`, `shared/world.md`,
   `shared/characters.md`, `shared/events.md`, and every
   `books/*/outline.md` that exists.

3. Use `file_read` on `shared/canon.md`. If it contains more than the
   template placeholder comment and `--force` was not supplied, stop.

4. Extract canonical facts. A canon entry is a single verifiable claim a
   future chapter must not contradict. Good entries:
   - dated events with named participants,
   - anatomical / physical consequences (scars, disabilities, deaths),
   - family relations, ranks, affiliations,
   - geographical constants (which side of the river, which gate faces
     north).
   Avoid thematic statements, opinions, or anything that could reasonably
   be rewritten later.

5. Use `file_write` to replace `shared/canon.md`. Start with `# Canon`.
   Entries as bullet list, one fact per bullet. Reference events by their
   `E-###` id in square brackets when applicable. No frontmatter.
</workflow>

<acceptance>
- `shared/canon.md` exists, begins with `# Canon`, and contains at least
  three bullet entries (lines beginning with `- `).
- No bullet is a thematic statement (no lines of the form
  "The story is about X" or "The theme is Y").
- Every `E-###` id referenced in bullets exists in `shared/events.md`.
</acceptance>
