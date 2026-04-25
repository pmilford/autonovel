"""Tier-3 smoke: sci-fi world-building hard-rule check.

Per REWRITE-PLAN §12 genre-specific test: `/autonovel:gen-world` must
not hallucinate current-year facts. The produced `world.md` contains
no `[citation needed]` placeholders and the technology-rules section
has at least three explicit hard limits.

Flakiness is allowed (§12.4): the assertion is structural, not a
word-match on prose. Retry-once comes for free from the smoke marker.
"""

from __future__ import annotations

import re

import pytest

from .conftest import run_command_in_runtime


FIXTURE_NAME = "tiny-series-scifi"


@pytest.mark.smoke
@pytest.mark.genre("scifi")
def test_scifi_world_has_hard_limits(tmp_runtime_series) -> None:
    series = tmp_runtime_series(FIXTURE_NAME)

    result = run_command_in_runtime(
        runtime="claude",
        command="/autonovel:gen-world",
        cwd=series.path,
        allowed_tools=["Read", "Write", "Bash"],
        timeout=900,
    )
    assert result.returncode == 0, (
        f"claude returned {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    world = series.path / "shared" / "world.md"
    assert world.is_file(), "shared/world.md not written by /autonovel:gen-world"
    text = world.read_text(encoding="utf-8")

    # No lazy placeholders.
    assert "[citation needed]" not in text.lower(), (
        "world.md contains `[citation needed]` placeholders — "
        "gen-world should fill in or flag uncertainty, not defer"
    )

    # Technology rules section exists and has ≥3 bulleted hard limits.
    lower = text.lower()
    tech_markers = ("technology rules", "hard limits", "hard rules", "rules of technology")
    assert any(m in lower for m in tech_markers), (
        "world.md missing a technology-rules / hard-limits section — "
        f"looked for one of {tech_markers}"
    )

    bullets = re.findall(r"(?m)^[\-\*]\s+\S", text)
    assert len(bullets) >= 3, (
        f"world.md has {len(bullets)} bullet-list items overall; "
        "sci-fi fixture requires ≥3 explicit hard limits"
    )
