"""Tier-3 smoke: romance outline covers the four-beat structure.

Per REWRITE-PLAN §12 genre-specific test: outline covers the four-beat
structure (meet, conflict, dark-moment, resolution); final chapter
outline explicitly names the HEA or HFN state.
"""

from __future__ import annotations

import re

import pytest

from .conftest import run_command_in_runtime


FIXTURE_NAME = "tiny-series-romance"
BOOK_NAME = "book-one"

_BEATS = (
    ("meet", r"\bmeet\b|meet[\-\s]?cute"),
    ("conflict", r"\bconflict\b"),
    ("dark moment", r"dark[\-\s]?moment|all is lost|black moment"),
    ("resolution", r"\bresolution\b|reconcili"),
)


@pytest.mark.smoke
@pytest.mark.genre("romance")
def test_romance_outline_covers_four_beats(tmp_runtime_series) -> None:
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

    missing = [name for name, pat in _BEATS if not re.search(pat, lower)]
    assert not missing, f"romance outline missing beats: {missing}"

    # HEA / HFN explicitly named.
    assert re.search(r"\bHEA\b|happily[\-\s]?ever[\-\s]?after|\bHFN\b|happy[\-\s]?for[\-\s]?now", text, re.IGNORECASE), (
        "outline does not explicitly name HEA or HFN ending"
    )
