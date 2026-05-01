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
    pin_model: bool = True,
    dry_run: bool = False,
) -> InstallResult:
    """Render every command into the runtime's install dir.

    `pin_model=False` omits the `model:` frontmatter field — for
    Claude Code, this is the recovery path when the user's session
    model is `[1m]` and the per-command pin silently downshifts.
    Codex / Gemini adapters accept the kwarg for symmetry but may
    not honour it (their model resolution rules differ); see each
    adapter's `render()` for behaviour.

    `dry_run=True` collects the list of paths that *would* be
    written (and renders each command to surface render errors) but
    touches no disk: no `mkdir`, no file writes. The returned
    `InstallResult.written` then names the would-be paths so the
    caller can preview the install plan.
    """
    root = install_root or adapter.default_install_root()
    src = commands_dir or _commands_source_dir()
    cmds = discover_commands(src)

    if not dry_run:
        root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    render_kwargs: dict = {"model_map": model_map}
    # Pass pin_model only to adapters that accept it. Inspecting via
    # signature avoids breaking the Codex/Gemini adapters until they
    # opt in.
    import inspect
    sig = inspect.signature(adapter.render)
    if "pin_model" in sig.parameters:
        render_kwargs["pin_model"] = pin_model
    for cmd in cmds:
        target = adapter.target_path(root, cmd)
        rendered = adapter.render(cmd, **render_kwargs)
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
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
