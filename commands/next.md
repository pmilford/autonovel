---
name: autonovel:next
description: Show the standard next step and common alternatives.
argument-hint: "[--book <short-name>]"
model_tier: light
allowed-tools:
  - file_read
reads:
  - project.yaml
  - .autonovel/state.json
  - .autonovel/last-action.json
writes: []
context_mode: none
---

<purpose>
Read-only "where am I" for after a `/clear`, after a break, or when the user
is unsure. Prints the last action, the standard next step, and up to three
sidequest alternatives. Never modifies files.
</purpose>

<workflow>
1. Use `file_read` on `.autonovel/last-action.json`. If absent, print
   "no autonovel action recorded yet in this series" and suggest
   `/autonovel:gen-world` as the usual first step.

2. Use `file_read` on `project.yaml` and `.autonovel/state.json` to know
   which books exist and what phase each is in.

3. If `$ARGUMENTS` includes `--book <name>`, filter to that book's last
   action; otherwise show the most recent action across the series.

4. Print the user-facing footer verbatim as stored in `last-action.json` —
   the `next_standard_step`, the rationale, and any `sidequests`.

5. Do not touch disk. This command is read-only by contract.
</workflow>

<acceptance>
- No files written.
- Output contains the `next_standard_step` value from
  `.autonovel/last-action.json` verbatim (when that file exists).
</acceptance>
