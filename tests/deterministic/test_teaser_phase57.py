"""Tier-1 tests for movie-teaser Phase 5.7: scene transitions.

A transition vocabulary on the cut-list + concat-compatible fade emission,
safe auto-defaults (open fade-in / close fade-out / title fade), and an
advisory suggester that flags candidate transition points from structured
signals (time jumps, location changes, pace shifts). The artistic
placement remains the LLM's call in the command body.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.teaser import assemble as asm
from autonovel.teaser.assemble import CutEntry, CutList
from autonovel.teaser.shots import Shot, Teaser


def _fc(argv):
    return argv[argv.index("-filter_complex") + 1]


def _shot(sid, **kw):
    base = dict(id=sid, role="escalation", duration_s=4.0, aspect_ratio="16:9",
                shot_size="wide", subject_name="JAKOB", subject_appearance="x",
                action="acts", setting="Augsburg", palette=["amber"])
    base.update(kw)
    return Shot(**base)


# ----------------------------- ffmpeg fades ------------------------------


def test_cut_has_no_fade() -> None:
    c = CutList(title="X", kind="image",
                entries=[CutEntry("01", "/c/01.png", 4.0)])  # transition=cut
    assert "fade=" not in _fc(asm.ffmpeg_command(c, "o.mp4"))


def test_fade_in_emitted() -> None:
    c = CutList(title="X", kind="image",
                entries=[CutEntry("01", "/c/01.png", 4.0, transition="fade")])
    assert "fade=t=in:st=0:d=0.5" in _fc(asm.ffmpeg_command(c, "o.mp4"))


def test_fade_out_emitted_at_clip_end() -> None:
    c = CutList(title="X", kind="image",
                entries=[CutEntry("01", "/c/01.png", 4.0, fade_out=True)])
    assert "fade=t=out:st=3.5:d=0.5" in _fc(asm.ffmpeg_command(c, "o.mp4"))


def test_fade_clamped_to_half_clip() -> None:
    c = CutList(title="X", kind="image",
                entries=[CutEntry("01", "/c/01.png", 0.6, transition="fade",
                                  fade_out=True, transition_dur=2.0)])
    fc = _fc(asm.ffmpeg_command(c, "o.mp4"))
    assert "fade=t=in:st=0:d=0.3" in fc          # clamped to dur/2
    assert "fade=t=out:st=0.3:d=0.3" in fc


def test_dissolve_degrades_to_fade_in_v1() -> None:
    c = CutList(title="X", kind="image",
                entries=[CutEntry("01", "/c/01.png", 4.0, transition="dissolve")])
    assert "fade=t=in:st=0" in _fc(asm.ffmpeg_command(c, "o.mp4"))


# ------------------------- build_cut_list defaults -----------------------


def test_build_cut_list_default_transitions(tmp_path) -> None:
    clips = tmp_path / "clips"
    clips.mkdir()
    for sid in ("01", "02", "03"):
        (clips / f"shot_{sid}.png").write_bytes(b"x")
    t = Teaser(title="X", provider="grok", shots=[
        _shot("01", role="hook"), _shot("02", role="title"), _shot("03", role="button")])
    cut, _ = asm.build_cut_list(t, clips, kind="image")
    by = {e.shot_id: e for e in cut.entries}
    assert by["01"].transition == "fade"   # open fades in
    assert by["02"].transition == "fade"   # title fades
    assert by["03"].fade_out is True       # close fades out


def test_build_cut_list_transitions_off(tmp_path) -> None:
    clips = tmp_path / "clips"
    clips.mkdir()
    (clips / "shot_01.png").write_bytes(b"x")
    t = Teaser(title="X", provider="grok", shots=[_shot("01", role="hook")])
    cut, _ = asm.build_cut_list(t, clips, kind="image", transitions=False)
    assert cut.entries[0].transition == "cut" and cut.entries[0].fade_out is False


def test_cutentry_transition_round_trip(tmp_path) -> None:
    c = CutList(title="X", entries=[CutEntry("01", "/c/01.png", 4.0,
               transition="dissolve", fade_out=True, transition_dur=1.0)])
    p = tmp_path / "cut_list.json"
    asm.dump(c, p)
    e = asm.load(p).entries[0]
    assert e.transition == "dissolve" and e.fade_out is True and e.transition_dur == 1.0


# ------------------------------ suggester --------------------------------


def test_suggest_time_jump_and_location_and_pace() -> None:
    t = Teaser(title="X", provider="grok", shots=[
        _shot("01", role="hook", story_year=1500, setting="Augsburg", duration_s=2.0),
        _shot("02", story_year=1500, setting="Augsburg", duration_s=2.0),     # no change
        _shot("03", story_year=1512, setting="Augsburg", duration_s=2.0),     # time jump
        _shot("04", story_year=1512, setting="Rome", duration_s=2.0),         # location
        _shot("05", role="button", story_year=1512, setting="Rome", duration_s=4.0),  # pace+beat
    ])
    sugg = asm.suggest_transitions(t)
    reasons_into = lambda sid: [r for s in sugg if s.into_shot == sid for r in s.reasons]
    kinds_into = lambda sid: {s.suggested for s in sugg if s.into_shot == sid}
    assert any("open" in r for r in reasons_into("01")) and "fade" in kinds_into("01")
    assert reasons_into("02") == []                          # nothing changed
    assert any("time jump" in r for r in reasons_into("03"))
    assert any("location change" in r for r in reasons_into("04"))
    assert "dissolve" in kinds_into("04")
    assert any("pace slows" in r or "beat shift" in r for r in reasons_into("05"))
    assert "fade-out" in kinds_into("05")                    # last shot also closes


def test_suggest_empty_teaser() -> None:
    assert asm.suggest_transitions(Teaser(title="X", shots=[])) == []


# ------------------------------- CLI -------------------------------------


def test_cli_teaser_transitions(tmp_path) -> None:
    from autonovel.teaser import shots as sm
    t = Teaser(title="X", provider="grok", shots=[
        _shot("01", role="hook", story_year=1500, setting="Augsburg"),
        _shot("02", role="button", story_year=1520, setting="Rome")])
    p = tmp_path / "teaser.json"
    sm.dump(t, p)
    out = subprocess.run([sys.executable, "-m", "autonovel.mechanical",
                          "teaser-transitions", str(p), "--format", "json"],
                         capture_output=True, text=True)
    data = json.loads(out.stdout)
    sugg = data["suggestions"]
    assert any(s["into_shot"] == "01" and s["suggested"] == "fade" for s in sugg)
    assert any(s["into_shot"] == "02" and any("time jump" in r for r in s["reasons"])
               for s in sugg)
