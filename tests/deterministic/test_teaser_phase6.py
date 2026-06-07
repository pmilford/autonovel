"""Tier-1 tests for movie-teaser Phase 6: teaser storytelling.

The render mechanics worked but the teaser read as a set of disconnected
clips — no throughline, no stakes, almost no dialogue. Phase 6 encodes the
**story spine** (dramatic question, logline, want vs. opposing force,
emotional arc, score direction) into the teaser data model, enforces it +
dialogue/text-card density via the mechanical critique, and versions the
generated scripts so a full pipeline re-run never destroys the previous
beats.md / teaser.json (while the refs/ originals are reused untouched).
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from autonovel.teaser import critique as crit
from autonovel.teaser import providers, takes
from autonovel.teaser.shots import Shot, Spine, Teaser


def _run(*argv):
    return subprocess.run([sys.executable, "-m", "autonovel.mechanical", *argv],
                          capture_output=True, text=True)


def _spine() -> Spine:
    return Spine(
        dramatic_question="Can a clerk outlast the bank that owns his country?",
        logline="A counting-house clerk takes on the empire's banker.",
        want="clear the forged ledger",
        opposing_force="the Fugger bank",
        emotional_arc="unease → dread → defiant hope",
        score_direction="a single building string ostinato",
    )


def _shot(sid="01", role="escalation", **kw):
    base = dict(id=sid, role=role, duration_s=4.0, subject_name="JAKOB",
                subject_appearance="ink-stained clerk", action="snaps the ledger shut",
                setting="counting-house", palette=["amber", "walnut"],
                reference_image="refs/jakob.png")
    base.update(kw)
    return Shot(**base)


def _full_teaser(provider="veo") -> Teaser:
    return Teaser(
        title="The Ledger", length_s=12, provider=provider, spine=_spine(),
        shots=[
            _shot("01", "hook", text_card="In a city built on debt",
                  audio={"dialogue": [{"speaker": "JAKOB", "line": "They said the books would balance."}]}),
            _shot("02", "button", text_card="One ledger could burn it down",
                  audio={"dialogue": [{"speaker": "JAKOB", "line": "Not while I can still count."}]}),
        ],
    )


# ------------------------------ Spine model ------------------------------


def test_spine_round_trips_through_teaser() -> None:
    t = _full_teaser()
    d = json.loads(json.dumps(t.to_dict()))
    assert "spine" in d
    t2 = Teaser.from_dict(d)
    assert t2.spine.dramatic_question == t.spine.dramatic_question
    assert t2.spine.want == "clear the forged ledger"
    assert t2.spine.opposing_force == "the Fugger bank"
    assert t2.spine.score_direction == "a single building string ostinato"


def test_empty_spine_is_omitted_from_json() -> None:
    """Existing teasers (no spine) round-trip byte-identical — additive."""
    t = Teaser(title="Y", shots=[_shot("1")])
    assert "spine" not in t.to_dict()
    assert Teaser.from_dict({"title": "Y", "shots": [_shot("1").to_dict()]}).spine.is_empty()


def test_dialogue_and_text_card_counts() -> None:
    t = _full_teaser()
    assert t.dialogue_line_count() == 2
    assert t.text_card_count() == 2


# --------------------------- critique: spine -----------------------------


def test_full_spine_teaser_has_no_spine_flags() -> None:
    rep = crit.critique(_full_teaser(), providers.get("veo"))
    codes = {f.code for f in rep.findings}
    for c in ("no-dramatic-question", "no-logline", "no-stakes",
              "no-emotional-arc", "thin-dialogue", "thin-text-cards"):
        assert c not in codes, (c, codes)


def test_missing_spine_raises_all_spine_flags() -> None:
    t = Teaser(title="T", length_s=12, provider="veo",
               shots=[_shot("01", "hook"), _shot("02", "button")])
    codes = {f.code for f in crit.critique(t, providers.get("veo")).findings}
    assert {"no-dramatic-question", "no-logline", "no-stakes",
            "no-emotional-arc"} <= codes


def test_partial_stakes_flags_no_stakes() -> None:
    sp = _spine()
    sp.opposing_force = ""  # want present, force missing → still a flag
    t = _full_teaser()
    t.spine = sp
    codes = {f.code for f in crit.critique(t, providers.get("veo")).findings}
    assert "no-stakes" in codes


def test_thin_dialogue_on_audio_provider() -> None:
    t = _full_teaser()
    # strip dialogue down to a single line across the teaser
    t.shots[1].audio = {}
    codes = {f.code for f in crit.critique(t, providers.get("veo")).findings}
    assert "thin-dialogue" in codes


def test_thin_dialogue_not_raised_for_silent_provider() -> None:
    """A no-native-audio provider can't speak lines — don't nag for them."""
    prof = providers.get("magichour")
    assert not prof.audio
    t = _full_teaser(provider="magichour")
    t.shots[0].audio = {}
    t.shots[1].audio = {}
    codes = {f.code for f in crit.critique(t, prof).findings}
    assert "thin-dialogue" not in codes


def test_thin_text_cards() -> None:
    t = _full_teaser()
    t.shots[1].text_card = None  # only one card left
    codes = {f.code for f in crit.critique(t, providers.get("veo")).findings}
    assert "thin-text-cards" in codes


# ----------------------- script versioning (re-run) ----------------------


def test_archive_script_keeps_prior_versions(tmp_path: Path) -> None:
    f = tmp_path / "beats.md"
    f.write_text("v1", encoding="utf-8")
    when = datetime(2026, 6, 6, 12, 0)
    a1 = takes.archive_script(f, when=when)
    assert a1 is not None and a1.exists() and a1.read_text() == "v1"
    assert a1.parent.name == "script-takes"
    f.write_text("v2", encoding="utf-8")
    a2 = takes.archive_script(f, when=when)  # same minute → suffixed, never clobbers
    assert a2 is not None and a2 != a1
    assert a2.read_text() == "v2"
    assert a1.read_text() == "v1"  # the first archive is preserved


def test_archive_script_noop_on_missing(tmp_path: Path) -> None:
    assert takes.archive_script(tmp_path / "nope.json") is None


# ---------------- bp 9 genre / bp 3 stakes ladder (model) ----------------


def test_genre_and_stakes_level_round_trip() -> None:
    sp = _spine()
    sp.genre = "historical thriller"
    t = Teaser(title="T", length_s=12, provider="veo", spine=sp,
               shots=[_shot("02", "escalation", stakes_level=3)])
    t2 = Teaser.from_dict(json.loads(json.dumps(t.to_dict())))
    assert t2.spine.genre == "historical thriller"
    assert t2.shots[0].stakes_level == 3
    # stakes_level omitted when None
    assert "stakes_level" not in _shot("9", "hook").to_dict()


def test_no_genre_flag() -> None:
    t = _full_teaser()  # _spine() has no genre
    codes = {f.code for f in crit.critique(t, providers.get("veo")).findings}
    assert "no-genre" in codes


# ----------------------- bp 2 four-act role order ------------------------


def _arc_teaser(roles, **spine_kw):
    sp = _spine()
    sp.genre = "thriller"
    for k, v in spine_kw.items():
        setattr(sp, k, v)
    shots = []
    for i, r in enumerate(roles):
        s = _shot(f"{i:02d}", r, text_card=("card" if i < 2 else None),
                  audio={"dialogue": [{"speaker": "JAKOB", "line": f"line {i}"}]} if i < 2 else {})
        if r == "escalation":
            s.stakes_level = i  # rising by construction
        shots.append(s)
    return Teaser(title="T", length_s=len(roles) * 4, provider="veo", spine=sp, shots=shots)


def test_role_order_clean() -> None:
    t = _arc_teaser(["hook", "escalation", "escalation", "title", "button"])
    codes = {f.code for f in crit.critique(t, providers.get("veo")).findings}
    for c in ("hook-not-first", "multiple-hooks", "no-title", "button-not-last",
              "title-after-button", "no-stakes-ladder", "stakes-not-rising"):
        assert c not in codes, (c, codes)


def test_hook_not_first_and_button_not_last() -> None:
    t = _arc_teaser(["escalation", "hook", "title", "button", "escalation"])
    codes = {f.code for f in crit.critique(t, providers.get("veo")).findings}
    assert "hook-not-first" in codes
    assert "button-not-last" in codes


def test_no_title_flag() -> None:
    t = _arc_teaser(["hook", "escalation", "button"])
    codes = {f.code for f in crit.critique(t, providers.get("veo")).findings}
    assert "no-title" in codes


def test_multiple_hooks_flag() -> None:
    t = _arc_teaser(["hook", "hook", "title", "button"])
    codes = {f.code for f in crit.critique(t, providers.get("veo")).findings}
    assert "multiple-hooks" in codes


# --------------------- bp 3 stakes ladder enforcement --------------------


def test_no_stakes_ladder_when_unranked() -> None:
    sp = _spine(); sp.genre = "thriller"
    t = Teaser(title="T", length_s=12, provider="veo", spine=sp, shots=[
        _shot("01", "hook"), _shot("02", "escalation"),  # no stakes_level
        _shot("03", "title"), _shot("04", "button")])
    codes = {f.code for f in crit.critique(t, providers.get("veo")).findings}
    assert "no-stakes-ladder" in codes


def test_stakes_not_rising_when_dips() -> None:
    sp = _spine(); sp.genre = "thriller"
    t = Teaser(title="T", length_s=12, provider="veo", spine=sp, shots=[
        _shot("01", "hook"),
        _shot("02", "escalation", stakes_level=3),
        _shot("03", "escalation", stakes_level=1),  # dip
        _shot("04", "title"), _shot("05", "button")])
    codes = {f.code for f in crit.critique(t, providers.get("veo")).findings}
    assert "stakes-not-rising" in codes
    assert "no-stakes-ladder" not in codes  # all ranked → ladder check, not missing


# ------------------------ bp 11 one hero face ----------------------------


def test_cast_sprawl_flag() -> None:
    t = _full_teaser()
    t.shots[0].subject_name = "A"
    t.shots.append(_shot("03", "escalation", subject_name="B"))
    t.shots.append(_shot("04", "escalation", subject_name="C"))
    t.shots.append(_shot("05", "escalation", subject_name="D"))  # 4 distinct
    codes = {f.code for f in crit.critique(t, providers.get("veo")).findings}
    assert "cast-sprawl" in codes


# ----------------- bp 12 render narrative gate (story-ready) --------------


def test_story_gate_helpers() -> None:
    bad = crit.critique(Teaser(title="T", provider="veo",
                               shots=[_shot("01", "hook")]), providers.get("veo"))
    assert not crit.story_ready(bad)
    assert {f.code for f in crit.story_gate_failures(bad)} <= set(crit.STORY_GATE_CODES)
    good = _arc_teaser(["hook", "escalation", "escalation", "title", "button"])
    good.spine.genre = "thriller"
    assert crit.story_ready(crit.critique(good, providers.get("veo")))


def _storyless(tmp_path: Path) -> Path:
    p = tmp_path / "teaser.json"
    p.write_text(json.dumps({
        "title": "T", "length_s": 8, "provider": "veo", "shots": [
            {"id": "01", "role": "hook", "duration_s": 4,
             "subject": {"name": "J", "appearance": "x"}, "action": "a", "palette": ["amber"]},
            {"id": "02", "role": "button", "duration_s": 4,
             "subject": {"name": "J", "appearance": "x"}, "action": "b", "palette": ["amber"]},
        ]}), encoding="utf-8")
    return p


def test_render_gate_blocks_real_provider(tmp_path: Path) -> None:
    out = _run("teaser-render", str(_storyless(tmp_path)), "--provider", "veo",
               "--kind", "video")
    assert out.returncode == 3, (out.returncode, out.stderr)
    assert "narrative gate" in out.stderr


def test_render_gate_exempts_stub(tmp_path: Path) -> None:
    out = _run("teaser-render", str(_storyless(tmp_path)), "--provider", "stub",
               "--kind", "image")
    assert out.returncode == 0, out.stderr
    assert "narrative gate" not in out.stderr


def test_render_gate_skip_override(tmp_path: Path) -> None:
    out = _run("teaser-render", str(_storyless(tmp_path)), "--provider", "veo",
               "--kind", "video", "--skip-narrative-gate")
    assert out.returncode != 3  # gate bypassed (may fail later on missing key)


def test_render_gate_dry_run_reports_block(tmp_path: Path) -> None:
    out = _run("teaser-render", str(_storyless(tmp_path)), "--provider", "veo",
               "--kind", "video", "--dry-run", "--format", "json")
    assert out.returncode == 0, out.stderr
    payload = json.loads(out.stdout)
    assert payload["narrative_gate_blocks"] is True
    assert "no-dramatic-question" in payload["narrative_gate_flags"]


def test_archive_script_cli_round_trip(tmp_path: Path) -> None:
    t = tmp_path / "teaser.json"
    t.write_text('{"title":"T","provider":"veo","shots":[]}', encoding="utf-8")
    out = _run("teaser-archive-script", str(t), "--format", "json")
    assert out.returncode == 0, out.stderr
    payload = json.loads(out.stdout)
    assert payload["archived"] and Path(payload["archived"]).exists()
    # missing file → no-op, still exit 0
    out2 = _run("teaser-archive-script", str(tmp_path / "missing.json"), "--format", "json")
    assert out2.returncode == 0
    assert json.loads(out2.stdout)["archived"] is None
