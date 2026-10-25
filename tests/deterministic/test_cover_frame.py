"""Tier-1: the `frame` cover layout, and the chosen layout survives a rebuild.

The author chose a period painting for the cover (the counting room
from Schwarz's book of clothes, whose drawers are labelled with the
house's cities). The translucent bands `composite_cover` lays over the
art would hide those labels; `frame` shows the art whole between two
solid bands. typeset's auto-prepare re-runs the composite with no preset
whenever the art is newer, so the choice is saved beside the art.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from autonovel.export.cover import composite_cover  # noqa: E402


def _series(tmp: Path) -> Path:
    art = tmp / "books" / "b" / "art"
    art.mkdir(parents=True)
    img = Image.new("RGB", (300, 480), (200, 40, 40))
    for y in range(0, 60):                 # a band of detail at the very top
        for x in range(300):
            img.putpixel((x, y), (20, 200, 20))
    img.save(art / "cover.png")
    (tmp / "project.yaml").write_text("series_name: s\nbooks:\n- name: b\n", encoding="utf-8")
    return tmp


def test_frame_keeps_the_art_whole_between_solid_bands(tmp_path: Path) -> None:
    root = _series(tmp_path)
    out = composite_cover(series_root=root, book="b", title="Kingmaker", author="A. Writer",
                          preset="frame", focus_y=0.0)
    img = Image.open(out).convert("RGB")
    w, h = img.size
    assert (w, h) == (300, 450)
    assert img.getpixel((2, 2)) == (24, 20, 16)            # solid title band
    assert img.getpixel((2, h - 2)) == (24, 20, 16)        # solid author band
    top = int(h * 0.167)
    assert img.getpixel((150, top + 3))[1] > 150           # focus 0 keeps the top detail
    saved = json.loads((root / "books/b/art/cover_layout.json").read_text())
    assert saved == {"preset": "frame", "focus_y": 0.0}


def test_a_rebuild_with_no_preset_keeps_the_chosen_layout(tmp_path: Path) -> None:
    root = _series(tmp_path)
    composite_cover(series_root=root, book="b", title="K", author="A", preset="frame", focus_y=0.0)
    out = composite_cover(series_root=root, book="b", title="K", author="A")  # preset auto
    img = Image.open(out).convert("RGB")
    assert img.size == (300, 450) and img.getpixel((2, 2)) == (24, 20, 16)
