"""Tier-1 tests for `autonovel mechanical build-front-matter-tex`
and `build_front_matter_tex()`.

Locks the helper that backs `/autonovel:introduction`'s typeset
side. preface.md (hand-authored) and introduction.md (typically
AI-generated) are concatenated into one front_matter.tex that
novel.tex `\\input{}`s — but only if at least one of the source
files exists.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.mechanical.front_matter import build_front_matter_tex


def test_no_files_returns_empty(tmp_path: Path) -> None:
    """Neither preface.md nor introduction.md → empty result, no
    write. The novel.tex `\\IfFileExists` guard handles this case
    silently in the typeset path."""
    content, titles = build_front_matter_tex(tmp_path)
    assert content == ""
    assert titles == []


def test_preface_only(tmp_path: Path) -> None:
    (tmp_path / "preface.md").write_text(
        "# Preface\n\nWhy I wrote this book.\n", encoding="utf-8"
    )
    content, titles = build_front_matter_tex(tmp_path)
    assert titles == ["Preface"]
    assert "\\chapter*{Preface}" in content
    assert "Why I wrote this book." in content


def test_introduction_only(tmp_path: Path) -> None:
    (tmp_path / "introduction.md").write_text(
        "# Introduction\n\nThis novel began as a question.\n", encoding="utf-8"
    )
    content, titles = build_front_matter_tex(tmp_path)
    assert titles == ["Introduction"]
    assert "\\chapter*{Introduction}" in content


def test_both_files_preface_first(tmp_path: Path) -> None:
    """Order is fixed: preface (author voice) before introduction
    (typically more about the work itself). Real books overwhelmingly
    follow this convention."""
    (tmp_path / "preface.md").write_text(
        "# Preface\n\nAuthor speaking.\n", encoding="utf-8"
    )
    (tmp_path / "introduction.md").write_text(
        "# Introduction\n\nIntroductory essay.\n", encoding="utf-8"
    )
    content, titles = build_front_matter_tex(tmp_path)
    assert titles == ["Preface", "Introduction"]
    assert content.index("Preface") < content.index("Introduction")


def test_glossary_included_after_introduction(tmp_path: Path) -> None:
    """Glossary sits last in the front-matter sequence so readers
    can flip back to it without paging through the introduction."""
    (tmp_path / "preface.md").write_text(
        "# Preface\n\nAuthor speaking.\n", encoding="utf-8"
    )
    (tmp_path / "introduction.md").write_text(
        "# Introduction\n\nEssay.\n", encoding="utf-8"
    )
    (tmp_path / "glossary.md").write_text(
        "# Glossary\n\n**grosso** — small Venetian silver coin.\n",
        encoding="utf-8",
    )
    content, titles = build_front_matter_tex(tmp_path)
    assert titles == ["Preface", "Introduction", "Glossary"]
    assert content.index("Preface") < content.index("Introduction")
    assert content.index("Introduction") < content.index("Glossary")


def test_glossary_only_renders(tmp_path: Path) -> None:
    """Glossary alone — no preface, no introduction — still renders
    as a chapter*. The most common shape for a quick-publish book."""
    (tmp_path / "glossary.md").write_text(
        "# Glossary\n\n**Doge** — chief magistrate of Venice.\n",
        encoding="utf-8",
    )
    content, titles = build_front_matter_tex(tmp_path)
    assert titles == ["Glossary"]
    assert "\\chapter*{Glossary}" in content


def test_each_section_emits_markboth_for_running_header(tmp_path: Path) -> None:
    """Each front-matter section emits \\markboth{}{<title>} so the
    running header reads its own name rather than inheriting the
    previous \\chaptermark value. Same fix as back_matter; same root
    cause."""
    (tmp_path / "preface.md").write_text(
        "# Preface\n\nProse.\n", encoding="utf-8",
    )
    (tmp_path / "introduction.md").write_text(
        "# Introduction\n\nProse.\n", encoding="utf-8",
    )
    (tmp_path / "glossary.md").write_text(
        "# Glossary\n\n**term** — def.\n", encoding="utf-8",
    )
    content, _ = build_front_matter_tex(tmp_path)
    assert "\\markboth{}{Preface}" in content
    assert "\\markboth{}{Introduction}" in content
    assert "\\markboth{}{Glossary}" in content


def test_addcontentsline_emitted_for_toc(tmp_path: Path) -> None:
    """Front-matter sections must appear in the TOC even though they
    use `\\chapter*` (which is unnumbered and otherwise excluded
    from the TOC). We add `\\addcontentsline` explicitly."""
    (tmp_path / "preface.md").write_text("# Preface\n\nBody.\n", encoding="utf-8")
    content, _ = build_front_matter_tex(tmp_path)
    assert "\\addcontentsline{toc}{chapter}{Preface}" in content


def test_yaml_frontmatter_stripped(tmp_path: Path) -> None:
    """preface.md / introduction.md may not normally have YAML
    frontmatter, but if they do (e.g. accidental copy from a chapter
    file), strip it — leaking `book: …` into the rendered preface
    is the same bug class fixed in latex.py and epub.py earlier."""
    (tmp_path / "preface.md").write_text(
        "---\nbook: tiny\n---\n# Preface\n\nReal body.\n", encoding="utf-8"
    )
    content, _ = build_front_matter_tex(tmp_path)
    assert "book: tiny" not in content
    assert "Real body." in content


def test_leading_heading_dropped(tmp_path: Path) -> None:
    """If the source file opens with a `# …` heading, drop it — we
    emit our own canonical `\\chapter*{Preface}` heading and don't
    want it duplicated."""
    (tmp_path / "preface.md").write_text(
        "# My Preface\n\nBody paragraph.\n", encoding="utf-8"
    )
    content, _ = build_front_matter_tex(tmp_path)
    # Our canonical heading is present.
    assert "\\chapter*{Preface}" in content
    # The source file's heading text isn't repeated as prose.
    assert "My Preface" not in content
    assert "Body paragraph." in content


def test_italics_converted(tmp_path: Path) -> None:
    """The same md_to_latex pipeline already used by chapters
    handles `*italic*`. Lock the round-trip so a future md_to_latex
    refactor doesn't silently break front matter."""
    (tmp_path / "preface.md").write_text(
        "# Preface\n\nThe word *novel* matters here.\n", encoding="utf-8"
    )
    content, _ = build_front_matter_tex(tmp_path)
    assert "\\textit{novel}" in content


