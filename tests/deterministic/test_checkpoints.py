"""Checkpoint round-trip (REWRITE-PLAN.md §21.4)."""

from __future__ import annotations

from pathlib import Path

from autonovel import checkpoints


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_roundtrip_existing_file(tmp_path: Path) -> None:
    series = tmp_path / "s"
    series.mkdir()
    target = series / "a.md"
    _write(target, "original\n")
    cps_dir = series / ".autonovel" / "checkpoints"

    cp = checkpoints.create(cps_dir, series, [target], command="/autonovel:revise", args=["1"])
    _write(target, "CHANGED\n")
    assert target.read_text() == "CHANGED\n"

    checkpoints.rollback(cp, series)
    assert target.read_text() == "original\n"


def test_roundtrip_newly_created_file_is_removed_by_rollback(tmp_path: Path) -> None:
    series = tmp_path / "s"
    series.mkdir()
    target = series / "chapters" / "ch_01.md"
    cps_dir = series / ".autonovel" / "checkpoints"

    cp = checkpoints.create(cps_dir, series, [target], command="/autonovel:draft", args=["1"])
    _write(target, "new chapter")
    assert target.exists()

    checkpoints.rollback(cp, series)
    assert not target.exists()


def test_list_and_prune(tmp_path: Path) -> None:
    series = tmp_path / "s"
    series.mkdir()
    cps_dir = series / ".autonovel" / "checkpoints"
    from datetime import datetime, timedelta, timezone
    base = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)

    for i in range(5):
        checkpoints.create(
            cps_dir,
            series,
            [series / f"file_{i}.md"],
            command="/autonovel:test",
            args=[str(i)],
            now=base + timedelta(seconds=i),
        )

    all_cps = checkpoints.list_checkpoints(cps_dir)
    assert len(all_cps) == 5
    assert [cp.timestamp for cp in all_cps] == sorted(cp.timestamp for cp in all_cps)

    removed = checkpoints.prune(cps_dir, keep=3)
    assert removed == 2
    assert len(checkpoints.list_checkpoints(cps_dir)) == 3


def test_reject_path_outside_series(tmp_path: Path) -> None:
    series = tmp_path / "s"
    series.mkdir()
    cps_dir = series / ".autonovel" / "checkpoints"
    outside = tmp_path / "other.md"
    outside.write_text("x", encoding="utf-8")
    try:
        checkpoints.create(cps_dir, series, [outside], command="/x", args=[])
    except ValueError as e:
        assert "outside series" in str(e)
    else:
        raise AssertionError("expected ValueError")
