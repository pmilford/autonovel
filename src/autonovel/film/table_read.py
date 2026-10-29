"""The table read: every line of a scene spoken in its cast voice, checked.

`autonovel mechanical table-read <seq.fountain> --scene <ID>` is the
mechanical half of `/autonovel:table-read`. It reads the voice casting
file `film/audio/voices.yaml`:

    voices:
      JAKOB:                                   # the script's cue
        character: bible/characters/jakob-fugger.yaml
        design: "a fourteen-year-old boy, ..."  # the written voice
        ref_text: "a neutral sentence for the reference clip"
        ref: audio/voices/jakob.wav            # made from `design` when missing
        consent: "synthetic: designed from a description; no real person's voice"
    lexicon:                                   # respellings for the voice only
      Fondaco: FON-dah-ko
    names: [Fondaco, Augsburgs]                # words the transcriber may misspell

builds a job of every line of the scenes (their IDs from the script),
skips each line whose recording is current (same words, same voice
reference), runs the TTS engine script in its own environment
(`--python`, or `$AUTONOVEL_TTS_PYTHON`) and writes
`film/audio/table_read/<line ID>.wav` and `manifest.json` with each
line's text, voice, length, attempts and what the transcriber heard.

Voices are consent-free by construction: a voice entry must say how its
reference was made, and one with no `design` must name a `ref` clip and a
`consent` line; the check refuses a reference whose consent is missing.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .shots import load_yaml

SCHEMA = "autonovel-film-table-read/1"


def _sha_file(p: Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def _sha_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]


def respell(text: str, lexicon: dict[str, str]) -> str:
    for word in sorted(lexicon, key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(word)}(?=\W|$|'s)", lexicon[word], text)
    return text


def load_voices(film: Path) -> tuple[dict, list[str]]:
    path = film / "audio" / "voices.yaml"
    data = load_yaml(path) if path.is_file() else {}
    problems = []
    if not data:
        problems.append(f"no voice casting file at {path}")
    for cue, v in (data.get("voices") or {}).items():
        if not isinstance(v, dict):
            problems.append(f"{cue}: voice entry must be a mapping")
            continue
        if not v.get("ref"):
            problems.append(f"{cue}: no ref (where the voice's reference clip is, under film/)")
        if not v.get("design") and not (film / str(v.get("ref", ""))).is_file():
            problems.append(f"{cue}: no design and no reference clip on file")
        if not (v.get("consent") or "").strip():
            problems.append(f"{cue}: no consent line; say how the voice was made (a synthetic voice "
                            "needs none from anyone, a recorded one needs the speaker's written consent)")
        if v.get("design") and not (v.get("ref_text") or "").strip():
            problems.append(f"{cue}: a designed voice needs ref_text (the sentence its reference clip says)")
    return data, problems


def manifest_path(film: Path) -> Path:
    return film / "audio" / "table_read" / "manifest.json"


def load_manifest(film: Path) -> dict:
    try:
        return json.loads(manifest_path(film).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema": SCHEMA, "lines": {}, "voices": {}, "runs": []}


def plan(script: Path, scenes: list[str], *, film: Path, force: bool = False) -> dict:
    """What a run would do: every line of the scenes, current or to render."""
    from ..mechanical import fountain as fountain_mod
    voices, problems = load_voices(film)
    man = load_manifest(film)
    lexicon = {str(k): str(v) for k, v in (voices.get("lexicon") or {}).items()}
    out = {"lines": [], "problems": list(problems), "current": [], "todo": []}
    for sid in scenes:
        bd = fountain_mod.scene_breakdown(script, sid)
        if bd is None:
            out["problems"].append(f"no scene {sid} in {script}")
            continue
        for ln in bd["lines"]:
            cue = ln["cue"]
            v = (voices.get("voices") or {}).get(cue)
            if v is None:
                out["problems"].append(f"{ln['id']}: {cue} has no voice in voices.yaml")
                continue
            ref = film / v["ref"]
            rec = (man.get("lines") or {}).get(ln["id"]) or {}
            current = (not force and rec.get("text") == ln["text"] and rec.get("ref_sha") == _sha_file(ref)
                       and ref.is_file() and (film / rec.get("file", "-")).is_file())
            item = {"id": ln["id"], "cue": cue, "text": ln["text"], "spoken": respell(ln["text"], lexicon),
                    "parens": ln.get("parens") or [], "scene": sid, "current": current,
                    "file": f"audio/table_read/{ln['id']}.wav"}
            out["lines"].append(item)
            (out["current"] if current else out["todo"]).append(ln["id"])
    return out


def run(script: Path, scenes: list[str], *, film: Path, python: str, gpu: int = 0, force: bool = False,
        tries: int = 4, remake_voices: bool = False, dry_run: bool = False, progress=print) -> dict:
    p = plan(script, scenes, film=film, force=force)
    if p["problems"] or dry_run or not p["todo"]:
        return {"ok": not p["problems"], **p, "rendered": []}
    voices, _ = load_voices(film)
    todo = [l for l in p["lines"] if not l["current"]]
    cues = sorted({l["cue"] for l in todo})
    names = set(str(n) for n in voices.get("names") or [])
    for l in todo:   # capitalised words inside a line are names to the transcriber
        names |= {w for w in re.findall(r"(?<=\w )[A-Z][a-z]+", l["text"])}
    job = {
        "gpu": gpu, "tries": tries, "names": sorted(n.lower() for n in names),
        "voices": {c: {**{k: v for k, v in voices["voices"][c].items() if k in ("design", "ref_text", "seed",
                                                                               "design_tries")},
                       "ref": str((film / voices["voices"][c]["ref"]).resolve()),
                       "remake": bool(remake_voices)} for c in cues},
        "lines": [{"id": l["id"], "cue": l["cue"], "text": l["text"], "spoken": l["spoken"],
                   "out": str((film / l["file"]).resolve())} for l in todo],
    }
    from .engines import engine_path
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump(job, fh)
        job_path = fh.name
    env = {**os.environ, "CUDA_DEVICE_ORDER": "PCI_BUS_ID"}
    try:
        proc = subprocess.run([python, str(engine_path("voxcpm_lines")), job_path], capture_output=True,
                              text=True, env=env)
    finally:
        os.unlink(job_path)
    if proc.stderr:
        progress(proc.stderr[-4000:])
    last = (proc.stdout.strip().splitlines() or [""])[-1]
    try:
        res = json.loads(last)
    except json.JSONDecodeError:
        return {"ok": False, **p, "rendered": [], "problems": [f"the engine failed (exit {proc.returncode}); "
                                                                f"see its output above"]}
    man = load_manifest(film)
    man["schema"] = SCHEMA
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for c in cues:
        v = voices["voices"][c]
        ref = film / v["ref"]
        man.setdefault("voices", {})[c] = {"ref": v["ref"], "ref_sha": _sha_file(ref), "design": v.get("design"),
                                          "consent": v.get("consent"), "character": v.get("character"),
                                          "made": (res.get("voices", {}).get(c) or {}).get("made")}
    for l in todo:
        r = res["lines"].get(l["id"])
        if not r:
            continue
        man.setdefault("lines", {})[l["id"]] = {
            "text": l["text"], "text_sha": _sha_text(l["text"]), "cue": l["cue"], "scene": l["scene"],
            "spoken": l["spoken"] if l["spoken"] != l["text"] else None, "file": l["file"],
            "ref_sha": _sha_file(film / voices["voices"][l["cue"]]["ref"]), "duration_s": r["duration_s"],
            "attempts": r["attempts"], "passed": r["passed"], "heard": r["heard"], "notes": r["notes"],
            "rendered": now}
    man.setdefault("runs", []).append({"when": now, "engine": res.get("engine"), "model": res.get("model"),
                                       "asr": res.get("asr"), "gpu": gpu, "lines": [l["id"] for l in todo],
                                       "load_s": res.get("load_s"), "generation_s": res.get("generation_s")})
    mp = manifest_path(film)
    mp.parent.mkdir(parents=True, exist_ok=True)
    tmp = mp.with_suffix(".json.part")
    tmp.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(mp)
    never = [i for i in (l["id"] for l in todo) if not res["lines"].get(i, {}).get("passed")]
    return {"ok": True, **p, "rendered": [l["id"] for l in todo], "never_passed": never,
            "generation_s": res.get("generation_s"), "load_s": res.get("load_s")}


def render_markdown(film: Path, ids: list[str] | None = None) -> str:
    man = load_manifest(film)
    out = ["# Table read", "", "| Line | Who | Words | Seconds | Tries | Heard as |", "|---|---|---|---|---|---|"]
    for lid, r in sorted((man.get("lines") or {}).items()):
        if ids and lid not in ids:
            continue
        flag = "" if r.get("passed") else " (never matched)"
        out.append(f"| {lid} | {r['cue']} | {r['text'].replace('|', '/')} | {r['duration_s']:g} | "
                   f"{r['attempts']}{flag} | {r['heard'].replace('|', '/')} |")
    out += ["", "| Voice | Made | Consent |", "|---|---|---|"]
    for c, v in sorted((man.get("voices") or {}).items()):
        out.append(f"| {c} | {(v.get('design') or v.get('ref'))[:80]} | {v.get('consent', '')} |")
    return "\n".join(out) + "\n"
