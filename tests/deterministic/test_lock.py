"""Lock lifecycle (REWRITE-PLAN.md §21.2-§21.3)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from autonovel import lock


def test_acquire_creates_lock_file(tmp_path: Path) -> None:
    lf = tmp_path / "in-progress.lock"
    info = lock.acquire(lf, runtime="claude", command="/autonovel:draft", args=["5"])
    assert lf.exists()
    assert info.pid == os.getpid()
    assert info.command == "/autonovel:draft"


def test_acquire_fails_if_live_lock_held(tmp_path: Path) -> None:
    lf = tmp_path / "in-progress.lock"
    lock.acquire(lf, runtime="claude", command="/autonovel:draft", args=[])
    with pytest.raises(lock.LockHeld):
        lock.acquire(lf, runtime="claude", command="/autonovel:draft", args=[])


def test_stale_lock_is_detected(tmp_path: Path) -> None:
    lf = tmp_path / "in-progress.lock"
    # PID 1 is almost always init (live), so pick an unassigned high PID.
    fake_pid = 10**9
    lock.acquire(lf, runtime="claude", command="/autonovel:draft", args=[], pid=fake_pid)
    assert lock.is_stale(lf) is True
    # Stale lock is not "held" from acquire's point of view:
    info = lock.acquire(lf, runtime="claude", command="/autonovel:draft", args=[])
    assert info.pid == os.getpid()


def test_release_removes_lock(tmp_path: Path) -> None:
    lf = tmp_path / "in-progress.lock"
    lock.acquire(lf, runtime="claude", command="/autonovel:draft", args=[])
    lock.release(lf)
    assert not lf.exists()
    # Idempotent.
    lock.release(lf)


def test_mark_interrupted(tmp_path: Path) -> None:
    lf = tmp_path / "in-progress.lock"
    lock.acquire(lf, runtime="claude", command="/autonovel:draft", args=[])
    lock.mark_interrupted(lf)
    info = lock.read(lf)
    assert info is not None and info.status == "interrupted"


# -------------------------------------------------- watchdog (lock-age expiry)


def _force_lock_started_at(lock_path: Path, *, seconds_ago: float) -> None:
    """Helper: backdate the lock's `started_at` field so it appears
    older than `seconds_ago`. Also pushes back mtime so the mtime
    fallback agrees."""
    import json
    import os
    import time
    from datetime import datetime, timedelta, timezone
    info = lock.read(lock_path)
    assert info is not None
    backdated = (datetime.now(timezone.utc)
                 - timedelta(seconds=seconds_ago)).isoformat()
    payload = info.to_dict()
    payload["started_at"] = backdated
    lock_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    age = time.time() - seconds_ago
    os.utime(lock_path, (age, age))


def test_watchdog_takes_over_expired_lock_same_pid(tmp_path: Path) -> None:
    """The bug class: same Claude Code session, same PID, but a
    prior command skipped `_end`. Old PID-only logic raised LockHeld
    forever; the watchdog (default 30 min) takes over with the
    abandoned lock surfaced."""
    lf = tmp_path / "in-progress.lock"
    lock.acquire(lf, runtime="claude", command="/autonovel:draft", args=[])
    _force_lock_started_at(lf, seconds_ago=2 * 60 * 60)  # 2 hours
    info, abandoned = lock.acquire_with_takeover(
        lf, runtime="claude", command="/autonovel:draft", args=[],
    )
    assert info.pid == os.getpid()
    assert abandoned is not None
    assert abandoned.pid == os.getpid()  # same PID — that's the point


def test_watchdog_does_not_take_over_fresh_lock(tmp_path: Path) -> None:
    lf = tmp_path / "in-progress.lock"
    lock.acquire(lf, runtime="claude", command="/autonovel:draft", args=[])
    # Default expiry is 30 minutes; 5-second-old lock must hold.
    with pytest.raises(lock.LockHeld):
        lock.acquire_with_takeover(
            lf, runtime="claude", command="/autonovel:draft", args=[],
        )


def test_watchdog_disabled_with_zero_or_none(tmp_path: Path) -> None:
    """`expire_after_seconds=None` reverts to the pre-2026-04-28
    PID-only logic for callers that explicitly opt out (e.g. tests
    of the held-lock path)."""
    lf = tmp_path / "in-progress.lock"
    lock.acquire(lf, runtime="claude", command="/autonovel:draft", args=[])
    _force_lock_started_at(lf, seconds_ago=10 * 60 * 60)  # 10 hours
    with pytest.raises(lock.LockHeld):
        lock.acquire_with_takeover(
            lf, runtime="claude", command="/autonovel:draft", args=[],
            expire_after_seconds=None,
        )
    with pytest.raises(lock.LockHeld):
        lock.acquire_with_takeover(
            lf, runtime="claude", command="/autonovel:draft", args=[],
            expire_after_seconds=0,
        )


def test_watchdog_custom_threshold(tmp_path: Path) -> None:
    """A caller can pick a tighter threshold for fast-moving sweeps."""
    lf = tmp_path / "in-progress.lock"
    lock.acquire(lf, runtime="claude", command="/autonovel:draft", args=[])
    _force_lock_started_at(lf, seconds_ago=120)  # 2 minutes
    # 1-minute threshold: take over.
    info, abandoned = lock.acquire_with_takeover(
        lf, runtime="claude", command="/autonovel:draft", args=[],
        expire_after_seconds=60,
    )
    assert abandoned is not None


def test_is_expired_predicate(tmp_path: Path) -> None:
    lf = tmp_path / "in-progress.lock"
    assert lock.is_expired(lf) is False  # no lock → not expired
    lock.acquire(lf, runtime="claude", command="/autonovel:draft", args=[])
    assert lock.is_expired(lf, max_age_seconds=60) is False  # fresh
    _force_lock_started_at(lf, seconds_ago=120)
    assert lock.is_expired(lf, max_age_seconds=60) is True


def test_is_expired_falls_back_to_mtime_on_corrupted_started_at(
    tmp_path: Path,
) -> None:
    """If the JSON `started_at` field is corrupted, mtime is the
    fallback so the watchdog doesn't fail-open."""
    import json
    import os
    import time
    lf = tmp_path / "in-progress.lock"
    lock.acquire(lf, runtime="claude", command="/autonovel:draft", args=[])
    payload = json.loads(lf.read_text())
    payload["started_at"] = "not-an-iso-timestamp"
    lf.write_text(json.dumps(payload), encoding="utf-8")
    # Force mtime back 2 minutes.
    age = time.time() - 120
    os.utime(lf, (age, age))
    assert lock.is_expired(lf, max_age_seconds=60) is True


def test_watchdog_in_lifecycle_begin_surfaces_abandoned(tmp_path: Path) -> None:
    """End-to-end: `lifecycle.begin` returns the abandoned lock when
    the watchdog fires, so the postamble can warn the user."""
    from autonovel.housekeeping import lifecycle, scaffold
    res = scaffold.new_series(tmp_path / "demo", series_name="demo")
    series = res.series

    # Plant an expired prior lock for some other command.
    lock.acquire(series.lock_file, runtime="claude",
                 command="autonovel:draft", args=["1"])
    _force_lock_started_at(series.lock_file, seconds_ago=2 * 60 * 60)

    # Begin a new command — the watchdog should take over.
    result = lifecycle.begin("autonovel:next", "", series=series)
    assert result.abandoned_lock is not None
    assert result.abandoned_lock.command == "autonovel:draft"
