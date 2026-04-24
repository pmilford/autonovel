---
name: autonovel:resume
description: Detect an in-flight command and offer redo / keep-partial / inspect.
argument-hint: "[--book <short-name>]"
model_tier: light
allowed-tools:
  - file_read
  - bash
reads:
  - .autonovel/in-progress.lock
  - .autonovel/checkpoints/*
writes: []
context_mode: none
---

<purpose>
Recovery surface after `/clear`, power loss, budget exhaustion, or a manual
kill. Detects the stale lock, reports what was in flight, and offers three
choices — Redo, Keep partial, Inspect — none of which are destructive until
the user explicitly picks one.
</purpose>

<workflow>
1. Use `file_read` on `.autonovel/in-progress.lock`. If absent, say
   "nothing to resume; run `/autonovel:next` for the standard next step"
   and stop.

2. Check whether the recorded PID is still live. Use `bash` with
   `autonovel doctor` (it reports stale locks) or `kill -0 <pid>` as a
   fallback. If the PID is live, refuse — another autonovel command is
   genuinely running.

3. If the lock is stale, print:
   - the command and args that were in flight,
   - the paths that were about to be written (from the matching manifest
     under `.autonovel/checkpoints/`), and
   - the three recovery options:
       [1] Redo — roll back from the checkpoint and re-run from scratch.
       [2] Keep partial — clear the lock but leave any partially written
           files untouched. The user will continue manually.
       [3] Inspect — show what would change and exit without doing anything.

4. Wait for explicit user input. Do not take any destructive action without
   it. Option [1] uses `bash` to run `autonovel rollback --to <timestamp>`;
   option [2] uses `bash` to remove `.autonovel/in-progress.lock`; option
   [3] does nothing.
</workflow>

<acceptance>
- Never writes files or runs rollback without explicit user confirmation.
- When no lock is present, the command prints the "nothing to resume"
  message and exits cleanly.
</acceptance>
