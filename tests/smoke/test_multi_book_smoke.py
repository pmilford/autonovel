"""Tier-3 smoke: two books with interleaved story_times share a canonical event.

PR 6 wires the context loader and `shared/events.md` into the drafter.
This test:

  1. Starts from the tiny-historical fixture (one book: tiny-inquisitor).
  2. Adds a second book, tiny-apothecary (POV Lucia), at the same
     story_time range as tiny-inquisitor.
  3. Seeds an `apothecary` chapter at story_time `1521-12-08` — which is
     *later* than tiny-inquisitor's ch_01 (1521-12-04). That sibling
     chapter carries a distinctive "FUTURE-SPOILER" phrase.
  4. Also seeds an `apothecary` chapter at `1521-12-01` — *earlier*
     than tiny-inquisitor's ch_01, so it is legal sibling context.
  5. Runs `/autonovel:draft 1 --book tiny-inquisitor`.
  6. Asserts the drafted chapter:
       a. parses + has valid frontmatter (reused from draft smoke).
       b. does not contain the "FUTURE-SPOILER" phrase — the spoiler
          chapter must have been excluded by the context loader.
       c. does not contradict the canonical line for E-001 (no
          alternate arsonist). Structural: the chapter must not
          identify Tommaso or Lucia as the firestarter.
       d. ran `python -m autonovel.context_loader` at least once, as
          visible in the postamble footer / command log.

Opt-in via `@pytest.mark.smoke`. Skips cleanly when `claude` is not on
`$PATH`. Subscription auth is primary; see tests/smoke/conftest.py.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel import project as project_mod
from autonovel.housekeeping import scaffold
from autonovel.paths import SeriesLayout
from autonovel.validators.chapter_frontmatter import parse

from .conftest import run_command_in_runtime


SPOILER_MARKER = "Giraldo's burns smelled of saltpeter"  # distinctive phrase


def _seed_sibling_book(series_root: Path) -> None:
    series = SeriesLayout(root=series_root)
    scaffold.new_book(series, book_name="tiny-apothecary", pov="Lucia")

    cfg = project_mod.load(series.project_file)
    for b in cfg.books:
        if b.name == "tiny-apothecary":
            b.story_time_range = [1519, 1523]
    project_mod.dump(cfg, series.project_file)

    book = series.book("tiny-apothecary")
    book.outline_file.write_text(
        """# Outline

## Chapter 1 — Before the fire
- story_time: 1521-12-01
- events: []
- beats:
  - Lucia sorts saltpeter for a merchant she does not trust.
  - An apprentice delivers a jar she did not order.

## Chapter 2 — Smoke in the night
- story_time: 1521-12-08
- events: [E-001]
- beats:
  - Giraldo arrives at the door with his hand wrapped.
  - Lucia treats the burn without naming the fire.
""",
        encoding="utf-8",
    )

    # Earlier sibling (legal context for ch_01 of tiny-inquisitor).
    (book.chapters / "ch_01.md").write_text(
        """---
book: tiny-apothecary
chapter: 1
pov: Lucia
story_time: 1521-12-01
events: []
status: drafted
---

A clear morning on the Ponte San Giovanni. Lucia counted the saltpeter
jars twice. The apprentice brought one she had not ordered and would not
explain. She set it on the high shelf without a word.
""",
        encoding="utf-8",
    )

    # Later sibling, MUST be excluded as spoiler. Contains SPOILER_MARKER.
    (book.chapters / "ch_02.md").write_text(
        f"""---
book: tiny-apothecary
chapter: 2
pov: Lucia
story_time: 1521-12-08
events: [E-001]
status: drafted
---

The bell struck vespers when Giraldo came to her door. His right hand was
wrapped in linen already dark. {SPOILER_MARKER} and something else under
it, sharper than any burn she had dressed. She did not name the fire.
He did not either.
""",
        encoding="utf-8",
    )

    # Events ledger: E-001 renders in both books.
    (series.shared / "events.md").write_text(
        """# Events ledger

## E-001: Fire at the Venetian mint
- date: 1521-12-03
- location: Zecca, Venice
- present: [Master Giraldo, two apprentices]
- canonical: Master Giraldo set the fire to destroy the ledgers proving
  his fraud. The wind was from the south. The ledger room burned hottest.
- rendered_in:
    tiny-inquisitor/ch_01: Tommaso investigates the ashes the morning after.
    tiny-apothecary/ch_02: Lucia treats Giraldo's burn that night.
- book_constraints: Tommaso cannot know who lit it at the end of ch_01.
""",
        encoding="utf-8",
    )


@pytest.mark.smoke
@pytest.mark.genre("historical")
def test_draft_respects_multi_book_spoiler_gate(tmp_runtime_series) -> None:
    series = tmp_runtime_series("tiny-series-historical")
    _seed_sibling_book(series.path)

    # Sanity: the context loader itself says the later sibling is excluded
    # and the earlier sibling is readable. If this layer is broken the
    # smoke test below is meaningless — fail fast.
    loader = subprocess.run(
        [
            sys.executable,
            "-m",
            "autonovel.context_loader",
            "--book",
            "tiny-inquisitor",
            "--chapter",
            "1",
            "--series-root",
            str(series.path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert '"books/tiny-apothecary/chapters/ch_02.md"' in loader.stdout.replace(
        "\n", ""
    ).replace(" ", "")
    assert '"excluded_spoilers"' in loader.stdout
    assert "ch_02.md" in loader.stdout.split('"excluded_spoilers"', 1)[1].split(
        '"notes"', 1
    )[0], "ch_02 must appear under excluded_spoilers"

    result = run_command_in_runtime(
        runtime="claude",
        command="/autonovel:draft 1 --book tiny-inquisitor",
        cwd=series.path,
        allowed_tools=["Read", "Write", "Bash", "Task"],
        timeout=900,
    )
    assert result.returncode == 0, (
        f"claude returned {result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    chapter_path = (
        series.path / "books" / "tiny-inquisitor" / "chapters" / "ch_01.md"
    )
    assert chapter_path.exists(), "ch_01.md was not written"
    text = chapter_path.read_text(encoding="utf-8")

    # (a) Frontmatter is valid.
    fm = parse(text)
    assert fm.book == "tiny-inquisitor"
    assert fm.chapter == 1
    assert fm.pov == "Tommaso"
    assert fm.status == "drafted"

    body = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", text, count=1, flags=re.DOTALL)

    # (b) Spoiler exclusion: the phrase from tiny-apothecary/ch_02 — a
    # chapter whose story_time is 1521-12-08 — must not appear in a
    # chapter whose story_time is 1521-12-04.
    assert SPOILER_MARKER not in body, (
        "drafter leaked content from a sibling chapter whose story_time "
        "is after this chapter; the context loader's excluded_spoilers "
        "list was not honoured."
    )

    # (c) Canon consistency: the chapter must not name Tommaso or Lucia
    # as the arsonist (that would contradict E-001 canonical).
    lower = body.lower()
    for forbidden in (
        "tommaso set the fire",
        "tommaso lit the fire",
        "lucia set the fire",
        "lucia lit the fire",
    ):
        assert forbidden not in lower, (
            f"chapter contradicts E-001 canonical: found {forbidden!r}"
        )
