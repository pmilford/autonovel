---
name: autonovel:sidequest
description: Dispatcher for non-standard-path operations (menu + routing only).
argument-hint: ""
model_tier: light
allowed-tools:
  - file_read
reads:
  - project.yaml
  - .autonovel/last-action.json
writes: []
context_mode: none
---

<purpose>
Interactive menu of every "off the standard path" operation. This command
is a dispatcher — it prints a numbered list and points the user at the
real slash command. It never modifies files directly; the target commands
each own their own lock / checkpoint / footer.

The menu grows with the project. This version shows only the sidequests
whose underlying commands ship in PR 3; later PRs add the revision and
research sidequests.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. No arguments are expected. If the user passes
   anything, still print the menu — the argument is ignored but not an
   error.

2. Use `file_read` on `project.yaml` to list the books in the series.
   Use `file_read` on `.autonovel/last-action.json` (if it exists) so the
   menu can show the last action at the top. If neither file is present,
   print the menu anyway — the dispatcher is valid even in an empty
   series.

3. Print the menu verbatim:

   ```
   /autonovel:sidequest

   Foundation work:
     1. Generate the world                → /autonovel:gen-world
     2. Generate the character roster     → /autonovel:gen-characters
     3. Generate a book's outline         → /autonovel:gen-outline --book <name>
     4. Discover a book's voice           → /autonovel:voice-discovery --book <name>
     5. Seed canon                        → /autonovel:gen-canon

   Drafting:
     6. Draft a chapter                   → /autonovel:draft <N> --book <name>

   Navigation:
     7. Where am I?                        → /autonovel:next
     8. Resume an interrupted command      → /autonovel:resume

   Maintenance:
     9. Roll back recent changes           → autonovel rollback
     10. Reconcile state                   → autonovel doctor
     11. Show status                       → autonovel status

   (More sidequests unlock in later PRs: shorten, lengthen, split,
   rename-character, reorder, research, etc.)

   Select [1-11, 0=exit]:
   ```

4. Wait for the user's selection. On `0` or empty input, print "exiting"
   and stop. On a valid number, print the corresponding command line and
   a one-line instruction: "Run that command now, or press Enter to stay
   in the menu." Do not invoke the command on the user's behalf — routing
   via a separate slash-command invocation preserves the lock / checkpoint
   guarantees of the target command.

5. If the user chooses a command that requires `--book <name>` and the
   series has exactly one book, substitute that book's name in the
   suggestion; otherwise leave the `<name>` placeholder literal so the
   user picks.
</workflow>

<acceptance>
- No files are written.
- The printed menu contains exactly the eleven options listed above (in
  that order).
- The command does not invoke any other slash command or CLI tool
  automatically — routing is advisory only.
</acceptance>
