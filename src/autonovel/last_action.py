"""`.autonovel/last-action.json` read/write (REWRITE-PLAN.md §21.2, §21.5)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class LastAction:
    command: str
    args: list[str]
    finished_at: str
    wrote: list[str] = field(default_factory=list)
    book: str | None = None
    next_standard_step: str | None = None
    next_rationale: str | None = None
    sidequests: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "args": list(self.args),
            "finished_at": self.finished_at,
            "wrote": list(self.wrote),
            "book": self.book,
            "next_standard_step": self.next_standard_step,
            "next_rationale": self.next_rationale,
            "sidequests": list(self.sidequests),
        }


def write(path: Path, *, command: str, args: list[str], wrote: list[str] | None = None,
          book: str | None = None, next_standard_step: str | None = None,
          next_rationale: str | None = None,
          sidequests: list[dict[str, str]] | None = None,
          now: datetime | None = None) -> LastAction:
    la = LastAction(
        command=command,
        args=list(args),
        finished_at=(now or datetime.now(timezone.utc)).isoformat(),
        wrote=list(wrote or []),
        book=book,
        next_standard_step=next_standard_step,
        next_rationale=next_rationale,
        sidequests=list(sidequests or []),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(la.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return la


def read(path: Path) -> LastAction | None:
    if not path.exists():
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    return LastAction(
        command=d["command"],
        args=list(d.get("args") or []),
        finished_at=d["finished_at"],
        wrote=list(d.get("wrote") or []),
        book=d.get("book"),
        next_standard_step=d.get("next_standard_step"),
        next_rationale=d.get("next_rationale"),
        sidequests=list(d.get("sidequests") or []),
    )
