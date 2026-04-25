"""Tier-3 smoke: literary voice-discovery produces distinct trials.

Per REWRITE-PLAN §12 genre-specific test: `/autonovel:voice-discovery`
produces ≥5 distinct trial passages and picks one with a written
justification. We check for distinctness structurally (each trial is
labelled, non-empty, and non-identical to any other).
"""

from __future__ import annotations

import difflib
import re

import pytest

from .conftest import run_command_in_runtime


FIXTURE_NAME = "tiny-series-literary"
BOOK_NAME = "book-one"


def _extract_trials(text: str) -> list[str]:
    """Pull out each trial passage body.

    Voice-discovery output convention (from commands/voice-discovery.md):
    numbered trial sections like `## Trial 1` or `### Trial 1 — <tag>`
    followed by the sample prose. We collect the bodies so we can test
    pairwise distinctness.
    """
    parts = re.split(r"(?mi)^#{1,6}\s+Trial\s+\d+\b.*$", text)
    return [p.strip() for p in parts[1:] if p.strip()]


@pytest.mark.smoke
@pytest.mark.genre("literary")
def test_literary_voice_discovery_produces_distinct_trials(tmp_runtime_series) -> None:
    series = tmp_runtime_series(FIXTURE_NAME)

    result = run_command_in_runtime(
        runtime="claude",
        command=f"/autonovel:voice-discovery --book {BOOK_NAME}",
        cwd=series.path,
        allowed_tools=["Read", "Write", "Bash"],
        timeout=900,
    )
    assert result.returncode == 0, (
        f"claude returned {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    voice = series.path / "books" / BOOK_NAME / "voice.md"
    assert voice.is_file(), "books/book-one/voice.md not written"
    text = voice.read_text(encoding="utf-8")

    trials = _extract_trials(text)
    assert len(trials) >= 5, (
        f"voice-discovery produced {len(trials)} trial passages; ≥5 required"
    )

    # Pairwise distinctness — no two trials may be ≥0.9 similar by
    # SequenceMatcher. That is a generous threshold; near-identical
    # passages differ by more than 10% of tokens.
    for i in range(len(trials)):
        for j in range(i + 1, len(trials)):
            ratio = difflib.SequenceMatcher(None, trials[i], trials[j]).ratio()
            assert ratio < 0.9, (
                f"trials {i + 1} and {j + 1} are {ratio:.0%} similar — "
                "voice-discovery should produce distinct trial passages"
            )

    # A pick + justification section is expected.
    lower = text.lower()
    assert any(k in lower for k in ("selected", "chosen", "pick", "final voice")), (
        "voice.md has no selected/chosen-trial section"
    )
