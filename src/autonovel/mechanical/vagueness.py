"""Vagueness / concreteness pre-flight scanner.

The same flaw that made the teaser VO fuzzy ("I bought speed", "the page no
one read") shows up in prose: abstract filler nouns, empty intensifiers, and
unearned evaluative adjectives that *tell* instead of rendering a concrete,
specific image. This scanner casts a wide net to surface candidate vague
lines so a brief / revise pass — or the LLM concreteness lens in
`/autonovel:evaluate` — can decide which to make concrete.

What's flagged (all CANDIDATES, never a gate):

  - **filler-noun** — abstract stand-ins for a concrete thing: *thing(s),
    stuff, something, anything, everything, somehow, a lot, sort of, kind
    of, some kind of*.
  - **empty-intensifier** — modifiers that inflate without adding meaning:
    *very, really, quite, rather, somewhat, extremely, incredibly,
    absolutely, totally, completely, so very*.
  - **empty-evaluative** — adjectives that judge instead of show: *good,
    bad, nice, great, interesting, beautiful, amazing, wonderful, terrible,
    special, important, strange*.
  - **hedge** — vagueness/approximation: *seemed to, somehow, in some way,
    more or less, or something, for some reason*.

Like `show_dont_tell`, this does NOT score quality — it surfaces line-level
targets for the author / the LLM judge (per the project rule that mechanical
scanners are candidate generators, not quality gates). The built-in lists
are a starting point; the real concreteness judgement is the LLM's in
`/autonovel:evaluate`.

Pure mechanical. No LLM. Tier-1 testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .frontmatter import strip_yaml_frontmatter
from ..paths import iter_chapter_files

FILLER_NOUNS = (
    "thing", "things", "stuff", "something", "anything", "everything",
    "nothing", "someone", "somebody", "somewhere", "somehow", "a lot",
    "lots", "plenty", "a bit", "sort of", "kind of", "some kind of",
    "a number of", "a couple of",
)

EMPTY_INTENSIFIERS = (
    "very", "really", "quite", "rather", "somewhat", "fairly", "extremely",
    "incredibly", "absolutely", "totally", "completely", "utterly",
    "remarkably", "truly", "literally", "actually", "basically",
)

EMPTY_EVALUATIVES = (
    "good", "bad", "nice", "great", "fine", "interesting", "beautiful",
    "amazing", "wonderful", "terrible", "awful", "special", "important",
    "strange", "weird", "lovely", "pretty", "ugly", "incredible",
    "stunning", "gorgeous",
)

HEDGES = (
    "seemed to", "somehow", "in some way", "more or less", "or something",
    "for some reason", "in a way", "of sorts", "if anything",
)


def _alt(words: tuple[str, ...]) -> str:
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


_FILLER_RE = re.compile(rf"\b(?P<m>{_alt(FILLER_NOUNS)})\b", re.IGNORECASE)
_INTENS_RE = re.compile(rf"\b(?P<m>{_alt(EMPTY_INTENSIFIERS)})\b", re.IGNORECASE)
_EVAL_RE = re.compile(rf"\b(?P<m>{_alt(EMPTY_EVALUATIVES)})\b", re.IGNORECASE)
_HEDGE_RE = re.compile(rf"\b(?P<m>{_alt(HEDGES)})\b", re.IGNORECASE)


@dataclass
class VagueCandidate:
    chapter: int
    line_no: int
    kind: str
    match: str
    snippet: str


@dataclass
class ChapterReport:
    chapter: int
    word_count: int
    candidates: list[VagueCandidate] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.candidates)

    @property
    def density_per_1000(self) -> float:
        if self.word_count == 0:
            return 0.0
        return round(self.total * 1000.0 / self.word_count, 2)


@dataclass
class VaguenessReport:
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
                        {"kind": h.kind, "match": h.match,
                         "line_no": h.line_no, "snippet": h.snippet}
                        for h in c.candidates
                    ],
                }
                for c in self.chapters
            ]
        }


def _snippet(line: str, start: int, *, window: int = 60) -> str:
    lo = max(0, start - window)
    hi = min(len(line), start + window)
    out = line[lo:hi]
    if lo > 0:
        out = "…" + out
    if hi < len(line):
        out = out + "…"
    return out.strip()


def scan_chapter(text: str, *, chapter: int = 1) -> ChapterReport:
    body = strip_yaml_frontmatter(text)
    word_count = len(re.findall(r"\b\w+\b", body))
    candidates: list[VagueCandidate] = []
    for line_no, line in enumerate(body.splitlines(), start=1):
        for kind, rx in (("filler-noun", _FILLER_RE),
                         ("empty-intensifier", _INTENS_RE),
                         ("empty-evaluative", _EVAL_RE),
                         ("hedge", _HEDGE_RE)):
            for m in rx.finditer(line):
                candidates.append(VagueCandidate(
                    chapter=chapter, line_no=line_no, kind=kind,
                    match=m.group("m").lower(), snippet=_snippet(line, m.start())))
    candidates.sort(key=lambda c: c.line_no)
    return ChapterReport(chapter=chapter, word_count=word_count, candidates=candidates)


def build_report(book_root: Path) -> VaguenessReport:
    chapters: list[ChapterReport] = []
    for path in iter_chapter_files(book_root / "chapters"):
        m = re.match(r"^ch_(\d+)\.md$", path.name)
        if not m:
            continue
        chapters.append(scan_chapter(path.read_text(encoding="utf-8"),
                                     chapter=int(m.group(1))))
    chapters.sort(key=lambda c: c.chapter)
    return VaguenessReport(chapters=chapters)


def render_markdown(report: VaguenessReport, *, book: str | None = None,
                    show_hits: bool = True) -> str:
    parts: list[str] = [f"# Vagueness scan — {book}" if book else "# Vagueness scan", ""]
    if not report.chapters:
        parts.append("_No chapters drafted yet._")
        return "\n".join(parts) + "\n"
    parts.append(
        "_Candidate vague/abstract lines per 1,000 words. The scanner casts a "
        "WIDE net — many candidates are legitimate (a 'good' meal, a 'thing' in "
        "dialogue). Use the per-line list as a review queue, NOT a gate; the LLM "
        "concreteness lens in `/autonovel:evaluate` is the real judge._")
    parts.append("")
    parts.append("| Ch | Words | Candidates | per 1k |")
    parts.append("|---|---|---|---|")
    for c in report.chapters:
        parts.append(f"| {c.chapter} | {c.word_count} | {c.total} | {c.density_per_1000:g} |")
    if show_hits:
        for c in report.chapters:
            if not c.candidates:
                continue
            parts.append("")
            parts.append(f"## Chapter {c.chapter}")
            for h in c.candidates:
                parts.append(f"- L{h.line_no} `{h.kind}` **{h.match}** — {h.snippet}")
    return "\n".join(parts) + "\n"
