"""Tier-1 tests for movie-teaser Phase 7: character/location references.

Generalises the manual Fugger reference spike into the normal flow:
- locations become first-class reference entities (opt-in `--with-locations`)
  so a period place gets its own anachronism-guarded plate (the Rialto fix);
- an appearance age ladder (parallel to voice ages) picks the age-correct
  appearance string per shot's story_year and feeds it as an
  `appearance_override` so the prompt text matches the reference image;
- the shot→refs map reaches the VIDEO backends: when a shot has no keyframe,
  the primary reference plate is used as the image-to-video start frame.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.teaser import refs, render
from autonovel.teaser import refmanifest as rm
from autonovel.teaser import backends
from autonovel.teaser.shots import Shot, Teaser


def _run(*argv):
    return subprocess.run([sys.executable, "-m", "autonovel.mechanical", *argv],
                          capture_output=True, text=True)


def _teaser():
    return Teaser(title="T", provider="veo", shots=[
        Shot(id="01", subject_name="JAKOB", subject_appearance="boy of fourteen",
             action="a", setting="Venice, Rialto", story_year=1485),
        Shot(id="02", subject_name="JAKOB", subject_appearance="a man of forty",
             action="b", setting="Venice, Rialto", story_year=1518),
        Shot(id="03", subject_name="ANNA", subject_appearance="x",
             action="c", setting="Augsburg counting-house"),
    ])


# ----------------------- locations as ref entities -----------------------


def test_plan_refs_locations_off_by_default() -> None:
    plan = refs.plan_refs(_teaser())
    assert all(e.kind == "character" for e in plan.entries)
    assert {e.subject for e in plan.entries} == {"JAKOB", "ANNA"}


def test_plan_refs_with_locations() -> None:
    plan = refs.plan_refs(_teaser(), include_locations=True)
    locs = {e.subject: e for e in plan.entries if e.kind == "location"}
    assert set(locs) == {"Venice, Rialto", "Augsburg counting-house"}
    assert locs["Venice, Rialto"].shots == ["01", "02"]
    assert locs["Venice, Rialto"].ref_path.startswith("refs/loc_")


def test_scaffold_includes_locations() -> None:
    man = rm.scaffold_from_teaser(_teaser(), include_locations=True)
    by = {s.subject: s for s in man.subjects}
    assert by["Venice, Rialto"].kind == "location"
    assert by["JAKOB"].kind == "character"
    # default (no flag) → characters only
    man2 = rm.scaffold_from_teaser(_teaser())
    assert all(s.kind == "character" for s in man2.subjects)


def test_status_with_locations_tracks_places() -> None:
    man = rm.RefManifest()
    status = rm.build_status(_teaser(), man, include_locations=True)
    subs = {r.subject for r in status.rows}
    assert "Venice, Rialto" in subs


# ------------------------ appearance age ladder --------------------------


def test_resolve_appearance_by_year() -> None:
    cr = rm.CharacterRef(subject="JAKOB", appearance="boy of fourteen", appearance_ages=[
        {"name": "youth", "appearance": "a youth of eighteen", "from_year": 1480, "to_year": 1495},
        {"name": "elder", "appearance": "a man of sixty, white-bearded", "from_year": 1515},
    ])
    assert cr.resolve_appearance(1485).startswith("a youth")
    assert cr.resolve_appearance(1530).startswith("a man of sixty")
    assert cr.resolve_appearance(None) == "boy of fourteen"
    assert cr.resolve_appearance(1470) == "boy of fourteen"  # before any window


def test_appearance_ages_round_trip(tmp_path: Path) -> None:
    cr = rm.CharacterRef(subject="JAKOB", appearance="boy", status="approved",
                         appearance_ages=[{"name": "man", "appearance": "a man of forty",
                                           "from_year": 1510}])
    p = tmp_path / "refs.yaml"
    rm.dump(rm.RefManifest(subjects=[cr]), p)
    back = rm.load(p).get("JAKOB")
    assert back.appearance_ages and back.resolve_appearance(1520).startswith("a man")


def test_build_request_appearance_override() -> None:
    shot = _teaser().shots[0]  # appearance "boy of fourteen"
    req = render.build_request(shot, provider="veo", kind="image",
                               out_dir=Path("/tmp"),
                               appearance_override="a youth of eighteen")
    assert "a youth of eighteen" in req.prompt
    assert "boy of fourteen" not in req.prompt


def test_appearances_map_resolves_by_story_year(tmp_path: Path) -> None:
    from autonovel.mechanical.__main__ import _load_teaser_appearances_map
    from autonovel.teaser import shots as shots_mod
    t = _teaser()
    tp = tmp_path / "teaser.json"
    shots_mod.dump(t, tp)
    man = rm.RefManifest(subjects=[rm.CharacterRef(
        subject="JAKOB", appearance="boy of fourteen", status="approved",
        appearance_ages=[
            {"name": "youth", "appearance": "a youth of eighteen", "from_year": 1480, "to_year": 1495},
            {"name": "man", "appearance": "a grey-templed man of forty", "from_year": 1510},
        ])])
    rm.dump(man, tmp_path / "refs.yaml")
    amap = _load_teaser_appearances_map(tp, None)
    assert amap["01"].startswith("a youth")        # story_year 1485 vs baked "boy"
    assert amap["02"].startswith("a grey-templed")  # 1518 variant ≠ baked "a man of forty"
    # unapproved subject contributes nothing
    man2 = rm.RefManifest(subjects=[rm.CharacterRef(
        subject="JAKOB", appearance="boy", status="pending",
        appearance_ages=[{"name": "man", "appearance": "a man", "from_year": 1510}])])
    rm.dump(man2, tmp_path / "refs.yaml")
    assert _load_teaser_appearances_map(tp, None) == {}


# ----------------- refs reach the video backends (init) ------------------


def test_init_image_falls_back_to_primary_reference(tmp_path: Path) -> None:
    """A video shot with no keyframe uses the primary ref plate as the
    image-to-video start frame, so identity reaches grok/veo/kie."""
    plate = tmp_path / "jakob.png"
    plate.write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal bytes; backend only b64s

    class _Req:
        init_image = ""
        reference_images = (str(plate),)

    class _Net:
        pass

    got = backends._init_image(_Req(), net=_Net())
    assert got is not None
    mime, b64 = got
    assert mime == "image/png" and b64


def test_init_image_prefers_explicit_keyframe(tmp_path: Path) -> None:
    kf = tmp_path / "kf.png"; kf.write_bytes(b"\x89PNG")
    plate = tmp_path / "ref.png"; plate.write_bytes(b"\x89PNGzzz")

    class _Req:
        init_image = str(kf)
        reference_images = (str(plate),)

    class _Net:
        pass

    mime, b64 = backends._init_image(_Req(), net=_Net())
    import base64
    assert base64.b64decode(b64) == b"\x89PNG"  # the keyframe, not the plate


# ------------------------------- CLI -------------------------------------


def test_cli_refs_init_with_locations(tmp_path: Path) -> None:
    from autonovel.teaser import shots as shots_mod
    tp = tmp_path / "teaser.json"
    shots_mod.dump(_teaser(), tp)
    out = _run("teaser-refs", str(tp), "--init", "--with-locations")
    assert out.returncode == 0, out.stderr
    man = rm.load(tmp_path / "refs.yaml")
    assert any(s.kind == "location" for s in man.subjects)


def test_cli_refs_plan_with_locations_json(tmp_path: Path) -> None:
    from autonovel.teaser import shots as shots_mod
    tp = tmp_path / "teaser.json"
    shots_mod.dump(_teaser(), tp)
    out = _run("teaser-refs-plan", str(tp), "--with-locations", "--format", "json")
    assert out.returncode == 0, out.stderr
    kinds = {e["kind"] for e in json.loads(out.stdout)["entries"]}
    assert "location" in kinds
