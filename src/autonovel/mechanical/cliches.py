"""Bigram cliché scanner — catches fiction-AI tells that single-word
slop scanning misses.

The existing slop scanner (slop.py) tier-lists individual words like
`delve` and `tapestry`. Many AI tells are *bigrams* — pairs of words
that read fine in isolation but together form a cliché the LLM
reaches for: "pale moonlight", "thin smile", "bated breath",
"deafening silence", "primal fear".

This scanner adds a deterministic regex pass over a curated bigram
list. Hits feed into the slop_penalty in /autonovel:evaluate
alongside the existing tier hits.

Curated 2026-04-25 from a survey of EQ-Bench slop-corpus + the
manual review of the Bells production. The list is intentionally
narrow: every entry is a phrase real LLMs reach for repeatedly
*and* that has a less-AI-shaped alternative. Adding new entries is
fine; removing them requires a real prose example showing the
phrase being used well.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Each entry is a regex of two consecutive lowercase words. We
# intentionally keep this conservative — every entry should be a
# bigram a competent prose writer would catch and replace, not just
# any common phrase.
CLICHE_BIGRAMS: tuple[str, ...] = (
    # Light, weather, atmosphere
    r"pale\s+moonlight",
    r"silver\s+moonlight",
    r"gentle\s+breeze",
    r"cool\s+breeze",
    r"warm\s+sun(?:light)?",
    r"dappled\s+light",
    r"deafening\s+silence",
    r"oppressive\s+silence",
    r"heavy\s+silence",
    r"pregnant\s+pause",
    r"sudden\s+silence",
    # Bodily reactions
    r"bated\s+breath",
    r"trembling\s+hands?",
    r"shaking\s+hands?",
    r"racing\s+heart",
    r"pounding\s+heart",
    r"thundering\s+heart",
    r"hammering\s+heart",
    r"icy\s+grip",
    r"icy\s+stare",
    r"cold\s+sweat",
    r"sharp\s+intake",
    # Smiles and expressions (the worst offenders)
    r"thin\s+smile",
    r"wry\s+smile",
    r"knowing\s+smile",
    r"tight\s+smile",
    r"cold\s+smile",
    r"grim\s+smile",
    r"sardonic\s+smile",
    r"rueful\s+smile",
    r"crooked\s+smile",
    r"ghost\s+of\s+a\s+smile",
    # Pain / sensation
    r"blinding\s+pain",
    r"searing\s+pain",
    r"white[\s\-]hot\s+(?:rage|pain|anger|fury)",
    r"burning\s+sensation",
    r"piercing\s+gaze",
    # Mythic / portentous
    r"primal\s+(?:fear|scream|urge|hunger)",
    r"ancient\s+evil",
    r"unspeakable\s+horror",
    r"existential\s+dread",
    r"creeping\s+dread",
    r"impending\s+doom",
    r"inexorable\s+(?:march|tide|pull|force)",
    # Time / change
    r"dawn\s+broke",
    r"darkness\s+fell",
    r"night\s+fell",
    r"the\s+world\s+seemed\s+to\s+",
    # AI-tell descriptive verbs
    r"shadows\s+danced",
    r"leaves\s+rustled",
    r"trees\s+swayed",
    r"wind\s+whispered",
    r"the\s+air\s+itself",
    r"a\s+symphony\s+of",
    r"a\s+tapestry\s+of",
    # Body-position cliches
    r"stood\s+rooted\s+to\s+the\s+spot",
    r"frozen\s+in\s+place",
    r"frozen\s+in\s+her\s+tracks",
    r"frozen\s+in\s+his\s+tracks",
    # Voice
    r"barely\s+a\s+whisper",
    r"voice\s+barely\s+above",
)

# Compile once. `\b` so we don't match inside longer words.
_COMPILED: tuple[re.Pattern, ...] = tuple(
    re.compile(rf"\b{p}\b", re.IGNORECASE) for p in CLICHE_BIGRAMS
)


@dataclass
class ClicheHit:
    pattern: str
    count: int

    def to_dict(self) -> dict:
        return {"pattern": self.pattern, "count": self.count}


def cliche_hits(text: str) -> list[ClicheHit]:
    """Return one entry per pattern that fires at least once.

    The result is sorted by count descending, then alphabetical, so
    the noisiest patterns are surfaced first.
    """
    out: list[ClicheHit] = []
    for raw, compiled in zip(CLICHE_BIGRAMS, _COMPILED):
        matches = compiled.findall(text)
        if matches:
            out.append(ClicheHit(pattern=raw, count=len(matches)))
    out.sort(key=lambda h: (-h.count, h.pattern))
    return out


def cliche_density(text: str) -> float:
    """Hits per 1000 words — comparable across chapter lengths."""
    word_count = len(text.split())
    if word_count == 0:
        return 0.0
    total = sum(len(c.findall(text)) for c in _COMPILED)
    return total * 1000.0 / word_count
