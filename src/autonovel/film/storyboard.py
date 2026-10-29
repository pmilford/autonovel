"""Keyframes: the frame manifest, its render loop and each frame's verdict.

One manifest per scene's storyboard (`film/storyboard/<scene>.json`) and
one per character sheet (`film/bible/sheets/<slug>.json`), both in the same
shape: an ordered list of frames, each with its prompt, its reference
images (paths under `film/`, which may be earlier frames' selects: a sheet's
three-quarter view is made from its front view), a seed and a status.

`render()` renders every frame that is `pending` or `regenerate` through a
local ComfyUI server, writing each take to `<manifest stem>/takes/` (takes
are never overwritten) and the current select to `<manifest stem>/<id>.png`;
the manifest is saved after every frame, so a crash loses at most one.
`verdict()` records the vision check's verdict on a frame: `keep`,
`regenerate` (with a revised prompt or seed; at most `MAX_REGENERATIONS`
times, after which the frame goes to the author) or `author`.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from . import comfy
from .shots import film_dir_of

SCHEMA = "autonovel-film-frames/1"
MAX_REGENERATIONS = 2
STATUSES = ("pending", "rendered", "keep", "regenerate", "author")
VERDICTS = ("keep", "regenerate", "author")
DEFAULT_SIZE = (1280, 720)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".json.part")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def out_dir(manifest: Path) -> Path:
    return manifest.with_suffix("")


def validate(data: dict, film: Path) -> list[str]:
    """Problems that stop a render: shape, IDs, statuses, references that
    are neither on disk nor an earlier frame's select."""
    errs: list[str] = []
    if data.get("schema") != SCHEMA:
        errs.append(f"schema is {data.get('schema')!r}; expected {SCHEMA!r}")
    frames = data.get("frames")
    if not isinstance(frames, list) or not frames:
        return errs + ["no frames"]
    seen: set[str] = set()
    for f in frames:
        fid = f.get("id") or "?"
        if fid in seen:
            errs.append(f"{fid}: frame ID repeats")
        seen.add(fid)
        if not (f.get("prompt") or "").strip():
            errs.append(f"{fid}: no prompt")
        if f.get("status", "pending") not in STATUSES:
            errs.append(f"{fid}: status {f.get('status')!r} is not one of {', '.join(STATUSES)}")
        for r in f.get("refs") or []:
            if not (film / r).is_file() and not _is_earlier_select(r, frames, fid, data, film):
                errs.append(f"{fid}: reference {r} is not under film/ and no earlier frame makes it")
    return errs


def _select_rel(manifest_rel_stem: str, fid: str) -> str:
    return f"{manifest_rel_stem}/{fid}.png"


def _is_earlier_select(ref: str, frames: list[dict], fid: str, data: dict, film: Path) -> bool:
    stem = data.get("_stem_rel") or ""
    for f in frames:
        if f.get("id") == fid:
            return False
        if stem and ref == _select_rel(stem, f["id"]):
            return True
    return False


def render(manifest: Path, *, client: comfy.Client, only: list[str] | None = None,
           models: dict | None = None, keep_loaded: bool = False, dry_run: bool = False,
           progress=print) -> dict:
    """Render every pending or regenerate frame. Returns a summary."""
    manifest = manifest.resolve()
    film = film_dir_of(manifest)
    data = load(manifest)
    stem_rel = str(out_dir(manifest).relative_to(film))
    data["_stem_rel"] = stem_rel
    errs = validate(data, film)
    data.pop("_stem_rel", None)
    if errs:
        return {"ok": False, "errors": errs, "rendered": []}
    todo = [f for f in data["frames"] if f.get("status", "pending") in ("pending", "regenerate")
            and (not only or f["id"] in only)]
    if dry_run:
        return {"ok": True, "dry_run": True, "would_render": [f["id"] for f in todo]}
    if not todo:
        return {"ok": True, "rendered": [], "note": "nothing pending"}
    stats = client.up()
    if stats is None:
        return {"ok": False, "errors": [f"no ComfyUI server at {client.url}; start one (under WSL with "
                                        "--disable-pinned-memory), or pass --url"], "rendered": []}
    m = {**comfy.KLEIN, **(models or {})}
    od = out_dir(manifest)
    (od / "takes").mkdir(parents=True, exist_ok=True)
    default_size = tuple(data.get("size") or DEFAULT_SIZE)
    done, failed = [], []
    t_all = time.time()
    try:
        for f in todo:
            w, h = tuple(f.get("size") or default_size)
            uploaded = []
            missing = [r for r in f.get("refs") or [] if not (film / r).is_file()]
            if missing:
                failed.append({"id": f["id"], "error": f"references not made yet: {', '.join(missing)}"})
                continue
            for r in f.get("refs") or []:
                uploaded.append(client.upload_image(film / r))
            seed = int(f.get("seed") or int(_sha(f["id"]), 16) % 10**6)
            wf = comfy.klein_workflow(f["prompt"], width=w, height=h, seed=seed, refs=uploaded,
                                      prefix=f"autonovel/{od.name}/{f['id']}", models=models)
            t0 = time.time()
            try:
                outputs = client.wait(client.queue(wf))
                images = client.fetch_images(outputs)
            except comfy.RamLimitExceeded:
                raise
            except comfy.ComfyError as e:
                failed.append({"id": f["id"], "error": str(e)})
                progress(f"{f['id']}: FAILED {e}")
                continue
            wall = round(time.time() - t0, 1)
            if not images:
                failed.append({"id": f["id"], "error": "the server returned no image"})
                continue
            takes = f.setdefault("takes", [])
            n = len(takes) + 1
            take = od / "takes" / f"{f['id']}_t{n:02d}.png"
            while take.exists():
                n += 1
                take = od / "takes" / f"{f['id']}_t{n:02d}.png"
            take.write_bytes(images[0])
            sel = od / f"{f['id']}.png"
            shutil.copyfile(take, sel)
            takes.append({"take": n, "file": str(take.relative_to(film)), "seed": seed,
                          "prompt_sha": _sha(f["prompt"]), "refs": list(f.get("refs") or []),
                          "size": [w, h], "wall_s": wall, "when": _now()})
            f["select"] = str(sel.relative_to(film))
            f["status"] = "rendered"
            f["seed"] = seed
            data["backend"] = {"kind": "comfyui", "url": client.url, "model": m["label"], "unet": m["unet"],
                               "steps": m["steps"], "licence": m["licence"]}
            save(manifest, data)
            done.append({"id": f["id"], "take": n, "wall_s": wall})
            progress(f"{f['id']}: take {n} in {wall} s")
    finally:
        freed = False if keep_loaded else client.free()
        log = data.setdefault("render_log", [])
        log.append({"when": _now(), "frames": [d["id"] for d in done], "failed": [x["id"] for x in failed],
                    "wall_s": round(time.time() - t_all, 1),
                    "gpu_s": round(sum(d["wall_s"] for d in done), 1),
                    "peak_ram_gb": round(client.peak_ram_gb, 1), "freed": freed})
        save(manifest, data)
    return {"ok": not failed, "rendered": done, "failed": failed, "freed": freed,
            "peak_ram_gb": round(client.peak_ram_gb, 1), "gpu_s": round(sum(d["wall_s"] for d in done), 1)}


