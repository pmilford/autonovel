"""Parse and validate `shared/events.md` (REWRITE-PLAN.md §8).

Each event is a level-2 heading `## E-NNN: <title>`, followed by a dash list
of typed fields:

    ## E-047: Fire at the Venetian mint
    - date: 1522-03-15
    - location: Zecca, Venice
    - present: [Tommaso, Lucia, Master Giraldo, two apprentices]
    - canonical: Master Giraldo set the fire to destroy the ledgers...
    - rendered_in:
        inquisitor/ch_12: Tommaso's POV, sees smoke from the Piazza.
        apothecary/ch_08: Lucia's POV, treats Giraldo's burns that night.
    - book_constraints: Lucia must not know who lit it at the end of this scene.

Drafters reading this for their POV use only the `canonical` field and their
POV row from `rendered_in`. This module's job is to parse the ledger into a
typed structure so the context loader can surface only the rows relevant to a
given (book, chapter).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml


_EVENT_HEADING_RE = re.compile(r"^##\s+(?P<id>E-\d+)\s*:\s*(?P<title>.+?)\s*$")
_FIELD_RE = re.compile(r"^\-\s+(?P<key>[a-z_]+)\s*:\s*(?P<value>.*)$")
_RENDERED_IN_ROW_RE = re.compile(
    r"^\s+(?P<book>[a-z][a-z0-9\-]*)/ch_(?P<chapter>\d+)\s*:\s*(?P<summary>.+?)\s*$"
)
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

REQUIRED_FIELDS = ("date", "location", "present", "canonical", "rendered_in")


@dataclass
class RenderedIn:
    book: str
    chapter: int
    summary: str


@dataclass
class Event:
    id: str
    title: str
    date: str
    location: str
    present: list[str]
    canonical: str
    rendered_in: list[RenderedIn]
    book_constraints: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def renders_for(self, book: str) -> list[RenderedIn]:
        return [r for r in self.rendered_in if r.book == book]


class EventsParseError(ValueError):
    pass


def parse(path_or_text: Path | str) -> tuple[list[Event], list[str]]:
    """Parse an events.md document. Return (events, problems).

    `problems` is a list of human-readable validation messages; empty list
    means the ledger is valid. The parser is forgiving: it returns every
    event it could identify even when some rows are malformed, so the
    caller can render a useful report.
    """
    text = path_or_text.read_text(encoding="utf-8") if isinstance(path_or_text, Path) else path_or_text
    events: list[Event] = []
    problems: list[str] = []
    seen_ids: set[str] = set()

    for block_lines, header_line_no in _iter_event_blocks(text):
        ev, block_problems = _parse_event_block(block_lines, header_line_no)
        problems.extend(block_problems)
        if ev is None:
            continue
        if ev.id in seen_ids:
            problems.append(f"{ev.id}: duplicate event id")
        seen_ids.add(ev.id)
        events.append(ev)
    return events, problems


def _iter_event_blocks(text: str):
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = _EVENT_HEADING_RE.match(lines[i])
        if not m:
            i += 1
            continue
        start = i
        i += 1
        while i < len(lines) and not _EVENT_HEADING_RE.match(lines[i]):
            i += 1
        yield lines[start:i], start + 1


def _parse_event_block(block: list[str], header_line_no: int) -> tuple[Event | None, list[str]]:
    problems: list[str] = []
    header = _EVENT_HEADING_RE.match(block[0])
    if header is None:
        return None, [f"line {header_line_no}: not an event heading"]

    eid = header.group("id")
    title = header.group("title").strip()

    fields: dict[str, Any] = {}
    rendered_in: list[RenderedIn] = []

    i = 1
    while i < len(block):
        line = block[i]
        if not line.strip():
            i += 1
            continue
        fm = _FIELD_RE.match(line)
        if not fm:
            i += 1
            continue
        key = fm.group("key")
        value = fm.group("value").strip()
        if key == "rendered_in":
            i += 1
            while i < len(block):
                row = block[i]
                if not row.strip():
                    i += 1
                    continue
                if _FIELD_RE.match(row):
                    break
                rm = _RENDERED_IN_ROW_RE.match(row)
                if rm is None:
                    problems.append(
                        f"{eid}: malformed rendered_in row: {row.rstrip()!r} "
                        f"(expected `<book>/ch_NN: <POV>, <summary>`)"
                    )
                    i += 1
                    continue
                rendered_in.append(
                    RenderedIn(
                        book=rm.group("book"),
                        chapter=int(rm.group("chapter")),
                        summary=rm.group("summary").strip(),
                    )
                )
                i += 1
            continue
        fields[key] = value
        i += 1

    for k in REQUIRED_FIELDS:
        if k == "rendered_in":
            if not rendered_in:
                problems.append(f"{eid}: missing required field `rendered_in`")
        elif k not in fields:
            problems.append(f"{eid}: missing required field `{k}`")

    date_val = fields.get("date", "")
    if date_val and not _ISO_DATE_RE.match(date_val):
        problems.append(f"{eid}: `date` must be ISO YYYY-MM-DD, got {date_val!r}")
    if date_val and _ISO_DATE_RE.match(date_val):
        try:
            y, m, d = date_val.split("-")
            date(int(y), int(m), int(d))
        except ValueError:
            problems.append(f"{eid}: `date` is not a real calendar date: {date_val!r}")

    present_raw = fields.get("present", "")
    present = _parse_list_field(present_raw)

    if not eid.startswith("E-") or not eid[2:].isdigit():
        problems.append(f"{eid}: id must look like `E-NNN`")

    ev = Event(
        id=eid,
        title=title,
        date=date_val,
        location=fields.get("location", ""),
        present=present,
        canonical=fields.get("canonical", ""),
        rendered_in=rendered_in,
        book_constraints=fields.get("book_constraints") or None,
        raw=fields,
    )
    return ev, problems


def _parse_list_field(value: str) -> list[str]:
    """Parse a list field that looks like `[a, b, c]` or `a, b, c`."""
    s = value.strip()
    if not s:
        return []
    if s.startswith("[") and s.endswith("]"):
        try:
            parsed = yaml.safe_load(s)
        except yaml.YAMLError:
            parsed = None
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    return [p.strip() for p in s.strip("[]").split(",") if p.strip()]


def check_cross_consistency(events: list[Event], project_books: list[str]) -> list[str]:
    """Additional checks that need the project book list.

    - Every `rendered_in` row references a book that exists in project.yaml.
    """
    problems: list[str] = []
    known = set(project_books)
    if not known:
        return problems
    for ev in events:
        for r in ev.rendered_in:
            if r.book not in known:
                problems.append(
                    f"{ev.id}: rendered_in references unknown book {r.book!r} "
                    f"(project.yaml lists: {sorted(known)})"
                )
    return problems
