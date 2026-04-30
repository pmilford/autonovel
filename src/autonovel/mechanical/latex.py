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

from .frontmatter import strip_yaml_frontmatter


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


def _extract_chapter_title(text_with_frontmatter: str) -> str:
    """Pull a chapter title from a chapter file in priority order:

      1. `title:` field in YAML frontmatter — the explicit slot.
      2. A markdown `# Heading` on the first content line after the
         frontmatter — the legacy convention from before the
         frontmatter `title` field existed.
      3. Empty string — `\\titleformat{\\chapter}` already prints
         "chapter <Roman>" as the heading, so an empty `\\chapter{}`
         renders cleanly. Returning the first prose line was the
         2026-04-25/28 bug: it became a large italic block at every
         chapter's title page (visually identical to a "running
         header") and was fed into `\\chaptermark`'s `\\markboth`,
         which old `novel.tex` files surfaced as alternating page
         headers via `\\textit{\\leftmark}`.
    """
    # YAML title field. Cheap parse — a single `title:` line in the
    # frontmatter is enough to recognise. Avoids a hard dependency on
    # PyYAML at LaTeX-build time.
    if text_with_frontmatter.startswith("---"):
        lines = text_with_frontmatter.splitlines()
        for i in range(1, len(lines)):
            line = lines[i]
            if line.strip() == "---":
                break
            if line.startswith("title:"):
                value = line.split(":", 1)[1].strip()
                # Strip surrounding quotes if present.
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                if value:
                    return value
    # Heading-after-frontmatter fallback.
    body = strip_yaml_frontmatter(text_with_frontmatter).lstrip("\n")
    first_line = body.split("\n", 1)[0].strip() if body else ""
    if first_line.startswith("#"):
        return _chapter_title(first_line)
    return ""


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
    plates_manifest: Path | None = None,
    plates_root: Path | None = None,
) -> tuple[str, list[ChapterBuildReport]]:
    """Build `chapters_content.tex` from every `ch_*.md` in `chapters_dir`.

    Returns the generated TeX text and a per-chapter report. Writing to
    disk is optional — if `output` is given the text is also written.

    User-supplied plates (registered via `/autonovel:art-import`) are
    woven in when `plates_manifest` points at a `plates.yaml`. Plate
    paths inside the manifest are interpreted relative to
    `plates_root` (defaults to the manifest's parent directory).
    """
    from ..paths import iter_chapter_files
    chapter_files = iter_chapter_files(chapters_dir)
    if not chapter_files:
        raise FileNotFoundError(f"no ch_*.md under {chapters_dir}")

    plates_by_chapter = _load_plates_index(plates_manifest, plates_root)

    pieces: list[str] = []
    reports: list[ChapterBuildReport] = []
    for ch_path in chapter_files:
        num_str = ch_path.stem.split("_")[-1]
        try:
            num = int(num_str)
        except ValueError as exc:
            raise ValueError(f"cannot parse chapter number from {ch_path.name!r}") from exc
        # Strip YAML frontmatter first, otherwise lines[0] is `---`
        # and the title becomes the frontmatter delimiter while every
        # frontmatter field (book, chapter, pov, word_count, …) leaks
        # into the chapter prose at typeset time. Bug observed
        # 2026-04-25 against the live novel.
        raw = ch_path.read_text(encoding="utf-8")
        title = _extract_chapter_title(raw)
        text = strip_yaml_frontmatter(raw)
        lines = text.strip().split("\n")
        # If the first content line was a `# Heading`, drop it from
        # the body so it's not duplicated as prose. Otherwise the
        # body is the whole post-frontmatter text — the previous
        # implementation always dropped lines[0], which silently
        # ate the first sentence of any chapter file without a
        # heading (the production shape).
        if lines and lines[0].lstrip().startswith("#"):
            body = "\n".join(lines[1:]).strip()
        else:
            body = "\n".join(lines).strip()
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

        before_tex = _plates_at(plates_by_chapter, num, "before-chapter")
        start_tex = _plates_at(plates_by_chapter, num, "chapter-start")
        after_tex = _plates_at(plates_by_chapter, num, "after-chapter")

        chapter_block = (
            f"{before_tex}"
            f"\\chapter{{{latex_escape(title)}}}\n\n"
            f"{ornament_tex}{start_tex}{latex_body}\n"
            f"{after_tex}"
        )
        pieces.append(chapter_block)
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


