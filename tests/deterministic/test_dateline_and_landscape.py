"""Tier-1: chapter datelines and landscape plates in the PDF and ePub.

Bug class (author, 2026-10-18, on a book that alternates 1519 with
1473–1518): "Need clear date changes for constant chapter back and forth
by dates" — the place and date must sit under every chapter title. And a
wide city view (de' Barbari's Venice) printed as a strip across a
portrait page was "way too small to be of interest": `layout:
landscape` turns the plate's page sideways. That still filled under half
the page, and the author asked again (2026-10-25): `layout: spread`
sets it across two facing pages.
"""

from __future__ import annotations

from pathlib import Path

from autonovel.mechanical import epub, latex


def _book(tmp: Path, *, dateline: str | None, layout: str | None) -> Path:
    book = tmp / "b"
    ch = book / "chapters"
    ch.mkdir(parents=True)
    dl = f'dateline: "{dateline}"\n' if dateline else ""
    (ch / "ch_01.md").write_text(
        f"---\nbook: b\nchapter: 1\ntitle: The Gate\n{dl}story_time: 1473-09\n---\n\nHe came in.\n",
        encoding="utf-8")
    ts = book / "typeset"
    (ts / "plates").mkdir(parents=True)
    (ts / "plates" / "view.jpg").write_bytes(b"\xff\xd8\xff")
    lay = f"  layout: {layout}\n" if layout else ""
    (ts / "plates.yaml").write_text(
        "plates:\n- slug: view\n  file: plates/view.jpg\n  placement: before-chapter\n"
        f"  chapter: 1\n  caption: A view.\n{lay}", encoding="utf-8")
    return book


def test_frontmatter_value_reads_quoted_and_bare() -> None:
    text = '---\ntitle: X\ndateline: "Venice, autumn 1473"\nfoo: bar\n---\nBody\n'
    assert latex.frontmatter_value(text, "dateline") == "Venice, autumn 1473"
    assert latex.frontmatter_value(text, "foo") == "bar"
    assert latex.frontmatter_value(text, "missing") == ""
    assert latex.frontmatter_value("no frontmatter", "dateline") == ""


def test_latex_prints_dateline_under_the_title(tmp_path: Path) -> None:
    book = _book(tmp_path, dateline="Venice, autumn 1473", layout=None)
    tex, _ = latex.build_chapters_tex(book / "chapters",
                                      plates_manifest=book / "typeset" / "plates.yaml")
    title_at = tex.index("\\chapter{The Gate}")
    date_at = tex.index("Venice, autumn 1473")
    assert title_at < date_at < tex.index("He came in")
    assert "\\begin{landscape}" not in tex


def test_latex_landscape_plate_turns_the_page(tmp_path: Path) -> None:
    book = _book(tmp_path, dateline=None, layout="landscape")
    tex, _ = latex.build_chapters_tex(book / "chapters",
                                      plates_manifest=book / "typeset" / "plates.yaml")
    assert "\\begin{landscape}" in tex and "\\end{landscape}" in tex
    assert tex.index("\\end{landscape}") < tex.index("\\chapter{The Gate}")


def test_latex_spread_plate_crosses_two_facing_pages(tmp_path: Path) -> None:
    """The author asked again (2026-10-25) for the Venice view at "at least
    one full page, and possibly 2": `layout: spread` sets it edge to edge
    across a verso and the recto beside it."""
    book = _book(tmp_path, dateline=None, layout="spread")
    tex, _ = latex.build_chapters_tex(book / "chapters",
                                      plates_manifest=book / "typeset" / "plates.yaml")
    block = tex[: tex.index("\\chapter{The Gate}")]
    assert "\\begin{landscape}" not in block
    # Starts on a verso, set once at twice the paper width, placed twice:
    # ending at the fold on the left page, starting at it on the right.
    assert block.index("\\ReadonlyShipoutCounter") < block.index("\\newgeometry{margin=0pt}")
    assert "width=2\\paperwidth" in block and block.count("view.jpg") == 1
    assert block.count("\\usebox{\\autonovelspread}") == 2
    left = block.index("[\\paperwidth][r]{\\makebox[0.5\\wd\\autonovelspread][l]")
    right = block.index("[\\paperwidth][l]{\\makebox[0.5\\wd\\autonovelspread][r]")
    assert left < block.index("\\clearpage", left) < right
    # The caption is under the right half, in a box of no height.
    assert right < block.index("A view.") < block.index("\\restoregeometry")
    assert block.count("\\smash{") == 2


def test_epub_spread_plate_fills_the_width(tmp_path: Path) -> None:
    book = _book(tmp_path, dateline=None, layout="spread")
    md, _ = epub.build_epub_md(book / "chapters",
                               plates_manifest=book / "typeset" / "plates.yaml")
    assert "width: 100%; max-width: 1400px;" in md


def test_epub_dateline_and_wide_plate(tmp_path: Path) -> None:
    book = _book(tmp_path, dateline="Augsburg, January 1519", layout="landscape")
    md, _ = epub.build_epub_md(book / "chapters",
                               plates_manifest=book / "typeset" / "plates.yaml")
    assert '<p class="dateline">Augsburg, January 1519</p>' in md
    assert md.index("# Chapter 1: The Gate") < md.index('class="dateline"')
    assert "width: 100%; max-width: 1400px;" in md


def test_template_loads_pdflscape_and_styles_dateline() -> None:
    root = Path(__file__).resolve().parents[2] / "src/autonovel/templates/series/typeset"
    assert "\\usepackage{pdflscape}" in (root / "novel.tex").read_text(encoding="utf-8")
    assert "p.dateline" in (root / "epub_style.css").read_text(encoding="utf-8")
