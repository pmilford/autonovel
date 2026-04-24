"""Tier-3 smoke: the PR 4 evaluation, revision, and sidequest commands.

One test per command (evaluate / adversarial-edit / apply-cuts /
brief / revise / shorten). Reader-panel and review, which need a fully
drafted book of multiple chapters to run meaningfully, are intentionally
skipped here — they run manually via `pytest -m smoke -k reader_panel`
against a real series, not against a fixture, because the marginal
cost of drafting three synthetic chapters every CI run is not justified.

Opt-in under `@pytest.mark.smoke`. Skips cleanly when `claude` is not on
`$PATH` (see `tests/smoke/conftest.py`). Subscription auth is primary.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from .conftest import run_command_in_runtime


# Seed target: ~2200 words. Well above the 1800-word Bells floor so
# /autonovel:shorten has real headroom (we ask it to compress to 1850),
# and above the 2000-word line evaluate uses to distinguish "drafted"
# from "stub". The paragraph below is ~140 words; we repeat it 16 times
# to land around ~2240 words, then assert in-tests that the body is in
# [2100, 2400] before exercising any command.
#
# The paragraph uses only vocabulary that passes the fixture's
# `shared/period_bans.txt` list for 1520 Venice — no modern idiom, no
# 21st-century register. If you add paragraphs, keep the same discipline.
_PARA = (
    "The bells woke him before the canal did. Tommaso lay with his eyes "
    "open in the dark, listening to the last echo fade off the stones of "
    "San Marco and into the water, and then he listened to the water. The "
    "cell smelled of tallow and of the lagoon underneath, salt and the "
    "iron that came before rain. He rose. He put on his wool over his "
    "shirt, and when he bent for his sandals the rope around his waist "
    "slipped a finger lower against the bone of his hip, and he thought, "
    "again, that he had been losing flesh all winter and had not noticed. "
    "The dispensary would be cold. The cold would be useful. In the cold "
    "a man saw clearly, the friar had said once, and Tommaso was trying "
    "very hard to see clearly this spring.\n\n"
)
# The seed body needs a unique sentence that apply-cuts tests can target
# without hitting the mechanical module's ambiguous-match refusal. We
# drop a marker paragraph after the repeated bulk so it appears exactly
# once and can be quoted unambiguously by tests.
_UNIQUE_CUT_MARKER = (
    "A single brass lamp hung above the dispensary door, its chain "
    "darkening where the smoke had crept into the brass over the "
    "years, and Tommaso, who had never found the lamp beautiful, "
    "noticed that morning that it had been polished by someone who "
    "was no longer there to polish it.\n\n"
)
# This is the exact quote tests pass to /autonovel:apply-cuts. It must
# be a substring of `_SEED_BODY`, must appear exactly once, and must be
# ≥25 characters after whitespace normalisation so the mechanical
# module doesn't reject it as too short.
SEED_UNIQUE_CUT_QUOTE = (
    "A single brass lamp hung above the dispensary door, its chain "
    "darkening where the smoke had crept into the brass over the years,"
)
_SEED_BODY = (_PARA * 15) + _UNIQUE_CUT_MARKER + _PARA
_SEED_BODY_WORDS = len(_SEED_BODY.split())
assert _SEED_BODY.count(SEED_UNIQUE_CUT_QUOTE) == 1, (
    "SEED_UNIQUE_CUT_QUOTE must appear exactly once in _SEED_BODY — "
    "apply-cuts refuses ambiguous matches."
)
assert 2100 <= _SEED_BODY_WORDS <= 2400, (
    f"seed body is {_SEED_BODY_WORDS} words; expected 2100-2400. "
    "Adjust the repetition count before using this seed."
)
SEED_CHAPTER_WORDS = _SEED_BODY_WORDS

_CHAPTER_FRONTMATTER = (
    "---\n"
    "book: tiny-inquisitor\n"
    "chapter: 1\n"
    "pov: Tommaso\n"
    "story_time: 1520-04-12\n"
    "events: []\n"
    "status: drafted\n"
    f"word_count: {SEED_CHAPTER_WORDS}\n"
    "---\n\n"
)


def _seed_chapter(series_path: Path) -> Path:
    chapter = series_path / "books" / "tiny-inquisitor" / "chapters" / "ch_01.md"
    chapter.parent.mkdir(parents=True, exist_ok=True)
    chapter.write_text(_CHAPTER_FRONTMATTER + _SEED_BODY, encoding="utf-8")
    return chapter


@pytest.mark.smoke
@pytest.mark.genre("historical")
def test_evaluate_chapter(tmp_runtime_series) -> None:
    series = tmp_runtime_series("tiny-series-historical")
    _seed_chapter(series.path)

    result = run_command_in_runtime(
        runtime="claude",
        command="/autonovel:evaluate --chapter 1 --book tiny-inquisitor",
        cwd=series.path,
        allowed_tools=["Read", "Write", "Bash"],
    )
    assert result.returncode == 0, (
        f"claude returned {result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    eval_dir = series.path / "books" / "tiny-inquisitor" / "eval_logs"
    logs = list(eval_dir.glob("*_ch01.json"))
    assert logs, f"no eval log under {eval_dir}"
    payload = json.loads(logs[0].read_text(encoding="utf-8"))
    assert "overall_score" in payload
    assert "slop" in payload, "mechanical slop penalty must be folded into the eval log"
    assert isinstance(payload["overall_score"], (int, float))
    assert 0 <= payload["overall_score"] <= 10


@pytest.mark.smoke
@pytest.mark.genre("historical")
def test_adversarial_edit_produces_cuts(tmp_runtime_series) -> None:
    series = tmp_runtime_series("tiny-series-historical")
    _seed_chapter(series.path)

    result = run_command_in_runtime(
        runtime="claude",
        command="/autonovel:adversarial-edit 1 --book tiny-inquisitor",
        cwd=series.path,
        allowed_tools=["Read", "Write", "Bash"],
    )
    assert result.returncode == 0, (
        f"claude returned {result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    cuts_file = series.path / "books" / "tiny-inquisitor" / "edit_logs" / "ch01_cuts.json"
    assert cuts_file.exists(), f"{cuts_file} not written"
    data = json.loads(cuts_file.read_text(encoding="utf-8"))
    assert isinstance(data.get("cuts"), list) and data["cuts"], "no cuts emitted"
    for cut in data["cuts"]:
        assert len(cut.get("quote", "")) >= 25, "cut quote too short"
        assert cut.get("type") in {"FAT", "REDUNDANT", "OVER-EXPLAIN", "GENERIC", "TELL", "STRUCTURAL"}
        assert cut.get("action") in {"CUT", "REWRITE"}


@pytest.mark.smoke
@pytest.mark.genre("historical")
def test_apply_cuts_reduces_word_count(tmp_runtime_series) -> None:
    series = tmp_runtime_series("tiny-series-historical")
    chapter_path = _seed_chapter(series.path)
    # Seed a known cuts file — we want to test apply-cuts' deterministic
    # path, not a dependency on adversarial-edit running first.
    cuts_dir = series.path / "books" / "tiny-inquisitor" / "edit_logs"
    cuts_dir.mkdir(parents=True, exist_ok=True)
    # Use the uniquely-placed marker quote. The mechanical module
    # refuses ambiguous matches; this quote is guaranteed to appear
    # exactly once (enforced by a collection-time assertion at module
    # load).
    (cuts_dir / "ch01_cuts.json").write_text(
        json.dumps(
            {
                "cuts": [
                    {"quote": SEED_UNIQUE_CUT_QUOTE, "type": "OVER-EXPLAIN",
                     "reason": "narrator summary of a lived moment",
                     "action": "CUT", "rewrite": None}
                ],
                "overall_fat_percentage": 25,
                "tightest_passage": "...",
                "loosest_passage": "...",
                "one_sentence_verdict": "seeded for smoke test",
            }
        ),
        encoding="utf-8",
    )

    before = len(chapter_path.read_text(encoding="utf-8").split())

    result = run_command_in_runtime(
        runtime="claude",
        command=(
            "/autonovel:apply-cuts 1 --book tiny-inquisitor "
            "--types OVER-EXPLAIN REDUNDANT"
        ),
        cwd=series.path,
        allowed_tools=["Read", "Bash"],
    )
    assert result.returncode == 0, (
        f"claude returned {result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    after = len(chapter_path.read_text(encoding="utf-8").split())
    assert after < before, f"word count did not shrink: {before} → {after}"


@pytest.mark.smoke
@pytest.mark.genre("historical")
def test_brief_writes_structured_brief(tmp_runtime_series) -> None:
    series = tmp_runtime_series("tiny-series-historical")
    _seed_chapter(series.path)
    # Provide a cuts file so --from auto picks it.
    cuts_dir = series.path / "books" / "tiny-inquisitor" / "edit_logs"
    cuts_dir.mkdir(parents=True, exist_ok=True)
    (cuts_dir / "ch01_cuts.json").write_text(
        json.dumps(
            {
                "cuts": [
                    {"quote": "The dispensary would be cold. The cold would be useful.",
                     "type": "REDUNDANT", "action": "CUT", "rewrite": None,
                     "reason": "said twice"}
                ],
                "overall_fat_percentage": 20,
                "one_sentence_verdict": "compressible",
            }
        ),
        encoding="utf-8",
    )

    result = run_command_in_runtime(
        runtime="claude",
        command="/autonovel:brief 1 --book tiny-inquisitor --from cuts",
        cwd=series.path,
        allowed_tools=["Read", "Write", "Bash"],
    )
    assert result.returncode == 0, (
        f"claude returned {result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    brief_path = series.path / "books" / "tiny-inquisitor" / "briefs" / "ch01.md"
    assert brief_path.exists(), f"{brief_path} not written"
    text = brief_path.read_text(encoding="utf-8")
    # Required H2 sections per commands/brief.md step 5.
    for section in (
        "## What works",
        "## What drags",
        "## Voice guardrails",
        "## Target length",
    ):
        assert section in text, f"brief missing section: {section}"
    # Target length must name a number.
    m = re.search(r"## Target length[\s\S]*?(\d{3,5})", text)
    assert m, "brief does not name a target word count"


@pytest.mark.smoke
@pytest.mark.genre("historical")
def test_revise_rewrites_chapter(tmp_runtime_series) -> None:
    series = tmp_runtime_series("tiny-series-historical")
    chapter_path = _seed_chapter(series.path)
    # Seed a minimal brief so revise has an input.
    briefs_dir = series.path / "books" / "tiny-inquisitor" / "briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)
    (briefs_dir / "ch01.md").write_text(
        "# Chapter 1 — revision target\n\n"
        "## What works\nThe chapter establishes Tommaso's interior cold.\n\n"
        "## What drags\nRepetition of 'cold' and 'clearly' within a few lines.\n\n"
        "## Specific cuts\n- Remove the narrator's summary of what the friar 'had said once'.\n\n"
        "## Specific rewrites\n- Move the rope-against-hip moment ahead of the bells.\n\n"
        "## Voice guardrails\n- Body-first emotion\n- No triadic sensory lists\n\n"
        "## Target length\n1900 words (same as current).\n",
        encoding="utf-8",
    )

    original = chapter_path.read_text(encoding="utf-8")

    result = run_command_in_runtime(
        runtime="claude",
        command="/autonovel:revise 1 --book tiny-inquisitor",
        cwd=series.path,
        allowed_tools=["Read", "Write", "Bash"],
    )
    assert result.returncode == 0, (
        f"claude returned {result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    revised = chapter_path.read_text(encoding="utf-8")
    assert revised != original, "revise did not change the chapter body"
    assert "status: revised" in revised, "frontmatter status not updated"


@pytest.mark.smoke
@pytest.mark.genre("historical")
def test_shorten_compresses_chapter(tmp_runtime_series) -> None:
    series = tmp_runtime_series("tiny-series-historical")
    chapter_path = _seed_chapter(series.path)
    before = len(chapter_path.read_text(encoding="utf-8").split())
    target = 1850  # Bells floor is 1800; pick just above.

    result = run_command_in_runtime(
        runtime="claude",
        command=(
            f"/autonovel:shorten --chapter 1 --book tiny-inquisitor "
            f"--target-words {target}"
        ),
        cwd=series.path,
        allowed_tools=["Read", "Write", "Bash"],
    )
    assert result.returncode == 0, (
        f"claude returned {result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    after = len(chapter_path.read_text(encoding="utf-8").split())
    # Within the ±10% band the command's acceptance promises.
    assert 1800 <= after <= int(target * 1.1), (
        f"shortened chapter at {after} words is outside [1800, {int(target * 1.1)}]"
    )
    assert after < before, f"word count did not shrink: {before} → {after}"
