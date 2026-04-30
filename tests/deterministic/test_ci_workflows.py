"""Tier-1 sanity checks for `.github/workflows/*.yml`.

Catches the bug class where a workflow file goes through a refactor
and ends up with malformed YAML, missing required fields, or stale
matrix entries — none of which a regular test run would notice
since CI workflows aren't loaded by Python.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")


_WORKFLOWS_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / ".github" / "workflows"
)


def _load_workflow(filename: str) -> dict:
    return yaml.safe_load(
        (_WORKFLOWS_DIR / filename).read_text(encoding="utf-8")
    )


# ----------------------------------------------------- test.yml


def test_test_workflow_parses_as_yaml() -> None:
    wf = _load_workflow("test.yml")
    assert wf["name"]
    assert "test" in wf["jobs"]


def test_test_workflow_runs_tier_1_and_2() -> None:
    wf = _load_workflow("test.yml")
    steps = wf["jobs"]["test"]["steps"]
    pytest_step = next(s for s in steps if s.get("name", "").startswith("Run Tier"))
    cmd = pytest_step["run"]
    assert "tests/deterministic" in cmd
    assert "tests/contracts" in cmd


def test_test_workflow_matrix_includes_supported_python_versions() -> None:
    """pyproject.toml floor is 3.11; matrix must include 3.11+ and a
    current release."""
    wf = _load_workflow("test.yml")
    versions = wf["jobs"]["test"]["strategy"]["matrix"]["python-version"]
    assert "3.11" in versions
    assert any(v.startswith("3.13") or v.startswith("3.12") for v in versions)


# ----------------------------------------------------- smoke-weekly.yml


def test_smoke_workflow_parses_as_yaml() -> None:
    wf = _load_workflow("smoke-weekly.yml")
    assert wf["name"]
    assert "claude-smoke" in wf["jobs"]


def test_smoke_workflow_runs_on_cron_and_dispatch() -> None:
    """Auth-needing jobs should never trigger on push; users would
    burn API credit on every commit. Confirm push isn't in the
    triggers."""
    # PyYAML parses bare `on:` as boolean True. Try both keys.
    wf = _load_workflow("smoke-weekly.yml")
    triggers = wf.get("on") or wf.get(True)
    assert triggers is not None, "smoke workflow has no triggers block"
    assert "schedule" in triggers
    assert "workflow_dispatch" in triggers
    assert "push" not in triggers
    assert "pull_request" not in triggers


def test_smoke_workflow_supports_oauth_and_api_key_paths() -> None:
    """Two distinct steps run pytest under different env shapes;
    one for subscription auth, one for API-key auth. Both must be
    present so the job works under either secret configuration."""
    wf = _load_workflow("smoke-weekly.yml")
    steps = wf["jobs"]["claude-smoke"]["steps"]
    step_names = [s.get("name", "") for s in steps]
    assert any("subscription auth" in n for n in step_names)
    assert any("API-key auth" in n for n in step_names)


def test_smoke_workflow_skips_when_no_auth_configured() -> None:
    """A job that fails because the user hasn't set the secret
    yet looks like a regression — but it's a config gap, not
    code drift. Workflow should exit 0 with a diagnostic when no
    auth is available."""
    wf = _load_workflow("smoke-weekly.yml")
    steps = wf["jobs"]["claude-smoke"]["steps"]
    skip_step = next(
        s for s in steps if "Skip with diagnostic" in s.get("name", "")
    )
    assert "exit 0" in skip_step["run"]
