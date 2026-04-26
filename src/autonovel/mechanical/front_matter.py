"""Build a `front_matter.tex` for typeset's PDF path.

Reads optional `preface.md` (hand-authored) and `introduction.md`
(AI-generated, or hand-authored — the file is just a file) from the
book's root, converts paragraphs via the existing md_to_latex
pipeline, wraps each in a starred chapter heading (`\\chapter*{}` so
it's unnumbered and excluded from the chapter numbering), and
concatenates the result. The output is `\\input{}`-able from
novel.tex.

The `\\frontmatter` LaTeX command must precede this content (already
the case in novel.tex). When neither preface nor introduction
exists, returns ("", []) and the typeset workflow simply doesn't
write `front_matter.tex` — novel.tex's `\\IfFileExists` then
silently skips inclusion.

Markdown shape supported (intentionally narrow — the same shape
md_to_latex already handles):

  - paragraphs separated by blank lines
  - `*italic*`
  - smart-quote / em-dash / en-dash conversion
  - `---` scene breaks (rare in front matter; supported anyway)

Headings inside a preface/introduction file are NOT promoted to
`\\section{}` — front matter typically has one heading (the
chapter*) and uninterrupted prose under it. If a preface needs
sub-headings, hand-edit `front_matter.tex` after generation.
"""

from __future__ import annotations

from pathlib import Path

from .frontmatter import strip_yaml_frontmatter
from .latex import latex_escape, md_to_latex


def build_front_matter_tex(
    book_root: Path,
    *,
    output: Path | None = None,
) -> tuple[str, list[str]]:
    """Concatenate preface + introduction into one front-matter
    LaTeX block. Returns the generated TeX and a list of section
    titles included (`["Preface", "Introduction"]` etc.).

    Both source files are optional; when neither exists the helper
    returns ("", []) and writing is skipped.
    """
    sections: list[tuple[str, Path]] = []
    preface = book_root / "preface.md"
    introduction = book_root / "introduction.md"
    if preface.is_file():
        sections.append(("Preface", preface))
    if introduction.is_file():
        sections.append(("Introduction", introduction))

    if not sections:
        return "", []

    pieces: list[str] = []
    titles: list[str] = []
    for title, path in sections:
        body = strip_yaml_frontmatter(path.read_text(encoding="utf-8")).strip()
        # If the file opens with its own `# Title`, drop that line —
        # we emit our own canonical chapter* heading. (Same shape as
        # the ePub builder.)
        body_lines = body.splitlines()
        if body_lines and body_lines[0].strip().startswith("#"):
            body_lines = body_lines[1:]
            while body_lines and body_lines[0].strip() == "":
                body_lines.pop(0)
        body = "\n".join(body_lines)

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
