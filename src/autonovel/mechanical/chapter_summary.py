"""Per-chapter overview table — what's in each chapter at a glance.

Pulls already-structured data from three places:

  1. Each `ch_NN.md` chapter file's YAML frontmatter — `chapter`,
     `pov`, `story_time`, `events`, `status`, `word_count`.
  2. Each `ch_NN.summary.md` continuity-handoff file's structured
     sections — **Plot**, **Cast on stage**, **Story time**.
  3. The latest eval log (`eval_logs/<timestamp>_chNN.json` or
     `eval_logs/<timestamp>_full.json`'s per-chapter rows) for
     `overall_score`.

Returns one record per drafted chapter with a normalised set of
fields the `/autonovel:chapter-summary` command renders as a
markdown table. Pure-Python; no LLM.

Bug story (2026-04-26): the user asked "how do I find which
chapters are mainly set in Venice when Jakob was learning?" and
correctly noted that grepping chapter prose isn't the right tool.
The structured fields above give a scannable per-chapter view that
makes that filter trivial — read down the Plot column, ignore
chapters whose `story_time` falls outside the relevant range.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .frontmatter import strip_yaml_frontmatter


@dataclass
class ChapterRow:
    chapter: int
    story_time: str | None = None
    pov: str | None = None
    word_count: int | None = None
    plot: str | None = None        # one-sentence pull from Plot
    cast: list[str] = field(default_factory=list)   # names from Cast on stage
    score: float | None = None     # latest overall_score
    status: str | None = None      # frontmatter status (drafted / revised / etc)

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter,
            "story_time": self.story_time,
            "pov": self.pov,
            "word_count": self.word_count,
            "plot": self.plot,
            "cast": list(self.cast),
            "score": self.score,
            "status": self.status,
        }


def summarize_chapters(book_root: Path) -> list[ChapterRow]:
    """Return one ChapterRow per drafted `ch_NN.md` under
    `book_root/chapters/`, ordered by chapter number. Chapters
    without a summary file or eval log produce a row with the
    available fields populated and the rest left None.
    """
    from ..paths import iter_chapter_files
    chapters_dir = book_root / "chapters"
    chapter_files = iter_chapter_files(chapters_dir)
    eval_dir = book_root / "eval_logs"
    eval_index = _index_latest_per_chapter_eval(eval_dir)

    rows: list[ChapterRow] = []
    for ch_path in chapter_files:
        num_str = ch_path.stem.split("_")[-1]
        try:
            num = int(num_str)
        except ValueError:
            continue

        row = ChapterRow(chapter=num)
        text = ch_path.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        row.story_time = fm.get("story_time")
        row.pov = fm.get("pov")
        row.status = fm.get("status")
        wc = fm.get("word_count")
        if wc is not None:
            try:
                row.word_count = int(wc)
            except (TypeError, ValueError):
                pass

        # Fall back to a real word count if frontmatter didn't carry one
        # (rare; chapters drafted before word_count became standard).
        # Strip the leading `# Title` heading so the fallback matches
        # the frontmatter convention (body words only, not the heading).
        if row.word_count is None:
            body = strip_yaml_frontmatter(text).lstrip()
            if body.startswith("#"):
                # Drop the heading line plus any blank lines after it.
                lines = body.splitlines()
                lines = lines[1:]
                while lines and lines[0].strip() == "":
                    lines.pop(0)
                body = "\n".join(lines)
            row.word_count = len(body.split())

        summary_path = chapters_dir / f"{ch_path.stem}.summary.md"
        if summary_path.is_file():
            sm = _parse_summary(summary_path.read_text(encoding="utf-8"))
            row.plot = sm.get("plot")
            row.cast = sm.get("cast") or []
            # The summary's Story time tends to be more specific than
            # the frontmatter's (which can be a range); prefer it
            # when present.
            if sm.get("story_time"):
                row.story_time = sm["story_time"]

        row.score = eval_index.get(num)
        rows.append(row)
    return rows


# ----------------------------------------------------- frontmatter parsing


_FRONTMATTER_FIELDS = ("chapter", "pov", "story_time", "events",
                       "status", "word_count", "book")


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract YAML frontmatter as a flat string→string dict.

    We don't pull in PyYAML for this — the chapter frontmatter is a
    flat shallow mapping with simple scalar values, and parsing it
    line-by-line keeps the helper dependency-light. Fields not in
    `_FRONTMATTER_FIELDS` are ignored.
    """
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out: dict[str, str] = {}
    for i in range(1, len(lines)):
        line = lines[i]
        if line.strip() == "---":
            break
        # Field on its own line: `key: value` (value may be quoted).
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if key not in _FRONTMATTER_FIELDS:
            continue
        # Strip surrounding quotes on the value (single or double).
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        out[key] = value
    return out


# --------------------------------------------------- summary.md parsing


_SECTION_RE = re.compile(r"^\s*\*\*([A-Z][A-Za-z ]+):\*\*\s*(.*)$")


