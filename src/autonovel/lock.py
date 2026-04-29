"""`.autonovel/in-progress.lock` lifecycle (REWRITE-PLAN.md §21.2-§21.3).

Pure-Python; no LLM. Called by command preamble/postamble and by
`autonovel resume`.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class LockInfo:
    pid: int
    runtime: str
    command: str
    args: list[str]
    started_at: str
    status: str = "running"  # running | interrupted

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "runtime": self.runtime,
            "command": self.command,
            "args": list(self.args),
            "started_at": self.started_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LockInfo":
        return cls(
            pid=int(d["pid"]),
            runtime=str(d["runtime"]),
            command=str(d["command"]),
            args=list(d.get("args") or []),
            started_at=str(d["started_at"]),
            status=str(d.get("status", "running")),
        )


class LockHeld(RuntimeError):
    """Raised when a lock is held by a live PID and takeover was refused."""

    def __init__(self, info: LockInfo):
        super().__init__(f"lock held by PID {info.pid} running {info.command}")
        self.info = info


def acquire(lock_path: Path, *, runtime: str, command: str, args: list[str],
             pid: int | None = None,
             expire_after_seconds: float | None = None) -> LockInfo:
    """Try to create a lock file. Raises LockHeld if a live lock exists
    that hasn't yet expired."""
    info, _ = acquire_with_takeover(
        lock_path, runtime=runtime, command=command, args=list(args),
        pid=pid, expire_after_seconds=expire_after_seconds,
    )
    return info


# Default watchdog timeout: a single autonovel command rarely runs longer
# than 30 min in practice (the heaviest is /autonovel:reader-panel which
# reads the whole book; even that finishes inside 20). Setting this to
# 30 min × 60 = 1800s means a lock that's been sitting around longer
# than the longest plausible command is treated as orphaned at the next
# `_begin`. Set to None or 0 to disable expiry. The 2026-04-28 watchdog
# fixed the bug class where an LLM skipped `_end` and the lock stayed
# blocking the next command indefinitely.
DEFAULT_LOCK_EXPIRE_SECONDS = 30 * 60


def acquire_with_takeover(
    lock_path: Path, *, runtime: str, command: str, args: list[str],
    pid: int | None = None,
    expire_after_seconds: float | None = DEFAULT_LOCK_EXPIRE_SECONDS,
) -> tuple[LockInfo, LockInfo | None]:
    """Like `acquire`, but also returns the prior abandoned lock when
    we silently took over a stale one. Callers who want to *warn* the
    user about an incomplete previous run should use this and surface
    the second return value if non-None.

    Cases:
      - No prior lock: new lock created; `prior` is None.
      - Live prior lock, fresh: `LockHeld` raised.
      - Live prior lock, expired (older than `expire_after_seconds`):
        silently taken over; `prior` is the abandoned LockInfo. This is
        the watchdog path — catches LLMs that skip `_end`.
      - Stale prior lock (PID is dead): silently taken over; `prior`
        is the abandoned LockInfo. (Pre-existing behaviour.)

    Set `expire_after_seconds` to `None` or `0` to disable the
    watchdog (back to the pre-2026-04-28 PID-only behaviour).
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    existing = read(lock_path)
    abandoned: LockInfo | None = None
    if existing is not None:
        is_live = _pid_is_live(existing.pid)
        is_expired_by_age = (
            expire_after_seconds is not None
            and expire_after_seconds > 0
            and _lock_age_seconds(lock_path) >= expire_after_seconds
        )
        if is_live and not is_expired_by_age:
            raise LockHeld(existing)
        abandoned = existing
    info = LockInfo(
        pid=pid if pid is not None else os.getpid(),
        runtime=runtime,
        command=command,
        args=list(args),
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    lock_path.write_text(json.dumps(info.to_dict(), indent=2), encoding="utf-8")
    return info, abandoned


def _lock_age_seconds(lock_path: Path) -> float:
    """Age of the lock file in seconds, by mtime. The lock's
    `started_at` field is a stronger source of truth (it survives a
    file `touch`), but we also fall back to mtime for resilience —
    if the JSON is corrupted, mtime still gives us *something*.

    Prefers parsing the `started_at` ISO timestamp from the file's
    JSON; falls back to mtime; returns 0.0 on every error so the
    watchdog never *adds* false-takeovers."""
    try:
        info = read(lock_path)
    except Exception:  # noqa: BLE001
        info = None
    if info is not None:
        try:
            started = datetime.fromisoformat(info.started_at)
            return max(0.0, (datetime.now(timezone.utc) - started).total_seconds())
        except (TypeError, ValueError):
            pass
    try:
        return max(0.0, _now_epoch() - lock_path.stat().st_mtime)
    except OSError:
        return 0.0


def is_expired(lock_path: Path, max_age_seconds: float = DEFAULT_LOCK_EXPIRE_SECONDS) -> bool:
    """True if the lock exists and is older than `max_age_seconds`.

    Independent of PID liveness — that's `is_stale`'s job. A lock can
    be both live (by PID) and expired (by age) when an LLM skipped
    `_end` inside a long-running runtime session; that's exactly the
    case the watchdog is for.
    """
    info = read(lock_path)
    if info is None:
        return False
    return _lock_age_seconds(lock_path) >= max_age_seconds


def read(lock_path: Path) -> LockInfo | None:
    if not lock_path.exists():
        return None
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return LockInfo.from_dict(data)


def release(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def is_stale(lock_path: Path) -> bool:
    """True if a lock file exists but its PID is no longer alive."""
    info = read(lock_path)
    if info is None:
        return False
    return not _pid_is_live(info.pid)


def mark_interrupted(lock_path: Path) -> None:
    info = read(lock_path)
    if info is None:
        return
    info.status = "interrupted"
    lock_path.write_text(json.dumps(info.to_dict(), indent=2), encoding="utf-8")


def _pid_is_live(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _now_epoch() -> float:  # test hook
    return time.time()
