"""Tier-1 safety guard for the movie-teaser feature work.

The prime directive while adding teaser/movie commands is: *do not
break the existing book-writing pipeline.* The structural property that
protects it is that `render()` is a pure function of a single
`CommandDef` — adding a new command file cannot perturb the rendered
output of any other command. These tests pin that property and prove a
newly-added command (e.g. `treatment`) installs exactly like the rest.

If a future change makes command rendering depend on sibling commands
(a cross-referencing adapter, a shared mutable registry, etc.), these
fail — which is the signal to stop before it can corrupt existing
commands.
"""

from __future__ import annotations

from autonovel.adapters.base import (
    CommandDef,
    discover_commands,
    parse_command,
)
from autonovel.adapters.claude_code import ClaudeCodeAdapter
from autonovel.adapters.installer import _commands_source_dir


def _all() -> list[CommandDef]:
    return discover_commands(_commands_source_dir())


def test_every_command_parses() -> None:
    """A malformed new command file would raise here (and break
    `autonovel install` for ALL commands). Pins that the whole set —
    including any new teaser commands — parses cleanly."""
    cmds = _all()
    assert len(cmds) >= 73  # baseline at the pre-movies tag
    for c in cmds:
        assert c.name.startswith("autonovel:")
        assert c.model_tier in {"heavy", "standard", "light"}


def test_render_is_independent_of_sibling_commands() -> None:
    """Rendering a command parsed in isolation is byte-identical to
    rendering it from the full discovered set — proves adding command
    files cannot change another command's installed output."""
    adapter = ClaudeCodeAdapter()
    cmds = _all()
    for stem in ("draft", "evaluate", "typeset"):
        from_set = next(c for c in cmds if c.stem == stem)
        in_isolation = parse_command(from_set.source_path)
        assert adapter.render(from_set) == adapter.render(in_isolation), (
            f"{stem}: render depends on sibling commands"
        )


def test_new_commands_install_like_the_rest() -> None:
    """Every command (incl. any newly-added teaser/movie command)
    renders with the standard begin/end lifecycle preamble + postamble,
    so it is installable and lifecycle-managed exactly like existing
    commands."""
    adapter = ClaudeCodeAdapter()
    for c in _all():
        rendered = adapter.render(c)
        assert "<autonovel-preamble>" in rendered
        assert "<autonovel-postamble>" in rendered
        assert "autonovel _begin" in rendered
        assert "autonovel _end" in rendered
