"""Fountain screenplays: parse, check, measure in eighths, export.

`autonovel mechanical fountain-check <file>` is the mechanical half of
`/autonovel:screenplay` (film pipeline stage F1, `docs/film-pipeline-plan.md`).
It reads a Fountain file (https://fountain.io/syntax/) and reports:

  - every scene heading without `INT.`/`EXT.`, a place or a time of day;
  - every speaking character who is neither in the book's cast
    (`books/<book>/cast.md`, `shared/characters.md`) nor listed under the
    title page's `Roles:` key, and one person under two cues;
  - the autonovel scene line under each heading,
    `= <ID> | <source> | <turn>` (SCREEN.md §1.8): IDs missing or
    repeated, sources it can't read;
  - each scene's length in eighths of a page, laid out on the standard
    US-letter page (55 lines; 61 characters to an action line, 36 to
    dialogue, 26 to a parenthetical, the afterwriting print profile);
  - advisories: action blocks over four lines, long speeches, camera
    directions, voice-over density.

With the optional `screenplain` package (MIT; `pip install
'autonovel[export]'`) it also writes the PDF and the Final Draft `.fdx`.
Without it the check still runs and the report says how to get the
exports. Nothing here calls a model; the parser is written for the checks
and follows the same rules screenplain uses to render, so a heading the
check accepts is a heading the PDF prints.
"""

from __future__ import annotations

import json
import re
import textwrap
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

LINES_PER_PAGE = 55
WIDTHS = {
    "heading": 61,
    "action": 61,
    "transition": 61,
    "centered": 58,
    "cue": 33,
    "paren": 26,
    "dialogue": 36,
    "lyric": 61,
}
ACTION_BLOCK_MAX_LINES = 4      # NFI: break action blocks over 3-4 lines
SPEECH_MAX_LINES = 4            # SCREEN.md §4.2
VO_LINES_PER_PAGE = 0.5         # SCREEN.md §4.7 [pipeline heuristic]

EXPORT_HINT = ("pip install 'autonovel[export]' (or: pip install screenplain) "
               "for the PDF and FDX")

_PREFIX_RE = re.compile(r"^(INT\.?/EXT|INT/EXT|I/E|INT|EXT|EST)(?=[ .])\.?\s*", re.I)
_SCENE_NUMBER_RE = re.compile(r"^(.*?)\s*#([\w\-.]+)#\s*$")
_SEP_RE = re.compile(r"\s+[-\u2013\u2014]\s+")
_TITLE_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z ]*?):\s*(.*)$")
_TITLE_CONT_RE = re.compile(r"^(?: {3,}|\t)(\S.*)$")
_NOTE_RE = re.compile(r"\[\[.*?\]\]", re.S)
_BONEYARD_RE = re.compile(r"/\*.*?\*/", re.S)
_CENTERED_RE = re.compile(r"^\s*>\s*(.*?)\s*<\s*$")
_PAGE_BREAK_RE = re.compile(r"^={3,}\s*$")
_SECTION_RE = re.compile(r"^#{1,6}\s*[^#]")
_EMPHASIS_RE = re.compile(r"\\([*_])|\*{1,3}|_")
_SYNOPSIS_LINE_RE = re.compile(r"^\s*(S\d{4,})\s*(?:\|\s*(.*?)\s*)?(?:\|\s*(.*?)\s*)?$")
_SOURCE_REF_RE = re.compile(r"^ch_?(\d+)(?::(\d+)(?:\s*-\s*(\d+))?)?$", re.I)
_SEQ_FROM_FILE_RE = re.compile(r"seq_?(\d+)", re.I)
_CAMERA_RE = re.compile(
    r"\b(ANGLE ON|CLOSE ON|CLOSE-UP|CLOSEUP|CAMERA|PAN(?:S|NING)? TO|DOLLY|ZOOM|"
    r"TRACKING SHOT|CRANE SHOT)\b")

TIMES_OF_DAY = {
    "DAY", "NIGHT", "DAWN", "DUSK", "MORNING", "AFTERNOON", "EVENING",
    "NOON", "MIDNIGHT", "SUNRISE", "SUNSET", "LATER", "CONTINUOUS",
    "MOMENTS LATER", "SAME", "SAME TIME", "PRE-DAWN", "FIRST LIGHT",
    "LATE NIGHT", "EARLY MORNING", "LATE AFTERNOON", "MIDDAY",
}

_STOPWORDS = {
    "the", "a", "an", "of", "and", "de", "von", "van", "der", "dei", "di",
    "da", "le", "la", "in", "at", "on", "his", "her", "their", "to", "for",
    "with", "by", "s",
}


# --------------------------------------------------------------- the model

