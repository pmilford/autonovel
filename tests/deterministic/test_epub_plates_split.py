"""A wide plate is cut into upright pages in the ePub.

The author found the two-page view of Venice "way too small to be of
interest" in the ePub and asked for it on two pages (2026-10-18); the next
ePub still put the whole view on one page (2026-10-28).
"""

from __future__ import annotations

from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from autonovel.mechanical.epub import build_epub_md, split_wide_plate  # noqa: E402


def _book(tmp_path: Path, size: tuple[int, int], layout: str) -> Path:
    b = tmp_path / "bk"
    (b / "chapters").mkdir(parents=True)
    (b / "typeset" / "plates").mkdir(parents=True)
    (b / "chapters" / "ch_01.md").write_text("---\ntitle: One\n---\n\nProse.\n", encoding="utf-8")
    Image.new("RGB", size, "white").save(b / "typeset" / "plates" / "view.jpg")
    (b / "typeset" / "plates.yaml").write_text(
        "plates:\n- slug: view\n  file: plates/view.jpg\n  placement: before-chapter\n"
        f"  chapter: 1\n  caption: A view.\n  layout: {layout}\n", encoding="utf-8")
    return b


def test_a_spread_is_cut_into_pages_with_the_caption_under_the_last(tmp_path: Path) -> None:
    b = _book(tmp_path, (4000, 2000), "spread")
    text, _ = build_epub_md(b / "chapters")
    assert text.count('class="plate"') == 2
    assert "view_part1of2.jpg" in text and "view_part2of2.jpg" in text
    assert text.index("1 of 2") < text.index("view_part2of2.jpg") < text.index("A view.")
    assert "page-break-before: always" in text
    w1, h1 = Image.open(b / "typeset" / "epub_plates" / "view_part1of2.jpg").size
    assert h1 == 2000 and 2000 <= w1 <= 2100  # half, plus the overlap at the cut


def test_an_upright_or_moderately_wide_plate_stays_whole(tmp_path: Path) -> None:
    b = _book(tmp_path, (1500, 1100), "landscape")
    assert split_wide_plate(b, "typeset/plates/view.jpg", "landscape") == ["typeset/plates/view.jpg"]
    text, _ = build_epub_md(b / "chapters")
    assert text.count('class="plate"') == 1 and "part1of" not in text


def test_a_very_wide_landscape_plate_is_cut_too(tmp_path: Path) -> None:
    b = _book(tmp_path, (2540, 1000), "landscape")
    assert len(split_wide_plate(b, "typeset/plates/view.jpg", "landscape")) == 2
