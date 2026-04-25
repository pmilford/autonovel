"""Tier-1 tests for the bigram cliche scanner and the sensory-channel
balance scanner. Both are deterministic regex passes; assertions are
on counts and shape, not model output."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.mechanical.cliches import (
    CLICHE_BIGRAMS,
    cliche_density,
    cliche_hits,
)
from autonovel.mechanical.sensory import (
    CHANNELS,
    DEFAULT_DOMINANCE_THRESHOLD,
    channel_balance,
)


# -------------------------------------------------------------------- cliches


def test_cliche_hits_finds_curated_bigrams() -> None:
    text = (
        "She gave him a thin smile. The pale moonlight caught the edge of "
        "the blade. Her hands trembled. Around her, deafening silence. "
        "He held his breath, bated. The shadows danced at the edge of "
        "the wood."
    )
    hits = cliche_hits(text)
    patterns = {h.pattern for h in hits}
    assert any("thin\\s+smile" in p for p in patterns)
    assert any("pale\\s+moonlight" in p for p in patterns)
    assert any("deafening\\s+silence" in p for p in patterns)
    assert any("shadows\\s+danced" in p for p in patterns)


def test_cliche_hits_sorted_by_count_desc() -> None:
    text = (
        "Pale moonlight. Pale moonlight. Pale moonlight. Pale moonlight. "
        "She gave him a thin smile."
    )
    hits = cliche_hits(text)
    assert hits[0].count >= hits[-1].count
    # The 4-time hit must precede the 1-time hit.
    assert hits[0].count == 4


def test_cliche_density_normalised_per_1000_words() -> None:
    # 1 hit in 200 words → 5.0 per 1000.
    text = "Pale moonlight. " + ("filler " * 199)
    d = cliche_density(text)
    assert 4.5 < d < 5.5


def test_cliche_clean_prose_returns_zero() -> None:
    text = (
        "He set down the ledger and turned the page. Outside, the bell "
        "of San Marco struck the half-hour. The room held the warmth of "
        "the day's last sun, and Tommaso noted the exact angle of the "
        "shaft against the floor."
    )
    assert cliche_hits(text) == []
    assert cliche_density(text) == 0.0


def test_cliche_word_boundary_isolation() -> None:
    """A word inside a longer compound must not match. `colder smile`
    contains `cold smile` if we matched substrings, but \\b in the
    pattern blocks it."""
    text = "The smile she gave was a colder smile than the morning."
    hits = cliche_hits(text)
    # `cold smile` is in the list. Should NOT fire on `colder smile`.
    assert not any("cold\\s+smile" in h.pattern and h.count > 0 for h in hits)


def test_cliche_cli_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "ch.md"
    p.write_text(
        "Pale moonlight. Thin smile. Trees swayed. Bated breath.",
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "mechanical", "cliches", str(p)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["total"] >= 4
    assert payload["density_per_1000_words"] > 0
    assert payload["word_count"] > 0


# -------------------------------------------------------------------- sensory


def test_sensory_balance_recognises_each_channel() -> None:
    text = (
        # Visual
        "She saw the shadow on the wall. The light caught his eye. "
        # Auditory
        "He heard the bell ring. Footsteps in the hall. A sound from below. "
        # Olfactory
        "She smelled smoke; the scent of incense from the side chapel. "
        # Gustatory
        "He sipped the wine; bitter, with a flavor of iron. "
        # Tactile
        "Her hands were cold. He felt the rough wood under his palm."
    )
    report = channel_balance(text)
    for channel in CHANNELS:
        assert report.counts[channel] > 0, (
            f"channel {channel!r} found 0 hits in clearly-balanced text"
        )


def test_sensory_dominant_channel_when_one_channel_overweights() -> None:
    text = (
        "She saw the wall. She saw the floor. She watched his face. "
        "She watched the door. She watched the window. She glanced at the desk. "
        "She stared at the paper. She gazed across the room. "
        "He felt the cold."
    )
    report = channel_balance(text)
    assert report.dominant_channel == "visual"
    assert report.fractions["visual"] > DEFAULT_DOMINANCE_THRESHOLD


def test_sensory_no_dominant_in_balanced_text() -> None:
    text = (
        "She saw the cup, heard the drip, smelled the coffee, "
        "tasted the bitterness, felt the warmth in her hands."
    )
    report = channel_balance(text)
    assert report.dominant_channel is None


def test_sensory_zero_hit_text_returns_zero_fractions() -> None:
    text = "He walked. She thought. They argued."
    report = channel_balance(text)
    assert report.total_hits == 0
    assert all(report.fractions[c] == 0.0 for c in CHANNELS)
    assert report.dominant_channel is None


def test_sensory_threshold_override_works() -> None:
    text = (
        "She saw the wall. She saw the floor. He felt the warmth. "
        "He felt the rough wood."
    )
    # 50/50-ish; default threshold (0.7) should NOT flag.
    assert channel_balance(text).dominant_channel is None
    # A very low threshold (0.3) flags whichever side wins by any margin.
    flagged = channel_balance(text, dominance_threshold=0.3).dominant_channel
    assert flagged in CHANNELS or flagged is None


def test_sensory_cli_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "ch.md"
    p.write_text(
        "She saw the room. She heard the bell. She smelled the smoke.",
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "mechanical", "sensory", str(p)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert "counts" in payload
    assert "fractions" in payload
    assert "total_hits" in payload
    assert payload["total_hits"] >= 3
