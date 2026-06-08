"""Tier-1 tests for `--fresh` teaser reset (2026-06-07).

A clean run from the top should archive every teaser artifact EXCEPT the
approved reference images (refs/, refs.yaml) — non-destructively (moved to
teaser/reset-archive/), so nothing is lost and the expensive hand-approved
references survive.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from autonovel.teaser import takes


def _populate(tdir: Path) -> None:
    tdir.mkdir(parents=True)
    (tdir / "beats.md").write_text("beats", encoding="utf-8")
    (tdir / "teaser.json").write_text("{}", encoding="utf-8")
    (tdir / "critique.md").write_text("c", encoding="utf-8")
    (tdir / "cut_list.json").write_text("{}", encoding="utf-8")
    (tdir / "shots").mkdir()
    (tdir / "shots" / "shot_01.md").write_text("s", encoding="utf-8")
    (tdir / "clips").mkdir()
    (tdir / "clips" / "shot_01.png").write_bytes(b"\x89PNG")
    # the keepers
    (tdir / "refs").mkdir()
    (tdir / "refs" / "jakob_ref.png").write_bytes(b"\x89PNG")
    (tdir / "refs.yaml").write_text("subjects: []", encoding="utf-8")


def test_reset_keeps_refs_archives_rest(tmp_path: Path) -> None:
    tdir = tmp_path / "teaser"
    _populate(tdir)
    rep = takes.reset_teaser(tdir, when=datetime(2026, 6, 7, 9, 0, 0))
    # refs survive in place
    assert (tdir / "refs" / "jakob_ref.png").exists()
    assert (tdir / "refs.yaml").exists()
    assert set(rep["kept"]) == {"refs", "refs.yaml"}
    # everything else moved out of the top level
    for gone in ("beats.md", "teaser.json", "critique.md", "cut_list.json",
                 "shots", "clips"):
        assert not (tdir / gone).exists(), gone
        assert gone in rep["archived"]
    # ...into reset-archive/<UTC>/
    arch = tdir / "reset-archive" / "20260607_090000"
    assert (arch / "beats.md").read_text() == "beats"
    assert (arch / "clips" / "shot_01.png").exists()


def test_reset_is_noop_on_missing_dir(tmp_path: Path) -> None:
    rep = takes.reset_teaser(tmp_path / "nope")
    assert rep == {"kept": [], "archived": []}


def test_reset_only_refs_present_archives_nothing(tmp_path: Path) -> None:
    tdir = tmp_path / "teaser"
    (tdir / "refs").mkdir(parents=True)
    (tdir / "refs.yaml").write_text("x", encoding="utf-8")
    rep = takes.reset_teaser(tdir)
    assert rep["archived"] == []
    assert set(rep["kept"]) == {"refs", "refs.yaml"}


def test_reset_archive_dir_itself_is_kept(tmp_path: Path) -> None:
    # a second reset must not nest the prior archive inside the new one
    tdir = tmp_path / "teaser"
    _populate(tdir)
    takes.reset_teaser(tdir, when=datetime(2026, 6, 7, 9, 0, 0))
    (tdir / "beats.md").write_text("beats2", encoding="utf-8")
    rep = takes.reset_teaser(tdir, when=datetime(2026, 6, 7, 10, 0, 0))
    assert "reset-archive" not in rep["archived"]
    assert (tdir / "reset-archive" / "20260607_090000" / "beats.md").exists()
    assert (tdir / "reset-archive" / "20260607_100000" / "beats.md").read_text() == "beats2"


def test_cli_reset_dry_run_and_apply(tmp_path: Path) -> None:
    tdir = tmp_path / "teaser"
    _populate(tdir)

    def run(*a):
        return subprocess.run([sys.executable, "-m", "autonovel.mechanical", *a],
                              capture_output=True, text=True)

    dry = run("teaser-reset", str(tdir), "--dry-run")
    assert dry.returncode == 0
    payload = json.loads(dry.stdout)
    assert "beats.md" in payload["would_archive"] and (tdir / "beats.md").exists()
    # accepts a teaser.json path too
    out = run("teaser-reset", str(tdir / "teaser.json"), "--format", "json")
    assert out.returncode == 0
    assert (tdir / "refs.yaml").exists() and not (tdir / "beats.md").exists()
