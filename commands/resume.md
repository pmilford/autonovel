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
  - .autonovel/sweep-progress.json
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
1. **Sweep-progress check first.** Use `bash` to invoke
   `autonovel _sweep-status --format human`. If a sweep is in
   flight (`.autonovel/sweep-progress.json` exists), the helper
   prints the original command, the target chapter list, the
   completed chapters, and the **remaining chapters**. Print this
   verbatim — it tells the user the precise "continue from
   chapter N" command to re-run, with the remaining list already
   formatted. Sweep tracking is independent of the lock: a
   `/clear` mid-sweep wipes the lock without clearing
   sweep-progress, so this signal works exactly when the
   `in-progress.lock` check below would say nothing to do.

   When sweep-progress is present, also fall through to the
   lock + checkpoint check below — the user may want to inspect
   the lock state separately before re-running the sweep.

2. Use `file_read` on `.autonovel/in-progress.lock`. If absent, say
   "nothing to resume; run `/autonovel:next` for the standard next step"
   (and skip the rest of this workflow if sweep-progress was also
   absent in step 1).

3. Check whether the recorded PID is still live. Use `bash` with
   `autonovel doctor` (it reports stale locks) or `kill -0 <pid>` as a
   fallback. If the PID is live, refuse — another autonovel command is
   genuinely running.

4. If the lock is stale, print:
   - the command and args that were in flight,
   - the paths that were about to be written (from the matching manifest
     under `.autonovel/checkpoints/`), and
   - the three recovery options:
       [1] Redo — roll back from the checkpoint and re-run from scratch.
       [2] Keep partial — clear the lock but leave any partially written
           files untouched. The user will continue manually.
       [3] Inspect — show what would change and exit without doing anything.

5. Wait for explicit user input. Do not take any destructive action without
   it. Option [1] uses `bash` to run `autonovel rollback --to <timestamp>`;
   option [2] uses `bash` to remove `.autonovel/in-progress.lock`; option
   [3] does nothing.
</workflow>

<acceptance>
- Never writes files or runs rollback without explicit user confirmation.
- When no lock is present, the command prints the "nothing to resume"
  message and exits cleanly.
</acceptance>
