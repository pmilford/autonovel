---
name: autonovel:table-read
description: Voice every line of one or more scenes of the screenplay in its cast voice on a free local voice model (VoxCPM2), each voice designed from a written description so no real person's voice is used, every take checked by a transcriber (Whisper) and re-taken when it says other words; writes a recording per line and a manifest the shot list and the animatic time themselves from.
argument-hint: "--scene <ID> [--scene <ID> ...] --book <short-name> [--gpu <n>] [--force] [--remake-voices]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - books/{book}/film/screenplay/seq_*.fountain
  - books/{book}/film/bible/characters/*.yaml
  - books/{book}/film/audio/voices.yaml
  - books/{book}/film/audio/table_read/manifest.json
writes:
  - books/{book}/film/audio/voices.yaml
  - books/{book}/film/audio/voices/*.wav
  - books/{book}/film/audio/table_read/*.wav
  - books/{book}/film/audio/table_read/manifest.json
context_mode: book
---

<purpose>
A table read: the script's lines spoken aloud in the voices the film will
use, so the scene's timing comes from real speech and the author can hear
the dialogue before anything is filmed (stage F4, milestone M4 of
`docs/film-pipeline-plan.md`; at F5 the same voices become the film's).

It writes, under `books/{book}/film/audio/`:

- `voices.yaml`: the casting: for each speaking cue, the character's bible
  file, a written description of the voice, the sentence its reference clip
  says, where that clip is, and how it was made (`consent`).
- `voices/<cue>.wav` (+ `.txt`): each voice's reference clip, designed by
  the voice model from the description: no person's recording is used, so
  there is no one whose consent is needed.
- `table_read/<line ID>.wav`: every line, in screen order IDs (`S0104-L01`).
- `table_read/manifest.json`: each line's words, voice, length, how many
  takes it needed and what the transcriber heard.

The voice model (VoxCPM2, Apache-2.0) and the transcriber (faster-whisper)
run in their own Python environment on the user's GPU; autonovel only
writes the job and reads the result. A line's recording is reused while its
words and its voice are unchanged.

`--scene`: the scene(s) to voice (repeatable). `--gpu`: the card (default
0). `--force`: voice every line again. `--remake-voices`: design the
reference clips again (after changing a description).
</purpose>

<workflow>
**Read-failure policy.** The sequence's Fountain file is load-bearing: stop
if it is missing. The bible's character files are best-effort (a voice is
described from the script's character introduction when there is none).
Do not retry a failed `file_read`.

1. **Parse `$ARGUMENTS`.** Find each scene's sequence file in
   `books/{book}/film/screenplay/seq_NN.fountain` (the scene ID's first two
   digits are the sequence).

2. **See what the scenes need.** Use `bash` from the series root:

   ```
   autonovel mechanical table-read books/{book}/film/screenplay/seq_NN.fountain --scene <ID> --dry-run
   ```

   It lists each line with its ID and cue, which are current, which must be
   voiced, and every cue with no voice yet.

3. **Cast each voice that is missing** in
   `books/{book}/film/audio/voices.yaml` (write it with `file_write`,
   keeping every existing entry). For each cue: `character` (its bible file
   in `books/{book}/film/bible/characters/`), `design`: one sentence
   describing the voice from the bible's voice notes and the character's age,
   class and manner (pitch, texture, pace, mood; "a fourteen-year-old boy, a
   light clear voice on the edge of breaking, quiet and careful"); no real
   person, actor or singer is named; `ref_text`: a plain sentence of about
   fifteen words, not a line of the script, with no names; `ref`:
   `audio/voices/<cue in lower case>.wav`; `seed`; and `consent`:
   "synthetic: designed from the written description; no real person's
   voice or recording". Never point `ref` at a recording of a real person
   unless the author gives one with that person's written consent, kept in
   `film/consent/`, and the `consent` line says so. In a period film the
   characters' own language is carried by the script's language (SCREEN.md
   §1.7): the voices carry age, class and manner, not a foreign accent.
   Add to `lexicon` a respelling for any name the model says wrongly, and
   to `names` the words the transcriber may spell its own way.

4. **Voice the lines.** One GPU job at a time: check nothing else (an image
   or video server, another voice job) is running on the card. Then:

   ```
   autonovel mechanical table-read books/{book}/film/screenplay/seq_NN.fountain --scene <ID> --python <the TTS environment's python> --gpu <n> --format markdown
   ```

   (`$AUTONOVEL_TTS_PYTHON` can name the interpreter instead of `--python`.)
   A voice with no reference clip is designed first, from several seeds,
   keeping the take the transcriber hears best at a natural pace. Each line
   is then spoken in that voice, transcribed and re-taken up to four times
   when words are added, dropped or changed; the best take is kept.

5. **Check the result.** Read the table it prints. A line marked "never
   matched" was kept as the best of its takes: read what the transcriber
   heard. A name heard as another word is usually right (add it to `names`);
   a wrong or missing word is not: respell the trouble word in `lexicon` and
   re-run with `--force` for that scene. Note each voice's character in a
   sentence (how it sounds against its description), for the author.

6. **Report to the author**, in plain sentences: each voice (who, how it
   was made, that no real person's voice was used), each line with its
   length and anything the transcriber heard differently, the total spoken
   time per scene, and the paths. Then **Next:**
   1. Listen to `books/{book}/film/audio/table_read/` in screen order.
   2. `autonovel mechanical shot-check books/{book}/film/shots/<ID>.json --retime`
      times the shots from the recordings; then
      `/autonovel:animatic --scene <ID> --book {book}`.
</workflow>

<acceptance>
- Every line of the scenes has `books/{book}/film/audio/table_read/<line ID>.wav`
  and a manifest entry whose text matches the script.
- Every voice in `books/{book}/film/audio/voices.yaml` has a `consent` line;
  every designed voice names no real person; no recording of a real person
  is used without written consent on file.
- Every line was checked by the transcriber; any line kept without a match
  is named in the report with what was heard.
- No script, shot list or book file is written.
</acceptance>
