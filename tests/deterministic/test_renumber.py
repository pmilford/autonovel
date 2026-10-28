"""Renumbering chapters moves everything keyed by a chapter's number.

Bug class (2026-10-28): swapping two chapters of one book by renaming
`ch_NN.md` alone would have left each chapter with the other's summary,
brief, score and cold read, and the release gate would have counted every
whole-book review as reading a rewritten book. `housekeeping/renumber.py`
moves them all by one map and sends back only what the order changed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autonovel import summaries
from autonovel.housekeeping import release_gate, renumber


def _book(tmp_path: Path, n: int = 4) -> Path:
    b = tmp_path / "books" / "bk"
    (b / "chapters").mkdir(parents=True)
    (b / "eval_logs").mkdir()
    (b / "edit_logs").mkdir()
    (b / "briefs").mkdir()
    (b / "typeset").mkdir()
    for i in range(1, n + 1):
        text = (f"---\nbook: bk\nchapter: {i}\ntitle: T{i}\n---\n\n"
                f"Chapter {i} prose, paragraph one.\n\nParagraph two of {i}.\n")
        ch = b / "chapters" / f"ch_{i:02d}.md"
        ch.write_text(text, encoding="utf-8")
        (b / "chapters" / f"ch_{i:02d}.summary.md").write_text(
            f"**Plot:** acts on ch {i - 1}'s news. " + "The house waits for the letter. " * 8 + "\n",
            encoding="utf-8")
        summaries.stamp(ch)
        (b / "briefs" / f"ch{i:02d}.md").write_text(
            f"---\nchapter: {i}\n---\n\n# Revision brief — chapter {i}\n", encoding="utf-8")
        (b / "eval_logs" / f"20260101_00000{i}_ch{i:02d}.json").write_text(json.dumps(
            {"chapter": i, "overall_score": 8.0, "weakest_dimension": "pace",
             "weakest_score": 7.5, "top_3_revisions": [f"echo ch {i - 1} less"]}), encoding="utf-8")
        summaries.stamp_eval(ch)
        (b / "edit_logs" / f"first_read_ch{i:02d}.md").write_text(f"# ch {i}\n", encoding="utf-8")
        release_gate.stamp_first_read(b, i)
    (b / "outline.md").write_text(
        "# Outline\n\n## Act I\n\n"
        + "".join(f"## Chapter {i} — T{i}\n- beats: b{i}\n\n" for i in range(1, 3))
        + "## Act II\n\n"
        + "".join(f"## Chapter {i} — T{i}\n- beats: b{i}\n\n" for i in range(3, n + 1))
        + "## Causal spine\n- 3 because 2: x\n- 4 because 3: y\n", encoding="utf-8")
    (b / "typeset" / "plates.yaml").write_text(
        "plates:\n- slug: a\n  placement: before-chapter\n  chapter: 3\n", encoding="utf-8")
    (b / "edit_logs" / "said_once_ledger.md").write_text(
        "# Said once\n\n## Points\n\n"
        "1. **The rule.** **Told:** ch 2 (L5, “x”). **Elsewhere:** ch 3 L9: cut.\n\n"
        "## By chapter\n\n### Chapter 3\n- L9 (point 1): cut\n", encoding="utf-8")
    for key in ("said_once", "structure_review", "reader_panel"):
        rel = release_gate.REPORTS[key][1]
        if not (b / rel).exists():
            (b / rel).write_text("{}" if rel.endswith(".json") else "# r\n", encoding="utf-8")
        release_gate.stamp_report(b, key)
    return b


def test_move_map_and_parse_map() -> None:
    assert renumber.move_map([1, 2, 3, 4], 3, 2) == {3: 2, 2: 3}
    assert renumber.move_map([1, 2, 3, 4], 1, 3) == {1: 3, 2: 1, 3: 2}
    assert renumber.parse_map("2:3,3:2", [1, 2, 3, 4]) == {2: 3, 3: 2}
    with pytest.raises(renumber.RenumberError):
        renumber.parse_map("2:3", [1, 2, 3, 4])  # two chapters 3


def test_rewrite_refs_follows_the_text() -> None:
    m = {10: 11, 11: 10}
    assert renumber.rewrite_refs("ch 10 L65 and ch 11 L3", m) == "ch 11 L65 and ch 10 L3"
    assert renumber.rewrite_refs("chapters 9–12 sag", m) == "chapters 9–12 sag"  # same set
    assert renumber.rewrite_refs("ch 10 and 11", m) == "ch 10 and 11"
    assert renumber.rewrite_refs("Chapter 10 — The Coffin", m) == "Chapter 11 — The Coffin"
    assert renumber.rewrite_refs("see first_read_ch10.md", m) == "see first_read_ch11.md"
    assert renumber.rewrite_refs("ch 10, 1514", m) == "ch 11, 1514"
    assert renumber.rewrite_refs("- 11 because 9: x", m) == "- 10 because 9: x"
    # A range whose chapters change is written out again.
    assert renumber.rewrite_refs("ch 8-10", {10: 12, 12: 10}) == "ch 8-9, 12"


def test_swap_moves_records_and_sends_back_only_what_order_changed(tmp_path: Path) -> None:
    b = _book(tmp_path)
    ch2_text = (b / "chapters" / "ch_02.md").read_text(encoding="utf-8")
    rep = renumber.renumber(b, {2: 3, 3: 2})

    # The text and its records moved together.
    new3 = (b / "chapters" / "ch_03.md").read_text(encoding="utf-8")
    assert "Chapter 2 prose" in new3 and "chapter: 3" in new3
    assert ch2_text.replace("chapter: 2", "chapter: 3") == new3
    assert "chapter: 3" in (b / "briefs" / "ch03.md").read_text(encoding="utf-8")
    assert json.loads((b / "eval_logs" / "20260101_000002_ch03.json").read_text())["chapter"] == 3
    assert summaries.state(b / "chapters" / "ch_03.md").status == "fresh"

    # The outline is back in reading order; act headings stay put.
    outline = (b / "outline.md").read_text(encoding="utf-8")
    assert outline.index("## Chapter 2 — T3") < outline.index("## Act II") < outline.index("## Chapter 3 — T2")
    assert "- 2 because 3: x" in outline
    assert "chapter: 2" in (b / "typeset" / "plates.yaml").read_text(encoding="utf-8")

    # Order: the chapters whose previous chapter changed are scored again,
    # the ones whose earlier chapters changed are read cold again.
    assert rep.rescore == [2, 3, 4]
    assert rep.reread == [2, 3]
    gate = {c.key: c for c in release_gate.check(b).checks}
    assert not gate["chapter_scores"].ok and "2-4" in gate["chapter_scores"].detail
    assert release_gate.first_read_state(b, 1) == "current"
    assert release_gate.first_read_state(b, 4) == "current"
    assert release_gate.first_read_state(b, 2) == "older"

    # The structure review judges the order; the panel follows the text.
    assert release_gate.report_state(b, "structure_review")[0] == "reordered"
    assert release_gate.report_state(b, "reader_panel")[0] == "current"
    # The said-once point was first told in ch 2 and cut in ch 3: after the
    # swap its cut telling comes first, so the ledger reads the book again.
    assert rep.said_once_inverted and release_gate.report_state(b, "said_once")[0] == "reordered"

    # Stamping the review again clears it.
    release_gate.stamp_report(b, "structure_review")
    assert release_gate.report_state(b, "structure_review")[0] == "current"


def test_a_rewritten_eval_log_keeps_its_time(tmp_path: Path) -> None:
    """A rewritten log made newer than the scorer's latest log became the
    "latest" score and brought back an old one (found testing the swap)."""
    b = _book(tmp_path)
    plain = b / "eval_logs" / "ch03_eval.json"
    plain.write_text(json.dumps({"chapter": 3, "overall_score": 5.0, "note": "ch 2 echo"}))
    import os
    os.utime(plain, (1_000_000, 1_000_000))
    renumber.renumber(b, {2: 3, 3: 2})
    assert (b / "eval_logs" / "ch02_eval.json").stat().st_mtime == 1_000_000
