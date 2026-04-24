"""Chapter frontmatter parser/validator (REWRITE-PLAN.md §7)."""

from __future__ import annotations

import pytest

from autonovel.validators.chapter_frontmatter import (
    ChapterFrontmatterError,
    extract,
    parse,
    validate,
)


VALID = """---
book: inquisitor
chapter: 5
pov: Tommaso
story_time: 1522-03-15
events: [E-047, E-048]
status: drafted
word_count: 3214
---

Body text.
"""


def test_extract_returns_dict() -> None:
    data = extract(VALID)
    assert data is not None
    assert data["chapter"] == 5
    assert data["events"] == ["E-047", "E-048"]


def test_valid_frontmatter_parses() -> None:
    fm = parse(VALID)
    assert fm.book == "inquisitor"
    assert fm.chapter == 5
    assert fm.status == "drafted"


def test_missing_required_field_flagged() -> None:
    data = {"book": "x", "chapter": 1, "pov": "A", "story_time": "2020-01-01", "events": [], "status": "drafted"}
    del data["pov"]
    problems = validate(data)
    assert any("pov" in p for p in problems)


def test_bad_iso_date_flagged() -> None:
    data = {"book": "x", "chapter": 1, "pov": "A", "story_time": "March 15, 1522", "events": [], "status": "drafted"}
    problems = validate(data)
    assert any("ISO" in p or "story_time" in p for p in problems)


def test_iso_range_accepted() -> None:
    data = {"book": "x", "chapter": 1, "pov": "A", "story_time": "1522-03-15..1522-03-18", "events": [], "status": "drafted"}
    assert validate(data) == []


def test_iso_range_reversed_flagged() -> None:
    data = {"book": "x", "chapter": 1, "pov": "A", "story_time": "1522-03-18..1522-03-15", "events": [], "status": "drafted"}
    problems = validate(data)
    assert any("range" in p for p in problems)


def test_bad_status_flagged() -> None:
    data = {"book": "x", "chapter": 1, "pov": "A", "story_time": "2020-01-01", "events": [], "status": "wip"}
    problems = validate(data)
    assert any("status" in p for p in problems)


def test_chapter_must_be_positive_int() -> None:
    data = {"book": "x", "chapter": 0, "pov": "A", "story_time": "2020-01-01", "events": [], "status": "drafted"}
    problems = validate(data)
    assert any("chapter" in p for p in problems)


def test_missing_frontmatter_raises() -> None:
    with pytest.raises(ChapterFrontmatterError):
        parse("just body, no frontmatter")


def test_events_as_non_list_flagged() -> None:
    data = {"book": "x", "chapter": 1, "pov": "A", "story_time": "2020-01-01", "events": "E-001", "status": "drafted"}
    problems = validate(data)
    assert any("events" in p for p in problems)
