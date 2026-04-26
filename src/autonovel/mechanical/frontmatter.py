"""Strip YAML frontmatter from chapter prose.

Chapter files (`books/{book}/chapters/ch_NN.md`) start with a YAML
block fenced by `---` lines, e.g.:

    ---
    book: ...
    chapter: 5
    pov: Tommaso
    word_count: 3245
    ---
    # Chapter title

    The actual prose…

Every renderer that consumes chapter prose for human display (PDF
typesetter, ePub builder, scene splitter for evaluation) must strip
the frontmatter first — leaking `book: …`, `word_count: 3245`, etc.
into the rendered chapter is the bug pattern this helper exists to
prevent.

Behaviour:

  - Text starting with `---\\n` (frontmatter open) and containing a
    later `---\\n` (frontmatter close) → return the text after the
    closing `---`.
  - Text not starting with `---\\n` → returned unchanged.
  - Text starting with `---\\n` but with no closing `---` → returned
    unchanged (treat as malformed; safer than swallowing prose).
"""

from __future__ import annotations


def strip_yaml_frontmatter(text: str) -> str:
    """Remove a leading `---\\n…\\n---\\n` YAML frontmatter block.

    Returns the body that follows. If the text doesn't open with
    `---`, returned unchanged.
    """
    if not text.startswith("---"):
        return text
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "".join(lines[i + 1:])
    # No closing `---`: malformed; return as-is.
    return text
