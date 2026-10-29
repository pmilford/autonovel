"""Tier-1 tests for the film stage F4 helpers: the keyframe render loop and
its verdicts (a fake ComfyUI client; no GPU), the table read (a stand-in
engine script; no voice model) and the animatic (ffmpeg, skipped when it is
not installed).

What they lock: takes are never overwritten and the manifest is saved per
frame; the server's models are freed at the end; a frame is regenerated at
most twice before it goes to the author; a voice without a consent line is
refused; a line is voiced again only when its words or its voice change;
the animatic holds each still for its shot's computed duration and places
each line where the shot list says.
"""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
import sys
import wave
import zlib
from pathlib import Path

import pytest

from autonovel.film import animatic as an
from autonovel.film import comfy
from autonovel.film import storyboard as sb
from autonovel.film import table_read as tr
from autonovel.mechanical.__main__ import main as mech_main

SCRIPT = """Title: The Crossing
Roles:
    FERRYMAN

EXT. RIVER - NIGHT

= S0101 | ch_01:5-7 | stranded -> across

SUPER: THE RIVER. 1473.

Black water. A ferry comes out of the dark, a lantern at its bow.

ANA
How far is it?

FERRYMAN
Far enough. Get in.
"""


def png_bytes(w: int = 64, h: int = 36, rgb=(40, 30, 20)) -> bytes:
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def write_wav(path: Path, seconds: float, rate: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))


@pytest.fixture()
def film(tmp_path: Path) -> Path:
    book = tmp_path / "s" / "books" / "b"
    (book / "chapters").mkdir(parents=True)
    f = book / "film"
    for d in ("screenplay", "shots", "storyboard", "bible/sheets", "audio"):
        (f / d).mkdir(parents=True)
    (f / "screenplay" / "seq_01.fountain").write_text(SCRIPT, encoding="utf-8")
    return f


# --------------------------------------------------------------- the render loop

class FakeClient(comfy.Client):
    def __init__(self, up=True, fail=()):
        super().__init__(url="http://fake")
        self._up, self._fail = up, set(fail)
        self.queued, self.uploads, self.freed = [], [], 0

    def up(self):
        return {"system": {}} if self._up else None

    def upload_image(self, path):
        self.uploads.append(path.name)
        return f"up_{path.name}"

    def queue(self, workflow):
        self.queued.append(workflow)
        return str(len(self.queued))

    def wait(self, prompt_id):
        wf = self.queued[int(prompt_id) - 1]
        prefix = next((n["inputs"].get("filename_prefix", "") for n in wf.values()
                       if n["class_type"] in ("SaveImage", "SaveAudio")), "")
        if any(f in prefix for f in self._fail):
            raise comfy.ComfyError("boom")
        key = "audio" if any(n["class_type"] == "SaveAudio" for n in wf.values()) else "images"
        return {"10": {key: [{"filename": "x", "subfolder": "", "type": "output"}]}}

    def fetch_images(self, outputs, key="images"):
        return [png_bytes()] if key == "images" else [b"fLaC fake"]

    def free(self):
        self.freed += 1
        return True


def sheet(film: Path) -> Path:
    p = film / "bible" / "sheets" / "ana.json"
    p.write_text(json.dumps({"schema": sb.SCHEMA, "kind": "sheet", "subject": "ana", "size": [64, 80], "frames": [
        {"id": "front", "prompt": "a woman", "refs": [], "seed": 1, "status": "pending"},
        {"id": "profile", "prompt": "the same woman in profile", "refs": ["bible/sheets/ana/front.png"],
         "seed": 2, "status": "pending"}]}), encoding="utf-8")
    return p


def test_render_writes_takes_selects_and_frees(film: Path) -> None:
    p = sheet(film)
    c = FakeClient()
    res = sb.render(p, client=c, progress=lambda m: None)
    assert res["ok"] and [r["id"] for r in res["rendered"]] == ["front", "profile"]
    assert (film / "bible/sheets/ana/front.png").is_file()
    assert (film / "bible/sheets/ana/takes/profile_t01.png").is_file()
    assert c.uploads == ["front.png"]             # the profile is made from the front
    assert "11" in c.queued[1] and "11" not in c.queued[0]   # ReferenceMultiLatent only with a reference
    assert c.freed == 1
    data = json.loads(p.read_text())
    assert all(f["status"] == "rendered" for f in data["frames"])
    assert data["render_log"][-1]["freed"] is True
    assert data["backend"]["kind"] == "comfyui"


