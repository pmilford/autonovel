"""Build a `back_matter.tex` for typeset's PDF path.

Reads optional `appendix.md` from the book's root, converts paragraphs
via the existing md_to_latex pipeline, wraps each in a starred
chapter heading (`\\chapter*{}` so it's unnumbered and excluded from
the chapter numbering), and concatenates the result. The output is
`\\input{}`-able from novel.tex, in the `\\backmatter` zone (after
the last chapter).

The `\\backmatter` LaTeX command must precede this content (already
the case in novel.tex). When the appendix doesn't exist, returns
("", []) and the typeset workflow simply doesn't write
`back_matter.tex` — novel.tex's `\\IfFileExists` then silently skips
inclusion.

Why a separate module from front_matter.py: front and back matter
sit in different LaTeX zones (`\\frontmatter` vs `\\backmatter`),
need different `\\input{}` lines in novel.tex, and grow at different
rates (back matter typically grows over multi-book series with
appendix sections accumulating). Keeping them in parallel files
matches the LaTeX layout and keeps the contract obvious.

Markdown shape supported (intentionally narrow — same as
front_matter.py):

  - paragraphs separated by blank lines
  - `*italic*`
  - smart-quote / em-dash / en-dash conversion
  - `---` scene breaks (rare but allowed)
  - `## Sub-heading` is allowed in appendix (unlike preface) since
    the appendix often has labelled sections (Timeline of events,
    Bios, Notes on sources, etc.). These render as `\\section*{}`
    in the LaTeX output.

Headings inside the appendix file:
  - `# Title` at the top is dropped — we emit our own canonical
    `\\chapter*{Appendix}` heading.
  - `## Section` lines are promoted to `\\section*{}` (unnumbered;
    not in the TOC by default, but appendix is itself a TOC entry
    so navigation still works).
"""

from __future__ import annotations

import re
from pathlib import Path

from .frontmatter import strip_yaml_frontmatter
from .latex import latex_escape, md_to_latex


_SUBHEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def build_back_matter_tex(
    book_root: Path,
    *,
    output: Path | None = None,
) -> tuple[str, list[str]]:
    """Concatenate appendix into one back-matter LaTeX block.
    Returns the generated TeX and a list of section titles included
    (`["Appendix"]` typically; future expansion can add more).

    The appendix file is optional; when absent the helper returns
    ("", []) and writing is skipped.
    """
    sections: list[tuple[str, Path]] = []
    appendix = book_root / "appendix.md"
    if appendix.is_file():
        sections.append(("Appendix", appendix))

    if not sections:
        return "", []

    pieces: list[str] = []
    titles: list[str] = []
    for title, path in sections:
        body = strip_yaml_frontmatter(path.read_text(encoding="utf-8")).strip()
        # Drop the `# Title` line if present (we emit our own).
        body_lines = body.splitlines()
        if body_lines and body_lines[0].strip().startswith("# "):
            body_lines = body_lines[1:]
            while body_lines and body_lines[0].strip() == "":
                body_lines.pop(0)
        body = "\n".join(body_lines)

        # Promote `## Sub-heading` to `\section*{Sub-heading}` BEFORE
        # md_to_latex runs (md_to_latex doesn't know about headings).
        body = _SUBHEADING_RE.sub(
            lambda m: f"\\section*{{{latex_escape(m.group(1))}}}",
            body,
        )

        latex_body = md_to_latex(body)
        chapter_block = (
            f"\\chapter*{{{latex_escape(title)}}}\n"
            f"\\addcontentsline{{toc}}{{chapter}}{{{latex_escape(title)}}}\n\n"
            f"{latex_body}\n"
        )
        pieces.append(chapter_block)
        titles.append(title)

    content = "\n\\clearpage\n\n".join(pieces)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    return content, titles
