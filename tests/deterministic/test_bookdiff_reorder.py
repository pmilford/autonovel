"""A reorder's change page pairs each moved chapter with itself, by title
(2026-10-28: a swap of chapters 10 and 11 diffed each against the other)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from autonovel.mechanical.bookdiff import build_diff


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_moved_chapters_pair_by_title(tmp_path: Path) -> None:
    root = tmp_path
    (root / "project.yaml").write_text("series_name: s\nbooks:\n- name: bk\n", encoding="utf-8")
    ch = root / "books" / "bk" / "chapters"
    ch.mkdir(parents=True)
    for n, t in ((1, "One"), (2, "Two"), (3, "Three")):
        (ch / f"ch_{n:02d}.md").write_text(f"---\ntitle: {t}\n---\n\nText of {t}, first line.\n\nSecond line.\n",
                                            encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "-c", "user.email=a@b", "-c", "user.name=a", "add", "-A")
    _git(root, "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qm", "v1")
    _git(root, "tag", "v1")
    a, b = (ch / "ch_02.md").read_text(), (ch / "ch_03.md").read_text()
    (ch / "ch_02.md").write_text(b.replace("Second line.", "Second line, changed."), encoding="utf-8")
    (ch / "ch_03.md").write_text(a, encoding="utf-8")
    rep = build_diff(root, "bk", from_spec="v1", foundation=False)
    labels = {f.chapter: (f.label, f.status) for f in rep.chapters}
    assert labels[2][0] == "Chapter 2 (was 3)" and labels[3][0] == "Chapter 3 (was 2)"
    assert labels[3][1] == "unchanged"   # the moved chapter is the same text
    assert labels[2][1] == "changed"
