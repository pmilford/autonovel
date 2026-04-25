---
name: autonovel:audiobook-voices
description: Configure or list ElevenLabs voice IDs for this book's speakers.
argument-hint: "--book <short-name> [--list | --set <SPEAKER>=<voice-id> ...]"
model_tier: light
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - shared/characters.md
  - books/{book}/audiobook/voices.yaml
  - books/{book}/audiobook/voices.yaml.example
writes:
  - books/{book}/audiobook/voices.yaml
context_mode: book
---

<purpose>
Replace `gen_audiobook.py --list-voices` + the manual-edit step for
`audiobook_voices.json`. One entry point for the two things a user
needs when setting up voices:

  - `--list` prints every voice the user's ElevenLabs account exposes
    (id, name, gender, age, accent) so they know what to choose from.
  - `--set NARRATOR=abc123 CASS=def456 ...` updates the book's
    `voices.yaml` atomically.

Light tier — no LLM, just an ElevenLabs API call and YAML file edit.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` is required. Exactly one
   of `--list` or one-or-more `--set <SPEAKER>=<voice-id>` pairs must
   be present; neither is a usage error.

2. Resolve `ELEVENLABS_API_KEY` from the environment. If missing,
   stop with a single-line message naming the env var and point at
   `.env.example`.

3. `--list` mode: use `bash` to call
   `python3 -c "from elevenlabs.client import ElevenLabs; import os, json; r = ElevenLabs(api_key=os.environ['ELEVENLABS_API_KEY']).voices.get_all(); print(json.dumps([{'id': v.voice_id, 'name': v.name, **(v.labels or {})} for v in r.voices], indent=2))"`.
   Parse the JSON and print a table: name · id · gender · age · accent.
   Do NOT write any files in this mode.

4. `--set` mode:
   a. Use `file_read` on the existing
      `books/{book}/audiobook/voices.yaml` (it is an existence-check —
      if missing, seed from `shared/characters.md` so every named
      character gets an unconfigured entry with
      `voice_id: REPLACE_WITH_VOICE_ID`). The shape to write matches
      `books/{book}/audiobook/voices.yaml.example` (shipped by
      `autonovel new-book`): an uppercase speaker key per character,
      plus a `NARRATOR` entry, each with `voice_id`, optional
      `description`, optional `why`. Preserve the optional metadata
      keys when round-tripping.
   b. For each `SPEAKER=id` pair in the arguments, update
      `voices[SPEAKER].voice_id`. If the speaker name is not in the
      current map, reject with a single-line message listing valid
      speaker keys — this catches typos like `CAS` for `CASS`. The user
      explicitly adds a new speaker by running the command with a
      fresh `--speaker-add <NAME>` flag first (not in PR 7; noted as
      follow-up).
   c. Use `file_write` to save the YAML with stable key ordering.

5. Print a one-screen summary: updated speakers, count still
   unconfigured (`voice_id: REPLACE_WITH_VOICE_ID`), and — if any
   remain unconfigured — the `--list` follow-up command.
</workflow>

<acceptance>
- `--list` mode writes no files and prints every voice available on
  the user's account.
- `--set` mode updates `books/{book}/audiobook/voices.yaml` and
  preserves all unrelated keys.
- A typo speaker name in `--set` is rejected before any write.
</acceptance>