def test_writes_output_when_path_given(tmp_path: Path) -> None:
    (tmp_path / "preface.md").write_text("# Preface\n\nBody.\n", encoding="utf-8")
    output = tmp_path / "typeset" / "front_matter.tex"
    content, _ = build_front_matter_tex(tmp_path, output=output)
    assert output.is_file()
    assert output.read_text(encoding="utf-8") == content


def test_no_write_when_empty(tmp_path: Path) -> None:
    """When neither source exists, an output path was given but no
    file was written — the typeset workflow expects this and reports
    `wrote: false` so the LaTeX `\\IfFileExists` guard handles the
    absent file."""
    output = tmp_path / "typeset" / "front_matter.tex"
    content, titles = build_front_matter_tex(tmp_path, output=output)
    assert content == ""
    assert titles == []
    # An output path was given but nothing got written — the helper
    # only writes when there's content. (Empty front_matter.tex would
    # change \input behaviour vs. \IfFileExists.)
    assert not output.exists()


# ---------------------------------------------------------- CLI roundtrip


def test_cli_round_trip(tmp_path: Path) -> None:
    (tmp_path / "preface.md").write_text(
        "# Preface\n\nReal body.\n", encoding="utf-8"
    )
    output = tmp_path / "typeset" / "front_matter.tex"
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "build-front-matter-tex",
         str(tmp_path), "--output", str(output)],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["sections"] == ["Preface"]
    assert payload["wrote"] is True
    assert output.is_file()


def test_cli_no_files_reports_no_write(tmp_path: Path) -> None:
    output = tmp_path / "typeset" / "front_matter.tex"
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "build-front-matter-tex",
         str(tmp_path), "--output", str(output)],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["sections"] == []
    assert payload["wrote"] is False
    assert not output.exists()
