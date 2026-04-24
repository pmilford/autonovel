"""Tier-1 tests for `src/autonovel/mechanical/spine.py`.

Verifies the three behaviours the cover-print command depends on:
  1. Spine width follows paper-stock × page-count exactly.
  2. Canvas dimensions add up: 2*bleed + 2*trim_w + spine (width axis).
  3. Pixel conversions round consistently at the default 300 DPI.

Bad inputs (zero/negative pages, unknown paper, etc.) raise ValueError.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from autonovel.mechanical.spine import (
    PAPER_INCHES_PER_PAGE,
    cover_spec,
    spine_width,
)


class TestSpineWidth:
    def test_cream_300_pages(self) -> None:
        assert spine_width(300, "cream") == pytest.approx(0.75)

    def test_white_300_pages(self) -> None:
        assert spine_width(300, "white") == pytest.approx(0.6)

    def test_paper_stock_case_insensitive(self) -> None:
        assert spine_width(100, "CREAM") == spine_width(100, "cream")

    def test_every_known_paper_stock_is_positive(self) -> None:
        for paper in PAPER_INCHES_PER_PAGE:
            assert spine_width(50, paper) > 0

    def test_unknown_paper_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown paper stock"):
            spine_width(300, "gold-leaf")

    def test_zero_pages_raises(self) -> None:
        with pytest.raises(ValueError):
            spine_width(0, "cream")

    def test_negative_pages_raises(self) -> None:
        with pytest.raises(ValueError):
            spine_width(-1, "cream")


class TestCoverSpec:
    def test_default_matches_pre_rewrite_gen_cover(self) -> None:
        """Pre-rewrite gen_cover_print.py used 5.5x8.5, cream, 0.125 bleed.

        At 300 pages the legacy script computed canvas_w = 2 × 0.125 +
        2 × 5.5 + 0.75 = 12.0 inches and canvas_h = 2 × 0.125 + 8.5 =
        8.75 inches. Locking that in keeps the cover-print command
        byte-equivalent for any book the legacy script was tuned on.
        """
        spec = cover_spec(pages=300)
        assert spec.canvas_w == pytest.approx(12.0)
        assert spec.canvas_h == pytest.approx(8.75)
        assert spec.spine_w == pytest.approx(0.75)
        assert spec.px_w == 3600
        assert spec.px_h == 2625

    def test_spine_override_wins_over_computed(self) -> None:
        spec = cover_spec(pages=300, spine_override=1.0)
        assert spec.spine_w == pytest.approx(1.0)
        assert spec.canvas_w == pytest.approx(12.25)

    def test_zero_bleed_allowed(self) -> None:
        spec = cover_spec(pages=100, bleed=0)
        assert spec.canvas_w == pytest.approx(2 * 5.5 + 0.25)

    def test_negative_bleed_rejected(self) -> None:
        with pytest.raises(ValueError):
            cover_spec(pages=100, bleed=-0.01)

    def test_non_square_trim(self) -> None:
        spec = cover_spec(trim_w=6.0, trim_h=9.0, pages=200)
        expected_canvas_w = 2 * 0.125 + 2 * 6.0 + 0.5
        assert spec.canvas_w == pytest.approx(expected_canvas_w)

    def test_low_dpi_rejected(self) -> None:
        with pytest.raises(ValueError):
            cover_spec(pages=100, dpi=30)


class TestCli:
    def test_spine_width_cli_emits_json(self) -> None:
        result = subprocess.run(
            [
                sys.executable, "-m", "autonovel.mechanical", "spine-width",
                "--pages", "250", "--paper", "white",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["pages"] == 250
        assert payload["paper"] == "white"
        assert payload["spine_w"] == pytest.approx(0.5)
        assert payload["canvas_w"] == pytest.approx(2 * 0.125 + 2 * 5.5 + 0.5)
