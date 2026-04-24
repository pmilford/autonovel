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
