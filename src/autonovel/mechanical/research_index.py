"""Research-notes index — `what's even in shared/research/notes/?`

Surfaced 2026-04-29 by author testing: with notes for Jakob
Fugger, Maximilian I, Charles V, the user wanted a structured
recall + cross-character query without reading every file. Today
the only paths are `Read` one at a time or shell `grep` — the
exact `feedback_no_shell_in_user_workflow.md` failure mode.

This module is the cheap mechanical half: a per-note metadata
table extracted from the structured headings every research note
emits (per `commands/research.md` step 8).

The LLM-side cross-source synthesis surface (`/autonovel:research
--query "<question>"`) is a slash-command extension; it doesn't
live in this module.

Public API:

    build_index(series_root) -> Index
    render_markdown(index, *, grep, cites_match) -> str
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# Section headings mandated by `commands/research.md` step 8. Used
# to locate the Sources block and exclude it from body-citation counts.
_SOURCES_HEADING_RE = re.compile(r"^##\s+Sources\s*$", re.MULTILINE)
_CANDIDATE_HEADING_RE = re.compile(
    r"^##\s+Candidate Canon Entries\s*$", re.MULTILINE,
)
_UNCERTAINTIES_HEADING_RE = re.compile(
    r"^##\s+Uncertainties\s*$", re.MULTILINE,
)
_HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_TITLE_HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_UPDATED_LINE_RE = re.compile(
    r"^Updated\s+(?P<date>\S+)\.?\s*(Period:\s*(?P<period>[^\n]+))?",
    re.MULTILINE,
)
_BRACKET_CITE_RE = re.compile(r"\[(?P<key>[A-Za-z][A-Za-z0-9_\-]*)\]")
_BULLET_RE = re.compile(r"^\s*-\s+", re.MULTILINE)


@dataclass
class NoteEntry:
    slug: str
    title: str = ""
    last_updated: str = ""        # ISO date from `Updated <date>` line
    period: str = ""              # `Period:` line content
    word_count: int = 0
    source_count: int = 0         # `[shortname]` entries under ## Sources
    body_citation_count: int = 0  # `[shortname]` references in body
    candidate_canon_count: int = 0
    uncertainty_count: int = 0
    sources_block: str = ""       # raw text of the Sources section (for --cites)
    body: str = ""                # full text (for --grep)

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "title": self.title,
            "last_updated": self.last_updated,
            "period": self.period,
            "word_count": self.word_count,
            "source_count": self.source_count,
            "body_citation_count": self.body_citation_count,
            "candidate_canon_count": self.candidate_canon_count,
            "uncertainty_count": self.uncertainty_count,
        }


@dataclass
class Index:
    notes: list[NoteEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"notes": [n.to_dict() for n in self.notes]}


def parse_note(path: Path) -> NoteEntry:
    """Extract metadata from one `shared/research/notes/<slug>.md`."""
    slug = path.stem
    raw = path.read_text(encoding="utf-8")
    title = ""
    title_m = _TITLE_HEADING_RE.search(raw)
    if title_m:
        title = title_m.group(1).strip()
    updated = ""
    period = ""
    upd_m = _UPDATED_LINE_RE.search(raw)
    if upd_m:
        updated = upd_m.group("date").rstrip(".")
        if upd_m.group("period"):
            period = upd_m.group("period").strip()
    sources_match = _SOURCES_HEADING_RE.search(raw)
    sources_text = ""
    body_text = raw
    if sources_match:
        sources_text = raw[sources_match.end():]
        body_text = raw[:sources_match.start()]
    sources_count = len(_BRACKET_CITE_RE.findall(sources_text))
    body_citations = len(_BRACKET_CITE_RE.findall(body_text))
    cand_count = _section_bullet_count(raw, _CANDIDATE_HEADING_RE)
    uncert_count = _section_bullet_count(raw, _UNCERTAINTIES_HEADING_RE)
    word_count = len(re.findall(r"\b\w+\b", body_text))
    return NoteEntry(
        slug=slug,
        title=title,
        last_updated=updated,
        period=period,
        word_count=word_count,
        source_count=sources_count,
        body_citation_count=body_citations,
        candidate_canon_count=cand_count,
        uncertainty_count=uncert_count,
        sources_block=sources_text,
        body=raw,
    )


def _section_bullet_count(text: str, heading_re: re.Pattern) -> int:
    """Count bullet lines (`- `) inside a section starting at the
    matched heading and ending at the next heading or end-of-file."""
    m = heading_re.search(text)
    if not m:
        return 0
    rest = text[m.end():]
    next_heading = _HEADING_RE.search(rest)
    section = rest[:next_heading.start()] if next_heading else rest
    return len(_BULLET_RE.findall(section))


def build_index(series_root: Path) -> Index:
    notes_dir = series_root / "shared" / "research" / "notes"
    if not notes_dir.is_dir():
        return Index(notes=[])
    entries = [parse_note(p) for p in sorted(notes_dir.glob("*.md"))]
    return Index(notes=entries)


def filter_index(index: Index, *, grep: str | None = None,
                  cites_match: str | None = None) -> list[NoteEntry]:
    """Apply optional --grep and --cites filters. Both are case-
    insensitive substring matches; --grep searches the whole file
    body; --cites only the `## Sources` block."""
    out = list(index.notes)
    if grep:
        needle = grep.lower()
        out = [n for n in out if needle in n.body.lower()]
    if cites_match:
        needle = cites_match.lower()
        out = [n for n in out if needle in n.sources_block.lower()]
    return out


# ----------------------------------------------------------- render


def render_markdown(index: Index, *, grep: str | None = None,
                     cites_match: str | None = None,
                     series_root: Path | None = None) -> str:
    """Markdown table of every note in the index, optionally filtered
    by --grep / --cites. Sorted by slug."""
    rows = filter_index(index, grep=grep, cites_match=cites_match)
    if not index.notes:
        return (
            "_No research notes found at `shared/research/notes/`. "
            "Run `/autonovel:research \"<topic>\"` or `/autonovel:research "
            "--from-seed` to start populating them._\n"
        )
    parts: list[str] = []
    parts.append("# Research notes index\n")
    if grep or cites_match:
        filters = []
        if grep:
            filters.append(f"grep `{grep}`")
        if cites_match:
            filters.append(f"cites `{cites_match}`")
        parts.append(f"_Filters: {' + '.join(filters)} — "
                     f"{len(rows)} of {len(index.notes)} notes match._\n")
    else:
        parts.append(f"_{len(index.notes)} notes._\n")
    if not rows:
        parts.append("_No notes match the filter._\n")
        return "\n".join(parts).rstrip() + "\n"
    parts.append(
        "| Slug | Title | Updated | Words | Sources | Citations | Candidates | Uncertainties |"
    )
    parts.append("|---|---|---|---:|---:|---:|---:|---:|")
    for n in rows:
        parts.append(
            f"| `{n.slug}` "
            f"| {n.title or '·'} "
            f"| {n.last_updated or '·'} "
            f"| {n.word_count} "
            f"| {n.source_count} "
            f"| {n.body_citation_count} "
            f"| {n.candidate_canon_count} "
            f"| {n.uncertainty_count} |"
        )
    parts.append("")
    parts.append(
        "Read one note: `cat shared/research/notes/<slug>.md` (or open in your editor)."
    )
    parts.append(
        "For cross-source synthesis Q+A, use "
        "`/autonovel:research --query \"<question>\"` (LLM, no web search; reads these notes only)."
    )
    parts.append("")
    return "\n".join(parts) + "\n"
