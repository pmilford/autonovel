"""Import an externally-written manuscript into autonovel's chapter shape.

Use case: the user has a finished or partial book (their own, an
estate's, a public-domain text being modernised) and wants to use
autonovel's evaluate / revise / panel / review / typeset surfaces
against it without re-drafting from scratch.

What this module does:

  - Splits a source path (a directory of `*.md` files OR a single
    combined manuscript) into chapter records, in source order.
  - Optional `--split-on <regex>` to override the default heading
    split for combined manuscripts.
  - Writes each chapter as `books/<book>/chapters/ch_NN.md` with
    autonovel-shape YAML frontmatter. Pre-existing frontmatter on
    the source side is stripped.
  - Marks the book as `mode: edit-imported` in `project.yaml` so
    `/autonovel:draft` refuses (without `--force`) to overwrite.

What this module does NOT do (yet — these are follow-up scopes):

  - Reverse-engineer a foundation (voice / characters / outline)
    from the imported prose. The user runs the existing
    foundation commands manually after import, OR supplies their
    own foundation files (the `--keep-foundation` posture is
    just "don't touch shared/").
  - Backfill `pov` / `story_time` / cast on the imported
    frontmatter. Those land as `inferred` placeholders that
    `/autonovel:summarize-chapter --all` can later fill via an
    LLM pass.
  - Convert non-markdown formats (`.docx`, `.epub`, `.txt`).
    Pandoc is the right tool for that and is already a documented
    optional dependency; users pre-convert before running import.

Pure mechanical. No LLM. No network. Tier-1 testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .mechanical.frontmatter import strip_yaml_frontmatter


@dataclass
class ChapterDoc:
    title: str | None        # heading text if found, else None
    body: str                # prose without any pre-existing frontmatter
    source: str              # one-line description of the source for audit


@dataclass
class ImportResult:
    chapters_written: list[Path]
    skipped_existing: list[Path]
    chapters: list[ChapterDoc]
    book_name: str
    mode_set: str            # "edit-imported" or "kept" (when --keep-mode)
    dry_run: bool

    def to_dict(self) -> dict:
        return {
            "book_name": self.book_name,
            "mode_set": self.mode_set,
            "dry_run": self.dry_run,
            "written": [str(p) for p in self.chapters_written],
            "skipped_existing": [str(p) for p in self.skipped_existing],
            "chapters": [
                {"title": c.title, "source": c.source,
                 "word_count": _word_count(c.body)}
                for c in self.chapters
            ],
        }


# ---------------------------------------------------------- splitting


# Matches a markdown level-1 heading on its own line.
_H1_RE = re.compile(r"^# +(?P<title>.+?)\s*$", re.MULTILINE)
# Falls back to level-2 when no level-1 headings exist.
_H2_RE = re.compile(r"^## +(?P<title>.+?)\s*$", re.MULTILINE)


class ImportError_(ValueError):
    """User-facing splitter / writer errors."""


def split_chapters(source: Path, *,
                    split_on: str | None = None) -> list[ChapterDoc]:
    """Split `source` into a list of ChapterDoc records in source order.

    `source` is one of:
      - A directory: every `*.md` file is treated as one chapter,
        sorted by filename. Sub-directories are not recursed.
      - A single `.md` file: split by the optional `--split-on`
        regex if supplied, else by `^# ` headings, falling back to
        `^## ` if the file has no level-1 headings, falling back
        to "treat the whole file as one chapter" if neither.

    Pre-existing YAML frontmatter on each section is stripped.
    Empty (whitespace-only) chunks are dropped.
    """
    if not source.exists():
        raise ImportError_(f"import source not found: {source}")
    if source.is_dir():
        return _split_directory(source)
    if source.is_file():
        return _split_single_file(source, split_on=split_on)
    raise ImportError_(f"unsupported import source: {source}")


def _split_directory(source: Path) -> list[ChapterDoc]:
    files = sorted(p for p in source.iterdir()
                    if p.is_file() and p.suffix.lower() == ".md")
    if not files:
        raise ImportError_(
            f"directory has no `*.md` files: {source}. Convert source "
            f"format with pandoc first; only markdown is supported."
        )
    chapters: list[ChapterDoc] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        body = strip_yaml_frontmatter(text).lstrip()
        if not body.strip():
            continue
        title = _heading_title(body) or path.stem
        # If the first body line was the heading, drop it from the body.
        body = _strip_leading_heading(body)
        chapters.append(ChapterDoc(
            title=title, body=body, source=str(path),
        ))
    if not chapters:
        raise ImportError_(
            f"every file in {source} was empty after frontmatter strip"
        )
    return chapters


def _split_single_file(source: Path, *,
                        split_on: str | None) -> list[ChapterDoc]:
    text = source.read_text(encoding="utf-8")
    text = strip_yaml_frontmatter(text)
    if split_on is not None:
        try:
            split_re = re.compile(split_on, re.MULTILINE)
        except re.error as e:
            raise ImportError_(
                f"--split-on regex {split_on!r} is not valid: {e}"
            ) from e
        return _split_by_regex(text, split_re, source)
    # Default cascade: H1 → H2 → single chapter.
    if _H1_RE.search(text):
        return _split_by_regex(text, _H1_RE, source)
    if _H2_RE.search(text):
        return _split_by_regex(text, _H2_RE, source)
    body = text.strip()
    if not body:
        raise ImportError_(f"source file is empty after frontmatter strip: {source}")
    return [ChapterDoc(title=None, body=body,
                        source=f"{source} (single chapter)")]


def _split_by_regex(text: str, pattern: re.Pattern[str],
                     source: Path) -> list[ChapterDoc]:
    """Split text on every match of `pattern`. Each chunk runs from
    one match's start through the next match's start (or end-of-text).
    Pre-match content (front matter / table of contents) is dropped.
    """
    matches = list(pattern.finditer(text))
    if not matches:
        body = text.strip()
        return [ChapterDoc(title=None, body=body,
                            source=f"{source} (single chapter)")]
    chapters: list[ChapterDoc] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()
        if not chunk:
            continue
        title = m.groupdict().get("title", "").strip() if m.groupdict() else ""
        # Strip the leading heading line from the body.
        body = _strip_leading_heading(chunk)
        chapters.append(ChapterDoc(
            title=title or None, body=body,
            source=f"{source}#L{text.count(chr(10), 0, start) + 1}",
        ))
    if not chapters:
        raise ImportError_(
            f"split by {pattern.pattern!r} produced no non-empty chapters"
        )
    return chapters


def _heading_title(body: str) -> str | None:
    m = _H1_RE.match(body) or _H2_RE.match(body)
    return m.group("title").strip() if m else None


def _strip_leading_heading(body: str) -> str:
    """Drop the first line if it's a markdown heading."""
    if not body:
        return body
    first_line, _, rest = body.partition("\n")
    if first_line.lstrip().startswith("#"):
        return rest.lstrip("\n")
    return body


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


