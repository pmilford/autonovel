"""Mechanical pass for the appendix timeline — extracts in-narrative
dates from chapter summaries + frontmatter events.

Surfaced 2026-04-30: the appendix timeline section (shipped in
/autonovel:appendix) is LLM-only, but a richer shape merges three
sources:

  1. Story-time, in-narrative — dates the book actually depicts.
     Pulled from chapter summaries' `## Story time` sections plus
     each chapter's frontmatter `events:` array. MECHANICAL —
     this module's job.
  2. Real, referenced in the book — historical events the prose
     mentions but doesn't depict. Detected via cross-reference
     against research notes' Candidate Canon Entries. LLM step
     (lives in the slash-command body).
  3. Real, context-setting — events the reader should know but
     the prose never mentions. Curated by the LLM from research
     notes + period scope.

This module produces (1). The slash-command merges in (2) and (3)
and renders the alphabetised-by-date timeline with markers
distinguishing each source.

Public API:

    extract_in_narrative_dates(book_root) -> list[TimelineRow]
    render_markdown(rows) -> str
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .chapter_summary import _parse_summary
from .frontmatter import strip_yaml_frontmatter
from ..paths import iter_chapter_files


@dataclass
class TimelineRow:
    """One row in the assembled timeline. The `source` field
    distinguishes mechanical-extracted in-narrative dates from
    LLM-merged real-world rows; the appendix slash-command sets
    `📖`, `🏛️ referenced`, `🏛️ context` markers per source."""
    date: str           # ISO date string (1492-08-03) or year ('1492')
    description: str    # one-sentence event description
    source: str = "narrative"   # narrative | referenced | context
    chapter: int | None = None  # which chapter (for narrative source)
    citation: str = ""          # [shortname] for referenced/context

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "description": self.description,
            "source": self.source,
            "chapter": self.chapter,
            "citation": self.citation,
        }


_FRONTMATTER_EVENTS_RE = re.compile(
    r"^events:\s*\[([^\]]*)\]\s*$", re.MULTILINE,
)
_DATE_LIKE_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{4}-\d{2}|\d{4})\b"
)


def extract_in_narrative_dates(book_root: Path) -> list[TimelineRow]:
    """Walk every chapter and pull dates from two places:

      - Frontmatter `story_time:` field (the chapter's primary
        date stamp; one ISO date or range per chapter).
      - Frontmatter `events:` list (named real-or-fictional
        events the chapter touches; resolved against
        `shared/events.md` by other commands but here we just
        capture the names).
      - Summary's `## Story time` section (often more precise
        than frontmatter when the chapter spans multiple days;
        e.g. frontmatter says `1492-08` and summary says
        `1492-08-03 to 1492-08-05`).

    Returns one TimelineRow per (chapter, date) pair the book
    depicts, in chapter order. The slash-command sorts by date
    after merging in real-world rows.
    """
    chapters_dir = book_root / "chapters"
    rows: list[TimelineRow] = []
    if not chapters_dir.is_dir():
        return rows
    for ch_path in iter_chapter_files(chapters_dir):
        try:
            ch_num = int(ch_path.stem.split("_")[-1])
        except ValueError:
            continue
        text = ch_path.read_text(encoding="utf-8")
        # Pull story_time from frontmatter (cheap parse).
        story_time = _extract_frontmatter_field(text, "story_time")

        # Per-chapter summary supplies the more specific date when
        # the frontmatter range is broader than one event.
        summary_path = chapters_dir / f"{ch_path.stem}.summary.md"
        summary_dates: list[str] = []
        plot_summary = ""
        if summary_path.is_file():
            sm = _parse_summary(summary_path.read_text(encoding="utf-8"))
            plot_summary = sm.get("plot") or ""
            sm_story_time = sm.get("story_time") or ""
            summary_dates = _DATE_LIKE_RE.findall(sm_story_time)

        # Prefer summary dates; fall back to frontmatter story_time.
        candidate_dates = summary_dates
        if not candidate_dates and story_time:
            candidate_dates = _DATE_LIKE_RE.findall(story_time)
        if not candidate_dates:
            continue

        # The first candidate date is the canonical one for this
        # chapter; merging multiple per-chapter dates would inflate
        # the timeline beyond reader-friendliness.
        rows.append(TimelineRow(
            date=candidate_dates[0],
            description=plot_summary or f"Chapter {ch_num} events.",
            source="narrative",
            chapter=ch_num,
        ))
    return rows


def _extract_frontmatter_field(text: str, field_name: str) -> str:
    """Cheap field extraction for top-level frontmatter scalars
    (story_time, pov, etc.). Avoids a hard PyYAML dep — the
    chapter frontmatter is intentionally flat."""
    if not text.startswith("---"):
        return ""
    for raw_line in text.splitlines()[1:]:
        if raw_line.strip() == "---":
            break
        if raw_line.startswith(f"{field_name}:"):
            value = raw_line.split(":", 1)[1].strip()
            if value.startswith(('"', "'")) and value.endswith(('"', "'")):
                value = value[1:-1]
            return value
    return ""


# ----------------------------------------------------- render


_SOURCE_MARKER = {
    "narrative": "📖",
    "referenced": "🏛️ referenced",
    "context": "🏛️ context",
}


def _date_sort_key(row: TimelineRow) -> tuple:
    """Sort by date. ISO dates compare lexicographically; year-
    only dates ('1492') compare correctly against full ISO
    ('1492-08-03') because '1492' < '1492-' in lexicographic
    order — a year-only entry sorts to the start of its year, the
    convention readers expect."""
    return (row.date, row.chapter or 0, row.description)


def render_markdown(rows: list[TimelineRow], *,
                     include_legend: bool = True,
                     book: str = "") -> str:
    """Render the merged timeline as markdown for the appendix.
    Sorts by date; alternates marker emoji per source; starts
    with a legend block when `include_legend` is True.
    """
    if not rows:
        return "_No dates found in chapter summaries or frontmatter._\n"
    rows = sorted(rows, key=_date_sort_key)
    parts: list[str] = []
    if include_legend:
        parts.append(
            "_Timeline legend: 📖 = depicted in-narrative; "
            "🏛️ referenced = real event the prose mentions but "
            "doesn't depict; 🏛️ context = real event the reader "
            "should know to follow the period (not mentioned in "
            "the prose)._\n"
        )
    for row in rows:
        marker = _SOURCE_MARKER.get(row.source, "·")
        chapter_tag = (
            f" *(ch {row.chapter})*" if row.chapter is not None
            else ""
        )
        cite_tag = (
            f" `[{row.citation}]`" if row.citation else ""
        )
        parts.append(
            f"- **{row.date}** {marker} — {row.description}"
            f"{chapter_tag}{cite_tag}"
        )
    parts.append("")
    return "\n".join(parts) + "\n"
