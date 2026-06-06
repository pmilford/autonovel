"""Tier-1 tests for movie-teaser Phase 3: the cut-list model + the
ffmpeg command planner.

Plan-only — ffmpeg is never executed (the command body runs it via bash,
like audiobook-assemble). Pure construction + filesystem facts.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel.teaser import assemble
from autonovel.teaser import shots as shots_mod
from autonovel.teaser.shots import Shot, Teaser


def _shot(**kw) -> Shot:
    base = dict(id="01a", role="hook", duration_s=5.0, subject_name="JAKOB",
                subject_appearance="x", action="y")
    base.update(kw)
    return Shot(**base)


def _run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", *argv],
        capture_output=True, text=True,
    )


# ----------------------------- build cut list ----------------------------


def test_build_cut_list_skips_missing_clips(tmp_path: Path) -> None:
    clips = tmp_path / "clips"
    clips.mkdir()
    (clips / "shot_01a.png").write_bytes(b"x")
    # 02b has no clip on disk.
    t = Teaser(title="My Teaser", shots=[
        _shot(id="01a", duration_s=5.0),
        _shot(id="02b", role="button", duration_s=3.0),
    ])
    cut, missing = assemble.build_cut_list(t, clips, kind="image")
    assert [e.shot_id for e in cut.entries] == ["01a"]
    assert missing == ["02b"]
    assert cut.total_duration_s() == 5.0
    assert cut.title == "My Teaser"


def test_cut_list_round_trip(tmp_path: Path) -> None:
    cut = assemble.CutList(title="X", kind="image", audio_bed="music.mp3",
                           entries=[assemble.CutEntry("01a", "clips/shot_01a.png", 5.0,
                                                      text_card="They told us it was over.")])
    p = tmp_path / "cut_list.json"
    assemble.dump(cut, p)
    back = assemble.load(p)
    assert back.title == "X"
    assert back.audio_bed == "music.mp3"
    assert back.entries[0].text_card == "They told us it was over."


def test_load_rejects_non_object(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("[1,2,3]", encoding="utf-8")
    with pytest.raises(ValueError, match="top level must be a JSON object"):
        assemble.load(p)


# ----------------------------- ffmpeg planner ----------------------------


def _cut(**kw) -> assemble.CutList:
    base = dict(title="X", kind="image", width=854, height=480, fps=30,
                entries=[assemble.CutEntry("01a", "clips/shot_01a.png", 5.0),
                         assemble.CutEntry("02b", "clips/shot_02b.png", 3.0)])
    base.update(kw)
    return assemble.CutList(**base)


def test_ffmpeg_command_image_slideshow() -> None:
    argv = assemble.ffmpeg_command(_cut(), "out.mp4")
    s = " ".join(argv)
    assert argv[0] == "ffmpeg"
    assert argv.count("-loop") == 2          # one per still
    assert "-t 5" in s and "-t 3" in s        # per-clip hold
    assert "concat=n=2:v=1:a=0[v]" in s
    assert "-map" in argv and "[v]" in argv
    assert "libx264" in s and "yuv420p" in s
    assert argv[-1] == "out.mp4"


def test_ffmpeg_command_video_uses_trim_not_loop() -> None:
    argv = assemble.ffmpeg_command(_cut(kind="video"), "out.mp4")
    s = " ".join(argv)
    assert "-loop" not in argv                # video clips aren't looped
    assert "trim=0:5" in s and "setpts=PTS-STARTPTS" in s


def test_ffmpeg_command_audio_bed_maps_and_shortens() -> None:
    argv = assemble.ffmpeg_command(_cut(audio_bed="music.mp3"), "out.mp4")
    s = " ".join(argv)
    assert "-i music.mp3" in s
    assert "-map 2:a" in s                    # audio is input index n (=2)
    assert "-shortest" in argv


def test_ffmpeg_command_empty_raises() -> None:
    with pytest.raises(ValueError, match="no entries"):
        assemble.ffmpeg_command(_cut(entries=[]), "out.mp4")


def test_ffmpeg_command_str_is_quoted() -> None:
    cut = _cut(entries=[assemble.CutEntry("01a", "a b/shot 01a.png", 5.0)])
    cmd = assemble.ffmpeg_command_str(cut, "out file.mp4")
    assert "'a b/shot 01a.png'" in cmd        # shlex-quoted spaces
    assert "'out file.mp4'" in cmd


# ------------------------------- CLI -------------------------------------


def test_cli_cut_list_and_ffmpeg_cmd(tmp_path: Path) -> None:
    clips = tmp_path / "clips"
    clips.mkdir()
    (clips / "shot_01a.png").write_bytes(b"x")
    t = Teaser(title="My Teaser", shots=[_shot(id="01a", duration_s=5.0)])
    tp = tmp_path / "teaser.json"
    shots_mod.dump(t, tp)

    out = _run("teaser-cut-list", str(tp), "--format", "json")
    assert out.returncode == 0
    data = json.loads(out.stdout)
    assert data["entries"] == 1
    cut_path = tmp_path / "cut_list.json"
    assert cut_path.exists()

    out2 = _run("teaser-ffmpeg-cmd", str(cut_path), "--format", "json")
    assert out2.returncode == 0
    d2 = json.loads(out2.stdout)
    assert d2["command"].startswith("ffmpeg")
    assert d2["out"].endswith("my_teaser_teaser.mp4")


def test_cli_cut_list_errors_when_no_clips(tmp_path: Path) -> None:
    t = Teaser(title="X", shots=[_shot(id="01a")])
    tp = tmp_path / "teaser.json"
    shots_mod.dump(t, tp)
    out = _run("teaser-cut-list", str(tp))
    assert out.returncode == 2  # no clips on disk → actionable error
    assert "render them first" in out.stderr
