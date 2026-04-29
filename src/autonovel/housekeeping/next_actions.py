"""State-aware next-action enumerator for `/autonovel:next`.

Today's `next_step()` (in next_step.py) returns a single canonical
"what to do next in the pipeline" given a PipelineState. That's
correct for the simple case but misses situations where multiple
concurrent actions matter — pending canon conflicts, chapter
regressions, stale panel reports, ungit-backed changes, missing
title/author, missing front matter, stale typeset.

This module reads filesystem state directly (no last-action.json
replay; no LLM) and returns a *list* of NextAction records ordered
by priority. The /autonovel:next slash-command body invokes the
underlying CLI helper and prints the list verbatim.

Why two modules:
  - next_step.py answers "given this PipelineState, what's the
    canonical next pipeline step?". It's pure-function, no I/O,
    deeply testable. Used by the postamble's footer.
  - next_actions.py answers "given the live filesystem RIGHT NOW,
    what concurrent things should the user be aware of?". I/O-
    heavy; covers state next_step.py doesn't model (regressions,
    backup status, front matter, etc.). Used by /autonovel:next.

Both are invoked together by the slash-command: the canonical
next-step is included as one of the actions (always present, lowest
priority because it's the "if nothing more urgent, do this" line),
and the situational actions are sorted ahead of it by severity.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .. import last_action as last_action_mod, project as project_mod
from ..paths import SeriesLayout, iter_chapter_files


@dataclass
class NextAction:
    """One actionable line in the /autonovel:next output."""
    priority: str           # "HIGH" | "MEDIUM" | "LOW" | "INFO"
    title: str              # one-line summary
    command: str | None     # the canonical command to run, if any
    rationale: str          # why this matters (2-3 sentences max)
    book: str | None = None # which book this concerns (None = series-wide)

    def to_dict(self) -> dict:
        return {
            "priority": self.priority,
            "title": self.title,
            "command": self.command,
            "rationale": self.rationale,
            "book": self.book,
        }


# Priority ordering: HIGH first, then MEDIUM, LOW, INFO.
_PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}


def enumerate_actions(series: SeriesLayout, *, book: str | None = None) -> list[NextAction]:
    """Inspect filesystem state for one book (or every book in the
    series if `book` is None) and return a prioritised action list.
    """
    actions: list[NextAction] = []
    cfg = project_mod.load(series.project_file)
    book_names = [b.name for b in cfg.books] if book is None else [book]
    for b in book_names:
        actions.extend(_actions_for_book(series, cfg, b))
    actions.extend(_series_wide_actions(series, cfg))
    actions.sort(key=lambda a: _PRIORITY_ORDER.get(a.priority, 99))
    return actions


def _actions_for_book(series: SeriesLayout, cfg: project_mod.ProjectConfig,
                      book: str) -> list[NextAction]:
    book_root = series.books / book
    if not book_root.is_dir():
        return []
    out: list[NextAction] = []
    out.extend(_pending_canon_conflict_actions(book_root, book))
    out.extend(_chapter_regression_actions(book_root, book))
    out.extend(_panel_staleness_actions(book_root, book))
    out.extend(_review_staleness_actions(book_root, book))
    out.extend(_typeset_staleness_actions(book_root, book, series.root))
    out.extend(_missing_title_author_actions(cfg, book))
    out.extend(_missing_front_matter_actions(book_root, book))
    return out


def _series_wide_actions(series: SeriesLayout,
                          cfg: project_mod.ProjectConfig) -> list[NextAction]:
    out: list[NextAction] = []
    out.extend(_git_backup_actions(series.root))
    return out


# ---------------------------------------------------------- per-book


def _pending_canon_conflict_actions(book_root: Path, book: str) -> list[NextAction]:
    pending = book_root / "pending_canon.md"
    if not pending.is_file():
        return []
    text = pending.read_text(encoding="utf-8")
    if "# Conflicts — resolve before next promote-canon" not in text:
        return []
    conflict_count = len(re.findall(r"^## Conflict \d+\s*$", text, re.MULTILINE))
    return [NextAction(
        priority="HIGH",
        title=f"Resolve {conflict_count} canon conflict(s) in {book}",
        command=None,  # manual edit; no single command resolves it
        rationale=(
            f"books/{book}/pending_canon.md has {conflict_count} "
            f"## Conflict N block(s) needing human resolution. Open "
            f"the file and follow the HOW TO RESOLVE A CONFLICT block "
            f"at the top (three labelled paths: accept / reject / "
            f"both wrong). Re-run /autonovel:promote-canon after "
            f"editing."
        ),
        book=book,
    )]


def _chapter_regression_actions(book_root: Path, book: str) -> list[NextAction]:
    """Find chapters whose latest eval score is LOWER than a prior
    eval score for the same chapter — those are regressions worth
    re-running.

    Only flags real regressions (drop ≥0.3) to filter eval-noise.
    """
    eval_dir = book_root / "eval_logs"
    if not eval_dir.is_dir():
        return []
    by_chapter: dict[int, list[tuple[str, float]]] = {}
    for path in eval_dir.iterdir():
        if not path.is_file() or path.suffix != ".json":
            continue
        # Tolerate the same three filename shapes as
        # mechanical/chapter_summary.py: `<ts>_chNN_eval.json`,
        # `<ts>_chNN.json`, plain `chNN_eval.json`. Plain shape has no
        # timestamp prefix → fall back to mtime so we can still order.
        m = re.match(r"^(?P<ts>\d{8}_\d{6})_ch(?P<ch>\d+)(_eval)?\.json$", path.name)
        if m:
            ts = m.group("ts")
            ch = int(m.group("ch"))
        else:
            plain = re.match(r"^ch(?P<ch>\d+)_eval\.json$", path.name)
            if not plain:
                continue
            ts = f"mtime_{path.stat().st_mtime:.0f}"
            ch = int(plain.group("ch"))
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(data, dict):
            continue
        score = data.get("overall_score")
        if not isinstance(score, (int, float)):
            continue
        by_chapter.setdefault(ch, []).append((ts, float(score)))

    regressed: list[tuple[int, float, float]] = []
    for ch, entries in by_chapter.items():
        entries.sort(key=lambda x: x[0])
        if len(entries) < 2:
            continue
        prior_max = max(s for _, s in entries[:-1])
        latest = entries[-1][1]
        if prior_max - latest >= 0.3:
            regressed.append((ch, prior_max, latest))

    if not regressed:
        return []
    chapters_str = ",".join(str(c) for c, _, _ in sorted(regressed))
    deltas = ", ".join(
        f"ch{c} {p:.1f}→{l:.1f}" for c, p, l in sorted(regressed)
    )
    return [NextAction(
        priority="HIGH",
        title=f"Re-run regressed chapter(s): {chapters_str}",
        command=f"/autonovel:revision-pass --chapters {chapters_str} --book {book}",
        rationale=(
            f"{len(regressed)} chapter(s) ended below their prior best "
            f"by ≥0.3 ({deltas}). The latest revise made them worse, "
            f"not better. Re-run the brief→revise cycle (without "
            f"--enrich-with this time) so the brief reconsiders from "
            f"cuts/eval evidence alone."
        ),
        book=book,
    )]


def _panel_staleness_actions(book_root: Path, book: str) -> list[NextAction]:
    panel = book_root / "edit_logs" / "reader_panel.json"
    return _staleness_check(
        report_path=panel,
        book_root=book_root,
        book=book,
        report_label="reader-panel report",
        rerun_command=f"/autonovel:reader-panel --book {book}",
        priority="MEDIUM",
    )


def _review_staleness_actions(book_root: Path, book: str) -> list[NextAction]:
    review = book_root / "edit_logs" / "opus_review.md"
    return _staleness_check(
        report_path=review,
        book_root=book_root,
        book=book,
        report_label="Opus review",
        rerun_command=f"/autonovel:review --book {book}",
        priority="MEDIUM",
    )


def _staleness_check(*, report_path: Path, book_root: Path, book: str,
                      report_label: str, rerun_command: str,
                      priority: str) -> list[NextAction]:
    """Generic mtime check: if the report exists but a chapter has
    been touched since, the report is stale."""
    if not report_path.is_file():
        return []
    report_mtime = report_path.stat().st_mtime
    newer_chapters: list[int] = []
    for ch_path in iter_chapter_files(book_root / "chapters"):
        if ch_path.stat().st_mtime > report_mtime:
            try:
                newer_chapters.append(int(ch_path.stem.split("_")[-1]))
            except ValueError:
                continue
    if not newer_chapters:
        return []
    return [NextAction(
        priority=priority,
        title=f"Re-run {report_label} ({len(newer_chapters)} chapter(s) changed since)",
        command=rerun_command,
        rationale=(
            f"{report_label} at {report_path.relative_to(book_root.parent.parent)} "
            f"was last written before chapters {sorted(newer_chapters)} were "
            f"touched. The prior report describes a manuscript that no "
            f"longer exists; re-running gives you a fresh flagged-chapter "
            f"list against the current prose."
        ),
        book=book,
    )]


def _typeset_staleness_actions(book_root: Path, book: str,
                                series_root: Path) -> list[NextAction]:
    typeset_dir = book_root / "typeset"
    if not typeset_dir.is_dir():
        return []
    # Look for the canonical *_latest.pdf written by typeset.
    latest_pdf = list(typeset_dir.glob("*_latest.pdf"))
    if not latest_pdf:
        return []
    pdf_mtime = latest_pdf[0].stat().st_mtime
    newer = [p for p in iter_chapter_files(book_root / "chapters")
             if p.stat().st_mtime > pdf_mtime]
    if not newer:
        return []
    return [NextAction(
        priority="LOW",
        title=f"Rebuild PDF + ePub ({len(newer)} chapter(s) changed since last typeset)",
        command=f"/autonovel:typeset --book {book}",
        rationale=(
            f"books/{book}/typeset/{latest_pdf[0].name} predates "
            f"{len(newer)} of your chapter files. Rebuild to read "
            f"the current state in PDF form (cheap; safe; read-only "
            f"against chapter prose)."
        ),
        book=book,
    )]


def _missing_title_author_actions(cfg: project_mod.ProjectConfig,
                                   book: str) -> list[NextAction]:
    """Suggest /autonovel:title only when the book is far enough
    along that the title page would actually appear in a typeset
    output (skip during foundation/early drafting)."""
    book_entry = cfg.book_by_name(book)
    if book_entry is None:
        return []
    has_title = bool(book_entry.title)
    has_author = bool(book_entry.author or cfg.author)
    if has_title and has_author:
        return []
    missing: list[str] = []
    if not has_title:
        missing.append("title")
    if not has_author:
        missing.append("author")
    return [NextAction(
        priority="LOW",
        title=f"Set the book's display {' + '.join(missing)} for typeset",
        command=f"/autonovel:title --book {book}",
        rationale=(
            f"project.yaml :: books[{book}].title and/or .author "
            f"is unset. Typeset will fall back to the series "
            f"slug / 'Anonymous' on the title page. Run "
            f"/autonovel:title to propose candidates from the "
            f"outline + seed (or use --set / --author to set "
            f"explicit values)."
        ),
        book=book,
    )]


def _missing_front_matter_actions(book_root: Path, book: str) -> list[NextAction]:
    """Suggest /autonovel:introduction only once the book has
    chapters drafted — front matter doesn't matter during
    foundation."""
    chapters = iter_chapter_files(book_root / "chapters")
    if len(chapters) < 3:
        return []
    has_preface = (book_root / "preface.md").is_file()
    has_intro = (book_root / "introduction.md").is_file()
    if has_preface or has_intro:
        return []
    return [NextAction(
        priority="LOW",
        title=f"Add a preface or introduction for the typeset front matter",
        command=f"/autonovel:introduction --book {book} --from both",
        rationale=(
            f"books/{book} has neither preface.md nor "
            f"introduction.md. Optional, but a typeset book without "
            f"either feels truncated at the title page. --from both "
            f"scaffolds preface.md (you write) and AI-drafts "
            f"introduction.md (you edit)."
        ),
        book=book,
    )]


# ---------------------------------------------------------- series-wide


def _git_backup_actions(series_root: Path) -> list[NextAction]:
    """Three states:
      - no git repo at all → suggest setting up the backup
      - git repo with no remote → suggest setting up the backup
      - git repo with remote AND uncommitted/unpushed changes →
        suggest commit + push
      - git repo, all clean → no action
    """
    if not (series_root / ".git").is_dir():
        return [NextAction(
            priority="MEDIUM",
            title="Back up your novel to a private GitHub repo",
            command=None,  # multi-step; see operating-guide §3e.1
            rationale=(
                f"{series_root} is not a git repository. Your novel "
                f"is local-only. See operating-guide §3e.1 for the "
                f"one-time setup (git init + .gitignore copy + "
                f"`gh repo create my-novel-backup --private "
                f"--source=. --remote=origin --push`)."
            ),
            book=None,
        )]
    # Check remote.
    try:
        remotes = subprocess.run(
            ["git", "-C", str(series_root), "remote"],
            capture_output=True, text=True, check=True,
        ).stdout.strip().splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    if not remotes:
        return [NextAction(
            priority="MEDIUM",
            title="Add a GitHub remote and push your novel as backup",
            command=None,
            rationale=(
                f"{series_root} is git-tracked but has no remote. "
                f"`gh repo create my-novel-backup --private --source=. "
                f"--remote=origin --push` from the series root sets "
                f"up the private backup. See operating-guide §3e.1."
            ),
            book=None,
        )]
    # Check for uncommitted or unpushed changes.
    try:
        status = subprocess.run(
            ["git", "-C", str(series_root), "status", "--porcelain"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return []
    if status:
        return [NextAction(
            priority="MEDIUM",
            title="Commit + push uncommitted changes to the GitHub backup",
            command=None,
            rationale=(
                f"{series_root} has uncommitted changes. From the "
                f"series root: `git add . && git commit -m \"Snapshot\" "
                f"&& git push`. Substantive revision passes are the "
                f"right cadence for a snapshot."
            ),
            book=None,
        )]
    # Check unpushed commits.
    try:
        ahead = subprocess.run(
            ["git", "-C", str(series_root), "rev-list", "--count",
             "@{u}..HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return []
    if ahead and ahead != "0":
        return [NextAction(
            priority="MEDIUM",
            title=f"Push {ahead} unpushed commit(s) to GitHub",
            command=None,
            rationale=(
                f"{series_root} is {ahead} commit(s) ahead of the "
                f"remote. `git push` from the series root sends them."
            ),
            book=None,
        )]
    return []


# ------------------------------------------------------- canonical step


def canonical_pipeline_action(series: SeriesLayout, *, book: str | None = None) -> NextAction | None:
    """Read the most recent last-action.json and return its
    next_standard_step as an INFO-priority action. This is the
    pipeline-canonical "if nothing more urgent applies, do this"
    line. None when no last-action.json exists yet (fresh series)."""
    la = last_action_mod.read(series.last_action_file)
    if la is None or not la.next_standard_step:
        return None
    if book is not None and la.book and la.book != book:
        return None
    return NextAction(
        priority="INFO",
        title="Pipeline-standard next step (from last command's footer)",
        command=la.next_standard_step,
        rationale=(
            la.next_rationale or
            f"After {la.command}, the standard next step in the "
            f"pipeline is what's stored in last-action.json. (Note: "
            f"this is replayed from the prior command — situational "
            f"actions above this line, when present, take "
            f"precedence.)"
        ),
        book=la.book,
    )


# ------------------------------------------------------------- render


def render_human(actions: list[NextAction], *, canonical: NextAction | None) -> str:
    """Markdown rendering for the slash-command's output. Groups by
    priority; canonical pipeline action comes last with its own
    block."""
    if not actions and canonical is None:
        return "_No actions queued. Series is clean._\n"
    parts: list[str] = []
    grouped: dict[str, list[NextAction]] = {}
    for a in actions:
        grouped.setdefault(a.priority, []).append(a)
    for prio in ("HIGH", "MEDIUM", "LOW"):
        if prio not in grouped:
            continue
        marker = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}[prio]
        parts.append(f"### {marker} {prio} priority\n")
        for a in grouped[prio]:
            parts.append(f"**{a.title}**" + (f" *({a.book})*" if a.book else ""))
            if a.command:
                parts.append(f"```text\n{a.command}\n```")
            parts.append(a.rationale)
            parts.append("")
    if canonical is not None:
        parts.append("### ⚪ Canonical pipeline next step\n")
        parts.append(f"**{canonical.title}**")
        if canonical.command:
            parts.append(f"```text\n{canonical.command}\n```")
        parts.append(canonical.rationale)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"
