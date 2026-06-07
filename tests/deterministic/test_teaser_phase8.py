"""Tier-1 tests for movie-teaser Phase 8: mixed assembly + burn-in cards.

A real teaser is mostly static keyframes with a few dynamic video shots
woven in. ``kind="mixed"`` picks, per shot, the video clip if present
(native audio, trimmed) else the still keyframe (held, silent), normalized
to one WxH/AAC so concat works. ``--burn-titles`` draws the text cards into
the picture (opt-in; title-role centered/large, others lower-third), faded
over each segment.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from autonovel.teaser import assemble as asm
from autonovel.teaser.assemble import CutEntry, CutList, build_cut_list
from autonovel.teaser.shots import Shot, Teaser


def _run(*argv):
    return subprocess.run([sys.executable, "-m", "autonovel.mechanical", *argv],
                          capture_output=True, text=True)


def _cmd(cl: CutList) -> str:
    return asm.ffmpeg_command_str(cl, "out.mp4")


# ----------------------------- mixed model -------------------------------


def test_media_kind_resolution() -> None:
    assert CutEntry("01", "a.mp4", media="video").media_kind("mixed") == "video"
    assert CutEntry("01", "a.png", media="image").media_kind("mixed") == "image"
    assert CutEntry("01", "a.png").media_kind("image") == "image"
    assert CutEntry("01", "a.mp4").media_kind("video") == "video"
    assert CutEntry("01", "a.png").media_kind("mixed") == "image"  # fallback


def test_build_cut_list_mixed_prefers_video(tmp_path: Path) -> None:
    clips = tmp_path / "clips"
    clips.mkdir()
    (clips / "shot_01.mp4").write_bytes(b"v")   # dynamic
    (clips / "shot_02.png").write_bytes(b"i")   # static only
    (clips / "shot_03.mp4").write_bytes(b"v")
    t = Teaser(title="T", shots=[
        Shot(id="01", role="hook", duration_s=4, text_card="open"),
        Shot(id="02", role="escalation", duration_s=3),
        Shot(id="03", role="title", duration_s=4, text_card="THE TITLE"),
    ])
    cut, missing = build_cut_list(t, clips, kind="mixed")
    media = {e.shot_id: e.media for e in cut.entries}
    assert media == {"01": "video", "02": "image", "03": "video"}
    assert not missing
    # title role → title card_kind
    assert next(e for e in cut.entries if e.shot_id == "03").card_kind == "title"
    assert cut.has_clip_audio()  # has video segments


def test_ffmpeg_mixed_silence_and_concat() -> None:
    cl = CutList(title="T", kind="mixed", audio_bed="bed.mp3", entries=[
        CutEntry("01", "shot_01.mp4", duration_s=4, media="video"),
        CutEntry("02", "shot_02.png", duration_s=3, media="image"),
    ])
    s = _cmd(cl)
    assert "-loop 1 -t 3 -i shot_02.png" in s     # still held
    assert "-i shot_01.mp4" in s                    # video plain input
    assert "anullsrc" in s                          # silence for the still
    assert "concat=n=2:v=1:a=1" in s
    assert "sidechaincompress" in s                 # bed ducks under (auto→duck)


def test_ffmpeg_mixed_no_bed_keeps_clip_audio() -> None:
    cl = CutList(title="T", kind="mixed", entries=[
        CutEntry("01", "a.mp4", duration_s=4, media="video"),
        CutEntry("02", "b.png", duration_s=3, media="image"),
    ])
    s = _cmd(cl)
    assert "concat=n=2:v=1:a=1" in s
    assert "[aclip]" in s


# ----------------------------- burn titles -------------------------------


def test_burn_titles_drawtext() -> None:
    cl = CutList(title="T", kind="image", burn_titles=True,
                 font_file="/fonts/EBGaramond.ttf", entries=[
                     CutEntry("01", "a.png", duration_s=4, text_card="In a city built on debt"),
                     CutEntry("T", "t.png", duration_s=4, text_card="THE LEDGER", card_kind="title"),
                 ])
    s = _cmd(cl)
    assert s.count("drawtext") == 2
    assert "EBGaramond" in s
    assert "In a city built on debt" in s
    assert "alpha=" in s  # fade ramp


def test_burn_titles_off_by_default() -> None:
    cl = CutList(title="T", kind="image", entries=[
        CutEntry("01", "a.png", duration_s=4, text_card="card")])
    assert "drawtext" not in _cmd(cl)


def test_drawtext_escapes_apostrophe_and_colon() -> None:
    cl = CutList(title="T", kind="image", burn_titles=True, entries=[
        CutEntry("01", "a.png", duration_s=4, text_card="It's 9:15 — run")])
    s = _cmd(cl)
    assert "It’s 9\\:15" in s        # apostrophe swapped, colon escaped
    assert "It's" not in s


def test_cutlist_round_trips_mixed_fields() -> None:
    cl = CutList(title="T", kind="mixed", burn_titles=True, font_file="/f.ttf",
                 entries=[CutEntry("01", "a.mp4", media="video", card_kind="title",
                                   text_card="X")])
    back = CutList.from_dict(cl.to_dict())
    assert back.kind == "mixed" and back.burn_titles and back.font_file == "/f.ttf"
    assert back.entries[0].media == "video" and back.entries[0].card_kind == "title"


# ------------------------------- CLI -------------------------------------


def test_cli_cut_list_mixed_and_burn(tmp_path: Path) -> None:
    from autonovel.teaser import shots as shots_mod
    base = tmp_path / "teaser"
    (base / "clips").mkdir(parents=True)
    (base / "clips" / "shot_01.mp4").write_bytes(b"v")
    (base / "clips" / "shot_02.png").write_bytes(b"i")
    t = Teaser(title="My Teaser", shots=[
        Shot(id="01", role="hook", duration_s=4, text_card="open"),
        Shot(id="02", role="title", duration_s=4, text_card="TITLE"),
    ])
    tp = base / "teaser.json"
    shots_mod.dump(t, tp)
    out = _run("teaser-cut-list", str(tp), "--kind", "mixed", "--burn-titles",
               "--format", "json")
    assert out.returncode == 0, out.stderr
    cl = asm.load(base / "cut_list.json")
    assert cl.kind == "mixed" and cl.burn_titles
    assert {e.shot_id: e.media for e in cl.entries} == {"01": "video", "02": "image"}
