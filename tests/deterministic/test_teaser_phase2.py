"""Tier-1 tests for movie-teaser Phase 2: per-provider render dialects
and the reference-image consistency plan.

Format translation + filesystem facts only — no quality judgement
(feedback_avoid_brittle_python).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.teaser import refs, render_prompt
from autonovel.teaser import shots as shots_mod
from autonovel.teaser.shots import Shot, Teaser


def _shot(**kw) -> Shot:
    base = dict(
        id="S01", role="hook", duration_s=5.0, shot_size="wide",
        camera_angle="eye-level",
        subject_name="JAKOB", subject_appearance="14yo, plain wool doublet",
        action="He looks up from the ledger", setting="Venice Rialto",
        lighting="torchlight", palette=["amber", "slate"], camera_movement="push in",
        lens="85mm", style="35mm film", mood="awe", negative_prompt="blurry",
        reference_image="refs/jakob.png",
    )
    base.update(kw)
    return Shot(**base)


def _run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", *argv],
        capture_output=True, text=True,
    )


# ------------------------------ dialects ---------------------------------


def test_visual_prose_for_veo_and_generic() -> None:
    s = _shot()
    assert render_prompt.render_visual(s, "veo") == render_prompt.render_prose(s)
    assert render_prompt.render_visual(s, "generic") == render_prompt.render_prose(s)


def test_runway_dialect_is_terse_comma_separated() -> None:
    s = _shot()
    terse = render_prompt.render_visual(s, "runway")
    # No sentence periods between fields; uses commas.
    assert ". " not in terse
    assert "wide, eye-level" in terse
    assert "JAKOB (14yo, plain wool doublet)" in terse
    # palette joined with slash in terse/enum form.
    assert "amber/slate palette" in terse


def test_luma_dialect_maps_camera_to_enum() -> None:
    s = _shot(camera_movement="push in")
    enum = render_prompt.render_visual(s, "luma")
    assert "Camera: Push In" in enum
    # Unknown moves pass through verbatim.
    assert render_prompt.luma_camera("vertigo dolly-zoom") == "vertigo dolly-zoom"
    assert render_prompt.luma_camera("ORBIT") == "Orbit Left"


def test_render_markdown_shows_dialect() -> None:
    md = render_prompt.render_markdown(_shot(), "runway")
    assert "*Dialect:* runway" in md


# ----------------------------- refs plan ---------------------------------


def test_refs_plan_groups_subjects_and_flags_missing(tmp_path: Path) -> None:
    t = Teaser(title="X", shots=[
        _shot(id="S01", subject_name="Jakob", reference_image="refs/jakob.png"),
        _shot(id="S02", role="button", subject_name="Jakob", reference_image="refs/jakob.png"),
        _shot(id="S03", subject_name="Ulrich", reference_image="refs/ulrich.png"),
    ])
    plan = refs.plan_refs(t, base_dir=tmp_path)
    assert len(plan.entries) == 2  # two distinct subjects
    jakob = next(e for e in plan.entries if e.subject == "Jakob")
    assert jakob.shots == ["S01", "S02"]
    assert not jakob.exists  # nothing on disk yet
    assert len(plan.missing) == 2


def test_refs_plan_finds_existing_and_shared_plate(tmp_path: Path) -> None:
    (tmp_path / "refs").mkdir()
    (tmp_path / "refs" / "jakob.png").write_bytes(b"\x89PNG")
    shared = tmp_path / "art_references"
    shared.mkdir()
    (shared / "ulrich.png").write_bytes(b"\x89PNG")
    t = Teaser(title="X", shots=[
        _shot(id="S01", subject_name="Jakob", reference_image="refs/jakob.png"),
        _shot(id="S02", role="button", subject_name="Ulrich", reference_image="refs/ulrich.png"),
    ])
    plan = refs.plan_refs(t, base_dir=tmp_path, art_references_dir=shared)
    jakob = next(e for e in plan.entries if e.subject == "Jakob")
    ulrich = next(e for e in plan.entries if e.subject == "Ulrich")
    assert jakob.exists and jakob.source == "teaser"
    assert ulrich.exists and ulrich.source == "art_references"
    assert ulrich.suggested_ref and ulrich.suggested_ref.endswith("ulrich.png")
    assert plan.missing == []


def test_refs_plan_notes_appearance_drift() -> None:
    t = Teaser(title="X", shots=[
        _shot(id="S01", subject_name="Jakob", subject_appearance="young, plain"),
        _shot(id="S02", role="button", subject_name="Jakob", subject_appearance="old, fur"),
    ])
    plan = refs.plan_refs(t)
    jakob = plan.entries[0]
    assert jakob.appearance_variants == 2


def test_cli_teaser_refs_plan_json(tmp_path: Path) -> None:
    t = Teaser(title="X", shots=[_shot(id="S01", subject_name="Jakob")])
    p = tmp_path / "teaser.json"
    shots_mod.dump(t, p)
    out = _run("teaser-refs-plan", str(p), "--format", "json")
    assert out.returncode == 0
    data = json.loads(out.stdout)
    assert data["subject_count"] == 1
    assert data["entries"][0]["subject"] == "Jakob"
