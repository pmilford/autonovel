"""Regex-only AI-slop scanners.

Ported verbatim from the pre-rewrite `evaluate.py` so the scoring surface
stays identical. No LLM call, no I/O — pure functions over text.

Used by:
  - `/autonovel:evaluate` (invokes `python -m autonovel.mechanical slop` to
    compute the deterministic half of a chapter's score).
  - `/autonovel:adversarial-edit` (sanity-check quotes against banned lists).
  - Tier-1 deterministic tests (see `tests/deterministic/test_slop.py`).

Scoring logic is frozen: if you change a constant or weight, update the
Tier-4 Bells regression reference in `tests/fixtures/bells-reference/`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


TIER1_BANNED: tuple[str, ...] = (
    "delve", "utilize", "leverage", "facilitate", "elucidate",
    "embark", "endeavor", "encompass", "multifaceted", "tapestry",
    "paradigm", "synergy", "synergize", "holistic", "catalyze",
    "catalyst", "juxtapose", "myriad", "plethora",
)

TIER2_SUSPICIOUS: tuple[str, ...] = (
    "robust", "comprehensive", "seamless", "seamlessly", "cutting-edge",
    "innovative", "streamline", "empower", "foster", "enhance", "elevate",
    "optimize", "pivotal", "intricate", "profound", "resonate",
    "underscore", "harness", "cultivate", "bolster", "galvanize",
    "cornerstone", "game-changer", "scalable",
)

TIER3_FILLER: tuple[str, ...] = (
    r"it'?s worth noting that",
    r"it'?s important to note that",
    r"^importantly,?\s",
    r"^notably,?\s",
    r"^interestingly,?\s",
    r"let'?s dive into",
    r"let'?s explore",
    r"as we can see",
    r"^furthermore,?\s",
    r"^moreover,?\s",
    r"^additionally,?\s",
    r"in today'?s .*(fast-paced|digital|modern)",
    r"at the end of the day",
    r"it goes without saying",
    r"when it comes to",
    r"one might argue that",
    r"not just .+, but",
)

TRANSITION_OPENERS: tuple[str, ...] = (
    "however", "furthermore", "additionally", "moreover",
    "nevertheless", "consequently", "nonetheless", "similarly",
)

FICTION_AI_TELLS: tuple[str, ...] = (
    r"a sense of \w+",
    r"couldn'?t help but feel",
    r"the weight of \w+",
    r"the air was thick with",
    r"eyes widened",
    r"a wave of \w+ washed over",
    r"a pang of \w+",
    r"heart pounded in (?:his|her|their) chest",
    r"(?:raven|dark|golden|silver) (?:hair|tresses) (?:spilled|cascaded|tumbled|fell)",
    r"piercing (?:blue|green|gray|grey|dark) eyes",
    r"a knowing (?:smile|grin|look|glance)",
    r"(?:he|she|they) felt a (?:surge|rush|wave|pang|flicker) of",
    r"the silence (?:was|hung|stretched|grew) (?:heavy|thick|oppressive|deafening)",
    r"let out a breath (?:he|she|they) didn'?t (?:know|realize)",
    r"something (?:dark|ancient|primal|unnamed) stirred",
)

STRUCTURAL_AI_TICS: tuple[str, ...] = (
    r"(?:I'm|I am) not (?:saying|asking|suggesting) .{3,40}(?:I'm|I am) (?:saying|asking|suggesting)",
    r"(?:which|that) means either .{3,40} or ",
    r"[Tt]here'?s a (?:difference|distinction)\.",
    r"[Tt]hose are (?:different|not the same) things\.",
    r"[Nn]ot (?:just|merely|simply) .{3,40}, but ",
    r"[Nn]ot (?:from|by|because of) .{3,40}, but (?:from|by|because)",
)

TELLING_PATTERNS: tuple[str, ...] = (
    r"\b(?:he|she|they|I|we|[A-Z]\w+) (?:felt|was|seemed|looked|appeared) (?:angry|sad|happy|scared|nervous|excited|jealous|guilty|anxious|lonely|desperate|furious|terrified|elated|miserable|hopeful|confused|relieved|horrified|disgusted|ashamed|proud|bitter|defeated|triumphant)\b",
    r"\b(?:angrily|sadly|happily|nervously|excitedly|desperately|furiously|anxiously|guiltily|bitterly|wearily|miserably)\b",
)


_TOKEN_STRIP = ".,;:!?\"'()"


@dataclass(frozen=True)
class SlopReport:
    tier1_hits: list[tuple[str, int]]
    tier2_hits: list[tuple[str, int]]
    tier2_clusters: int
    tier3_hits: list[tuple[str, int]]
    fiction_ai_tells: list[tuple[str, int]]
    structural_ai_tics: list[tuple[str, int]]
    telling_violations: int
    em_dash_density: float
    sentence_length_cv: float
    transition_opener_ratio: float
    slop_penalty: float

    def to_dict(self) -> dict:
        return {
            "tier1_hits": list(self.tier1_hits),
            "tier2_hits": list(self.tier2_hits),
            "tier2_clusters": self.tier2_clusters,
            "tier3_hits": list(self.tier3_hits),
            "fiction_ai_tells": list(self.fiction_ai_tells),
            "structural_ai_tics": list(self.structural_ai_tics),
            "telling_violations": self.telling_violations,
            "em_dash_density": self.em_dash_density,
            "sentence_length_cv": self.sentence_length_cv,
            "transition_opener_ratio": self.transition_opener_ratio,
            "slop_penalty": self.slop_penalty,
        }


def slop_score(text: str) -> SlopReport:
    """Deterministic slop report for a prose passage.

    `slop_penalty` is a 0-10 deduction the LLM judge can subtract from its
    own overall score to punish mechanical AI-tells without hand-waving.
    """
    words = text.lower().split()
    word_count = len(words) or 1

    tier1_hits: list[tuple[str, int]] = []
    for w in TIER1_BANNED:
        c = sum(1 for token in words if token.strip(_TOKEN_STRIP) == w)
        if c:
            tier1_hits.append((w, c))

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    tier2_hits: list[tuple[str, int]] = []
    tier2_clusters = 0
    for w in TIER2_SUSPICIOUS:
        c = sum(1 for token in words if token.strip(_TOKEN_STRIP) == w)
        if c:
            tier2_hits.append((w, c))
    for para in paragraphs:
        para_lower = para.lower()
        if sum(1 for w in TIER2_SUSPICIOUS if w in para_lower) >= 3:
            tier2_clusters += 1

    tier3_hits: list[tuple[str, int]] = []
    for pattern in TIER3_FILLER:
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        if matches:
            tier3_hits.append((pattern, len(matches)))

    em_dashes = text.count("—") + text.count("--")
    em_dash_density = (em_dashes / word_count) * 1000

    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip().split()) > 2]
    if len(sentences) > 2:
        lengths = [len(s.split()) for s in sentences]
        mean_len = sum(lengths) / len(lengths)
        variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
        std_len = variance ** 0.5
        sentence_length_cv = std_len / mean_len if mean_len > 0 else 0.0
    else:
        sentence_length_cv = 0.5

    transition_starts = 0
    for para in paragraphs:
        first = para.split()[0].lower().strip(_TOKEN_STRIP) if para.split() else ""
        if first in TRANSITION_OPENERS:
            transition_starts += 1
    transition_ratio = transition_starts / len(paragraphs) if paragraphs else 0.0

    fiction_tells: list[tuple[str, int]] = []
    for pattern in FICTION_AI_TELLS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            fiction_tells.append((pattern[:40], len(matches)))
    fiction_tell_count = sum(c for _, c in fiction_tells)

    telling_count = 0
    for pattern in TELLING_PATTERNS:
        telling_count += len(re.findall(pattern, text, re.IGNORECASE))

    structural_tics: list[tuple[str, int]] = []
    for pattern in STRUCTURAL_AI_TICS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            structural_tics.append((pattern[:40], len(matches)))
    structural_tic_count = sum(c for _, c in structural_tics)

    penalty = 0.0
    penalty += min(len(tier1_hits) * 1.5, 4.0)
    penalty += min(tier2_clusters * 1.0, 2.0)
    penalty += min(sum(c for _, c in tier3_hits) * 0.3, 2.0)
    if em_dash_density > 15:
        penalty += min((em_dash_density - 15) * 0.3, 1.0)
    if sentence_length_cv < 0.3:
        penalty += 1.0
    if transition_ratio > 0.3:
        penalty += min(transition_ratio * 2, 1.0)
    penalty += min(fiction_tell_count * 0.3, 2.0)
    penalty += min(telling_count * 0.2, 1.5)
    penalty += min(structural_tic_count * 0.5, 2.0)
    penalty = min(penalty, 10.0)

    return SlopReport(
        tier1_hits=tier1_hits,
        tier2_hits=tier2_hits,
        tier2_clusters=tier2_clusters,
        tier3_hits=tier3_hits,
        fiction_ai_tells=fiction_tells,
        structural_ai_tics=structural_tics,
        telling_violations=telling_count,
        em_dash_density=round(em_dash_density, 2),
        sentence_length_cv=round(sentence_length_cv, 3),
        transition_opener_ratio=round(transition_ratio, 3),
        slop_penalty=round(penalty, 2),
    )


def period_ban_hits(text: str, bans: list[str]) -> list[tuple[str, int]]:
    """Case-insensitive word-boundary matches against a period-bans list.

    Shared by `/autonovel:evaluate` and `/autonovel:check-anachronism`
    (the latter ships in PR 5). Returning (word, count) tuples lets the
    caller present them sorted / filtered however it wants.
    """
    hits: list[tuple[str, int]] = []
    for w in bans:
        w = w.strip()
        if not w or w.startswith("#"):
            continue
        pattern = r"\b" + re.escape(w) + r"\b"
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            hits.append((w, len(matches)))
    return hits
