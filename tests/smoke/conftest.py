"""Shared fixtures for Tier-3 smoke tests.

Smoke tests invoke a real AI CLI runtime against a copy of a fixture series.
They cost money and depend on network, so the whole module is opt-in under
`@pytest.mark.smoke` and skips cleanly when `claude` is not on `$PATH`.

Authentication: `claude -p` uses whatever auth the Claude Code CLI already
has — typically an OAuth login via `claude login` (Claude Max / Team / Pro
subscription), or an API key if the user explicitly set
`ANTHROPIC_API_KEY`. We deliberately do **not** require an API key,
because most users are on subscription auth.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from autonovel.adapters.claude_code import ClaudeCodeAdapter
from autonovel.adapters import installer


FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@dataclass
class LiveSeries:
    path: Path
    claude_binary: Path


def _claude_binary() -> Path | None:
    found = shutil.which("claude")
    return Path(found) if found else None


@pytest.fixture
def tmp_runtime_series(tmp_path: Path):
    """Yield a factory that copies a named fixture series into tmp_path,
    installs /autonovel:* commands into a project-local .claude/commands,
    and returns a LiveSeries bundle.

    Skips cleanly if `claude` is not on `$PATH`. Does not check for an API
    key: `claude -p` uses the subscription OAuth auth established by
    `claude login`, and requiring `ANTHROPIC_API_KEY` here would either
    skip legitimate runs or silently route billing through the wrong
    account when both auth modes are present.
    """

    claude = _claude_binary()
    if claude is None:
        pytest.skip(
            "`claude` CLI not on $PATH. Install Claude Code "
            "(https://docs.claude.com/en/docs/claude-code) and run `claude login` "
            "(or set `ANTHROPIC_API_KEY`) before running smoke tests."
        )

    def factory(fixture_name: str) -> LiveSeries:
        src = FIXTURES / fixture_name
        if not src.is_dir():
            pytest.fail(f"fixture {fixture_name!r} not found at {src}")
        dst = tmp_path / fixture_name
        shutil.copytree(src, dst)
        # Install commands into the project-local `.claude/commands/` so
        # that the invocation in *this* series picks them up without
        # touching the user's global install.
        installer.install(
            ClaudeCodeAdapter(),
            install_root=dst / ".claude" / "commands",
        )
        return LiveSeries(path=dst, claude_binary=claude)

    return factory


def run_command_in_runtime(
    runtime: str,
    *,
    command: str,
    cwd: Path,
    allowed_tools: list[str],
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    if runtime != "claude":
        raise NotImplementedError(f"runtime {runtime!r} not supported until PR 8")
    cmd = [
        "claude",
        "-p",
        command,
        "--allowed-tools",
        ",".join(allowed_tools),
    ]
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
