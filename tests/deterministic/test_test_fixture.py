"""`autonovel test-fixture new|list|run` housekeeping (PR 9 §12a).

These tests cover the scaffolding produced by `test_fixture.new_fixture`.
The runner (`test_fixture.run_fixture`) shells to `pytest`; we don't
exercise that path here — we just lock the layout it would target.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autonovel.housekeeping import test_fixture


def _make_repo_root(tmp_path: Path) -> Path:
    """Build the minimum repo shape `test_fixture` requires."""
    (tmp_path / "tests" / "fixtures").mkdir(parents=True)
    (tmp_path / "tests" / "smoke").mkdir(parents=True)
    return tmp_path


def test_new_fixture_creates_series_and_smoke_test(tmp_path: Path) -> None:
    repo = _make_repo_root(tmp_path)
    result = test_fixture.new_fixture("mystery", repo_root=repo)

    series_root = repo / "tests" / "fixtures" / "tiny-series-mystery"
    smoke_path = repo / "tests" / "smoke" / "test_mystery_smoke.py"

    assert result.fixture.name == "mystery"
    assert result.fixture.path == series_root
    assert result.fixture.smoke_test_path == smoke_path
    assert result.fixture.has_smoke_test is True

    # Series shape mirrors `autonovel new-series` + a book + a README.
    assert (series_root / "project.yaml").is_file()
    assert (series_root / "README.md").is_file()
    assert (series_root / "shared" / "world.md").is_file()
    assert (series_root / "shared" / "events.md").is_file()
    assert (series_root / "shared" / "research" / "sources.yaml").is_file()
    assert (series_root / "books" / "book-one" / "seed.txt").is_file()

    # Smoke test stub is importable Python with the right markers.
    text = smoke_path.read_text(encoding="utf-8")
    assert "@pytest.mark.smoke" in text
    assert '@pytest.mark.genre("mystery")' in text
    assert "tiny-series-mystery" in text


def test_new_fixture_with_dashes(tmp_path: Path) -> None:
    repo = _make_repo_root(tmp_path)
    result = test_fixture.new_fixture("space-opera", repo_root=repo)

    smoke_path = repo / "tests" / "smoke" / "test_space_opera_smoke.py"
    assert smoke_path.is_file()
    assert result.fixture.smoke_test_path == smoke_path

    text = smoke_path.read_text(encoding="utf-8")
    # Function names use underscores; markers use the original short name.
    assert "def test_space_opera_genre_check(" in text
    assert '@pytest.mark.genre("space-opera")' in text


def test_new_fixture_rejects_bad_name(tmp_path: Path) -> None:
    repo = _make_repo_root(tmp_path)
    with pytest.raises(test_fixture.FixtureError):
        test_fixture.new_fixture("Bad Name", repo_root=repo)
    with pytest.raises(test_fixture.FixtureError):
        test_fixture.new_fixture("9-leading-digit", repo_root=repo)


def test_new_fixture_rejects_existing(tmp_path: Path) -> None:
    repo = _make_repo_root(tmp_path)
    test_fixture.new_fixture("mystery", repo_root=repo)
    with pytest.raises(test_fixture.FixtureError):
        test_fixture.new_fixture("mystery", repo_root=repo)


def test_list_fixtures_returns_known_shape(tmp_path: Path) -> None:
    repo = _make_repo_root(tmp_path)
    test_fixture.new_fixture("mystery", repo_root=repo)
    test_fixture.new_fixture("thriller", repo_root=repo)

    fixtures = test_fixture.list_fixtures(repo_root=repo)
    names = [f.name for f in fixtures]
    assert names == ["mystery", "thriller"]
    for f in fixtures:
        assert f.has_smoke_test is True
        assert f.smoke_test_path.is_file()


def test_list_fixtures_skips_non_fixture_dirs(tmp_path: Path) -> None:
    repo = _make_repo_root(tmp_path)
    # A stray directory not matching the `tiny-series-*` shape.
    (repo / "tests" / "fixtures" / "bells-reference").mkdir()
    (repo / "tests" / "fixtures" / "bells-reference" / "scores.json").write_text("{}", encoding="utf-8")
    test_fixture.new_fixture("mystery", repo_root=repo)

    fixtures = test_fixture.list_fixtures(repo_root=repo)
    assert [f.name for f in fixtures] == ["mystery"]


def test_list_fixtures_marks_missing_smoke_test(tmp_path: Path) -> None:
    repo = _make_repo_root(tmp_path)
    test_fixture.new_fixture("mystery", repo_root=repo)
    smoke_path = repo / "tests" / "smoke" / "test_mystery_smoke.py"
    smoke_path.unlink()

    fixtures = test_fixture.list_fixtures(repo_root=repo)
    assert len(fixtures) == 1
    assert fixtures[0].has_smoke_test is False


def test_repo_root_from_walks_up(tmp_path: Path) -> None:
    repo = _make_repo_root(tmp_path)
    nested = repo / "tests" / "smoke"
    found = test_fixture.repo_root_from(nested)
    assert found == repo


def test_repo_root_from_raises_when_no_repo(tmp_path: Path) -> None:
    # A directory tree that doesn't contain tests/fixtures + tests/smoke.
    (tmp_path / "nope").mkdir()
    with pytest.raises(test_fixture.FixtureError):
        test_fixture.repo_root_from(tmp_path / "nope")


def test_render_list_shape() -> None:
    out = test_fixture.render_list([])
    assert "no fixtures" in out


def test_run_fixture_rejects_missing_smoke(tmp_path: Path) -> None:
    repo = _make_repo_root(tmp_path)
    with pytest.raises(test_fixture.FixtureError):
        test_fixture.run_fixture("nonexistent", repo_root=repo)
