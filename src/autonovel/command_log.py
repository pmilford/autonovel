"""Append-only command log at `.autonovel/command-log.jsonl` (REWRITE-PLAN.md §21.2)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = ("timestamp", "command", "args", "status")


@dataclass
class LogEntry:
    timestamp: str
    command: str
    args: list[str]
    status: str  # ok | error | cancelled
    wrote: list[str] = field(default_factory=list)
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "command": self.command,
            "args": list(self.args),
            "status": self.status,
            "wrote": list(self.wrote),
            "note": self.note,
        }


def append(
    log_path: Path,
    *,
    command: str,
    args: list[str],
    status: str,
    wrote: list[str] | None = None,
    note: str | None = None,
    now: datetime | None = None,
) -> LogEntry:
    t = (now or datetime.now(timezone.utc)).isoformat()
    entry = LogEntry(
        timestamp=t,
        command=command,
        args=list(args),
        status=status,
        wrote=list(wrote or []),
        note=note,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
    return entry


def read_all(log_path: Path) -> list[LogEntry]:
    if not log_path.exists():
        return []
    out: list[LogEntry] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        out.append(
            LogEntry(
                timestamp=d["timestamp"],
                command=d["command"],
                args=list(d.get("args") or []),
                status=d["status"],
                wrote=list(d.get("wrote") or []),
                note=d.get("note"),
            )
        )
    return out
