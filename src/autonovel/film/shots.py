"""The shot list (film pipeline F3): schema, checks and timing.

`autonovel mechanical shot-check <film/shots/<scene>.json>` is the
mechanical half of `/autonovel:shot-list`. A shot list is one JSON file
per scene, in the plan's extended schema (docs/film-pipeline-plan.md §3):
coverage, size, angle, camera, move (with its motivation), blocking,
screen direction, which side of the line the camera is on, eyeline,
lines, action paragraphs, continuity and a duration. The check reports:

  - the schema: every enum, every shot ID, a motivation for every move;
  - coverage: every line of the scene's dialogue is played in a shot, every
    action paragraph is shown or its omission has a reason;
  - the 180-degree line: the camera stays on one side of the scene's axis
    unless a neutral shot, a cutaway or a move across comes between, and a
    traveller keeps one screen direction the same way;
  - eyelines: a person looking at another looks the same way in every shot
    from the same side, and two people looking at each other look opposite
    ways;
  - continuity: wardrobe, props, time, weather and light carry from shot to
    shot (and from the scene before, when this one is CONTINUOUS), unless a
    change is recorded with its reason;
  - timing: each shot's duration is computed from its lines (recorded in
    the table read when there is one, estimated from their words when not)
    and its action, not guessed; the scene's total is compared with its
    page time;
  - the look: frame rate, lenses and moves against `film/bible/look.yaml`.

All of it checks what the shot list declares; whether the coverage tells
the story is the director/DP critic's judgement (CAMERA.md §10).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "autonovel-film-shots/1"

COVERAGE = ("establishing", "master", "single", "two-shot", "group", "over-shoulder", "insert",
            "cutaway", "pov", "reaction")
SIZES = ("EWS", "WS", "FS", "MS", "MCU", "CU", "ECU")
ANGLES = ("eye", "low", "high", "overhead", "dutch")
MOVES = ("static", "pan", "tilt", "push_in", "pull_out", "track", "follow", "drift", "crane",
         "handheld", "zoom", "arc", "whip_pan", "drone")
SPEEDS = ("slow", "medium", "fast")
DIRECTIONS = ("left_to_right", "right_to_left", "toward", "away", "neutral", "static")
SIDES = ("A", "B", "on_line")
LOOKS = ("frame_left", "frame_right", "camera", "up", "down", "neutral", "off")
# A move type, and the word that names it in a look's "never" lists.
MOVE_WORDS = {"handheld": "handheld", "zoom": "zoom", "whip_pan": "whip", "drone": "drone",
              "arc": "orbit", "crane": "crane"}

# Timing (CAMERA.md §6). Lead and tail are the breath before a line and the
# reaction after it; the minimum is how long the eye needs to read a shot.
# [pipeline heuristic]
DEFAULT_LEAD_S = 0.5
DEFAULT_TAIL_S = 0.7
DEFAULT_GAP_S = 0.3
MIN_SHOT_S = {"insert": 1.5, "cutaway": 1.5, "establishing": 3.0}
MIN_ANY_SHOT_S = 1.5
RETIME_TOLERANCE = 0.15          # a stored duration within 15% (or 0.5 s) is current
PAGE_TIME_TOLERANCE = 0.10       # milestone M4: the animatic within ±10% of page time


@dataclass
class ShotReport:
    path: str
    scene_id: str = ""
    shots: list[dict] = field(default_factory=list)
    total_s: float = 0.0
    page_time_s: float = 0.0
    line_source: str = "estimate"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    advisories: list[str] = field(default_factory=list)
    retimed: list[str] = field(default_factory=list)
    stamped: bool = False

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ok"] = self.ok
        d["ratio_to_page_time"] = round(self.total_s / self.page_time_s, 2) if self.page_time_s else None
        return d


# --------------------------------------------------------------- loading

def film_dir_of(shots_path: Path) -> Path:
    """`<book>/film/` for a file at `<book>/film/shots/<scene>.json`."""
    p = shots_path.resolve()
    for d in [p.parent, *p.parents]:
        if d.name == "film":
            return d
    return p.parent.parent


def load_yaml(path: Path) -> dict:
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError, ImportError):
        return {}
    except Exception:  # yaml.YAMLError
        return {}


def file_sha(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def _norm(v: object) -> str:
    s = json.dumps(v, sort_keys=True, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
    s = re.sub(r"\s+", " ", s.casefold()).strip(" .;,")
    return s


def table_read_durations(film: Path, lines: list[dict]) -> tuple[dict[str, float], str]:
    """Recorded durations from `film/audio/table_read/manifest.json` for the
    lines whose text still matches; the rest are estimated."""
    out = {ln["id"]: float(ln["est_s"]) for ln in lines}
    man = film / "audio" / "table_read" / "manifest.json"
    try:
        data = json.loads(man.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return out, "estimate"
    recorded = 0
    for ln in lines:
        rec = (data.get("lines") or {}).get(ln["id"])
        if rec and rec.get("text") == ln["text"] and rec.get("duration_s"):
            out[ln["id"]] = float(rec["duration_s"])
            recorded += 1
    if recorded == len(lines) and lines:
        return out, "table read"
    return out, f"table read for {recorded} of {len(lines)} lines" if recorded else "estimate"


def look_rules(look: dict) -> dict:
    fmt = look.get("format") or {}
    cam = look.get("camera") or {}
    lenses = look.get("lenses") or {}
    lens_set = [float(x) for x in (lenses.get("set_mm") or []) if isinstance(x, (int, float))]
    macro = re.findall(r"(\d+)\s*mm", str(lenses.get("macro") or ""))
    lens_set += [float(m) for m in macro]
    never: list[str] = []
    for src in ((cam.get("movement") or {}).get("never") or [], lenses.get("never") or [], fmt.get("never") or []):
        never += [str(x) for x in src]
    shutter = re.search(r"(\d+)\s*deg", str(fmt.get("shutter") or ""))
    return {"fps": fmt.get("frame_rate"), "shutter_deg": float(shutter.group(1)) if shutter else None,
            "lens_set": sorted(set(lens_set)), "never": never}


# --------------------------------------------------------------- timing

def shot_timing(shot: dict, line_s: dict[str, float], beat_share: dict[str, float]) -> float:
    """A shot's duration from what plays in it: lead + its lines (with a
    gap between them) + tail, or its action if that runs longer, plus any
    hold the DP asks for; never under the minimum a viewer needs to read
    the shot."""
    t = shot.get("timing") or {}
    lines = [l for l in shot.get("lines") or [] if l in line_s]
    if lines:
        lead = float(t.get("lead_s", DEFAULT_LEAD_S))
        tail = float(t.get("tail_s", DEFAULT_TAIL_S))
        gap = float(t.get("gap_s", DEFAULT_GAP_S))
        dialogue = lead + sum(line_s[l] for l in lines) + gap * (len(lines) - 1) + tail
    else:
        dialogue = 0.0
    if t.get("action_s") is not None:
        action = float(t["action_s"])
    else:
        action = sum(beat_share.get(b, 0.0) for b in shot.get("beats") or [])
    dur = max(dialogue, action) + float(t.get("hold_s", 0.0))
    dur = max(dur, MIN_SHOT_S.get(shot.get("coverage", ""), MIN_ANY_SHOT_S))
    return round(dur, 1)


def line_offsets(shot: dict, line_s: dict[str, float]) -> list[tuple[str, float]]:
    """Where each of the shot's lines starts, in seconds from the cut."""
    t = shot.get("timing") or {}
    pos = float(t.get("lead_s", DEFAULT_LEAD_S))
    gap = float(t.get("gap_s", DEFAULT_GAP_S))
    out = []
    for l in shot.get("lines") or []:
        if l not in line_s:
            continue
        out.append((l, round(pos, 2)))
        pos += line_s[l] + gap
    return out


