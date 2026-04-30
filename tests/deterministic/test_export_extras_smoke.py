"""Tier-1 smoke test: when the [export] optional extra is installed,
its top-level imports actually work.

The [export] extra in pyproject.toml pins Pillow + pydub, but no
test in the existing suite imports them — so a dependency drift in
either package (a major-version bump that breaks our usage, an
upstream removal, a name change) only surfaces at export time when
the user actually runs `/autonovel:cover-print` or
`/autonovel:audiobook-assemble`.

These tests are skip-when-missing rather than always-required: a
fresh dev clone without `[export]` shouldn't fail the suite. The
point is to catch breakage when the extra IS installed.
"""

from __future__ import annotations

import importlib

import pytest


def _pillow_available() -> bool:
    try:
        importlib.import_module("PIL")
        return True
    except ImportError:
        return False


def _pydub_available() -> bool:
    try:
        importlib.import_module("pydub")
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _pillow_available(),
                     reason="Pillow not installed; install via pip install autonovel[export]")
def test_pillow_basic_imports_work() -> None:
    """The Pillow surfaces autonovel/export/cover.py uses must resolve."""
    from PIL import Image, ImageDraw, ImageFont
    # Smoke a tiny in-memory image to confirm the engine works.
    img = Image.new("RGB", (10, 10), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.point((5, 5), fill=(0, 0, 0))
    assert img.size == (10, 10)
    # ImageFont needs to be loadable; we don't load a TTF here (system
    # fonts vary), just confirm the class exists.
    assert ImageFont is not None


@pytest.mark.skipif(not _pydub_available(),
                     reason="pydub not installed; install via pip install autonovel[export]")
def test_pydub_basic_imports_work() -> None:
    """The pydub surfaces autonovel/export/audiobook code uses must
    resolve. We don't actually run ffmpeg — just exercise the
    Python-side import chain."""
    from pydub import AudioSegment
    # AudioSegment.silent is pure-Python; doesn't touch ffmpeg.
    silent = AudioSegment.silent(duration=10)
    assert len(silent) == 10


@pytest.mark.skipif(not _pillow_available(),
                     reason="Pillow not installed")
def test_export_cover_module_imports_without_error() -> None:
    """The cover module is import-guarded — verify that with Pillow
    available, it imports cleanly. Catches the bug class where a
    Pillow major-version bump changes the public API in a way our
    top-of-file import statements don't tolerate."""
    import autonovel.export.cover  # noqa: F401
