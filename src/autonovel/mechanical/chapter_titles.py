"""Read / inspect / report chapter title status across a book.

Surfaced 2026-04-30: typeset's TOC reads the per-chapter `title:`
frontmatter field, but books drafted before the title-by-default
shipped (autonovel pre-2026-04-30) have no titles, so the TOC
reads `Chapter I`, `Chapter II`, … — the publishing convention is
"Chapter VII — The Apothecary's Mortar", not numbers alone.

This module is the mechanical inspector: walks every chapter,
reads the `title:` frontmatter (or extracts a fallback from a
`# Heading` line if present), and reports which chapters have
titles vs which need backfill. The actual *generation* of titles
for empty chapters is an LLM step delegated to a slash-command
(`/autonovel:extract-chapter-titles`) — autonovel's Python side
never calls the LLM directly per the architecture rule.

Public API:

    inspect_titles(book_root) -> TitleReport
    render_markdown(report) -> str
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .frontmatter import strip_yaml_frontmatter
from .latex import _extract_chapter_title
from ..paths import iter_chapter_files


@dataclass
class ChapterTitleStatus:
    chapter: int
    path: Path
    title: str = ""           # extracted title (frontmatter or `# Heading`)
    source: str = "missing"   # "frontmatter" | "heading" | "missing"

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter,
            "path": str(self.path),
            "title": self.title,
            "source": self.source,
        }


@dataclass
class TitleReport:
    rows: list[ChapterTitleStatus] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.rows)

    @property
    def with_title(self) -> int:
        return sum(1 for r in self.rows if r.title)

    @property
    def missing(self) -> list[int]:
        """Chapters whose `title:` frontmatter field is empty AND
        which have no `# Heading` line either — the ones that need
        backfill."""
        return [r.chapter for r in self.rows if r.source == "missing"]

    @property
    def heading_only(self) -> list[int]:
        """Chapters with a `# Heading` but no frontmatter
        `title:`. These already work in typeset (the heading falls
        through `_extract_chapter_title`'s priority-2 path), but
        moving the title into frontmatter is cleaner and lets
        `/autonovel:summaries` etc. surface it."""
        return [r.chapter for r in self.rows if r.source == "heading"]

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "with_title": self.with_title,
            "missing": self.missing,
            "heading_only": self.heading_only,
            "rows": [r.to_dict() for r in self.rows],
        }


def _detect_source(text: str) -> tuple[str, str]:
    """Return `(title, source)` where source is `"frontmatter"`,
    `"heading"`, or `"missing"`. Uses the same priority order as
    `latex._extract_chapter_title` so the report matches what
    typeset will render."""
    extracted = _extract_chapter_title(text)
    if not extracted:
        return ("", "missing")
    # `_extract_chapter_title` reads frontmatter first, then heading.
    # We mirror that priority to label the source.
    if text.startswith("---"):
        for raw_line in text.splitlines()[1:]:
            if raw_line.strip() == "---":
                break
            if raw_line.startswith("title:"):
                value = raw_line.split(":", 1)[1].strip()
                if value.startswith(('"', "'")) and value.endswith(('"', "'")):
                    value = value[1:-1]
                if value:
                    return (extracted, "frontmatter")
    return (extracted, "heading")


def inspect_titles(book_root: Path) -> TitleReport:
    chapters_dir = book_root / "chapters"
    rows: list[ChapterTitleStatus] = []
    if not chapters_dir.is_dir():
        return TitleReport()
    for ch_path in iter_chapter_files(chapters_dir):
        try:
            ch_num = int(ch_path.stem.split("_")[-1])
        except ValueError:
            continue
        text = ch_path.read_text(encoding="utf-8")
        title, source = _detect_source(text)
        rows.append(ChapterTitleStatus(
            chapter=ch_num, path=ch_path,
            title=title, source=source,
        ))
    return TitleReport(rows=rows)


def render_markdown(report: TitleReport) -> str:
    if not report.rows:
        return "_No chapter files found._\n"
    parts: list[str] = []
    parts.append("# Chapter title status")
    parts.append("")
    parts.append(
        f"_{report.with_title} of {report.total} chapters have a title; "
        f"{len(report.missing)} need backfill._\n"
    )
    parts.append("| ch | source | title |")
    parts.append("|---:|---|---|")
    for r in report.rows:
        marker = {"frontmatter": "✅ frontmatter",
                  "heading": "📝 # Heading",
                  "missing": "❌ missing"}[r.source]
        title_cell = r.title or "—"
        if len(title_cell) > 60:
            title_cell = title_cell[:57] + "…"
        parts.append(f"| {r.chapter} | {marker} | {title_cell} |")
    parts.append("")
    if report.missing:
        chapters_str = ",".join(str(c) for c in report.missing)
        parts.append("## Backfill missing titles")
        parts.append("")
        parts.append(
            f"Run `/autonovel:extract-chapter-titles --book <name> "
            f"--chapters {chapters_str}` to LLM-generate titles for "
            f"the missing chapters from each chapter's plot summary "
            f"and opening prose. The slash-command writes a 2-6 word "
            f"evocative phrase into each chapter's frontmatter "
            f"`title:` field — same shape as new drafts produce."
        )
    if report.heading_only:
        chapters_str = ",".join(str(c) for c in report.heading_only)
        parts.append("")
        parts.append(
            f"_{len(report.heading_only)} chapter(s) "
            f"({chapters_str}) have a `# Heading` line but no "
            f"frontmatter `title:`. These already render in typeset "
            f"via the heading-fallback path, but moving the title "
            f"into frontmatter is cleaner and makes it queryable._"
        )
    return "\n".join(parts) + "\n"
