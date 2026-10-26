"""Is each chapter's continuity summary still a summary of that chapter?

Every drafter and reviser reads the earlier chapters'
`ch_NN.summary.md` as its memory of the book. A summary written before
the chapter's prose last changed hands the next chapter a story that is
no longer on the page.

Freshness used to be judged by file mtimes. That flagged every revised
chapter as stale (revise writes the summary, then the chapter's
frontmatter), so the warning was ignored, and it was blind to a summary
touched after the prose changed (the `touch` workaround) or to a fresh
clone, where checkout order sets the mtimes. Now a summary records a
fingerprint of the chapter body it was written from, `summary_of:` in
its frontmatter, written by `autonovel _stamp-summary`. A summary is
fresh when that fingerprint matches the chapter as it now stands.

States:

  - `fresh`      stamped, and the fingerprint matches the chapter body.
  - `stale`      stamped with a different body; or, for a summary from
                 before fingerprints, the chapter file is newer.
  - `unverified` from before fingerprints and not older than its
                 chapter: probably right, but nothing proves it.
  - `missing`    no summary, or only a stub.

Anything but `fresh` is refreshed before a command reads it (the
preamble's summary step, driven by `_begin`), and `_end` refuses to
close a command that changed a chapter and left its summary behind.
Pure Python; no LLM.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .mechanical.frontmatter import strip_yaml_frontmatter

STAMP_KEY = "summary_of"
# A summary shorter than this is a stub, not a summary (the threshold
# `/autonovel:summarize-chapter` has always used to refuse overwriting).
MIN_SUMMARY_CHARS = 100

_CHAPTER_RE = re.compile(r"^ch_(\d+)\.md$")
_STAMP_RE = re.compile(rf"^{STAMP_KEY}:\s*(\S+)\s*$", re.MULTILINE)

REASONS = {
    "fresh": "matches the chapter as it now stands",
    "stale": "the chapter's text changed after this summary was written",
    "unverified": "written before summaries carried a fingerprint of their chapter",
    "missing": "no summary yet",
}


def body_hash(chapter_text: str) -> str:
    """Fingerprint of a chapter's prose: the text after its YAML
    frontmatter and its `# Title` line, with line endings and trailing
    whitespace normalised. Frontmatter edits (`word_count`, `status`,
    `title`) leave it unchanged; any change to the prose changes it."""
    body = strip_yaml_frontmatter(chapter_text).replace("\r\n", "\n")
    lines = [ln.rstrip() for ln in body.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    if lines and lines[0].startswith("# "):
        lines.pop(0)
    body = "\n".join(lines).strip("\n")
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def summary_path_for(chapter_path: Path) -> Path:
    return chapter_path.with_name(f"{chapter_path.stem}.summary.md")


def read_stamp(summary_text: str) -> str | None:
    """The `summary_of:` fingerprint from a summary's frontmatter."""
    if not summary_text.startswith("---"):
        return None
    head = summary_text[: len(summary_text) - len(strip_yaml_frontmatter(summary_text))]
    m = _STAMP_RE.search(head)
    return m.group(1) if m else None


def summary_body(summary_text: str) -> str:
    return strip_yaml_frontmatter(summary_text).strip()


@dataclass
class SummaryState:
    chapter: int
    chapter_path: Path
    summary_path: Path
    status: str  # fresh | stale | unverified | missing
    stamped: bool = True  # False for a summary from before fingerprints

    @property
    def needs_refresh(self) -> bool:
        return self.status != "fresh"

    @property
    def reason(self) -> str:
        if self.status == "stale" and not self.stamped:
            return ("the chapter file is newer than this summary, which was written "
                    "before summaries carried a fingerprint")
        return REASONS[self.status]

    def to_dict(self, root: Path | None = None) -> dict:
        def rel(p: Path) -> str:
            if root is None:
                return str(p)
            try:
                return str(p.resolve().relative_to(root.resolve()))
            except ValueError:
                return str(p)
        return {
            "chapter": self.chapter,
            "status": self.status,
            "reason": self.reason,
            "chapter_file": rel(self.chapter_path),
            "summary_file": rel(self.summary_path),
        }


