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

The menu grows with the project. This version includes the PR 3
foundation + drafting sidequests, the PR 4 evaluation, revision,
and structural-edit sidequests, and the PR 5 research, period-guardrail,
canon-promotion, and character/subplot/foreshadowing entries.
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
     1.  Generate the world                → /autonovel:gen-world
     2.  Generate the character roster     → /autonovel:gen-characters
     3.  Generate a book's outline         → /autonovel:gen-outline --book <name>
     4.  Discover a book's voice           → /autonovel:voice-discovery --book <name>
     5.  Seed canon                        → /autonovel:gen-canon

   Drafting:
     6.  Draft a chapter                   → /autonovel:draft <N> --book <name>

   Evaluation:
     7.  Score a chapter / book / compare  → /autonovel:evaluate --chapter <N> --book <name>
     8.  Reader panel (4 personas)         → /autonovel:reader-panel --book <name>
     9.  Deep Opus review                  → /autonovel:review --book <name>

   Revision:
     10. Adversarial edit (find cuts)      → /autonovel:adversarial-edit <N> --book <name>
     11. Apply cuts deterministically      → /autonovel:apply-cuts <N> --book <name>
     12. Generate a revision brief         → /autonovel:brief <N> --book <name>
     13. Rewrite a chapter from brief      → /autonovel:revise <N> --book <name>

   Structural edits (one checkpoint each):
     14. Shorten a chapter                 → /autonovel:shorten --chapter <N> --book <name> --target-words <W>
     15. Lengthen a chapter                → /autonovel:lengthen --chapter <N> --book <name> --target-words <W>
     16. Split a chapter in two            → /autonovel:split-chapter --chapter <N> --book <name>
     17. Merge two adjacent chapters       → /autonovel:merge-chapters --chapters <N>,<M> --book <name>
     18. Revoice one chapter               → /autonovel:revoice <N> --book <name> --pov <name>

   Research and period guardrails:
     19. Research a real-world topic       → /autonovel:research "<topic>"
     20. Check period anachronisms         → /autonovel:check-anachronism <N> --book <name>
     21. Promote pending canon             → /autonovel:promote-canon
     22. Register a new research source    → /autonovel:add-source <url-or-doi>

   Cast and threads:
     23. Add a character                   → /autonovel:add-character --name <name>
     24. Deepen a character                → /autonovel:deepen-character <name> --book <name>
     25. Rename a character (global)       → /autonovel:rename-character --old <X> --new <Y>
     26. Add a two-beat subplot            → /autonovel:add-subplot --thread "<desc>" --plant <N> --payoff <M> --book <name>
     27. Foreshadow a plant+payoff         → /autonovel:foreshadow --plant <N> --payoff <M> --thread "<desc>" --book <name>

   Navigation:
     28. Where am I?                       → /autonovel:next
     29. Resume an interrupted command     → /autonovel:resume

   Maintenance:
     30. Roll back recent changes          → autonovel rollback
     31. Reconcile state                   → autonovel doctor
     32. Show status                       → autonovel status

   (More sidequests unlock in later PRs: reorder, remove-chapter.)

   Select [1-32, 0=exit]:
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
- The printed menu contains exactly the thirty-two options listed
  above (in that order).
- The command does not invoke any other slash command or CLI tool
  automatically — routing is advisory only.
</acceptance>
