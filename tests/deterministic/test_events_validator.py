"""Tier-1 tests for `autonovel.validators.events`."""

from __future__ import annotations

from pathlib import Path

from autonovel.validators.events import (
    check_cross_consistency,
    parse,
)


GOOD = """\
# Events ledger

## E-001: Fire at the Venetian mint
- date: 1522-03-15
- location: Zecca, Venice
- present: [Tommaso, Lucia, Master Giraldo]
- canonical: Master Giraldo set the fire to destroy ledgers.
- rendered_in:
    inquisitor/ch_12: Tommaso's POV, sees smoke from the Piazza.
    apothecary/ch_08: Lucia's POV, treats Giraldo's burns that night.
- book_constraints: Lucia must not know who lit it at the end of this scene.

## E-002: Benedetta crosses the bridge
- date: 1522-04-01
- location: Rialto
- present: [Benedetta, Tommaso]
- canonical: She passes him a slip naming the warehouse.
- rendered_in:
    inquisitor/ch_14: Tommaso receives the slip without meeting her eye.
"""


def test_parse_good_ledger() -> None:
    events, problems = parse(GOOD)
    assert problems == []
    assert [e.id for e in events] == ["E-001", "E-002"]
    e1 = events[0]
    assert e1.title == "Fire at the Venetian mint"
    assert e1.date == "1522-03-15"
    assert e1.location == "Zecca, Venice"
    assert "Tommaso" in e1.present
    assert "Lucia" in e1.present
    assert e1.canonical.startswith("Master Giraldo set the fire")
    assert e1.book_constraints and "Lucia must not know" in e1.book_constraints
    assert [(r.book, r.chapter) for r in e1.rendered_in] == [
        ("inquisitor", 12),
        ("apothecary", 8),
    ]
    assert [(r.book, r.chapter) for r in e1.renders_for("inquisitor")] == [
        ("inquisitor", 12)
    ]


def test_parse_detects_duplicates() -> None:
    text = GOOD + """
## E-001: Collision
- date: 1522-05-01
- location: Rialto
- present: [Tommaso]
- canonical: Duplicate id.
- rendered_in:
    inquisitor/ch_15: Just a second copy.
"""
    _events, problems = parse(text)
    assert any("duplicate event id" in p for p in problems)


def test_parse_flags_missing_required_fields() -> None:
    text = """
## E-010: Lacking details
- date: 1522-06-01
- location: Venice
"""
    _events, problems = parse(text)
    assert any("missing required field `present`" in p for p in problems)
    assert any("missing required field `canonical`" in p for p in problems)
    assert any("missing required field `rendered_in`" in p for p in problems)


def test_parse_flags_bad_date() -> None:
    text = """
## E-020: Not a real date
- date: 1522-13-40
- location: Venice
- present: [X]
- canonical: Nope.
- rendered_in:
    inquisitor/ch_01: Placeholder.
"""
    _events, problems = parse(text)
    assert any("1522-13-40" in p for p in problems)


def test_rendered_in_row_must_follow_book_slash_ch() -> None:
    text = """
## E-030: Malformed row
- date: 1522-07-01
- location: Venice
- present: [X]
- canonical: ...
- rendered_in:
    inquisitor ch_07 freeform text
"""
    _events, problems = parse(text)
    assert any("malformed rendered_in row" in p for p in problems)


def test_cross_consistency_flags_unknown_books() -> None:
    events, problems = parse(GOOD)
    assert problems == []
    extra = check_cross_consistency(events, project_books=["inquisitor"])
    assert any("unknown book" in p and "apothecary" in p for p in extra)


def test_cross_consistency_quiet_when_all_books_present() -> None:
    events, _ = parse(GOOD)
    extra = check_cross_consistency(events, project_books=["inquisitor", "apothecary"])
    assert extra == []


def test_empty_document_is_valid() -> None:
    events, problems = parse("# Events ledger\n\nNothing here yet.\n")
    assert events == []
    assert problems == []


def test_parse_accepts_pathlib(tmp_path: Path) -> None:
    f = tmp_path / "events.md"
    f.write_text(GOOD, encoding="utf-8")
    events, problems = parse(f)
    assert problems == []
    assert len(events) == 2
