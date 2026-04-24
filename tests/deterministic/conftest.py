from __future__ import annotations

from pathlib import Path

import pytest

from autonovel.housekeeping import scaffold


@pytest.fixture
def series_root(tmp_path: Path) -> Path:
    """A real series at tmp_path/demo, created via the scaffolder."""
    result = scaffold.new_series(tmp_path / "demo", series_name="demo", genre="literary")
    return result.series.root
