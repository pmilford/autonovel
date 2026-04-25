"""Tier-3 smoke: horror outline carries dread arc per chapter.

Per REWRITE-PLAN §12 genre-specific test: outline mentions a dread /
escalation arc; chapter outline entries carry sensory-specific imagery
rather than abstract scare beats. Presence-plus-nonempty, not score.
"""

from __future__ import annotations

import re

import pytest

from .conftest import run_command_in_runtime


FIXTURE_NAME = "tiny-series-horror"
BOOK_NAME = "book-one"

_DREAD_KEYWORDS = (
    "dread", "unease", "wrong", "creep", "tension",
    "menace", "foreboding", "uncanny",
)
_SENSORY_KEYWORDS = (
    "smell", "sound", "hum", "echo", "taste", "cold", "damp", "silence",
    "tremor", "scrape", "rustle", "chill", "dark", "warm", "humid",
)


@pytest.mark.smoke
@pytest.mark.genre("horror")
def test_horror_outline_has_dread_arc(tmp_runtime_series) -> None:
    series = tmp_runtime_series(FIXTURE_NAME)

    result = run_command_in_runtime(
        runtime="claude",
        command=f"/autonovel:gen-outline --book {BOOK_NAME}",
        cwd=series.path,
        allowed_tools=["Read", "Write", "Bash"],
        timeout=900,
    )
    assert result.returncode == 0, (
        f"claude returned {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    outline = series.path / "books" / BOOK_NAME / "outline.md"
    assert outline.is_file(), "books/book-one/outline.md not written"
    text = outline.read_text(encoding="utf-8")
    lower = text.lower()

    # ≥1 dread keyword somewhere.
    assert any(kw in lower for kw in _DREAD_KEYWORDS), (
        f"outline missing any dread/escalation cue ({_DREAD_KEYWORDS})"
    )

    # Each chapter section carries ≥1 sensory keyword.
    chapter_pattern = re.compile(r"(?mi)^#{1,6}\s+Chapter\s+\d+\b.*$")
    starts = [m.start() for m in chapter_pattern.finditer(text)]
    assert starts, "outline has no `## Chapter N` headers"
    starts.append(len(text))
    chapters_missing_sensory: list[int] = []
    for i in range(len(starts) - 1):
        section = text[starts[i] : starts[i + 1]].lower()
        if not any(kw in section for kw in _SENSORY_KEYWORDS):
            chapters_missing_sensory.append(i + 1)
    assert not chapters_missing_sensory, (
        f"chapters {chapters_missing_sensory} have no sensory specifics; "
        f"horror requires sensory-specific imagery over abstract scares"
    )
