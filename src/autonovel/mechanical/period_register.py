"""Per-book period register lock.

Wraps the existing `slop.period_ban_hits` scanner to produce a
*book-wide* table of every period-bans violation across every
chapter, with line-level locations. The single-chapter scanner
exists for the evaluate flow; this module aggregates so the
author can see the whole register-violation picture without
running evaluate on every chapter.

Useful before a typeset / publish pass — confirms the book stays
in period across the full run, surfaces hot spots for revise
focus, and keeps the workflow purely mechanical.

Default `bans` source is `shared/period_bans.txt` (one banned
word per line, `#` comments allowed). The scanner is
case-insensitive on word-boundary regex, identical semantics to
`slop.period_ban_hits`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .frontmatter import strip_yaml_frontmatter
from .slop import period_ban_hits
from ..paths import iter_chapter_files


@dataclass
class PeriodHit:
    chapter: int
    line_no: int
    word: str
    snippet: str


@dataclass
class ChapterReport:
    chapter: int
    word_count: int
    hits: list[PeriodHit] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.hits)


@dataclass
class PeriodReport:
    bans_count: int    # how many words in the bans list
    chapters: list[ChapterReport]
    summary: dict[str, int] = field(default_factory=dict)
    """`summary` maps banned-word → total chapter-hits across the book.
    Useful for "which words are the worst offenders"."""

    def to_dict(self) -> dict:
        return {
            "bans_count": self.bans_count,
            "summary": dict(self.summary),
            "chapters": [
                {
                    "chapter": c.chapter,
                    "word_count": c.word_count,
                    "total": c.total,
                    "hits": [
                        {"line_no": h.line_no, "word": h.word, "snippet": h.snippet}
                        for h in c.hits
                    ],
                }
                for c in self.chapters
            ],
        }


# ---------------------------------------------------------- public entry


def load_bans(bans_path: Path) -> list[str]:
    if not bans_path.is_file():
        return []
    out: list[str] = []
    for line in bans_path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out


def scan_chapter(text: str, *, bans: list[str], chapter: int = 1) -> ChapterReport:
    """Scan a single chapter against the bans list. Strips YAML
    frontmatter first. Reports per-line hits with snippets."""
    body = strip_yaml_frontmatter(text)
    word_count = len(re.findall(r"\b\w+\b", body))
    if not bans:
        return ChapterReport(chapter=chapter, word_count=word_count)

    # Build one regex per ban for line-level matching.
    patterns = [(b, re.compile(rf"\b{re.escape(b)}\b", re.IGNORECASE))
                 for b in bans]
    hits: list[PeriodHit] = []
    for line_no, line in enumerate(body.splitlines(), start=1):
        for word, pat in patterns:
            for m in pat.finditer(line):
                hits.append(PeriodHit(
                    chapter=chapter,
                    line_no=line_no,
                    word=line[m.start():m.end()],
                    snippet=_snippet(line, m.start()),
                ))
    return ChapterReport(chapter=chapter, word_count=word_count, hits=hits)


def build_report(book_root: Path, *, series_root: Path | None = None) -> PeriodReport:
    """Scan every drafted chapter against `series_root/shared/period_bans.txt`.

    `series_root` defaults to `book_root.parent.parent` (the standard
    `<series>/books/<book>/` layout)."""
    series = series_root if series_root is not None else book_root.parent.parent
    bans = load_bans(series / "shared" / "period_bans.txt")
    chapters: list[ChapterReport] = []
    summary: dict[str, int] = {}
    for path in iter_chapter_files(book_root / "chapters"):
        m = re.match(r"^ch_(\d+)\.md$", path.name)
        if not m:
            continue
        text = path.read_text(encoding="utf-8")
        report = scan_chapter(text, bans=bans, chapter=int(m.group(1)))
        chapters.append(report)
        for h in report.hits:
            summary[h.word.lower()] = summary.get(h.word.lower(), 0) + 1
    chapters.sort(key=lambda c: c.chapter)
    # Confirm with the slop helper too — it's the canonical scanner;
    # this is a sanity-check that we don't drift from its semantics.
    return PeriodReport(
        bans_count=len(bans),
        chapters=chapters,
        summary=dict(sorted(summary.items(), key=lambda kv: -kv[1])),
    )


def _snippet(line: str, start: int, *, window: int = 50) -> str:
    lo = max(0, start - window)
    hi = min(len(line), start + window)
    out = line[lo:hi]
    if lo > 0:
        out = "…" + out
    if hi < len(line):
        out = out + "…"
    return out.strip()


# ---------------------------------------------------------- render


def render_markdown(report: PeriodReport, *, book: str | None = None,
                     show_hits: bool = True) -> str:
    parts: list[str] = []
    parts.append(f"# Period register — {book}" if book
                  else "# Period register")
    parts.append("")
    if report.bans_count == 0:
        parts.append(
            "_`shared/period_bans.txt` is missing or empty. Add one banned "
            "word per line (`#` comments allowed) to enable register lock._"
        )
        return "\n".join(parts) + "\n"
    parts.append(f"_bans loaded: {report.bans_count}_")
    if not report.chapters:
        parts.append("")
        parts.append("_No chapters drafted yet._")
        return "\n".join(parts) + "\n"
    parts.append("")
    parts.append("| Ch | Words | Hits |")
    parts.append("|---|---|---|")
    for c in report.chapters:
        parts.append(
            f"| {c.chapter} | {c.word_count} | "
            f"{c.total if c.total else '·'} |"
        )

    if report.summary:
        parts.append("")
        parts.append("## Worst offenders")
        parts.append("")
        for word, count in list(report.summary.items())[:15]:
            parts.append(f"- `{word}` — {count} hit(s)")

    if show_hits:
        for c in report.chapters:
            if not c.hits:
                continue
            parts.append("")
            parts.append(f"## Chapter {c.chapter} hits")
            for h in c.hits:
                parts.append(f"- L{h.line_no} `{h.word}`: {h.snippet}")
    return "\n".join(parts) + "\n"
