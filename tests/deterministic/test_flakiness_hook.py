"""Tier-1: the top-level flakiness hook applies `flaky` to smoke tests.

We don't want to actually run a smoke test to verify this — that costs
money. Instead we run pytest in a subprocess against a tiny inline test
module that declares one smoke-marked test, and inspect the collected
markers.
"""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


RERUNFAILURES_AVAILABLE = importlib.util.find_spec("pytest_rerunfailures") is not None
reruns_only = pytest.mark.skipif(
    not RERUNFAILURES_AVAILABLE,
    reason="pytest-rerunfailures not installed; retry-once policy is a no-op",
)


@reruns_only
def test_hook_adds_flaky_marker_to_smoke_tests(tmp_path: Path) -> None:
    """Copy the repo's tests/conftest.py into a tmp project and collect a
    smoke-marked dummy test. The `flaky` marker must appear in the report."""

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    repo_conftest = Path(__file__).resolve().parents[1] / "conftest.py"
    shutil.copy2(repo_conftest, tests_dir / "conftest.py")

    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [tool.pytest.ini_options]
            testpaths = ["tests"]
            markers = [
                "smoke: smoke",
                "regression: regression",
                "genre(name): genre",
            ]
            """),
        encoding="utf-8",
    )

    (tests_dir / "test_probe.py").write_text(
        textwrap.dedent("""\
            import pytest

            @pytest.mark.smoke
            def test_smoke_probe():
                pass

            def test_non_smoke_probe():
                pass
            """),
        encoding="utf-8",
    )

    # `--collect-only -q` prints each collected test node id but does not run
    # them. For marker inspection we use `--markers` plus a Python one-liner
    # that imports pytest and introspects. Simpler: use `-p no:cacheprovider`
    # and parse `--collect-only --co -v` output.
    # Easier still: use pytest's own API via subprocess.
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "--no-header",
            "-o", "addopts=",
            "tests",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"collection failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "test_smoke_probe" in result.stdout
    assert "test_non_smoke_probe" in result.stdout

    # Inspect markers by running a tiny collection hook that prints them.
    inspector = tmp_path / "inspect_markers.py"
    inspector.write_text(
        textwrap.dedent("""\
            import pytest, sys
            from _pytest.config import get_config

            class _Plugin:
                def pytest_collection_modifyitems(self, items):
                    for item in items:
                        names = sorted(m.name for m in item.iter_markers())
                        print(f"{item.nodeid}:{','.join(names)}")
                    # Stop the session — we don't need to run anything.
                    pytest.exit("done", returncode=0)

            sys.exit(pytest.main(
                ["--collect-only", "-q", "--no-header", "-o", "addopts=", "tests"],
                plugins=[_Plugin()],
            ))
            """),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(inspector)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    # The Plugin prints lines like "tests/test_probe.py::test_smoke_probe:flaky,smoke"
    lines = {
        ln.split(":", 2)[-1]
        for ln in result.stdout.splitlines()
        if "test_probe.py" in ln
    }
    smoke_line = next(
        ln for ln in result.stdout.splitlines()
        if "test_smoke_probe" in ln
    )
    non_smoke_line = next(
        ln for ln in result.stdout.splitlines()
        if "test_non_smoke_probe" in ln
    )
    assert "flaky" in smoke_line, f"smoke test missing flaky marker: {smoke_line}"
    assert "flaky" not in non_smoke_line, f"non-smoke test got flaky marker: {non_smoke_line}"


def test_hook_module_importable() -> None:
    """Minimum sanity: tests/conftest.py loads cleanly under this Python."""
    path = Path(__file__).resolve().parents[1] / "conftest.py"
    import importlib.util

    spec = importlib.util.spec_from_file_location("autonovel_test_conftest_probe", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert hasattr(module, "pytest_collection_modifyitems")
    assert hasattr(module, "pytest_runtest_logreport")
