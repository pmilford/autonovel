"""Movie/teaser mode helpers (mechanical only — no LLM calls).

This package backs the movie-script + AI-video-teaser feature scoped in
``docs/prd-movie-teaser-mode.md`` and built per
``docs/impl-plan-movie-teaser.md``. It is **additive**: nothing here is
imported by the existing novel pipeline, so the book-writing tools are
unaffected whether or not teaser mode is ever used.

Phase 0 ships only this package marker plus the additive ``teaser`` /
``video`` optional dicts on :class:`autonovel.project.ProjectConfig`.
Later phases add: ``shots`` (the per-shot schema + ``teaser.json`` I/O),
``beats`` (beat-sheet structure), ``render_prompt`` (schema → provider
prose), ``providers`` (capability table), ``critique`` (self-critique
report shape), ``videoprovider`` (resolve-video-provider precedence),
``render`` (thin Pollinations-first render adapter), and ``assemble``
(ffmpeg cut list). Quality is judged by the LLM/vision judge in the
command bodies; Python here only does mechanical structure.
"""
