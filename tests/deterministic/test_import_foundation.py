"""Tier-1 tests for `import_foundation.py` (Phase 2 of the
edit-imported workflow).

Covers:
  - capitalised-token extraction with sentence-initial filtering
  - common-word rejection
  - frequency thresholding
  - characters.md write / append / skip-exists behaviour
  - reverse-engineer integration result shape
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autonovel import import_foundation


# ---------------------------------------------------- helpers


def _make_chapter(book_root: Path, n: int, prose: str) -> Path:
    chapters = book_root / "chapters"
    chapters.mkdir(parents=True, exist_ok=True)
    path = chapters / f"ch_{n:02d}.md"
    path.write_text(
        f"---\nchapter: {n}\nstatus: imported\n---\n\n{prose}",
        encoding="utf-8",
    )
    return path


def _make_book_root(tmp_path: Path, name: str = "the-book") -> tuple[Path, Path]:
    series = tmp_path / "series"
    book_root = series / "books" / name
    book_root.mkdir(parents=True)
    (series / "shared").mkdir(parents=True, exist_ok=True)
    return series, book_root


# ---------------------------------------------------- extract


def test_extract_finds_high_frequency_proper_nouns(tmp_path: Path) -> None:
    series, book_root = _make_book_root(tmp_path)
    _make_chapter(book_root, 1,
        "Jakob walked into the hall. He found Anselmo and Lucia waiting. "
        "Jakob nodded at Anselmo. Lucia smiled at Jakob."
    )
    _make_chapter(book_root, 2,
        "Anselmo and Jakob counted the coins. Lucia stayed silent. "
        "Jakob said the books were balanced."
    )
    candidates = import_foundation.extract_character_candidates(
        book_root, min_occurrences=3,
    )
    names = [c.name for c in candidates]
    assert "Jakob" in names
    assert "Anselmo" in names
    assert "Lucia" in names


def test_extract_skips_sentence_initial_only_words(tmp_path: Path) -> None:
    """Tokens that ONLY appear at sentence start are very likely
    common words, not character names."""
    series, book_root = _make_book_root(tmp_path)
    _make_chapter(book_root, 1,
        "Suddenly the door slammed. Suddenly the wind picked up. "
        "Suddenly there was silence. Suddenly the room stilled."
    )
    candidates = import_foundation.extract_character_candidates(
        book_root, min_occurrences=2,
    )
    assert "Suddenly" not in [c.name for c in candidates]


def test_extract_rejects_structural_english(tmp_path: Path) -> None:
    """The reject list filters The / And / He / etc. — sentence-
    starters that the heuristic would otherwise count as
    capitalised."""
    series, book_root = _make_book_root(tmp_path)
    _make_chapter(book_root, 1,
        "The door opened. The hall was dark. The candle flickered. "
        "And he waited. And she came. And the night ended."
    )
    candidates = import_foundation.extract_character_candidates(
        book_root, min_occurrences=2,
    )
    names = [c.name for c in candidates]
    for rejected in ("The", "And", "He", "She"):
        assert rejected not in names


def test_extract_respects_min_occurrences(tmp_path: Path) -> None:
    series, book_root = _make_book_root(tmp_path)
    _make_chapter(book_root, 1,
        "Jakob walked. Jakob walked again. Jakob walked once more. "
        "Pietro appeared once."
    )
    cands = import_foundation.extract_character_candidates(
        book_root, min_occurrences=3,
    )
    names = [c.name for c in cands]
    assert "Jakob" in names
    assert "Pietro" not in names  # only one occurrence


def test_extract_respects_max_candidates(tmp_path: Path) -> None:
    series, book_root = _make_book_root(tmp_path)
    # 5 distinct characters, each appearing 3 times.
    parts = []
    for name in ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]:
        parts.append(
            f"Listen, {name} stood there. Then {name} laughed. Finally "
            f"{name} sat down."
        )
    _make_chapter(book_root, 1, " ".join(parts))
    cands = import_foundation.extract_character_candidates(
        book_root, min_occurrences=2, max_candidates=2,
    )
    assert len(cands) == 2


def test_extract_multiword_names_surface_as_constituent_parts(tmp_path: Path) -> None:
    """Multi-word names ('Jakob Fugger') surface as their constituent
    capitalised words ('Jakob' and 'Fugger') — the user merges them
    in the generated stub. Single-token matching is the simpler shape;
    greedy multi-word matching steals bare-name counts."""
    series, book_root = _make_book_root(tmp_path)
    _make_chapter(book_root, 1,
        "Listen, Jakob Fugger arrived. Jakob Fugger nodded. Then "
        "Jakob Fugger sat. Maximilian I waited. Maximilian I waited."
    )
    cands = import_foundation.extract_character_candidates(
        book_root, min_occurrences=2,
    )
    names = [c.name for c in cands]
    assert "Jakob" in names
    assert "Fugger" in names
    assert "Maximilian" in names


def test_extract_records_chapter_spread(tmp_path: Path) -> None:
    series, book_root = _make_book_root(tmp_path)
    for n in (1, 2, 3):
        _make_chapter(book_root, n,
            "Listen, Jakob walked. Then Jakob waited. Finally Jakob spoke."
        )
    cands = import_foundation.extract_character_candidates(
        book_root, min_occurrences=3,
    )
    jakob = next(c for c in cands if c.name == "Jakob")
    assert jakob.sample_chapters == [1, 2, 3]


def test_extract_no_chapters_returns_empty(tmp_path: Path) -> None:
    series, book_root = _make_book_root(tmp_path)
    assert import_foundation.extract_character_candidates(book_root) == []


# ---------------------------------------------------- characters.md


def test_reverse_engineer_writes_when_missing(tmp_path: Path) -> None:
    series, book_root = _make_book_root(tmp_path)
    _make_chapter(book_root, 1,
        "Listen, Jakob came. Then Jakob laughed. Finally Jakob sat. "
        "Listen, Anselmo waited. Then Anselmo spoke. Finally Anselmo left."
    )
    result = import_foundation.reverse_engineer(series, book_root)
    assert result.characters_md_action == "wrote"
    chars_path = series / "shared" / "characters.md"
    assert chars_path.is_file()
    content = chars_path.read_text(encoding="utf-8")
    assert "Jakob" in content
    assert "Anselmo" in content
    # The auto-detected header sentinel is present so re-runs don't
    # double-append.
    assert "Candidate cast (auto-detected" in content


def test_reverse_engineer_appends_when_existing_without_block(tmp_path: Path) -> None:
    series, book_root = _make_book_root(tmp_path)
    _make_chapter(book_root, 1,
        "Listen, Jakob came. Then Jakob laughed. Finally Jakob sat down."
    )
    chars_path = series / "shared" / "characters.md"
    chars_path.parent.mkdir(parents=True, exist_ok=True)
    chars_path.write_text("# Characters\n\n**Existing** — protagonist.\n",
                          encoding="utf-8")
    result = import_foundation.reverse_engineer(series, book_root)
    assert result.characters_md_action == "appended"
    content = chars_path.read_text(encoding="utf-8")
    assert "Existing" in content  # preserved
    assert "Candidate cast (auto-detected" in content
    assert "Jakob" in content


def test_reverse_engineer_idempotent_when_block_already_present(
    tmp_path: Path,
) -> None:
    series, book_root = _make_book_root(tmp_path)
    _make_chapter(book_root, 1,
        "Listen, Jakob came. Then Jakob laughed. Finally Jakob sat down."
    )
    # Pre-existing characters.md with the auto-detected sentinel.
    chars_path = series / "shared" / "characters.md"
    chars_path.parent.mkdir(parents=True, exist_ok=True)
    chars_path.write_text(
        "# Characters\n\n## Candidate cast (auto-detected from imported prose)\n\n"
        "- **Jakob** (3 occurrences)\n",
        encoding="utf-8",
    )
    result = import_foundation.reverse_engineer(series, book_root)
    assert result.characters_md_action == "skipped-exists"


def test_reverse_engineer_skipped_when_no_candidates(tmp_path: Path) -> None:
    series, book_root = _make_book_root(tmp_path)
    _make_chapter(book_root, 1,
        "the door closed. the hall was empty. the morning came slowly.",
    )
    result = import_foundation.reverse_engineer(series, book_root)
    assert result.characters_md_action == "skipped-empty"
    assert result.characters_md_path is None


def test_reverse_engineer_dry_run_writes_nothing(tmp_path: Path) -> None:
    series, book_root = _make_book_root(tmp_path)
    _make_chapter(book_root, 1,
        "Listen, Jakob came. Then Jakob laughed. Finally Jakob sat."
    )
    result = import_foundation.reverse_engineer(series, book_root, dry_run=True)
    assert result.characters_md_action == "wrote"  # would-write
    assert result.dry_run is True
    chars_path = series / "shared" / "characters.md"
    assert not chars_path.is_file()


def test_reverse_engineer_next_steps_present(tmp_path: Path) -> None:
    series, book_root = _make_book_root(tmp_path)
    _make_chapter(book_root, 1, "Listen, Jakob came. Then Jakob waited. Finally Jakob spoke.")
    result = import_foundation.reverse_engineer(series, book_root)
    joined = " ".join(result.next_steps).lower()
    assert "voice-discovery" in joined
    assert "summarize-chapter" in joined
    assert "gen-outline" in joined
    assert "evaluate" in joined
