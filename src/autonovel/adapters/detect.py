"""Detect which AI-CLI runtimes are installed."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .base import RuntimeAdapter
from .claude_code import ClaudeCodeAdapter


@dataclass
class DetectedRuntime:
    name: str
    binary: Path | None
    adapter: RuntimeAdapter

    @property
    def available(self) -> bool:
        return self.binary is not None


def detect_all() -> list[DetectedRuntime]:
    """Return DetectedRuntime for every adapter that has a matching binary."""
    out: list[DetectedRuntime] = []
    for name, adapter, binary in _candidates():
        out.append(
            DetectedRuntime(
                name=name,
                binary=_which(binary),
                adapter=adapter,
            )
        )
    return out


def detect(name: str) -> DetectedRuntime:
    """Detect a specific runtime by short name."""
    for dr in detect_all():
        if dr.name == name:
            return dr
    raise KeyError(f"unknown runtime: {name!r}")


def _candidates() -> list[tuple[str, RuntimeAdapter, str]]:
    # Codex + Gemini adapters land in PR 8; until then only claude is real.
    return [("claude", ClaudeCodeAdapter(), "claude")]


def _which(binary: str) -> Path | None:
    found = shutil.which(binary)
    return Path(found) if found else None
