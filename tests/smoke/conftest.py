"""Shared fixtures for Tier-3 smoke tests.

Smoke tests invoke a real Claude Code runtime against a copy of a fixture
series, so the whole module is opt-in under `@pytest.mark.smoke` and skips
cleanly when `claude` is not on `$PATH`.

Authentication policy (the thing most places this file fusses with):

    SUBSCRIPTION IS THE PRIMARY AUTH MODE FOR THIS PROJECT.

Claude Code itself, when invoked with both `ANTHROPIC_API_KEY` set *and*
an OAuth session from `claude login`, prefers the API key — it will bill
pay-per-token through the API account instead of the subscription. That's
the wrong default for autonovel: our runtime commands are meant to run
inside the user's subscription (Claude Max / Team / Pro), which is
effectively "free" against an already-paid plan.

So by default this conftest strips `ANTHROPIC_API_KEY` from the
subprocess environment before invoking `claude -p`. Result: the smoke
test uses whatever `claude login` produced — the subscription path.

Escape hatch for developers who *do* want to exercise the API-key path
(e.g. to reproduce a billing/rate-limit issue): set
`AUTONOVEL_SMOKE_USE_API_KEY=1` in the environment. The conftest will
then preserve `ANTHROPIC_API_KEY` on the subprocess.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from autonovel.adapters.claude_code import ClaudeCodeAdapter
from autonovel.adapters import installer


FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

# Env var that flips the subprocess from subscription auth to API-key auth.
API_KEY_OPT_IN = "AUTONOVEL_SMOKE_USE_API_KEY"


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

    Skips cleanly if `claude` is not on `$PATH`.
    """

    claude = _claude_binary()
    if claude is None:
        pytest.skip(
            "`claude` CLI not on $PATH. Install Claude Code "
            "(https://docs.claude.com/en/docs/claude-code) and run `claude login` "
            "before running smoke tests. Smoke tests use your subscription "
            "auth by default; see `AUTONOVEL_SMOKE_USE_API_KEY` in conftest "
            "to opt into API-key billing instead."
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


def auth_aware_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Return a subprocess env that routes `claude -p` through subscription
    auth unless the developer opted into API-key auth with
    `AUTONOVEL_SMOKE_USE_API_KEY=1`.

    The rule: by default, strip `ANTHROPIC_API_KEY`. With the opt-in env
    var set, preserve it verbatim.

    Separate from the fixture so it can be unit-tested without spawning a
    subprocess.
    """
    env = dict(base) if base is not None else dict(os.environ)
    use_api_key = env.get(API_KEY_OPT_IN, "").strip().lower() in {"1", "true", "yes"}
    if not use_api_key:
        env.pop("ANTHROPIC_API_KEY", None)
        # ANTHROPIC_AUTH_TOKEN is the other pay-per-token auth header Claude
        # Code honours; strip it too for the same reason.
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
    return env


def run_command_in_runtime(
    runtime: str,
    *,
    command: str,
    cwd: Path,
    allowed_tools: list[str],
    timeout: int = 600,
    env: dict[str, str] | None = None,
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
        env=auth_aware_env(env),
    )