# ---------------------------------------------------------- writing


def write_chapters(book_root: Path, chapters: list[ChapterDoc], *,
                    book_name: str,
                    start_at: int = 1,
                    pov: str | None = None,
                    overwrite_existing: bool = False,
                    dry_run: bool = False) -> tuple[list[Path], list[Path]]:
    """Write each ChapterDoc as `books/<book>/chapters/ch_NN.md` with
    autonovel-shape frontmatter. Returns `(written, skipped_existing)`.

    Without `overwrite_existing`, a chapter file that already exists at
    the target path is left untouched and recorded under
    `skipped_existing`. With it, the file is overwritten (use the
    flag deliberately — the source manuscript loses its prior
    autonovel-shape edits).
    """
    chapters_dir = book_root / "chapters"
    if not dry_run:
        chapters_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    skipped: list[Path] = []
    for i, chapter in enumerate(chapters):
        n = start_at + i
        target = chapters_dir / f"ch_{n:02d}.md"
        if target.exists() and not overwrite_existing:
            skipped.append(target)
            continue
        rendered = _render_chapter(chapter, n=n, book_name=book_name, pov=pov)
        if not dry_run:
            target.write_text(rendered, encoding="utf-8")
        written.append(target)
    return written, skipped


def _render_chapter(c: ChapterDoc, *, n: int, book_name: str,
                     pov: str | None) -> str:
    """Render one chapter file: autonovel-shape YAML + body."""
    body = c.body.rstrip() + "\n"
    wc = _word_count(body)
    pov_line = f"pov: {pov}\n" if pov else "pov: inferred\n"
    title_line = f"title: {_yaml_quote(c.title)}\n" if c.title else ""
    return (
        f"---\n"
        f"book: {book_name}\n"
        f"chapter: {n}\n"
        f"{title_line}"
        f"{pov_line}"
        f"story_time: inferred\n"
        f"events: []\n"
        f"status: imported\n"
        f"word_count: {wc}\n"
        f"imported_from: {_yaml_quote(c.source)}\n"
        f"---\n\n"
        f"{body}"
    )