def state(chapter_path: Path) -> SummaryState:
    m = _CHAPTER_RE.match(chapter_path.name)
    chapter = int(m.group(1)) if m else 0
    spath = summary_path_for(chapter_path)
    if not spath.is_file():
        return SummaryState(chapter, chapter_path, spath, "missing")
    stext = spath.read_text(encoding="utf-8")
    if len(summary_body(stext)) < MIN_SUMMARY_CHARS:
        return SummaryState(chapter, chapter_path, spath, "missing")
    stamp = read_stamp(stext)
    if stamp is not None:
        current = body_hash(chapter_path.read_text(encoding="utf-8"))
        status = "fresh" if stamp == current else "stale"
        return SummaryState(chapter, chapter_path, spath, status)
    try:
        newer = chapter_path.stat().st_mtime > spath.stat().st_mtime
    except OSError:  # pragma: no cover
        newer = False
    return SummaryState(chapter, chapter_path, spath, "stale" if newer else "unverified",
                        stamped=False)


def chapter_files(book_root: Path) -> list[Path]:
    chapters_dir = book_root / "chapters"
    if not chapters_dir.is_dir():
        return []
    out = [p for p in chapters_dir.iterdir() if _CHAPTER_RE.match(p.name)]
    return sorted(out, key=lambda p: int(_CHAPTER_RE.match(p.name).group(1)))  # type: ignore[union-attr]


def book_states(book_root: Path, chapters: set[int] | None = None) -> list[SummaryState]:
    """One state per drafted chapter, in chapter order; `chapters`
    restricts the scan."""
    out: list[SummaryState] = []
    for path in chapter_files(book_root):
        s = state(path)
        if chapters is None or s.chapter in chapters:
            out.append(s)
    return out


class StampError(ValueError):
    pass


def stamp(chapter_path: Path) -> str:
    """Record in the chapter's summary that it summarises the chapter
    as it now stands. Call it right after writing the summary from the
    chapter, or after re-reading an existing summary against the chapter
    and finding it still true. Returns the fingerprint."""
    spath = summary_path_for(chapter_path)
    if not chapter_path.is_file():
        raise StampError(f"no chapter file at {chapter_path}")
    if not spath.is_file():
        raise StampError(f"no summary at {spath}; write the summary first")
    stext = spath.read_text(encoding="utf-8")
    body = summary_body(stext)
    if len(body) < MIN_SUMMARY_CHARS:
        raise StampError(f"{spath} is a stub ({len(body)} characters); write the summary first")
    fp = body_hash(chapter_path.read_text(encoding="utf-8"))
    line = f"{STAMP_KEY}: {fp}"
    if stext.startswith("---") and strip_yaml_frontmatter(stext) != stext:
        head = stext[: len(stext) - len(strip_yaml_frontmatter(stext))]
        rest = stext[len(head):]
        if _STAMP_RE.search(head):
            head = _STAMP_RE.sub(line, head, count=1)
        else:
            first_nl = head.index("\n") + 1
            head = head[:first_nl] + line + "\n" + head[first_nl:]
        new = head + rest
    else:
        new = f"---\n{line}\n---\n\n{body}\n"
    spath.write_text(new, encoding="utf-8")
    return fp


# ------------------------------------------------------------ eval logs

# A chapter's score describes the text the judge read. On one book every
# chapter but the first was scored before a whole-book pass cut about 160
# repeats, and the scores went on being reported as the book's (author,
# 2026-10-25: "Without scoring the current content to see how good?").
# An eval log now records the fingerprint of the text it scored, and every
# surface that shows a score says whether it is a score of this text.

EVAL_KEY = "scored_text"
SCORE_STATES = {
    "current": "scored on the chapter as it now stands",
    "older": "scored on an older text of the chapter",
    "unstamped": "the score doesn't record which text it was taken on",
}


def score_state(chapter_path: Path, scored_text: str | None) -> str:
    """`current`, `older` or `unstamped` for a score whose eval log
    recorded `scored_text` (None: no record)."""
    if not scored_text:
        return "unstamped"
    return "current" if scored_text == body_hash(chapter_path.read_text(encoding="utf-8")) else "older"


