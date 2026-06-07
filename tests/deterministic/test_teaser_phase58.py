"""Tier-1 tests for movie-teaser Phase 5.8: versioned takes.

Re-rendering never overwrites — each clip is archived under a monotonic
take number; an earlier take can be listed and promoted back to latest.
The assembled mp4 can be timestamped so a re-assemble keeps prior cuts.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from autonovel.teaser import takes as tk
from autonovel.teaser import shots as shots_mod
from autonovel.teaser.shots import Shot, Teaser


def _run(*argv):
    return subprocess.run([sys.executable, "-m", "autonovel.mechanical", *argv],
                          capture_output=True, text=True)


# ------------------------------ takes.py ---------------------------------


def test_parse_clip_name() -> None:
    assert tk.parse_clip_name(Path("shot_01a.png")) == ("01a", None, ".png")
    assert tk.parse_clip_name(Path("shot_01a_take3.mp4")) == ("01a", 3, ".mp4")


def test_archive_take_is_monotonic_and_never_overwrites(tmp_path) -> None:
    clips = tmp_path / "clips"
    clips.mkdir()
    takes = clips / "takes"
    src = clips / "shot_01.png"
    src.write_bytes(b"A")
    d1 = tk.archive_take(src, takes)
    assert d1.name == "shot_01_take1.png" and d1.read_bytes() == b"A"
    src.write_bytes(b"B")           # re-render → new bytes at the latest pointer
    d2 = tk.archive_take(src, takes)
    assert d2.name == "shot_01_take2.png" and d2.read_bytes() == b"B"
    assert d1.read_bytes() == b"A"  # earlier take untouched
    assert tk.next_take_number(takes, "01", "png") == 3


def test_list_and_promote(tmp_path) -> None:
    clips = tmp_path / "clips"
    takes = clips / "takes"
    takes.mkdir(parents=True)
    (takes / "shot_01_take1.png").write_bytes(b"first")
    (takes / "shot_01_take2.png").write_bytes(b"second")
    listing = tk.list_takes(takes)
    assert [t.take for t in listing["01"]] == [1, 2]
    # promote the earlier take back to latest
    dest = tk.promote_take(takes, clips, "01", 1)
    assert dest == clips / "shot_01.png" and dest.read_bytes() == b"first"


def test_promote_missing_raises(tmp_path) -> None:
    clips = tmp_path / "clips"
    (clips / "takes").mkdir(parents=True)
    try:
        tk.promote_take(clips / "takes", clips, "99", 1)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("expected FileNotFoundError")


# ------------------------- render archives takes -------------------------


def _stub_teaser(tmp_path):
    t = Teaser(title="My Teaser", provider="stub", shots=[
        Shot(id="01", role="hook", duration_s=4.0, aspect_ratio="16:9",
             shot_size="wide", subject_name="A", subject_appearance="x",
             action="y", setting="z", palette=["amber"])])
    p = tmp_path / "teaser.json"
    shots_mod.dump(t, p)
    return p


def test_render_archives_each_take(tmp_path) -> None:
    p = _stub_teaser(tmp_path)
    clips = tmp_path / "clips"
    # two stub renders → two archived takes, latest pointer overwritten
    for _ in range(2):
        out = _run("teaser-render", str(p), "--provider", "stub",
                   "--out-dir", str(clips), "--format", "json")
        assert out.returncode == 0
    data = json.loads(out.stdout)
    assert data["archived"] == 1
    takes = tk.list_takes(clips / "takes")
    assert [t.take for t in takes["01"]] == [1, 2]
    assert (clips / "shot_01.png").exists()  # latest pointer present


def test_render_no_archive_flag(tmp_path) -> None:
    p = _stub_teaser(tmp_path)
    clips = tmp_path / "clips"
    out = _run("teaser-render", str(p), "--provider", "stub",
               "--out-dir", str(clips), "--no-archive", "--format", "json")
    assert json.loads(out.stdout)["archived"] == 0
    assert not (clips / "takes").exists()


# ------------------------------- CLI -------------------------------------


def test_cli_takes_and_pick(tmp_path) -> None:
    p = _stub_teaser(tmp_path)
    clips = tmp_path / "clips"
    for _ in range(2):
        _run("teaser-render", str(p), "--provider", "stub", "--out-dir", str(clips))
    # list
    out = _run("teaser-takes", str(p), "--format", "json")
    data = json.loads(out.stdout)
    assert [t["take"] for t in data["shots"]["01"]] == [1, 2]
    # promote take 1
    out2 = _run("teaser-take-pick", str(p), "--shot", "01", "--take", "1",
                "--format", "json")
    assert json.loads(out2.stdout)["latest"].endswith("shot_01.png")


def test_ffmpeg_cmd_versioned_filename(tmp_path) -> None:
    from autonovel.teaser import assemble as asm
    cut = asm.CutList(title="My Teaser", kind="image",
                      entries=[asm.CutEntry("01", str(tmp_path / "shot_01.png"), 4.0)])
    cl = tmp_path / "cut_list.json"
    asm.dump(cut, cl)
    out = _run("teaser-ffmpeg-cmd", str(cl), "--versioned", "--format", "json")
    data = json.loads(out.stdout)
    assert re.search(r"my_teaser_teaser_\d{8}_\d{4}\.mp4$", data["out"])
    assert data["latest"].endswith("my_teaser_teaser_latest.mp4")