def test_takes_are_never_overwritten_and_verdicts_limit_regeneration(film: Path) -> None:
    p = sheet(film)
    sb.render(p, client=FakeClient(), progress=lambda m: None)
    for n in (1, 2):
        r = sb.verdict(p, "front", "regenerate", f"wrong boots {n}", prompt=f"a woman, try {n}")
        assert r["status"] == "regenerate" and r["regenerations"] == n
        sb.render(p, client=FakeClient(), progress=lambda m: None)
    takes = sorted(x.name for x in (film / "bible/sheets/ana/takes").glob("front_t*.png"))
    assert takes == ["front_t01.png", "front_t02.png", "front_t03.png"]
    r = sb.verdict(p, "front", "regenerate", "still wrong")
    assert r["status"] == "author" and "the author decides" in r["note"]
    data = json.loads(p.read_text())
    front = data["frames"][0]
    assert front["prompt"] == "a woman, try 2" and front["seed"] == 3
    sb.verdict(p, "profile", "keep", "fine", take=1)
    best = sb.verdict(p, "front", "author", "the model cannot draw it; take 2 is the best", take=2)
    assert best["status"] == "author"
    assert (film / "bible/sheets/ana/front.png").read_bytes() == (film / "bible/sheets/ana/takes/front_t02.png").read_bytes()
    st = sb.status(p)
    assert st["ready"] and st["counts"] == {"author": 1, "keep": 1}


def test_render_reports_a_missing_server_and_bad_manifests(film: Path) -> None:
    p = sheet(film)
    res = sb.render(p, client=FakeClient(up=False), progress=lambda m: None)
    assert not res["ok"] and "no ComfyUI server" in res["errors"][0]
    bad = film / "storyboard" / "S0101.json"
    bad.write_text(json.dumps({"schema": sb.SCHEMA, "frames": [
        {"id": "S0101-01", "prompt": "", "refs": ["bible/sheets/nobody/front.png"]},
        {"id": "S0101-01", "prompt": "x", "status": "weird"}]}), encoding="utf-8")
    errs = sb.render(bad, client=FakeClient(), progress=lambda m: None)["errors"]
    assert any("no prompt" in e for e in errs) and any("repeats" in e for e in errs)
    assert any("nobody" in e for e in errs) and any("weird" in e for e in errs)


def test_a_failed_job_is_reported_and_the_rest_render(film: Path) -> None:
    p = sheet(film)
    res = sb.render(p, client=FakeClient(fail=("front",)), progress=lambda m: None)
    assert [f["id"] for f in res["failed"]] == ["front", "profile"]   # the profile needs the front
    assert not res["ok"]


def test_sound_cues_render_to_flac(film: Path) -> None:
    p = film / "audio" / "S0101.json"
    p.write_text(json.dumps({"schema": sb.SCHEMA, "kind": "sound", "frames": [
        {"id": "bed", "prompt": "water", "seconds": 5, "status": "pending"}]}), encoding="utf-8")
    c = FakeClient()
    sb.render(p, client=c, progress=lambda m: None)
    assert (film / "audio/S0101/bed.flac").is_file()
    assert any(n["class_type"] == "EmptyLatentAudio" and n["inputs"]["seconds"] == 5.0 for n in c.queued[0].values())


def test_keyframe_cli(film: Path, capsys) -> None:
    p = sheet(film)
    assert mech_main(["keyframe-render", str(p), "--dry-run"]) == 0
    assert "front" in capsys.readouterr().out
    assert mech_main(["keyframe-status", str(p)]) == 0
    assert "2 pending" in capsys.readouterr().out
    assert mech_main(["keyframe-verdict", str(p), "--frame", "nope", "--verdict", "keep", "--note", "x"]) == 1


