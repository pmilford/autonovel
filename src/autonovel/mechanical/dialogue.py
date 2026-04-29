"""Dialogue-mechanics linter.

Pure-mechanical scanner for the dialogue patterns that are
reliable AI-tells:

  - adverb-heavy speech tags ("she said quietly")
  - said-bookisms in dense clusters
  - repeated speech-verb stutter (same non-`said` verb 3+ times
    in a 10-line window)
  - **action-beat-as-tag** — dialogue immediately followed by a
    body-action attribution that's used *in place of* a speech
    verb (`"...,". She laughed.`). One-off action beats are fine
    and often preferable to said-bookisms; the helper flags
    *clusters* of 3+ in a 10-line window.
  - **softening-qualifier in retorts** — the AI tendency to
    pad confrontation lines with `maybe`, `kind of`, `a little`
    where direct speech would land harder. Flagged in dialogue
    lines under ~80 chars (the retort/comeback length band).
  - **unattributed dialogue with ≥3 speakers on stage** —
    when the last 3+ paragraphs of dialogue have no speaker
    tag at all and the chapter has 3+ named speakers, surface
    the cluster so the reader doesn't have to guess.

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


# Action-beat verbs — body / face actions used as a tag in place of
# a speech verb. One-off use is good craft; clusters of 3+ in a
# 10-line window are AI-tell territory.
ACTION_BEAT_VERBS = {
    "laughed", "chuckled", "smiled", "grinned", "smirked",
    "frowned", "scowled", "grimaced", "shrugged", "nodded",
    "shook", "winced", "sighed", "groaned", "gasped",
    "snorted", "rolled", "tilted", "leaned", "stiffened",
    "stepped", "turned", "looked", "blinked", "swallowed",
}


# Softening-qualifier patterns that flatten retorts.
SOFTENING_QUALIFIERS = {
    "maybe", "perhaps", "kind of", "kinda", "sort of", "sorta",
    "a little", "a bit", "a tiny bit", "somewhat", "rather",
    "i guess", "i think", "i suppose",
}


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
                        # | "action-beat-cluster" | "softening" | "unattributed-cluster"
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
    action_beat_cluster_hits: int = 0
    softening_hits: int = 0
    unattributed_cluster_hits: int = 0
    hits: list[DialogueHit] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (
            self.adverb_hits + self.bookism_hits + self.stutter_hits
            + self.action_beat_cluster_hits + self.softening_hits
            + self.unattributed_cluster_hits
        )


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
                    "action_beat_cluster_hits": c.action_beat_cluster_hits,
                    "softening_hits": c.softening_hits,
                    "unattributed_cluster_hits": c.unattributed_cluster_hits,
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

    # --- Extension detectors (2026-04-29) -------------------------------
    action_beat_lines = _scan_action_beats(lines, chapter, hits,
                                             stutter_window_lines)
    softening_lines = _scan_softening_qualifiers(lines, chapter, hits)
    unattributed_lines = _scan_unattributed_dialogue(lines, chapter, hits)

    return ChapterReport(
        chapter=chapter,
        word_count=word_count,
        adverb_hits=adverb_hits,
        bookism_hits=bookism_hits,
        stutter_hits=stutter_hits,
        action_beat_cluster_hits=action_beat_lines,
        softening_hits=softening_lines,
        unattributed_cluster_hits=unattributed_lines,
        hits=hits,
    )


# ---------------------------------------------------------- extension detectors


# Action-beat-as-tag: dialogue closing punctuation immediately
# followed (same line OR next-line capitalised) by an action-beat
# verb in `<Subject> <verb>` shape. Conservative — we want to
# catch the pattern reliably and let the LLM judge sort one-off
# legitimate uses from clusters.
_ACTION_BEAT_AFTER_QUOTE_RE = re.compile(
    r'"[^"\n]*[",.?!\-]\s*'
    rf"(?:[A-Z][a-zA-Z]+\s+)?(?P<verb>{'|'.join(ACTION_BEAT_VERBS)})\b",
    re.IGNORECASE,
)


def _scan_action_beats(lines: list[str], chapter: int,
                        hits: list[DialogueHit],
                        window: int) -> int:
    """Cluster detection: 3+ action-beat-as-tag uses within
    `window` lines. Single uses are fine craft (often
    preferable to a said-bookism); clusters are AI tells.
    Returns the number of cluster events recorded."""
    occurrences: list[tuple[int, str, str]] = []  # (line_no, verb, snippet)
    for i, line in enumerate(lines, start=1):
        for m in _ACTION_BEAT_AFTER_QUOTE_RE.finditer(line):
            verb = m.group("verb").lower()
            occurrences.append(
                (i, verb, _snippet(line, m.start()))
            )
    if len(occurrences) < 3:
        return 0
    cluster_hits = 0
    seen_starts: set[int] = set()
    for j in range(len(occurrences) - 2):
        win = occurrences[j:j + 3]
        if win[-1][0] - win[0][0] <= window and win[0][0] not in seen_starts:
            cluster_hits += 1
            seen_starts.add(win[0][0])
            hits.append(DialogueHit(
                chapter=chapter, kind="action-beat-cluster",
                verb=", ".join(o[1] for o in win),
                adverb=None, line_no=win[0][0],
                snippet=(
                    f"action-beat tags `{', '.join(o[1] for o in win)}` in "
                    f"lines {win[0][0]}-{win[-1][0]}"
                ),
            ))
    return cluster_hits


# Softening qualifier inside a dialogue line under ~80 chars. Capture
# any quoted substring on the line, count its length, and check for
# a softening token inside.
_QUOTED_SUBSTR_RE = re.compile(r'"([^"\n]+)"')
_SOFTENING_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(q) for q in sorted(
        SOFTENING_QUALIFIERS, key=len, reverse=True
    )) + r")\b",
    re.IGNORECASE,
)


def _scan_softening_qualifiers(lines: list[str], chapter: int,
                                 hits: list[DialogueHit]) -> int:
    count = 0
    for i, line in enumerate(lines, start=1):
        for m in _QUOTED_SUBSTR_RE.finditer(line):
            quoted = m.group(1)
            if len(quoted) > 80:
                continue
            soft = _SOFTENING_RE.search(quoted)
            if soft:
                count += 1
                hits.append(DialogueHit(
                    chapter=chapter, kind="softening",
                    verb=soft.group(0).lower(),
                    adverb=None, line_no=i,
                    snippet=_snippet(line, m.start()),
                ))
    return count


# Unattributed-dialogue cluster: ≥3 consecutive paragraphs that
# are pure dialogue (start with `"`) with no speech tag verb on
# the same paragraph.
#
# This is reported as a "review list, not a gate" — the scanner
# can't reliably tell whether the surrounding narration makes the
# speakers obvious. Two-speaker exchanges using clean back-and-
# forth pacing get false positives here. That's the cost of
# avoiding a cast-count proxy that would itself drift on Unicode
# names, sentence-initial caps, or unusual narrators (the proxy
# was tried 2026-04-29 and reverted — see
# feedback_avoid_brittle_python.md).
#
# The LLM judge in /autonovel:evaluate's voice_adherence
# dimension is the right place to *score* this; the scanner
# surfaces candidates.
def _scan_unattributed_dialogue(lines: list[str], chapter: int,
                                  hits: list[DialogueHit]) -> int:
    text = "\n".join(lines)
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) < 3:
        return 0

    def _is_dialogue_without_tag(para: str) -> bool:
        stripped = para.lstrip()
        if not stripped.startswith('"') and not stripped.startswith("“"):
            return False
        # If the paragraph contains a known speech verb, it's tagged.
        for verb in SPEECH_VERBS:
            if re.search(rf"\b{verb}\b", stripped, re.IGNORECASE):
                return False
        return True

    # Find 3+ consecutive un-tagged dialogue paragraphs.
    cluster_hits = 0
    streak = 0
    streak_start_para = -1
    para_to_line: dict[int, int] = {}
    line_no = 1
    for idx, para in enumerate(paragraphs):
        para_to_line[idx] = line_no
        line_no += para.count("\n") + 2  # +2 for the blank-line gap
    for idx, para in enumerate(paragraphs):
        if _is_dialogue_without_tag(para):
            if streak == 0:
                streak_start_para = idx
            streak += 1
        else:
            if streak >= 3:
                cluster_hits += 1
                start_line = para_to_line[streak_start_para]
                hits.append(DialogueHit(
                    chapter=chapter, kind="unattributed-cluster",
                    verb=f"{streak} paras",
                    adverb=None, line_no=start_line,
                    snippet=(
                        f"{streak} consecutive un-tagged dialogue paragraphs "
                        f"(may be a fast back-and-forth between two known "
                        f"speakers — review list, not a gate)"
                    ),
                ))
            streak = 0
    # Trailing streak.
    if streak >= 3:
        cluster_hits += 1
        start_line = para_to_line[streak_start_para]
        hits.append(DialogueHit(
            chapter=chapter, kind="unattributed-cluster",
            verb=f"{streak} paras",
            adverb=None, line_no=start_line,
            snippet=(
                f"{streak} consecutive un-tagged dialogue paragraphs "
                f"(review list, not a gate)"
            ),
        ))
    return cluster_hits


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
    parts.append(
        "| Ch | Words | Adverb tags | Said-bookisms | Stutters | "
        "Action-beat clusters | Softening | Unattributed clusters | Total |"
    )
    parts.append("|" + "|".join("---" for _ in range(9)) + "|")
    for c in report.chapters:
        parts.append(
            "| {ch} | {wc} | {a} | {b} | {s} | {ab} | {sf} | {un} | {t} |".format(
                ch=c.chapter, wc=c.word_count,
                a=c.adverb_hits or "·", b=c.bookism_hits or "·",
                s=c.stutter_hits or "·",
                ab=c.action_beat_cluster_hits or "·",
                sf=c.softening_hits or "·",
                un=c.unattributed_cluster_hits or "·",
                t=c.total or "·",
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
