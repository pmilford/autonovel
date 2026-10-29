"""Tier-1 tests for the shot list (film pipeline F3): `autonovel mechanical
scene-lines` and `shot-check`.

Milestone M3's acceptance is that the checker catches a planted crossing of
the line and a planted costume change; these tests plant both, and the
other faults a crew would catch on set (a line nobody films, a move with no
reason, a look the bible forbids, two people looking the same way at each
other, a duration nobody computed).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from autonovel.film import shots as sh
from autonovel.mechanical import fountain as fm
from autonovel.mechanical.__main__ import main as mech_main

SCRIPT = """Title: The Crossing
Roles:
    FERRYMAN

EXT. RIVER - NIGHT

= S0101 | ch_01:5-7 | stranded -> across

Black water. A ferry comes out of the dark, a lantern at its bow.

ANA (20s) stands on the bank in a grey cloak, her hood up.

ANA
How far is it?

FERRYMAN
Far enough. Get in.

She steps down into the boat.

EXT. FAR BANK - STEPS - CONTINUOUS

= S0102 | ch_01:8 | a stranger -> let in

A dog comes down the steps and sniffs her hand.

FERRYMAN
It likes you.
"""

LOOK = """format:
  frame_rate: 24
  shutter: "180 degrees (1/48 s)"
camera:
  movement:
    never: ["drone or helicopter moves", "handheld shake for energy", "dutch angles"]
lenses:
  set_mm: [25, 32, 50, 75]
  macro: "100 mm macro for coins"
  never: ["zoom moves"]
