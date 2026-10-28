"""Give chapters new numbers, and move everything that names a chapter by
its number with them.

A chapter's number is its key in more than a dozen places: its summary,
its brief, every eval log, its cold reader's report, the stamped copies of
the text each whole-book report read, the outline's entry, the plates
placed before it, and every "ch 10" in the reports, the design and the
canon. A reorder that moved only `ch_NN.md` left every one of those
pointing at the wrong chapter: the brief for the new chapter 10 was the
old chapter 10's, its score was another chapter's score, and the release
gate saw every chapter as rewritten and sent every whole-book review back
to be read again (2026-10-28, a swap of two chapters on one book).

`renumber` moves them all by one map, then decides what the move itself
changed:

  - every file named for a chapter moves with its chapter (two-phase, so
    no two names collide);
  - every reference to a chapter by number in the book's working files
    (outline, design, cast, canon, appendix, briefs, summaries, eval
    logs, the current whole-book reports, the plates manifest) follows
    the text; dated and archived files are history and stay as written;
  - the outline's chapter entries are put back in reading order;
  - the stamps follow the text, so a chapter that only moved still counts
    as read by every report that read it;
  - what the order itself changed is sent back: a chapter whose previous
    chapter is now a different one is scored again (its score judged
    continuity against the old one); a chapter whose earlier chapters
    are now a different set is read cold again (a cold reader's "I
    didn't know" depends on what came before); the structure review and
    the whole-book score, which judge the order itself, read the book
    again; the said-once ledger reads it again only when a point's first
    telling now comes after a later one.

Pure Python; no LLM.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import release_gate
from ..paths import iter_chapter_files

ORDER_JUDGED = release_gate.ORDER_JUDGED

_CHAPTER_RE = re.compile(r"^ch_(\d+)\.md$")

# (folder relative to the book root, filename pattern with groups
# (prefix, number, rest), recurse?)
_FILE_PATTERNS: list[tuple[str, re.Pattern, bool]] = [
    ("chapters", re.compile(r"^(ch_)(\d+)(\..+)$"), False),
    ("briefs", re.compile(r"^(ch)(\d+)((?:[._-].*)?)$"), False),
    ("eval_logs", re.compile(r"^(ch)(\d+)(_.+)$"), False),
    ("eval_logs", re.compile(r"^(\d{8}_\d{6}_ch)(\d+)((?:_eval)?\.json)$"), False),
    ("edit_logs", re.compile(r"^(ch)(\d+)(_.+)$"), False),
    ("edit_logs", re.compile(r"^(first_read_ch)(\d+)((?:_\d+)?(?:\.prev)?\.md)$"), False),
    (f"edit_logs/{release_gate.SNAPSHOT_DIR}", re.compile(r"^(ch)(\d+)(\.md)$"), True),
    ("art", re.compile(r"^(ornament_ch)(\d+)(\..+)$"), True),
    ("art", re.compile(r"^(ch)(\d+)(_.+)$"), True),
    ("audiobook", re.compile(r"^(ch_?)(\d+)([._-].+)$"), True),
]

# Working files whose chapter references follow the text. Anything dated
# (`_2026-10-25T1738`, `_20261028`), archived or a diff is history.
_REF_FILES = [
    "outline.md", "design.md", "cast.md", "canon.md", "pending_canon.md",
    "appendix.md", "glossary.md", "introduction.md",
    "edit_logs/said_once_ledger.md", "edit_logs/structure_review.md",
    "edit_logs/structure_review.json", "edit_logs/editor_letter.md",
    "edit_logs/editor_read_notes.md", "edit_logs/reader_panel.json",
    "edit_logs/review.json", "edit_logs/review.md",
]
_REF_GLOBS = [
    "briefs/*.md", "chapters/ch_*.summary.md", "eval_logs/*.json",
    "edit_logs/first_read_ch*.md",
]
_DATED_RE = re.compile(r"(?:_\d{4}-\d{2}-\d{2}|_\d{8})")

# "ch 10", "ch. 10", "chs 10-12", "chapter 10", "Chapters 7 and 8",
# "ch 2, 6 and 8"; or a file name, "first_read_ch10.md", "ch_10.md".
_NUM = r"\d{1,3}(?!\d)"
# A range never crosses a line: "ch 1" at a line's end and a "- 10 because"
# list item under it once read as "ch 1-10" and merged two lines.
_SEP = r"(?:[ \t]*[-–—][ \t]*|[ \t]+to[ \t]+|\s*,\s*(?:and\s+|or\s+)?|\s+and\s+|\s*&\s*|\s+or\s+)"
_REF_RE = re.compile(
    rf"(?P<file>(?<![A-Za-z])ch_?(?P<fnum>\d{{2}})(?=[._-]))"
    rf"|(?P<word>\b(?:[Cc]hapters?|CHAPTERS?|[Cc]hs?\.?)[ \t]*)(?P<nums>{_NUM}(?:{_SEP}{_NUM})*)"
)
_RANGE_SEP_RE = re.compile(r"^[ \t]*(?:[-–—]|to)[ \t]*$")
_SPINE_RE = re.compile(r"^(\s*-\s*)(\d+)( because )(\d+)", re.MULTILINE)
_YAML_CHAPTER_RE = re.compile(r"^(\s*-?\s*chapter:\s*)(\d+)(\s*)$", re.MULTILINE)
_HEADING_RE = re.compile(r"^(#{2,4}) Chapter (\d+)\b", re.MULTILINE)


class RenumberError(ValueError):
    pass


@dataclass
class RenumberReport:
    book: str
    mapping: dict[int, int]
    moved: list[tuple[str, str]] = field(default_factory=list)
    rewritten: list[str] = field(default_factory=list)
    rescore: list[int] = field(default_factory=list)
    reread: list[int] = field(default_factory=list)
    seams: list[tuple[int, int]] = field(default_factory=list)
    order_reports: list[str] = field(default_factory=list)
    said_once_inverted: list[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict:
        return {"book": self.book, "dry_run": self.dry_run,
                "mapping": {str(k): v for k, v in sorted(self.mapping.items())},
                "moved": [list(m) for m in self.moved], "rewritten": self.rewritten,
                "rescore": self.rescore, "reread": self.reread,
                "seams": [list(x) for x in self.seams],
                "order_reports": self.order_reports,
                "said_once_inverted": self.said_once_inverted}


# ------------------------------------------------------------ the map


def chapter_numbers(book_root: Path) -> list[int]:
    out = []
    for path in iter_chapter_files(book_root / "chapters"):
        m = _CHAPTER_RE.match(path.name)
        if m:
            out.append(int(m.group(1)))
    return sorted(out)


def move_map(numbers: list[int], frm: int, to: int) -> dict[int, int]:
    """old -> new for moving chapter `frm` to position `to`, the chapters
    between shifting by one (`/autonovel:reorder --from A --to B`)."""
    if frm not in numbers or to not in numbers:
        raise RenumberError(f"chapters run {numbers[0]}-{numbers[-1]}; can't move {frm} to {to}")
    order = [n for n in numbers if n != frm]
    order.insert(numbers.index(to), frm)
    return {old: new for old, new in zip(order, numbers) if old != new}


def parse_map(spec: str, numbers: list[int]) -> dict[int, int]:
    """`10:11,11:10` -> {10: 11, 11: 10}; must permute the chapters."""
    mapping: dict[int, int] = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            a, b = (int(x) for x in part.split(":"))
        except ValueError as exc:
            raise RenumberError(f"bad map entry {part!r}; write old:new, e.g. 10:11") from exc
        mapping[a] = b
    full = {n: mapping.get(n, n) for n in numbers}
    if set(mapping) - set(numbers):
        raise RenumberError(f"no chapter {', '.join(map(str, sorted(set(mapping) - set(numbers))))}")
    if sorted(full.values()) != numbers:
        raise RenumberError("the map must give every chapter a different number from the "
                            f"same set ({numbers[0]}-{numbers[-1]}); merging, splitting and "
                            "removing chapters have their own commands")
    return {a: b for a, b in full.items() if a != b}


# ------------------------------------------------------------ references


def _expand(nums: list[int], seps: list[str]) -> set[int]:
    out: set[int] = set()
    i = 0
    while i < len(nums):
        if i < len(seps) and _RANGE_SEP_RE.match(seps[i]) and nums[i] < nums[i + 1]:
            out.update(range(nums[i], nums[i + 1] + 1))
            i += 2
        else:
            out.add(nums[i])
            i += 1
    return out


def _compress(nums: list[int], dash: str) -> str:
    runs: list[str] = []
    nums = sorted(nums)
    start = prev = nums[0]
    for n in nums[1:] + [None]:
        if n is not None and n == prev + 1:
            prev = n
            continue
        runs.append(str(start) if start == prev else f"{start}{dash}{prev}")
        if n is not None:
            start = prev = n
    return ", ".join(runs)


def rewrite_refs(text: str, mapping: dict[int, int]) -> str:
    """Every chapter reference in `text`, by the map. A list or range that
    names the same chapters after the move is left as written ("ch 9-12"
    under a swap of 10 and 11)."""
    if not mapping:
        return text

    def sub(m: re.Match) -> str:
        if m.group("file"):
            n = int(m.group("fnum"))
            if n not in mapping:
                return m.group(0)
            return m.group(0)[: m.start("fnum") - m.start()] + f"{mapping[n]:02d}"
        nums_text = m.group("nums")
        parts = re.split(f"({_SEP})", nums_text)
        nums = [int(p) for p in parts[0::2]]
        seps = parts[1::2]
        if not any(n in mapping for n in nums):
            return m.group(0)
        before = _expand(nums, seps)
        after = {mapping.get(n, n) for n in before}
        if after == before:
            return m.group(0)
        if any(_RANGE_SEP_RE.match(s) for s in seps):
            dash = next((s.strip() for s in seps if s.strip() and s.strip() in "-–—"), "–")
            return m.group("word") + _compress(sorted(after), dash)
        out = [str(mapping.get(n, n)) for n in nums]
        return m.group("word") + "".join(x for pair in zip(out, seps + [""]) for x in pair)

    text = _REF_RE.sub(sub, text)
    text = _SPINE_RE.sub(lambda m: f"{m.group(1)}{mapping.get(int(m.group(2)), int(m.group(2)))}"
                                   f"{m.group(3)}{mapping.get(int(m.group(4)), int(m.group(4)))}", text)
    return text


def _rewrite_yaml_chapters(text: str, mapping: dict[int, int]) -> str:
    return _YAML_CHAPTER_RE.sub(
        lambda m: f"{m.group(1)}{mapping.get(int(m.group(2)), int(m.group(2)))}{m.group(3)}", text)


def reorder_chapter_blocks(text: str) -> str:
    """Put `## Chapter N` blocks back in number order, each into the place
    a chapter block held, so act headings between them stay where they
    are (a chapter moved into another act lands under that act)."""
    heads = list(_HEADING_RE.finditer(text))
    if len(heads) < 2:
        return text
    level = min(len(h.group(1)) for h in heads)
    stop_re = re.compile(rf"^#{{1,{level}}} ", re.MULTILINE)
    blocks: list[tuple[int, int, int]] = []  # (start, end, number)
    for h in heads:
        if len(h.group(1)) != level:
            continue
        nxt = stop_re.search(text, h.end())
        end = nxt.start() if nxt else len(text)
        blocks.append((h.start(), end, int(h.group(2))))
    if [b[2] for b in blocks] == sorted(b[2] for b in blocks):
        return text
    bodies = {b[2]: text[b[0]:b[1]] for b in blocks}
    if len(bodies) != len(blocks):
        return text  # two blocks with one number: leave it for a person
    ordered = sorted(bodies)
    out, pos = [], 0
    for (start, end, _n), n in zip(blocks, ordered):
        out.append(text[pos:start])
        slot = text[start:end]
        trail = slot[len(slot.rstrip()):]
        out.append(bodies[n].rstrip() + trail)
        pos = end
    out.append(text[pos:])
    return "".join(out)


def _rewrite_json(obj, mapping: dict[int, int]):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key_is_chapter = ("chapter" in k.lower() and k != "chapter_count") or k in ("ch", "chapters")
            if key_is_chapter and isinstance(v, int) and not isinstance(v, bool):
                out[k] = mapping.get(v, v)
            elif key_is_chapter and isinstance(v, list) and all(
                    isinstance(x, int) and not isinstance(x, bool) for x in v):
                out[k] = [mapping.get(x, x) for x in v]
            else:
                out[k] = _rewrite_json(v, mapping)
        return out
    if isinstance(obj, list):
        return [_rewrite_json(v, mapping) for v in obj]
    if isinstance(obj, str):
        return rewrite_refs(obj, mapping)
    return obj


def _write_keeping_time(path: Path, text: str) -> None:
    """Rewrite a file without making it look newer: a renumber renews no
    report and no score, and file times decide which eval log is the
    latest and whether an unstamped report is older than its chapters."""
    import os
    st = path.stat()
    path.write_text(text, encoding="utf-8")
    os.utime(path, (st.st_atime, st.st_mtime))


def _ref_files(book_root: Path) -> list[Path]:
    seen: dict[Path, None] = {}
    for rel in _REF_FILES:
        p = book_root / rel
        if p.is_file():
            seen[p] = None
    for pat in _REF_GLOBS:
        for p in sorted(book_root.glob(pat)):
            if p.is_file() and not _DATED_RE.search(p.stem):
                seen[p] = None
    plates = book_root / "typeset" / "plates.yaml"
    if plates.is_file():
        seen[plates] = None
    return list(seen)


# ------------------------------------------------------------ order checks


def _order(numbers: list[int], mapping: dict[int, int]) -> list[int]:
    """Old chapter numbers in the new reading order."""
    inverse = {mapping.get(n, n): n for n in numbers}
    return [inverse[n] for n in numbers]


def _predecessor_changed(numbers: list[int], mapping: dict[int, int]) -> list[int]:
    order = _order(numbers, mapping)
    out = []
    for i, old in enumerate(order):
        before = numbers[numbers.index(old) - 1] if numbers.index(old) > 0 else None
        after = order[i - 1] if i > 0 else None
        if before != after:
            out.append(numbers[i])
    return out


def _earlier_set_changed(numbers: list[int], mapping: dict[int, int]) -> list[int]:
    order = _order(numbers, mapping)
    out = []
    for i, old in enumerate(order):
        before = set(numbers[: numbers.index(old)])
        after = set(order[:i])
        if before != after:
            out.append(numbers[i])
    return out


_DATE_RE = re.compile(r"\d{4}(?:-\d{2}(?:-\d{2})?)?")


def _story_span(path: Path) -> tuple[tuple[int, ...], tuple[int, ...]] | None:
    """(start, end) of a chapter's frontmatter `story_time`, as
    (year, month, day) tuples padded with 0 and 99, or None."""
    from ..mechanical.latex import frontmatter_value
    try:
        value = frontmatter_value(path.read_text(encoding="utf-8"), "story_time")
    except OSError:
        return None
    dates = _DATE_RE.findall(value or "")
    if not dates:
        return None

    def parse(d: str, pad: int) -> tuple[int, ...]:
        parts = [int(x) for x in d.split("-")]
        return tuple(parts + [pad] * (3 - len(parts)))
    return parse(dates[0], 0), parse(dates[-1], 99)


def seam_pairs(book_root: Path, numbers: list[int], mapping: dict[int, int]) -> list[tuple[int, int]]:
    """Every join a reader now meets differently, as (earlier, later) in
    the new numbering: each chapter whose previous chapter changed, read
    after that previous chapter; and each chapter that takes up a story
    where another left it (the next chapter told whose `story_time`
    starts after the other's ends) at a different distance than before,
    read across the gap. One reorder of two chapters moved a book's May
    story two chapters and two time jumps away from the chapter that
    resumes it; reading only the moved chapters' own seams missed it."""
    full = {n: mapping.get(n, n) for n in numbers}
    pairs: set[tuple[int, int]] = set()
    for n in _predecessor_changed(numbers, mapping):
        if n > numbers[0]:
            pairs.add((numbers[numbers.index(n) - 1], n))
    spans = {n: _story_span(book_root / "chapters" / f"ch_{n:02d}.md") for n in numbers}
    for x in numbers:
        if not spans.get(x):
            continue
        end = spans[x][1]
        later = [c for c in numbers if c != x and spans.get(c) and spans[c][0] >= end[:2] + (0,)
                 and full[c] > full[x]]
        if not later:
            continue
        c = min(later, key=lambda c: (spans[c][0], full[c]))
        if full[c] - full[x] != c - x:
            pairs.add((full[x], full[c]))
    return sorted(pairs, key=lambda p: (p[1], p[0]))


_POINT_RE = re.compile(r"^\s*(\d+)\.\s+\*\*(.+?)\*\*", re.MULTILINE)
_TOLD_RE = re.compile(r"\*\*Told:\*\*\s*ch\.?\s*(\d+)")
_MENTION_RE = re.compile(r"\bch\.?\s*(\d+)\s+L\d+")


def said_once_inversions(ledger: str, mapping: dict[int, int]) -> list[str]:
    """Points of the said-once ledger whose first telling, after the move,
    comes after a chapter the ledger counted as a later telling."""
    if not mapping:
        return []
    m = re.search(r"^## Points\s*$", ledger, re.MULTILINE)
    if not m:
        return []
    end = re.search(r"^## ", ledger[m.end():], re.MULTILINE)
    body = ledger[m.end(): m.end() + end.start()] if end else ledger[m.end():]
    points = list(_POINT_RE.finditer(body))
    out = []
    for i, p in enumerate(points):
        chunk = body[p.start(): points[i + 1].start() if i + 1 < len(points) else len(body)]
        told = _TOLD_RE.search(chunk)
        if not told:
            continue
        first = int(told.group(1))
        rest = chunk[told.end():]
        later = {int(x) for x in _MENTION_RE.findall(rest)} - {first}
        new_first = mapping.get(first, first)
        if any(mapping.get(c, c) < new_first for c in later if c > first):
            out.append(f"{p.group(1)}. {p.group(2)}")
    return out


# ------------------------------------------------------------ apply


def _planned_moves(book_root: Path, mapping: dict[int, int]) -> list[tuple[Path, Path]]:
    moves: list[tuple[Path, Path]] = []
    for folder, pat, recurse in _FILE_PATTERNS:
        base = book_root / folder
        if not base.is_dir():
            continue
        paths = base.rglob("*") if recurse else base.iterdir()
        for p in sorted(paths):
            if not p.is_file():
                continue
            m = pat.match(p.name)
            if not m:
                continue
            n = int(m.group(2))
            if n not in mapping:
                continue
            width = len(m.group(2))
            target = p.with_name(f"{m.group(1)}{mapping[n]:0{width}d}{m.group(3)}")
            if (p, target) not in moves:
                moves.append((p, target))
    return moves


def renumber(book_root: Path, mapping: dict[int, int], *, dry_run: bool = False) -> RenumberReport:
    numbers = chapter_numbers(book_root)
    if not numbers:
        raise RenumberError(f"no chapters under {book_root / 'chapters'}")
    full = {n: mapping.get(n, n) for n in numbers}
    if sorted(full.values()) != numbers:
        raise RenumberError("the map must permute the existing chapter numbers")
    mapping = {a: b for a, b in full.items() if a != b}
    rep = RenumberReport(book=book_root.name, mapping=mapping, dry_run=dry_run)
    if not mapping:
        return rep

    rep.rescore = _predecessor_changed(numbers, mapping)
    rep.reread = _earlier_set_changed(numbers, mapping)
    rep.seams = seam_pairs(book_root, numbers, mapping)
    ledger = book_root / "edit_logs" / "said_once_ledger.md"
    if ledger.is_file():
        rep.said_once_inverted = said_once_inversions(ledger.read_text(encoding="utf-8"), mapping)
    stamps = release_gate.load_stamps(book_root)
    rep.order_reports = [k for k in ORDER_JUDGED if isinstance(stamps.get(k), dict)]
    if rep.said_once_inverted and isinstance(stamps.get("said_once"), dict):
        rep.order_reports.append("said_once")

    moves = _planned_moves(book_root, mapping)
    rep.moved = [(str(a.relative_to(book_root)), str(b.relative_to(book_root))) for a, b in moves]
    ref_files = _ref_files(book_root)
    if dry_run:
        rep.rewritten = [str(p.relative_to(book_root)) for p in ref_files]
        return rep

    # 1. Move every file named for a chapter, through temporary names.
    tmp = []
    for i, (src, dst) in enumerate(moves):
        t = src.with_name(f".renumber-{i}-{src.name}")
        src.rename(t)
        tmp.append((t, dst))
    for t, dst in tmp:
        dst.parent.mkdir(parents=True, exist_ok=True)
        t.rename(dst)

    # 2. The chapter's own frontmatter and its brief's.
    for n in numbers:
        new = full[n]
        if new == n:
            continue
        for path in (book_root / "chapters" / f"ch_{new:02d}.md", book_root / "briefs" / f"ch{new:02d}.md"):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                fixed = re.sub(r"^(chapter:\s*)\d+\s*$", rf"\g<1>{new}", text, count=1, flags=re.MULTILINE)
                if fixed != text:
                    _write_keeping_time(path, fixed)

    # 3. References that follow the text.
    ref_files = _ref_files(book_root)
    for path in ref_files:
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            try:
                data = json.loads(text)
            except ValueError:
                new_text = rewrite_refs(text, mapping)
            else:
                new_data = _rewrite_json(data, mapping)
                if isinstance(new_data, dict) and path.parent.name == "eval_logs" and \
                        isinstance(new_data.get("chapter"), int) and \
                        re.match(r"^(?:\d{8}_\d{6}_)?ch\d+", path.name):
                    new_data["chapter"] = int(re.search(r"ch(\d+)", path.name).group(1))
                new_text = (json.dumps(new_data, indent=2, ensure_ascii=False) + "\n"
                            if new_data != data else text)
        elif path.name == "plates.yaml":
            new_text = _rewrite_yaml_chapters(text, mapping)
        else:
            new_text = rewrite_refs(text, mapping)
            if path.name in ("outline.md", "said_once_ledger.md"):
                new_text = reorder_chapter_blocks(new_text)
        if new_text != text:
            _write_keeping_time(path, new_text)
            rep.rewritten.append(str(path.relative_to(book_root)))

    # 4. The stamps follow the text; what the order changed goes back.
    when = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for key, entry in list(stamps.items()):
        if key == release_gate.FIRST_READ_KEY and isinstance(entry, dict):
            moved = {}
            for n, e in entry.items():
                new = full.get(int(n), int(n)) if str(n).isdigit() else n
                if isinstance(e, dict) and isinstance(e.get("text"), str):
                    e["text"] = re.sub(r"ch\d+\.md$", f"ch{int(new):02d}.md", e["text"])
                moved[str(new)] = e
            for n in rep.reread:
                if isinstance(moved.get(str(n)), dict):
                    moved[str(n)]["order_changed"] = when
            stamps[key] = moved
        elif key in release_gate.REPORTS and isinstance(entry, dict):
            for part in ("chapters", "paragraphs"):
                if isinstance(entry.get(part), dict):
                    entry[part] = {str(full.get(int(n), int(n))): v for n, v in entry[part].items()}
            if key in rep.order_reports:
                mark = entry.get("reordered") if isinstance(entry.get("reordered"), dict) else {}
                moved = {int(n) for n in mark.get("chapters", [])} | set(mapping)
                entry["reordered"] = {"when": when, "chapters": sorted(moved)}
    events = stamps.get("renumbered") if isinstance(stamps.get("renumbered"), list) else []
    events.append({"when": when, "map": {str(k): v for k, v in sorted(mapping.items())},
                   "order_reports": rep.order_reports,
                   "said_once_inverted": rep.said_once_inverted})
    stamps["renumbered"] = events
    path = book_root / "edit_logs" / release_gate.STAMPS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stamps, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # A score judged continuity against the chapter before it; where that
    # is now another chapter, the score no longer describes this chapter
    # in this place.
    from ..mechanical.chapter_summary import latest_chapter_eval_path
    from ..summaries import EVAL_KEY
    for n in rep.rescore:
        log = latest_chapter_eval_path(book_root / "eval_logs", n)
        if log is None:
            continue
        data = json.loads(log.read_text(encoding="utf-8"))
        if data.get(EVAL_KEY):
            data[f"{EVAL_KEY}_before_reorder"] = data.pop(EVAL_KEY)
            data["reordered"] = (f"{when}: the chapter before this one changed when chapters "
                                 f"were renumbered; score it again in its new place")
            _write_keeping_time(log, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return rep


def render_text(rep: RenumberReport) -> str:
    if not rep.mapping:
        return "nothing to do: every chapter keeps its number"
    lines = [("would renumber" if rep.dry_run else "renumbered") + ": "
             + ", ".join(f"ch {a} -> {b}" for a, b in sorted(rep.mapping.items()))]
    lines.append(f"files {'to move' if rep.dry_run else 'moved'}: {len(rep.moved)}")
    for a, b in rep.moved:
        lines.append(f"  {a} -> {b}")
    shown = rep.rewritten if len(rep.rewritten) <= 12 else rep.rewritten[:12] + [
        f"and {len(rep.rewritten) - 12} more (--format json lists them)"]
    lines.append(f"references {'to check' if rep.dry_run else 'rewritten'} in "
                 f"{len(rep.rewritten)} files: " + (", ".join(shown) if shown else "none"))
    if rep.rescore:
        lines.append(f"score again (the chapter before each is now another): ch "
                     f"{', '.join(map(str, rep.rescore))}")
    if rep.reread:
        lines.append(f"read cold again (the chapters before each are now others): ch "
                     f"{', '.join(map(str, rep.reread))}")
    if rep.seams:
        lines.append("read these seams, the later chapter's opening after the earlier one's "
                     "ending: " + ", ".join(f"{a}→{b}" if b == a + 1 else f"{a}…{b} (across "
                                            f"{b - a - 1} chapter{'s' if b - a > 2 else ''})"
                                            for a, b in rep.seams))
    if rep.order_reports:
        lines.append("read the book again (they judge the order): " + ", ".join(rep.order_reports))
    if rep.said_once_inverted:
        lines.append("said-once points whose first telling now comes later: "
                     + "; ".join(rep.said_once_inverted))
    return "\n".join(lines)
