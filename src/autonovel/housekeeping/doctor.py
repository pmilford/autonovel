"""`autonovel doctor` — sanity-check a series directory.

Reports what is wrong without changing anything (unless `fix=True`, which only
does safe mkdirs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .. import lock, project as project_mod
from ..paths import SERIES_MARKER, SeriesLayout


@dataclass
class DoctorReport:
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


REQUIRED_DIRS = (
    "shared",
    "shared/research",
    "shared/research/seed",
    "shared/research/notes",
    "books",
    ".autonovel",
    ".autonovel/checkpoints",
    ".autonovel/session-notes",
)

REQUIRED_SHARED_FILES = (
    "shared/world.md",
    "shared/characters.md",
    "shared/canon.md",
    "shared/events.md",
    "shared/timeline.md",
    "shared/MYSTERY.md",
    "shared/period_bans.txt",
    "shared/sources.bib",
    "shared/research/sources.yaml",
)


def run(series_root: Path, *, fix: bool = False) -> DoctorReport:
    report = DoctorReport()
    if not (series_root / SERIES_MARKER).is_file():
        report.problems.append(f"missing {SERIES_MARKER} in {series_root}")
        return report

    try:
        cfg = project_mod.load(series_root / SERIES_MARKER)
    except Exception as e:  # noqa: BLE001 — doctor must not crash on malformed yaml
        report.problems.append(f"project.yaml did not parse: {e}")
        return report

    problems = project_mod.validate(cfg)
    report.problems.extend(problems)

    series = SeriesLayout(root=series_root)

    for rel in REQUIRED_DIRS:
        p = series_root / rel
        if not p.exists():
            if fix:
                p.mkdir(parents=True, exist_ok=True)
                report.fixed.append(f"created {rel}/")
            else:
                report.problems.append(f"missing directory: {rel}/")

    for rel in REQUIRED_SHARED_FILES:
        if not (series_root / rel).is_file():
            report.warnings.append(f"missing shared file: {rel}")

    for b in cfg.books:
        book = series.book(b.name)
        if not book.root.is_dir():
            report.problems.append(f"book {b.name!r} listed in project.yaml but books/{b.name}/ is missing")
            continue
        for rel in ("seed.txt", "voice.md", "outline.md", "state.json"):
            if not (book.root / rel).is_file():
                report.warnings.append(f"books/{b.name}/{rel} missing")
        if not book.chapters.is_dir():
            if fix:
                book.chapters.mkdir(parents=True, exist_ok=True)
                report.fixed.append(f"created books/{b.name}/chapters/")
            else:
                report.problems.append(f"books/{b.name}/chapters/ missing")

    info = lock.read(series.lock_file)
    if info is not None and lock.is_stale(series.lock_file):
        report.warnings.append(
            f"stale lock from PID {info.pid} ({info.command}); `autonovel resume` to recover"
        )

    return report


def render(report: DoctorReport) -> str:
    out: list[str] = []
    if report.ok and not report.warnings:
        out.append("ok: no problems found")
    for p in report.problems:
        out.append(f"PROBLEM: {p}")
    for w in report.warnings:
        out.append(f"WARNING: {w}")
    for f in report.fixed:
        out.append(f"FIXED: {f}")
    return "\n".join(out)
