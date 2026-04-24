"""Claude Code adapter — translates generic commands to `.claude/commands/...`."""

from __future__ import annotations

from pathlib import Path

from .base import CommandDef, RuntimeAdapter


CLAUDE_TOOL_MAP = {
    "file_read": "Read",
    "file_write": "Write",
    "task": "Task",
    "web_search": "WebSearch",
    "web_fetch": "WebFetch",
    "bash": "Bash",
}

DEFAULT_MODEL_MAP = {
    "heavy": "claude-opus-4-7",
    "standard": "claude-sonnet-4-6",
    "light": "claude-haiku-4-5-20251001",
}

# Bash is used by the injected preamble/postamble itself, so every command
# ends up needing it at runtime even if its generic frontmatter didn't list it.
IMPLICIT_TOOLS = ("Read", "Write", "Bash")


class ClaudeCodeAdapter(RuntimeAdapter):
    name = "claude"

    def default_install_root(self) -> Path:
        return Path.home() / ".claude" / "commands"

    def install_dir_marker(self, install_root: Path) -> Path:
        return install_root / "autonovel"

    def target_path(self, install_root: Path, cmd: CommandDef) -> Path:
        return install_root / "autonovel" / f"{cmd.stem}.md"

    def render(
        self,
        cmd: CommandDef,
        *,
        model_map: dict[str, str] | None = None,
    ) -> str:
        tools = [CLAUDE_TOOL_MAP[t] for t in cmd.allowed_tools]
        for implicit in IMPLICIT_TOOLS:
            if implicit not in tools:
                tools.append(implicit)

        model = (model_map or DEFAULT_MODEL_MAP)[cmd.model_tier]

        lines: list[str] = ["---"]
        lines.append(f"description: {cmd.description}")
        if cmd.argument_hint:
            lines.append(f"argument-hint: {cmd.argument_hint}")
        lines.append(f"allowed-tools: {', '.join(tools)}")
        lines.append(f"model: {model}")
        lines.append("---")
        lines.append("")
        lines.append(_preamble(cmd))
        lines.append("")
        lines.append(cmd.body.strip("\n"))
        lines.append("")
        lines.append(_postamble(cmd))
        lines.append("")
        return "\n".join(lines)


def _preamble(cmd: CommandDef) -> str:
    writes_bullet = "\n".join(f"  - {p}" for p in cmd.writes) or "  (none)"
    return f"""<autonovel-preamble>
Before following the <workflow> below, run the autonovel preamble. This is
mechanical; it handles the lock and checkpoints described in the
autonovel rewrite plan (§21.2) so that every command is interruptible and
every destructive change is reversible.

1. Use the `Bash` tool to run:
   `autonovel _begin --command {cmd.name} --args "$ARGUMENTS"`
   The helper resolves `$ARGUMENTS` against this command's `writes:` paths
   (listed below), acquires `.autonovel/in-progress.lock`, and snapshots
   the current state of every write target into
   `.autonovel/checkpoints/<UTC-timestamp>/`. If it exits non-zero —
   another command is in flight or the series is malformed — stop and
   surface the message verbatim.

2. Only proceed to the <workflow> below once `_begin` has succeeded.

Writes this command will perform (for context):
{writes_bullet}
</autonovel-preamble>"""


def _postamble(cmd: CommandDef) -> str:
    return f"""<autonovel-postamble>
After the <workflow> succeeds, run the autonovel postamble:

1. Use the `Bash` tool to run:
   `autonovel _end --command {cmd.name} --args "$ARGUMENTS" --status ok`
   passing `--wrote <path>` once for each file that was actually written.
   This releases the lock, writes `.autonovel/last-action.json` with the
   standard next step, and appends a JSON line to
   `.autonovel/command-log.jsonl`.

2. Print the user-facing footer exactly as emitted by `_end` (it includes
   the next standard step and a few sidequest alternatives). That footer is
   the primary UX for "what do I do next"; always show it.

If the <workflow> fails partway through:
- Run `autonovel _end --command {cmd.name} --args "$ARGUMENTS" --status error`
  (no `--wrote` paths). That leaves the lock marked `interrupted` so
  `/autonovel:resume` can offer recovery, and records the error in the
  command log without overwriting `last-action.json`.
</autonovel-postamble>"""
