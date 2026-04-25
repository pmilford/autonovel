"""Housekeeping helpers for `autonovel test-fixture new|list|run`.

Per §12a: end users (and we) can spin up a new genre fixture under
`tests/fixtures/tiny-series-<name>/` with a paired smoke-test stub at
`tests/smoke/test_<name>_smoke.py`. The fixture mirrors what
`autonovel new-series` produces, plus a small amount of genre-aware
seeding so the smoke test has something to assert against.

This module deliberately stays a thin wrapper over `scaffold.new_series`
+ `scaffold.new_book`: a fixture is just a series with a known shape and
a paired smoke test. Tier-1 tests assert the produced layout matches.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import scaffold

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_FIXTURE_PREFIX = "tiny-series-"


class FixtureError(ValueError):
    pass


@dataclass(frozen=True)
class FixtureInfo:
    name: str
    path: Path
    has_smoke_test: bool
    smoke_test_path: Path


@dataclass
class NewFixtureResult:
    fixture: FixtureInfo
    created: list[Path]


def repo_root_from(start: Path | None = None) -> Path:
    """Walk up from `start` (default cwd) to find the repo root.

    A directory is the repo root if it contains both `tests/fixtures/`
    and `tests/smoke/`. We do not walk past the user's home directory.
    """
    here = (start or Path.cwd()).resolve()
    home = Path.home().resolve()
    candidate = here
    while True:
        if (candidate / "tests" / "fixtures").is_dir() and (candidate / "tests" / "smoke").is_dir():
            return candidate
        if candidate == candidate.parent or candidate == home:
            break
        candidate = candidate.parent
    raise FixtureError(
        f"could not find a repo root with tests/fixtures/ and tests/smoke/ "
        f"walking up from {here}"
    )


def _fixtures_dir(repo_root: Path) -> Path:
    return repo_root / "tests" / "fixtures"


def _smoke_dir(repo_root: Path) -> Path:
    return repo_root / "tests" / "smoke"


def _strip_prefix(name: str) -> str:
    return name[len(_FIXTURE_PREFIX):] if name.startswith(_FIXTURE_PREFIX) else name


def _validate_name(short_name: str) -> None:
    if not _NAME_RE.match(short_name):
        raise FixtureError(
            f"fixture name must match [a-z][a-z0-9-]*; got {short_name!r}"
        )


def list_fixtures(repo_root: Path | None = None) -> list[FixtureInfo]:
    root = repo_root or repo_root_from()
    fixtures_dir = _fixtures_dir(root)
    smoke_dir = _smoke_dir(root)
    out: list[FixtureInfo] = []
    if not fixtures_dir.is_dir():
        return out
    for entry in sorted(fixtures_dir.iterdir()):
        if not entry.is_dir():
            continue
        if not entry.name.startswith(_FIXTURE_PREFIX):
            continue
        if not (entry / "project.yaml").is_file():
            continue
        short = _strip_prefix(entry.name)
        smoke_path = smoke_dir / f"test_{short.replace('-', '_')}_smoke.py"
        has_smoke = smoke_path.is_file() or _has_genre_smoke(smoke_dir, short)
        out.append(FixtureInfo(
            name=short,
            path=entry,
            has_smoke_test=has_smoke,
            smoke_test_path=smoke_path,
        ))
    return out


def _has_genre_smoke(smoke_dir: Path, short_name: str) -> bool:
    """Detect a smoke test that uses `@pytest.mark.genre("<short>")` even if
    its file is not named `test_<short>_smoke.py`. Handles legacy fixtures
    (e.g. historical's `test_historical_research.py`) without requiring
    a rename."""
    if not smoke_dir.is_dir():
        return False
    needle = f'genre("{short_name}")'
    for f in smoke_dir.glob("test_*.py"):
        try:
            if needle in f.read_text(encoding="utf-8"):
                return True
        except OSError:
            continue
    return False


def new_fixture(
    short_name: str,
    *,
    repo_root: Path | None = None,
    genre: str | None = None,
    book_name: str = "book-one",
) -> NewFixtureResult:
    _validate_name(short_name)
    root = repo_root or repo_root_from()
    fixtures_dir = _fixtures_dir(root)
    smoke_dir = _smoke_dir(root)
    if not fixtures_dir.is_dir():
        raise FixtureError(f"{fixtures_dir} does not exist")
    if not smoke_dir.is_dir():
        raise FixtureError(f"{smoke_dir} does not exist")

    series_full_name = f"{_FIXTURE_PREFIX}{short_name}"
    series_root = fixtures_dir / series_full_name
    if series_root.exists() and any(series_root.iterdir()):
        raise FixtureError(f"{series_root} already exists and is not empty")

    created: list[Path] = []

    series_result = scaffold.new_series(
        series_root,
        series_name=series_full_name,
        genre=genre or short_name,
    )
    created.extend(series_result.created)

    book_result = scaffold.new_book(series_result.series, book_name=book_name)
    created.extend(book_result.created)

    readme_path = series_root / "README.md"
    readme_path.write_text(_render_fixture_readme(short_name, genre or short_name), encoding="utf-8")
    created.append(readme_path)

    smoke_path = smoke_dir / f"test_{short_name.replace('-', '_')}_smoke.py"
    if smoke_path.exists():
        raise FixtureError(f"smoke test already exists: {smoke_path}")
    smoke_path.write_text(_render_smoke_test(short_name, book_name), encoding="utf-8")
    created.append(smoke_path)

    fixture = FixtureInfo(
        name=short_name,
        path=series_root,
        has_smoke_test=True,
        smoke_test_path=smoke_path,
    )
    return NewFixtureResult(fixture=fixture, created=created)


def run_fixture(
    short_name: str,
    *,
    repo_root: Path | None = None,
    extra_pytest_args: list[str] | None = None,
) -> int:
    """Shell out to pytest for a single fixture's smoke test.

    Returns the pytest exit code. Caller is responsible for paying for it
    (smoke tests cost money — see CLAUDE.md auth policy).
    """
    _validate_name(short_name)
    root = repo_root or repo_root_from()
    smoke_path = _smoke_dir(root) / f"test_{short_name.replace('-', '_')}_smoke.py"
    if not smoke_path.is_file():
        raise FixtureError(f"smoke test not found: {smoke_path}")
    args = [
        sys.executable, "-m", "pytest",
        str(smoke_path),
        "-q", "-m", "smoke",
    ]
    if extra_pytest_args:
        args.extend(extra_pytest_args)
    proc = subprocess.run(args, cwd=root)
    return proc.returncode


def render_list(fixtures: list[FixtureInfo]) -> str:
    if not fixtures:
        return "(no fixtures found under tests/fixtures/tiny-series-*)"
    lines = []
    for f in fixtures:
        marker = "✓" if f.has_smoke_test else "·"
        lines.append(f"  {marker} {f.name}    ({f.path.relative_to(f.path.parent.parent.parent)})")
    lines.append("")
    lines.append("Legend: ✓ has smoke test, · scaffolded but no smoke test yet")
    return "\n".join(lines)


def _render_fixture_readme(short_name: str, genre: str) -> str:
    return f"""# tiny-series-{short_name}

Genre fixture for Tier-3 smoke tests. Created by
`autonovel test-fixture new {short_name}`.

**Genre:** {genre}

## What this fixture exercises

Replace this paragraph with one or two sentences describing the genre
quirk the smoke test asserts on (per §12a contract). Examples:

  - mystery: fair-play clue seeding; red-herring ledger.
  - fantasy: Sanderson's-laws hard-rule check on the magic system.
  - thriller: ticking-clock / stakes-escalation per chapter.

## Filling out the seeds

The scaffolder created an empty series shell. Edit before running the
smoke test:

  - `project.yaml` — set `period`, `genre`, default thresholds.
  - `seed.txt` (book and series) — the initial concept.
  - `shared/world.md`, `shared/characters.md` — minimal seed lore.
  - `shared/period_bans.txt` — only if period-sensitive (historical /
    period fantasy).

## Running the test

```bash
autonovel test-fixture run {short_name}
# or directly:
pytest tests/smoke/test_{short_name.replace('-', '_')}_smoke.py -q -m smoke
```
"""


def _render_smoke_test(short_name: str, book_name: str) -> str:
    fn_short = short_name.replace("-", "_")
    return f'''"""Tier-3 smoke: genre-characteristic assertion for {short_name}.

Per §12a: every fixture must assert at least one genre-characteristic
behaviour, not just "a file was written". Replace the body of
`test_{fn_short}_genre_check` with the assertion that proves the
{short_name} fixture's genre quirk is honoured.

This stub runs `/autonovel:gen-world` against the fixture and verifies
the world.md file was written. Customize as needed.
"""

from __future__ import annotations

import pytest

from .conftest import run_command_in_runtime


FIXTURE_NAME = "tiny-series-{short_name}"
BOOK_NAME = "{book_name}"


@pytest.mark.smoke
@pytest.mark.genre("{short_name}")
def test_{fn_short}_genre_check(tmp_runtime_series) -> None:
    series = tmp_runtime_series(FIXTURE_NAME)

    result = run_command_in_runtime(
        runtime="claude",
        command="/autonovel:gen-world",
        cwd=series.path,
        allowed_tools=["Read", "Write", "Bash"],
        timeout=600,
    )
    assert result.returncode == 0, (
        f"claude returned {{result.returncode}}\\n"
        f"stdout:\\n{{result.stdout}}\\n"
        f"stderr:\\n{{result.stderr}}"
    )

    world = series.path / "shared" / "world.md"
    assert world.is_file(), f"shared/world.md not written by /autonovel:gen-world"
    text = world.read_text(encoding="utf-8")

    # TODO ({short_name}): replace this generic length check with a
    # genre-characteristic assertion (e.g. "magic system has costs",
    # "outline ledger flags red herrings", "stakes escalate per chapter").
    assert len(text.strip()) > 50, (
        f"world.md is suspiciously empty for fixture {{FIXTURE_NAME}}"
    )
'''