def verdict(manifest: Path, frame_id: str, decision: str, note: str, *, prompt: str | None = None,
            seed: int | None = None, take: int | None = None) -> dict:
    """Record the vision check's verdict on one frame."""
    if decision not in VERDICTS:
        raise ValueError(f"verdict must be one of {', '.join(VERDICTS)}")
    manifest = manifest.resolve()
    film = film_dir_of(manifest)
    data = load(manifest)
    f = next((x for x in data.get("frames") or [] if x.get("id") == frame_id), None)
    if f is None:
        raise KeyError(f"no frame {frame_id} in {manifest}")
    takes = f.get("takes") or []
    rec = {"verdict": decision, "note": note, "when": _now(),
           "take": take or (takes[-1]["take"] if takes else None)}
    if decision == "keep":
        if not takes:
            raise ValueError(f"{frame_id} has no take to keep")
        chosen = next((t for t in takes if t["take"] == rec["take"]), takes[-1])
        sel = out_dir(manifest) / f"{frame_id}.png"
        shutil.copyfile(film / chosen["file"], sel)
        f["select"] = str(sel.relative_to(film))
        f["status"] = "keep"
    elif decision == "regenerate":
        if int(f.get("regenerations", 0)) >= MAX_REGENERATIONS:
            f["status"] = "author"
            rec["verdict"] = "author"
            rec["note"] = f"{note} (failed after {MAX_REGENERATIONS} regenerations; the author decides)"
        else:
            f["regenerations"] = int(f.get("regenerations", 0)) + 1
            f["status"] = "regenerate"
            if prompt:
                f["prompt"] = prompt
            f["seed"] = int(seed) if seed is not None else int(f.get("seed") or 0) + 1
    else:
        f["status"] = "author"
    f.setdefault("verdicts", []).append(rec)
    save(manifest, data)
    return {"frame": frame_id, "status": f["status"], "regenerations": f.get("regenerations", 0), **rec}


def status(manifest: Path) -> dict:
    data = load(manifest)
    rows = []
    for f in data.get("frames") or []:
        last = (f.get("verdicts") or [{}])[-1]
        rows.append({"id": f["id"], "status": f.get("status", "pending"), "takes": len(f.get("takes") or []),
                     "regenerations": f.get("regenerations", 0), "select": f.get("select"),
                     "last_verdict": last.get("verdict"), "note": last.get("note", "")})
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    gpu_s = sum(x.get("gpu_s", 0) for x in data.get("render_log") or [])
    return {"manifest": str(manifest), "frames": rows, "counts": counts, "gpu_s": round(gpu_s, 1),
            "ready": all(r["status"] in ("keep", "author") for r in rows)}


def render_status_markdown(st: dict) -> str:
    out = [f"# frames: {Path(st['manifest']).name}", "",
           f"{', '.join(f'{v} {k}' for k, v in sorted(st['counts'].items()))}; GPU time so far {st['gpu_s']:g} s; "
           f"{'every frame has a verdict' if st['ready'] else 'not every frame has a verdict yet'}.", "",
           "| Frame | Status | Takes | Regenerations | Last verdict |", "|---|---|---|---|---|"]
    for r in st["frames"]:
        v = f"{r['last_verdict']}: {r['note']}" if r["last_verdict"] else "—"
        out.append(f"| {r['id']} | {r['status']} | {r['takes']} | {r['regenerations']} | {v.replace('|', '/')} |")
    return "\n".join(out) + "\n"
