"""Tier-1 tests for `autonovel.import_book`."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from autonovel import import_book as ib_mod
from autonovel import project as project_mod
from autonovel.housekeeping import scaffold


# ---------------------------------------------------------- splitter


def test_split_directory_one_chapter_per_file(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "01.md").write_text("# Chapter One\n\nFirst.\n", encoding="utf-8")
    (src / "02.md").write_text("# Chapter Two\n\nSecond.\n", encoding="utf-8")
    out = ib_mod.split_chapters(src)
    assert [c.title for c in out] == ["Chapter One", "Chapter Two"]
    assert out[0].body.strip() == "First."


def test_split_directory_strips_existing_frontmatter(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "01.md").write_text(
        "---\nfoo: bar\n---\n\n# Title\n\nProse.\n", encoding="utf-8")
    out = ib_mod.split_chapters(src)
    assert "foo: bar" not in out[0].body
    assert "Prose." in out[0].body


def test_split_directory_falls_back_to_filename_for_title(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "manuscript.md").write_text("Just prose, no heading.\n", encoding="utf-8")
    out = ib_mod.split_chapters(src)
    assert out[0].title == "manuscript"


def test_split_directory_skips_non_md_files(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "01.md").write_text("# A\n\nA.\n", encoding="utf-8")
    (src / "notes.txt").write_text("ignored", encoding="utf-8")
    out = ib_mod.split_chapters(src)
    assert len(out) == 1


def test_split_directory_no_md_files_raises(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "x.txt").write_text("not md", encoding="utf-8")
    with pytest.raises(ib_mod.ImportError_) as e:
        ib_mod.split_chapters(src)
    assert "no `*.md` files" in str(e.value)


def test_split_single_file_h1_headings(tmp_path: Path) -> None:
    src = tmp_path / "book.md"
    src.write_text(
        "# Chapter One\n\nFirst chapter.\n\n# Chapter Two\n\nSecond.\n",
        encoding="utf-8",
    )
    out = ib_mod.split_chapters(src)
    assert [c.title for c in out] == ["Chapter One", "Chapter Two"]


def test_split_single_file_falls_back_to_h2(tmp_path: Path) -> None:
    src = tmp_path / "book.md"
    src.write_text(
        "## Section One\n\nFirst.\n\n## Section Two\n\nSecond.\n",
        encoding="utf-8",
    )
    out = ib_mod.split_chapters(src)
    assert len(out) == 2


def test_split_single_file_no_headings_one_chapter(tmp_path: Path) -> None:
    src = tmp_path / "book.md"
    src.write_text("Just prose, no headings at all.\n", encoding="utf-8")
    out = ib_mod.split_chapters(src)
    assert len(out) == 1
    assert out[0].title is None


def test_split_single_file_strips_frontmatter(tmp_path: Path) -> None:
    src = tmp_path / "book.md"
    src.write_text(
        "---\ntitle: My Book\n---\n\n# Chapter One\n\nProse.\n",
        encoding="utf-8",
    )
    out = ib_mod.split_chapters(src)
    assert "title: My Book" not in out[0].body


def test_split_single_file_custom_split_on(tmp_path: Path) -> None:
    src = tmp_path / "book.md"
    src.write_text(
        "Chapter 1: The Bell\n\nFirst.\n\n"
        "Chapter 2: The Mortar\n\nSecond.\n",
        encoding="utf-8",
    )
    out = ib_mod.split_chapters(src, split_on=r"^Chapter \d+: (?P<title>.+)$")
    assert [c.title for c in out] == ["The Bell", "The Mortar"]


def test_split_invalid_regex_raises(tmp_path: Path) -> None:
    src = tmp_path / "book.md"
    src.write_text("# A\n\nA.\n", encoding="utf-8")
    with pytest.raises(ib_mod.ImportError_):
        ib_mod.split_chapters(src, split_on="(unclosed")


def test_split_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(ib_mod.ImportError_):
        ib_mod.split_chapters(tmp_path / "nope")


# ---------------------------------------------------------- writer


def test_write_chapters_renders_frontmatter(tmp_path: Path) -> None:
    book_root = tmp_path / "book"
    chapters = [
        ib_mod.ChapterDoc(title="The Bell", body="Prose for one.",
                            source="x.md"),
        ib_mod.ChapterDoc(title=None, body="Prose for two.",
                            source="y.md"),
    ]
    written, skipped = ib_mod.write_chapters(
        book_root, chapters, book_name="b",
    )
    assert len(written) == 2
    assert skipped == []
    text = written[0].read_text(encoding="utf-8")
    assert "book: b" in text
    assert "chapter: 1" in text
    assert "status: imported" in text
    assert "title: The Bell" in text
    assert "imported_from:" in text
    assert "Prose for one." in text


def test_write_chapters_skips_existing_unless_overwrite(tmp_path: Path) -> None:
    book_root = tmp_path / "book"
    (book_root / "chapters").mkdir(parents=True)
    (book_root / "chapters" / "ch_01.md").write_text(
        "EXISTING", encoding="utf-8")
    chapters = [ib_mod.ChapterDoc(title="A", body="New.", source="x.md")]
    written, skipped = ib_mod.write_chapters(
        book_root, chapters, book_name="b",
    )
    assert written == []
    assert len(skipped) == 1
    assert (book_root / "chapters" / "ch_01.md").read_text() == "EXISTING"
    # With overwrite:
    written, skipped = ib_mod.write_chapters(
        book_root, chapters, book_name="b", overwrite_existing=True,
    )
    assert len(written) == 1
    assert "EXISTING" not in (book_root / "chapters" / "ch_01.md").read_text()


def test_write_chapters_dry_run_no_files(tmp_path: Path) -> None:
    book_root = tmp_path / "book"
    chapters = [ib_mod.ChapterDoc(title="A", body="Prose.", source="x.md")]
    written, _ = ib_mod.write_chapters(
        book_root, chapters, book_name="b", dry_run=True,
    )
    assert len(written) == 1
    assert not written[0].exists()


def test_write_chapters_start_at_appends(tmp_path: Path) -> None:
    book_root = tmp_path / "book"
    chapters = [
        ib_mod.ChapterDoc(title="A", body="A.", source="x.md"),
        ib_mod.ChapterDoc(title="B", body="B.", source="y.md"),
    ]
    written, _ = ib_mod.write_chapters(
        book_root, chapters, book_name="b", start_at=5,
    )
    assert [p.name for p in written] == ["ch_05.md", "ch_06.md"]


# ---------------------------------------------------------- import_manuscript


@pytest.fixture
def series(tmp_path: Path):
    res = scaffold.new_series(tmp_path / "demo", series_name="demo")
    scaffold.new_book(res.series, book_name="b", pov="Tommaso")
    return res.series.root


def test_import_manuscript_writes_and_flips_mode(series: Path,
                                                    tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "01.md").write_text("# A\n\nFirst.\n", encoding="utf-8")
    (src / "02.md").write_text("# B\n\nSecond.\n", encoding="utf-8")
    result = ib_mod.import_manuscript(series, "b", src)
    assert len(result.chapters_written) == 2
    cfg = project_mod.load(series / "project.yaml")
    assert cfg.book_by_name("b").mode == "edit-imported"


def test_import_manuscript_keep_mode_preserves(series: Path, tmp_path: Path) -> None:
    src = tmp_path / "book.md"
    src.write_text("# A\n\nFirst.\n", encoding="utf-8")
    result = ib_mod.import_manuscript(series, "b", src, keep_mode=True)
    cfg = project_mod.load(series / "project.yaml")
    assert cfg.book_by_name("b").mode == "draft"
    assert result.mode_set == "kept"


def test_import_manuscript_dry_run_writes_nothing(series: Path, tmp_path: Path) -> None:
    src = tmp_path / "book.md"
    src.write_text("# A\n\nFirst.\n", encoding="utf-8")
    result = ib_mod.import_manuscript(series, "b", src, dry_run=True)
    assert len(result.chapters_written) == 1
    assert not result.chapters_written[0].exists()
    cfg = project_mod.load(series / "project.yaml")
    # Dry-run does not flip mode either.
    assert cfg.book_by_name("b").mode == "draft"


def test_import_manuscript_unknown_book_raises(series: Path, tmp_path: Path) -> None:
    src = tmp_path / "book.md"
    src.write_text("# A\n\nFirst.\n", encoding="utf-8")
    with pytest.raises(ib_mod.ImportError_) as e:
        ib_mod.import_manuscript(series, "ghost", src)
    assert "ghost" in str(e.value)
    assert "new-book" in str(e.value)


def test_import_manuscript_appends_after_existing(series: Path, tmp_path: Path) -> None:
    book_root = series / "books" / "b"
    chapters_dir = book_root / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    (chapters_dir / "ch_01.md").write_text(
        "---\nchapter: 1\n---\n\nExisting.\n", encoding="utf-8")
    src = tmp_path / "more.md"
    src.write_text("# Two\n\nNew.\n", encoding="utf-8")
    result = ib_mod.import_manuscript(series, "b", src)
    # Existing ch_01 untouched; new chapter appended at ch_02.
    assert len(result.chapters_written) == 1
    assert result.chapters_written[0].name == "ch_02.md"


# ---------------------------------------------------------- BookEntry.mode


def test_book_entry_mode_default_is_draft() -> None:
    entry = project_mod.BookEntry(name="b")
    assert entry.mode == "draft"
    # Default mode is omitted from YAML to keep existing files clean.
    assert "mode" not in entry.to_dict()


def test_book_entry_mode_round_trip(tmp_path: Path) -> None:
    cfg = project_mod.ProjectConfig.default(series_name="s")
    cfg.books.append(project_mod.BookEntry(name="b", mode="edit-imported"))
    p = tmp_path / "project.yaml"
    project_mod.dump(cfg, p)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert raw["books"][0]["mode"] == "edit-imported"
    cfg2 = project_mod.load(p)
    assert cfg2.book_by_name("b").mode == "edit-imported"


# ---------------------------------------------------------- CLI


def test_cli_import_book_round_trip(series: Path, tmp_path: Path) -> None:
    src = tmp_path / "book.md"
    src.write_text("# Chapter One\n\nProse one.\n\n# Chapter Two\n\nProse two.\n",
                    encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "import-book", "b",
         "--from", str(src)],
        cwd=series, capture_output=True, text=True, check=True,
    )
    assert "wrote 2 chapter file(s)" in proc.stdout
    assert (series / "books" / "b" / "chapters" / "ch_01.md").is_file()
    assert (series / "books" / "b" / "chapters" / "ch_02.md").is_file()


def test_cli_import_book_dry_run(series: Path, tmp_path: Path) -> None:
    src = tmp_path / "book.md"
    src.write_text("# A\n\nProse.\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "import-book", "b",
         "--from", str(src), "--dry-run"],
        cwd=series, capture_output=True, text=True, check=True,
    )
    assert "would write" in proc.stdout
    assert "(dry-run" in proc.stdout
    assert not (series / "books" / "b" / "chapters" / "ch_01.md").exists()


def test_cli_import_book_unknown_book_exits_non_zero(series: Path, tmp_path: Path) -> None:
    src = tmp_path / "book.md"
    src.write_text("# A\n\nProse.\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "import-book", "ghost",
         "--from", str(src)],
        cwd=series, capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert "ghost" in proc.stderr