def stamp_eval(chapter_path: Path) -> tuple[Path, str]:
    """Record in the chapter's latest eval log (the one every score
    column reads) the fingerprint of the chapter as it now stands. Run it
    right after writing the log, before anything changes the chapter.
    Returns the log's path and the fingerprint."""
    import json

    from .mechanical.chapter_summary import latest_chapter_eval_path
    m = _CHAPTER_RE.match(chapter_path.name)
    if not m or not chapter_path.is_file():
        raise StampError(f"no chapter file at {chapter_path}")
    eval_dir = chapter_path.parent.parent / "eval_logs"
    log = latest_chapter_eval_path(eval_dir, int(m.group(1)))
    if log is None:
        raise StampError(f"no eval log with an overall_score for {chapter_path.name}; "
                         f"write the eval log first")
    # The log just written must be the one the name order calls latest. A
    # log named in local time instead of UTC sorts early, and the stamp
    # would land on an older score and make it look current.
    newest = _newest_written_eval(eval_dir, int(m.group(1)))
    if newest is not None and newest != log and newest.stat().st_mtime > log.stat().st_mtime + 1:
        raise StampError(f"{newest.name} was written after {log.name} but its name sorts "
                         f"earlier; name eval logs by UTC time (`date -u +%Y%m%d_%H%M%S`) "
                         f"and rename it before stamping")
    data = json.loads(log.read_text(encoding="utf-8"))
    fp = body_hash(chapter_path.read_text(encoding="utf-8"))
    data[EVAL_KEY] = fp
    log.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return log, fp


def _newest_written_eval(eval_dir: Path, chapter: int) -> Path | None:
    """The chapter's timestamp-named eval log with the latest mtime."""
    from .mechanical.chapter_summary import _iter_chapter_eval_files
    best: Path | None = None
    for ch, _when, path in _iter_chapter_eval_files(eval_dir):
        if ch != chapter or not re.match(r"^\d{8}_\d{6}_", path.name):
            continue
        if best is None or path.stat().st_mtime > best.stat().st_mtime:
            best = path
    return best


# ------------------------------------------------------------ briefs

BRIEF_KEY = "brief_for"
_BRIEF_RE = re.compile(rf"^{BRIEF_KEY}:\s*(\S+)\s*$", re.MULTILINE)


def brief_path_for(chapter_path: Path) -> Path:
    m = _CHAPTER_RE.match(chapter_path.name)
    n = int(m.group(1)) if m else 0
    return chapter_path.parent.parent / "briefs" / f"ch{n:02d}.md"


def brief_pending(chapter_path: Path) -> bool | None:
    """Is the chapter's revision brief still waiting for its revise?

    A brief records the fingerprint of the chapter it was written
    against (`brief_for:`, by `autonovel _stamp-brief`); it is pending
    while the chapter's prose is unchanged since, and consumed once the
    chapter has been rewritten. A brief from before fingerprints falls
    back to the old test (brief file newer than the chapter file).
    None when there is no brief."""
    bpath = brief_path_for(chapter_path)
    if not bpath.is_file() or not chapter_path.is_file():
        return None
    text = bpath.read_text(encoding="utf-8")
    m = _BRIEF_RE.search(text[: len(text) - len(strip_yaml_frontmatter(text))]) if text.startswith("---") else None
    if m:
        return m.group(1) == body_hash(chapter_path.read_text(encoding="utf-8"))
    return bpath.stat().st_mtime > chapter_path.stat().st_mtime


def stamp_brief(chapter_path: Path) -> str:
    """Record in the chapter's brief the fingerprint of the chapter as it
    now stands, the text the brief was written against."""
    bpath = brief_path_for(chapter_path)
    if not chapter_path.is_file():
        raise StampError(f"no chapter file at {chapter_path}")
    if not bpath.is_file():
        raise StampError(f"no brief at {bpath}; write the brief first")
    text = bpath.read_text(encoding="utf-8")
    fp = body_hash(chapter_path.read_text(encoding="utf-8"))
    line = f"{BRIEF_KEY}: {fp}"
    if text.startswith("---") and strip_yaml_frontmatter(text) != text:
        head = text[: len(text) - len(strip_yaml_frontmatter(text))]
        rest = text[len(head):]
        if _BRIEF_RE.search(head):
            head = _BRIEF_RE.sub(line, head, count=1)
        else:
            nl = head.index("\n") + 1
            head = head[:nl] + line + "\n" + head[nl:]
        new = head + rest
    else:
        new = f"---\n{line}\n---\n\n{text.lstrip()}"
    bpath.write_text(new, encoding="utf-8")
    return fp
