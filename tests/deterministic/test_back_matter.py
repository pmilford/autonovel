"""Tier-1 tests for `mechanical/back_matter.py` and the
`autonovel mechanical build-back-matter-tex` CLI subcommand.

Parallels test_front_matter.py — back-matter is the same shape
but in `\\backmatter` zone (post-chapters), reading appendix.md
instead of preface.md/introduction.md.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.mechanical.back_matter import build_back_matter_tex


# ----------------------------------------------------- build helper


def test_no_appendix_returns_empty(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    content, titles = build_back_matter_tex(book)
    assert content == ""
    assert titles == []


def test_appendix_renders_as_chapter_star(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    (book / "appendix.md").write_text(
        "# Appendix\n\n"
        "## Timeline\n\n"
        "**1492-08-03** — Lucia first appears [parish-records].\n\n"
        "**1492-11-04** — Mint fire [council-minutes].\n\n"
        "## Bios\n\n"
        "**Jakob Fugger** (1459–1525). Augsburg banker who financed "
        "Maximilian I's imperial elections.\n",
        encoding="utf-8",
    )
    content, titles = build_back_matter_tex(book)
    assert titles == ["Appendix"]
    assert "\\chapter*{Appendix}" in content
    assert "\\addcontentsline{toc}{chapter}{Appendix}" in content


def test_subheadings_promoted_to_section_star(tmp_path: Path) -> None:
    """## headings inside the appendix become \\section*{...} so
    Timeline / Bios / Sources / Notes render with proper breaks."""
    book = tmp_path / "book"
    book.mkdir()
    (book / "appendix.md").write_text(
        "# Appendix\n\n## Timeline\n\nProse.\n\n## Bios\n\nMore prose.\n",
        encoding="utf-8",
    )
    content, _ = build_back_matter_tex(book)
    assert "\\section*{Timeline}" in content
    assert "\\section*{Bios}" in content
    # Top-level # heading should be dropped (we emit our own).
    # Verify by counting chapter* — should be exactly 1.
    assert content.count("\\chapter*") == 1


def test_writes_to_output_path(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    (book / "appendix.md").write_text(
        "# Appendix\n\nSome content.\n", encoding="utf-8",
    )
    output = tmp_path / "out" / "back_matter.tex"
    content, titles = build_back_matter_tex(book, output=output)
    assert output.is_file()
    assert "\\chapter*{Appendix}" in output.read_text(encoding="utf-8")


# ----------------------------------------------------- CLI


def test_cli_build_back_matter_tex(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    (book / "appendix.md").write_text(
        "# Appendix\n\n## Sources\n\nHistorical archive notes.\n",
        encoding="utf-8",
    )
    output = tmp_path / "back_matter.tex"
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical",
         "build-back-matter-tex",
         str(book), "--output", str(output)],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data["sections"] == ["Appendix"]
    assert data["wrote"] is True
    assert output.is_file()


def test_cli_no_appendix_no_write(tmp_path: Path) -> None:
    book = tmp_path / "book"
    book.mkdir()
    output = tmp_path / "back_matter.tex"
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical",
         "build-back-matter-tex",
         str(book), "--output", str(output)],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data["sections"] == []
    assert data["wrote"] is False
    assert not output.is_file()