"""


def shot(sid, **kw):
    base = {
        "id": sid, "coverage": "single", "shot_size": "MS", "angle": "eye",
        "camera": {"height_m": 1.5, "lens_mm": 50, "t_stop": 2.0, "fps": 24, "shutter_deg": 180},
        "move": {"type": "static"}, "in_frame": ["Ana"], "blocking": {"Ana": "bank, frame left"},
        "screen_direction": "static", "line_side": "A", "lines": [], "beats": [],
        "continuity": {"wardrobe": {"Ana": "grey cloak, hood up"}, "time": "night"},
        "purpose": "we see her",
    }
    base.update(kw)
    return base


def good_shots() -> dict:
    return {
        "schema": sh.SCHEMA, "scene_id": "S0101", "script": "screenplay/seq_01.fountain",
        "axis": {"between": ["Ana", "the ferry"]},
        "cast_refs": {"Ana": "bible/characters/ana.yaml"},
        "shots": [
            shot("S0101-01", coverage="establishing", shot_size="WS", in_frame=["the ferry", "Ana"],
                 camera={"lens_mm": 25, "fps": 24}, move={"type": "pan", "speed": "slow",
                                                         "motivation": "follows the ferry in"},
                 screen_direction="left_to_right", beats=["S0101-A01", "S0101-A02"],
                 timing={"action_s": 6.0}),
            shot("S0101-02", lines=["S0101-L01"], eyeline={"who": "Ana", "looks": "frame_right", "at": "the ferryman"}),
            shot("S0101-03", in_frame=["the ferryman"], lines=["S0101-L02"],
                 eyeline={"who": "the ferryman", "looks": "frame_left", "at": "Ana"},
                 continuity={"time": "night"}),
            shot("S0101-04", coverage="two-shot", shot_size="WS", beats=["S0101-A03"],
                 screen_direction="left_to_right", timing={"action_s": 3.0}),
        ],
    }


@pytest.fixture()
def film(tmp_path: Path) -> Path:
    book = tmp_path / "s" / "books" / "b"
    (book / "chapters").mkdir(parents=True)
    f = book / "film"
    (f / "screenplay").mkdir(parents=True)
    (f / "shots").mkdir()
    (f / "bible" / "characters").mkdir(parents=True)
    (f / "bible" / "look.yaml").write_text(LOOK, encoding="utf-8")
    (f / "bible" / "characters" / "ana.yaml").write_text("slug: ana\n", encoding="utf-8")
    (f / "screenplay" / "seq_01.fountain").write_text(SCRIPT, encoding="utf-8")
    return f


def write(film: Path, data: dict, scene: str = "S0101") -> Path:
    p = film / "shots" / f"{scene}.json"
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


def run(film: Path, data: dict, **kw) -> sh.ShotReport:
    return sh.check(write(film, data, data.get("scene_id", "S0101")), **kw)


# --------------------------------------------------------------- scene-lines

def test_scene_breakdown_numbers_lines_and_action(film: Path) -> None:
    bd = fm.scene_breakdown(film / "screenplay" / "seq_01.fountain", "S0101")
    assert [ln["id"] for ln in bd["lines"]] == ["S0101-L01", "S0101-L02"]
    assert [ln["cue"] for ln in bd["lines"]] == ["ANA", "FERRYMAN"]
    assert bd["lines"][1]["text"] == "Far enough. Get in."
    assert [b["id"] for b in bd["beats"]] == ["S0101-A01", "S0101-A02", "S0101-A03"]
    assert all(b["est_s"] > 0 for b in bd["beats"])
    assert bd["page_time_s"] == round(bd["eighths"] / 8 * 60, 1)
    assert bd["next_scene"] == "S0102" and bd["previous_scene"] == ""
    assert len(bd["scene_sha"]) == 16


def test_speech_seconds_grows_with_words_and_sentences() -> None:
    assert fm.speech_seconds("") == 0.0
    assert fm.speech_seconds("Up.") == fm.SPEECH_MIN_S
    assert fm.speech_seconds("A b c d e. F g h i j.") > fm.speech_seconds("A b c d e f g h i j")


def test_scenes_json_carries_the_line_ids(film: Path) -> None:
    fm.run(film / "screenplay" / "seq_01.fountain", do_export=False, cast_paths=[])
    data = json.loads((film / "scenes.json").read_text())
    s1 = next(s for s in data["scenes"] if s["id"] == "S0101")
    assert [ln["id"] for ln in s1["lines"]] == ["S0101-L01", "S0101-L02"]


def test_possessive_counts_as_presence(film: Path) -> None:
    bd = fm.scene_breakdown(film / "screenplay" / "seq_01.fountain", "S0102")
    assert "FERRYMAN" in bd["characters"]
    script = (film / "screenplay" / "seq_01.fountain")
    script.write_text(SCRIPT.replace("sniffs her hand", "sniffs the ferryman's boots"), encoding="utf-8")
    bd = fm.scene_breakdown(script, "S0102")
    assert "FERRYMAN" in bd["characters"]


def test_scene_lines_cli(film: Path, capsys) -> None:
    rc = mech_main(["scene-lines", str(film / "screenplay" / "seq_01.fountain"), "--scene", "S0101",
                    "--format", "markdown"])
    out = capsys.readouterr().out
    assert rc == 0 and "S0101-L02" in out and "S0101-A03" in out
    assert mech_main(["scene-lines", str(film / "screenplay" / "seq_01.fountain"), "--scene", "S0199"]) == 2


# --------------------------------------------------------------- shot-check: clean

def test_a_sound_shot_list_passes_and_is_retimed(film: Path) -> None:
    rep = run(film, good_shots(), retime=True)
    assert rep.ok, rep.errors
    data = json.loads((film / "shots" / "S0101.json").read_text())
    durs = [s["duration_s"] for s in data["shots"]]
    assert durs[0] == 6.0 and durs[3] == 3.0
    # a line shot: lead + line + tail
    l1 = fm.speech_seconds("How far is it?")
    assert durs[1] == round(sh.DEFAULT_LEAD_S + l1 + sh.DEFAULT_TAIL_S, 1)
    assert rep.line_source == "estimate"


def test_missing_line_and_unknown_ids(film: Path) -> None:
    d = good_shots()
    d["shots"][2]["lines"] = []
    d["shots"][3]["lines"] = ["S0101-L09"]
    rep = run(film, d)
    assert any("S0101-L02" in e and "no shot" in e for e in rep.errors)
    assert any("S0101-L09" in e for e in rep.errors)


def test_an_action_paragraph_left_out_needs_a_reason(film: Path) -> None:
    d = good_shots()
    d["shots"][3]["beats"] = []
    rep = run(film, d)
    assert any("S0101-A03" in w for w in rep.warnings)
    d["omitted_beats"] = {"S0101-A03": "carried by the sound of her step"}
    rep = run(film, d)
    assert not any("S0101-A03" in w for w in rep.warnings)


# --------------------------------------------------------------- the line

def test_planted_crossing_of_the_line_is_caught(film: Path) -> None:
    d = good_shots()
    d["shots"][2]["line_side"] = "B"
    rep = run(film, d)
    assert any("crosses the line" in e and "S0101-03" in e for e in rep.errors)


def test_a_neutral_shot_or_a_recorded_move_makes_the_cross_legal(film: Path) -> None:
    d = good_shots()
    d["shots"][2]["line_side"] = "B"
    d["shots"][3]["line_side"] = "B"
    d["shots"].insert(2, shot("S0101-02a", line_side="on_line", coverage="insert", shot_size="CU",
                              continuity={}, in_frame=["the lantern"]))
    assert not any("crosses the line" in e for e in run(film, d).errors)
    d = good_shots()
    d["shots"][2]["line_side"] = "B"
    d["shots"][2]["crossing"] = "the camera tracks round behind the ferryman as she steps down"
    d["shots"][3]["line_side"] = "B"
    assert not any("crosses the line" in e for e in run(film, d).errors)


def test_screen_direction_reversal_is_caught(film: Path) -> None:
    d = good_shots()
    d["shots"][3]["screen_direction"] = "right_to_left"
    rep = run(film, d)
    assert any("screen direction reverses" in e for e in rep.errors)
    d["shots"][2]["screen_direction"] = "toward"
    assert not any("reverses" in e for e in run(film, d).errors)


def test_eyelines_must_meet(film: Path) -> None:
    d = good_shots()
    d["shots"][2]["eyeline"]["looks"] = "frame_right"
    rep = run(film, d)
    assert any("look opposite ways" in e for e in rep.errors)
    d = good_shots()
    d["shots"].append(shot("S0101-05", eyeline={"who": "Ana", "looks": "frame_left", "at": "the ferryman"},
                           timing={"action_s": 2}))
    rep = run(film, d)
    assert any("Ana looks frame left" in e for e in rep.errors)


# --------------------------------------------------------------- continuity

def test_planted_costume_change_is_caught(film: Path) -> None:
    d = good_shots()
    d["shots"][3]["continuity"] = {"wardrobe": {"Ana": "grey cloak, hood down"}, "time": "night"}
    rep = run(film, d)
    assert any("wardrobe of Ana" in e and "S0101-04" in e for e in rep.errors)
    d["shots"][3]["continuity_change"] = {"Ana": "she pushes the hood back to see the steps"}
    assert run(film, d).ok


def test_wording_noise_is_not_a_change(film: Path) -> None:
    d = good_shots()
    d["shots"][3]["continuity"] = {"wardrobe": {"Ana": "Grey cloak,  hood up."}, "time": "Night"}
    assert run(film, d).ok


def test_continuity_runs_on_into_a_continuous_scene(film: Path) -> None:
    run(film, good_shots())
    d2 = {"schema": sh.SCHEMA, "scene_id": "S0102", "script": "screenplay/seq_01.fountain",
          "shots": [shot("S0102-01", coverage="master", shot_size="WS", beats=["S0102-A01"],
                         lines=["S0102-L01"], continuity={"wardrobe": {"Ana": "no cloak"}, "time": "night"})]}
    rep = run(film, d2)
    assert any("wardrobe of Ana" in e and "S0101-0" in e for e in rep.errors)
    assert any("carried in from S0101" in a for a in rep.advisories)


# --------------------------------------------------------------- moves and the look

def test_moves_need_a_motivation_and_obey_the_look(film: Path) -> None:
    d = good_shots()
    d["shots"][1]["move"] = {"type": "push_in", "speed": "slow"}
    d["shots"][2]["move"] = {"type": "handheld", "motivation": "energy"}
    d["shots"][3]["angle"] = "dutch"
    d["shots"][3]["camera"]["fps"] = 30
    d["shots"][3]["camera"]["lens_mm"] = 18
    rep = run(film, d)
    assert any("S0101-02" in e and "no motivation" in e for e in rep.errors)
    assert any("S0101-03" in e and "forbids" in e for e in rep.errors)
    assert any("dutch" in e for e in rep.errors)
    assert any("30 fps" in e for e in rep.errors)
    assert any("18 mm" in w for w in rep.warnings)


def test_macro_lens_is_in_the_set(film: Path) -> None:
    d = good_shots()
    d["shots"][3]["camera"]["lens_mm"] = 100
    assert not any("100 mm" in w for w in run(film, d).warnings)


def test_bad_enums_and_ids(film: Path) -> None:
    d = good_shots()
    d["shots"][0]["coverage"] = "glamour"
    d["shots"][1]["id"] = "shot-2"
    d["shots"][2]["shot_size"] = "MEDIUM"
    del d["shots"][3]["in_frame"]
    rep = run(film, d)
    for needle in ("glamour", "shot-2", "MEDIUM", "in_frame"):
        assert any(needle in e for e in rep.errors), needle


def test_same_framing_twice_is_flagged_as_a_jump(film: Path) -> None:
    d = good_shots()
    d["shots"][2] = copy.deepcopy(d["shots"][1])
    d["shots"][2]["id"] = "S0101-03"
    d["shots"][2]["lines"] = ["S0101-L02"]
    rep = run(film, d)
    assert any("will jump" in a for a in rep.advisories)


# --------------------------------------------------------------- timing

def test_retime_uses_the_table_read_when_its_text_matches(film: Path) -> None:
    man = film / "audio" / "table_read"
    man.mkdir(parents=True)
    (man / "manifest.json").write_text(json.dumps({"lines": {
        "S0101-L01": {"text": "How far is it?", "duration_s": 2.4},
        "S0101-L02": {"text": "an older wording", "duration_s": 9.0},
    }}), encoding="utf-8")
    rep = run(film, good_shots(), retime=True)
    data = json.loads((film / "shots" / "S0101.json").read_text())
    assert data["shots"][1]["duration_s"] == round(sh.DEFAULT_LEAD_S + 2.4 + sh.DEFAULT_TAIL_S, 1)
    # the stale recording is not used
    est = fm.speech_seconds("Far enough. Get in.")
    assert data["shots"][2]["duration_s"] == round(sh.DEFAULT_LEAD_S + est + sh.DEFAULT_TAIL_S, 1)
    assert rep.line_source == "table read for 1 of 2 lines"


def test_a_stored_duration_nobody_computed_is_flagged(film: Path) -> None:
    d = good_shots()
    for s in d["shots"]:
        s["duration_s"] = 1.0
    d["shots"][0]["duration_s"] = 6.0
    rep = run(film, d)
    assert any("S0101-03" in w and "--retime" in w for w in rep.warnings)
    d["shots"][2]["timing"] = {"hold_s": 0}
    assert sh.shot_timing(d["shots"][2], {"S0101-L02": 2.0}, {}) == round(0.5 + 2.0 + 0.7, 1)


def test_minimum_read_time_and_hold() -> None:
    assert sh.shot_timing({"coverage": "insert"}, {}, {}) == sh.MIN_SHOT_S["insert"]
    assert sh.shot_timing({"coverage": "single", "timing": {"action_s": 2, "hold_s": 1.5}}, {}, {}) == 3.5
    assert sh.line_offsets({"lines": ["a", "b"], "timing": {"lead_s": 1}}, {"a": 2.0, "b": 1.0}) == [("a", 1.0), ("b", 3.3)]


def test_page_time_tolerance(film: Path) -> None:
    d = good_shots()
    d["shots"][0]["timing"] = {"action_s": 90}
    rep = run(film, d, retime=True)
    assert any("page time" in w for w in rep.warnings)


# --------------------------------------------------------------- staleness and the CLI

def test_stamp_then_a_script_edit_is_reported(film: Path) -> None:
    rep = run(film, good_shots(), stamp=True)
    assert rep.stamped
    p = film / "shots" / "S0101.json"
    assert json.loads(p.read_text())["inputs"]["scene_sha"]
    script = film / "screenplay" / "seq_01.fountain"
    script.write_text(SCRIPT.replace("Far enough. Get in.", "Far enough. Sit down."), encoding="utf-8")
    rep = sh.check(p)
    assert any("changed in the script" in w for w in rep.warnings)


def test_shot_check_cli_exit_codes(film: Path, capsys) -> None:
    p = write(film, good_shots())
    assert mech_main(["shot-check", str(p), "--retime", "--stamp", "--format", "markdown"]) == 0
    assert "S0101-04" in capsys.readouterr().out
    d = good_shots()
    d["shots"][2]["line_side"] = "B"
    p = write(film, d)
    assert mech_main(["shot-check", str(p)]) == 1
    assert mech_main(["shot-check", str(film / "shots" / "nope.json")]) == 2
