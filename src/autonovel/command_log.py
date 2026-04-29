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
    # Token + cost tracking (FUTURE-TODOS shipped 2026-04-28).
    # All optional — callers (postamble, hidden helpers) pass them
    # when known. The runtime sets them from the LLM session's
    # usage report; mechanical-only commands leave them as None
    # so the cost helpers can distinguish "free" from "unknown".
    book: str | None = None              # the active book this run targeted
    model: str | None = None             # provider-specific model id
    tier: str | None = None              # heavy | standard | light | mechanical
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None
    cost_usd: float | None = None        # estimated, NOT authoritative

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "timestamp": self.timestamp,
            "command": self.command,
            "args": list(self.args),
            "status": self.status,
            "wrote": list(self.wrote),
            "note": self.note,
        }
        # Token / cost fields — emitted only when populated to keep
        # historical entries readable.
        for key in ("book", "model", "tier", "input_tokens",
                     "output_tokens", "cache_read_tokens",
                     "cache_creation_tokens", "cost_usd"):
            value = getattr(self, key)
            if value is not None:
                d[key] = value
        return d


def append(
    log_path: Path,
    *,
    command: str,
    args: list[str],
    status: str,
    wrote: list[str] | None = None,
    note: str | None = None,
    book: str | None = None,
    model: str | None = None,
    tier: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cache_read_tokens: int | None = None,
    cache_creation_tokens: int | None = None,
    cost_usd: float | None = None,
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
        book=book,
        model=model,
        tier=tier,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_creation_tokens=cache_creation_tokens,
        cost_usd=cost_usd,
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
                book=d.get("book"),
                model=d.get("model"),
                tier=d.get("tier"),
                input_tokens=d.get("input_tokens"),
                output_tokens=d.get("output_tokens"),
                cache_read_tokens=d.get("cache_read_tokens"),
                cache_creation_tokens=d.get("cache_creation_tokens"),
                cost_usd=d.get("cost_usd"),
            )
        )
    return out
