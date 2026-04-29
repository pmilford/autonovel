"""Dialogue-mechanics linter.

Pure-mechanical scanner for the small set of dialogue patterns
that are reliable AI-tells: adverb-heavy speech tags
("she said quietly"), said-bookisms in dense clusters
("she exclaimed", "he murmured", "they whispered" within a few
lines), spoke-the-pun pattern ("said sadly", "asked drily" — a
dictionary of the worst offenders), and repeated speech-verb
stutter (the same non-`said` verb three times within ten lines).

What it does NOT do:
- Score *quality* — that's the LLM judge in
  `/autonovel:evaluate`. This scanner just surfaces hits so the
  brief→revise pipeline (or a human reading the output) can
  decide.
- Catch *all* bad dialogue mechanics. This is a finite list of
  signatures with high precision; recall is intentionally
  lower than the LLM pass would give.

What it DOES catch is the long tail of tells that:
- the LLM judge sometimes misses on a single pass,
- live in chapters that haven't been LLM-evaluated yet, and
- the user can fix in a fast revise loop without spending a
  full eval call.

Output shape: per-chapter counts + the offending lines (with
location in the chapter prose) so the user can hand-edit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .frontmatter import strip_yaml_frontmatter
from ..paths import iter_chapter_files


# Adverbs that turn most speech tags into AI-tell territory. Not
# every -ly word — just the reliably-overused ones for dialogue.
ADVERBS = {
    "quietly", "softly", "loudly", "angrily", "sadly", "happily",
    "gently", "harshly", "carefully", "nervously", "calmly",
    "warmly", "coldly", "slowly", "quickly", "slowly", "evenly",
    "firmly", "sharply", "wearily", "hopefully", "drily", "dryly",
    "thoughtfully", "absently", "tersely", "curtly", "hesitantly",
    "earnestly", "smoothly", "icily", "kindly", "stiffly", "tightly",
    "smugly", "cheerfully", "grimly", "anxiously", "darkly",
    "lightly", "heavily", "knowingly", "pointedly", "neutrally",
}

# Said-bookisms — speech verbs other than `said` that read as
# overwriting when used too often. Light list; the value's in
# clustering, not single hits.
SAID_BOOKISMS = {
    "exclaimed", "murmured", "whispered", "muttered", "shouted",
    "yelled", "growled", "snarled", "hissed", "purred", "drawled",
    "barked", "snapped", "blurted", "intoned", "interjected",
    "remarked", "retorted", "rejoined", "chuckled", "laughed",
    "sneered", "spat", "sputtered", "stammered", "stuttered",
    "gasped", "moaned", "sighed", "smirked", "scoffed", "scolded",
    "demanded", "declared", "announced", "lamented", "marveled",
    "marvelled",
}

# Speech-tag verbs (case-insensitive). Used to find tags so we can
# look at their adverbs.
SPEECH_VERBS = {"said", "asked", "replied", "answered", *SAID_BOOKISMS}


# Speech-tag matcher. Scans for any speech verb in `SPEECH_VERBS`
# and treats it as a tag when it follows a recently-closed quote
# OR introduces a quoted phrase. The optional adverb captures the
# `quietly` / `softly` / etc. that immediately follows the verb.
#
# We build the pattern from `SPEECH_VERBS` at import time so the
# verb set lives in one place.
def _build_tag_re() -> re.Pattern[str]:
    verb_alt = "|".join(sorted(SPEECH_VERBS, key=len, reverse=True))
    return re.compile(
        rf"\b(?P<verb>{verb_alt})"
        rf"(?:\s+(?P<adverb>[a-z][a-zA-Z]+ly))?"
        rf"\b",
        re.IGNORECASE,
    )


_TAG_RE = _build_tag_re()


def _is_speech_tag_context(line: str, verb_start: int) -> bool:
    """Return True when the verb at `verb_start` looks like a
    speech tag — i.e. there's a closing quote (`"`/`"`) within the
    last ~80 chars before it, OR a quote starts within the next
    ~80 chars. Filters out non-speech uses of `said`/`asked` etc.
    (rare with the canonical verbs but matters for the bookism
    list)."""
    look_back = line[max(0, verb_start - 80):verb_start]
    look_fwd = line[verb_start:verb_start + 80]
    return ('"' in look_back or "”" in look_back
            or '"' in look_fwd or "“" in look_fwd)


@dataclass
class DialogueHit:
    chapter: int
    kind: str           # "adverb" | "bookism" | "stutter"
    verb: str
    adverb: str | None
    line_no: int
    snippet: str        # the surrounding ~120 chars


@dataclass
class ChapterReport:
    chapter: int
    word_count: int
    adverb_hits: int
    bookism_hits: int
    stutter_hits: int
    hits: list[DialogueHit] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.adverb_hits + self.bookism_hits + self.stutter_hits


@dataclass
class DialogueReport:
    chapters: list[ChapterReport]

    def to_dict(self) -> dict:
        return {
            "chapters": [
                {
                    "chapter": c.chapter,
                    "word_count": c.word_count,
                    "adverb_hits": c.adverb_hits,
                    "bookism_hits": c.bookism_hits,
                    "stutter_hits": c.stutter_hits,
                    "total": c.total,
                    "hits": [
                        {
                            "kind": h.kind, "verb": h.verb,
                            "adverb": h.adverb, "line_no": h.line_no,
                            "snippet": h.snippet,
                        }
                        for h in c.hits
                    ],
                }
                for c in self.chapters
            ]
        }


# ---------------------------------------------------------- public entry


def scan_chapter(text: str, *, chapter: int = 1,
                  stutter_window_lines: int = 10,
                  stutter_threshold: int = 3) -> ChapterReport:
    """Scan a single chapter's prose. Strips YAML frontmatter
    first."""
    body = strip_yaml_frontmatter(text)
    lines = body.splitlines()
    word_count = len(re.findall(r"\b\w+\b", body))
    hits: list[DialogueHit] = []
    adverb_hits = 0
    bookism_hits = 0
    bookism_per_line: list[tuple[int, str]] = []  # (line_no, verb)

    for i, line in enumerate(lines, start=1):
        for m in _TAG_RE.finditer(line):
            verb = m.group("verb").lower()
            adverb = (m.group("adverb") or "").lower() or None
            if verb not in SPEECH_VERBS:
                continue
            if not _is_speech_tag_context(line, m.start()):
                continue
            snippet = _snippet(line, m.start())
            if adverb in ADVERBS:
                adverb_hits += 1
                hits.append(DialogueHit(
                    chapter=chapter, kind="adverb", verb=verb,
                    adverb=adverb, line_no=i, snippet=snippet,
                ))
            if verb in SAID_BOOKISMS:
                bookism_hits += 1
                bookism_per_line.append((i, verb))
                hits.append(DialogueHit(
                    chapter=chapter, kind="bookism", verb=verb,
                    adverb=adverb, line_no=i, snippet=snippet,
                ))

    # Stutter detection: same non-`said` verb appearing
    # `stutter_threshold` times within `stutter_window_lines`.
    stutter_hits = 0
    by_verb: dict[str, list[int]] = {}
    for line_no, verb in bookism_per_line:
        by_verb.setdefault(verb, []).append(line_no)
    for verb, line_nos in by_verb.items():
        if len(line_nos) < stutter_threshold:
            continue
        # Sliding window.
        for i in range(len(line_nos) - stutter_threshold + 1):
            window = line_nos[i:i + stutter_threshold]
            if window[-1] - window[0] <= stutter_window_lines:
                stutter_hits += 1
                hits.append(DialogueHit(
                    chapter=chapter, kind="stutter", verb=verb,
                    adverb=None, line_no=window[0],
                    snippet=(
                        f"`{verb}` appears {stutter_threshold} times "
                        f"in lines {window[0]}–{window[-1]}"
                    ),
                ))
                break  # one stutter alarm per verb is enough

    return ChapterReport(
        chapter=chapter,
        word_count=word_count,
        adverb_hits=adverb_hits,
        bookism_hits=bookism_hits,
        stutter_hits=stutter_hits,
        hits=hits,
    )


def build_report(book_root: Path) -> DialogueReport:
    """Scan every drafted chapter under `book_root/chapters/`."""
    chapters: list[ChapterReport] = []
    for path in iter_chapter_files(book_root / "chapters"):
        m = re.match(r"^ch_(\d+)\.md$", path.name)
        if not m:
            continue
        text = path.read_text(encoding="utf-8")
        chapters.append(scan_chapter(text, chapter=int(m.group(1))))
    chapters.sort(key=lambda c: c.chapter)
    return DialogueReport(chapters=chapters)


def _snippet(line: str, start: int, *, window: int = 60) -> str:
    """Return a ~120-char window around `start` for context."""
    lo = max(0, start - window)
    hi = min(len(line), start + window)
    out = line[lo:hi]
    if lo > 0:
        out = "…" + out
    if hi < len(line):
        out = out + "…"
    return out.strip()


# ---------------------------------------------------------- render


def render_markdown(report: DialogueReport, *, book: str | None = None,
                     show_hits: bool = True) -> str:
    parts: list[str] = []
    parts.append(f"# Dialogue mechanics — {book}" if book
                  else "# Dialogue mechanics")
    parts.append("")
    if not report.chapters:
        parts.append("_No chapters drafted yet._")
        return "\n".join(parts) + "\n"
    parts.append("| Ch | Words | Adverb tags | Said-bookisms | Stutters | Total |")
    parts.append("|---|---|---|---|---|---|")
    for c in report.chapters:
        parts.append(
            "| {ch} | {wc} | {a} | {b} | {s} | {t} |".format(
                ch=c.chapter, wc=c.word_count,
                a=c.adverb_hits or "·", b=c.bookism_hits or "·",
                s=c.stutter_hits or "·", t=c.total or "·",
            )
        )
    if show_hits:
        for c in report.chapters:
            if not c.hits:
                continue
            parts.append("")
            parts.append(f"## Chapter {c.chapter} hits")
            for h in c.hits:
                if h.kind == "adverb":
                    parts.append(
                        f"- L{h.line_no} adverb tag (`{h.verb} {h.adverb}`): {h.snippet}"
                    )
                elif h.kind == "bookism":
                    parts.append(
                        f"- L{h.line_no} said-bookism (`{h.verb}`): {h.snippet}"
                    )
                else:
                    parts.append(
                        f"- L{h.line_no} stutter: {h.snippet}"
                    )
    return "\n".join(parts) + "\n"
