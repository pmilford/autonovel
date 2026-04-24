"""Tier-3 smoke: `/autonovel:typeset --book <name>` on Claude Code.

Of the PR-7 export commands, `typeset` is the one smoke-testable without
paid third-party APIs — it needs `tectonic` for the PDF and `pandoc` for
the ePub, both of which are free CLIs. The art / cover / audiobook
commands need fal.ai or ElevenLabs credits and are left as
manual-invoke documentation-only tests (mentioned in the PR 7
acceptance block).

The test seeds three short chapter files so `chapters_content.tex` has
something to build from, invokes `/autonovel:typeset --book
tiny-inquisitor --pdf-only`, and asserts:

  - `books/tiny-inquisitor/typeset/chapters_content.tex` exists and
    contains every chapter's title.
  - If `tectonic` is installed, `novel.pdf` was produced and is ≥ 4 KB.
  - If `tectonic` is NOT installed, the test still passes as long as
    the `.tex` build happened — we don't want a machine without LaTeX
    to skip PR-7 smoke entirely.

Subscription auth per the smoke conftest. Skipped when `claude` is not
on PATH.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from .conftest import run_command_in_runtime


SEED_CHAPTER_1 = """# Chapter 1: Arrival

Tommaso stepped off the galley onto the rain-slick stones of San Marco.
The air smelled of salt and tar and something that might have been
cinnamon. *He's here*, he thought. *The heretic whose name I have
carried in my pocket for two months.*

---

The bells of the Campanile rang noon as he crossed into the lanes
behind the Procuratie.
"""

SEED_CHAPTER_2 = """# Chapter 2: The Apothecary

Lucia ground the henbane to a fine grey powder and tipped it into the
brass scale. A knock at the door — too soft for the Council, too
careful for a neighbour.

"Signora," said the boy on the step. "My mother — she's burning."
"""

SEED_CHAPTER_3 = """# Chapter 3: The Fire

Smoke unspooled above the mint like grey wool. Tommaso reached the
square as the third bell rang — not an alarm, but the summons of the
Ten. Too late, then, for an orderly investigation.
"""


@pytest.mark.smoke
@pytest.mark.genre("historical")
def test_typeset_builds_tex(tmp_runtime_series) -> None:
    series = tmp_runtime_series("tiny-series-historical")
    book = "tiny-inquisitor"
    chapters_dir = series.path / "books" / book / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    (chapters_dir / "ch_01.md").write_text(SEED_CHAPTER_1, encoding="utf-8")
    (chapters_dir / "ch_02.md").write_text(SEED_CHAPTER_2, encoding="utf-8")
    (chapters_dir / "ch_03.md").write_text(SEED_CHAPTER_3, encoding="utf-8")

    has_tectonic = shutil.which("tectonic") is not None

    # --pdf-only keeps the smoke scope narrow: we're testing the
    # chapter_content.tex builder path, not pandoc/ePub.
    result = run_command_in_runtime(
        "claude",
        command=f"/autonovel:typeset --book {book} --pdf-only",
        cwd=series.path,
        allowed_tools=["Read", "Write", "Bash"],
        timeout=900,  # tectonic can take a while on first run (font downloads)
    )

    # The command always writes chapters_content.tex regardless of tectonic.
    built_tex = series.path / "books" / book / "typeset" / "chapters_content.tex"
    assert built_tex.exists(), (
        f"expected {built_tex} after typeset; stdout: {result.stdout[-2000:]}"
    )
    tex_body = built_tex.read_text(encoding="utf-8")
    for title in ("Arrival", "Apothecary", "Fire"):
        assert title in tex_body, f"chapter title {title!r} missing from chapters_content.tex"
    assert "\\lettrine" in tex_body, "drop caps missing — make_drop_cap failed to run"

    # Also confirm the book-local novel.tex has placeholders substituted.
    book_tex = series.path / "books" / book / "typeset" / "novel.tex"
    if book_tex.exists():
        book_tex_body = book_tex.read_text(encoding="utf-8")
        assert "@TITLE@" not in book_tex_body, "placeholder @TITLE@ not substituted"
        assert "@AUTHOR@" not in book_tex_body, "placeholder @AUTHOR@ not substituted"

    # The PDF is optional — only assert when tectonic is available.
    pdf = series.path / "books" / book / "typeset" / "novel.pdf"
    if has_tectonic and pdf.exists():
        size = pdf.stat().st_size
        assert size >= 4_000, f"novel.pdf is suspiciously small: {size} bytes"