def test_klein_workflow_shapes() -> None:
    wf = comfy.klein_workflow("p", width=1280, height=720, seed=5, refs=["a.png", "b.png"])
    assert wf["11"]["inputs"]["images.image1"] == ["201", 0]
    assert wf["8"]["inputs"]["positive"] == ["11", 0]
    assert comfy.klein_workflow("p", width=64, height=64, seed=1)["8"]["inputs"]["positive"] == ["5", 0]


# --------------------------------------------------------------- the table read

VOICES = """voices:
  ANA:
    character: bible/characters/ana.yaml
    design: "a young woman, a low calm voice"
    ref_text: "A plain sentence for the reference clip."
    ref: audio/voices/ana.wav
    consent: "synthetic: designed from the description"
  FERRYMAN:
    design: "an old man"
    ref_text: "Another plain sentence."
    ref: audio/voices/ferryman.wav
    consent: "synthetic"
lexicon:
  far: faar
names: [Ana]
"""

FAKE_ENGINE = r'''
import json, sys, wave, os
job = json.load(open(sys.argv[1]))
def w(path, secs):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000); f.writeframes(b"\0\0" * int(secs * 16000))
res = {"engine": "fake", "voices": {}, "lines": {}, "load_s": 0, "generation_s": 0}
for cue, v in job["voices"].items():
    if not os.path.exists(v["ref"]):
        w(v["ref"], 1.0); open(v["ref"][:-4] + ".txt", "w").write(v["ref_text"])
    res["voices"][cue] = {"ref": v["ref"], "made": None}
for ln in job["lines"]:
    w(ln["out"], 0.5 + 0.1 * len(ln["text"].split()))
    res["lines"][ln["id"]] = {"duration_s": round(0.5 + 0.1 * len(ln["text"].split()), 2), "attempts": 1,
                              "passed": True, "heard": ln["spoken"], "notes": [], "takes": []}
print("noise on stdout first")
print(json.dumps(res))
'''


def test_voices_need_consent_and_a_reference_sentence(film: Path) -> None:
    (film / "audio" / "voices.yaml").write_text(
        "voices:\n  ANA:\n    design: x\n    ref: audio/voices/ana.wav\n", encoding="utf-8")
    _, problems = tr.load_voices(film)
    assert any("consent" in p for p in problems) and any("ref_text" in p for p in problems)


def test_table_read_voices_once_and_again_only_on_change(film: Path, tmp_path: Path) -> None:
    (film / "audio" / "voices.yaml").write_text(VOICES, encoding="utf-8")
    eng = tmp_path / "fake_engine.py"
    eng.write_text(FAKE_ENGINE, encoding="utf-8")
    script = film / "screenplay" / "seq_01.fountain"
    res = tr.run(script, ["S0101"], film=film, python=sys.executable, engine=eng, progress=lambda m: None)
    assert res["ok"] and res["rendered"] == ["S0101-L01", "S0101-L02"]
    man = json.loads((film / "audio/table_read/manifest.json").read_text())
    assert man["lines"]["S0101-L01"]["spoken"] == "How faar is it?"      # the lexicon, voice only
    assert man["lines"]["S0101-L01"]["text"] == "How far is it?"
    assert man["voices"]["ANA"]["consent"].startswith("synthetic")
    again = tr.run(script, ["S0101"], film=film, python=sys.executable, engine=eng, progress=lambda m: None)
    assert again["rendered"] == [] and again["current"] == ["S0101-L01", "S0101-L02"]
    script.write_text(SCRIPT.replace("Far enough. Get in.", "Far enough. Sit."), encoding="utf-8")
    p = tr.plan(script, ["S0101"], film=film)
    assert p["todo"] == ["S0101-L02"]


def test_table_read_names_a_cue_with_no_voice(film: Path) -> None:
    (film / "audio" / "voices.yaml").write_text(VOICES.split("  FERRYMAN:")[0] + "lexicon: {}\n", encoding="utf-8")
    p = tr.plan(film / "screenplay" / "seq_01.fountain", ["S0101"], film=film)
    assert any("FERRYMAN has no voice" in x for x in p["problems"])


# --------------------------------------------------------------- the animatic

