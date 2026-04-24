"""Command file parser + adapter base class.

The repo ships generic command files under `commands/`. Each adapter
translates a generic CommandDef into the runtime-specific on-disk form.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REQUIRED_FRONTMATTER = ("name", "description", "model_tier", "allowed-tools")
VALID_MODEL_TIERS = {"heavy", "standard", "light"}
VALID_CONTEXT_MODES = {"none", "book", "series"}
GENERIC_TOOL_NAMES = {
    "file_read",
    "file_write",
    "task",
    "web_search",
    "web_fetch",
    "bash",
}

_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<fm>.*?\n)---\s*\n(?P<body>.*)\Z",
    re.DOTALL,
)


class CommandParseError(ValueError):
    pass


@dataclass
class CommandDef:
    name: str
    description: str
    argument_hint: str | None
    model_tier: str
    allowed_tools: list[str]
    reads: list[str]
    writes: list[str]
    context_mode: str
    body: str
    source_path: Path | None
    raw_frontmatter: dict[str, Any]

    @property
    def stem(self) -> str:
        return self.name.split(":", 1)[1] if ":" in self.name else self.name


def parse_command(path: Path) -> CommandDef:
    text = path.read_text(encoding="utf-8")
    return parse_command_text(text, source_path=path)


def parse_command_text(text: str, *, source_path: Path | None = None) -> CommandDef:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise CommandParseError(f"{source_path or '<text>'}: missing YAML frontmatter block")
    fm = yaml.safe_load(m.group("fm")) or {}
    if not isinstance(fm, dict):
        raise CommandParseError(f"{source_path or '<text>'}: frontmatter is not a mapping")
    body = m.group("body")

    problems = validate_frontmatter(fm)
    if problems:
        raise CommandParseError(
            f"{source_path or '<text>'}: " + "; ".join(problems)
        )

    return CommandDef(
        name=fm["name"],
        description=fm["description"],
        argument_hint=fm.get("argument-hint"),
        model_tier=fm["model_tier"],
        allowed_tools=list(fm.get("allowed-tools") or []),
        reads=list(fm.get("reads") or []),
        writes=list(fm.get("writes") or []),
        context_mode=fm.get("context_mode", "book"),
        body=body,
        source_path=source_path,
        raw_frontmatter=fm,
    )


def validate_frontmatter(fm: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for k in REQUIRED_FRONTMATTER:
        if k not in fm:
            problems.append(f"missing frontmatter field: {k}")
    name = fm.get("name")
    if name is not None and not (isinstance(name, str) and name.startswith("autonovel:")):
        problems.append("`name` must be a string starting with `autonovel:`")
    tier = fm.get("model_tier")
    if tier is not None and tier not in VALID_MODEL_TIERS:
        problems.append(
            f"`model_tier` must be one of {sorted(VALID_MODEL_TIERS)}; got {tier!r}"
        )
    ctx = fm.get("context_mode")
    if ctx is not None and ctx not in VALID_CONTEXT_MODES:
        problems.append(
            f"`context_mode` must be one of {sorted(VALID_CONTEXT_MODES)}; got {ctx!r}"
        )
    tools = fm.get("allowed-tools") or []
    if not isinstance(tools, list):
        problems.append("`allowed-tools` must be a list")
    else:
        for t in tools:
            if t not in GENERIC_TOOL_NAMES:
                problems.append(
                    f"unknown generic tool: {t!r} (valid: {sorted(GENERIC_TOOL_NAMES)})"
                )
    for key in ("reads", "writes"):
        if key in fm and not isinstance(fm[key], list):
            problems.append(f"`{key}` must be a list")
    return problems


def discover_commands(commands_dir: Path) -> list[CommandDef]:
    """Parse every commands/*.md (non-recursive)."""
    return [parse_command(p) for p in sorted(commands_dir.glob("*.md"))]


class RuntimeAdapter:
    """Base class for runtime-specific adapters."""

    name: str = "base"

    def default_install_root(self) -> Path:
        raise NotImplementedError

    def target_path(self, install_root: Path, cmd: CommandDef) -> Path:
        raise NotImplementedError

    def render(self, cmd: CommandDef, *, model_map: dict[str, str] | None = None) -> str:
        raise NotImplementedError

    def install_dir_marker(self, install_root: Path) -> Path:
        """Directory the adapter owns under install_root (for uninstall)."""
        raise NotImplementedError
