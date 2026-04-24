"""Tier-1 tests for `src/autonovel/mechanical/latex.py`.

Covers the three things `/autonovel:typeset` leans on:

  - `latex_escape` — the five special characters.
  - `md_to_latex` — scene-break translation, italic, quotes, dashes.
  - `build_chapters_tex` — multi-chapter build, drop caps, ornament
    wiring with PDF-preferred-over-PNG.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel.mechanical.latex import (
    build_chapters_tex,
    find_ornament,
    latex_escape,
    make_drop_cap,
    md_to_latex,
)


class TestLatexEscape:
    @pytest.mark.parametrize(
        "raw,escaped",
        [
            ("a & b", r"a \& b"),
            ("50% off", r"50\% off"),
            ("$5", r"\$5"),
            ("#hashtag", r"\#hashtag"),
            ("snake_case", r"snake\_case"),
        ],
    )
    def test_special_characters(self, raw: str, escaped: str) -> None:
        assert latex_escape(raw) == escaped


class TestMdToLatex:
    def test_scene_break(self) -> None:
        out = md_to_latex("paragraph one\n\n---\n\nparagraph two")
        assert "\\scenebreak" in out

    def test_italic(self) -> None:
        assert "\\textit{word}" in md_to_latex("a *word* here")

    def test_em_dash(self) -> None:
        assert "---" in md_to_latex("word—word")

    def test_en_dash(self) -> None:
        assert "--" in md_to_latex("p. 10–12")

    def test_smart_quotes(self) -> None:
        out = md_to_latex("“hello,” she said")
        assert "``hello,''" in out

    def test_straight_quotes_folded(self) -> None:
        out = md_to_latex('"Go," he said')
        assert "``Go,''" in out

    def test_ellipsis(self) -> None:
        assert "\\ldots{}" in md_to_latex("and then…")

    def test_ampersand_escaped(self) -> None:
        assert r"\&" in md_to_latex("Smith & Co.")


class TestDropCap:
    def test_simple_paragraph(self) -> None:
        out = make_drop_cap("Cass woke up.")
        assert "\\lettrine" in out
        assert "{C}" in out

    def test_multi_word_first_word(self) -> None:
        out = make_drop_cap("Hello world, and more.")
        assert "{H}" in out
        assert "{ello}" in out

    def test_empty_body_noop(self) -> None:
        assert make_drop_cap("") == ""

    def test_preserves_rest_of_body(self) -> None:
        body = "First paragraph.\n\nSecond paragraph here."
        out = make_drop_cap(body)
        assert "Second paragraph here." in out


class TestBuildChaptersTex:
    def _seed_chapters(self, root: Path, count: int = 2) -> Path:
        ch_dir = root / "chapters"
        ch_dir.mkdir()
        for i in range(1, count + 1):
            (ch_dir / f"ch_{i:02d}.md").write_text(
                f"# Chapter {i}: Title {i}\n\nFirst paragraph of chapter {i}.\n\n"
                f"Second paragraph here.\n",
                encoding="utf-8",
            )
        return ch_dir

    def test_builds_two_chapters(self, tmp_path: Path) -> None:
        ch_dir = self._seed_chapters(tmp_path, count=2)
        content, reports = build_chapters_tex(ch_dir)
        assert len(reports) == 2
        assert "\\chapter{Title 1}" in content
        assert "\\chapter{Title 2}" in content
        assert "\\clearpage" in content

    def test_drops_cap_on_each_chapter(self, tmp_path: Path) -> None:
        ch_dir = self._seed_chapters(tmp_path, count=2)
        content, _ = build_chapters_tex(ch_dir)
        assert content.count("\\lettrine") == 2

    def test_writes_output_file(self, tmp_path: Path) -> None:
        ch_dir = self._seed_chapters(tmp_path)
        output = tmp_path / "out" / "chapters_content.tex"
        content, _ = build_chapters_tex(ch_dir, output=output)
        assert output.read_text(encoding="utf-8") == content

    def test_empty_dir_raises(self, tmp_path: Path) -> None:
        empty = tmp_path / "chapters"
        empty.mkdir()
        with pytest.raises(FileNotFoundError):
            build_chapters_tex(empty)

    def test_ornament_pdf_preferred_over_png(self, tmp_path: Path) -> None:
        ch_dir = self._seed_chapters(tmp_path, count=1)
        art = tmp_path / "art"
        (art / "pdf").mkdir(parents=True)
        (art / "pdf" / "ornament_ch01.pdf").write_bytes(b"%PDF-1.4")
        (art / "ornament_ch01.png").write_bytes(b"PNG")
        content, reports = build_chapters_tex(ch_dir, art_dir=art)
        assert reports[0].ornament is not None
        assert reports[0].ornament.suffix == ".pdf"
        assert "ornament_ch01.pdf" in content

    def test_ornament_png_used_when_pdf_absent(self, tmp_path: Path) -> None:
        ch_dir = self._seed_chapters(tmp_path, count=1)
        art = tmp_path / "art"
        art.mkdir()
        (art / "ornament_ch01.png").write_bytes(b"PNG")
        content, _ = build_chapters_tex(ch_dir, art_dir=art)
        assert "ornament_ch01.png" in content

    def test_find_ornament_returns_none_when_missing(self, tmp_path: Path) -> None:
        art = tmp_path / "art"
        art.mkdir()
        assert find_ornament(art, 5) is None


class TestCli:
    def test_build_tex_cli_writes_output(self, tmp_path: Path) -> None:
        ch_dir = tmp_path / "chapters"
        ch_dir.mkdir()
        (ch_dir / "ch_01.md").write_text("# Ch 1: Title\n\nHello.\n", encoding="utf-8")
        out = tmp_path / "out.tex"
        result = subprocess.run(
            [sys.executable, "-m", "autonovel.mechanical", "build-tex",
             str(ch_dir), "--output", str(out)],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["chapters"] == 1
        assert out.exists()
        assert "\\chapter{Title}" in out.read_text(encoding="utf-8")
