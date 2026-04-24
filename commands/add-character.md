---
name: autonovel:add-character
description: Add one character to the series cast; update shared/characters.md with a full entry.
argument-hint: "--name <name> [--role <role>] [--book <short-name>]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/characters.md
  - shared/world.md
  - books/{book}/outline.md
  - books/{book}/voice.md
writes:
  - shared/characters.md
context_mode: series
---

<purpose>
Sidequest: add a character to `shared/characters.md`. Writes one new
entry — name, role, age bracket, standing, one defining want, one
defining fear, one defining secret, and a short voice / speech note.
Does not modify any chapter; plumbing a new character into existing
prose is a separate `/autonovel:revise` job. One checkpoint, so
`autonovel rollback` undoes the add.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Required: `--name <name>`. Optional:
   `--role <role>` (e.g. "apothecary's apprentice"),
   `--book <short-name>` (which book the character debuts in; if
   omitted, the character is series-wide). Missing `--name` is a
   usage error.

2. Use `file_read` on `project.yaml`, `shared/characters.md`, and
   `shared/world.md`. The world bible pins what is possible; the
   existing `shared/characters.md` pins the family / political /
   institutional web the new character must fit into. If `--book`
   is set, also `file_read` `books/{book}/outline.md` and
   `books/{book}/voice.md` so the character's debut arc and voice
   are coherent with the book that adopts them.

3. Check for a name clash. If `shared/characters.md` already names
   this character, stop with a one-line reminder suggesting
   `/autonovel:deepen-character` instead.

4. Draft the character entry. Required fields (in this order):
   - **Name** (with any epithets / titles the world uses).
   - **Role** (one line).
   - **Age bracket** (decade — exact year is over-commitment).
   - **Standing** (class / guild / family; one sentence).
   - **Want** (what they are chasing, one sentence).
   - **Fear** (what they avoid, one sentence).
   - **Secret** (one thing not yet known to other characters).
   - **Voice note** (one or two lines on cadence, register, a
     verbal tic; tied to the book's `voice.md` if `--book` was
     passed).
   - **Debuts in** (book short-name, or `series` for series-wide).

   Keep the entry to 120-250 words. Concrete over abstract. Do not
   invent facts the world bible contradicts.

5. Use `file_write` to append the entry to
   `shared/characters.md` under a new `## <Name>` heading. Preserve
   the rest of the file verbatim.
</workflow>

<acceptance>
- `shared/characters.md` contains a new `## <Name>` section.
- The new section has all eight required fields (Role, Age bracket,
  Standing, Want, Fear, Secret, Voice note, Debuts in).
- No chapter under `books/*/chapters/` is modified.
</acceptance>
