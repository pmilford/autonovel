"""The animatic: storyboard stills timed to the table read, with the shot
list's camera moves, the scene's sound under them, assembled with ffmpeg.

`autonovel mechanical animatic film/shots/<scene>.json [...] [--join NAME]`
is the mechanical half of `/autonovel:animatic`. For each scene it reads:

  - the shot list (`film/shots/<scene>.json`): order, each shot's duration
    (computed from its lines and action by `shot-check --retime`), its move,
    its lines and where they fall (`timing.lead_s`, `gap_s`);
  - the storyboard (`film/storyboard/<scene>.json`): each shot's select;
  - the table read (`film/audio/table_read/manifest.json`): each line's
    recording, used only while its text still matches the script;
  - the scene's sound cues (`film/audio/ambience/<scene>.json`, optional):
    beds laid under a run of shots, effects at a moment in a shot.

and writes `film/animatic/<scene>.mp4`, its cut list `<scene>.json` (every
shot's in and out, every line's start, every source with its fingerprint)
and, with `--frames`, one still per shot from the finished cut for the
viewer check. `--join` concatenates the scenes into `film/animatic/<NAME>.mp4`.

Moves are done on the still (CAMERA.md §9): a push or pull is a slow zoom,
a pan or tilt slides across a slightly enlarged frame, a drift or track adds
a small slide in the shot's screen direction; a static shot holds. The
still is enlarged first, so the move is smooth and not stepped. The frame
is letterboxed to the look's 1.85:1. Lines are levelled to one loudness and
the mix is normalised to -16 LUFS.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .shots import film_dir_of, line_offsets

FPS = 24
SIZE = (1280, 720)
ASPECT = 1.85
LINE_TARGET_DB = -20.0           # mean level each line is brought to before the mix [pipeline heuristic]
MIX_LUFS = -16.0
FONT_CANDIDATES = ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                   "/usr/share/fonts/dejavu/DejaVuSans.ttf",
                   "/Library/Fonts/Arial.ttf", "C:/Windows/Fonts/arial.ttf")
MOVE_AMOUNT = {"slow": 0.06, "medium": 0.12, "fast": 0.2}


@dataclass
class ScenePlan:
    scene_id: str
    shots: list[dict] = field(default_factory=list)      # id, start, dur, still, move, super, lines
    lines: list[dict] = field(default_factory=list)      # id, cue, text, file, start, dur
    cues: list[dict] = field(default_factory=list)       # id, file, start, end, gain_db, fade_s, kind
    duration_s: float = 0.0
    page_time_s: float = 0.0
    problems: list[str] = field(default_factory=list)
    sources: dict = field(default_factory=dict)


def _sha(p: Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg is not on PATH (install it with your package manager)")
    return exe


def _font() -> str | None:
    return next((f for f in FONT_CANDIDATES if Path(f).is_file()), None)


def plan_scene(shots_path: Path) -> ScenePlan:
    from ..mechanical import fountain as fountain_mod
    from .table_read import load_manifest
    film = film_dir_of(shots_path)
    data = json.loads(shots_path.read_text(encoding="utf-8"))
    sid = data.get("scene_id") or shots_path.stem
    plan = ScenePlan(scene_id=sid)
    script = film / (data.get("script") or "")
    bd = fountain_mod.scene_breakdown(script, sid) if script.is_file() else None
    if bd is None:
        plan.problems.append(f"scene {sid} not found in {data.get('script')}")
        return plan
    plan.page_time_s = bd["page_time_s"]
    texts = {ln["id"]: ln for ln in bd["lines"]}
    beats = {b["id"]: b["text"] for b in bd["beats"]}
    sb_path = film / "storyboard" / f"{sid}.json"
    try:
        frames = {f["id"]: f for f in json.loads(sb_path.read_text(encoding="utf-8")).get("frames", [])}
    except (OSError, json.JSONDecodeError):
        frames = {}
        plan.problems.append(f"no storyboard at {sb_path.relative_to(film)}: every shot is a card")
    man = load_manifest(film)
    recorded = man.get("lines") or {}
    line_s: dict[str, float] = {}
    for lid, ln in texts.items():
        rec = recorded.get(lid)
        if rec and rec.get("text") == ln["text"] and (film / rec["file"]).is_file():
            line_s[lid] = float(rec["duration_s"])
        else:
            plan.problems.append(f"{lid}: no current recording in the table read; run table-read first")
    pos = 0.0
    for shot in data.get("shots") or []:
        dur = float(shot.get("duration_s") or 0)
        if dur <= 0:
            plan.problems.append(f"{shot.get('id')}: no duration_s; run shot-check --retime")
            continue
        fr = frames.get(shot["id"]) or {}
        still = film / fr["select"] if fr.get("select") else None
        if still is None or not still.is_file():
            plan.problems.append(f"{shot['id']}: no keyframe; shown as a card")
            still = None
        sup = next((beats[b][len("SUPER:"):].strip() for b in shot.get("beats") or []
                    if beats.get(b, "").upper().startswith("SUPER:")), "")
        item = {"id": shot["id"], "start": round(pos, 3), "dur": dur,
                "still": str(still) if still else None, "status": fr.get("status"),
                "move": shot.get("move") or {"type": "static"}, "direction": shot.get("screen_direction"),
                "super": sup, "card": (shot.get("action") or "")[:200], "lines": []}
        for lid, off in line_offsets(shot, line_s):
            rec = recorded[lid]
            ln = {"id": lid, "cue": texts[lid]["cue"], "text": texts[lid]["text"], "file": str(film / rec["file"]),
                  "start": round(pos + off, 3), "dur": line_s[lid], "shot": shot["id"]}
            plan.lines.append(ln)
            item["lines"].append(lid)
        plan.shots.append(item)
        pos += dur
    plan.duration_s = round(pos, 3)
    starts = {s["id"]: s for s in plan.shots}
    amb_path = film / "audio" / "ambience" / f"{sid}.json"
    if amb_path.is_file():
        for cue in json.loads(amb_path.read_text(encoding="utf-8")).get("frames", []):
            place = cue.get("place") or {}
            sel = film / cue["select"] if cue.get("select") else None
            if sel is None or not sel.is_file():
                plan.problems.append(f"sound {cue.get('id')}: not rendered")
                continue
            if place.get("shots"):
                runs = [starts[s] for s in place["shots"] if s in starts]
                if not runs:
                    continue
                start, end = runs[0]["start"], runs[-1]["start"] + runs[-1]["dur"]
                plan.cues.append({"id": cue["id"], "file": str(sel), "start": start, "end": end, "kind": "bed",
                                  "gain_db": float(place.get("gain_db", -20)), "fade_s": float(place.get("fade_s", 1))})
            elif place.get("shot") in starts:
                s = starts[place["shot"]]
                plan.cues.append({"id": cue["id"], "file": str(sel), "start": s["start"] + float(place.get("at_s", 0)),
                                  "end": None, "kind": "fx", "gain_db": float(place.get("gain_db", -10)),
                                  "fade_s": 0.0})
    plan.sources = {"shots": _sha(shots_path), "storyboard": _sha(sb_path),
                    "table_read": _sha(film / "audio" / "table_read" / "manifest.json"),
                    "ambience": _sha(amb_path) if amb_path.is_file() else ""}
    return plan


# --------------------------------------------------------------- video

def _move_expr(move: dict, direction: str | None, frames: int) -> tuple[str, str, str]:
    """zoompan z, x, y expressions for a move on an enlarged still."""
    mtype = move.get("type") or "static"
    amt = MOVE_AMOUNT.get(move.get("speed") or "slow", 0.06)
    n = max(1, frames - 1)
    t = f"(on/{n})"
    centre_x, centre_y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    sign = -1 if (direction == "right_to_left" or move.get("direction") in ("left",)) else 1
    if mtype in ("push_in",):
        return f"1+{amt}*{t}", centre_x, centre_y
    if mtype in ("pull_out",):
        return f"1+{amt}-{amt}*{t}", centre_x, centre_y
    if mtype in ("pan", "track", "follow"):
        z = 1 + amt + 0.02
        return f"{z}", f"(iw-iw/zoom)*({0 if sign > 0 else 1}+{sign}*{t})", centre_y
    if mtype in ("tilt", "crane"):
        z = 1 + amt + 0.02
        up = move.get("direction") == "up"
        return f"{z}", centre_x, f"(ih-ih/zoom)*({1 if up else 0}{'-' if up else '+'}{t})"
    if mtype == "drift":
        if direction in ("away", "toward", "neutral", "static", None):
            return f"1+{amt * 0.6}*{t}", centre_x, centre_y
        z = 1 + amt * 0.6
        return f"{z}", f"(iw-iw/zoom)*(0.5+{sign}*0.5*{t})", centre_y
    return "1", centre_x, centre_y


def _escape(path: str) -> str:
    return path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def render_shot(item: dict, out: Path, tmp: Path, *, labels: bool, subtitles: bool, plan: ScenePlan) -> list[str]:
    W, H = SIZE
    # Whole frames from the cumulative timeline, so rounding never drifts.
    frames = max(1, round((item["start"] + item["dur"]) * FPS) - round(item["start"] * FPS))
    bar = max(0, round((H - W / ASPECT) / 2))
    font = _font()
    vf = []
    if item["still"]:
        z, x, y = _move_expr(item["move"], item["direction"], frames)
        src = ["-loop", "1", "-i", item["still"]]
        vf.append(f"scale={W * 4}:{H * 4}:flags=lanczos,setsar=1")
        vf.append(f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={FPS}")
    else:
        src = ["-f", "lavfi", "-i", f"color=c=0x101010:s={W}x{H}:r={FPS}"]
        if font:
            tf = tmp / f"{item['id']}_card.txt"
            tf.write_text("\n".join(_wrap(item["card"] or "(no keyframe)", 60)), encoding="utf-8")
            vf.append(f"drawtext=fontfile='{_escape(font)}':textfile='{_escape(str(tf))}':fontcolor=0xbbbbbb:"
                      f"fontsize=26:line_spacing=8:x=(w-text_w)/2:y=(h-text_h)/2")
    if bar:
        vf.append(f"drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill,drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill")
    if font and labels:
        vf.append(f"drawtext=fontfile='{_escape(font)}':text='{item['id']}':fontcolor=0x9a9a9a:fontsize=16:"
                  f"x=14:y=h-{max(bar, 8)}+({max(bar, 8)}-text_h)/2")
    if font and item["super"]:
        tf = tmp / f"{item['id']}_super.txt"
        tf.write_text(item["super"], encoding="utf-8")
        a, b = 0.6, max(0.8, item["dur"] - 0.6)
        vf.append(f"drawtext=fontfile='{_escape(font)}':textfile='{_escape(str(tf))}':fontcolor=0xe8e2d0:fontsize=30:"
                  f"x=(w-text_w)/2:y=h*0.72:enable='between(t,{a},{b})'")
    if font and subtitles:
        for ln in plan.lines:
            if ln["shot"] != item["id"]:
                continue
            tf = tmp / f"{ln['id']}_sub.txt"
            tf.write_text("\n".join(_wrap(ln["text"], 52)), encoding="utf-8")
            a = ln["start"] - item["start"]
            b = min(item["dur"], a + ln["dur"] + 0.3)
            vf.append(f"drawtext=fontfile='{_escape(font)}':textfile='{_escape(str(tf))}':fontcolor=white:fontsize=24:"
                      f"line_spacing=6:box=1:boxcolor=black@0.45:boxborderw=8:x=(w-text_w)/2:"
                      f"y=h-{bar}-text_h-24:enable='between(t,{a:.2f},{b:.2f})'")
    return [_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", *src, "-frames:v", str(frames),
            "-vf", ",".join(vf), "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-an", str(out)]


def _wrap(text: str, width: int) -> list[str]:
    import textwrap
    return textwrap.wrap(text, width) or [""]


# --------------------------------------------------------------- audio

def _mean_db(path: str) -> float | None:
    p = subprocess.run([_ffmpeg(), "-hide_banner", "-nostats", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", p.stderr)
    return float(m.group(1)) if m else None


def build_audio(plan: ScenePlan, out: Path) -> list[str]:
    inputs: list[str] = []
    chains: list[str] = []
    k = 0
    for ln in plan.lines:
        mean = _mean_db(ln["file"])
        gain = (LINE_TARGET_DB - mean) if mean is not None else 0.0
        inputs += ["-i", ln["file"]]
        chains.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,volume={gain:.1f}dB,"
                      f"adelay={int(ln['start'] * 1000)}:all=1[a{k}]")
        k += 1
    for cue in plan.cues:
        if cue["kind"] == "bed":
            length = cue["end"] - cue["start"]
            inputs += ["-stream_loop", "-1", "-i", cue["file"]]
            fade = min(cue["fade_s"], length / 3)
            chains.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{length:.3f},"
                          f"asetpts=PTS-STARTPTS,afade=t=in:d={fade:.2f},afade=t=out:st={length - fade:.3f}:d={fade:.2f},"
                          f"volume={cue['gain_db']}dB,adelay={int(cue['start'] * 1000)}:all=1[a{k}]")
        else:
            inputs += ["-i", cue["file"]]
            remain = max(0.5, plan.duration_s - cue["start"])
            chains.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{remain:.3f},"
                          f"volume={cue['gain_db']}dB,adelay={int(cue['start'] * 1000)}:all=1[a{k}]")
        k += 1
    if k == 0:
        return [_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                f"anullsrc=r=48000:cl=stereo", "-t", f"{plan.duration_s:.3f}", str(out)]
    mix = "".join(f"[a{i}]" for i in range(k))
    graph = ";".join(chains) + f";{mix}amix=inputs={k}:normalize=0:duration=longest,apad=whole_dur={plan.duration_s:.3f}," \
        f"atrim=0:{plan.duration_s:.3f},loudnorm=I={MIX_LUFS}:TP=-1.5:LRA=11,aresample=48000[mix]"
    return [_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", graph,
            "-map", "[mix]", "-c:a", "pcm_s16le", str(out)]


# --------------------------------------------------------------- assembly

def _run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"ffmpeg failed ({p.returncode}): {p.stderr[-1500:]}")


def build_scene(shots_path: Path, *, labels: bool = True, subtitles: bool = True, frames: bool = False,
                progress=print) -> dict:
    film = film_dir_of(shots_path)
    plan = plan_scene(shots_path)
    if not plan.shots:
        return {"ok": False, "scene": plan.scene_id, "problems": plan.problems}
    out_dir = film / "animatic"
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4 = out_dir / f"{plan.scene_id}.mp4"
    with tempfile.TemporaryDirectory(prefix="animatic_") as td:
        tmp = Path(td)
        clips = []
        for item in plan.shots:
            clip = tmp / f"{item['id']}.mp4"
            _run(render_shot(item, clip, tmp, labels=labels, subtitles=subtitles, plan=plan))
            clips.append(clip)
            progress(f"{item['id']}: {item['dur']:g} s ({(item['move'] or {}).get('type', 'static')})")
        lst = tmp / "list.txt"
        lst.write_text("".join(f"file '{c}'\n" for c in clips), encoding="utf-8")
        video = tmp / "video.mp4"
        _run([_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
              "-c", "copy", str(video)])
        audio = tmp / "audio.wav"
        _run(build_audio(plan, audio))
        part = mp4.with_suffix(".part.mp4")
        _run([_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(video), "-i", str(audio),
              "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
              "-movflags", "+faststart", str(part)])
        part.replace(mp4)
    sample_dir = None
    if frames:
        sample_dir = out_dir / f"{plan.scene_id}_frames"
        sample_dir.mkdir(exist_ok=True)
        for item in plan.shots:
            t = item["start"] + item["dur"] * 0.6
            _run([_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(mp4),
                  "-frames:v", "1", str(sample_dir / f"{item['id']}.jpg")])
    cut = {
        "schema": "autonovel-film-animatic/1", "scene_id": plan.scene_id, "file": str(mp4.relative_to(film)),
        "duration_s": plan.duration_s, "page_time_s": plan.page_time_s,
        "ratio_to_page_time": round(plan.duration_s / plan.page_time_s, 2) if plan.page_time_s else None,
        "shots": [{k: v for k, v in s.items() if k != "card"} for s in plan.shots],
        "lines": plan.lines, "sound": plan.cues, "sources": plan.sources, "problems": plan.problems,
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    for s in cut["shots"]:
        if s.get("still"):
            s["still"] = str(Path(s["still"]).relative_to(film))
    for x in cut["lines"] + cut["sound"]:
        x["file"] = str(Path(x["file"]).relative_to(film))
    (out_dir / f"{plan.scene_id}.json").write_text(json.dumps(cut, indent=2, ensure_ascii=False) + "\n",
                                                   encoding="utf-8")
    return {"ok": True, "scene": plan.scene_id, "file": str(mp4), "duration_s": plan.duration_s,
            "page_time_s": plan.page_time_s, "ratio_to_page_time": cut["ratio_to_page_time"],
            "problems": plan.problems, "frames": str(sample_dir) if sample_dir else None}


def join(scene_files: list[Path], out: Path) -> dict:
    """Concatenate built scenes (same size, rate and codecs) into one film."""
    with tempfile.TemporaryDirectory(prefix="animatic_join_") as td:
        lst = Path(td) / "list.txt"
        lst.write_text("".join(f"file '{p.resolve()}'\n" for p in scene_files), encoding="utf-8")
        part = out.with_suffix(".part.mp4")
        _run([_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
              "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(part)])
        part.replace(out)
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                       capture_output=True, text=True)
    return {"ok": True, "file": str(out), "duration_s": round(float(p.stdout.strip() or 0), 2)}


def summary_markdown(results: list[dict], joined: dict | None) -> str:
    out = ["# Animatic", "", "| Scene | Length | Page time | Ratio | File |", "|---|---|---|---|---|"]
    for r in results:
        if not r.get("ok"):
            out.append(f"| {r['scene']} | — | — | — | not built: {'; '.join(r['problems'])} |")
            continue
        out.append(f"| {r['scene']} | {r['duration_s']:g} s | {r['page_time_s']:g} s | "
                   f"{r['ratio_to_page_time']:.0%} | {r['file']} |")
    if joined:
        out += ["", f"Joined: {joined['file']} ({joined['duration_s']:g} s)."]
    probs = [p for r in results for p in r.get("problems", [])]
    out += ["", f"## Problems ({len(probs)})"] + ([f"- {p}" for p in probs] or ["- none"])
    return "\n".join(out) + "\n"
