"""Sensory-channel balance scanner.

A scene that's 90% visual reads as a film-script camera-move — a
known LLM tell. Real prose alternates between sight, sound, smell,
taste, and touch, with the channel mix shaped by the scene's
emotional register.

The scanner counts per-channel keywords and reports the per-chapter
ratio. Rule of thumb for a flag: any single channel >70% of the
total is suspicious. Below that, the scanner just reports the
distribution so the writer can see where they're skewing.

Lists are intentionally short — about 15-25 keywords per channel —
chosen to be high-signal nouns and verbs, not weak signals that
inflate every count. Channel-defining words override channel-
neutral synonyms (`heard` is auditory; `noticed` is not categorised).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Words that strongly signal each channel. Lowercase, word-boundary
# matched. Verbs in their common tenses; nouns in singular and plural.
CHANNEL_VOCAB: dict[str, tuple[str, ...]] = {
    "visual": (
        "saw", "see", "seeing", "looked", "looking", "stared", "staring",
        "glanced", "watched", "watching", "gazed", "peered",
        "shadow", "shadows", "light", "lights", "darkness", "bright",
        "dim", "glint", "gleam", "shimmer", "shimmered",
        "color", "colors", "colour", "colours",
    ),
    "auditory": (
        "heard", "hearing", "listened", "listening", "sound", "sounds",
        "voice", "voices", "noise", "noises",
        "whisper", "whispered", "whispers",
        "shout", "shouted", "shouts", "cried", "called", "yelled",
        "rang", "rung", "rings", "ringing",
        "crash", "crashed", "thud", "footsteps", "creak", "creaked",
        "silence",
    ),
    "olfactory": (
        "smelled", "smelling", "smell", "smells", "scent", "scents",
        "scented", "aroma", "fragrance", "perfume", "stink", "stench",
        "reeked", "reek",
        "incense", "smoke",
    ),
    "gustatory": (
        "tasted", "tasting", "taste", "tastes", "flavor", "flavour",
        "flavors", "flavours", "bitter", "sweet", "sour", "salty",
        "savory", "savoury", "tangy", "sip", "sipped", "swallowed",
        "chewed", "drank",
    ),
    "tactile": (
        "felt", "feeling", "touch", "touched", "touching",
        "rough", "smooth", "warm", "warmth", "cold", "cool",
        "hot", "heat", "soft", "hard",
        "brushed", "brushing", "stroked", "gripped", "clutched",
        "pressed", "trembled", "trembling",
    ),
}

CHANNELS: tuple[str, ...] = tuple(CHANNEL_VOCAB.keys())

_COMPILED: dict[str, tuple[re.Pattern, ...]] = {
    channel: tuple(re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE)
                   for w in words)
    for channel, words in CHANNEL_VOCAB.items()
}

# Default flag threshold: any single channel >70% of the total.
DEFAULT_DOMINANCE_THRESHOLD = 0.70


@dataclass
class SensoryReport:
    counts: dict[str, int]            # raw hits per channel
    fractions: dict[str, float]       # channel / total
    total_hits: int
    word_count: int
    dominant_channel: str | None      # channel above threshold, if any
    dominance_threshold: float

    def to_dict(self) -> dict:
        return {
            "counts": dict(self.counts),
            "fractions": {k: round(v, 4) for k, v in self.fractions.items()},
            "total_hits": self.total_hits,
            "word_count": self.word_count,
            "dominant_channel": self.dominant_channel,
            "dominance_threshold": self.dominance_threshold,
        }


def channel_balance(
    text: str,
    *,
    dominance_threshold: float = DEFAULT_DOMINANCE_THRESHOLD,
) -> SensoryReport:
    """Score a chapter's per-channel keyword balance.

    `dominant_channel` is set to the channel name when its share
    exceeds `dominance_threshold`; None otherwise. Below threshold
    the report still carries the distribution.
    """
    word_count = len(text.split())
    counts: dict[str, int] = {}
    for channel, patterns in _COMPILED.items():
        counts[channel] = sum(len(p.findall(text)) for p in patterns)

    total = sum(counts.values())
    fractions: dict[str, float] = {}
    if total == 0:
        fractions = {c: 0.0 for c in CHANNELS}
        dominant = None
    else:
        fractions = {c: counts[c] / total for c in CHANNELS}
        dominant = next(
            (c for c, f in fractions.items() if f > dominance_threshold),
            None,
        )

    return SensoryReport(
        counts=counts,
        fractions=fractions,
        total_hits=total,
        word_count=word_count,
        dominant_channel=dominant,
        dominance_threshold=dominance_threshold,
    )
