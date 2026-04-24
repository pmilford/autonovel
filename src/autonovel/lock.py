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


def acquire(lock_path: Path, *, runtime: str, command: str, args: list[str], pid: int | None = None) -> LockInfo:
    """Try to create a lock file. Raises LockHeld if a live lock exists."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    existing = read(lock_path)
    if existing is not None and _pid_is_live(existing.pid):
        raise LockHeld(existing)
    info = LockInfo(
        pid=pid if pid is not None else os.getpid(),
        runtime=runtime,
        command=command,
        args=list(args),
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    lock_path.write_text(json.dumps(info.to_dict(), indent=2), encoding="utf-8")
    return info


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
