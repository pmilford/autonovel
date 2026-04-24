"""Tier-1 adapter tests: render + install + uninstall for Gemini CLI."""

from __future__ import annotations

from pathlib import Path

from autonovel.adapters.base import parse_command_text
from autonovel.adapters.gemini import (
    DEFAULT_MODEL_MAP,
    GEMINI_TOOL_MAP,
    GeminiAdapter,
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
  - web_search
reads:
  - books/{book}/outline.md
writes:
  - books/{book}/chapters/ch_{chapter}.md
context_mode: book
---

<workflow>
1. Use `file_read` on the outline.
2. Use `web_search` for sources. (a creative task otherwise.)
3. Use `task` to fan out a sibling load.
</workflow>
"""


def test_render_emits_toml_with_description_and_prompt() -> None:
    cmd = parse_command_text(SAMPLE)
    rendered = GeminiAdapter().render(cmd)
    assert rendered.startswith('description = "Sample for adapter tests."'), rendered[:80]
    assert 'arg_hint = "<chapter-number> --book <short-name>"' in rendered
    assert "prompt = '''" in rendered
    assert rendered.rstrip().endswith("'''")


def test_render_translates_only_backticked_tool_names() -> None:
    cmd = parse_command_text(SAMPLE)
    rendered = GeminiAdapter().render(cmd)
    # Backticked references map to Gemini verbs:
    assert "`read_file`" in rendered
    assert "`google_web_search`" in rendered
    assert "`run_agent`" in rendered  # task -> run_agent
    # Prose untouched:
    assert "creative task" in rendered, "prose word `task` was wrongly rewritten"
    assert GEMINI_TOOL_MAP["task"] == "run_agent"


def test_render_metadata_block_records_model_tier() -> None:
    cmd = parse_command_text(SAMPLE)
    rendered = GeminiAdapter().render(cmd)
    assert "model_tier: standard" in rendered
    assert f"suggested_model: {DEFAULT_MODEL_MAP['standard']}" in rendered


def test_render_injects_preamble_and_postamble() -> None:
    cmd = parse_command_text(SAMPLE)
    rendered = GeminiAdapter().render(cmd)
    assert "<autonovel-preamble>" in rendered
    assert "autonovel _begin --command autonovel:sample --runtime gemini" in rendered
    assert "<autonovel-postamble>" in rendered
    assert "autonovel _end --command autonovel:sample" in rendered
    # Gemini argument substitution uses {{args}}, not $ARGUMENTS.
    assert "{{args}}" in rendered


def test_render_respects_custom_model_map() -> None:
    cmd = parse_command_text(SAMPLE)
    rendered = GeminiAdapter().render(
        cmd,
        model_map={"standard": "my-gemini-model", "heavy": "x", "light": "y"},
    )
    assert "suggested_model: my-gemini-model" in rendered


def test_toml_string_escapes_quotes_and_backslashes() -> None:
    from autonovel.adapters.gemini import _toml_string

    assert _toml_string("plain") == '"plain"'
    assert _toml_string('he said "ok"') == '"he said \\"ok\\""'
    assert _toml_string("path\\\\with\\back") == '"path\\\\\\\\with\\\\back"'


def test_target_path_under_autonovel_subdir(tmp_path: Path) -> None:
    cmd = parse_command_text(SAMPLE)
    target = GeminiAdapter().target_path(tmp_path, cmd)
    assert target == tmp_path / "autonovel" / "sample.toml"


def test_default_install_root_is_under_gemini() -> None:
    root = GeminiAdapter().default_install_root()
    assert root.name == "commands"
    assert root.parent.name == ".gemini"


def test_install_round_trip(tmp_path: Path) -> None:
    adapter = GeminiAdapter()
    result = installer.install(adapter, install_root=tmp_path)
    assert len(result.written) >= 3
    for w in result.written:
        assert w.is_file()
        assert w.suffix == ".toml"
        text = w.read_text(encoding="utf-8")
        assert text.startswith("description = ")
        assert "<autonovel-preamble>" in text

    un = installer.uninstall(adapter, install_root=tmp_path)
    assert not (tmp_path / "autonovel").exists()
    assert {p.name for p in un.removed} == {w.name for w in result.written}


def test_install_twice_overwrites(tmp_path: Path) -> None:
    adapter = GeminiAdapter()
    installer.install(adapter, install_root=tmp_path)
    target = tmp_path / "autonovel" / "draft.toml"
    target.write_text("clobbered", encoding="utf-8")
    installer.install(adapter, install_root=tmp_path)
    text = target.read_text(encoding="utf-8")
    assert text.startswith("description = "), text[:60]


def test_install_renders_valid_toml(tmp_path: Path) -> None:
    """Every emitted .toml must round-trip through a TOML parser."""
    try:
        import tomllib  # py311+
    except ImportError:  # pragma: no cover
        import tomli as tomllib  # type: ignore[no-redef]

    adapter = GeminiAdapter()
    result = installer.install(adapter, install_root=tmp_path)
    for path in result.written:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        assert "description" in data, f"{path}: missing description"
        assert "prompt" in data, f"{path}: missing prompt"
        assert isinstance(data["prompt"], str)
        assert "<autonovel-preamble>" in data["prompt"]


def test_load_adapter_returns_gemini() -> None:
    assert installer.load_adapter("gemini").name == "gemini"
