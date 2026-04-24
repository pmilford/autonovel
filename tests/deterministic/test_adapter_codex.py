"""Tier-1 adapter tests: render + install + uninstall for Codex."""

from __future__ import annotations

from pathlib import Path

import yaml

from autonovel.adapters.base import parse_command_text
from autonovel.adapters.codex import (
    CODEX_TOOL_MAP,
    DEFAULT_MODEL_MAP,
    CodexAdapter,
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
  - task
  - bash
reads:
  - books/{book}/outline.md
writes:
  - books/{book}/chapters/ch_{chapter}.md
context_mode: book
---

<workflow>
1. Use `file_read` on the outline.
2. Use `task` to fan out a sibling load. (a creative task otherwise.)
3. Run `bash` to call the helper. The shell snippet uses bash semantics.
</workflow>
"""


def _split_frontmatter(text: str) -> tuple[dict, str]:
    assert text.startswith("---\n")
    _, fm_block, body = text.split("---\n", 2)
    return yaml.safe_load(fm_block), body


def test_render_emits_skill_md_frontmatter() -> None:
    cmd = parse_command_text(SAMPLE)
    rendered = CodexAdapter().render(cmd)
    fm, _ = _split_frontmatter(rendered)

    assert fm["name"] == "autonovel-sample"
    assert fm["description"] == "Sample for adapter tests."
    assert fm["metadata"]["model_tier"] == "standard"
    assert fm["metadata"]["suggested_model"] == DEFAULT_MODEL_MAP["standard"]
    assert fm["metadata"]["argument-hint"] == "<chapter-number> --book <short-name>"


def test_render_translates_only_backticked_tool_names() -> None:
    cmd = parse_command_text(SAMPLE)
    rendered = CodexAdapter().render(cmd)
    # Backticked references rewritten:
    assert "`spawn`" in rendered, "backticked `task` should map to `spawn`"
    assert "`shell`" in rendered, "backticked `bash` should map to `shell`"
    # Prose untouched:
    assert "creative task" in rendered, "prose word `task` was wrongly rewritten"
    assert "bash semantics" in rendered, "prose word `bash` was wrongly rewritten"
    # `file_read` is identity in CODEX_TOOL_MAP — backticked form survives.
    assert "`file_read`" in rendered
    assert CODEX_TOOL_MAP["task"] == "spawn"
    assert CODEX_TOOL_MAP["bash"] == "shell"


def test_render_injects_preamble_and_postamble() -> None:
    cmd = parse_command_text(SAMPLE)
    rendered = CodexAdapter().render(cmd)
    assert "<autonovel-preamble>" in rendered
    assert "autonovel _begin --command autonovel:sample --runtime codex" in rendered
    assert "<autonovel-postamble>" in rendered
    assert "autonovel _end --command autonovel:sample" in rendered


def test_render_respects_custom_model_map() -> None:
    cmd = parse_command_text(SAMPLE)
    rendered = CodexAdapter().render(
        cmd,
        model_map={"standard": "my-codex-model", "heavy": "x", "light": "y"},
    )
    fm, _ = _split_frontmatter(rendered)
    assert fm["metadata"]["suggested_model"] == "my-codex-model"


def test_target_path_under_autonovel_subdir(tmp_path: Path) -> None:
    cmd = parse_command_text(SAMPLE)
    target = CodexAdapter().target_path(tmp_path, cmd)
    assert target == tmp_path / "autonovel" / "sample" / "SKILL.md"


def test_default_install_root_is_under_codex() -> None:
    root = CodexAdapter().default_install_root()
    assert root.name == "skills"
    assert root.parent.name == ".codex"


def test_install_round_trip(tmp_path: Path) -> None:
    adapter = CodexAdapter()
    result = installer.install(adapter, install_root=tmp_path)
    assert len(result.written) >= 3
    for w in result.written:
        assert w.is_file()
        assert w.name == "SKILL.md"
        assert "<autonovel-preamble>" in w.read_text(encoding="utf-8")

    un = installer.uninstall(adapter, install_root=tmp_path)
    assert not (tmp_path / "autonovel").exists()
    assert {p.name for p in un.removed} == {w.name for w in result.written}


def test_install_twice_overwrites(tmp_path: Path) -> None:
    adapter = CodexAdapter()
    installer.install(adapter, install_root=tmp_path)
    target = tmp_path / "autonovel" / "draft" / "SKILL.md"
    target.write_text("clobbered", encoding="utf-8")
    installer.install(adapter, install_root=tmp_path)
    assert "<autonovel-preamble>" in target.read_text(encoding="utf-8")


def test_load_adapter_returns_codex() -> None:
    assert installer.load_adapter("codex").name == "codex"