# --------------------------------------------------------------- checking

def _enum(rep: ShotReport, sid: str, field_name: str, value: object, allowed: tuple, required: bool = True):
    if value in (None, ""):
        if required:
            rep.errors.append(f"{sid}: no {field_name} (one of {', '.join(allowed)})")
        return
    if value not in allowed:
        rep.errors.append(f"{sid}: {field_name} {value!r} is not one of {', '.join(allowed)}")


def previous_scene_state(film: Path, scene: dict) -> tuple[dict, str]:
    """The continuity state at the end of the scene before, when this one
    runs on from it (CONTINUOUS) and that scene has a shot list."""
    prev = scene.get("previous_scene")
    if not prev or (scene.get("time") or "").upper() not in ("CONTINUOUS", "SAME", "SAME TIME", "MOMENTS LATER"):
        return {}, ""
    p = film / "shots" / f"{prev}.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, ""
    state: dict = {}
    for shot in data.get("shots") or []:
        _apply_continuity(state, shot, None, shot.get("id") or prev)
    return state, prev


def _cont_items(cont: dict) -> list[tuple[str, str]]:
    """(key, value) pairs a shot's continuity declares: wardrobe and props
    per person or object, then the scene-wide time, weather and light."""
    out: list[tuple[str, str]] = []
    for who, v in (cont.get("wardrobe") or {}).items():
        out.append((f"wardrobe of {who}", v))
    props = cont.get("props")
    if isinstance(props, dict):
        for k, v in props.items():
            out.append((f"prop {k}", v))
    for k in ("time", "weather", "light"):
        if cont.get(k) not in (None, ""):
            out.append((k, cont[k]))
    return out


