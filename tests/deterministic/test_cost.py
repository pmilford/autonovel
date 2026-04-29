"""Tier-1 tests for token + cost tracking.

Covers three layers:
  - command_log.LogEntry round-trip with the new usage fields.
  - cost.build_report aggregation by book / tier / command.
  - cost.render_markdown shape and CLI round-trip.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel import command_log, cost
from autonovel.housekeeping import scaffold


# ---------------------------------------------------------- LogEntry


def test_log_entry_token_fields_round_trip(tmp_path: Path) -> None:
    log = tmp_path / "command-log.jsonl"
    command_log.append(
        log, command="autonovel:draft", args=["1"], status="ok",
        book="b", model="claude-sonnet-4-6", tier="standard",
        input_tokens=1500, output_tokens=4200, cache_read_tokens=900,
        cost_usd=0.0735,
    )
    entries = command_log.read_all(log)
    assert len(entries) == 1
    e = entries[0]
    assert e.book == "b"
    assert e.model == "claude-sonnet-4-6"
    assert e.tier == "standard"
    assert e.input_tokens == 1500
    assert e.output_tokens == 4200
    assert e.cache_read_tokens == 900
    assert e.cost_usd == 0.0735


def test_log_entry_default_fields_omitted_from_json(tmp_path: Path) -> None:
    """A mechanical-only command leaves token fields None; they
    should NOT appear in the rendered JSON line so historical
    entries stay compact."""
    log = tmp_path / "command-log.jsonl"
    command_log.append(log, command="autonovel:next", args=[], status="ok")
    raw = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert "input_tokens" not in raw
    assert "cost_usd" not in raw
    assert "model" not in raw


def test_log_entry_partial_telemetry(tmp_path: Path) -> None:
    """Some telemetry fields can land while others stay None — e.g.
    a runtime that reports tokens but not cost USD."""
    log = tmp_path / "command-log.jsonl"
    command_log.append(
        log, command="autonovel:draft", args=[], status="ok",
        input_tokens=1000, output_tokens=2000,
    )
    raw = json.loads(log.read_text().splitlines()[0])
    assert raw["input_tokens"] == 1000
    assert "cost_usd" not in raw


# ---------------------------------------------------------- build_report


def _seed_log(tmp_path: Path, rows: list[dict]) -> Path:
    log = tmp_path / "command-log.jsonl"
    for row in rows:
        command_log.append(log, **row)
    return log


def test_build_report_total_aggregation(tmp_path: Path) -> None:
    log = _seed_log(tmp_path, [
        {"command": "autonovel:draft", "args": ["1"], "status": "ok",
         "book": "a", "tier": "standard",
         "input_tokens": 1000, "output_tokens": 2000, "cost_usd": 0.05},
        {"command": "autonovel:revise", "args": ["1"], "status": "ok",
         "book": "a", "tier": "heavy",
         "input_tokens": 2000, "output_tokens": 4000, "cost_usd": 0.20},
    ])
    report = cost.build_report(log)
    assert report.total.runs == 2
    assert report.total.input_tokens == 3000
    assert report.total.output_tokens == 6000
    assert abs(report.total.cost_usd - 0.25) < 1e-9


def test_build_report_by_book(tmp_path: Path) -> None:
    log = _seed_log(tmp_path, [
        {"command": "autonovel:draft", "args": [], "status": "ok",
         "book": "a", "input_tokens": 1000, "output_tokens": 2000,
         "cost_usd": 0.05},
        {"command": "autonovel:draft", "args": [], "status": "ok",
         "book": "b", "input_tokens": 500, "output_tokens": 1000,
         "cost_usd": 0.02},
    ])
    report = cost.build_report(log)
    assert report.by_book["a"].cost_usd == 0.05
    assert report.by_book["b"].cost_usd == 0.02
    assert report.by_book["a"].runs == 1


def test_build_report_by_tier(tmp_path: Path) -> None:
    log = _seed_log(tmp_path, [
        {"command": "autonovel:draft", "args": [], "status": "ok",
         "book": "a", "tier": "heavy",
         "input_tokens": 1000, "output_tokens": 2000, "cost_usd": 0.10},
        {"command": "autonovel:next", "args": [], "status": "ok",
         "book": "a"},  # mechanical
        {"command": "autonovel:summarize-chapter", "args": ["1"],
         "status": "ok", "book": "a", "tier": "standard",
         "input_tokens": 200, "output_tokens": 500, "cost_usd": 0.01},
    ])
    report = cost.build_report(log)
    assert report.mechanical_runs == 1
    assert report.by_tier["heavy"].runs == 1
    assert report.by_tier["standard"].runs == 1
    # Mechanical-only runs land under "mechanical" tier when no tier
    # was given.
    assert "mechanical" in report.by_tier


def test_build_report_by_command_top(tmp_path: Path) -> None:
    log = _seed_log(tmp_path, [
        {"command": "autonovel:draft", "args": [], "status": "ok",
         "input_tokens": 1000, "output_tokens": 2000, "cost_usd": 0.10},
        {"command": "autonovel:draft", "args": [], "status": "ok",
         "input_tokens": 500, "output_tokens": 1000, "cost_usd": 0.05},
        {"command": "autonovel:revise", "args": [], "status": "ok",
         "input_tokens": 2000, "output_tokens": 4000, "cost_usd": 0.20},
    ])
    report = cost.build_report(log)
    # draft ran twice; revise ran once but cost more.
    assert report.by_command["autonovel:draft"].runs == 2
    assert report.by_command["autonovel:revise"].cost_usd == 0.20


def test_build_report_unknown_cost(tmp_path: Path) -> None:
    """A row with token counts but no cost_usd lands in
    cost_unknown_runs so the user knows the cost figure is
    incomplete."""
    log = _seed_log(tmp_path, [
        {"command": "autonovel:draft", "args": [], "status": "ok",
         "book": "a", "input_tokens": 1000, "output_tokens": 2000},
        # ↑ tokens but no cost
        {"command": "autonovel:revise", "args": [], "status": "ok",
         "book": "a", "input_tokens": 500, "output_tokens": 1000,
         "cost_usd": 0.05},
    ])
    report = cost.build_report(log)
    assert report.total.cost_known_runs == 1
    assert report.total.cost_unknown_runs == 1


def test_build_report_error_runs_counted_separately(tmp_path: Path) -> None:
    log = _seed_log(tmp_path, [
        {"command": "autonovel:draft", "args": [], "status": "error",
         "input_tokens": 500, "output_tokens": 100, "cost_usd": 0.02},
    ])
    report = cost.build_report(log)
    assert report.error_runs == 1


def test_build_report_empty_log(tmp_path: Path) -> None:
    log = tmp_path / "command-log.jsonl"
    report = cost.build_report(log)
    assert report.total.runs == 0
    assert report.mechanical_runs == 0


# ---------------------------------------------------------- render


def test_render_markdown_empty_log(tmp_path: Path) -> None:
    out = cost.render_markdown(cost.build_report(tmp_path / "missing.jsonl"))
    assert "No commands logged" in out


def test_render_markdown_includes_total_and_books(tmp_path: Path) -> None:
    log = _seed_log(tmp_path, [
        {"command": "autonovel:draft", "args": [], "status": "ok",
         "book": "a", "tier": "standard",
         "input_tokens": 1000, "output_tokens": 2000, "cost_usd": 0.05},
    ])
    out = cost.render_markdown(cost.build_report(log))
    assert "Cost summary" in out
    assert "$0.05" in out
    assert "By book" in out
    assert "| a |" in out


def test_render_markdown_mechanical_runs_note(tmp_path: Path) -> None:
    log = _seed_log(tmp_path, [
        {"command": "autonovel:next", "args": [], "status": "ok"},
    ])
    out = cost.render_markdown(cost.build_report(log))
    assert "mechanical" in out.lower()


# ---------------------------------------------------------- lifecycle wiring


@pytest.fixture
def series_root(tmp_path: Path):
    res = scaffold.new_series(tmp_path / "demo", series_name="demo")
    return res.series.root


def test_lifecycle_end_writes_usage_fields_to_log(series_root: Path) -> None:
    """End-to-end: lifecycle.end forwards the usage dict into the
    command-log entry."""
    from autonovel.housekeeping import lifecycle
    from autonovel.paths import SeriesLayout

    series = SeriesLayout(root=series_root)
    lifecycle.begin("autonovel:next", "", series=series)
    lifecycle.end(
        "autonovel:next", "", status="ok", wrote=[], series=series,
        usage={
            "model": "claude-haiku-4-5",
            "tier": "light",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.001,
        },
    )
    entries = command_log.read_all(series.command_log_file)
    e = next(x for x in entries if x.command == "autonovel:next")
    assert e.tier == "light"
    assert e.input_tokens == 100
    assert e.cost_usd == 0.001


def test_lifecycle_end_omits_usage_when_not_provided(series_root: Path) -> None:
    """Mechanical commands pass no usage dict; the log entry should
    still write cleanly with all telemetry fields None."""
    from autonovel.housekeeping import lifecycle
    from autonovel.paths import SeriesLayout

    series = SeriesLayout(root=series_root)
    lifecycle.begin("autonovel:next", "", series=series)
    lifecycle.end("autonovel:next", "", status="ok", wrote=[], series=series)
    entries = command_log.read_all(series.command_log_file)
    e = next(x for x in entries if x.command == "autonovel:next")
    assert e.input_tokens is None
    assert e.cost_usd is None


# ---------------------------------------------------------- CLI


def test_cli_cost_markdown(series_root: Path) -> None:
    log = series_root / ".autonovel" / "command-log.jsonl"
    command_log.append(log, command="autonovel:draft", args=["1"],
                        status="ok", book="b", tier="standard",
                        input_tokens=1000, output_tokens=2000,
                        cost_usd=0.05)
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "cost"],
        cwd=series_root, capture_output=True, text=True, check=True,
    )
    assert "Cost summary" in proc.stdout
    assert "$0.05" in proc.stdout


def test_cli_cost_json(series_root: Path) -> None:
    log = series_root / ".autonovel" / "command-log.jsonl"
    command_log.append(log, command="autonovel:draft", args=[],
                        status="ok", book="b",
                        input_tokens=1000, output_tokens=2000, cost_usd=0.05)
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "cost", "--format", "json"],
        cwd=series_root, capture_output=True, text=True, check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["total"]["runs"] == 1
    assert payload["total"]["cost_usd"] == 0.05
    assert "b" in payload["by_book"]


def test_cli_end_accepts_usage_flags(series_root: Path) -> None:
    """`autonovel _end --command ... --tier heavy --input-tokens N
    --cost-usd 0.5` populates the log entry."""
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "_begin",
         "--command", "autonovel:next", "--args", ""],
        cwd=series_root, capture_output=True, text=True, check=True,
    )
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "_end",
         "--command", "autonovel:next", "--args", "",
         "--tier", "heavy", "--input-tokens", "1500",
         "--output-tokens", "3000", "--cost-usd", "0.075"],
        cwd=series_root, capture_output=True, text=True, check=True,
    )
    entries = command_log.read_all(
        series_root / ".autonovel" / "command-log.jsonl"
    )
    e = next(x for x in entries if x.command == "autonovel:next")
    assert e.tier == "heavy"
    assert e.input_tokens == 1500
    assert e.cost_usd == 0.075
