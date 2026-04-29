"""Per-chapter motif tracker.

Some books reward repetition of a central image — the bell, the
apothecary's mortar, a recurring colour, an animal that means
something in the book's emotional grammar. AI drafts tend to under-
or over-use these images: the writer drops a motif in a strong
opening chapter, then forgets it for ten chapters; or hammers it in
every paragraph until it stops carrying weight.

This is the mechanical scanner half (FUTURE-TODOS #22 from the live
author session). The judgment half — *should* this motif appear in
this chapter? — is left to the writer or to a future LLM-based pass.
This file only counts.

Config: per-book `books/<book>/motifs.md` lists motifs as bullet
points. Format::

    # Motifs

    - bells: bell, bells, ringing, peal, toll
    - mortar: mortar, pestle, herb, herbs, balm
    - river: river, current, banks, water

The first colon-separated token is the motif slug; everything after
is a comma-separated list of keywords. Keywords are case-insensitive
and matched on word-boundary regex so "bell" doesn't match
"bellhop". Lines that don't match the bullet shape are ignored, so
the file may also contain prose / commentary.

Output: a `MotifReport` with per-chapter density rows + a list of
warnings flagging motifs that drop to zero in the *back half* of
the book (story reaches the close without revisiting the image).
The mechanical CLI renders the report as a markdown table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..paths import iter_chapter_files


_BULLET_RE = re.compile(r"^\s*-\s*([A-Za-z0-9_-]+)\s*:\s*(.+?)\s*$")


@dataclass
class Motif:
    slug: str
    keywords: list[str]

    def pattern(self) -> re.Pattern[str]:
        # Word-boundary match, case-insensitive, longest keywords
        # first so `bells` is preferred over `bell` when both
        # appear in the keyword list.
        kws = sorted(self.keywords, key=len, reverse=True)
        alt = "|".join(re.escape(k) for k in kws)
        return re.compile(rf"\b(?:{alt})\b", re.IGNORECASE)


@dataclass
class ChapterRow:
    chapter: int
    word_count: int
    counts: dict[str, int] = field(default_factory=dict)


@dataclass
class Warning_:
    chapter: int
    motif: str
    message: str


@dataclass
class MotifReport:
    motifs: list[Motif]
    rows: list[ChapterRow]
    warnings: list[Warning_]

    def to_dict(self) -> dict:
        return {
            "motifs": [m.slug for m in self.motifs],
            "rows": [
                {"chapter": r.chapter, "word_count": r.word_count,
                 "counts": dict(r.counts)} for r in self.rows
            ],
            "warnings": [
                {"chapter": w.chapter, "motif": w.motif, "message": w.message}
                for w in self.warnings
            ],
        }


def parse_motifs_file(path: Path) -> list[Motif]:
    """Read `motifs.md` and return a list of Motif records.

    Returns an empty list if the file is missing or empty. Skips
    bullet lines whose keyword list is empty or just whitespace.
    """
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    out: list[Motif] = []
    seen: set[str] = set()
    for line in text.splitlines():
        m = _BULLET_RE.match(line)
        if not m:
            continue
        slug = m.group(1).lower()
        kw_raw = m.group(2)
        keywords = [k.strip() for k in kw_raw.split(",") if k.strip()]
        if not keywords:
            continue
        if slug in seen:
            continue  # duplicate slug — first wins, rest ignored
        seen.add(slug)
        out.append(Motif(slug=slug, keywords=keywords))
    return out


def scan_chapter(text: str, motifs: list[Motif]) -> tuple[int, dict[str, int]]:
    """Strip the YAML frontmatter (if any) before counting, so motif
    keywords inside `---` blocks (e.g. `events: [bell-toll]`) don't
    inflate the prose-side counts. Returns (word_count, {slug: hits})."""
    body = _strip_frontmatter(text)
    counts: dict[str, int] = {}
    for motif in motifs:
        counts[motif.slug] = len(motif.pattern().findall(body))
    word_count = len(re.findall(r"\b\w+\b", body))
    return word_count, counts


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    # Find the closing fence on its own line.
    parts = text.split("\n", 1)
    if len(parts) < 2:
        return text
    rest = parts[1]
    end = rest.find("\n---\n")
    if end == -1:
        return text
    return rest[end + len("\n---\n"):]


def build_report(book_root: Path) -> MotifReport:
    """Scan every `ch_NN.md` under `book_root/chapters/` against
    motifs declared in `book_root/motifs.md`. Returns a MotifReport.

    Warnings: a motif that hit zero counts in any chapter past the
    halfway point of the book emits a warning. (The cutoff is
    `chapters_total // 2 + 1`, so a 10-chapter book flags zero-hit
    chapters from chapter 6 onward.) Books with fewer than 4
    chapters skip the back-half warning logic entirely; you can't
    diagnose a motif drop in a 3-chapter book.
    """
    motifs = parse_motifs_file(book_root / "motifs.md")
    rows: list[ChapterRow] = []
    chapter_paths = iter_chapter_files(book_root / "chapters")
    for path in chapter_paths:
        n_match = re.match(r"^ch_(\d+)\.md$", path.name)
        if not n_match:
            continue
        text = path.read_text(encoding="utf-8")
        wc, counts = scan_chapter(text, motifs)
        rows.append(ChapterRow(
            chapter=int(n_match.group(1)),
            word_count=wc,
            counts=counts,
        ))
    rows.sort(key=lambda r: r.chapter)

    warnings: list[Warning_] = []
    if rows and motifs and len(rows) >= 4:
        cutoff = len(rows) // 2 + 1  # 1-indexed back half
        for motif in motifs:
            # Find the LAST chapter where this motif was hit before
            # the back half — only flag a back-half drop if the
            # motif was once present (so a motif a writer simply
            # never used doesn't generate noise).
            ever_hit_in_first_half = any(
                r.counts.get(motif.slug, 0) > 0
                for r in rows[:cutoff - 1]
            )
            if not ever_hit_in_first_half:
                continue
            for r in rows[cutoff - 1:]:
                if r.counts.get(motif.slug, 0) == 0:
                    warnings.append(Warning_(
                        chapter=r.chapter,
                        motif=motif.slug,
                        message=(
                            f"motif `{motif.slug}` drops to zero in "
                            f"chapter {r.chapter} (back half) — "
                            f"the image is set up earlier; consider "
                            f"a callback."
                        ),
                    ))
    return MotifReport(motifs=motifs, rows=rows, warnings=warnings)


def render_markdown(report: MotifReport, *, book: str | None = None) -> str:
    """Render the report as a markdown table + warnings list."""
    if not report.motifs:
        if book:
            return (
                f"# Motif tracker — {book}\n\n"
                f"_No motifs configured. Create `books/{book}/motifs.md` "
                f"with one bullet per motif (`- slug: keyword1, "
                f"keyword2`) to enable tracking._\n"
            )
        return (
            "# Motif tracker\n\n"
            "_No motifs configured. Create `motifs.md` with one bullet "
            "per motif (`- slug: keyword1, keyword2`) to enable tracking._\n"
        )

    parts: list[str] = []
    title = f"# Motif tracker — {book}" if book else "# Motif tracker"
    parts.append(title)
    parts.append("")
    headers = ["Chapter", "Words", *[m.slug for m in report.motifs]]
    parts.append("| " + " | ".join(headers) + " |")
    parts.append("|" + "|".join(["---"] * len(headers)) + "|")
    for r in report.rows:
        cells = [str(r.chapter), str(r.word_count)]
        for m in report.motifs:
            n = r.counts.get(m.slug, 0)
            cells.append(str(n) if n else "·")
        parts.append("| " + " | ".join(cells) + " |")
    if report.warnings:
        parts.append("")
        parts.append("## Warnings")
        parts.append("")
        for w in report.warnings:
            parts.append(f"- ch{w.chapter:02d}: {w.message}")
    return "\n".join(parts) + "\n"
