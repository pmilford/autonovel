"""File-level checkpoints under `.autonovel/checkpoints/` (REWRITE-PLAN.md §21.2, §21.4).

Each checkpoint is a directory named by an ISO-8601 timestamp containing a
`_manifest.json` and the pre-state `.bak` copy of every file the command was
about to write. `rollback()` restores from a manifest.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


MANIFEST_NAME = "_manifest.json"


@dataclass
class Checkpoint:
    directory: Path
    timestamp: str
    command: str
    args: list[str]
    files: list[str]  # paths relative to series root
    reason: str | None = None

    def manifest_path(self) -> Path:
        return self.directory / MANIFEST_NAME

    def to_manifest(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "command": self.command,
            "args": list(self.args),
            "files": list(self.files),
            "reason": self.reason,
        }

    @classmethod
    def from_manifest(cls, directory: Path) -> "Checkpoint":
        data = json.loads((directory / MANIFEST_NAME).read_text(encoding="utf-8"))
        return cls(
            directory=directory,
            timestamp=str(data["timestamp"]),
            command=str(data["command"]),
            args=list(data.get("args") or []),
            files=list(data.get("files") or []),
            reason=data.get("reason"),
        )


def _timestamp(now: datetime | None = None) -> str:
    t = now or datetime.now(timezone.utc)
    return t.strftime("%Y-%m-%dT%H-%M-%S")


def create(
    checkpoints_dir: Path,
    series_root: Path,
    files_to_back_up: list[Path],
    *,
    command: str,
    args: list[str],
    reason: str | None = None,
    now: datetime | None = None,
) -> Checkpoint:
    """Snapshot the current state of *files_to_back_up* before a destructive change.

    Files that don't yet exist are still recorded — rollback will delete them.
    """
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp(now)
    cp_dir = checkpoints_dir / stamp
    suffix = 1
    while cp_dir.exists():
        suffix += 1
        cp_dir = checkpoints_dir / f"{stamp}-{suffix}"
    cp_dir.mkdir()

    rel_paths: list[str] = []
    for src in files_to_back_up:
        src_abs = src if src.is_absolute() else (series_root / src)
        try:
            rel = src_abs.resolve().relative_to(series_root.resolve())
        except ValueError as e:
            raise ValueError(f"checkpoint target {src_abs} is outside series {series_root}") from e
        rel_paths.append(str(rel))
        if src_abs.exists():
            dst = cp_dir / (str(rel) + ".bak")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_abs, dst)
        else:
            marker = cp_dir / (str(rel) + ".absent")
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("", encoding="utf-8")

    cp = Checkpoint(
        directory=cp_dir,
        timestamp=stamp,
        command=command,
        args=list(args),
        files=rel_paths,
        reason=reason,
    )
    cp.manifest_path().write_text(
        json.dumps(cp.to_manifest(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return cp


def list_checkpoints(checkpoints_dir: Path) -> list[Checkpoint]:
    if not checkpoints_dir.exists():
        return []
    out: list[Checkpoint] = []
    for child in sorted(checkpoints_dir.iterdir()):
        if not child.is_dir():
            continue
        if not (child / MANIFEST_NAME).exists():
            continue
        out.append(Checkpoint.from_manifest(child))
    return out


def rollback(cp: Checkpoint, series_root: Path) -> None:
    """Restore files to their pre-checkpoint state."""
    for rel in cp.files:
        dst = series_root / rel
        bak = cp.directory / (rel + ".bak")
        absent = cp.directory / (rel + ".absent")
        if bak.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bak, dst)
        elif absent.exists():
            if dst.exists():
                dst.unlink()


@dataclass
class WriteVerificationItem:
    """One claim from `_end --wrote <path>` audited against its
    checkpoint snapshot."""
    path: str          # path relative to series root
    status: str        # "created" | "modified" | "deleted" | "unchanged" | "missing" | "outside-checkpoint"


@dataclass
class WriteVerificationReport:
    items: list[WriteVerificationItem]

    @property
    def warnings(self) -> list[WriteVerificationItem]:
        """Items the postamble should warn about — file was claimed
        as written but the checkpoint says it was either unchanged
        (the LLM lied about modifying it) or missing (the LLM
        claimed creation but no file appeared)."""
        return [i for i in self.items
                if i.status in ("unchanged", "missing")]

    def to_dict(self) -> dict:
        return {
            "items": [
                {"path": i.path, "status": i.status} for i in self.items
            ],
            "warnings": [
                {"path": i.path, "status": i.status} for i in self.warnings
            ],
        }


def verify_writes(cp: Checkpoint, series_root: Path,
                   claimed: list[str]) -> WriteVerificationReport:
    """Compare each *claimed* path against its checkpoint snapshot.

    Background: the postamble passes `--wrote <path>` flags that are
    self-reported by the LLM. The LLM can claim a write without
    actually invoking the `Write` / `Edit` tool. This helper compares
    each path against the checkpoint backup and surfaces the
    mismatches.

    Behaviour:
      - File was absent at begin (`*.absent` marker), exists now →
        `created`.
      - File was absent at begin, still absent now → `missing`.
        (The LLM claimed creation but didn't actually write.)
      - File existed at begin (`*.bak`), bytes equal now → `unchanged`.
        (The LLM claimed modification but didn't actually change
        anything.)
      - File existed at begin, bytes differ now → `modified`.
      - File existed at begin, gone now → `deleted`.
      - Claimed path doesn't appear in the checkpoint at all (e.g.
        the postamble passed `--wrote` for a file outside `writes:`)
        → `outside-checkpoint`. We can't verify; not a warning.

    Pure I/O comparison; no LLM. Safe to call on every command's
    `_end`.
    """
    items: list[WriteVerificationItem] = []
    cp_files = set(cp.files)
    for raw in claimed:
        path = raw.strip()
        if not path:
            continue
        # Skip paths that still contain placeholders — they were
        # never resolved against the runtime context, so we can't
        # check them. Surface as outside-checkpoint so the postamble
        # has visibility but doesn't warn.
        if "{" in path or "}" in path:
            items.append(WriteVerificationItem(
                path=path, status="outside-checkpoint",
            ))
            continue
        # Normalise to series-root-relative.
        try:
            abs_path = (series_root / path).resolve()
            rel = str(abs_path.relative_to(series_root.resolve()))
        except ValueError:
            items.append(WriteVerificationItem(
                path=path, status="outside-checkpoint",
            ))
            continue
        if rel not in cp_files:
            items.append(WriteVerificationItem(
                path=rel, status="outside-checkpoint",
            ))
            continue
        bak = cp.directory / (rel + ".bak")
        absent = cp.directory / (rel + ".absent")
        live_path = series_root / rel
        if absent.exists():
            # File was absent at begin.
            status = "created" if live_path.exists() else "missing"
        elif bak.exists():
            # File existed at begin.
            if not live_path.exists():
                status = "deleted"
            else:
                try:
                    if live_path.read_bytes() == bak.read_bytes():
                        status = "unchanged"
                    else:
                        status = "modified"
                except OSError:
                    status = "outside-checkpoint"
        else:
            status = "outside-checkpoint"
        items.append(WriteVerificationItem(path=rel, status=status))
    return WriteVerificationReport(items=items)


def prune(checkpoints_dir: Path, keep: int = 20) -> int:
    """Delete oldest checkpoints, keeping *keep* most recent. Returns count removed."""
    cps = list_checkpoints(checkpoints_dir)
    if len(cps) <= keep:
        return 0
    to_remove = cps[: len(cps) - keep]
    for cp in to_remove:
        shutil.rmtree(cp.directory)
    return len(to_remove)
