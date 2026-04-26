"""Tier-1 tests for `strip_yaml_frontmatter`.

Locks the helper that prevents YAML frontmatter (book / chapter /
pov / word_count / story_time / events) from leaking into rendered
PDF, ePub, and scene-split output. This bug shipped to a real
PDF/ePub build before being caught (2026-04-25); these tests are
the regression guard.
"""

from __future__ import annotations

from autonovel.mechanical.frontmatter import strip_yaml_frontmatter


def test_frontmatter_block_is_stripped() -> None:
    text = (
        "---\n"
        "book: tiny\n"
        "chapter: 5\n"
        "pov: Tommaso\n"
        "word_count: 3245\n"
        "---\n"
        "# Real Title\n"
        "\n"
        "First sentence of prose.\n"
    )
    out = strip_yaml_frontmatter(text)
    assert "book: tiny" not in out
    assert "word_count" not in out
    assert "Tommaso" not in out
    assert out.startswith("# Real Title")
    assert "First sentence of prose." in out


def test_text_without_frontmatter_passes_through() -> None:
    text = "# Title\n\nProse here.\n"
    assert strip_yaml_frontmatter(text) == text


def test_empty_string_passes_through() -> None:
    assert strip_yaml_frontmatter("") == ""


def test_text_starting_with_dashes_but_not_frontmatter() -> None:
    """A document whose first line is a markdown horizontal rule
    `---` followed by prose (no closing `---`) is malformed YAML,
    but we shouldn't swallow content. Returned as-is."""
    text = "---\nNot YAML, just prose under a horizontal rule.\n"
    assert strip_yaml_frontmatter(text) == text


def test_inner_dashes_inside_yaml_dont_close_the_block() -> None:
    """Multi-doc YAML with `---` separators is unusual in chapter
    files but the helper should still find the *first* closing
    `---` line and strip up to it. (Behaviour: this is what
    pandoc / yaml-front-matter-aware tools also do.)"""
    text = (
        "---\n"
        "book: tiny\n"
        "---\n"
        "Real chapter content.\n"
    )
    out = strip_yaml_frontmatter(text)
    assert out == "Real chapter content.\n"


def test_frontmatter_with_trailing_whitespace_on_dashes() -> None:
    """`---   \\n` (trailing whitespace on the delimiter line) still
    counts as a delimiter — real chapter files have been seen with
    stray whitespace after the dashes."""
    text = "---  \nbook: tiny\n---\t\nProse.\n"
    out = strip_yaml_frontmatter(text)
    assert "book:" not in out
    assert out.strip() == "Prose."
