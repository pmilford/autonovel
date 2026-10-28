"""Is this version ready for the author to read?

A version went to one author four times with whole-book reviews that had
never run on it, or ran two versions earlier: the reader panel and the
dual review never ran on the book at all, the developmental edit was two
versions old, and every chapter score had been taken before the last
pass. The footer had printed the next review after every build; nothing
stopped the build going out. The author: "You are wasting my time asking
me to read content that has not been reviewed and corrected by our
tools." (2026-10-25)

`check` lists everything that must hold before a version goes to the
author, in the order `/autonovel:review-cycle` makes it hold:

  1. summaries        every continuity summary matches its chapter
  2. chapter scores   every chapter scored on the text as it stands
  3. floor            no chapter dimension under the floor
  4. cold readers     a cold reader read every chapter as it stands
                      (within a light fix), the chapter was scored
                      after that read, and no item it found is open
  5. said-once        the whole-book repetition ledger read this text
  6. structure        the structure review read this text, and passes
  7. letter           the developmental edit read this text
  8. reader panel     the reader panel read this text
  9. review           the dual review read this text
 10. book score       `evaluate --full` read this text
 11. book floor       no dimension of that score under the floor
 12. fixes acted on   no staged fix in briefs/conversation.md still queued

A whole-book report "read this text" when it was stamped
(`autonovel _stamp-report`) with the fingerprint of every chapter as it
now stands, or when the chapters have changed since only by a light fix
pass (see `BOOK_CHANGE_LIMIT`); `report_stamps.json` under edit_logs/
holds the stamps. A report without a stamp counts as not read. Pure
Python; no LLM.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .. import summaries
from ..paths import iter_chapter_files

STAMPS_FILE = "report_stamps.json"

# key -> (what it is, file it writes relative to the book root, command)
REPORTS: dict[str, tuple[str, str, str]] = {
    "said_once": ("the whole-book repetition ledger", "edit_logs/said_once_ledger.md",
                  "/autonovel:said-once --book {book} --stage"),
    "structure_review": ("the structure review", "edit_logs/structure_review.json",
                         "/autonovel:structure-review --book {book}"),
    "developmental_edit": ("the developmental edit (editor's letter)", "edit_logs/editor_letter.md",
                           "/autonovel:developmental-edit --book {book} --stage"),
    "reader_panel": ("the reader panel", "edit_logs/reader_panel.json",
                     "/autonovel:reader-panel --book {book}"),
    "review": ("the dual review", "edit_logs/review.json",
               "/autonovel:review --book {book}"),
    "full_eval": ("the whole-book score (evaluate --full)", "eval_logs",
                  "/autonovel:evaluate --full --book {book}"),
}

_CHAPTER_RE = re.compile(r"^ch_(\d+)\.md$")

# The whole-book reports that judge the order itself: the chain from
# chapter to chapter and the act ladder (the structure review), the pace
# (the whole-book score). When chapters are renumbered (`renumber.py`),
# these read the book again; the reader panel, the dual review and the
# editor's letter judge what is on the page, so their references follow
# the text and they stand. The said-once ledger reads it again only when a
# point's first telling now comes after a later one.
ORDER_JUDGED = ("structure_review", "full_eval")


@dataclass
class Check:
    key: str
    ok: bool
    what: str
    detail: str = ""
    command: str | None = None

    def to_dict(self) -> dict:
        return {"key": self.key, "ok": self.ok, "what": self.what,
                "detail": self.detail, "command": self.command}


@dataclass
class GateReport:
    book: str
    checks: list[Check] = field(default_factory=list)

    @property
    def passes(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def open(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]

    def to_dict(self) -> dict:
        return {"book": self.book, "passes": self.passes,
                "open": len(self.open), "checks": [c.to_dict() for c in self.checks]}


# ------------------------------------------------------------ report stamps


def chapter_fingerprints(book_root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in iter_chapter_files(book_root / "chapters"):
        m = _CHAPTER_RE.match(path.name)
        if m:
            out[str(int(m.group(1)))] = summaries.body_hash(path.read_text(encoding="utf-8"))
    return out


def paragraph_hashes(book_root: Path) -> dict[str, list[str]]:
    """Short hashes of every paragraph of every chapter, so a later check
    can tell a light fix pass from a rewrite."""
    import hashlib
    from ..mechanical.frontmatter import strip_yaml_frontmatter
    out: dict[str, list[str]] = {}
    for path in iter_chapter_files(book_root / "chapters"):
        m = _CHAPTER_RE.match(path.name)
        if not m:
            continue
        body = strip_yaml_frontmatter(path.read_text(encoding="utf-8"))
        paras = [p.strip() for p in body.split("\n\n") if p.strip()]
        out[str(int(m.group(1)))] = [hashlib.sha1(p.encode("utf-8")).hexdigest()[:8] for p in paras]
    return out


# A whole-book report stays current through a light fix pass: it read the
# book, and a few changed sentences don't change what it found. One that
# re-ran after every pass would never let the review cycle finish. A
# rewrite (more than this share of the book's words, or of one chapter's)
# sends it back to be read again. A cold reader's report on one chapter
# stands through less (FIRST_READ_CHANGE_LIMIT). Chapter scores have no
# such allowance: they describe one chapter's text exactly.
#
# The share is of the words the reviewer read that are now changed or
# gone, measured against a copy of that text kept at the stamp
# (`stamped_texts/`). Counting touched paragraphs instead made a pass of
# forty one-clause fixes look like a rewrite, and sent every chapter back
# to a fresh reader who found forty more (2026-10-26). Stamps made before
# the copies were kept fall back to the paragraph count.
BOOK_CHANGE_LIMIT = 0.10
CHAPTER_CHANGE_LIMIT = 0.25
FIRST_READ_CHANGE_LIMIT = 0.15
SNAPSHOT_DIR = "stamped_texts"


def _body_of(path: Path) -> str:
    from ..mechanical.frontmatter import strip_yaml_frontmatter
    return strip_yaml_frontmatter(path.read_text(encoding="utf-8"))


def _snapshot_path(book_root: Path, key: str, chapter: int | str) -> Path:
    return book_root / "edit_logs" / SNAPSHOT_DIR / key / f"ch{int(chapter):02d}.md"


def _write_snapshots(book_root: Path, key: str, chapters: dict[int, Path]) -> None:
    folder = book_root / "edit_logs" / SNAPSHOT_DIR / key
    folder.mkdir(parents=True, exist_ok=True)
    for n, path in chapters.items():
        (folder / f"ch{n:02d}.md").write_text(_body_of(path), encoding="utf-8")


def word_change(old_text: str, new_text: str) -> float:
    """Share of the old text's words that are changed or gone in the new
    (0.0 identical, 1.0 nothing left)."""
    import difflib
    a, b = old_text.split(), new_text.split()
    if not a:
        return 0.0 if not b else 1.0
    same = sum(m.size for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return 1.0 - same / len(a)


def _numbered_chapters(book_root: Path) -> dict[int, Path]:
    out: dict[int, Path] = {}
    for path in iter_chapter_files(book_root / "chapters"):
        m = _CHAPTER_RE.match(path.name)
        if m:
            out[int(m.group(1))] = path
    return out


def _stamps_path(book_root: Path) -> Path:
    return book_root / "edit_logs" / STAMPS_FILE


def load_stamps(book_root: Path) -> dict:
    path = _stamps_path(book_root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def stamp_report(book_root: Path, key: str) -> dict:
    """Record that report `key` was written from the chapters as they now
    stand. Run it right after the report is written."""
    if key not in REPORTS:
        raise KeyError(f"unknown report {key!r}; one of {', '.join(REPORTS)}")
    stamps = load_stamps(book_root)
    entry = {"when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "chapters": chapter_fingerprints(book_root),
             "paragraphs": paragraph_hashes(book_root),
             "texts": f"{SNAPSHOT_DIR}/{key}"}
    folder = book_root / "edit_logs" / SNAPSHOT_DIR / key
    if folder.is_dir():
        for old in folder.glob("ch*.md"):
            old.unlink()
    _write_snapshots(book_root, key, _numbered_chapters(book_root))
    stamps[key] = entry
    path = _stamps_path(book_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stamps, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return entry


def _reordered_chapters(entry: dict) -> list[int]:
    """Chapters a renumbering moved since the report was stamped, when
    the move changed what the report judges (`ORDER_JUDGED`); the mark is
    written by `renumber.py` and cleared by stamping the report again."""
    mark = entry.get("reordered")
    if not isinstance(mark, dict):
        return []
    return sorted(int(n) for n in mark.get("chapters", []) if str(n).isdigit())


def report_state(book_root: Path, key: str) -> tuple[str, list[int]]:
    """(`current` | `light` | `reordered` | `older` | `unstamped` |
    `missing`, chapters changed since the report read them). `light`:
    changed, but within the limits above, so the report still stands.
    `reordered`: chapters were renumbered since, and this report judges
    the order (`ORDER_JUDGED`)."""
    _what, rel, _cmd = REPORTS[key]
    target = book_root / rel
    if key == "full_eval":
        present = target.is_dir() and any(target.glob("*_full.json"))
    else:
        present = target.is_file()
    if not present:
        return "missing", []
    entry = load_stamps(book_root).get(key)
    if not isinstance(entry, dict) or not isinstance(entry.get("chapters"), dict):
        return "unstamped", []
    reordered = _reordered_chapters(entry)
    if reordered:
        return "reordered", reordered
    then = entry["chapters"]
    now = chapter_fingerprints(book_root)
    changed = sorted(int(n) for n in set(now) | set(then) if now.get(n) != then.get(n))
    if not changed:
        return "current", []
    if set(now) != set(then):
        return "older", changed
    if entry.get("texts"):
        chapters = _numbered_chapters(book_root)
        total = moved = 0.0
        for n in changed:
            snap = _snapshot_path(book_root, key, n)
            if not snap.is_file() or n not in chapters:
                return "older", changed
            old = snap.read_text(encoding="utf-8")
            share = word_change(old, _body_of(chapters[n]))
            if share > CHAPTER_CHANGE_LIMIT:
                return "older", changed
            moved += share * len(old.split())
        for n, path in chapters.items():
            snap = _snapshot_path(book_root, key, n)
            total += len(snap.read_text(encoding="utf-8").split()) if snap.is_file() else 0
        if total and moved / total > BOOK_CHANGE_LIMIT:
            return "older", changed
        return "light", changed
    if not isinstance(entry.get("paragraphs"), dict):
        return "older", changed
    before = entry["paragraphs"]
    after = paragraph_hashes(book_root)
    total = moved = 0
    for n, paras in after.items():
        old = before.get(n) or []
        gone = len(set(old) - set(paras))
        new = len(set(paras) - set(old))
        size = max(len(old), len(paras), 1)
        if max(gone, new) / size > CHAPTER_CHANGE_LIMIT:
            return "older", changed
        total += size
        moved += max(gone, new)
    if total and moved / total > BOOK_CHANGE_LIMIT:
        return "older", changed
    return "light", changed


# ------------------------------------------------------------ cold readers
#
# A cold reader's open items were counted from whatever report was last
# written, however old: on one book every report predated two versions and
# two review rounds, so the gate counted items nobody had looked for in
# the text the author would read (2026-10-25). The author should never be
# the first reader (`/autonovel:first-read`), so each chapter's report is
# stamped with the text it read, like the whole-book reports, and holds
# through a light fix of that chapter only.

FIRST_READ_KEY = "first_read"


def _paragraph_hashes_of(text: str) -> list[str]:
    import hashlib
    from ..mechanical.frontmatter import strip_yaml_frontmatter
    body = strip_yaml_frontmatter(text)
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    return [hashlib.sha1(p.encode("utf-8")).hexdigest()[:8] for p in paras]


def _chapter_file(book_root: Path, chapter: int) -> Path | None:
    for path in iter_chapter_files(book_root / "chapters"):
        m = _CHAPTER_RE.match(path.name)
        if m and int(m.group(1)) == chapter:
            return path
    return None


def first_read_reports(book_root: Path, chapter: int) -> list[Path]:
    """`first_read_chNN.md` and the second reader's `first_read_chNN_2.md`."""
    pat = re.compile(rf"^first_read_ch0*{chapter}(?:_\d+)?\.md$")
    edit = book_root / "edit_logs"
    if not edit.is_dir():
        return []
    return sorted(p for p in edit.iterdir() if pat.match(p.name))