def shots_file(film: Path) -> Path:
    data = {"schema": "autonovel-film-shots/1", "scene_id": "S0101", "script": "screenplay/seq_01.fountain",
            "shots": [
                {"id": "S0101-01", "move": {"type": "push_in", "speed": "slow"}, "screen_direction": "away",
                 "beats": ["S0101-A01", "S0101-A02"], "lines": [], "duration_s": 2.0},
                {"id": "S0101-02", "move": {"type": "static"}, "lines": ["S0101-L01", "S0101-L02"],
                 "timing": {"lead_s": 0.4, "gap_s": 0.2}, "duration_s": 3.0}]}
    p = film / "shots" / "S0101.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def recorded(film: Path) -> None:
    lines = {}
    for lid, text, secs in (("S0101-L01", "How far is it?", 0.8), ("S0101-L02", "Far enough. Get in.", 1.1)):
        write_wav(film / "audio" / "table_read" / f"{lid}.wav", secs)
        lines[lid] = {"text": text, "file": f"audio/table_read/{lid}.wav", "duration_s": secs}
    (film / "audio" / "table_read" / "manifest.json").write_text(json.dumps({"lines": lines}), encoding="utf-8")


def test_animatic_plan_places_lines_and_supers(film: Path) -> None:
    p = shots_file(film)
    recorded(film)
    plan = an.plan_scene(p)
    assert [s["start"] for s in plan.shots] == [0.0, 2.0]
    assert plan.shots[0]["super"] == "THE RIVER. 1473."
    assert [(l["id"], l["start"]) for l in plan.lines] == [("S0101-L01", 2.4), ("S0101-L02", 3.4)]
    assert plan.duration_s == 5.0
    assert any("no storyboard" in x for x in plan.problems)


def test_animatic_plan_refuses_a_stale_recording(film: Path) -> None:
    p = shots_file(film)
    recorded(film)
    man = film / "audio" / "table_read" / "manifest.json"
    d = json.loads(man.read_text())
    d["lines"]["S0101-L02"]["text"] = "an older wording"
    man.write_text(json.dumps(d), encoding="utf-8")
    plan = an.plan_scene(p)
    assert [l["id"] for l in plan.lines] == ["S0101-L01"]
    assert any("S0101-L02" in x and "no current recording" in x for x in plan.problems)


def test_move_expressions() -> None:
    z, x, y = an._move_expr({"type": "push_in", "speed": "slow"}, "away", 49)
    assert z.startswith("1+0.06*") and "iw/2" in x
    z, x, _ = an._move_expr({"type": "pan"}, "right_to_left", 49)
    assert "(1+-1*" in x
    assert an._move_expr({"type": "static"}, None, 10)[0] == "1"


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="ffmpeg not installed")
def test_animatic_builds_in_sync(film: Path) -> None:
    p = shots_file(film)
    recorded(film)
    sel = film / "storyboard" / "S0101"
    sel.mkdir()
    (sel / "S0101-01.png").write_bytes(png_bytes(128, 72))
    (film / "storyboard" / "S0101.json").write_text(json.dumps({"schema": sb.SCHEMA, "frames": [
        {"id": "S0101-01", "select": "storyboard/S0101/S0101-01.png", "status": "keep", "prompt": "x"}]}),
        encoding="utf-8")
    res = an.build_scene(p, frames=True, progress=lambda m: None)
    assert res["ok"] and res["duration_s"] == 5.0
    out = Path(res["file"])
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_entries",
                            "stream=codec_type,nb_read_frames,width,height", "-of", "json", str(out)],
                           capture_output=True, text=True)
    streams = {s["codec_type"]: s for s in json.loads(probe.stdout)["streams"]}
    assert int(streams["video"]["nb_read_frames"]) == 120 and streams["video"]["width"] == 1280
    assert "audio" in streams
    cut = json.loads((film / "animatic" / "S0101.json").read_text())
    assert cut["shots"][0]["still"] == "storyboard/S0101/S0101-01.png"
    assert any("S0101-02: no keyframe" in x for x in cut["problems"])
    assert len(list((film / "animatic" / "S0101_frames").glob("*.jpg"))) == 2
    joined = an.join([out, out], film / "animatic" / "both.mp4")
    assert abs(joined["duration_s"] - 10.0) < 0.2