def _parse_summary(text: str) -> dict:
    """Pull `**Plot:**`, `**Cast on stage:**`, `**Story time:**` from
    a summary.md. Returns a dict with `plot` (one-sentence string),
    `cast` (list of names), `story_time` (string).

    The summary template (commands/draft.md step 12, summarize-
    chapter.md step) writes each field as `**Field:** value` — the
    regex above matches that shape and is generous about
    whitespace.
    """
    sections: dict[str, str] = {}
    current_key: str | None = None
    current_buf: list[str] = []

    def flush() -> None:
        nonlocal current_key, current_buf
        if current_key:
            sections[current_key] = " ".join(current_buf).strip()
        current_key = None
        current_buf = []

    for raw in text.splitlines():
        m = _SECTION_RE.match(raw)
        if m:
            flush()
            key = m.group(1).strip().lower()
            current_key = key
            first_value = m.group(2).strip()
            if first_value:
                current_buf.append(first_value)
        elif current_key:
            stripped = raw.strip()
            if stripped:
                current_buf.append(stripped)
    flush()

    out: dict = {}
    if "plot" in sections:
        out["plot"] = _first_sentence(sections["plot"])
    if "cast on stage" in sections:
        out["cast"] = _parse_cast(sections["cast on stage"])
    if "story time" in sections:
        out["story_time"] = sections["story time"]
    return out


def _first_sentence(text: str) -> str:
    """Return text up through the first sentence-ending punctuation
    (`.`, `?`, `!`). If none found, return the whole text. Caps at
    180 chars in either case so a single rambling sentence doesn't
    blow the column width."""
    if not text:
        return ""
    m = re.search(r"[.!?](?=\s|$)", text)
    if m:
        result = text[: m.end()].strip()
    else:
        result = text.strip()
    if len(result) > 180:
        result = result[:179].rstrip() + "…"
    return result


def _parse_cast(text: str) -> list[str]:
    """The Cast on stage line in a summary looks like:
       'Tommaso — POV; Niccolò — first appearance, declined to speak; Marco — antagonist'
    Pull just the names (everything before the first '—' or ',' in
    each ';'-separated entry)."""
    names: list[str] = []
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        # Split off any role descriptor after `—`, `-`, or `,`.
        for sep in (" — ", " – ", " - ", ","):
            if sep in chunk:
                chunk = chunk.split(sep, 1)[0]
                break
        chunk = chunk.strip()
        if chunk and chunk not in names:
            names.append(chunk)
    return names


# ----------------------------------------------------- eval log indexing


_EVAL_FILENAME_RE = re.compile(
    r"^(?P<ts>\d{8}_\d{6})_ch(?P<chapter>\d+)_eval\.json$"
)
_EVAL_CH_FILENAME_RE = re.compile(
    r"^(?P<ts>\d{8}_\d{6})_ch(?P<chapter>\d+)\.json$"
)


def _index_latest_per_chapter_eval(eval_dir: Path) -> dict[int, float]:
    """Return {chapter_number: latest overall_score} by scanning
    `eval_logs/`. Tolerates a few historical naming conventions
    (`<ts>_ch01.json`, `<ts>_ch01_eval.json`, plain `chNN_eval.json`).
    Picks the latest by filename timestamp prefix, or by mtime when
    no timestamp prefix is present. Skips files it can't parse.
    """
    if not eval_dir.is_dir():
        return {}
    by_chapter: dict[int, tuple[str, float]] = {}
    for path in eval_dir.iterdir():
        if not path.is_file() or path.suffix != ".json":
            continue
        m = _EVAL_FILENAME_RE.match(path.name) or _EVAL_CH_FILENAME_RE.match(path.name)
        if m:
            ts = m.group("ts")
            try:
                chapter = int(m.group("chapter"))
            except ValueError:
                continue
        else:
            # Plain `chNN_eval.json` (no timestamp prefix) — use mtime.
            plain = re.match(r"^ch(\d+)_eval\.json$", path.name)
            if not plain:
                continue
            try:
                chapter = int(plain.group(1))
            except ValueError:
                continue
            ts = f"mtime_{path.stat().st_mtime:.0f}"

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — skip malformed eval logs
            continue
        if not isinstance(data, dict):
            continue
        score = data.get("overall_score")
        if score is None:
            continue
        try:
            score_f = float(score)
        except (TypeError, ValueError):
            continue

        prior = by_chapter.get(chapter)
        if prior is None or ts > prior[0]:
            by_chapter[chapter] = (ts, score_f)
    return {ch: score for ch, (_ts, score) in by_chapter.items()}


# ----------------------------------------------------- table renderer


def render_markdown_table(rows: list[ChapterRow]) -> str:
    """Render the chapter summary as a markdown table the
    `/autonovel:chapter-summary` command prints to stdout.

    Columns: Ch | Date | POV | Score | Words | Cast | Plot.
    Cast and Plot are width-trimmed defensively so the table stays
    one-row-per-chapter even on long entries.
    """
    if not rows:
        return "_No chapters drafted yet._\n"

    header = "| Ch | Date       | POV       | Score | Words | Cast                          | Plot |"
    sep    = "|----|------------|-----------|-------|-------|-------------------------------|------|"
    lines = [header, sep]
    for r in rows:
        ch = f"{r.chapter:>2}"
        date = (r.story_time or "—")[:10].ljust(10)
        pov = (r.pov or "—")[:9].ljust(9)
        score = f"{r.score:.1f}" if r.score is not None else "—"
        score_col = score.center(5)
        words = f"{r.word_count}" if r.word_count is not None else "—"
        words_col = words.rjust(5)
        cast_str = ", ".join(r.cast) if r.cast else "—"
        if len(cast_str) > 29:
            cast_str = cast_str[:28] + "…"
        cast_col = cast_str.ljust(29)
        plot = (r.plot or "—").replace("|", "\\|")
        lines.append(f"| {ch} | {date} | {pov} | {score_col} | {words_col} | {cast_col} | {plot} |")
    return "\n".join(lines) + "\n"
