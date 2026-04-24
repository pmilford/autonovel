"""Tier-1 deterministic tests for `autonovel.mechanical.slop`.

These lock in the regex-only scoring surface so the Tier-4 Bells
regression harness has a stable floor. Changing any of these tests
requires re-freezing the Bells reference scores.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from autonovel.mechanical import (
    TIER1_BANNED,
    period_ban_hits,
    slop_score,
)


CLEAN_PROSE = (
    "The bells woke him before dawn. Cold stone pressed against his knee. "
    "Tommaso rose and pulled on his wool cloak, the lamp oil guttering beside the jug. "
    "Outside, fog lay thick on the canal like a second water, slow and patient. "
    "He could smell it before he saw it, salt and rope and the iron of a coming rain."
)


SLOPPY_PROSE = (
    "Importantly, let's delve into the multifaceted tapestry of his life.\n\n"
    "Furthermore, he utilized his paradigm to leverage the holistic endeavor.\n\n"
    "Moreover, a sense of dread washed over him. His eyes widened. "
    "The silence was heavy. A pang of sorrow. The air was thick with grief.\n\n"
    "Additionally, he felt a surge of rage. It's worth noting that he was angry. "
    "He was sad. She was terrified. They were nervous.\n\n"
    "In today's fast-paced modern world — we must — use — em — dashes — "
    "everywhere — to — sound — cool."
)


def test_clean_prose_has_low_penalty() -> None:
    report = slop_score(CLEAN_PROSE)
    assert report.slop_penalty < 1.0
    assert report.tier1_hits == []
    assert report.tier2_clusters == 0


def test_sloppy_prose_gets_heavy_penalty() -> None:
    report = slop_score(SLOPPY_PROSE)
    assert report.slop_penalty >= 5.0, f"expected heavy penalty, got {report.slop_penalty}"
    # At least one tier-1 hit ("delve", "multifaceted", "tapestry", "utilize", "paradigm",
    # "leverage", "holistic", "endeavor").
    assert len(report.tier1_hits) >= 3
    # Em dash abuse.
    assert report.em_dash_density > 15


def test_penalty_is_capped_at_ten() -> None:
    # Worst-case-ish: every tier-1 word, every filler, every fiction tell.
    text = " ".join(TIER1_BANNED) + " " + SLOPPY_PROSE * 5
    report = slop_score(text)
    assert report.slop_penalty <= 10.0


def test_report_to_dict_is_json_serialisable() -> None:
    report = slop_score(SLOPPY_PROSE)
    # Must survive a round trip through json.
    payload = json.dumps(report.to_dict())
    assert "slop_penalty" in payload


def test_tier3_anchored_patterns_fire_at_line_start() -> None:
    report = slop_score("Importantly, he rose.\n\nMoreover, he walked.\n\nThe end.")
    patterns = [p for p, _ in report.tier3_hits]
    assert any("importantly" in p.lower() for p in patterns)
    assert any("moreover" in p.lower() for p in patterns)


def test_period_ban_hits_case_insensitive_word_boundary() -> None:
    bans = ["potato", "television", "# commented-out"]
    text = "He ate a potato. The potato was cold. He turned on the television."
    hits = dict(period_ban_hits(text, bans))
    assert hits == {"potato": 2, "television": 1}


def test_period_ban_hits_respects_word_boundary() -> None:
    # "potato" should not match "potatoes"
    hits = period_ban_hits("potatoes and yams", ["potato"])
    assert hits == []


def test_cli_slop_emits_valid_json(tmp_path) -> None:
    p = tmp_path / "ch.md"
    p.write_text(SLOPPY_PROSE, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "slop", str(p)],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert "slop_penalty" in data
    assert data["slop_penalty"] > 0


def test_cli_period_bans(tmp_path) -> None:
    chapter = tmp_path / "ch.md"
    bans = tmp_path / "bans.txt"
    chapter.write_text("The potato sat on the television.", encoding="utf-8")
    bans.write_text("# bans\npotato\ntelevision\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "period-bans", str(chapter), str(bans)],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert data["total"] == 2