def _yaml_quote(value: str) -> str:
    """Minimal-safe YAML scalar quoting — single-quote unless the
    value is plain ASCII without colons/quotes/braces."""
    if (not value or any(ch in value for ch in ':\'"#{}[]&*?|>!%@`,')):
        # Single-quote and double up internal apostrophes.
        return "'" + value.replace("'", "''") + "'"
    return value


# ---------------------------------------------------------- top-level entry


def import_manuscript(
    series_root: Path, book_name: str, source: Path, *,
    split_on: str | None = None,
    start_at: int | None = None,
    pov: str | None = None,
    keep_mode: bool = False,
    overwrite_existing: bool = False,
    dry_run: bool = False,
) -> ImportResult:
    """End-to-end import: split + write chapters + update project.yaml mode.

    Refuses if the book doesn't yet exist in `project.yaml` (caller
    must run `autonovel new-book <name>` first); we do this so the
    book has a consistent path layout and lifecycle entry.

    `start_at` defaults to one more than the highest existing
    `ch_NN.md` in the target chapters dir, so re-running with
    additional source files appends rather than overwriting.
    `keep_mode=True` leaves `project.yaml :: books[].mode`
    untouched — useful when the user wants to import additional
    chapters into a draft-mode book without flipping it to
    edit-imported.
    """
    from . import project as project_mod
    from .paths import iter_chapter_files

    cfg = project_mod.load(series_root / "project.yaml")
    entry = cfg.book_by_name(book_name)
    if entry is None:
        raise ImportError_(
            f"book {book_name!r} is not in project.yaml. Run "
            f"`autonovel new-book {book_name}` first."
        )
    book_root = series_root / "books" / book_name

    if start_at is None:
        existing = iter_chapter_files(book_root / "chapters")
        if existing:
            last = max(int(p.stem.split("_")[-1]) for p in existing)
            start_at = last + 1
        else:
            start_at = 1

    chapters = split_chapters(source, split_on=split_on)
    written, skipped = write_chapters(
        book_root, chapters,
        book_name=book_name,
        start_at=start_at,
        pov=pov,
        overwrite_existing=overwrite_existing,
        dry_run=dry_run,
    )

    if keep_mode:
        mode_set = "kept"
    else:
        entry.mode = "edit-imported"
        if not dry_run:
            project_mod.dump(cfg, series_root / "project.yaml")
        mode_set = "edit-imported"

    return ImportResult(
        chapters_written=written,
        skipped_existing=skipped,
        chapters=chapters,
        book_name=book_name,
        mode_set=mode_set,
        dry_run=dry_run,
    )
