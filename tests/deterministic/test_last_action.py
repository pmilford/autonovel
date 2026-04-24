"""last-action.json round-trip."""

from __future__ import annotations

from pathlib import Path

from autonovel import last_action


def test_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "last-action.json"
    last_action.write(
        path,
        command="/autonovel:draft",
        args=["5", "--book", "a"],
        wrote=["books/a/chapters/ch_05.md"],
        book="a",
        next_standard_step="/autonovel:evaluate --chapter 5 --book a",
        next_rationale="standard path: evaluate the draft you just wrote",
    )
    la = last_action.read(path)
    assert la is not None
    assert la.command == "/autonovel:draft"
    assert la.book == "a"
    assert la.next_standard_step.startswith("/autonovel:evaluate")
    assert la.next_rationale and "evaluate" in la.next_rationale


def test_read_missing_returns_none(tmp_path: Path) -> None:
    assert last_action.read(tmp_path / "missing.json") is None
