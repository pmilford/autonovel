"""Install / uninstall: render all commands through an adapter and write them."""

from __future__ import annotations

import importlib.resources as resources
import shutil
from dataclasses import dataclass
from pathlib import Path

from .base import CommandDef, RuntimeAdapter, discover_commands
from .claude_code import ClaudeCodeAdapter
from .codex import CodexAdapter
from .gemini import GeminiAdapter


@dataclass
class InstallResult:
    adapter_name: str
    install_root: Path
    written: list[Path]


@dataclass
class UninstallResult:
    adapter_name: str
    install_root: Path
    removed: list[Path]


def _commands_source_dir() -> Path:
    """Directory holding the generic commands/*.md files.

    In the source tree they live at the repo root under `commands/`. A wheel
    install ships a copy inside the package at `autonovel/commands/` (see
    pyproject.toml's `force-include`). Editable installs fall back to the
    source tree.
    """
    packaged = Path(__file__).resolve().parent.parent / "commands"
    if packaged.is_dir() and any(packaged.glob("*.md")):
        return packaged
    here = Path(__file__).resolve().parent
    for candidate in [here, *here.parents]:
        cd = candidate / "commands"
        if cd.is_dir() and any(cd.glob("*.md")):
            return cd
    raise FileNotFoundError("could not locate commands/ source directory")


def install(
    adapter: RuntimeAdapter,
    *,
    install_root: Path | None = None,
    commands_dir: Path | None = None,
    model_map: dict[str, str] | None = None,
) -> InstallResult:
    root = install_root or adapter.default_install_root()
    src = commands_dir or _commands_source_dir()
    cmds = discover_commands(src)

    root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for cmd in cmds:
        target = adapter.target_path(root, cmd)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(adapter.render(cmd, model_map=model_map), encoding="utf-8")
        written.append(target)

    return InstallResult(adapter_name=adapter.name, install_root=root, written=written)


def uninstall(
    adapter: RuntimeAdapter,
    *,
    install_root: Path | None = None,
) -> UninstallResult:
    root = install_root or adapter.default_install_root()
    marker = adapter.install_dir_marker(root)
    removed: list[Path] = []
    if marker.exists():
        for p in sorted(marker.rglob("*"), reverse=True):
            if p.is_file():
                removed.append(p)
        shutil.rmtree(marker)
    return UninstallResult(adapter_name=adapter.name, install_root=root, removed=removed)


def load_adapter(name: str) -> RuntimeAdapter:
    if name == "claude":
        return ClaudeCodeAdapter()
    if name == "codex":
        return CodexAdapter()
    if name == "gemini":
        return GeminiAdapter()
    raise KeyError(f"unknown adapter: {name!r}")
