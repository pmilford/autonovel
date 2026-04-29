"""Tier-3 `pipx install` round-trip — confirms the wheel is
self-contained.

Bug class this catches: a CLI subcommand or import path that works
under `pip install -e .` (because the editable-install path lets
relative imports / templates / data files resolve via the source
tree) but fails under `pipx install <repo>` (which builds a wheel
and installs into an isolated venv). The 2026-04-25 production
incident was `python -m autonovel.mechanical` not finding a
templates file because it lived under `src/autonovel/templates/`
but wasn't declared in `[tool.hatch.build.targets.wheel.force-include]`.

What this test does:
  1. Skip cleanly if `pipx` is not on $PATH.
  2. Set `PIPX_HOME` and `PIPX_BIN_DIR` to a tmp dir so the
     install does NOT touch the developer's real pipx state.
  3. `pipx install <repo_root>` — actually builds a wheel and
     installs it, exactly as a user running `pipx install
     autonovel` would.
  4. Run a few hand-picked subcommands through the installed
     binary and assert exit-code 0:
       - `autonovel doctor`            (no LLM, no series)
       - `autonovel --help`            (cli registers + exits)
       - `autonovel _next-actions
            --help`                    (housekeeping subcommand
                                        + helper module imports)
       - `autonovel mechanical
            slop --help`               (mechanical subgroup loads)
  5. The shell whose `python` is the system python is what runs
     this — pipx isolates the installed venv from the project
     venv, which is the whole point.

Marked `@pytest.mark.smoke` (cost: ~30s install; only opt-in) AND
`@pytest.mark.pipx_install` so it can be excluded independently
of the LLM-cost smoke tests via `-m "smoke and not pipx_install"`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _pipx_invocation() -> list[str] | None:
    """Return the argv prefix that runs pipx, or None if it isn't
    available. Prefer the `pipx` binary on $PATH (typical user
    install); fall back to `python -m pipx` (CI / ad-hoc)."""
    if shutil.which("pipx") is not None:
        return ["pipx"]
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pipx", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode == 0:
            return [sys.executable, "-m", "pipx"]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


@pytest.fixture
def pipx_home(tmp_path: Path) -> tuple[list[str], dict[str, str]]:
    """Returns `(pipx_argv_prefix, env)`. The env points pipx at an
    isolated tmp home + bin dir so the install does not touch the
    user's pipx state. Skips the test cleanly when pipx is not
    available either as a PATH binary or as a `python -m pipx`
    module on the test runner's interpreter."""
    pipx_argv = _pipx_invocation()
    if pipx_argv is None:
        pytest.skip(
            "pipx not available. `pip install --user pipx` then "
            "`python -m pipx ensurepath` to install."
        )
    pipx_home_dir = tmp_path / "pipx-home"
    pipx_bin_dir = tmp_path / "pipx-bin"
    pipx_home_dir.mkdir()
    pipx_bin_dir.mkdir()
    env = dict(os.environ)
    env["PIPX_HOME"] = str(pipx_home_dir)
    env["PIPX_BIN_DIR"] = str(pipx_bin_dir)
    # Suppress the colour escape codes pipx loves to emit.
    env["NO_COLOR"] = "1"
    return pipx_argv, env


def _install(pipx_argv: list[str], env: dict[str, str]) -> Path:
    """Run `pipx install <repo>` against the isolated home and
    return the path to the installed `autonovel` binary."""
    proc = subprocess.run(
        [*pipx_argv, "install", str(REPO_ROOT), "--force"],
        env=env, capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, (
        f"pipx install failed (exit {proc.returncode}):\n"
        f"STDOUT:\n{proc.stdout}\n"
        f"STDERR:\n{proc.stderr}"
    )
    bin_path = Path(env["PIPX_BIN_DIR"]) / "autonovel"
    assert bin_path.is_file(), f"pipx install left no `autonovel` at {bin_path}"
    return bin_path


def _run(autonovel: Path, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(autonovel), *args], env=env,
        capture_output=True, text=True, timeout=30,
    )


@pytest.mark.smoke
@pytest.mark.pipx_install
def test_pipx_install_subcommands_load(
    pipx_home: tuple[list[str], dict[str, str]],
    tmp_path: Path,
) -> None:
    """Install via pipx, then exercise the CLI surfaces that have
    historically broken under wheel packaging. If any one of them
    errors on import (the bug class this test catches), pipx puts
    a non-zero exit code on stdout/stderr."""
    pipx_argv, env = pipx_home
    autonovel = _install(pipx_argv, env)

    # `autonovel --help` — the CLI parser registers without error.
    proc = _run(autonovel, "--help", env=env)
    assert proc.returncode == 0, proc.stderr
    assert "autonovel" in proc.stdout.lower()

    # `autonovel _next-actions --help` — confirms the helper
    # module + its transitive imports (project.py, paths.py,
    # last_action.py) all resolve under the installed wheel.
    proc = _run(autonovel, "_next-actions", "--help", env=env)
    assert proc.returncode == 0, proc.stderr

    # `autonovel mechanical slop --help` — confirms the mechanical
    # subgroup's lazy imports succeed (this was the 2026-04-25
    # production failure mode).
    proc = _run(autonovel, "mechanical", "slop", "--help", env=env)
    assert proc.returncode == 0, proc.stderr

    # `autonovel _promote-canon --help` — confirms the promote-canon
    # module + its YAML/datetime imports resolve under the wheel.
    proc = _run(autonovel, "_promote-canon", "--help", env=env)
    assert proc.returncode == 0, proc.stderr

    # End-to-end exercise: build a fresh series + book using the
    # installed CLI, then run `doctor` inside it. This is the
    # strongest check for templates packaging — `new-series`
    # writes from `src/autonovel/templates/`, so a missing
    # force-include in pyproject.toml fails here loudly.
    series_parent = tmp_path / "series-parent"
    series_parent.mkdir()
    proc = subprocess.run(
        [str(autonovel), "new-series", "demo-series",
         "--dest", str(series_parent), "--genre", "literary"],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, (
        f"new-series failed (templates not packaged?):\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    series_dir = series_parent / "demo-series"
    assert (series_dir / "project.yaml").is_file()

    # `autonovel doctor` against the freshly-created series.
    proc = subprocess.run(
        [str(autonovel), "doctor"],
        env=env, cwd=series_dir, capture_output=True, text=True, timeout=30,
    )
    # doctor is informational; warnings are fine but exit must be 0 (ok)
    # or 1 (warnings present). Non-zero-and-not-1 means an error.
    assert proc.returncode in (0, 1), (
        f"doctor errored:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