def _apply_continuity(state: dict, shot: dict, rep: ShotReport | None, sid: str) -> None:
    cont = shot.get("continuity") or {}
    if not isinstance(cont, dict):
        if rep is not None:
            rep.errors.append(f"{sid}: continuity must be an object (wardrobe, props, time, weather, light)")
        return
    changes = shot.get("continuity_change") or {}
    for key, value in _cont_items(cont):
        prev = state.get(key)
        if rep is not None and prev is not None and _norm(prev[0]) != _norm(value):
            who = key.split(" of ", 1)[-1].replace("prop ", "")
            if not any(c in changes for c in (key, who)):
                rep.errors.append(
                    f"{sid}: continuity: {key} goes from {prev[0]!r} ({prev[1]}) to {value!r} with no change "
                    "recorded; match it, or say why in continuity_change (CAMERA.md §5)")
        state[key] = (value, sid)


def check(shots_path: Path, *, retime: bool = False, stamp: bool = False) -> ShotReport:
    from ..mechanical import fountain as fountain_mod

    rep = ShotReport(path=str(shots_path))
    try:
        data = json.loads(shots_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        rep.errors.append(f"cannot read {shots_path}: {e}")
        return rep
    film = film_dir_of(shots_path)
    if data.get("schema") != SCHEMA:
        rep.warnings.append(f"schema is {data.get('schema')!r}; expected {SCHEMA!r}")
    sid_scene = data.get("scene_id") or shots_path.stem
    rep.scene_id = sid_scene

    # The scene in the script.
    script = data.get("script") or ""
    script_path = (film / script) if script else None
    scene = None
    if not script_path or not script_path.is_file():
        rep.errors.append(f"script {script!r} not found under {film} (the shot list names the Fountain "
                          "file it was made from, relative to film/)")
    else:
        scene = fountain_mod.scene_breakdown(script_path, sid_scene)
        if scene is None:
            rep.errors.append(f"scene {sid_scene} is not in {script}")
    lines = scene["lines"] if scene else []
    beats = scene["beats"] if scene else []
    rep.page_time_s = scene["page_time_s"] if scene else 0.0

    # Inputs and staleness.
    look_path = film / "bible" / "look.yaml"
    inputs = data.get("inputs") or {}
    now = {"scene_sha": scene["scene_sha"] if scene else "", "look_sha": file_sha(look_path)}
    if stamp:
        data["inputs"] = {**now, "stamped": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        rep.stamped = True
    else:
        if inputs.get("scene_sha") and now["scene_sha"] and inputs["scene_sha"] != now["scene_sha"]:
            rep.warnings.append(f"{sid_scene} has changed in the script since this shot list was made; re-run "
                                "/autonovel:shot-list (or re-stamp with --stamp after checking every shot)")
        if inputs.get("look_sha") and now["look_sha"] and inputs["look_sha"] != now["look_sha"]:
            rep.warnings.append("film/bible/look.yaml has changed since this shot list was made; check the "
                                "lenses and moves, then re-stamp")
        if not inputs:
            rep.warnings.append("no inputs fingerprint; run with --stamp once the shot list is written")

    look = load_yaml(look_path) if look_path.is_file() else {}
    rules = look_rules(look) if look else {"fps": None, "shutter_deg": None, "lens_set": [], "never": []}
    if not look:
        rep.warnings.append("no film/bible/look.yaml: lenses, frame rate and forbidden moves were not checked")

    # Bible references.
    for name, ref in (data.get("cast_refs") or {}).items():
        if not (film / ref).is_file():
            rep.warnings.append(f"cast_refs: {name} -> {ref} does not exist under film/")
    if data.get("axis") in (None, "", {}) and any((s.get("line_side") in ("A", "B")) for s in data.get("shots") or []):
        rep.errors.append("shots name a side of the line but the scene declares no axis (what the line runs "
                          "between, CAMERA.md §4)")

    shots = data.get("shots") or []
    if not shots:
        rep.errors.append("no shots")
    line_ids = {ln["id"] for ln in lines}
    beat_ids = {b["id"] for b in beats}
    seen_ids: set[str] = set()
    line_shots: dict[str, list[str]] = {l: [] for l in line_ids}
    beat_shots: dict[str, list[str]] = {b: [] for b in beat_ids}

    for k, shot in enumerate(shots, 1):
        sid = shot.get("id") or f"#{k}"
        if not re.fullmatch(rf"{re.escape(sid_scene)}-\d{{2,3}}[a-z]?", sid):
            rep.errors.append(f"{sid}: shot ID should be {sid_scene}-NN (scene ID, a dash, its number)")
        if sid in seen_ids:
            rep.errors.append(f"{sid}: shot ID repeats")
        seen_ids.add(sid)
        _enum(rep, sid, "coverage", shot.get("coverage"), COVERAGE)
        _enum(rep, sid, "shot_size", shot.get("shot_size"), SIZES)
        _enum(rep, sid, "angle", shot.get("angle"), ANGLES)
        _enum(rep, sid, "screen_direction", shot.get("screen_direction"), DIRECTIONS)
        _enum(rep, sid, "line_side", shot.get("line_side"), SIDES, required=False)
        if not (shot.get("purpose") or "").strip():
            rep.warnings.append(f"{sid}: no purpose (what the audience learns or feels from this shot)")
        if not isinstance(shot.get("in_frame"), list):
            rep.errors.append(f"{sid}: in_frame must list who and what is in the frame ([] for nobody)")
        cam = shot.get("camera") or {}
        lens = cam.get("lens_mm")
        if not isinstance(lens, (int, float)):
            rep.errors.append(f"{sid}: camera.lens_mm must be a number")
        elif rules["lens_set"] and float(lens) not in rules["lens_set"]:
            rep.warnings.append(f"{sid}: {lens} mm is not in the look's lens set "
                                f"({', '.join(f'{x:g}' for x in rules['lens_set'])})")
        if rules["fps"] and cam.get("fps") not in (None, rules["fps"]):
            rep.errors.append(f"{sid}: {cam.get('fps')} fps; the look is {rules['fps']} fps")
        if rules["shutter_deg"] and cam.get("shutter_deg") not in (None, rules["shutter_deg"]):
            rep.warnings.append(f"{sid}: shutter {cam.get('shutter_deg')} degrees; the look is {rules['shutter_deg']:g}")
        if shot.get("angle") == "dutch" and any("dutch" in n.lower() for n in rules["never"]):
            rep.errors.append(f"{sid}: a dutch angle, which the look forbids")
        move = shot.get("move") or {}
        mtype = move.get("type")
        _enum(rep, sid, "move.type", mtype, MOVES)
        if mtype and mtype != "static":
            if not (move.get("motivation") or "").strip():
                rep.errors.append(f"{sid}: a {mtype} with no motivation; every move answers to something in the "
                                  "scene (a person moving, a reveal the story needs; CAMERA.md §3)")
            _enum(rep, sid, "move.speed", move.get("speed"), SPEEDS, required=False)
            word = MOVE_WORDS.get(mtype)
            hit = next((n for n in rules["never"] if word and word in n.lower()), None)
            if hit:
                rep.errors.append(f"{sid}: a {mtype}, which the look forbids ({hit!r})")
        for l in shot.get("lines") or []:
            if l in line_shots:
                line_shots[l].append(sid)
            else:
                rep.errors.append(f"{sid}: line {l} is not a line of {sid_scene}")
        for b in shot.get("beats") or []:
            if b in beat_shots:
                beat_shots[b].append(sid)
            else:
                rep.errors.append(f"{sid}: action paragraph {b} is not in {sid_scene}")
        ey = shot.get("eyeline")
        if isinstance(ey, dict):
            _enum(rep, sid, "eyeline.looks", ey.get("looks"), LOOKS)
        elif ey not in (None, ""):
            rep.advisories.append(f"{sid}: eyeline is free text; give it as {{who, looks, at}} so it can be checked")

    # Coverage of the page.
    for l, where in line_shots.items():
        if not where:
            text = next(ln["text"] for ln in lines if ln["id"] == l)
            rep.errors.append(f"line {l} ({text[:50]!r}) is played in no shot")
        elif len(where) > 1:
            rep.advisories.append(f"line {l} is listed in {', '.join(where)}; the animatic plays it in {where[0]} "
                                  "(list it once, in the shot it is heard in)")
    omitted = data.get("omitted_beats") or {}
    for b, where in beat_shots.items():
        if not where and not (omitted.get(b) or "").strip():
            text = next(x["text"] for x in beats if x["id"] == b)
            rep.warnings.append(f"action paragraph {b} ({text[:50]!r}) is in no shot; show it, or give the "
                                "reason in omitted_beats")

    # The line, screen direction, eyelines.
    _check_line(rep, shots)
    _check_eyelines(rep, shots)

    # Continuity, from the scene before when this one runs on from it.
    state, prev_scene = previous_scene_state(film, scene or {})
    for shot in shots:
        _apply_continuity(state, shot, rep, shot.get("id", "?"))
    if prev_scene:
        rep.advisories.append(f"continuity carried in from {prev_scene} (this scene runs on from it)")

    # Variety: no cut between two near-identical framings.
    for a, b in zip(shots, shots[1:]):
        same = all(a.get(k) == b.get(k) for k in ("shot_size", "angle", "coverage", "line_side"))
        if same and a.get("in_frame") == b.get("in_frame"):
            rep.advisories.append(f"{a.get('id')} -> {b.get('id')}: same size, angle and subject; the cut will "
                                  "jump (change the size or the angle by enough, CAMERA.md §2)")
    if shots and not any(s.get("coverage") in ("establishing", "master") for s in shots):
        rep.advisories.append("no establishing shot or master: is the place and who is where clear (CAMERA.md §2)?")

    # Timing.
    line_s, rep.line_source = table_read_durations(film, lines)
    share: dict[str, float] = {}
    for b in beats:
        n = len(beat_shots.get(b["id"]) or []) or 1
        share[b["id"]] = b["est_s"] / n
    total = 0.0
    for shot in shots:
        sid = shot.get("id", "?")
        computed = shot_timing(shot, line_s, share)
        stored = shot.get("duration_s")
        if retime or not isinstance(stored, (int, float)):
            if stored != computed:
                rep.retimed.append(f"{sid}: {stored} -> {computed} s")
            shot["duration_s"] = computed
        elif abs(stored - computed) > max(0.5, RETIME_TOLERANCE * computed):
            rep.warnings.append(f"{sid}: duration_s {stored} s, but its lines and action come to {computed} s; "
                                "run with --retime (or give timing.hold_s / action_s for a held shot)")
        total += float(shot["duration_s"])
        rep.shots.append({"id": sid, "coverage": shot.get("coverage"), "size": shot.get("shot_size"),
                          "angle": shot.get("angle"), "move": (shot.get("move") or {}).get("type"),
                          "lens_mm": (shot.get("camera") or {}).get("lens_mm"),
                          "lines": shot.get("lines") or [], "duration_s": shot["duration_s"],
                          "computed_s": computed})
    rep.total_s = round(total, 1)
    if rep.page_time_s:
        ratio = rep.total_s / rep.page_time_s
        if abs(ratio - 1) > PAGE_TIME_TOLERANCE:
            rep.warnings.append(
                f"the shots run {rep.total_s:g} s against the scene's page time of {rep.page_time_s:g} s "
                f"({ratio:.0%}); a page is about a minute, so outside ±{PAGE_TIME_TOLERANCE:.0%} the cut is "
                "either padding or rushing the page (say which, and why, in the scene's notes)")

    if retime or stamp:
        data.setdefault("schema", SCHEMA)
        tmp = shots_path.with_suffix(".json.part")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(shots_path)
    return rep


def _check_line(rep: ShotReport, shots: list[dict]) -> None:
    """The 180-degree rule and screen direction, shot to shot."""
    last_side: tuple[str, str] | None = None
    last_dir: tuple[str, str] | None = None
    for shot in shots:
        sid = shot.get("id", "?")
        side = shot.get("line_side")
        direction = shot.get("screen_direction")
        reset = bool(shot.get("crossing")) or shot.get("coverage") == "cutaway"
        if reset:
            last_side = (side, sid) if side in ("A", "B") else None
            last_dir = (direction, sid) if direction in ("left_to_right", "right_to_left") else None
            continue
        if side == "on_line":
            last_side = None
        elif side in ("A", "B"):
            if last_side and last_side[0] != side:
                rep.errors.append(
                    f"{sid}: crosses the line: {last_side[1]} is on side {last_side[0]}, {sid} on side {side}, "
                    "with no neutral shot on the line, cutaway or move across between them (CAMERA.md §4); "
                    "keep the side, add one, or record how the cross is made in `crossing`")
            last_side = (side, sid)
        if direction in ("toward", "away", "neutral"):
            last_dir = None
        elif direction in ("left_to_right", "right_to_left"):
            if last_dir and last_dir[0] != direction:
                rep.errors.append(
                    f"{sid}: screen direction reverses: {last_dir[1]} moves {last_dir[0].replace('_', ' ')}, "
                    f"{sid} {direction.replace('_', ' ')}; the traveller seems to turn back (CAMERA.md §4)")
            last_dir = (direction, sid)


def _check_eyelines(rep: ShotReport, shots: list[dict]) -> None:
    seen: dict[tuple[str, str, str], tuple[str, str]] = {}
    for shot in shots:
        ey = shot.get("eyeline")
        if not isinstance(ey, dict):
            continue
        who, at, looks = (ey.get("who") or "").strip(), (ey.get("at") or "").strip(), ey.get("looks")
        side = shot.get("line_side") or ""
        if not who or not at or looks not in ("frame_left", "frame_right") or side not in ("A", "B"):
            continue
        sid = shot.get("id", "?")
        key = (who.casefold(), at.casefold(), side)
        if key in seen and seen[key][0] != looks:
            rep.errors.append(f"{sid}: {who} looks {looks.replace('_', ' ')} at {at}, but "
                              f"{seen[key][0].replace('_', ' ')} in {seen[key][1]} from the same side "
                              "(CAMERA.md §4: eyelines)")
        seen.setdefault(key, (looks, sid))
        rev = (at.casefold(), who.casefold(), side)
        if rev in seen and seen[rev][0] == looks:
            rep.errors.append(f"{sid}: {who} and {at} both look {looks.replace('_', ' ')} "
                              f"({seen[rev][1]}); people looking at each other look opposite ways")


# --------------------------------------------------------------- reporting

def render_markdown(rep: ShotReport) -> str:
    d = rep.to_dict()
    out = [f"# shot-check: {rep.scene_id}", ""]
    ratio = f" ({d['ratio_to_page_time']:.0%} of its page time, {rep.page_time_s:g} s)" if rep.page_time_s else ""
    out.append(f"**{'OK' if rep.ok else 'ERRORS'}** — {len(rep.shots)} shots, {rep.total_s:g} s{ratio}; "
               f"line times from: {rep.line_source}.")
    out += ["", "| Shot | Coverage | Size | Angle | Move | Lens | Lines | Duration (computed) |",
            "|---|---|---|---|---|---|---|---|"]
    for s in rep.shots:
        out.append(f"| {s['id']} | {s['coverage']} | {s['size']} | {s['angle']} | {s['move']} | "
                   f"{s['lens_mm']} | {', '.join(s['lines']) or '—'} | {s['duration_s']} ({s['computed_s']}) |")
    for title, items in (("Errors", rep.errors), ("Warnings", rep.warnings), ("Advisories", rep.advisories),
                         ("Retimed", rep.retimed)):
        out += ["", f"## {title} ({len(items)})"]
        out += [f"- {x}" for x in items] if items else ["- none"]
    if rep.stamped:
        out += ["", "Stamped with the scene's and the look's fingerprints."]
    return "\n".join(out) + "\n"


SIZE_WORDS = {"EWS": "extreme wide", "WS": "wide", "FS": "full figure", "MS": "medium (waist up)",
              "MCU": "medium close (chest up)", "CU": "close-up", "ECU": "extreme close-up"}


def render_sheet(shots_path: Path) -> str:
    """The shot list as a page the author reads: what each shot shows, how
    it is framed and why it moves, which lines play in it, how long it runs."""
    data = json.loads(shots_path.read_text(encoding="utf-8"))
    sid = data.get("scene_id", shots_path.stem)
    out = [f"# Shot list: {sid} {data.get('slugline', '')}".rstrip(), ""]
    for key, label in (("intent", "What the scene must do"), ("coverage_plan", "How it is covered"),
                       ("geography", "Where everyone is")):
        if data.get(key):
            out += [f"**{label}.** {data[key]}", ""]
    axis = data.get("axis")
    if axis:
        out += [f"**The line.** {axis.get('description') or axis if isinstance(axis, dict) else axis}", ""]
    total = 0.0
    out += ["| Shot | Framing | What we see | Camera | Lines | Seconds |", "|---|---|---|---|---|---|"]
    for shot in data.get("shots") or []:
        cam = shot.get("camera") or {}
        move = shot.get("move") or {}
        framing = (f"{SIZE_WORDS.get(shot.get('shot_size'), shot.get('shot_size'))}, {shot.get('angle')} angle, "
                   f"{cam.get('lens_mm')} mm; {shot.get('coverage')}")
        if move.get("type") and move["type"] != "static":
            camera = f"{move['type'].replace('_', ' ')} ({move.get('speed') or 'slow'}): {move.get('motivation', '')}"
        else:
            camera = "still"
        what = (shot.get("action") or shot.get("purpose") or "").replace("|", "/")
        if shot.get("purpose") and shot.get("action"):
            what += f" *Why: {shot['purpose'].replace('|', '/')}*"
        lines = ", ".join(shot.get("lines") or []) or "—"
        dur = shot.get("duration_s") or 0
        total += float(dur)
        out.append(f"| {shot.get('id')} | {framing} | {what} | {camera.replace('|', '/')} | {lines} | {dur:g} |")
    out += ["", f"Total {total:.1f} s."]
    return "\n".join(out) + "\n"


def to_json(rep: ShotReport) -> str:
    return json.dumps(rep.to_dict(), indent=2, ensure_ascii=False) + "\n"
