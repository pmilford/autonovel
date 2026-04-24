"""Top-level pytest hooks for the autonovel test suite.

The big thing this file does: implement the §12 item 1 flakiness policy.
Every test marked `smoke` is auto-rerun **once** on failure. A test that
flips (one fail, one pass) is tracked in `tests/flakiness.jsonl`; a test
that fails both times is a real signal.

This is intentionally applied via a collection hook rather than by editing
each smoke test, so command authors writing new smoke tests just drop
`@pytest.mark.smoke` and get the retry behaviour for free.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parent.parent
_FLAKINESS_LOG = _REPO_ROOT / "tests" / "flakiness.jsonl"


try:  # pytest-rerunfailures is an optional test dep (pyproject [test])
    import pytest_rerunfailures  # noqa: F401
    _HAVE_RERUN = True
except ImportError:  # pragma: no cover — exercised only without the dev dep
    _HAVE_RERUN = False


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply `@pytest.mark.flaky(reruns=1, reruns_delay=2)` to every smoke test.

    If pytest-rerunfailures is not installed, do nothing — the smoke tests
    still run, they just don't retry. The policy degrades gracefully.
    """
    if not _HAVE_RERUN:
        return
    for item in items:
        if "smoke" not in item.keywords:
            continue
        if "flaky" in item.keywords:
            continue  # the test already declared its own retry policy
        item.add_marker(pytest.mark.flaky(reruns=1, reruns_delay=2))


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """If a smoke test flips (one fail, one pass) within a single session,
    append a line to `tests/flakiness.jsonl` so we can spot tests that have
    degraded to worthless. Only fires on the final 'call' phase."""
    if report.when != "call":
        return
    if "smoke" not in getattr(report, "keywords", {}):
        return
    # pytest-rerunfailures tags rerun reports with the `rerun` outcome or an
    # `execution_count` attribute. We only log when the rerun count is > 0 AND
    # the final outcome is passed — a real flake-that-recovered.
    exec_count = getattr(report, "execution_count", 1) or 1
    if exec_count <= 1:
        return
    if report.outcome != "passed":
        return
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "test": report.nodeid,
        "attempts": exec_count,
        "pid": os.getpid(),
    }
    _FLAKINESS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with _FLAKINESS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
