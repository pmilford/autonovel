"""Tier-1: every commands/*.md parses and has a legal frontmatter."""

from __future__ import annotations

from pathlib import Path

import pytest

from autonovel.adapters.base import (
    GENERIC_TOOL_NAMES,
    VALID_CONTEXT_MODES,
    VALID_MODEL_TIERS,
    CommandParseError,
    discover_commands,
    parse_command_text,
    validate_frontmatter,
)
from autonovel.adapters.installer import _commands_source_dir


def _repo_commands_dir() -> Path:
    return _commands_source_dir()


def test_repo_commands_parse() -> None:
    cmds = discover_commands(_repo_commands_dir())
    assert len(cmds) >= 3  # draft, next, resume
    names = {c.name for c in cmds}
    assert {"autonovel:draft", "autonovel:next", "autonovel:resume"} <= names


@pytest.mark.parametrize("cmd_path", sorted(_repo_commands_dir().glob("*.md")))
def test_each_command_frontmatter_valid(cmd_path: Path) -> None:
    # parse_command raises on invalid frontmatter.
    from autonovel.adapters.base import parse_command
    cmd = parse_command(cmd_path)
    assert cmd.name.startswith("autonovel:")
    assert cmd.model_tier in VALID_MODEL_TIERS
    assert cmd.context_mode in VALID_CONTEXT_MODES
    for tool in cmd.allowed_tools:
        assert tool in GENERIC_TOOL_NAMES, f"{cmd.name} uses unknown tool {tool!r}"


def test_missing_name_rejected() -> None:
    problems = validate_frontmatter({
        "description": "x",
        "model_tier": "standard",
        "allowed-tools": ["file_read"],
    })
    assert any("name" in p for p in problems)


def test_bad_model_tier_rejected() -> None:
    problems = validate_frontmatter({
        "name": "autonovel:x",
        "description": "x",
        "model_tier": "super",
        "allowed-tools": [],
    })
    assert any("model_tier" in p for p in problems)


def test_bad_tool_rejected() -> None:
    problems = validate_frontmatter({
        "name": "autonovel:x",
        "description": "x",
        "model_tier": "light",
        "allowed-tools": ["file_read", "rocket_launch"],
    })
    assert any("rocket_launch" in p for p in problems)


def test_parse_command_text_missing_frontmatter_raises() -> None:
    with pytest.raises(CommandParseError):
        parse_command_text("no frontmatter here")


def test_parse_command_text_bad_name_raises() -> None:
    text = """---
name: other:draft
description: wrong namespace
model_tier: standard
allowed-tools: [file_read]
---
body
"""
    with pytest.raises(CommandParseError):
        parse_command_text(text)
