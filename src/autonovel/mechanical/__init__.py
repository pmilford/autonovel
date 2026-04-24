"""Regex-only helpers ported from evaluate.py and apply_cuts.py.

Pure Python, no LLM, no network. Commands shell out to
`python -m autonovel.mechanical <subcmd>` so the regex logic stays
testable and out of the prompt.
"""

from .cuts import (
    VALID_TYPES,
    CutStats,
    apply_cuts,
    collapse_blank_lines,
    find_and_remove,
)
from .slop import (
    FICTION_AI_TELLS,
    STRUCTURAL_AI_TICS,
    TELLING_PATTERNS,
    TIER1_BANNED,
    TIER2_SUSPICIOUS,
    TIER3_FILLER,
    TRANSITION_OPENERS,
    SlopReport,
    period_ban_hits,
    slop_score,
)

__all__ = [
    "CutStats",
    "FICTION_AI_TELLS",
    "STRUCTURAL_AI_TICS",
    "SlopReport",
    "TELLING_PATTERNS",
    "TIER1_BANNED",
    "TIER2_SUSPICIOUS",
    "TIER3_FILLER",
    "TRANSITION_OPENERS",
    "VALID_TYPES",
    "apply_cuts",
    "collapse_blank_lines",
    "find_and_remove",
    "period_ban_hits",
    "slop_score",
]
