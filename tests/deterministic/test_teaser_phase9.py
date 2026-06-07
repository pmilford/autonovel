"""Tier-1 tests for movie-teaser Phase 9: music-generation backend.

A teaser can now score itself: `teaser-music` generates one cohesive bed
from a prompt (defaulting to the spine's `score_direction`), versioned, then
fed to `teaser-assemble --audio`. The `stub` provider writes a valid silent
WAV offline so the generate→assemble chain works for $0; real backends
(musicgen/elevenlabs) POST via an injectable client. A per-shot `audio.music`
cue is emitted only on the `native` score path.
"""

from __future__ import annotations

import json
import subprocess
import sys
import wave
from pathlib import Path

from autonovel.teaser import music
from autonovel.teaser.backends import RenderError
from autonovel.teaser.render_prompt import render_audio_for_prompt
from autonovel.teaser.shots import Shot, Spine, Teaser


def _run(*argv):
    return subprocess.run([sys.executable, "-m", "autonovel.mechanical", *argv],
                          capture_output=True, text=True)


# ------------------------------ stub bed ---------------------------------


def test_stub_writes_valid_silent_wav(tmp_path: Path) -> None:
    out = music.generate_bed("tense strings", tmp_path / "bed.wav",
                             provider="stub", duration_s=2)
    assert out.exists()
    with wave.open(str(out)) as w:
        assert w.getnchannels() == 2
        assert w.getframerate() == 44100
        assert w.getnframes() >= 44100 * 2 - 10  # ~2s


def test_stub_needs_no_key_and_default_prompt(tmp_path: Path) -> None:
    assert not music.needs_key("stub")
    out = music.generate_bed("", tmp_path / "b.wav", provider="stub", duration_s=0.5)
    assert out.exists()  # empty prompt → default, still writes


# --------------------------- real backends -------------------------------


class _Resp:
    def __init__(self, content=b"AUDIO", status=200):
        self.content = content
        self.status_code = status


class _Client:
    def __init__(self, resp):
        self.resp = resp
        self.calls = []

    def post(self, url, **kw):
        self.calls.append((url, kw))
        return self.resp


def test_musicgen_posts_and_writes(tmp_path: Path) -> None:
    c = _Client(_Resp(b"FLACDATA"))
    out = music.generate_bed("driving ostinato", tmp_path / "m.flac",
                             provider="musicgen", token="hf_x", client=c)
    assert out.read_bytes() == b"FLACDATA"
    assert "api-inference.huggingface.co" in c.calls[0][0]


def test_musicgen_auth_error(tmp_path: Path) -> None:
    c = _Client(_Resp(b"", status=401))
    try:
        music.generate_bed("x", tmp_path / "m.flac", provider="musicgen",
                            token="bad", client=c)
    except RenderError as e:
        assert e.kind == "auth"
    else:
        raise AssertionError("expected auth RenderError")


def test_missing_key_raises(tmp_path: Path, monkeypatch) -> None:
    for v in ("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        monkeypatch.delenv(v, raising=False)
    try:
        music.generate_bed("x", tmp_path / "m.flac", provider="musicgen")
    except RenderError as e:
        assert e.kind == "auth"
    else:
        raise AssertionError("expected auth RenderError for missing key")


# ----------------------- audio.music prompt line -------------------------


def test_audio_music_line_native_only() -> None:
    s = Shot(id="1", audio={"music": "driving string ostinato",
                            "dialogue": [{"speaker": "J", "line": "Now."}]})
    assert "Music: driving string ostinato" in render_audio_for_prompt(s, score="native")
    # on the bed/none paths the model must add no score → no Music line
    assert "Music:" not in render_audio_for_prompt(s, score="bed")
    assert "Music:" not in render_audio_for_prompt(s, score="none")


# ------------------------------- CLI -------------------------------------


def _teaser(tmp_path: Path) -> Path:
    from autonovel.teaser import shots as shots_mod
    t = Teaser(title="The Ledger", provider="veo",
               spine=Spine(score_direction="a single building string ostinato"),
               shots=[Shot(id="01", role="hook", action="a", subject_name="J",
                           subject_appearance="x")])
    p = tmp_path / "teaser.json"
    shots_mod.dump(t, p)
    return p


def test_cli_music_stub_defaults_to_spine(tmp_path: Path) -> None:
    p = _teaser(tmp_path)
    out = _run("teaser-music", str(p), "--provider", "stub", "--duration", "1",
               "--format", "json")
    assert out.returncode == 0, out.stderr
    payload = json.loads(out.stdout)
    assert payload["prompt"] == "a single building string ostinato"  # from spine
    assert Path(payload["out"]).exists() and Path(payload["latest"]).exists()
    assert payload["out"].endswith(".wav")


def test_cli_music_dry_run_reports_key(tmp_path: Path) -> None:
    p = _teaser(tmp_path)
    out = _run("teaser-music", str(p), "--provider", "musicgen", "--dry-run",
               "--format", "json")
    assert out.returncode == 0, out.stderr
    payload = json.loads(out.stdout)
    assert payload["needs_key"] is True
    assert payload["out"].endswith(".flac")


def test_cli_music_versioned_never_clobbers(tmp_path: Path) -> None:
    p = _teaser(tmp_path)
    a = _run("teaser-music", str(p), "--provider", "stub", "--duration", "1", "--format", "json")
    import time
    time.sleep(0.01)
    b = _run("teaser-music", str(p), "--provider", "stub", "--duration", "1", "--format", "json")
    # both timestamped beds + the latest pointer live under music/
    beds = list((tmp_path / "music").glob("the_ledger_bed_*.wav"))
    assert len([x for x in beds if "latest" not in x.name]) >= 1
    assert (tmp_path / "music" / "the_ledger_bed_latest.wav").exists()
