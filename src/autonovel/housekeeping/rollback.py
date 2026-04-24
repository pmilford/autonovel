"""`autonovel rollback` — list and restore checkpoints (REWRITE-PLAN.md §21.4).

Rollback itself creates a new checkpoint before restoring, so the operation
is itself reversible.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .. import checkpoints
from ..paths import SeriesLayout


@dataclass
class RollbackResult:
    restored_from: str
    new_checkpoint: str
    files_restored: list[str]


def list_recent(series: SeriesLayout, limit: int = 20) -> list[checkpoints.Checkpoint]:
    cps = checkpoints.list_checkpoints(series.checkpoints)
    return list(reversed(cps))[:limit]


def render_list(cps: list[checkpoints.Checkpoint]) -> str:
    if not cps:
        return "(no checkpoints yet)"
    lines = ["Recent checkpoints:"]
    for i, cp in enumerate(cps, start=1):
        lines.append(f"  [{i}] {cp.timestamp}  {cp.command} {' '.join(cp.args)}")
        for f in cp.files:
            lines.append(f"       → {f}")
    return "\n".join(lines)


def rollback_to(series: SeriesLayout, cp: checkpoints.Checkpoint) -> RollbackResult:
    series_root = series.root
    files_now = [series_root / f for f in cp.files]
    pre = checkpoints.create(
        series.checkpoints,
        series_root,
        files_now,
        command="autonovel rollback",
        args=[cp.timestamp],
        reason=f"rollback of {cp.command} {' '.join(cp.args)}",
    )
    checkpoints.rollback(cp, series_root)
    return RollbackResult(
        restored_from=cp.timestamp,
        new_checkpoint=pre.timestamp,
        files_restored=list(cp.files),
    )
