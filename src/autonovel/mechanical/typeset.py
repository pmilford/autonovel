"""Typeset-side helpers: template substitution, output filenames.

Two pieces commands/typeset.md previously did with bash:

  1. `sed -i 's/@TITLE@/.../g' ...` to substitute placeholders in
     `novel.tex`. This is fragile — a title containing `/` (a date, a
     URL fragment) or `&` or `\\` breaks the sed in surprising ways and
     produces a malformed .tex that tectonic chokes on. Author testing
     2026-04-25 hit a "first run didn't work" symptom consistent with
     this fragility.
  2. Hard-coded `novel.pdf` / `novel.epub` output names. Re-running
     typeset overwrote the previous build, making it hard to keep
     side-by-side versions to compare across revisions.

This module replaces the bash with two deterministic Python helpers:
`render_novel_tex(template, substitutions)` does string substitution
safely (no sed, no regex on user input), and `output_filename(slug,
kind, when=...)` returns the canonical timestamped filename.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def render_novel_tex(template: str, substitutions: dict[str, str]) -> str:
    """Replace `@KEY@` placeholders in *template* with the corresponding
    values from *substitutions*. Pure string replacement — no regex, no
    shell interpretation of either side. Each value is used verbatim;
    callers escape for LaTeX before passing in.

    Unknown placeholders in the template are left as-is (so a future
    template addition doesn't silently fail). Missing values raise
    KeyError so a typo in the substitution dict surfaces loudly rather
    than producing a half-rendered .tex tectonic will reject with a
    confusing error.
    """
    out = template
    for key, value in substitutions.items():
        out = out.replace(f"@{key}@", value)
    return out


def output_filename(slug: str, kind: str, *, when: datetime | None = None) -> str:
    """Return the canonical timestamped output filename for a typeset
    artefact. Format: `<slug>_<YYYYMMDD>_<HHMM>.<kind>`.

    `kind` is the file extension without dot — typically `pdf` or
    `epub`. `when` defaults to "now in local time"; tests pass an
    explicit datetime to lock the output deterministically.

    Slug is normalised: lowercase, non-alphanumeric → `-`, collapsed
    runs of `-`. This matches the book-name convention used elsewhere
    in autonovel (mirrors how `new-book` slugs the user's input) so
    the filename plays nicely with shell globbing and Windows file
    explorer.
    """
    when = when or datetime.now()
    safe_slug = _slugify(slug)
    timestamp = when.strftime("%Y%m%d_%H%M")
    return f"{safe_slug}_{timestamp}.{kind}"


def latest_filename(slug: str, kind: str) -> str:
    """Return the `<slug>_latest.<kind>` filename — the convenience
    pointer typeset writes alongside each timestamped build so
    downstream readers (`open <book>_latest.pdf`) don't need to chase
    the most recent timestamp.
    """
    return f"{_slugify(slug)}_latest.{kind}"


def _slugify(s: str) -> str:
    """Lowercase, collapse non-alphanumeric to `-`, strip leading /
    trailing `-`. Keeps `_` as itself (book names like `the_inquisitor`
    survive intact)."""
    out: list[str] = []
    for ch in s.lower():
        if ch.isalnum() or ch in ("-", "_"):
            out.append(ch)
        else:
            out.append("-")
    raw = "".join(out)
    # Collapse runs of `-` to a single `-`.
    while "--" in raw:
        raw = raw.replace("--", "-")
    return raw.strip("-")
