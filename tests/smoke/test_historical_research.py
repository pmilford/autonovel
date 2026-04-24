"""Tier-3 smoke: `/autonovel:research` on a real historical topic with live web search.

This is the genre-specific test called out in REWRITE-PLAN.md §12
"Genre test — historical fiction live-search". It is intentionally
tolerant of web-search drift — it asserts the *shape* of the produced
notes file (cited, hedged, candidate canon entries present), not the
exact factual content.

Flakiness policy (REWRITE-PLAN.md §12 "Flakiness policy"):
live web search is non-deterministic and the pytest retry-once policy
in `tests/conftest.py` already handles transient search failures. A
test that flips fail→pass across retries is tracked but not blocking.

Opt-in under `@pytest.mark.smoke`. Skips cleanly when `claude` is not
on `$PATH` (see `tests/smoke/conftest.py`). Subscription auth is
primary; set `AUTONOVEL_SMOKE_USE_API_KEY=1` to bill via API key.
"""

from __future__ import annotations

import re

import pytest
import yaml

from .conftest import run_command_in_runtime


# The canonical historical research test. Topic is period-specific
# (1400-1600 Europe window, which is what `shared/period_bans.txt`
# ships pre-seeded for) and the `known_details` list is intentionally
# generous per §12.4 so ordinary web-search drift doesn't fail it.
HISTORICAL_TOPIC = "Venetian apothecaries 1520"
HISTORICAL_SLUG = "venetian-apothecaries-1520"

# Sources commonly surfaced for Venetian apothecary research; the notes
# file should hit at least two. Any two is enough — the test exists to
# catch gross failure (empty file, fabricated sources, ignored primary
# URLs), not to police exact recall.
HISTORICAL_KNOWN_DETAILS = (
    "theriac",
    "mithridate",
    "Zecca",
    "speziale",
    "Rialto",
    "bezoar",
    "aqua vitae",
    "guild",
    "Venice",
)


@pytest.mark.smoke
@pytest.mark.genre("historical")
def test_research_venetian_apothecaries_1520(tmp_runtime_series) -> None:
    series = tmp_runtime_series("tiny-series-historical")

    result = run_command_in_runtime(
        runtime="claude",
        command=f'/autonovel:research "{HISTORICAL_TOPIC}"',
        cwd=series.path,
        # Bash is needed by the preamble/postamble; Read/Write for the
        # notes file; WebSearch/WebFetch for the live research itself.
        allowed_tools=["Read", "Write", "Bash", "WebSearch", "WebFetch"],
        timeout=900,  # live web search can be slow
    )
    assert result.returncode == 0, (
        f"claude returned {result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    notes = series.path / "shared" / "research" / "notes" / f"{HISTORICAL_SLUG}.md"
    assert notes.exists(), f"notes file missing: {notes}"

    text = notes.read_text(encoding="utf-8")

    # 1. A sources section with at least two distinct [shortname] citations.
    assert "## Sources" in text, "notes file missing `## Sources` section"
    citations = set(re.findall(r"\[([a-zA-Z0-9][a-zA-Z0-9._-]*)\]", text))
    assert len(citations) >= 2, (
        f"expected ≥2 distinct [shortname] citations, found {sorted(citations)}"
    )

    # 2. At least one forced primary URL from sources.yaml appears in the notes.
    sources_yaml = series.path / "shared" / "research" / "sources.yaml"
    data = yaml.safe_load(sources_yaml.read_text(encoding="utf-8")) or {}
    entries = data.get("sources", []) or []
    primary_urls = [s["url"] for s in entries if s.get("weight") == "primary"]
    assert primary_urls, (
        "tiny-series-historical fixture lost its primary URL; check "
        "tests/fixtures/tiny-series-historical/shared/research/sources.yaml"
    )
    assert any(u in text for u in primary_urls), (
        f"none of the primary URLs {primary_urls} appear in the notes file"
    )

    # 3. Period-specific detail from the generous keyword list (≥2 hits).
    text_lower = text.lower()
    detail_hits = [d for d in HISTORICAL_KNOWN_DETAILS if d.lower() in text_lower]
    assert len(detail_hits) >= 2, (
        f"notes file contains fewer than 2 known period details; "
        f"hits: {detail_hits}"
    )

    # 4. Uncertainty is flagged somewhere.
    assert any(
        marker in text
        for marker in ("Speculative", "Uncertain", "Needs verification")
    ), "notes file has no uncertainty hedge; research should flag what it doesn't know"

    # 5. Candidate canon entries section exists.
    assert "## Candidate Canon Entries" in text, (
        "notes file missing `## Candidate Canon Entries` section"
    )
