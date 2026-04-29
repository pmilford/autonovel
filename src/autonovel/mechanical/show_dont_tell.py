"""Show-don't-tell pre-flight scanner.

The slop scanner already penalises a small set of tell patterns
(`he felt a surge of`, `she felt sad`). That's a high-precision /
low-recall starting point. This module casts a wider net to surface
every candidate "tell" line so a brief / revise pass (or an LLM
classifier in `/autonovel:evaluate`) can decide which are real
problems.

What's flagged:

  - **Direct emotion-state**: `<X> was/felt/seemed/appeared
    <emotion>` where `<emotion>` is one of a curated emotion
    word-list. Always a candidate; sometimes a legitimate
    summary line, but always worth looking at.
  - **Interiority-verb tells**: `<X> knew / realised / understood
    / recognised / sensed / noticed / decided` followed by a
    proposition, with no sensory or behavioural anchor in the
    same paragraph.
  - **Adverbial filtering**: `Y looked / sounded /
    seemed <adverb>` patterns that filter the reader's
    perception through the narrator's labelling.
  - **Direct tell-rather-than-show**: `It was [adjective]` and
    `There was [emotion]` constructions that skip embodiment.

The scanner does NOT compute a ratio of tell-vs-show — that's the
LLM judge's job. We surface candidates so the judge has line-level
targets and the user gets a free pre-flight before paying for an
eval call.

Pure mechanical. No LLM. Tier-1 testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .frontmatter import strip_yaml_frontmatter
from ..paths import iter_chapter_files


# ---------------------------------------------------------- patterns


# Curated emotion word-list used in `<X> was|felt|seemed <emotion>`
# matches. These are the words that almost always signal naming
# rather than rendering.
EMOTIONS = (
    "angry", "sad", "happy", "scared", "afraid", "frightened",
    "nervous", "anxious", "excited", "jealous", "envious",
    "guilty", "ashamed", "lonely", "desperate", "furious",
    "terrified", "elated", "miserable", "hopeful", "confused",
    "relieved", "horrified", "disgusted", "proud", "bitter",
    "defeated", "triumphant", "exhausted", "frustrated",
    "irritated", "annoyed", "delighted", "thrilled", "shocked",
    "stunned", "enraged", "calm", "peaceful", "content",
    "embarrassed", "humiliated", "grateful", "sympathetic",
    "indifferent", "uncertain", "doubtful",
)

# Interiority verbs — "telling" when the rest of the sentence
# is a flat proposition with no body-anchored evidence.
INTERIORITY_VERBS = (
    "knew", "realised", "realized", "understood", "recognised",
    "recognized", "sensed", "noticed", "decided", "concluded",
    "remembered", "thought", "believed", "doubted", "wondered",
    "hoped", "feared", "wished", "longed",
)

# Adverbs that filter perception. Used in
# `<Y> looked|sounded|seemed <adverb>` patterns.
FILTER_ADVERBS = (
    "angrily", "sadly", "happily", "nervously", "anxiously",
    "calmly", "warmly", "coldly", "knowingly", "thoughtfully",
    "absently", "tersely", "curtly", "smugly", "wearily",
    "menacingly", "furtively", "guiltily", "dreadfully",
)


# `<X> was|felt|seemed|appeared|looked <EMOTION>`
_EMOTION_STATE_RE = re.compile(
    r"\b(?:he|she|they|I|we|[A-Z]\w+)\s+"
    r"(?:was|felt|seemed|appeared|looked|sounded)\s+"
    r"(?:(?:so|very|quite|rather|deeply|terribly|completely)\s+)?"
    rf"(?P<emotion>{'|'.join(EMOTIONS)})\b",
    re.IGNORECASE,
)

# `<X> knew/realised/etc.` followed by `that` or a proposition.
_INTERIORITY_RE = re.compile(
    rf"\b(?:he|she|they|I|we|[A-Z]\w+)\s+"
    rf"(?P<verb>{'|'.join(INTERIORITY_VERBS)})\b",
    re.IGNORECASE,
)

# `<Y> looked/sounded/seemed <ADVERB>`.
_PERCEPTION_FILTER_RE = re.compile(
    r"\b(?:he|she|they|it|I|we|[A-Z]\w+)\s+"
    r"(?:looked|sounded|seemed|appeared)\s+"
    rf"(?P<adverb>{'|'.join(FILTER_ADVERBS)})\b",
    re.IGNORECASE,
)

# `It was <adjective>` and `There was <emotion>` constructions —
# narrator-labels-the-mood patterns. Conservative: only flag the
# ones using a curated emotion / mood word; "It was raining" is
# fine, "It was sad" is a tell.
_NARRATOR_LABEL_RE = re.compile(
    r"\b(?:It|There)\s+was\s+"
    rf"(?:a\s+)?(?:(?:so|very|quite|rather)\s+)?"
    rf"(?P<emotion>{'|'.join(EMOTIONS)})\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------- data


@dataclass
class TellCandidate:
    chapter: int
    line_no: int
    kind: str          # "emotion-state" | "interiority" | "perception-filter" | "narrator-label"
    match: str         # the matched verb / emotion / adverb
    snippet: str


@dataclass
class ChapterReport:
    chapter: int
    word_count: int
    candidates: list[TellCandidate] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.candidates)

    @property
    def density_per_1000(self) -> float:
        if self.word_count == 0:
            return 0.0
        return round(self.total * 1000.0 / self.word_count, 2)


@dataclass
class ShowDontTellReport:
    chapters: list[ChapterReport]

    def to_dict(self) -> dict:
        return {
            "chapters": [
                {
                    "chapter": c.chapter,
                    "word_count": c.word_count,
                    "total": c.total,
                    "density_per_1000": c.density_per_1000,
                    "candidates": [
                        {
                            "kind": h.kind, "match": h.match,
                            "line_no": h.line_no, "snippet": h.snippet,
                        }
                        for h in c.candidates
                    ],
                }
                for c in self.chapters
            ]
        }


# ---------------------------------------------------------- public entry


def scan_chapter(text: str, *, chapter: int = 1) -> ChapterReport:
    body = strip_yaml_frontmatter(text)
    word_count = len(re.findall(r"\b\w+\b", body))
    candidates: list[TellCandidate] = []
    for line_no, line in enumerate(body.splitlines(), start=1):
        for m in _EMOTION_STATE_RE.finditer(line):
            candidates.append(TellCandidate(
                chapter=chapter, line_no=line_no, kind="emotion-state",
                match=m.group("emotion").lower(),
                snippet=_snippet(line, m.start()),
            ))
        for m in _INTERIORITY_RE.finditer(line):
            candidates.append(TellCandidate(
                chapter=chapter, line_no=line_no, kind="interiority",
                match=m.group("verb").lower(),
                snippet=_snippet(line, m.start()),
            ))
        for m in _PERCEPTION_FILTER_RE.finditer(line):
            candidates.append(TellCandidate(
                chapter=chapter, line_no=line_no, kind="perception-filter",
                match=m.group("adverb").lower(),
                snippet=_snippet(line, m.start()),
            ))
        for m in _NARRATOR_LABEL_RE.finditer(line):
            candidates.append(TellCandidate(
                chapter=chapter, line_no=line_no, kind="narrator-label",
                match=m.group("emotion").lower(),
                snippet=_snippet(line, m.start()),
            ))
    return ChapterReport(
        chapter=chapter, word_count=word_count, candidates=candidates,
    )


def build_report(book_root: Path) -> ShowDontTellReport:
    chapters: list[ChapterReport] = []
    for path in iter_chapter_files(book_root / "chapters"):
        m = re.match(r"^ch_(\d+)\.md$", path.name)
        if not m:
            continue
        text = path.read_text(encoding="utf-8")
        chapters.append(scan_chapter(text, chapter=int(m.group(1))))
    chapters.sort(key=lambda c: c.chapter)
    return ShowDontTellReport(chapters=chapters)


def _snippet(line: str, start: int, *, window: int = 60) -> str:
    lo = max(0, start - window)
    hi = min(len(line), start + window)
    out = line[lo:hi]
    if lo > 0:
        out = "…" + out
    if hi < len(line):
        out = out + "…"
    return out.strip()


# ---------------------------------------------------------- render


def render_markdown(report: ShowDontTellReport, *,
                     book: str | None = None,
                     show_hits: bool = True) -> str:
    parts: list[str] = []
    parts.append(f"# Show-don't-tell — {book}" if book
                  else "# Show-don't-tell")
    parts.append("")
    if not report.chapters:
        parts.append("_No chapters drafted yet._")
        return "\n".join(parts) + "\n"
    parts.append(
        "_Tell-candidate density per 1,000 words. The scanner casts a "
        "wide net — many candidates are legitimate. Use the per-line "
        "list as a review queue, not a gate. The LLM judge in "
        "`/autonovel:evaluate` produces the actual show-vs-tell ratio._"
    )
    parts.append("")
    parts.append("| Ch | Words | Total | / 1k words | Emotion | Interior | Filter | Label |")
    parts.append("|---|---|---|---|---|---|---|---|")
    for c in report.chapters:
        em = sum(1 for h in c.candidates if h.kind == "emotion-state")
        it = sum(1 for h in c.candidates if h.kind == "interiority")
        fl = sum(1 for h in c.candidates if h.kind == "perception-filter")
        la = sum(1 for h in c.candidates if h.kind == "narrator-label")
        parts.append(
            f"| {c.chapter} | {c.word_count} | "
            f"{c.total or '·'} | {c.density_per_1000} | "
            f"{em or '·'} | {it or '·'} | {fl or '·'} | {la or '·'} |"
        )
    if show_hits:
        for c in report.chapters:
            if not c.candidates:
                continue
            parts.append("")
            parts.append(f"## Chapter {c.chapter} candidates")
            for h in c.candidates:
                parts.append(
                    f"- L{h.line_no} {h.kind} (`{h.match}`): {h.snippet}"
                )
    return "\n".join(parts) + "\n"