@dataclass
class Element:
    kind: str          # heading action cue paren dialogue transition centered
                       # synopsis section page_break lyric
    text: str
    line: int          # 1-based line in the source file
    forced: bool = False
    dual: bool = False


@dataclass
class Speech:
    cue: str           # normalised name, e.g. "VIANELLO"
    raw_cue: str       # as written, e.g. "VIANELLO (V.O.)"
    line: int
    extensions: list[str]
    lines: int         # wrapped dialogue + parenthetical lines


@dataclass
class Scene:
    index: int
    heading: str
    line: int
    int_ext: str = ""
    location: str = ""
    time: str = ""
    id: str = ""
    source: list[dict] = field(default_factory=list)
    source_text: str = ""
    turn: str = ""
    page_lines: int = 0
    eighths: int = 0
    speaking: list[str] = field(default_factory=list)
    characters: list[str] = field(default_factory=list)
    voice_over: int = 0


@dataclass
class CastEntry:
    name: str
    where: str
    tokens: frozenset


@dataclass
class Report:
    path: str
    title_page: dict = field(default_factory=dict)
    scenes: list[Scene] = field(default_factory=list)
    speakers: dict = field(default_factory=dict)
    roles: list[str] = field(default_factory=list)
    cast_files: list[str] = field(default_factory=list)
    page_lines: int = 0
    eighths: int = 0
    voice_over_lines: int = 0
    first_minute: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    advisories: list[str] = field(default_factory=list)
    exports: dict = field(default_factory=dict)
    scenes_json: str = ""

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def pages(self) -> float:
        return round(self.page_lines / LINES_PER_PAGE, 2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ok"] = self.ok
        d["pages"] = self.pages
        d["length"] = eighths_label(self.eighths)
        d["minutes_estimate"] = round(self.eighths / 8, 1)
        for s in d["scenes"]:
            s["length"] = eighths_label(s["eighths"])
        return d


def eighths_label(eighths: int) -> str:
    """Production style: 11 eighths is '1 3/8', 4 eighths is '4/8' (never
    reduced to 1/2), 16 is '2'."""
    whole, rest = divmod(int(eighths), 8)
    if whole and rest:
        return f"{whole} {rest}/8"
    if whole:
        return str(whole)
    return f"{rest}/8"


# --------------------------------------------------------------- parsing

def _blank_out(match: re.Match) -> str:
    """Replace a note or boneyard with the same number of newlines, so the
    line numbers of everything after it stay true."""
    return "\n" * match.group(0).count("\n")


def parse_title_page(lines: list[str]) -> tuple[dict, int]:
    """The title page is the file's opening block of `key: value` lines,
    ended by the first blank line. Returns ({Key: [values]}, lines used).
    The rules are screenplain's, so what this reads is what the PDF prints:
    a key with its value on the same line takes no more lines; a key with
    nothing after the colon takes the indented lines below it."""
    if not lines or not _TITLE_KEY_RE.match(lines[0]):
        return {}, 0
    out: dict[str, list[str]] = {}
    key = None
    open_key = False
    used = 0
    for ln in lines:
        if ln == "":
            break
        used += 1
        cont = _TITLE_CONT_RE.match(ln)
        if open_key and cont:
            out[key].append(cont.group(1).strip())
            continue
        m = _TITLE_KEY_RE.match(ln)
        if not m:
            return {}, 0   # not a title page after all
        key = m.group(1).strip().capitalize()
        out.setdefault(key, [])
        value = m.group(2).strip()
        open_key = not value
        if value:
            out[key].append(value)
    return out, used


def _is_blank(line: str) -> bool:
    # A line of exactly two spaces is a deliberate empty line inside
    # dialogue (Fountain); anything else that is whitespace is blank.
    return not line.strip() and line != "  "


def _is_cue(first: str) -> bool:
    if first.endswith("  "):
        return False
    if first.startswith("@") and len(first) > 1:
        return True
    before = first.split("(", 1)[0].rstrip("^ ").strip()
    return bool(before) and before.isupper() and any(c.isalpha() for c in before)


def parse(text: str) -> tuple[dict, list[Element], list[str]]:
    """Fountain text -> (title page, elements, problems found while parsing)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").expandtabs(4)
    text = _BONEYARD_RE.sub(_blank_out, text)
    text = _NOTE_RE.sub(_blank_out, text)
    lines = text.split("\n")
    title, used = parse_title_page(lines)
    problems: list[str] = []
    if not title and lines and _TITLE_KEY_RE.match(lines[0]):
        problems.append(
            "line 1: the title page was not read and will print as action: a key with its value on "
            "the same line takes no more lines; put a list (Roles:) on indented lines under an "
            "empty key")
    elements: list[Element] = []

    # Group the body into blocks of consecutive non-blank lines.
    blocks: list[tuple[int, list[str]]] = []
    cur: list[str] = []
    start = 0
    for i in range(used, len(lines)):
        ln = lines[i]
        if _is_blank(ln):
            if cur:
                blocks.append((start, cur))
                cur = []
            continue
        if not cur:
            start = i + 1
        cur.append(ln.rstrip("\n"))
    if cur:
        blocks.append((start, cur))

    for lineno, block in blocks:
        first = block[0]
        stripped = first.strip()
        if first.startswith("!"):
            elements.append(Element("action", "\n".join([first[1:]] + block[1:]), lineno, forced=True))
            continue
        if len(block) == 1 and _PAGE_BREAK_RE.match(stripped):
            elements.append(Element("page_break", "", lineno))
            continue
        if all(ln.strip().startswith("=") and not _PAGE_BREAK_RE.match(ln.strip()) or _SECTION_RE.match(ln.strip())
               for ln in block):
            for k, ln in enumerate(block):
                s = ln.strip()
                kind = "section" if _SECTION_RE.match(s) else "synopsis"
                elements.append(Element(kind, s.lstrip("#=").strip(), lineno + k))
            continue
        heading = _heading_text(first)
        if heading is not None:
            if len(block) == 1:
                elements.append(Element("heading", heading, lineno, forced=stripped.startswith(".")))
                continue
            problems.append(
                f"line {lineno}: scene heading {stripped!r} has no blank line after it; "
                "Fountain needs one, and as written it prints as dialogue")
        if all(_CENTERED_RE.match(ln) for ln in block):
            elements.append(Element("centered", "\n".join(_CENTERED_RE.match(ln).group(1) for ln in block), lineno))
            continue
        if len(block) >= 2 and _is_cue(stripped):
            dual = stripped.endswith("^")
            cue_text = stripped[1:] if stripped.startswith("@") else stripped
            elements.append(Element("cue", cue_text.rstrip("^ ").strip(), lineno, dual=dual))
            for k, ln in enumerate(block[1:], 1):
                s = ln.strip()
                if s.startswith("(") and s.endswith(")"):
                    elements.append(Element("paren", s, lineno + k))
                else:
                    elements.append(Element("dialogue", s if ln != "  " else "", lineno + k))
            continue
        if len(block) == 1 and (stripped.startswith(">") or (stripped.isupper() and stripped.endswith("TO:"))):
            elements.append(Element("transition", stripped.lstrip(">").strip(), lineno))
            continue
        if all(ln.strip().startswith("~") for ln in block):
            elements.append(Element("lyric", "\n".join(ln.strip()[1:] for ln in block), lineno))
            continue
        elements.append(Element("action", "\n".join(block), lineno))
    return title, elements, problems


def _heading_text(line: str) -> str | None:
    s = line.strip()
    if s.startswith(".") and len(s) > 1 and s[1] != ".":
        return s[1:].strip()
    if s.startswith("!"):
        return None
    if _PREFIX_RE.match(s):
        return s
    return None


def split_heading(text: str) -> tuple[str, str, str, str]:
    """Heading text -> (INT/EXT prefix, location, time of day, scene number)."""
    number = ""
    m = _SCENE_NUMBER_RE.match(text)
    if m:
        text, number = m.group(1), m.group(2)
    text = text.strip()
    prefix = ""
    pm = _PREFIX_RE.match(text)
    if pm:
        raw = pm.group(1).upper()
        prefix = {"INT/EXT": "INT./EXT.", "INT./EXT": "INT./EXT.", "I/E": "INT./EXT."}.get(raw, raw + ".")
        text = text[pm.end():].strip()
    parts = _SEP_RE.split(text)
    if len(parts) >= 2:
        return prefix, " - ".join(p.strip() for p in parts[:-1]), parts[-1].strip().upper(), number
    return prefix, text, "", number


# --------------------------------------------------------------- measuring

def plain(text: str) -> str:
    """Strip Fountain emphasis markers (keeping escaped * and _)."""
    return _EMPHASIS_RE.sub(lambda m: m.group(1) or "", text)


def wrapped_lines(text: str, width: int) -> int:
    n = 0
    for ln in text.split("\n"):
        ln = plain(ln).strip()
        n += max(1, len(textwrap.wrap(ln, width, break_long_words=True, break_on_hyphens=False)) if ln else 1)
    return n


def element_lines(el: Element, prev: Element | None) -> int:
    """Printed lines an element takes, with the blank line before it."""
    if el.kind in ("synopsis", "section"):
        return 0
    if el.kind in ("paren", "dialogue"):
        return wrapped_lines(el.text, WIDTHS["paren" if el.kind == "paren" else "dialogue"])
    if el.kind == "cue":
        return 1 + wrapped_lines(el.text, WIDTHS["cue"])
    width = WIDTHS.get(el.kind, 61)
    return 1 + wrapped_lines(el.text, width)


def cue_name(raw: str) -> tuple[str, list[str]]:
    """'VIANELLO (V.O.)' -> ('VIANELLO', ['V.O.'])."""
    exts = [e.strip() for e in re.findall(r"\(([^)]*)\)", raw)]
    name = re.sub(r"\([^)]*\)", " ", raw)
    name = re.sub(r"\s+", " ", name).strip().upper()
    return name, exts


# --------------------------------------------------------------- the cast

def tokens(text: str) -> frozenset:
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c)).casefold()
    t = re.sub(r"['\u2019]s\b", "", t)
    return frozenset(w for w in re.split(r"[^a-z0-9]+", t) if w and w not in _STOPWORDS)


def _name_part(text: str) -> str:
    text = re.sub(r"[`*_]", "", text).strip()
    text = re.split(r"\s+[\u2014\u2013-]\s+|\s*:\s+", text, maxsplit=1)[0]
    text = re.sub(r"\s*\((?:real|invented|inference)[^)]*\)\s*$", "", text, flags=re.I)
    return text.strip()


def load_cast(paths: list[Path]) -> list[CastEntry]:
    """Every name a cast file gives: `##`-`####` headings, a bold name that
    opens a line or bullet, and the first cell of a table row (cast.md's
    "called by a role" table). The name is the text before a dash."""
    out: list[CastEntry] = []
    head_re = re.compile(r"^#{2,4}\s+(.+?)\s*$")
    bold_re = re.compile(r"^\s*(?:[-*+]\s+)?\*\*(.+?)\*\*")
    row_re = re.compile(r"^\|\s*([^|]+?)\s*\|")
    for p in paths:
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for i, ln in enumerate(lines, 1):
            for rx in (head_re, bold_re, row_re):
                m = rx.match(ln)
                if not m:
                    continue
                cell = m.group(1)
                if rx is row_re and (set(cell) <= set("-: ") or cell.lower() in ("in the record", "name")):
                    continue
                name = _name_part(cell)
                toks = tokens(name)
                if toks:
                    out.append(CastEntry(name=name, where=f"{p.name}:{i}", tokens=toks))
                break
    return out


def match_cast(cue: str, cast: list[CastEntry]) -> CastEntry | None:
    want = tokens(cue)
    if not want:
        return None
    best = None
    for e in cast:
        if want <= e.tokens:
            if best is None or len(e.tokens) < len(best.tokens):
                best = e
    return best


def role_names(title: dict) -> list[str]:
    out = []
    for v in title.get("Roles", []):
        for part in v.split(","):
            name = _name_part(part)
            if name:
                out.append(re.sub(r"\s+", " ", name).upper())
    return out


# --------------------------------------------------------------- checking

def find_book_root(path: Path) -> Path | None:
    """Walk up from a script to the book folder (the one holding
    `chapters/` or `cast.md`)."""
    for d in [path.parent, *path.parents]:
        if (d / "cast.md").is_file() or (d / "chapters").is_dir():
            return d
    return None


def default_cast_paths(book_root: Path | None) -> list[Path]:
    if book_root is None:
        return []
    out = [book_root / "cast.md"]
    series = book_root.parent.parent if book_root.parent.name == "books" else None
    if series is not None:
        out.append(series / "shared" / "characters.md")
    return [p for p in out if p.is_file()]


def parse_source(text: str) -> tuple[list[dict], str | None]:
    """'ch_02:141-147, ch_02:160' or 'invented (...)' -> refs, problem."""
    refs: list[dict] = []
    text = (text or "").strip()
    if not text:
        return refs, "no source"
    for part in [p.strip() for p in text.split(",") if p.strip()]:
        if part.lower().startswith("invented"):
            refs.append({"invented": True, "note": part[len("invented"):].strip(" ()") or ""})
            continue
        m = _SOURCE_REF_RE.match(part.replace(" ", ""))
        if not m:
            return refs, f"source {part!r} not understood (want ch_NN:first-last or 'invented')"
        ref = {"chapter": int(m.group(1))}
        if m.group(2):
            ref["from"] = int(m.group(2))
            ref["to"] = int(m.group(3) or m.group(2))
        refs.append(ref)
    return refs, None


def check(path: Path, *, cast_paths: list[Path] | None = None,
          book_root: Path | None = None) -> Report:
    rep = Report(path=str(path))
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        rep.errors.append(f"cannot read {path}: {e}")
        return rep
    title, elements, problems = parse(text)
    rep.title_page = title
    rep.errors.extend(problems)
    rep.roles = role_names(title)

    if book_root is None:
        book_root = find_book_root(path)
    if cast_paths is None:
        cast_paths = default_cast_paths(book_root)
    cast = load_cast(cast_paths)
    rep.cast_files = [str(p) for p in cast_paths]
    if not cast_paths:
        rep.warnings.append("no cast.md found: speaking characters were not checked against a cast "
                            "(pass --cast or --book-root)")

    # Walk the elements into scenes, measuring as we go.
    scenes: list[Scene] = []
    speeches: list[tuple[Scene | None, Speech]] = []
    pre_lines = 0
    prev: Element | None = None
    cur: Scene | None = None
    cur_speech: Speech | None = None
    awaiting_synopsis = False
    action_text: dict[int, list[str]] = {}
    for el in elements:
        n = element_lines(el, prev)
        if el.kind == "page_break":
            total = pre_lines + sum(s.page_lines for s in scenes)
            n = (-total) % LINES_PER_PAGE
        if el.kind == "heading":
            cur = Scene(index=len(scenes) + 1, heading=el.text, line=el.line)
            cur.int_ext, cur.location, cur.time, _ = split_heading(el.text)
            scenes.append(cur)
            awaiting_synopsis = True
            _check_heading(cur, el, rep)
        elif el.kind == "synopsis" and cur is not None and awaiting_synopsis:
            awaiting_synopsis = False
            _read_scene_line(cur, el, rep)
        elif el.kind not in ("synopsis", "section"):
            awaiting_synopsis = False
        if el.kind == "cue":
            name, exts = cue_name(el.text)
            cur_speech = Speech(cue=name, raw_cue=el.text, line=el.line, extensions=exts, lines=0)
            speeches.append((cur, cur_speech))
            if any(e.upper().replace(" ", "") in ("V.O.", "VO") for e in exts):
                rep.voice_over_lines += 1
                if cur is not None:
                    cur.voice_over += 1
        elif el.kind in ("paren", "dialogue") and cur_speech is not None:
            cur_speech.lines += element_lines(el, prev)
        elif el.kind not in ("synopsis", "section"):
            cur_speech = None
        if el.kind == "action":
            wl = wrapped_lines(el.text, WIDTHS["action"])
            if wl > ACTION_BLOCK_MAX_LINES:
                rep.advisories.append(
                    f"line {el.line}: action block of {wl} lines; break it into shots of four or fewer "
                    "(SCREEN.md §1.3)")
            cam = _CAMERA_RE.search(el.text)
            if cam:
                rep.advisories.append(
                    f"line {el.line}: camera direction {cam.group(1)!r} in a spec page; keep only if the "
                    "story depends on it (SCREEN.md §1.6)")
            if cur is not None:
                action_text.setdefault(cur.index, []).append(el.text)
        if cur is None:
            pre_lines += n
        else:
            cur.page_lines += n
        prev = el

    rep.scenes = scenes
    if not scenes:
        rep.errors.append("no scene headings: a screenplay needs at least one INT./EXT. heading")

    # Speakers: cast, role or unknown.
    by_entry: dict[str, set[str]] = {}
    for scene, sp in speeches:
        info = rep.speakers.setdefault(sp.cue, {"status": "", "match": "", "speeches": 0, "first_line": sp.line})
        info["speeches"] += 1
        if scene is not None and sp.cue not in scene.speaking:
            scene.speaking.append(sp.cue)
        if sp.lines > SPEECH_MAX_LINES:
            rep.advisories.append(
                f"line {sp.line}: {sp.cue} speaks {sp.lines} lines at once; over four, break it with "
                "action or cut (SCREEN.md §4.2)")
    for name, info in rep.speakers.items():
        entry = match_cast(name, cast) if cast else None
        if entry is not None:
            info["status"], info["match"] = "cast", f"{entry.name} ({entry.where})"
            by_entry.setdefault(entry.name, set()).add(name)
        elif name in rep.roles:
            info["status"] = "role"
        elif not cast_paths:
            info["status"] = "unchecked"
        else:
            info["status"] = "unknown"
            rep.errors.append(
                f"line {info['first_line']}: {name} speaks but is neither in the cast nor listed under "
                "the title page's Roles: (SCREEN.md §5.4: no new named people)")
    for entry_name, cues in by_entry.items():
        if len(cues) > 1:
            rep.warnings.append(
                f"one person, two cues: {', '.join(sorted(cues))} (cast: {entry_name}); "
                "use one cue every time (SCREEN.md §1.4)")
    for role in rep.roles:
        if role not in rep.speakers:
            rep.warnings.append(f"Roles: lists {role}, who never speaks")

    # Who is in each scene: its speakers, plus any speaker named in its action.
    names = sorted(rep.speakers, key=len, reverse=True)
    for sc in scenes:
        chars = list(sc.speaking)
        body = " ".join(action_text.get(sc.index, []))
        for nm in names:
            if nm not in chars and re.search(rf"(?<![\w']){re.escape(nm)}(?![\w'])", body, re.I):
                chars.append(nm)
        sc.characters = chars

    # Scene IDs.
    with_id = [s for s in scenes if s.id]
    if scenes and not with_id:
        rep.warnings.append("no scene lines (`= S0101 | ch_NN:a-b | before -> after`) under the headings; "
                            "scenes.json will number scenes by position")
    elif with_id and len(with_id) < len(scenes):
        for s in scenes:
            if not s.id:
                rep.errors.append(f"line {s.line}: scene {s.heading!r} has no scene line "
                                  "(`= <ID> | <source> | <turn>`) though others do")
    seen: dict[str, int] = {}
    for s in with_id:
        if s.id in seen:
            rep.errors.append(f"line {s.line}: scene ID {s.id} repeats the one at line {seen[s.id]}")
        seen.setdefault(s.id, s.line)

    # Length.
    for s in scenes:
        s.eighths = max(1, round(s.page_lines * 8 / LINES_PER_PAGE))
    rep.page_lines = pre_lines + sum(s.page_lines for s in scenes)
    rep.eighths = sum(s.eighths for s in scenes)
    pages = rep.page_lines / LINES_PER_PAGE
    if rep.voice_over_lines and rep.voice_over_lines > max(1.0, pages * VO_LINES_PER_PAGE):
        rep.advisories.append(
            f"{rep.voice_over_lines} voice-over speeches in {pages:.1f} pages; SCREEN.md §4.7 asks for at "
            "most one per two pages")

    # The best first minute to render, when the title page names one.
    fm = " ".join(title.get("First minute", []))
    if fm:
        m = re.match(r"\s*(S\d{4,})\s*(?:[\u2014\u2013:|-]+\s*(.*))?$", fm)
        if not m:
            rep.errors.append(f"title page First minute: {fm!r} should start with a scene ID")
        else:
            rep.first_minute = {"scene": m.group(1), "why": (m.group(2) or "").strip()}
            if m.group(1) not in seen:
                rep.errors.append(f"title page First minute: names {m.group(1)}, which is not a scene ID here")
    return rep


def _check_heading(sc: Scene, el: Element, rep: Report) -> None:
    where = f"line {el.line}: heading {el.text!r}"
    if not sc.int_ext:
        rep.warnings.append(f"{where} has no INT./EXT.; it prints as a heading but breaks down as no place "
                            "(SCREEN.md §1.2)")
        return
    if not sc.location:
        rep.errors.append(f"{where} names no place")
    if not sc.time:
        rep.errors.append(f"{where} has no time of day after ' - ' (DAY, NIGHT, DAWN, ...)")
    elif sc.time not in TIMES_OF_DAY:
        rep.warnings.append(f"{where}: time of day {sc.time!r} is not a standard one "
                            f"({', '.join(sorted(TIMES_OF_DAY)[:8])}, ...)")


def _read_scene_line(sc: Scene, el: Element, rep: Report) -> None:
    m = _SYNOPSIS_LINE_RE.match(el.text)
    if not m:
        return
    sc.id = m.group(1)
    sc.source_text = (m.group(2) or "").strip()
    sc.turn = (m.group(3) or "").strip()
    refs, problem = parse_source(sc.source_text)
    sc.source = refs
    if problem:
        rep.errors.append(f"line {el.line}: {sc.id}: {problem}")
    if not sc.turn:
        rep.warnings.append(f"line {el.line}: {sc.id} names no turn (`before -> after`, SCREEN.md §2.1)")
    elif "->" not in sc.turn and "\u2192" not in sc.turn:
        rep.warnings.append(f"line {el.line}: {sc.id}'s turn {sc.turn!r} doesn't name a before and an after "
                            "(`before -> after`)")


# --------------------------------------------------------------- exporting

def export(path: Path, out_dir: Path, formats: tuple[str, ...] = ("pdf", "fdx"),
           stem: str | None = None) -> dict:
    """Write `<stem>.pdf` and `<stem>.fdx` with screenplain. Returns
    {format: path} plus `pdf_pages`, or {"skipped": reason} when the
    optional dependency is missing."""
    try:
        from screenplain.parsers import fountain as sp_fountain  # type: ignore
    except ImportError:
        return {"skipped": f"screenplain is not installed; {EXPORT_HINT}"}
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = stem or path.stem
    with path.open(encoding="utf-8-sig") as fh:
        screenplay = sp_fountain.parse(fh)
    out: dict = {}
    if "fdx" in formats:
        from screenplain.export.fdx import to_fdx  # type: ignore
        fdx = out_dir / f"{stem}.fdx"
        with fdx.open("w", encoding="utf-8") as fh:
            to_fdx(screenplay, fh)
        out["fdx"] = str(fdx)
        out["fdx_check"] = check_fdx(fdx)
    if "pdf" in formats:
        try:
            from screenplain.export import pdf as sp_pdf  # type: ignore
        except ImportError as e:   # reportlab missing
            out["pdf_skipped"] = f"PDF needs reportlab ({e}); {EXPORT_HINT}"
        else:
            pdf = out_dir / f"{stem}.pdf"
            with pdf.open("wb") as fh:
                sp_pdf.to_pdf(screenplay, fh)
            out["pdf"] = str(pdf)
            out["pdf_pages"] = pdf_page_count(pdf)
    return out


def pdf_page_count(pdf: Path) -> int:
    data = pdf.read_bytes()
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", data))


def check_fdx(fdx: Path) -> dict:
    """The FDX parses as XML, is a Final Draft document, and holds the
    paragraph types a screenwriting app expects."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.parse(fdx).getroot()
    except ET.ParseError as e:
        return {"ok": False, "problem": f"not well-formed XML: {e}"}
    types: dict[str, int] = {}
    for p in root.iter("Paragraph"):
        t = p.get("Type", "")
        types[t] = types.get(t, 0) + 1
    ok = root.tag == "FinalDraft" and types.get("Scene Heading", 0) > 0
    return {"ok": ok, "paragraphs": types}


# --------------------------------------------------------------- scenes.json

def seq_of(path: Path, rep: Report) -> str:
    m = _SEQ_FROM_FILE_RE.search(path.stem)
    if m:
        return f"{int(m.group(1)):02d}"
    for s in rep.scenes:
        if s.id:
            return s.id[1:3]
    return path.stem


def chapter_fingerprints(book_root: Path | None, rep: Report) -> dict[str, str]:
    from ..summaries import body_hash
    out: dict[str, str] = {}
    if book_root is None:
        return out
    chapters = sorted({r["chapter"] for s in rep.scenes for r in s.source if "chapter" in r})
    for n in chapters:
        p = book_root / "chapters" / f"ch_{n:02d}.md"
        if p.is_file():
            out[f"ch_{n:02d}"] = body_hash(p.read_text(encoding="utf-8"))
    return out


def update_scenes_json(json_path: Path, path: Path, rep: Report, *, book_root: Path | None,
                       stamp: bool = False) -> dict:
    """Write this sequence's scenes into `film/scenes.json`, keeping the
    other sequences and any keys this check doesn't own. With `stamp`,
    record the fingerprint of each cited chapter as it now stands (the
    script was adapted from that text); without it, warn when a chapter
    changed since the last stamp."""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8")) if json_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        data = {}
    data.setdefault("schema", "autonovel-film-scenes/1")
    seqs = data.setdefault("sequences", {})
    seq = seq_of(path, rep)
    entry = seqs.setdefault(seq, {})
    rel = path.name
    try:
        rel = str(path.resolve().relative_to(json_path.resolve().parent))
    except ValueError:
        pass
    now = chapter_fingerprints(book_root, rep)
    stored = entry.get("adapted_from", {})
    if stamp or not stored:
        entry["adapted_from"] = now
    else:
        for ch, fp in now.items():
            if stored.get(ch) and stored[ch] != fp:
                rep.warnings.append(
                    f"{ch} has changed since this sequence was adapted from it; re-read the passage and "
                    "re-stamp (`--stamp`) after revising the script")
    chapters: dict[str, list[int]] = {}
    for s in rep.scenes:
        for r in s.source:
            if "from" in r:
                lo_hi = chapters.setdefault(f"ch_{r['chapter']:02d}", [r["from"], r["to"]])
                lo_hi[0], lo_hi[1] = min(lo_hi[0], r["from"]), max(lo_hi[1], r["to"])
    entry.update({
        "file": rel,
        "title": " ".join(rep.title_page.get("Title", [])) or path.stem,
        "source_lines": chapters,
        "scenes": [s.id or f"{seq}-{s.index:02d}" for s in rep.scenes],
        "eighths": rep.eighths,
        "length": eighths_label(rep.eighths),
        "page_lines": rep.page_lines,
        "pdf_pages": rep.exports.get("pdf_pages"),
        "roles": rep.roles,
        "checked": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    if rep.first_minute:
        entry["first_minute"] = rep.first_minute
    others = [s for s in data.get("scenes", []) if s.get("seq") != seq]
    mine = []
    for s in rep.scenes:
        mine.append({
            "id": s.id or f"{seq}-{s.index:02d}",
            "seq": seq,
            "slugline": f"{s.int_ext} {s.location} - {s.time}".strip() if s.int_ext else s.heading,
            "int_ext": s.int_ext,
            "location": s.location,
            "time": s.time,
            "characters": s.characters,
            "speaking": s.speaking,
            "source": s.source,
            "turn": s.turn,
            "eighths": s.eighths,
            "length": eighths_label(s.eighths),
            "line": s.line,
        })
    data["scenes"] = sorted(others + mine, key=lambda s: (s.get("seq", ""), s.get("id", "")))
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rep.scenes_json = str(json_path)
    return data


# --------------------------------------------------------------- reporting

def render_markdown(rep: Report) -> str:
    d = rep.to_dict()
    out = [f"# fountain-check: {Path(rep.path).name}", ""]
    out.append(f"**{'OK' if rep.ok else 'ERRORS'}** — {len(rep.scenes)} scenes, "
               f"{d['length']} pages by eighths ({rep.page_lines} lines, about "
               f"{d['minutes_estimate']} minutes)"
               + (f"; the PDF has {rep.exports['pdf_pages']} pages, title page included"
                  if rep.exports.get("pdf_pages") else "") + ".")
    out.append("")
    out.append("| ID | Heading | Length | Speaking | Turn |")
    out.append("|---|---|---|---|---|")
    for s in rep.scenes:
        out.append(f"| {s.id or s.index} | {s.heading} | {eighths_label(s.eighths)} | "
                   f"{', '.join(s.speaking) or '—'} | {s.turn or '—'} |")
    out.append("")
    out.append("| Speaker | Status | Speeches | Cast entry |")
    out.append("|---|---|---|---|")
    for name, info in sorted(rep.speakers.items()):
        out.append(f"| {name} | {info['status']} | {info['speeches']} | {info['match'] or '—'} |")
    for title, items in (("Errors", rep.errors), ("Warnings", rep.warnings),
                         ("Advisories", rep.advisories)):
        out.append("")
        out.append(f"## {title} ({len(items)})")
        out.extend(f"- {x}" for x in items) if items else out.append("- none")
    out.append("")
    out.append("## Exports")
    if not rep.exports:
        out.append("- not requested")
    for k, v in rep.exports.items():
        out.append(f"- {k}: {v}")
    if rep.first_minute:
        out.append("")
        out.append(f"**First minute to render:** {rep.first_minute['scene']} — {rep.first_minute['why']}")
    if rep.scenes_json:
        out.append("")
        out.append(f"scenes.json: {rep.scenes_json}")
    return "\n".join(out) + "\n"


def to_json(rep: Report) -> str:
    return json.dumps(rep.to_dict(), indent=2, ensure_ascii=False) + "\n"


def run(path: Path, *, book_root: Path | None = None, cast_paths: list[Path] | None = None,
        do_export: bool = True, export_dir: Path | None = None,
        scenes_json: Path | None | bool = None, stamp: bool = False) -> Report:
    """Check, export and record one script. `scenes_json=None` means the
    default (`<book>/film/scenes.json` when the script sits under
    `<book>/film/`), False means don't write it."""
    if book_root is None:
        book_root = find_book_root(path)
    rep = check(path, cast_paths=cast_paths, book_root=book_root)
    film = _film_dir(path, book_root)
    if do_export and rep.scenes:
        out_dir = export_dir or (film / "export" if film else path.parent)
        try:
            rep.exports = export(path, out_dir)
        except Exception as e:  # a renderer bug must not hide the check
            rep.exports = {"failed": f"{type(e).__name__}: {e}"}
            rep.errors.append(f"export failed: {type(e).__name__}: {e}")
        fdx_check = rep.exports.get("fdx_check")
        if fdx_check and not fdx_check.get("ok"):
            rep.errors.append(f"the FDX is not a usable Final Draft file: {fdx_check}")
    if scenes_json is None:
        scenes_json = (film / "scenes.json") if film else False
    if scenes_json:
        update_scenes_json(Path(scenes_json), path, rep, book_root=book_root, stamp=stamp)
    return rep


def _film_dir(path: Path, book_root: Path | None) -> Path | None:
    for d in [path.parent, *path.parents]:
        if d.name == "film":
            return d
        if book_root is not None and d == book_root:
            break
    return None
