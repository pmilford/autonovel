"""Command-log invariants (REWRITE-PLAN.md §21.2, §21.12)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from autonovel import command_log


def test_append_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "command-log.jsonl"
    command_log.append(path, command="/autonovel:draft", args=["1"], status="ok", wrote=["books/a/chapters/ch_01.md"])
    command_log.append(path, command="/autonovel:evaluate", args=["--chapter", "1"], status="ok")

    entries = command_log.read_all(path)
    assert len(entries) == 2
    assert entries[0].command == "/autonovel:draft"
    assert entries[0].wrote == ["books/a/chapters/ch_01.md"]
    assert entries[1].status == "ok"


def test_timestamps_monotonic_when_simulated(tmp_path: Path) -> None:
    path = tmp_path / "command-log.jsonl"
    base = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)
    for i in range(5):
        command_log.append(
            path, command="/autonovel:x", args=[str(i)], status="ok", now=base + timedelta(seconds=i)
        )
    entries = command_log.read_all(path)
    stamps = [e.timestamp for e in entries]
    assert stamps == sorted(stamps)


def test_required_fields_present(tmp_path: Path) -> None:
    path = tmp_path / "command-log.jsonl"
    command_log.append(path, command="/autonovel:x", args=[], status="error", note="boom")
    entries = command_log.read_all(path)
    e = entries[0]
    for f in command_log.REQUIRED_FIELDS:
        assert getattr(e, f) is not None
    assert e.note == "boom"
