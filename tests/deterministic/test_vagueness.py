"""Tier-1 tests for the vagueness / concreteness pre-flight scanner.

A candidate generator (like show-dont-tell), NOT a quality gate: it surfaces
vague/abstract lines for the author / the LLM concreteness lens to judge.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.mechanical import vagueness as vg


def test_flags_each_kind() -> None:
    text = ("He felt something, and it was a very good thing.\n"
            "The room was really beautiful, somehow.\n")
    rep = vg.scan_chapter(text, chapter=3)
    kinds = {c.kind for c in rep.candidates}
    assert {"filler-noun", "empty-intensifier", "empty-evaluative", "hedge"} <= kinds
    matches = {c.match for c in rep.candidates}
    assert "something" in matches and "very" in matches
    assert "good" in matches and "beautiful" in matches and "somehow" in matches


def test_clean_concrete_prose_flags_little() -> None:
    text = ("He snapped the ledger shut. Ink dried on his thumb. "
            "Three coins lay on the oak table, stamped with the doge's seal.")
    rep = vg.scan_chapter(text, chapter=1)
    assert rep.total == 0


def test_density_and_word_count() -> None:
    rep = vg.scan_chapter("a very very nice thing", chapter=1)
    assert rep.word_count == 5
    assert rep.total == 4  # very, very, nice, thing
    assert rep.density_per_1000 > 0


def test_word_boundaries_no_false_substring() -> None:
    # "things" matches (it's in the list) but "nothing" should match as a
    # whole word, and an embedded "thing" inside "something" is one match,
    # not double-counted across overlapping list entries on the same span.
    rep = vg.scan_chapter("Anything is nothing.", chapter=1)
    matches = sorted(c.match for c in rep.candidates)
    assert "anything" in matches and "nothing" in matches


def test_cli_json(tmp_path: Path) -> None:
    book = tmp_path / "book"
    (book / "chapters").mkdir(parents=True)
    (book / "chapters" / "ch_01.md").write_text(
        "It was a very interesting thing, somehow.", encoding="utf-8")
    out = subprocess.run([sys.executable, "-m", "autonovel.mechanical", "vagueness",
                          str(book), "--format", "json"], capture_output=True, text=True)
    assert out.returncode == 0
    d = json.loads(out.stdout)
    assert d["chapters"][0]["total"] >= 4


def test_cli_markdown_calls_it_a_review_queue(tmp_path: Path) -> None:
    book = tmp_path / "book"
    (book / "chapters").mkdir(parents=True)
    (book / "chapters" / "ch_01.md").write_text("a very nice thing", encoding="utf-8")
    out = subprocess.run([sys.executable, "-m", "autonovel.mechanical", "vagueness",
                          str(book)], capture_output=True, text=True)
    assert out.returncode == 0
    # framed as advisory, not a gate (per feedback_avoid_brittle_python)
    assert "review queue" in out.stdout.lower() and "not a gate" in out.stdout.lower()
