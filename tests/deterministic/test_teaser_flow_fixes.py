"""Tier-1 tests for the run-feedback fixes (2026-06-07):

1. `teaser-refs --init --force` must NOT wipe locked/approved entries —
   re-scaffold preserves every declared entry (data-loss bug from a real run).
2. Teaser commands' postamble next-step chains into the teaser flow
   (`teaser-render → teaser-assemble`), not "draft chapter N+1".
3. The narrative-gate refusal names the regenerate fix when the spine is
   absent.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.teaser import refmanifest as rm
from autonovel.teaser import shots as shots_mod
from autonovel.teaser.shots import Shot, Teaser
from autonovel.housekeeping.lifecycle import _teaser_next_step


def _run(*argv):
    return subprocess.run([sys.executable, "-m", "autonovel.mechanical", *argv],
                          capture_output=True, text=True)


def _teaser():
    return Teaser(title="T", shots=[
        Shot(id="01", subject_name="JAKOB", subject_appearance="boy", action="a", setting="Venice"),
        Shot(id="02", subject_name="ANNA", subject_appearance="x", action="b", setting="Augsburg"),
    ])


# ----------------- fix 1: re-scaffold preserves locked entries -----------


def test_scaffold_preserves_locked_entry() -> None:
    existing = rm.RefManifest(subjects=[rm.CharacterRef(
        subject="JAKOB", source="wikimedia", source_ref="File:Durer.jpg",
        appearance="fur-collared merchant", status="locked",
        ref_path="refs/jakob_ref.png", voice="gravelly",
        appearance_ages=[{"name": "man", "appearance": "a man of forty", "from_year": 1510}])])
    merged = rm.scaffold_from_teaser(_teaser(), preserve=existing)
    j = merged.get("JAKOB")
    assert j.status == "locked" and j.source == "wikimedia"
    assert j.ref_path == "refs/jakob_ref.png" and j.voice == "gravelly"
    assert j.appearance_ages  # age ladder survived
    assert j.shots == ["01"]  # shots refreshed from the new plan
    assert merged.get("ANNA").status == "pending"  # genuinely-new subject added


def test_scaffold_retains_orphan_locked_subject() -> None:
    existing = rm.RefManifest(subjects=[rm.CharacterRef(
        subject="GHOST", status="locked", ref_path="refs/ghost.png")])
    merged = rm.scaffold_from_teaser(_teaser(), preserve=existing)
    assert merged.get("GHOST") is not None and merged.get("GHOST").status == "locked"


def test_cli_init_force_preserves_locked(tmp_path: Path) -> None:
    tp = tmp_path / "teaser.json"
    shots_mod.dump(_teaser(), tp)
    # Hand-locked manifest on disk
    rm.dump(rm.RefManifest(subjects=[rm.CharacterRef(
        subject="JAKOB", source="wikimedia", source_ref="File:Durer.jpg",
        status="locked", ref_path="refs/jakob_ref.png")]),
        tmp_path / "refs.yaml")
    out = _run("teaser-refs", str(tp), "--init", "--force")
    assert out.returncode == 0, out.stderr
    assert "Preserved 1 approved/locked" in out.stdout
    back = rm.load(tmp_path / "refs.yaml")
    assert back.get("JAKOB").status == "locked"      # NOT wiped to pending
    assert back.get("JAKOB").source_ref == "File:Durer.jpg"
    assert back.get("ANNA").status == "pending"


# ----------------- fix 2: teaser-flow next step --------------------------


def test_teaser_next_step_chains_within_flow() -> None:
    cases = {
        "autonovel:teaser-render": "teaser-assemble",
        "autonovel:shot-prompts": "teaser-critique",
        "autonovel:teaser-beats": "shot-prompts",
        "autonovel:teaser-critique": "teaser-render",
        "autonovel:teaser-refs": "teaser-render",
        "autonovel:treatment": "teaser",
    }
    for cmd, expect in cases.items():
        ns = _teaser_next_step(cmd, "medieval-king-maker")
        assert ns is not None, cmd
        assert expect in ns.command, (cmd, ns.command)
        assert "draft" not in ns.command  # never the chapter pipeline
        assert "medieval-king-maker" in ns.command


def test_non_teaser_command_falls_through() -> None:
    assert _teaser_next_step("autonovel:draft", "x") is None
    assert _teaser_next_step("autonovel:evaluate", "x") is None


# ----------------- fix 3: gate names the regenerate fix ------------------


def test_gate_message_points_at_regenerate_when_spine_absent(tmp_path: Path) -> None:
    p = tmp_path / "teaser.json"
    p.write_text(json.dumps({
        "title": "T", "length_s": 8, "provider": "veo", "shots": [
            {"id": "01", "role": "hook", "duration_s": 4,
             "subject": {"name": "J", "appearance": "x"}, "action": "a", "palette": ["amber"]},
            {"id": "02", "role": "button", "duration_s": 4,
             "subject": {"name": "J", "appearance": "x"}, "action": "b", "palette": ["amber"]},
        ]}), encoding="utf-8")  # no spine block
    out = _run("teaser-render", str(p), "--provider", "veo", "--kind", "video")
    assert out.returncode == 3
    assert "NO `spine` block" in out.stderr
    assert "--force" in out.stderr
