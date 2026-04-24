"""Markdown-to-LaTeX chapter builder.

Ported from the pre-rewrite `typeset/build_tex.py`. Pure-text helpers
plus a `build_chapters_tex(chapters_dir, art_dir)` entry point that
emits `chapters_content.tex`.

The scope is deliberately narrow: escape, scene-break translation,
drop-cap, chapter-ornament `\\includegraphics{…}`. Everything else
(page layout, fonts, title page) lives in `typeset/novel.tex`, which
is a template we copy into each book's typeset dir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


def latex_escape(text: str) -> str:
    """Escape the five characters that need it in running LaTeX text.

    Backslash is NOT escaped — we assume the md_to_latex pipeline has
    already emitted any `\\textit{...}` or `\\scenebreak` macros before
    escape runs, and that the input markdown does not contain literal
    backslashes.
    """
    return (
        text
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("$", r"\$")
        .replace("#", r"\#")
        .replace("_", r"\_")
    )


def md_to_latex(body: str) -> str:
    """Convert chapter Markdown to inline LaTeX.

    Handles: `---` scene breaks; `*italic*`; smart quotes / em+en
    dashes / ellipses; straight ASCII quotes folded to ``…''.
    Paragraphs are preserved as blank-line separated text.
    """
    out: list[str] = []
    for line in body.split("\n"):
        s = line.strip()
        if s == "---":
            out.append("\n\\scenebreak\n")
        elif s == "":
            out.append("")
        else:
            # italic before escape: leave the `\textit{}` alone, escape the
            # content separately.
            # Do *italic* → \textit{italic}
            s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\\textit{\1}", s)
            s = latex_escape(s)
            s = s.replace("—", "---")
            s = s.replace("–", "--")
            s = s.replace("“", "``").replace("”", "''")
            s = s.replace("‘", "`").replace("’", "'")
            s = s.replace("…", "\\ldots{}")
            # Straight ASCII quotes → LaTeX open/close
            s = re.sub(r'(?<=\s)"(?=\w)', "``", s)
            s = re.sub(r'^"(?=\w)', "``", s)
            s = re.sub(r'(?<=\w)"(?=[\s.,;:!?\-])', "''", s)
            s = re.sub(r'(?<=\w)"$', "''", s)
            s = re.sub(r'(?<=[.?!])"', "''", s)
            s = re.sub(r'(?<=\s)"', "``", s)
            s = re.sub(r'"(?=\s)', "''", s)
            s = re.sub(r'^"', "``", s)
            out.append(s)
    return "\n".join(out)


def make_drop_cap(latex_body: str) -> str:
    """Wrap the first letter of the first paragraph in `\\lettrine{…}{…}`.

    Idempotent only in the weak sense — calling twice on the same body
    produces malformed LaTeX. Callers should only apply once per
    chapter.
    """
    lines = latex_body.split("\n")
    first_para: list[str] = []
    rest_start = 0
    found = False
    for i, line in enumerate(lines):
        if not found and line.strip():
            found = True
        if found:
            if line.strip() == "" or line.strip().startswith("\\scenebreak"):
                rest_start = i
                break
            first_para.append(line)
        else:
            rest_start = i + 1
    if not first_para:
        return latex_body
    para_text = " ".join(first_para)
    rest = "\n".join(lines[rest_start:])
    if len(para_text) < 2:
        return latex_body
    first_letter = para_text[0]
    after_first = para_text[1:]
    space_idx = after_first.find(" ")
    if space_idx > 0:
        word_rest = after_first[:space_idx]
        para_rest = after_first[space_idx:]
    else:
        word_rest = after_first
        para_rest = ""
    drop = (
        f"\\lettrine[lines=2, lhang=0.1, nindent=0.2em]"
        f"{{{first_letter}}}{{{word_rest}}}{para_rest}"
    )
    return drop + "\n\n" + rest


@dataclass
class ChapterBuildReport:
    path: Path
    chapter: int
    title: str
    ornament: Path | None


def _chapter_title(raw: str) -> str:
    t = raw.lstrip("# ").strip()
    if ": " in t:
        _, t = t.split(": ", 1)
    return t


def find_ornament(art_dir: Path, chapter: int) -> Path | None:
    """Prefer a vectorised `art/pdf/ornament_chNN.pdf` over the raster PNG.

    Returns `None` if neither is present.
    """
    pdf = art_dir / "pdf" / f"ornament_ch{chapter:02d}.pdf"
    png = art_dir / f"ornament_ch{chapter:02d}.png"
    if pdf.exists():
        return pdf
    if png.exists():
        return png
    return None


def build_chapters_tex(
    chapters_dir: Path,
    *,
    art_dir: Path | None = None,
    output: Path | None = None,
) -> tuple[str, list[ChapterBuildReport]]:
    """Build `chapters_content.tex` from every `ch_*.md` in `chapters_dir`.

    Returns the generated TeX text and a per-chapter report. Writing to
    disk is optional — if `output` is given the text is also written.
    """
    chapter_files = sorted(chapters_dir.glob("ch_*.md"))
    if not chapter_files:
        raise FileNotFoundError(f"no ch_*.md under {chapters_dir}")
    pieces: list[str] = []
    reports: list[ChapterBuildReport] = []
    for ch_path in chapter_files:
        num_str = ch_path.stem.split("_")[-1]
        try:
            num = int(num_str)
        except ValueError as exc:
            raise ValueError(f"cannot parse chapter number from {ch_path.name!r}") from exc
        text = ch_path.read_text(encoding="utf-8")
        lines = text.strip().split("\n")
        title = _chapter_title(lines[0]) if lines else f"Chapter {num}"
        body = "\n".join(lines[1:]).strip()
        latex_body = md_to_latex(body)
        latex_body = make_drop_cap(latex_body)
        ornament_tex = ""
        ornament: Path | None = None
        if art_dir is not None:
            ornament = find_ornament(art_dir, num)
        if ornament is not None:
            ornament_tex = (
                "\\begin{center}\n"
                f"\\includegraphics[width=0.8in]{{{ornament.as_posix()}}}\n"
                "\\end{center}\n"
                "\\vspace{0.15in}\n"
            )
        pieces.append(
            f"\\chapter{{{latex_escape(title)}}}\n\n{ornament_tex}{latex_body}\n"
        )
        reports.append(ChapterBuildReport(
            path=ch_path,
            chapter=num,
            title=title,
            ornament=ornament,
        ))
    content = "\n\\clearpage\n\n".join(pieces)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    return content, reports
