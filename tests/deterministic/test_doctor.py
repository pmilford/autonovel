"""autonovel doctor against a freshly scaffolded series."""

from __future__ import annotations

import shutil
from pathlib import Path

from autonovel.housekeeping import doctor


def test_fresh_series_is_clean(series_root: Path) -> None:
    report = doctor.run(series_root)
    assert report.ok, f"problems: {report.problems}"


def test_missing_dir_is_flagged(series_root: Path) -> None:
    shutil.rmtree(series_root / ".autonovel" / "checkpoints")
    report = doctor.run(series_root)
    assert not report.ok
    assert any("checkpoints" in p for p in report.problems)


def test_fix_recreates_missing_dir(series_root: Path) -> None:
    shutil.rmtree(series_root / ".autonovel" / "checkpoints")
    report = doctor.run(series_root, fix=True)
    assert (series_root / ".autonovel" / "checkpoints").is_dir()
    assert any("checkpoints" in f for f in report.fixed)


def test_missing_project_yaml_is_fatal(tmp_path: Path) -> None:
    report = doctor.run(tmp_path)
    assert not report.ok
    assert any("project.yaml" in p for p in report.problems)


def test_export_tool_check_enumerates_known_tools() -> None:
    """Every line from `check_export_tools` mentions both the missing
    tool and the command surface it unlocks, so a user sees *why* to
    install it."""
    from autonovel.housekeeping.doctor import EXPORT_TOOLS, check_export_tools

    lines = check_export_tools()
    # We don't know which tools are installed on the test box, so just
    # assert the shape of whatever is reported.
    for line in lines:
        assert ": missing — needed for " in line
        assert "install:" in line
    reported_tools = {line.split(":", 1)[0] for line in lines}
    assert reported_tools.issubset(set(EXPORT_TOOLS))


def test_export_tool_check_is_not_fatal(series_root: Path) -> None:
    """Missing export tools surface as warnings, not problems."""
    report = doctor.run(series_root)
    for w in report.warnings:
        assert "PROBLEM" not in w
    # Optional tools cannot make a fresh series report `not ok`.
    assert report.ok


def test_export_tool_check_can_be_suppressed(series_root: Path) -> None:
    report = doctor.run(series_root, export_tools=False)
    assert not any("export tool" in w for w in report.warnings)
