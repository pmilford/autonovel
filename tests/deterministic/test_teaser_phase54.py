"""Tier-1 tests for movie-teaser Phase 5.4: audio-bed mixing in assembly.

Video clips with native dialogue/music keep their audio, and a music bed
**ducks under** the dialogue instead of replacing it. Pure ffmpeg-argv
planning (no execution), so we assert on the filtergraph + maps.
"""

from __future__ import annotations

from autonovel.teaser import assemble as asm
from autonovel.teaser.assemble import CutEntry, CutList


def _cut(kind="video", *, audio_bed=None, audio_mode="auto", clip_audio=None, n=2):
    return CutList(
        title="X", kind=kind, audio_bed=audio_bed, audio_mode=audio_mode,
        clip_audio=clip_audio,
        entries=[CutEntry(shot_id=f"{i:02d}", clip=f"/c/shot_{i:02d}."
                          + ("png" if kind == "image" else "mp4"),
                          duration_s=4.0) for i in range(1, n + 1)],
    )


def _fc(argv):
    """Return the -filter_complex string from an argv list."""
    return argv[argv.index("-filter_complex") + 1]


def _maps(argv):
    return [argv[i + 1] for i, a in enumerate(argv) if a == "-map"]


# --------------------------- mode resolution -----------------------------


def test_resolve_auto_modes() -> None:
    assert _cut("image").resolve_audio_mode() == "none"
    assert _cut("image", audio_bed="b.mp3").resolve_audio_mode() == "bed-only"
    assert _cut("video").resolve_audio_mode() == "clip-only"          # clips have audio
    assert _cut("video", audio_bed="b.mp3").resolve_audio_mode() == "duck"
    # explicit clip_audio=False (silent video, e.g. magichour)
    assert _cut("video", clip_audio=False, audio_bed="b.mp3").resolve_audio_mode() == "bed-only"
    assert _cut("video", clip_audio=False).resolve_audio_mode() == "none"


# ----------------------------- filtergraph -------------------------------


def test_image_slideshow_silent_by_default() -> None:
    argv = asm.ffmpeg_command(_cut("image"), "out.mp4")
    assert "concat=n=2:v=1:a=0[v]" in _fc(argv)
    assert _maps(argv) == ["[v]"]          # no audio map


def test_image_bed_only() -> None:
    argv = asm.ffmpeg_command(_cut("image", audio_bed="bed.mp3"), "out.mp4")
    assert "a=0[v]" in _fc(argv)
    assert _maps(argv) == ["[v]", "2:a"]  # bed input #2; raw stream → no brackets
    assert "-shortest" in argv


def test_video_clip_only_keeps_native_audio() -> None:
    argv = asm.ffmpeg_command(_cut("video"), "out.mp4")
    fc = _fc(argv)
    assert "concat=n=2:v=1:a=1[v][aclip]" in fc   # clip audio preserved
    assert _maps(argv) == ["[v]", "[aclip]"]
    assert "-shortest" not in argv                 # clip audio matches video length


def test_video_duck_bed_under_dialogue() -> None:
    argv = asm.ffmpeg_command(_cut("video", audio_bed="bed.mp3"), "out.mp4")
    fc = _fc(argv)
    assert "concat=n=2:v=1:a=1[v][aclip]" in fc
    assert "asplit=2[ak][am]" in fc
    assert "sidechaincompress=" in fc              # the bed ducks under dialogue
    assert "[bedduck]" in fc and "amix=inputs=2" in fc
    assert _maps(argv) == ["[v]", "[a]"]


def test_video_mix_mode() -> None:
    argv = asm.ffmpeg_command(_cut("video", audio_bed="bed.mp3", audio_mode="mix"), "out.mp4")
    fc = _fc(argv)
    assert "amix=inputs=2" in fc and "sidechaincompress" not in fc
    assert _maps(argv) == ["[v]", "[a]"]


def test_silent_video_with_bed_falls_back_to_bed_only() -> None:
    argv = asm.ffmpeg_command(
        _cut("video", clip_audio=False, audio_bed="bed.mp3"), "out.mp4")
    # No clip audio → concat stays a=0, bed is the only track.
    assert "a=0[v]" in _fc(argv)
    assert _maps(argv) == ["[v]", "2:a"]


def test_none_mode_is_silent() -> None:
    argv = asm.ffmpeg_command(_cut("video", audio_mode="none"), "out.mp4")
    assert _maps(argv) == ["[v]"]
    assert "a=0[v]" in _fc(argv)


# ------------------------------- round-trip ------------------------------


def test_cutlist_audio_fields_round_trip(tmp_path) -> None:
    c = _cut("video", audio_bed="bed.mp3", audio_mode="duck", clip_audio=True)
    p = tmp_path / "cut_list.json"
    asm.dump(c, p)
    back = asm.load(p)
    assert back.audio_mode == "duck" and back.clip_audio is True
    assert back.resolve_audio_mode() == "duck"


def test_build_cut_list_threads_audio_fields(tmp_path) -> None:
    from autonovel.teaser.shots import Shot, Teaser
    clips = tmp_path / "clips"
    clips.mkdir()
    (clips / "shot_01.mp4").write_bytes(b"v")
    t = Teaser(title="X", provider="grok", shots=[
        Shot(id="01", role="hook", duration_s=5.0, aspect_ratio="16:9",
             shot_size="wide", subject_name="A", subject_appearance="x",
             action="y", setting="z", palette=["amber"])])
    cut, _missing = asm.build_cut_list(t, clips, kind="video",
                                       audio_bed="bed.mp3", audio_mode="duck")
    assert cut.audio_mode == "duck" and cut.audio_bed == "bed.mp3"
