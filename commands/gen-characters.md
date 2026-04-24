---
name: autonovel:gen-characters
description: Generate shared/characters.md from the world and the books' seeds.
argument-hint: ""
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/world.md
  - books/*/seed.txt
  - shared/characters.md
writes:
  - shared/characters.md
context_mode: series
---

<purpose>
Seed the series-wide character roster in `shared/characters.md`. This is a
Layer-3 artifact: who acts. Every book's POV is drawn from this file;
every draft reads it. Characters introduced later (per-book minor cast)
may be added by sidequests, but the cross-book principals belong here.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--force` permits overwriting a populated file;
   otherwise no positional arguments are expected. Any other argument is a
   usage error — stop and surface a one-line reminder.

2. Use `file_read` on `project.yaml`. Note the `books[*].name` and
   `books[*].pov` entries: every declared POV must appear in the roster
   with enough depth to sustain a book.

3. Use `file_read` on `shared/world.md`. Characters inhabit the world;
   their professions, loyalties, and constraints come from it.

4. Use `file_read` on every `books/*/seed.txt`. Mine them for named and
   implied figures. A seed that says "her brother" commits you to a
   brother; write him in.

5. Use `file_read` on `shared/characters.md`. If it contains more than the
   template placeholder comment and `--force` was not supplied, stop.

6. Draft the roster. Each principal gets a short paragraph: name, age or
   life-stage, standing in the world, what they want, what they refuse.
   POV characters get one extra line on their private contradiction.
   Avoid catalog-style bullet-fests; write people, not stat blocks.

7. Use `file_write` to replace `shared/characters.md`. Start with
   `# Characters` as the first heading. No frontmatter.
</workflow>

<acceptance>
- `shared/characters.md` exists, begins with `# Characters`, and contains
  one entry per POV listed in `project.yaml :: books[*].pov`.
- Each entry names the character and states what they want or refuse.
- No plot outline content (scene lists, chapter-by-chapter arcs) is in
  this file — that is `outline.md`'s job.
</acceptance>
