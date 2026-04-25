"""Tier-3 smoke: thriller outline carries stakes-escalation per chapter.

Per REWRITE-PLAN §12 genre-specific test: every chapter's outline entry
carries a stakes-escalation note; ≥1 chapter per act ends on an
explicit page-turn hook (external threat or revelation).
"""

from __future__ import annotations

import re

import pytest

from .conftest import run_command_in_runtime


FIXTURE_NAME = "tiny-series-thriller"
BOOK_NAME = "book-one"

_STAKES_KEYWORDS = (
    "stakes", "escalat", "raise", "raises", "ticking", "deadline",
    "page-turn", "hook", "cliffhanger",
)


@pytest.mark.smoke
@pytest.mark.genre("thriller")
def test_thriller_outline_has_stakes_escalation(tmp_runtime_series) -> None:
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

    chapter_pattern = re.compile(r"(?mi)^#{1,6}\s+Chapter\s+\d+\b.*$")
    starts = [m.start() for m in chapter_pattern.finditer(text)]
    assert starts, "outline has no `## Chapter N` headers"
    starts.append(len(text))

    chapters_missing_stakes: list[int] = []
    for i in range(len(starts) - 1):
        section = text[starts[i] : starts[i + 1]].lower()
        if not any(kw in section for kw in _STAKES_KEYWORDS):
            chapters_missing_stakes.append(i + 1)
    assert not chapters_missing_stakes, (
        f"chapters {chapters_missing_stakes} missing stakes/escalation note "
        f"(expected ≥1 of {_STAKES_KEYWORDS})"
    )

    # ≥1 page-turn hook somewhere in the outline.
    lower = text.lower()
    assert any(k in lower for k in ("page-turn", "page turn", "cliffhanger", "hook")), (
        "outline has no explicit page-turn / cliffhanger / hook line"
    )
