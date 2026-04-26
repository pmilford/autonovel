"""Scene splitter — slice a chapter into scenes by scene-break markers.

A "scene" inside a chapter is the unit between scene breaks. Most LLM-
generated chapters use `***` on its own line as the break; some use
`---` (the latex.py mechanical knows about both). This helper produces
a deterministic per-scene index so /autonovel:evaluate can walk a
chapter scene-by-scene to score beat coverage (goal / conflict /
disaster-or-decision / consequence) per scene rather than per chapter,
and so /autonovel:brief can name weak scenes by index instead of
vague "tighten chapter 8".

Strips YAML frontmatter (chapter files start with `---\n…\n---\n`)
before splitting so a chapter's frontmatter delimiter never registers
as a scene break.

Returns a list of scene dicts with stable, JSON-emittable shape — the
LLM judge in evaluate.md reads the JSON and scores each scene; nothing
in this module knows or cares about beats.
"""

from __future__ import annotations

import re

from .frontmatter import strip_yaml_frontmatter


# A scene-break line is a line containing only `***` or `---` (with
# optional surrounding whitespace), nothing else. Markdown horizontal
# rules use the same syntax; in chapter prose those have always been
# scene breaks.
_BREAK_LINE_RE = re.compile(r"^\s*(\*\s*\*\s*\*|-\s*-\s*-)\s*$")


def split_scenes(text: str) -> list[dict]:
    """Split a chapter's prose into scenes by `***` or `---` break
    lines. Returns a list of scene dicts ordered by appearance.

    Each scene dict carries:
      - `index`: 1-based scene index within the chapter.
      - `text`: the scene's prose (no leading/trailing blank lines).
      - `word_count`: int.
      - `opening_line`: first non-empty line of the scene (may be
        truncated to ~120 chars for compact output).
      - `closing_line`: last non-empty line of the scene (similarly
        truncated).

    Empty scenes (zero words) are dropped — a chapter that opens or
    closes with a scene break would otherwise produce phantom scenes
    with index 1 or last that the judge has nothing to score.

    A chapter with no scene breaks is one scene; the result list has
    length 1.
    """
    body = strip_yaml_frontmatter(text)
    chunks: list[str] = []
    current: list[str] = []
    for line in body.splitlines():
        if _BREAK_LINE_RE.match(line):
            if current:
                chunks.append("\n".join(current))
                current = []
            continue
        current.append(line)
    if current:
        chunks.append("\n".join(current))

    scenes: list[dict] = []
    for chunk in chunks:
        stripped = chunk.strip("\n")
        word_count = len(stripped.split())
        if word_count == 0:
            continue
        non_empty = [ln for ln in stripped.splitlines() if ln.strip()]
        opening = (non_empty[0].strip() if non_empty else "")
        closing = (non_empty[-1].strip() if non_empty else "")
        scenes.append({
            "index": len(scenes) + 1,
            "text": stripped,
            "word_count": word_count,
            "opening_line": _truncate(opening, 120),
            "closing_line": _truncate(closing, 120),
        })
    return scenes


def _truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "…"
