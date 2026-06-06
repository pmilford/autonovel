"""Tier-1 tests for movie-teaser Phase 5: character-reference manifest
+ approval status. Pure data + filesystem; no network, no LLM (the
picking/approving/fetching are the command-body steps)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.teaser import refmanifest as rm
from autonovel.teaser import shots as shots_mod
from autonovel.teaser.shots import Shot, Teaser


def _teaser(*subjects: str) -> Teaser:
    shots = []
    for i, subj in enumerate(subjects, 1):
        shots.append(Shot(
            id=f"{i:02d}", role="hook" if i == 1 else "escalation",
            duration_s=5.0, aspect_ratio="16:9", shot_size="wide",
            subject_name=subj, subject_appearance=f"{subj} appearance",
            action="acts", setting="Augsburg", palette=["amber"]))
    return Teaser(title="Fugger", provider="grok", shots=shots)


def _run(*argv):
    return subprocess.run([sys.executable, "-m", "autonovel.mechanical", *argv],
                          capture_output=True, text=True)


# ----------------------------- model / IO --------------------------------


def test_manifest_round_trip(tmp_path: Path) -> None:
    man = rm.RefManifest(subjects=[
        rm.CharacterRef(subject="JAKOB FUGGER", source="wikimedia",
                        source_ref="File:Dürer Fugger.jpg",
                        appearance="fur-collared merchant", status="approved",
                        ref_path="refs/jakob_fugger.png"),
    ])
    p = tmp_path / "refs.yaml"
    rm.dump(man, p)
    text = p.read_text(encoding="utf-8")
    assert text.startswith("#")  # header comment block
    back = rm.load(p)
    cr = back.get("jakob  fugger")  # slug-insensitive lookup
    assert cr is not None and cr.source == "wikimedia" and cr.approved


def test_load_rejects_non_mapping(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("- just\n- a\n- list\n", encoding="utf-8")
    try:
        rm.load(p)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError on non-mapping manifest")


def test_load_coerces_bad_enums(tmp_path: Path) -> None:
    p = tmp_path / "refs.yaml"
    p.write_text("subjects:\n  - subject: X\n    source: bogus\n    status: weird\n",
                 encoding="utf-8")
    cr = rm.load(p).get("X")
    assert cr.source == "generate" and cr.status == "pending"


# --------------------------- scaffold + status ---------------------------


def test_scaffold_from_teaser(tmp_path: Path) -> None:
    man = rm.scaffold_from_teaser(_teaser("JAKOB", "SCHWARZ"), base_dir=tmp_path)
    assert [c.subject for c in man.subjects] == ["JAKOB", "SCHWARZ"]
    assert all(c.status == "pending" and c.source == "generate" for c in man.subjects)


def test_status_next_actions(tmp_path: Path) -> None:
    teaser = _teaser("JAKOB", "SCHWARZ", "ANNA")
    # JAKOB: declared + plate exists + approved → ready
    (tmp_path / "refs").mkdir()
    (tmp_path / "refs" / "jakob.png").write_bytes(b"\x89PNG")
    man = rm.RefManifest(subjects=[
        rm.CharacterRef(subject="JAKOB", source="wikimedia",
                        source_ref="File:x.jpg", status="approved",
                        ref_path="refs/jakob.png"),
        # SCHWARZ: declared wikimedia but not on disk → fetch-source
        rm.CharacterRef(subject="SCHWARZ", source="wikimedia",
                        source_ref="File:y.jpg", status="pending",
                        ref_path="refs/schwarz.png"),
        # ANNA: omitted entirely → declare-source
    ])
    status = rm.build_status(teaser, man, base_dir=tmp_path)
    by = {r.subject: r for r in status.rows}
    assert by["JAKOB"].next_action == "ready"
    assert by["SCHWARZ"].next_action == "fetch-source"
    assert by["ANNA"].next_action == "declare-source"
    # approval gate
    assert set(status.unapproved_subjects()) == {"SCHWARZ", "ANNA"}
    assert status.to_dict()["all_approved"] is False


def test_status_approve_pending_plate(tmp_path: Path) -> None:
    teaser = _teaser("JAKOB")
    (tmp_path / "refs").mkdir()
    (tmp_path / "refs" / "jakob.png").write_bytes(b"\x89PNG")
    man = rm.RefManifest(subjects=[
        rm.CharacterRef(subject="JAKOB", source="local",
                        status="pending", ref_path="refs/jakob.png")])
    status = rm.build_status(teaser, man, base_dir=tmp_path)
    assert status.rows[0].next_action == "approve"  # exists but not approved


# ------------------------------- CLI -------------------------------------


def test_cli_init_then_status(tmp_path: Path) -> None:
    t = _teaser("JAKOB", "SCHWARZ")
    p = tmp_path / "teaser.json"
    shots_mod.dump(t, p)
    # --init scaffolds refs.yaml
    out = _run("teaser-refs", str(p), "--init")
    assert out.returncode == 0 and (tmp_path / "refs.yaml").exists()
    # re-init without --force refuses
    out2 = _run("teaser-refs", str(p), "--init")
    assert out2.returncode == 2
    # status JSON reflects the scaffolded (pending, generate) subjects
    out3 = _run("teaser-refs", str(p), "--format", "json")
    data = json.loads(out3.stdout)
    assert data["subject_count"] == 2
    assert data["all_approved"] is False
    assert {r["next_action"] for r in data["rows"]} == {"generate"}


def test_cli_status_no_manifest(tmp_path: Path) -> None:
    t = _teaser("JAKOB")
    p = tmp_path / "teaser.json"
    shots_mod.dump(t, p)
    out = _run("teaser-refs", str(p), "--format", "json")
    data = json.loads(out.stdout)
    assert data["manifest_exists"] is False
    assert data["rows"][0]["next_action"] == "declare-source"
