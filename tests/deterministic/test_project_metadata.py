"""Tier-1 tests for the title/subtitle/author fields on BookEntry +
the series-level author on ProjectConfig.

Added 2026-04-25 to back the `/autonovel:title` command and the
typeset-side display-metadata resolution. The fields are all
optional; the helpers fall back through book → series → "Anonymous"
sensibly so a writer who never runs `/autonovel:title` still gets
a usable PDF.
"""

from __future__ import annotations

from pathlib import Path

from autonovel import project as project_mod
from autonovel.project import BookEntry, ProjectConfig


def test_book_entry_defaults_to_no_metadata() -> None:
    b = BookEntry(name="the-bell")
    assert b.title is None
    assert b.subtitle is None
    assert b.author is None


def test_display_title_falls_back_through_chain() -> None:
    b = BookEntry(name="the-bell")
    # No explicit title, no fallback → name slug.
    assert b.display_title() == "the-bell"
    # Fallback (series_name) used when title unset.
    assert b.display_title(fallback="House of Bells") == "House of Bells"
    # Explicit title wins over fallback.
    b.title = "The Real Title"
    assert b.display_title(fallback="House of Bells") == "The Real Title"


def test_display_author_falls_back_to_anonymous() -> None:
    b = BookEntry(name="the-bell")
    assert b.display_author() == "Anonymous"
    assert b.display_author(fallback="Series Author") == "Series Author"
    b.author = "P. M. Calvi"
    assert b.display_author(fallback="Series Author") == "P. M. Calvi"


def test_to_dict_omits_unset_metadata() -> None:
    """Optional fields don't appear in the serialised YAML when unset
    — keeps project.yaml visually clean for new books."""
    b = BookEntry(name="the-bell")
    d = b.to_dict()
    assert "title" not in d
    assert "subtitle" not in d
    assert "author" not in d


def test_to_dict_includes_set_metadata() -> None:
    b = BookEntry(
        name="the-bell",
        title="The Real Title",
        subtitle="A Novel of Bells",
        author="P. M. Calvi",
    )
    d = b.to_dict()
    assert d["title"] == "The Real Title"
    assert d["subtitle"] == "A Novel of Bells"
    assert d["author"] == "P. M. Calvi"


def test_project_config_series_level_author() -> None:
    cfg = ProjectConfig(series_name="house-of-bells", author="P. M. Calvi")
    assert cfg.author == "P. M. Calvi"
    d = cfg.to_dict()
    assert d["author"] == "P. M. Calvi"


def test_project_config_to_dict_omits_unset_author() -> None:
    cfg = ProjectConfig(series_name="house-of-bells")
    assert "author" not in cfg.to_dict()


def test_yaml_roundtrip_preserves_metadata(tmp_path: Path) -> None:
    """The full read/write cycle: build a ProjectConfig with all the
    new fields populated, dump, load, assert round-trip."""
    cfg = ProjectConfig(series_name="house-of-bells", author="P. M. Calvi")
    cfg.books.append(BookEntry(
        name="the-bell",
        pov="Tommaso",
        title="The Bell at Vespers",
        subtitle="A Novel",
        author="R. M. Calvi",  # book-level overrides series-level
    ))
    path = tmp_path / "project.yaml"
    project_mod.dump(cfg, path)

    loaded = project_mod.load(path)
    assert loaded.author == "P. M. Calvi"
    book = loaded.book_by_name("the-bell")
    assert book is not None
    assert book.title == "The Bell at Vespers"
    assert book.subtitle == "A Novel"
    assert book.author == "R. M. Calvi"
    # display_author respects the book-level override.
    assert book.display_author(fallback=loaded.author) == "R. M. Calvi"


def test_yaml_with_no_metadata_loads_cleanly(tmp_path: Path) -> None:
    """Backward compatibility: an existing project.yaml from before
    the title/author fields shipped must still load. Real users have
    these on disk."""
    path = tmp_path / "project.yaml"
    path.write_text(
        "series_name: house-of-bells\n"
        "genre: historical-fiction\n"
        "books:\n"
        "  - name: the-bell\n"
        "    pov: Tommaso\n"
        "    status: drafted\n",
        encoding="utf-8",
    )
    cfg = project_mod.load(path)
    assert cfg.author is None
    book = cfg.book_by_name("the-bell")
    assert book is not None
    assert book.title is None
    assert book.author is None
    # Falls back through the chain cleanly.
    assert book.display_title(fallback=cfg.series_name) == "house-of-bells"
    assert book.display_author(fallback=cfg.author) == "Anonymous"
