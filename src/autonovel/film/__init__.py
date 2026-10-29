"""The film stages after the screenplay (docs/film-pipeline-plan.md, F3-F4).

- `shots`: the shot list's schema and its checks (coverage of every line
  and action paragraph, the 180-degree line, eyelines, continuity between
  shots, durations from the lines and the action, the look's rules).
- `comfy`: a small client for a local ComfyUI server and the keyframe
  workflows the storyboard renders through.
- `storyboard`: the storyboard manifest and its render loop (takes are
  never overwritten; each frame's verdict is recorded).
- `table_read`: the voice casting file and the per-line render job, run
  by a separate TTS engine script in its own Python environment.
- `animatic`: stills timed to the read and the action, with the shot
  list's camera moves, assembled with ffmpeg.

Nothing here calls a language model. Image and voice models run in their
own processes (a ComfyUI server; a TTS engine script) on the user's own
machine.
"""