def archive_first_reads(book_root: Path, chapter: int) -> list[Path]:
    """Move the chapter's earlier cold-reader reports into
    `edit_logs/first_read_archive/`, each named with its date, before a new
    reader reads the chapter. Left in place, an old second reader's
    `first_read_chNN_2.md` is read by evaluate as the latest report on
    the new text."""
    from datetime import date
    moved: list[Path] = []
    archive = book_root / "edit_logs" / "first_read_archive"
    for path in first_read_reports(book_root, chapter):
        day = date.fromtimestamp(path.stat().st_mtime).strftime("%Y%m%d")
        archive.mkdir(parents=True, exist_ok=True)
        target = archive / f"{path.stem}_{day}{path.suffix}"
        i = 2
        while target.exists():
            target = archive / f"{path.stem}_{day}_{i}{path.suffix}"
            i += 1
        path.rename(target)
        moved.append(target)
    return moved


def stamp_first_read(book_root: Path, chapter: int) -> dict:
    """Record that the cold reader's report on `chapter` read the chapter
    as it now stands. `/autonovel:first-read` runs it after saving."""
    path = _chapter_file(book_root, chapter)
    if path is None:
        raise KeyError(f"no chapter {chapter} in {book_root.name}")
    text = path.read_text(encoding="utf-8")
    stamps = load_stamps(book_root)
    reads = stamps.get(FIRST_READ_KEY)
    if not isinstance(reads, dict):
        reads = {}
    entry = {"when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "chapter": summaries.body_hash(text),
             "paragraphs": _paragraph_hashes_of(text),
             "text": f"{SNAPSHOT_DIR}/{FIRST_READ_KEY}/ch{chapter:02d}.md"}
    _write_snapshots(book_root, FIRST_READ_KEY, {chapter: path})
    reads[str(chapter)] = entry
    stamps[FIRST_READ_KEY] = reads
    out = _stamps_path(book_root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(stamps, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return entry


def first_read_state(book_root: Path, chapter: int) -> str:
    """`current` | `light` | `older` | `unstamped` | `missing` for the cold
    reader's report on one chapter (`light`: changed since, within
    `CHAPTER_CHANGE_LIMIT`, so the report still stands)."""
    if not first_read_reports(book_root, chapter):
        return "missing"
    reads = load_stamps(book_root).get(FIRST_READ_KEY)
    entry = reads.get(str(chapter)) if isinstance(reads, dict) else None
    path = _chapter_file(book_root, chapter)
    if not isinstance(entry, dict) or path is None:
        return "unstamped"
    if entry.get("order_changed"):
        # The chapters before this one changed in a renumbering, and a cold
        # reader's "I didn't know" depends on what came before.
        return "older"
    text = path.read_text(encoding="utf-8")
    if entry.get("chapter") == summaries.body_hash(text):
        return "current"
    snap = _snapshot_path(book_root, FIRST_READ_KEY, chapter)
    if entry.get("text") and snap.is_file():
        share = word_change(snap.read_text(encoding="utf-8"), _body_of(path))
        return "light" if share <= FIRST_READ_CHANGE_LIMIT else "older"
    old = entry.get("paragraphs")
    if not isinstance(old, list):
        return "older"
    now = _paragraph_hashes_of(text)
    changed = max(len(set(old) - set(now)), len(set(now) - set(old)))
    return "light" if changed / max(len(old), len(now), 1) <= CHAPTER_CHANGE_LIMIT else "older"


def read_changes(book_root: Path) -> dict:
    """How much each report's text has changed since it was read: for every
    chapter's cold read, the share of its words changed (None when the
    stamp kept no copy) and its state; for every whole-book report, the
    share of the book's words changed and its state."""
    chapters = _numbered_chapters(book_root)
    cold = {}
    for n, path in chapters.items():
        snap = _snapshot_path(book_root, FIRST_READ_KEY, n)
        share = (word_change(snap.read_text(encoding="utf-8"), _body_of(path))
                 if snap.is_file() else None)
        cold[n] = {"state": first_read_state(book_root, n), "changed": share}
    books = {}
    for key in REPORTS:
        state, _changed = report_state(book_root, key)
        total = moved = 0.0
        kept = True
        for n, path in chapters.items():
            snap = _snapshot_path(book_root, key, n)
            if not snap.is_file():
                kept = False
                break
            old = snap.read_text(encoding="utf-8")
            total += len(old.split())
            moved += word_change(old, _body_of(path)) * len(old.split())
        books[key] = {"state": state, "changed": (moved / total if total else 0.0) if kept else None}
    return {"cold_reads": cold, "reports": books,
            "limits": {"cold_read": FIRST_READ_CHANGE_LIMIT, "chapter": CHAPTER_CHANGE_LIMIT,
                       "book": BOOK_CHANGE_LIMIT}}


def _first_read_when(book_root: Path, chapter: int) -> float | None:
    reads = load_stamps(book_root).get(FIRST_READ_KEY)
    entry = reads.get(str(chapter)) if isinstance(reads, dict) else None
    try:
        return datetime.fromisoformat(entry["when"]).timestamp()
    except (TypeError, KeyError, ValueError):
        return None


def _latest_score_when(eval_dir: Path) -> dict[int, float]:
    from ..mechanical.chapter_summary import _eval_number, _iter_chapter_eval_logs
    out: dict[int, float] = {}
    for chapter, when, data in _iter_chapter_eval_logs(eval_dir):
        if _eval_number(data, "overall_score") is not None and when > out.get(chapter, -1.0):
            out[chapter] = when
    return out


# ------------------------------------------------------------ the gate


def _ranges(nums: list[int]) -> str:
    out: list[str] = []
    start = prev = None
    for n in sorted(nums):
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(f"{start}" if start == prev else f"{start}-{prev}")
            start = prev = n
    if start is not None:
        out.append(f"{start}" if start == prev else f"{start}-{prev}")
    return ", ".join(out)


def check(book_root: Path, *, floor: float = 7.0) -> GateReport:
    from ..mechanical.chapter_summary import chapter_score_details
    from ..mechanical import structure_review

    book = book_root.name
    rep = GateReport(book=book)
    chapters = [p for p in iter_chapter_files(book_root / "chapters") if _CHAPTER_RE.match(p.name)]
    numbers = {int(_CHAPTER_RE.match(p.name).group(1)): p for p in chapters}

    stale = [s.chapter for s in summaries.book_states(book_root) if s.needs_refresh]
    rep.checks.append(Check(
        "summaries", not stale, "every continuity summary matches its chapter",
        f"refresh ch {_ranges(stale)}" if stale else "",
        f"/autonovel:summarize-chapter --stale --book {book}" if stale else None))

    details = chapter_score_details(book_root / "eval_logs")
    unscored, older = [], []
    for n, path in numbers.items():
        d = details.get(n)
        if d is None:
            unscored.append(n)
        elif summaries.score_state(path, d.scored_text) != "current":
            older.append(n)
    need = sorted(unscored + older)
    rep.checks.append(Check(
        "chapter_scores", not need, "every chapter scored on the text as it stands",
        f"score ch {_ranges(need)}" if need else "",
        f"/autonovel:evaluate --chapter {need[0]} --book {book} (and each of ch {_ranges(need)})"
        if need else None))

    low = sorted((d.chapter, d.low_dim, d.low_score) for d in details.values()
                 if d.low_score is not None and d.low_score < floor and d.chapter in numbers)
    rep.checks.append(Check(
        "floor", not low, f"no chapter dimension under the {floor:.1f} floor",
        "; ".join(f"ch {c} {dim} {s:.1f}" for c, dim, s in low),
        f"/autonovel:revision-pass --chapters {','.join(str(c) for c, _, _ in low)} --book {book}"
        if low else None))

    unread = [n for n in numbers if first_read_state(book_root, n) not in ("current", "light")]
    scored_at = _latest_score_when(book_root / "eval_logs")
    unchecked = [n for n in numbers if n not in unread and n not in need
                 and (_first_read_when(book_root, n) or 0) > scored_at.get(n, 0)]
    open_reader = sorted(d.chapter for d in details.values()
                         if d.reader_open and d.chapter in numbers
                         and d.chapter not in unread and d.chapter not in unchecked)
    parts = []
    if unread:
        parts.append(f"no cold reader has read the text as it stands: ch {_ranges(sorted(unread))}")
    if unchecked:
        parts.append(f"scored before its cold read, so nobody checked the reader's items: "
                     f"ch {_ranges(sorted(unchecked))}")
    if open_reader:
        parts.append(f"open in ch {_ranges(open_reader)}")
    if unread:
        first = sorted(unread)
        reader_cmd = (f"/autonovel:first-read {first[0]} --book {book} "
                      f"(and each of ch {_ranges(first)})")
    elif unchecked:
        reader_cmd = (f"/autonovel:evaluate --chapter {min(unchecked)} --book {book} "
                      f"(and each of ch {_ranges(sorted(unchecked))})")
    elif open_reader:
        reader_cmd = f"/autonovel:revision-pass --chapters {','.join(map(str, open_reader))} --book {book}"
    else:
        reader_cmd = None
    rep.checks.append(Check(
        "cold_readers", not parts,
        "a cold reader read every chapter as it stands, and no item it found is open",
        "; ".join(parts), reader_cmd))

    for key, (what, _rel, cmd) in REPORTS.items():
        state, changed = report_state(book_root, key)
        ok = state in ("current", "light")
        detail = {"missing": "never run on this book",
                  "unstamped": "doesn't record which text it read",
                  "older": f"read an older text (ch {_ranges(changed)} rewritten since)",
                  "reordered": f"read the chapters in an older order (ch {_ranges(changed)} "
                               f"renumbered since), and it judges the order",
                  "light": f"light fixes since in ch {_ranges(changed)}; still stands",
                  "current": ""}[state]
        if key == "structure_review" and ok:
            gate = structure_review.check(book_root / "edit_logs" / "structure_review.json",
                                          book_root=book_root).gate
            # Its own staleness test reads file times; the stamp above has
            # already decided whether this review read the text.
            reasons = [str(r) for r in gate.get("reasons", []) if not str(r).startswith("stale")]
            if reasons:
                ok = False
                detail = "read this text, but its gate blocks: " + "; ".join(reasons)
        rep.checks.append(Check(key, ok, f"{what} read this text", detail,
                                None if ok else cmd.format(book=book)))

    under = _book_dimensions_under(book_root, floor)
    rep.checks.append(Check(
        "book_floor", not under, f"no whole-book dimension under the {floor:.1f} floor",
        ("; ".join(f"{name} {score:.1f}" for name, score in under)
         + f" — fix where the score names, then take it again "
           f"(`/autonovel:evaluate --full --book {book}`); a light fix lets "
           f"the score stand but doesn't lift it") if under else "",
        f"/autonovel:review-cycle --book {book}" if under else None))

    queued = _queued_turns(book_root)
    rep.checks.append(Check(
        "fixes_acted_on", not queued, "every staged fix carried out",
        f"{len(queued)} staged turn(s) still queued, ch {_ranges(sorted(set(queued)))}"
        if queued else "",
        f"/autonovel:revision-pass --chapters {','.join(map(str, sorted(set(queued))))} --book {book}"
        if queued else None))
    return rep


def _book_dimensions_under(book_root: Path, floor: float) -> list[tuple[str, float]]:
    """Dimensions of the latest whole-book score (`evaluate --full`) under
    the floor, lowest first. A book scored once and found slow in the
    whole (engagement 6.5) passed every chapter's floor; the scorecard's
    own floor is a release condition too."""
    logs = sorted((book_root / "eval_logs").glob("*_full.json")) if (book_root / "eval_logs").is_dir() else []
    if not logs:
        return []
    try:
        data = json.loads(logs[-1].read_text(encoding="utf-8"))
    except ValueError:
        return []
    dims = data.get("dimensions") if isinstance(data, dict) else None
    out: list[tuple[str, float]] = []
    if isinstance(dims, dict):
        for name, body in dims.items():
            score = body.get("score") if isinstance(body, dict) else body
            if isinstance(score, (int, float)) and not isinstance(score, bool) and score < floor:
                out.append((name, float(score)))
    return sorted(out, key=lambda x: x[1])


_TURN_RE = re.compile(r"^## .*?turn", re.MULTILINE)


def _queued_turns(book_root: Path) -> list[int]:
    """Chapter numbers of turns in briefs/conversation.md still marked
    `**Status:** queued`."""
    path = book_root / "briefs" / "conversation.md"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    starts = [m.start() for m in _TURN_RE.finditer(text)] + [len(text)]
    out: list[int] = []
    for a, b in zip(starts, starts[1:]):
        block = text[a:b]
        if not re.search(r"\*\*Status:\*\*\s*queued", block):
            continue
        m = re.search(r"\*\*Target:\*\*\s*chapter\s+(\d+)", block)
        out.append(int(m.group(1)) if m else 0)
    return out


TURN_STATUSES = ("queued", "applied", "declined")
_TURN_NUM_RE = re.compile(r"^## .*?turn (\d+)\b", re.MULTILINE)


def set_turn_status(book_root: Path, turns: list[int], status: str) -> dict[int, str]:
    """Set `**Status:**` on the numbered turns of briefs/conversation.md.

    The one writer of a turn's status when a sweep runs its chapters in
    parallel (`/autonovel:review-cycle`): the per-chapter workers leave the
    file alone and the sweep marks what each carried out. `declined` is for
    a staged finding the editor decided against, with the reason in the
    round notes; the gate counts only `queued`. Returns {turn: previous
    status}; raises KeyError naming any turn not in the file."""
    if status not in TURN_STATUSES:
        raise ValueError(f"status must be one of {', '.join(TURN_STATUSES)}")
    path = book_root / "briefs" / "conversation.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    marks = list(_TURN_NUM_RE.finditer(text))
    spans = {int(m.group(1)): (m.start(), marks[i + 1].start() if i + 1 < len(marks) else len(text))
             for i, m in enumerate(marks)}
    missing = [t for t in turns if t not in spans]
    if missing:
        raise KeyError(f"no turn {', '.join(map(str, missing))} in {path}")
    previous: dict[int, str] = {}
    for t in sorted(set(turns), reverse=True):
        a, b = spans[t]
        block = text[a:b]
        m = re.search(r"\*\*Status:\*\*\s*(\w+)", block)
        if not m:
            new_block = block.rstrip("\n") + f"\n\n**Status:** {status}\n\n"
            previous[t] = "none"
        else:
            previous[t] = m.group(1)
            new_block = block[:m.start(1)] + status + block[m.end(1):]
        text = text[:a] + new_block + text[b:]
    path.write_text(text, encoding="utf-8")
    return previous


def render_markdown(rep: GateReport) -> str:
    lines = [f"# Ready for the author? — {rep.book}", ""]
    lines.append("**Ready.** Every whole-book review read this text and its fixes are made."
                 if rep.passes else
                 f"**Not ready: {len(rep.open)} of {len(rep.checks)} checks open.** "
                 "Don't hand this version to the author; run "
                 f"`/autonovel:review-cycle --book {rep.book}`.")
    lines.append("")
    for c in rep.checks:
        mark = "✓" if c.ok else "✗"
        line = f"- {mark} {c.what}"
        if c.detail:
            line += f" — {c.detail}"
        if c.command and not c.ok:
            line += f" (`{c.command}`)"
        lines.append(line)
    return "\n".join(lines) + "\n"
