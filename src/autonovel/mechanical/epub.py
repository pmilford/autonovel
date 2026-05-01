"""ePub-ready combined-markdown builder.

Bug story (2026-04-25): the previous ePub path passed
`books/{book}/chapters/ch_*.md` directly to pandoc as a shell glob,
which:

  1. Matched `ch_NN.summary.md` as well as `ch_NN.md`, so the
     continuity-handoff summaries (POV / threads_opened /
     threads_closed) leaked into the rendered ePub as if they were
     reader content.
  2. Did not strip YAML frontmatter from each chapter, so `book:`,
     `word_count:`, `pov:` etc. rendered as visible prose at the top
     of every chapter.
  3. Did not normalise chapter headings, so pandoc's chapter-detection
     was unreliable — "chapters were not well marked in the epub" per
     the user.

This module takes the same chapters dir and emits one combined
markdown file with:

  - Only `ch_NN.md` files included (`iter_chapter_files()` already
    excludes `ch_NN.summary.md` and other adjuncts).
  - YAML frontmatter stripped from each chapter (shared helper).
  - A canonical `# Chapter N: Title` (or `# Chapter N` when the
    chapter file has no `# …` heading) at the top of each chapter,
    so pandoc reliably sees a top-level division per chapter.
  - Chapter bodies separated by blank lines (no extra delimiter
    needed — pandoc treats every `# …` line as a top-level division).

Pandoc invocation paired with this output: pass the combined file
plus `--top-level-division=chapter --toc` and the resulting ePub
has a clean per-chapter spine with proper TOC entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .frontmatter import strip_yaml_frontmatter


@dataclass
class CombinedChapter:
    chapter: int
    title: str
    word_count: int


def build_epub_md(
    chapters_dir: Path,
    *,
    output: Path | None = None,
    art_dir: Path | None = None,
) -> tuple[str, list[CombinedChapter]]:
    """Concatenate `ch_NN.md` files into one ePub-ready markdown blob.

    Returns the combined text and a per-chapter report. Writing to
    disk is optional — if `output` is given the text is also written.

    Excludes `ch_NN.summary.md` and any adjunct files via the shared
    `iter_chapter_files()` filter.

    `art_dir` (defaults to `chapters_dir.parent / "art"`) is searched
    for per-chapter ornament PNGs (`ornament_chNN.png`); when found,
    a markdown image reference is emitted at the top of each chapter
    so pandoc embeds the PNG into the ePub. User 2026-04-30 reported
    "the ePub doesn't show the images" — root cause was that
    build_epub_md only emitted prose; pandoc never saw any image
    references.
    """
    from ..paths import iter_chapter_files
    chapter_files = iter_chapter_files(chapters_dir)
    if not chapter_files:
        raise FileNotFoundError(f"no ch_*.md under {chapters_dir}")
    if art_dir is None:
        art_dir = chapters_dir.parent / "art"

    pieces: list[str] = []
    reports: list[CombinedChapter] = []
    for ch_path in chapter_files:
        num_str = ch_path.stem.split("_")[-1]
        try:
            num = int(num_str)
        except ValueError as exc:
            raise ValueError(f"cannot parse chapter number from {ch_path.name!r}") from exc

        body = strip_yaml_frontmatter(ch_path.read_text(encoding="utf-8")).strip()

        # Find the chapter's own `# …` heading if it has one; otherwise
        # synthesise `Chapter N`. Either way we emit a canonical
        # `# Chapter N: <title>` header so pandoc sees one top-level
        # division per chapter.
        title = _extract_chapter_title(body, default=f"Chapter {num}")
        # If body opens with a `# Title` line, drop it — we're going to
        # emit our own canonical header in front of the prose.
        body_without_title = _strip_leading_heading(body)

        canonical_heading = f"# Chapter {num}: {title}" if title and not title.lower().startswith("chapter ") else f"# {title}"
        # Per-chapter ornament — a small image at the chapter
        # opening, parallel to the LaTeX `\includegraphics` step in
        # build_chapters_tex. Pandoc embeds the referenced PNG into
        # the ePub bundle automatically when it sees a `![](path)`
        # markdown image. Use a relative path from the chapters_dir
        # since pandoc resolves image paths relative to the input
        # markdown file.
        ornament_md = ""
        ornament_png = art_dir / f"ornament_ch{num:02d}.png"
        if ornament_png.is_file():
            try:
                rel = ornament_png.relative_to(chapters_dir.parent)
            except ValueError:
                rel = ornament_png
            # Centered image. Pandoc's gfm extension respects an
            # explicit width attribute; 60% works on most readers.
            ornament_md = (
                f'\n<p style="text-align: center;">'
                f'<img src="{rel}" alt="" style="width: 60%; max-width: 400px;" />'
                f'</p>\n\n'
            )
        pieces.append(
            f"{canonical_heading}\n{ornament_md}\n{body_without_title}".rstrip() + "\n"
        )
        reports.append(CombinedChapter(
            chapter=num,
            title=title,
            word_count=len(body_without_title.split()),
        ))

    content = "\n".join(pieces)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    return content, reports


def _extract_chapter_title(body: str, *, default: str) -> str:
    """Return the chapter's title from the first non-empty line if
    that line is a markdown heading (`# …`); otherwise *default*.
    Treats `# Chapter N: Title` and `# Title` and `# N. Title` the
    same way — strip the leading marker and return the right-hand side.
    """
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            heading = stripped.lstrip("# ").strip()
            # `Chapter N: Real Title` → `Real Title`
            if ": " in heading:
                _, right = heading.split(": ", 1)
                if right.strip():
                    return right.strip()
            # `N. Real Title` → `Real Title`
            if ". " in heading and heading.split(". ", 1)[0].isdigit():
                return heading.split(". ", 1)[1].strip()
            return heading or default
        return default
    return default


def _strip_leading_heading(body: str) -> str:
    """If *body* opens with a `# …` line, drop that line plus any
    immediately-following blank line. Used because we emit our own
    canonical heading and don't want it to appear twice.
    """
    lines = body.splitlines()
    if not lines:
        return body
    first = lines[0].strip()
    if not first.startswith("#"):
        return body
    out = lines[1:]
    while out and out[0].strip() == "":
        out.pop(0)
    return "\n".join(out)
