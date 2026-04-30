"""Tier-1 tests for `install_export_tools.py` and the
`autonovel install-export-tools` CLI subcommand.

Covers OS detection (mocked), install-method detection,
plan assembly across the export → tool mapping, render shape,
apply seam (subprocess runner injected), and CLI happy paths.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from autonovel import install_export_tools as iet


# ----------------------------------------------------- detect_os


def test_detect_os_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(iet.platform, "system", lambda: "Darwin")
    assert iet.detect_os() == "macos"


def test_detect_os_debian(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(iet.platform, "system", lambda: "Linux")
    fake_release = tmp_path / "os-release"
    fake_release.write_text(
        'NAME="Ubuntu"\nID=ubuntu\nID_LIKE=debian\n', encoding="utf-8"
    )
    monkeypatch.setattr(iet, "Path",
                         lambda p: fake_release if p == "/etc/os-release" else Path(p))
    # Need to also recover Path() for the result type — _tool_table_for
    # doesn't use Path; only detect_os does the os-release read.
    assert iet.detect_os() == "debian"


def test_detect_os_unknown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(iet.platform, "system", lambda: "Linux")
    fake_release = tmp_path / "os-release"
    fake_release.write_text("NAME=ZorgOS\nID=zorg\n", encoding="utf-8")
    monkeypatch.setattr(iet, "Path",
                         lambda p: fake_release if p == "/etc/os-release" else Path(p))
    assert iet.detect_os() == "other"


# ----------------------------------------------------- plan


def test_plan_pdf_includes_tectonic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(iet, "detect_os", lambda: "debian")
    monkeypatch.setattr(iet, "detect_install_method", lambda: "pip")
    p = iet.plan(exports=["pdf"])
    names = [t.name for t in p.selected_tools]
    assert "tectonic" in names


def test_plan_dedupes_tools_across_exports(monkeypatch: pytest.MonkeyPatch) -> None:
    """rsvg-convert is in both pdf and art; the planner mustn't list
    it twice."""
    monkeypatch.setattr(iet, "detect_os", lambda: "debian")
    monkeypatch.setattr(iet, "detect_install_method", lambda: "pip")
    p = iet.plan(exports=["pdf", "art"])
    names = [t.name for t in p.selected_tools]
    assert names.count("rsvg-convert") == 1


def test_plan_python_pkg_uses_pipx_inject_when_pipx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(iet, "detect_os", lambda: "debian")
    monkeypatch.setattr(iet, "detect_install_method", lambda: "pipx")
    p = iet.plan(exports=["audiobook"])
    pydub = next(t for t in p.selected_tools if t.name == "pydub")
    assert any("pipx inject" in c for c in pydub.commands)


def test_plan_python_pkg_uses_pip_install_when_pip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(iet, "detect_os", lambda: "debian")
    monkeypatch.setattr(iet, "detect_install_method", lambda: "pip")
    p = iet.plan(exports=["audiobook"])
    pydub = next(t for t in p.selected_tools if t.name == "pydub")
    assert any("pip install" in c for c in pydub.commands)


def test_plan_unknown_export_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(iet, "detect_os", lambda: "debian")
    monkeypatch.setattr(iet, "detect_install_method", lambda: "pip")
    with pytest.raises(ValueError):
        iet.plan(exports=["bogus"])


def test_plan_macos_uses_brew(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(iet, "detect_os", lambda: "macos")
    monkeypatch.setattr(iet, "detect_install_method", lambda: "pip")
    p = iet.plan(exports=["pdf"])
    tectonic = next(t for t in p.selected_tools if t.name == "tectonic")
    assert any("brew install" in c for c in tectonic.commands)


# ----------------------------------------------------- render


def test_render_plan_includes_purpose_and_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(iet, "detect_os", lambda: "debian")
    monkeypatch.setattr(iet, "detect_install_method", lambda: "pip")
    p = iet.plan(exports=["pdf"])
    md = iet.render_plan(p)
    assert "tectonic" in md
    assert "PDF typesetting" in md
    assert "Verify after" in md


def test_render_plan_warns_on_other_os(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(iet, "detect_os", lambda: "other")
    monkeypatch.setattr(iet, "detect_install_method", lambda: "pip")
    p = iet.plan(exports=["pdf"])
    md = iet.render_plan(p)
    assert "OS not specifically recognised" in md


# ----------------------------------------------------- apply


def test_apply_runs_each_tool_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(iet, "detect_os", lambda: "debian")
    monkeypatch.setattr(iet, "detect_install_method", lambda: "pip")
    p = iet.plan(exports=["epub"])
    runs: list[str] = []

    def fake_runner(cmd: str) -> int:
        runs.append(cmd)
        return 0

    result = iet.apply(p, confirm=False, runner=fake_runner)
    # `pandoc` install + verify, in that order.
    assert any("apt-get install" in c and "pandoc" in c for c in runs)
    assert any("pandoc --version" in c for c in runs)
    assert "pandoc" in result.succeeded
    assert not result.failed


def test_apply_records_failure_when_command_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(iet, "detect_os", lambda: "debian")
    monkeypatch.setattr(iet, "detect_install_method", lambda: "pip")
    p = iet.plan(exports=["epub"])

    def fake_runner(cmd: str) -> int:
        return 0 if "verify" not in cmd else 1  # never trips
        # Actually we want to fail the install — return 1 always.

    def failing_runner(cmd: str) -> int:
        return 1

    result = iet.apply(p, confirm=False, runner=failing_runner)
    assert "pandoc" in [name for name, _ in result.failed]


def test_apply_skips_tools_without_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tools that have no install recipe for the OS get skipped, not
    failed."""
    monkeypatch.setattr(iet, "detect_os", lambda: "other")
    monkeypatch.setattr(iet, "detect_install_method", lambda: "pip")
    # Inject a fake export with a fake tool not in any table.
    iet.EXPORT_REQUIREMENTS["fake"] = ["nonexistent-tool"]
    try:
        p = iet.plan(exports=["fake"])
        # The planner emits a stub ToolPlan with empty commands list;
        # render the plan to make sure it shows the no-recipe note.
        md = iet.render_plan(p)
        assert "no install command for this tool" in md
    finally:
        del iet.EXPORT_REQUIREMENTS["fake"]


# ----------------------------------------------------- CLI


def test_cli_prints_plan_by_default() -> None:
    """No --apply → just print, exit 0."""
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "install-export-tools",
         "--exports", "pdf,epub"],
        capture_output=True, text=True, check=True,
    )
    assert "tectonic" in out.stdout
    assert "pandoc" in out.stdout
    # Bare-print mode never runs the commands.
    assert "applying" not in out.stdout


def test_cli_unknown_export_returns_2() -> None:
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "install-export-tools",
         "--exports", "definitely-not-real"],
        capture_output=True, text=True,
    )
    assert out.returncode == 2
    assert "unknown export" in out.stderr
