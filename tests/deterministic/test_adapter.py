"""Tier-1 adapter tests: render + install + uninstall for Claude Code."""

from __future__ import annotations

from pathlib import Path

from autonovel.adapters.base import parse_command_text
from autonovel.adapters.claude_code import (
    CLAUDE_TOOL_MAP,
    DEFAULT_MODEL_MAP,
    ClaudeCodeAdapter,
)
from autonovel.adapters import installer


SAMPLE = """---
name: autonovel:sample
description: Sample for adapter tests.
argument-hint: "<chapter-number> --book <short-name>"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
reads:
  - books/{book}/outline.md
writes:
  - books/{book}/chapters/ch_{chapter}.md
context_mode: book
---

<workflow>
One step only.
</workflow>
"""


def test_render_has_expected_frontmatter() -> None:
    cmd = parse_command_text(SAMPLE)
    rendered = ClaudeCodeAdapter().render(cmd)
    head, _, _ = rendered.partition("\n---\n")
    assert "description: Sample for adapter tests." in head
    assert "argument-hint: <chapter-number> --book <short-name>" in head
    assert f"model: {DEFAULT_MODEL_MAP['standard']}" in head
    # Generic tool names translated:
    assert CLAUDE_TOOL_MAP["file_read"] in head
    assert CLAUDE_TOOL_MAP["file_write"] in head
    # Implicit Bash is added for the preamble/postamble:
    assert "Bash" in head


def test_render_pin_model_false_omits_model_field() -> None:
    """`--no-model-pin` recovery path for [1m] session-model
    users — the rendered command should contain no `model:` line so
    the runtime's session model wins."""
    cmd = parse_command_text(SAMPLE)
    rendered = ClaudeCodeAdapter().render(cmd, pin_model=False)
    head, _, _ = rendered.partition("\n---\n")
    assert "model:" not in head


def test_install_no_model_pin_propagates_to_render(tmp_path) -> None:
    """`autonovel install --no-model-pin` reaches the adapter's
    render path and the resulting files contain no `model:` line."""
    from autonovel.adapters import installer
    from autonovel.adapters.claude_code import ClaudeCodeAdapter

    install_root = tmp_path / "claude-commands"
    installer.install(
        ClaudeCodeAdapter(),
        install_root=install_root,
        pin_model=False,
    )
    # Inspect any installed file.
    files = list(install_root.rglob("*.md"))
    assert files
    for f in files:
        head, _, _ = f.read_text(encoding="utf-8").partition("\n---\n")
        assert "model:" not in head, f"{f} still pins model"


def test_install_default_keeps_model_pin(tmp_path) -> None:
    from autonovel.adapters import installer
    from autonovel.adapters.claude_code import ClaudeCodeAdapter

    install_root = tmp_path / "claude-commands"
    installer.install(ClaudeCodeAdapter(), install_root=install_root)
    files = list(install_root.rglob("*.md"))
    assert files
    # At least one file should still contain `model:` since the
    # default behaviour pins it.
    assert any("model:" in f.read_text(encoding="utf-8") for f in files)


def test_render_injects_preamble_and_postamble() -> None:
    cmd = parse_command_text(SAMPLE)
    rendered = ClaudeCodeAdapter().render(cmd)
    assert "<autonovel-preamble>" in rendered
    assert "autonovel _begin" in rendered
    assert "<autonovel-postamble>" in rendered
    assert "autonovel _end" in rendered
    # The body itself survives unchanged:
    assert "<workflow>\nOne step only." in rendered


def test_render_respects_custom_model_map() -> None:
    cmd = parse_command_text(SAMPLE)
    rendered = ClaudeCodeAdapter().render(
        cmd,
        model_map={"standard": "my-custom-model", "heavy": "x", "light": "y"},
    )
    assert "model: my-custom-model" in rendered


def test_target_path_under_autonovel_subdir(tmp_path: Path) -> None:
    cmd = parse_command_text(SAMPLE)
    adapter = ClaudeCodeAdapter()
    target = adapter.target_path(tmp_path, cmd)
    assert target == tmp_path / "autonovel" / "sample.md"


def test_default_install_root_is_under_home() -> None:
    root = ClaudeCodeAdapter().default_install_root()
    assert root.name == "commands"
    assert root.parent.name == ".claude"


def test_install_round_trip(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter()
    result = installer.install(adapter, install_root=tmp_path)
    assert len(result.written) >= 3
    for w in result.written:
        assert w.is_file()
        # Golden: every installed command has the adapter's preamble.
        assert "<autonovel-preamble>" in w.read_text(encoding="utf-8")

    un = installer.uninstall(adapter, install_root=tmp_path)
    assert not (tmp_path / "autonovel").exists()
    assert {p.name for p in un.removed} == {w.name for w in result.written}


def test_install_twice_overwrites(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter()
    installer.install(adapter, install_root=tmp_path)
    # Clobber one file, re-install, check it's restored.
    target = tmp_path / "autonovel" / "draft.md"
    target.write_text("clobbered", encoding="utf-8")
    installer.install(adapter, install_root=tmp_path)
    assert "<autonovel-preamble>" in target.read_text(encoding="utf-8")


def test_load_adapter_rejects_unknown() -> None:
    import pytest
    with pytest.raises(KeyError):
        installer.load_adapter("emacs-org-mode")
