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
