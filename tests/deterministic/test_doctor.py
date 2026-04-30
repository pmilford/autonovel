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


# ---------------------------------------------------------------------------
# Missing export tools — used by `autonovel doctor --install-missing`
# to delegate to install-export-tools for the missing-tools subset.

def test_missing_export_tools_returns_subset_of_known_tools() -> None:
    """`missing_export_tools` returns names that are NOT on PATH —
    by definition a subset of `EXPORT_TOOLS` keys."""
    from autonovel.housekeeping.doctor import (
        EXPORT_TOOLS,
        missing_export_tools,
    )
    missing = missing_export_tools()
    for name in missing:
        assert name in EXPORT_TOOLS


def test_missing_export_tools_excludes_present_tools(monkeypatch) -> None:
    """When a tool IS on PATH (mocked), it must not appear in the
    missing list."""
    import autonovel.housekeeping.doctor as doc_mod

    real_which = doc_mod.shutil.which

    def fake_which(name: str):
        if name == "tectonic":
            return "/usr/local/bin/tectonic"  # pretend installed
        return real_which(name)

    monkeypatch.setattr(doc_mod.shutil, "which", fake_which)
    missing = doc_mod.missing_export_tools()
    assert "tectonic" not in missing


# ---------------------------------------------------------------------------
# Claude Code settings — [1m] context-mode billing-gate detection.

import json as _json


def test_claude_settings_warns_on_1m_model(tmp_path):
    from autonovel.housekeeping import doctor
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(_json.dumps({
        "model": "claude-opus-4-7[1m]",
    }), encoding="utf-8")
    warnings = doctor.check_claude_settings(home=home)
    assert any("[1m]" in w for w in warnings)
    assert any("/extra-usage" in w for w in warnings)
    assert any("/model" in w for w in warnings)


def test_claude_settings_clean_when_no_1m(tmp_path):
    from autonovel.housekeeping import doctor
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(_json.dumps({
        "model": "claude-sonnet-4-6",
    }), encoding="utf-8")
    assert doctor.check_claude_settings(home=home) == []


def test_claude_settings_walks_nested_keys(tmp_path):
    from autonovel.housekeeping import doctor
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(_json.dumps({
        "preferred": {"models": ["claude-opus-4-7", "claude-sonnet-4-6[1m]"]},
    }), encoding="utf-8")
    warnings = doctor.check_claude_settings(home=home)
    assert len(warnings) == 1
    assert "claude-sonnet-4-6[1m]" in warnings[0]


def test_claude_settings_skips_missing_files(tmp_path):
    from autonovel.housekeeping import doctor
    # No ~/.claude/settings.json, no <project>/.claude/settings.json.
    assert doctor.check_claude_settings(home=tmp_path / "no-home",
                                         project_root=tmp_path / "no-project") == []


def test_claude_settings_skips_malformed_json(tmp_path):
    from autonovel.housekeeping import doctor
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text("{not json", encoding="utf-8")
    # Malformed file is *not* our remit; we just don't crash.
    assert doctor.check_claude_settings(home=home) == []


def test_claude_settings_includes_project_local(tmp_path):
    from autonovel.housekeeping import doctor
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    (project / ".claude" / "settings.json").write_text(_json.dumps({
        "statusLine": {"command": "echo"},
        "model": "claude-haiku-4-5[1m]",
    }), encoding="utf-8")
    warnings = doctor.check_claude_settings(home=tmp_path / "no-home",
                                             project_root=project)
    assert any("[1m]" in w for w in warnings)
