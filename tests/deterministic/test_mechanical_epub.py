"""Tier-1 tests for `autonovel mechanical build-epub-md` and
`build_epub_md()`.

Ships as the fix for two ePub bugs reported 2026-04-25 against the
live novel:

  1. Continuity-handoff summaries (`ch_NN.summary.md`) leaked into
     the rendered ePub because the previous typeset path used a
     bash glob `ch_*.md` which matched both prose and summary files.
  2. YAML frontmatter rendered as visible prose at the top of every
     chapter (book / chapter / pov / word_count fields).

The combiner uses `iter_chapter_files()` to filter (which already
excludes `.summary.md`) and the shared frontmatter helper to strip.
This test file locks both behaviours.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.mechanical.epub import build_epub_md


def _make_chapter(dir: Path, num: int, *, title: str, body: str,
                  with_frontmatter: bool = True) -> Path:
    """Write a chapter file shaped like a real autonovel chapter
    (YAML frontmatter + `# Title` + prose)."""
    parts: list[str] = []
    if with_frontmatter:
        parts.extend([
            "---",
            f"book: tiny",
            f"chapter: {num}",
            f"pov: Tommaso",
            f"story_time: 1521-12-04",
            f"events: []",
            f"status: drafted",
            f"word_count: {len(body.split())}",
            "---",
        ])
    parts.extend([
        f"# {title}",
        "",
        body,
        "",
    ])
    path = dir / f"ch_{num:02d}.md"
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


def _make_summary(dir: Path, num: int) -> Path:
    """Write a continuity-handoff summary file alongside the prose
    chapter. This is the file that MUST NOT appear in the ePub."""
    path = dir / f"ch_{num:02d}.summary.md"
    path.write_text(
        "**Plot:** Tommaso confronts the apothecary.\n"
        "**POV state:** Now suspects Niccolò.\n"
        "**Threads opened:** the missing ledger.\n"
        "**Threads closed:** the saltpeter mystery.\n",
        encoding="utf-8",
    )
    return path


def test_summary_files_are_excluded(tmp_path: Path) -> None:
    """The bug that motivated this module: ch_NN.summary.md MUST
    NOT appear in the combined output."""
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    _make_chapter(chapters, 1, title="The Bell", body="Real chapter prose.")
    _make_summary(chapters, 1)
    _make_chapter(chapters, 2, title="The Coin", body="More chapter prose.")
    _make_summary(chapters, 2)

    content, reports = build_epub_md(chapters)

    assert "Threads opened" not in content
    assert "POV state" not in content
    assert "**Plot:**" not in content
    assert len(reports) == 2  # not 4
    assert [r.chapter for r in reports] == [1, 2]


def test_yaml_frontmatter_is_stripped(tmp_path: Path) -> None:
    """Frontmatter fields (book / chapter / pov / word_count) must
    not appear as visible prose in the combined output."""
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    _make_chapter(chapters, 1, title="The Bell",
                  body="Tommaso heard the bell.")

    content, _ = build_epub_md(chapters)

    assert "book: tiny" not in content
    assert "word_count" not in content
    assert "story_time" not in content
    assert "events: []" not in content
    assert "status: drafted" not in content
    assert "Tommaso heard the bell." in content


def test_canonical_chapter_heading_emitted(tmp_path: Path) -> None:
    """Each chapter starts with a `# Chapter N: <title>` heading so
    pandoc reliably sees one top-level division per chapter (which
    is what makes ePub chapter navigation actually work)."""
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    _make_chapter(chapters, 1, title="The Bell", body="Prose 1.")
    _make_chapter(chapters, 2, title="The Coin", body="Prose 2.")
    _make_chapter(chapters, 3, title="The Ledger", body="Prose 3.")

    content, reports = build_epub_md(chapters)

    assert "# Chapter 1: The Bell" in content
    assert "# Chapter 2: The Coin" in content
    assert "# Chapter 3: The Ledger" in content
    # The original `# Title` heading was dropped (we emit our own).
    # So `# The Bell` should NOT appear standalone.
    assert "\n# The Bell\n" not in content


def test_chapter_ornament_referenced_when_png_exists(tmp_path: Path) -> None:
    """User 2026-04-30 reported "the ePub doesn't show the images".
    Root cause: build_epub_md only emitted prose; pandoc never saw
    any image refs. Fix: when `art/ornament_chNN.png` exists, emit
    a markdown image tag at the top of each chapter so pandoc
    embeds the PNG into the ePub bundle."""
    chapters = tmp_path / "book" / "chapters"
    chapters.mkdir(parents=True)
    art = tmp_path / "book" / "art"
    art.mkdir(parents=True)
    # Create a tiny placeholder ornament file (content doesn't
    # matter for the markdown emission test).
    (art / "ornament_ch01.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (chapters / "ch_01.md").write_text(
        "# A Chapter\n\nProse.\n", encoding="utf-8"
    )
    content, _ = build_epub_md(chapters)
    # Ornament image reference appears between the chapter heading
    # and the chapter prose.
    heading_idx = content.find("# Chapter 1")
    img_idx = content.find("ornament_ch01.png")
    prose_idx = content.find("Prose.")
    assert heading_idx >= 0 and img_idx > heading_idx
    assert img_idx < prose_idx, (
        "ornament image must precede prose so the ePub renders it "
        "at the chapter opening"
    )


def test_chapter_without_ornament_renders_cleanly(tmp_path: Path) -> None:
    """No ornament_chNN.png → no image markup; chapter still parses."""
    chapters = tmp_path / "book" / "chapters"
    chapters.mkdir(parents=True)
    (chapters / "ch_01.md").write_text(
        "# A Chapter\n\nProse.\n", encoding="utf-8"
    )
    content, _ = build_epub_md(chapters)
    assert "ornament_ch01.png" not in content
    assert "Prose." in content


def test_chapter_with_no_heading_gets_synthesised_title(tmp_path: Path) -> None:
    """A chapter file that lacks a `# …` heading still gets a
    canonical `# Chapter N` heading (so pandoc still sees a
    top-level division)."""
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    path = chapters / "ch_01.md"
    path.write_text(
        "---\nbook: tiny\nchapter: 1\n---\n"
        "Just prose, no markdown heading at all.\n",
        encoding="utf-8",
    )
    content, reports = build_epub_md(chapters)

    assert "# Chapter 1" in content
    assert "Just prose, no markdown heading" in content
    assert reports[0].title == "Chapter 1"


def test_chapter_n_colon_title_form_is_handled(tmp_path: Path) -> None:
    """When the chapter heading is already `# Chapter 5: Real Title`,
    we extract `Real Title` and re-emit it in canonical form (we
    don't end up with `# Chapter 5: Chapter 5: Real Title`)."""
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    path = chapters / "ch_05.md"
    path.write_text(
        "---\nbook: tiny\nchapter: 5\n---\n"
        "# Chapter 5: The Real Title\n"
        "\n"
        "Prose.\n",
        encoding="utf-8",
    )
    content, _ = build_epub_md(chapters)
    assert "# Chapter 5: The Real Title" in content
    assert "Chapter 5: Chapter 5" not in content


def test_chapters_are_separated_by_blank_lines(tmp_path: Path) -> None:
    """Chapters must be separated by at least one blank line so
    pandoc parses each `# Chapter N:` as its own division and
    doesn't accidentally fold prose from chapter N into chapter N+1's
    block."""
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    _make_chapter(chapters, 1, title="One", body="Last sentence of one.")
    _make_chapter(chapters, 2, title="Two", body="First sentence of two.")

    content, _ = build_epub_md(chapters)

    # Find the boundary between chapter 1 and chapter 2 — there must
    # be a blank line right before `# Chapter 2:` so pandoc splits.
    idx = content.index("# Chapter 2:")
    preceding = content[:idx].rstrip("\n")
    after_strip = content[len(preceding):]
    assert after_strip.startswith("\n\n"), \
        "Chapter 2 heading must be preceded by at least one blank line"


def test_word_count_per_chapter_is_returned(tmp_path: Path) -> None:
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    _make_chapter(chapters, 1, title="One", body="alpha beta gamma delta")
    content, reports = build_epub_md(chapters)
    # The body has 4 words; the canonical heading we add ("# Chapter
    # 1: One") is NOT counted in word_count — that's reader-meaningful
    # prose only.
    assert reports[0].word_count == 4


def test_missing_chapters_dir_raises(tmp_path: Path) -> None:
    """An explicit error beats silently producing an empty ePub."""
    import pytest
    with pytest.raises(FileNotFoundError):
        build_epub_md(tmp_path / "does_not_exist")


def test_empty_chapters_dir_raises(tmp_path: Path) -> None:
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    import pytest
    with pytest.raises(FileNotFoundError):
        build_epub_md(chapters)


def test_combined_md_writes_to_disk(tmp_path: Path) -> None:
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    _make_chapter(chapters, 1, title="One", body="Prose.")
    output = tmp_path / "out" / "combined.md"
    content, _ = build_epub_md(chapters, output=output)
    assert output.is_file()
    assert output.read_text(encoding="utf-8") == content


# ---------------------------------------------------------- CLI roundtrip


def test_cli_round_trip(tmp_path: Path) -> None:
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    _make_chapter(chapters, 1, title="Bell", body="Body of one.")
    _make_summary(chapters, 1)  # must be ignored
    _make_chapter(chapters, 2, title="Coin", body="Body of two.")

    output = tmp_path / "combined.md"
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "build-epub-md",
         str(chapters), "--output", str(output)],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["chapters"] == 2
    assert [r["chapter"] for r in payload["reports"]] == [1, 2]

    body = output.read_text(encoding="utf-8")
    assert "# Chapter 1: Bell" in body
    assert "# Chapter 2: Coin" in body
    assert "POV state" not in body
    assert "word_count" not in body
