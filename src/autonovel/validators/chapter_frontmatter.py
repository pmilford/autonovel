"""Chapter frontmatter parser and validator (REWRITE-PLAN.md §7).

Given a chapter file, parse its YAML frontmatter block and return a list of
validation problems. Zero problems == valid.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml


REQUIRED = ("book", "chapter", "pov", "story_time", "events", "status")
ALLOWED_STATUS = {"drafted", "revised", "locked"}

_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<body>.*?\n)---\s*(?:\n|\Z)",
    flags=re.DOTALL,
)

_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


@dataclass
class ChapterFrontmatter:
    book: str
    chapter: int
    pov: str
    story_time: str
    events: list[str]
    status: str
    raw: dict[str, Any]


class ChapterFrontmatterError(ValueError):
    pass


def extract(text: str) -> dict[str, Any] | None:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    data = yaml.safe_load(m.group("body"))
    if not isinstance(data, dict):
        raise ChapterFrontmatterError("frontmatter is not a mapping")
    return data


def parse(path_or_text: Path | str) -> ChapterFrontmatter:
    text = path_or_text.read_text(encoding="utf-8") if isinstance(path_or_text, Path) else path_or_text
    data = extract(text)
    if data is None:
        raise ChapterFrontmatterError("missing YAML frontmatter block")
    problems = validate(data)
    if problems:
        raise ChapterFrontmatterError("; ".join(problems))
    return ChapterFrontmatter(
        book=data["book"],
        chapter=int(data["chapter"]),
        pov=data["pov"],
        story_time=str(data["story_time"]),
        events=list(data.get("events") or []),
        status=data["status"],
        raw=data,
    )


def validate(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for key in REQUIRED:
        if key not in data:
            problems.append(f"missing required field: {key}")

    if "book" in data and not (isinstance(data["book"], str) and data["book"].strip()):
        problems.append("`book` must be a non-empty string")

    if "chapter" in data:
        ch = data["chapter"]
        if not isinstance(ch, int) or isinstance(ch, bool) or ch < 1:
            problems.append("`chapter` must be a positive integer")

    if "pov" in data and not (isinstance(data["pov"], str) and data["pov"].strip()):
        problems.append("`pov` must be a non-empty string")

    if "story_time" in data:
        problems.extend(_validate_story_time(data["story_time"]))

    if "events" in data:
        ev = data["events"]
        if not isinstance(ev, list):
            problems.append("`events` must be a list")
        else:
            for i, e in enumerate(ev):
                if not (isinstance(e, str) and e.strip()):
                    problems.append(f"events[{i}] must be a non-empty string")

    if "status" in data and data["status"] not in ALLOWED_STATUS:
        problems.append(
            f"`status` must be one of {sorted(ALLOWED_STATUS)}; got {data['status']!r}"
        )

    return problems


def _validate_story_time(value: Any) -> list[str]:
    if isinstance(value, date):
        return []
    if not isinstance(value, str):
        return ["`story_time` must be an ISO date or range"]
    parts = value.split("..")
    if len(parts) == 1:
        if not _is_iso_date(parts[0]):
            return [f"`story_time` is not a valid ISO date: {value!r}"]
        return []
    if len(parts) == 2:
        start, end = parts
        if not (_is_iso_date(start) and _is_iso_date(end)):
            return [f"`story_time` range has non-ISO endpoints: {value!r}"]
        if start > end:
            return [f"`story_time` range start after end: {value!r}"]
        return []
    return [f"`story_time` must be `YYYY-MM-DD` or `YYYY-MM-DD..YYYY-MM-DD`: {value!r}"]


def _is_iso_date(s: str) -> bool:
    m = _ISO.match(s)
    if not m:
        return False
    try:
        date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return False
    return True