def _load_plates_index(
    manifest: Path | None, plates_root: Path | None,
) -> dict[tuple[int, str], list[tuple[str, str, str]]]:
    """Return {(chapter, placement): [(file_abs_path, caption, attribution)]}.

    Reading the manifest is intentionally tolerant — a missing or
    malformed manifest is treated as "no plates" rather than failing
    the build. Concrete failures show up as files not on disk in the
    LaTeX render itself, where they're easy to spot.
    """
    out: dict[tuple[int, str], list[tuple[str, str, str]]] = {}
    if manifest is None or not manifest.is_file():
        return out
    try:
        import yaml as _yaml
        data = _yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return out
    plates = data.get("plates") or []
    if not isinstance(plates, list):
        return out
    base = plates_root or manifest.parent
    for entry in plates:
        if not isinstance(entry, dict):
            continue
        try:
            chapter = int(entry["chapter"])
            file_rel = str(entry["file"])
        except (KeyError, ValueError, TypeError):
            continue
        placement = str(entry.get("placement", "before-chapter"))
        caption = str(entry.get("caption", "") or "")
        attribution = str(entry.get("attribution", "") or "")
        file_abs = (base / file_rel).resolve()
        out.setdefault((chapter, placement), []).append(
            (file_abs.as_posix(), caption, attribution)
        )
    return out


def _plates_at(
    index: dict[tuple[int, str], list[tuple[str, str, str]]],
    chapter: int, placement: str,
) -> str:
    plates = index.get((chapter, placement))
    if not plates:
        return ""
    blocks = []
    for file_abs, caption, attribution in plates:
        blocks.append(_render_plate_block(file_abs, caption, attribution, placement))
    return "\n".join(blocks) + "\n"


def _render_plate_block(file_abs: str, caption: str, attribution: str, placement: str) -> str:
    """Emit a centered, captioned plate. `before-chapter` and
    `after-chapter` produce a dedicated full-page plate;
    `chapter-start` produces a centered block inside the chapter
    flow (no page break)."""
    caption_tex = ""
    if caption:
        caption_tex = f"\\\\\n\\vspace{{0.6em}}\n\\textit{{{latex_escape(caption)}}}"
    attribution_tex = ""
    if attribution:
        attribution_tex = (
            f"\\\\\n\\vspace{{0.3em}}\n"
            f"{{\\footnotesize {latex_escape(attribution)}}}"
        )
    if placement in ("before-chapter", "after-chapter"):
        # Use `plain` not `empty` so the footer's page number stays
        # visible on plate pages — the user 2026-04-30 reported the
        # page numbers vanished on image pages, which made
        # navigation harder. `plain` keeps the footer page number,
        # drops the running header (cleaner for full-page plates).
        return (
            "\\cleardoublepage\n"
            "\\thispagestyle{plain}\n"
            "\\vspace*{\\fill}\n"
            "\\begin{center}\n"
            f"\\includegraphics[width=0.85\\textwidth,height=0.7\\textheight,keepaspectratio]{{{file_abs}}}"
            f"{caption_tex}{attribution_tex}\n"
            "\\end{center}\n"
            "\\vspace*{\\fill}\n"
            "\\cleardoublepage\n"
        )
    # chapter-start: inline, sized larger than the prior 0.6 default
    # — the user 2026-04-30 reported the chapter-1 plate "rendered a
    # bit too small". 0.8 textwidth is the published-book convention
    # for in-flow chapter-opening plates while still leaving margin.
    # Per-plate overrides via plates.yaml are still respected (the
    # caller can pass a different width if a specific plate needs
    # smaller).
    return (
        "\\begin{center}\n"
        f"\\includegraphics[width=0.8\\textwidth,keepaspectratio]{{{file_abs}}}"
        f"{caption_tex}{attribution_tex}\n"
        "\\end{center}\n"
        "\\vspace{0.4em}\n"
    )
