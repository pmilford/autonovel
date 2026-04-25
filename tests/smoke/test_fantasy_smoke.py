"""Tier-3 smoke: fantasy magic system has costs/limits per power.

Per REWRITE-PLAN §12 genre-specific test: `/autonovel:gen-world` magic
system section has costs/limits for every listed power. Sanderson's
First Law: an author's ability to solve problems with magic is in
direct proportion to how well the reader understands said magic.
"""

from __future__ import annotations

import re

import pytest

from .conftest import run_command_in_runtime


FIXTURE_NAME = "tiny-series-fantasy"

_COST_KEYWORDS = (
    "cost", "limit", "limits", "price", "tradeoff", "trade-off",
    "consequence", "drawback", "requires", "drains",
)


@pytest.mark.smoke
@pytest.mark.genre("fantasy")
def test_fantasy_world_magic_has_costs(tmp_runtime_series) -> None:
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
    assert world.is_file(), "shared/world.md not written"
    text = world.read_text(encoding="utf-8")

    # Find the magic-system section heading.
    magic_match = re.search(
        r"(?mi)^#{1,6}\s+(?:magic|magic system|the magic system)\b.*$", text
    )
    assert magic_match, "world.md missing a Magic System section heading"

    # Section body up to the next heading of equal or higher level.
    start = magic_match.end()
    rest = text[start:]
    next_heading = re.search(r"(?m)^#{1,6}\s+\S", rest)
    section = rest if not next_heading else rest[: next_heading.start()]

    # Pull bullet powers; require each carries a cost keyword.
    bullets = re.findall(r"(?m)^[\-\*]\s+(.+)$", section)
    assert bullets, "magic system section has no bulleted powers"

    powers_without_cost = [b for b in bullets if not any(k in b.lower() for k in _COST_KEYWORDS)]
    assert not powers_without_cost, (
        f"{len(powers_without_cost)} magic-system bullet(s) lack a cost/limit clause: "
        f"{powers_without_cost}"
    )
