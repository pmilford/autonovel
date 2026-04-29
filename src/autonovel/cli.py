"""`autonovel` command-line entry point.

This CLI does housekeeping only — it never calls an LLM. The `install`
subcommand renders the generic `commands/*.md` files through a runtime-
specific adapter and writes them into the runtime's expected location.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .adapters import detect as detect_mod
from .adapters import installer as installer_mod
from .housekeeping import doctor, lifecycle, plates as plates_mod, rollback, scaffold, status, statusline as statusline_mod, statusline_setup, test_fixture
from .paths import SeriesNotFound, load_series


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="autonovel")
    p.add_argument("--version", action="version", version=f"autonovel {__version__}")
    sub = p.add_subparsers(dest="command")

    new_series = sub.add_parser("new-series", help="Create a new series folder.")
    new_series.add_argument("name")
    new_series.add_argument("--genre", default="general")
    new_series.add_argument("--dest", default=None, help="Parent directory (default: cwd)")
    new_series.set_defaults(func=_cmd_new_series)

    new_book = sub.add_parser("new-book", help="Add a book to a series.")
    new_book.add_argument("name")
    new_book.add_argument("--series", default=None, help="Series name or path; default: walk up from cwd")
    new_book.add_argument("--pov", default=None)
    new_book.add_argument(
        "--story-time-range",
        default=None,
        help="Inclusive year range, e.g. `1519-1523`",
    )
    new_book.set_defaults(func=_cmd_new_book)

    st = sub.add_parser("status", help="Show series status.")
    st.add_argument("--series", default=None)
    st.set_defaults(func=_cmd_status)

    doc = sub.add_parser("doctor", help="Sanity-check a series directory.")
    doc.add_argument("--series", default=None)
    doc.add_argument("--fix", action="store_true", help="Recreate missing directories")
    doc.set_defaults(func=_cmd_doctor)

    rb = sub.add_parser("rollback", help="List checkpoints and restore one.")
    rb.add_argument("--series", default=None)
    rb.add_argument("--to", default=None, help="Checkpoint timestamp (default: interactive pick)")
    rb.add_argument("--list", action="store_true", help="List only; do not restore")
    rb.set_defaults(func=_cmd_rollback)

    ver = sub.add_parser("version", help="Print version and exit.")
    ver.set_defaults(func=lambda _args: (print(__version__), 0)[1])

    inst = sub.add_parser("install", help="Install /autonovel:* commands into a CLI runtime.")
    inst.add_argument("--only", default=None, choices=["claude", "codex", "gemini"])
    inst.add_argument("--path", default=None,
                      help="Override the install root (default: the adapter's default).")
    inst.set_defaults(func=_cmd_install)

    uninst = sub.add_parser("uninstall", help="Uninstall /autonovel:* commands.")
    uninst.add_argument("--only", default=None, choices=["claude", "codex", "gemini"])
    uninst.add_argument("--path", default=None)
    uninst.set_defaults(func=_cmd_uninstall)

    ai = sub.add_parser(
        "art-import",
        help="Import a user-supplied image as a typeset plate or chapter ornament.",
    )
    ai.add_argument("--file", required=True, help="Source image path (PNG/JPG/PDF/SVG/TIFF).")
    ai.add_argument("--book", default=None, help="Book short-name (defaults to inferred book).")
    ai.add_argument("--chapter", type=int, required=True, help="Anchor chapter (1-indexed).")
    ai.add_argument("--as", dest="kind", default="plate", choices=["plate", "ornament"],
                    help="`plate`: full-page captioned image (historical maps, paintings). "
                         "`ornament`: replaces the AI-generated chapter ornament.")
    ai.add_argument("--placement", default="before-chapter",
                    choices=["before-chapter", "chapter-start", "after-chapter"],
                    help="Where the plate goes relative to its chapter (plate mode only).")
    ai.add_argument("--slug", default=None, help="Slug for the registered plate (default: derived from filename).")
    ai.add_argument("--caption", default="", help="Italic caption under the plate (e.g. \"Map of Venice, c. 1500\").")
    ai.add_argument("--attribution", default="", help="Small-print credit line under the caption.")
    ai.add_argument("--force", action="store_true", help="Overwrite an existing import with the same slug or chapter.")
    ai.set_defaults(func=_cmd_art_import)

    sl = sub.add_parser("statusline", help="Print one-line status for Claude Code's status bar.")
    sl.set_defaults(func=_cmd_statusline)

    sl_setup = sub.add_parser("statusline-setup",
                              help="Wire the statusline + permissions into a series's .claude/settings.json.")
    sl_setup.add_argument("--series", default=None,
                          help="Path to the series root (default: walk up from cwd).")
    sl_setup.add_argument("--force", action="store_true",
                          help="Overwrite an existing statusLine config and skip the malformed-file guard.")
    sl_setup.set_defaults(func=_cmd_statusline_setup)

    tf = sub.add_parser("test-fixture", help="Manage genre-fixture series under tests/fixtures/.")
    tf_sub = tf.add_subparsers(dest="action", required=True)

    tf_new = tf_sub.add_parser("new", help="Scaffold a new genre fixture + smoke test.")
    tf_new.add_argument("name", help="Short fixture name, e.g. `mystery`")
    tf_new.add_argument("--genre", default=None, help="Genre label (default: same as name)")
    tf_new.add_argument("--book-name", default="book-one")
    tf_new.add_argument("--repo-root", default=None,
                        help="Override repo root (default: walk up to find tests/fixtures/)")
    tf_new.set_defaults(func=_cmd_fixture_new)

    tf_list = tf_sub.add_parser("list", help="List available fixtures.")
    tf_list.add_argument("--repo-root", default=None)
    tf_list.set_defaults(func=_cmd_fixture_list)

    tf_run = tf_sub.add_parser("run", help="Run one fixture's smoke test via pytest.")
    tf_run.add_argument("name")
    tf_run.add_argument("--repo-root", default=None)
    tf_run.add_argument("pytest_args", nargs=argparse.REMAINDER,
                        help="Extra args passed verbatim to pytest after `--`.")
    tf_run.set_defaults(func=_cmd_fixture_run)

    mech = sub.add_parser(
        "mechanical",
        help="Run a deterministic mechanical helper (slop, period-bans, apply-cuts, spine-width, audio-*, build-tex).",
        description=(
            "Forwards the rest of $ARGV to `autonovel.mechanical`'s CLI. "
            "Use `autonovel mechanical <subcmd> --help` for per-subcommand "
            "help. This is the entry point command-body authors should "
            "invoke from the `bash` tool — it survives pipx install (which "
            "isolates the `autonovel` Python module so `python -m "
            "autonovel.mechanical` does not work outside the pipx venv)."
        ),
        add_help=False,  # let mechanical.main handle --help itself
    )
    mech.add_argument("mech_args", nargs=argparse.REMAINDER)
    mech.set_defaults(func=_cmd_mechanical)

    _tc = sub.add_parser("_tail-chapter", help=argparse.SUPPRESS)
    _tc.add_argument("--book", required=True)
    _tc.add_argument("--chapter", type=int, required=True)
    _tc.add_argument("--words", type=int, default=1000,
                     help="Number of trailing words to print (default 1000).")
    _tc.set_defaults(func=_cmd_tail_chapter)

    _begin = sub.add_parser("_begin", help=argparse.SUPPRESS)
    _begin.add_argument("--command", required=True)
    _begin.add_argument("--args", default="")
    _begin.add_argument("--runtime", default="claude")
    _begin.set_defaults(func=_cmd_begin)

    _end = sub.add_parser("_end", help=argparse.SUPPRESS)
    _end.add_argument("--command", required=True)
    _end.add_argument("--args", default="")
    _end.add_argument("--status", default="ok")
    _end.add_argument("--wrote", action="append", default=[])
    _end.set_defaults(func=_cmd_end)

    _na = sub.add_parser("_next-actions", help=argparse.SUPPRESS)
    _na.add_argument("--book", default=None,
                     help="Restrict to one book; default: every book in project.yaml.")
    _na.add_argument("--format", choices=("human", "json"), default="human",
                     help="Output format (default: human markdown).")
    _na.set_defaults(func=_cmd_next_actions)

    _pc = sub.add_parser("_promote-canon", help=argparse.SUPPRESS)
    _pc.add_argument("--book", default=None,
                     help="Book name to promote; default: every book in project.yaml.")
    _pc.add_argument("--no-lock", action="store_true",
                     help="Do not check in-progress.lock — for use inside a sweep "
                          "subagent whose parent already holds the lock. Without this "
                          "flag the helper refuses to run when a lock is held.")
    _pc.add_argument("--dry-run", action="store_true",
                     help="Print what would be promoted without writing.")
    _pc.add_argument("--format", choices=("json", "human"), default="human",
                     help="Output format (default: human).")
    _pc.set_defaults(func=_cmd_promote_canon)

    return p


def _cmd_new_series(args: argparse.Namespace) -> int:
    parent = Path(args.dest).resolve() if args.dest else Path.cwd()
    root = parent / args.name
    try:
        result = scaffold.new_series(root, series_name=args.name, genre=args.genre)
    except scaffold.ScaffoldError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    rel = result.series.root
    print(f"Created {rel}/")
    print(f"Next: cd {rel.name} && autonovel new-book <name>")
    return 0


def _cmd_new_book(args: argparse.Namespace) -> int:
    try:
        series = _resolve_series(args.series)
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    story_time_range: list[int] | None = None
    if args.story_time_range:
        try:
            start_s, end_s = args.story_time_range.split("-", 1)
            story_time_range = [int(start_s), int(end_s)]
        except ValueError:
            print(f"error: --story-time-range must be `START-END` e.g. `1519-1523`", file=sys.stderr)
            return 2
    try:
        result = scaffold.new_book(
            series, book_name=args.name, pov=args.pov, story_time_range=story_time_range
        )
    except scaffold.ScaffoldError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"Created {result.book_root.relative_to(series.root.parent)}/")
    print(f"Edit {result.book_root.name}/seed.txt, then open the series in your runtime.")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    try:
        series = _resolve_series(args.series)
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    report = status.gather(series)
    print(status.render(report))
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    try:
        series = _resolve_series(args.series)
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    report = doctor.run(series.root, fix=args.fix)
    print(doctor.render(report))
    return 0 if report.ok else 1


def _cmd_rollback(args: argparse.Namespace) -> int:
    try:
        series = _resolve_series(args.series)
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    cps = rollback.list_recent(series)
    if args.list or args.to is None:
        print(rollback.render_list(cps))
        if args.list:
            return 0
        if not cps:
            return 0
        # Interactive pick
        print("")
        try:
            choice = input(f"Roll back to which? [1-{len(cps)}, 0=cancel]: ").strip()
        except EOFError:
            print("(no input; cancelled)")
            return 0
        if not choice or choice == "0":
            print("cancelled")
            return 0
        try:
            idx = int(choice)
        except ValueError:
            print("error: not a number", file=sys.stderr)
            return 2
        if not 1 <= idx <= len(cps):
            print("error: out of range", file=sys.stderr)
            return 2
        target = cps[idx - 1]
    else:
        match = [c for c in cps if c.timestamp == args.to]
        if not match:
            print(f"error: no checkpoint with timestamp {args.to}", file=sys.stderr)
            return 2
        target = match[0]

    result = rollback.rollback_to(series, target)
    print(f"Restored from {result.restored_from} (new checkpoint {result.new_checkpoint})")
    for f in result.files_restored:
        print(f"  → {f}")
    return 0


def _cmd_install(args: argparse.Namespace) -> int:
    adapters = _select_adapters(args.only)
    if not adapters:
        print(
            "error: no known runtimes found on $PATH. Install one of:\n"
            "  - Claude Code (`claude`)\n"
            "  - OpenAI Codex (`codex`)\n"
            "  - Gemini CLI (`gemini`)\n"
            "Or pass `--only <runtime> --path <dir>` to install anyway.",
            file=sys.stderr,
        )
        return 2
    path = Path(args.path).resolve() if args.path else None
    for adapter in adapters:
        result = installer_mod.install(adapter, install_root=path)
        print(f"installed [{result.adapter_name}] → {result.install_root}")
        for w in result.written:
            print(f"  + {w.relative_to(result.install_root)}")
    return 0


def _cmd_uninstall(args: argparse.Namespace) -> int:
    adapters = _select_adapters(args.only)
    if not adapters:
        print("error: no runtime selected; pass --only <runtime>", file=sys.stderr)
        return 2
    path = Path(args.path).resolve() if args.path else None
    for adapter in adapters:
        result = installer_mod.uninstall(adapter, install_root=path)
        print(f"uninstalled [{result.adapter_name}] from {result.install_root}")
        for r in result.removed:
            print(f"  - {r.name}")
    return 0


def _cmd_art_import(args: argparse.Namespace) -> int:
    try:
        series = load_series()
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    book_name = args.book
    if book_name is None:
        # Walk the same inference path /autonovel:* commands use.
        from .housekeeping.lifecycle import _infer_book
        ctx = _infer_book({}, series)
        book_name = ctx.get("book")
    if book_name is None:
        print("error: --book not provided and could not be inferred. "
              "Pass --book <name> or run from a series with exactly one book.",
              file=sys.stderr)
        return 2
    book_root = series.books / book_name
    if not book_root.is_dir():
        print(f"error: book {book_name!r} not found at {book_root}", file=sys.stderr)
        return 2
    source = Path(args.file).expanduser().resolve()
    try:
        result = plates_mod.import_image(
            book_root, source,
            chapter=args.chapter,
            kind=args.kind,
            placement=args.placement,
            slug=args.slug,
            caption=args.caption,
            attribution=args.attribution,
            force=args.force,
        )
    except plates_mod.ImportError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    rel = result.installed_path.relative_to(series.root)
    verb = "Replaced" if result.overwrote else "Imported"
    print(f"{verb} {result.kind} → {rel}")
    if result.plate is not None:
        print(f"  slug: {result.plate.slug}")
        print(f"  placement: {result.plate.placement} (chapter {result.plate.chapter})")
        if result.plate.caption:
            print(f"  caption: {result.plate.caption}")
        if result.plate.attribution:
            print(f"  attribution: {result.plate.attribution}")
        manifest = book_root / "typeset" / "plates.yaml"
        print(f"  manifest: {manifest.relative_to(series.root)}")
    print("")
    print(f"Next: run /autonovel:typeset --book {book_name} to rebuild the PDF.")
    return 0


def _cmd_statusline(args: argparse.Namespace) -> int:
    return statusline_mod.main()


def _cmd_statusline_setup(args: argparse.Namespace) -> int:
    try:
        series = _resolve_series(args.series)
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    try:
        result = statusline_setup.setup(series, force=args.force)
    except statusline_setup.SetupError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    rel = result.settings_path
    verb = "Created" if result.created else "Updated"
    print(f"{verb} {rel}")
    if result.statusline_added:
        print("  + statusLine: autonovel statusline")
    else:
        print("  · statusLine already configured (use --force to overwrite)")
    if result.permissions_added:
        print(f"  + {result.permissions_added} permissions added "
              f"(scoped Bash + Read/Write/Task/WebSearch/WebFetch)")
    if result.permissions_already_present:
        print(f"  · {result.permissions_already_present} already present")
    print("")
    print("Next: restart Claude Code to pick up the new settings. After")
    print("that, autonovel commands stop prompting for tool approval, and")
    print("the status bar shows series · book · phase · lock | model · "
          "context% · cost.")
    return 0


def _cmd_fixture_new(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    try:
        result = test_fixture.new_fixture(
            args.name,
            repo_root=repo_root,
            genre=args.genre,
            book_name=args.book_name,
        )
    except test_fixture.FixtureError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"Created fixture tiny-series-{result.fixture.name}/")
    print(f"  fixture:    {result.fixture.path}")
    print(f"  smoke test: {result.fixture.smoke_test_path}")
    print("")
    print(f"Next: edit the seed files, then:")
    print(f"  autonovel test-fixture run {args.name}")
    return 0


def _cmd_fixture_list(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    try:
        fixtures = test_fixture.list_fixtures(repo_root=repo_root)
    except test_fixture.FixtureError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(test_fixture.render_list(fixtures))
    return 0


def _cmd_fixture_run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    extra: list[str] = list(args.pytest_args or [])
    if extra and extra[0] == "--":
        extra = extra[1:]
    try:
        rc = test_fixture.run_fixture(
            args.name,
            repo_root=repo_root,
            extra_pytest_args=extra,
        )
    except test_fixture.FixtureError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return rc


def _cmd_mechanical(args: argparse.Namespace) -> int:
    """Dispatch to autonovel.mechanical's CLI. The whole point is that
    `autonovel` is on $PATH after pipx install, while `python -m
    autonovel.mechanical` only works when `autonovel` is importable
    from the system Python — which is *not* true under pipx isolation.
    Command bodies that previously shelled to `python -m
    autonovel.mechanical` should now shell to `autonovel mechanical`."""
    from .mechanical.__main__ import main as mech_main
    return mech_main(args.mech_args)


def _cmd_tail_chapter(args: argparse.Namespace) -> int:
    """Print the last N words of a chapter file. Replaces an LLM-side
    `Read offset/limit` hack that stalled on author-testing 2026-04-25
    when the LLM's chosen line range overran EOF (e.g. asking for lines
    88-147 of a 146-line chapter, then retrying when fewer lines came
    back than expected). Deterministic, single-shot, no retries."""
    try:
        series = load_series()
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    book_root = series.books / args.book
    chapter_file = book_root / "chapters" / f"ch_{args.chapter:02d}.md"
    if not chapter_file.is_file():
        # Soft failure: prior chapter not drafted is a normal state for
        # chapter 1. Exit zero with no output so the caller falls back
        # to "no prior chapter context".
        return 0
    try:
        text = chapter_file.read_text(encoding="utf-8")
    except OSError as e:
        print(f"error: read failed: {e}", file=sys.stderr)
        return 1
    if not text.strip():
        return 0
    # Strip a leading YAML frontmatter block so we don't bleed
    # `book: foo\nchapter: 2\n...` into the continuity quote.
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5:]
    words = text.split()
    n = max(1, args.words)
    tail = words[-n:] if len(words) > n else words
    sys.stdout.write(" ".join(tail))
    sys.stdout.write("\n")
    return 0


def _cmd_begin(args: argparse.Namespace) -> int:
    try:
        series = load_series()
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    try:
        result = lifecycle.begin(args.command, args.args, runtime=args.runtime, series=series)
    except lifecycle.BeginError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001 — surface a clean message for the model
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    print(f"_begin ok: locked as PID {result.lock_info.pid}; "
          f"checkpoint {result.checkpoint.timestamp if result.checkpoint else '(none)'}")
    if result.resolved_book is not None:
        suffix = " (inferred from last-action / single-book project)" if result.book_inferred else ""
        print(f"book: {result.resolved_book}{suffix}")
    if result.abandoned_lock is not None:
        ab = result.abandoned_lock
        print(
            f"WARNING: previous run of /{ab.command} (PID {ab.pid}, started "
            f"{ab.started_at}) ended without running its postamble. "
            f"Lock taken over. Run `/autonovel:resume` if you want to "
            f"inspect the partial state from that run."
        )
    return 0


def _cmd_end(args: argparse.Namespace) -> int:
    try:
        series = load_series()
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    result = lifecycle.end(
        args.command, args.args, status=args.status, wrote=list(args.wrote), series=series
    )
    if args.status == "ok" and result.footer:
        print(result.footer)
    else:
        print(f"_end: status={args.status}; log updated")
    return 0


def _cmd_next_actions(args: argparse.Namespace) -> int:
    """Hidden subcommand: enumerate state-aware next actions for
    /autonovel:next. Reads filesystem state directly; never replays
    last-action.json (that's a separate input, surfaced as the
    canonical pipeline action at the bottom of the output)."""
    import json as _json
    from .housekeeping import next_actions
    try:
        series = load_series()
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    actions = next_actions.enumerate_actions(series, book=args.book)
    canonical = next_actions.canonical_pipeline_action(series, book=args.book)
    if args.format == "json":
        payload = {
            "actions": [a.to_dict() for a in actions],
            "canonical": canonical.to_dict() if canonical else None,
        }
        _json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(next_actions.render_human(actions, canonical=canonical))
    return 0


def _cmd_promote_canon(args: argparse.Namespace) -> int:
    """Hidden subcommand: promote pending canon entries into
    shared/canon.md atomically. Slash-command body and sweep
    sub-agents both call this; --no-lock lets sweep sub-agents
    bypass the in-progress lock that the parent already holds."""
    import json as _json
    from . import lock as lock_mod, promote_canon as pc
    try:
        series = load_series()
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not args.no_lock:
        # Refuse if the lock is held by another process, mirroring
        # what `_begin` would have done at the slash-command's
        # preamble. With --no-lock the caller is asserting "I know
        # the parent holds the lock; just do the file ops."
        info = lock_mod.read(series.lock_file)
        if info is not None and not lock_mod.is_stale(series.lock_file):
            print(
                f"error: another autonovel command is in progress "
                f"(PID {info.pid}, command {info.command!r}). "
                f"Pass --no-lock if invoking from inside that command's sub-agent.",
                file=sys.stderr,
            )
            return 3
    try:
        report = pc.promote(
            series,
            book=args.book,
            dry_run=args.dry_run,
            no_lock=args.no_lock,
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 4
    if args.format == "json":
        _json.dump(report.to_dict(), sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        for br in report.books:
            print(f"book: {br.book}")
            print(f"  promoted:    {br.promoted}")
            print(f"  duplicates:  {br.duplicates}")
            print(f"  conflicts:   {br.conflicts}")
            print(f"  supersedures: {br.supersedures}")
            for sup in br.supersedure_records:
                print(f"  superseded:  `{sup.superseded_line}` ← `{sup.new_entry.fact_text}` ({sup.rationale})")
            for cr in br.conflict_records:
                print(f"  conflict:    `{cr.candidate.fact_text}` vs `{cr.existing_line}` in {cr.existing_file}")
        if args.dry_run:
            print("(dry-run — no files written)")
    return 0


def _select_adapters(only: str | None):
    if only is not None:
        try:
            return [installer_mod.load_adapter(only)]
        except KeyError as e:
            print(f"error: {e}", file=sys.stderr)
            return []
    return [dr.adapter for dr in detect_mod.detect_all() if dr.available]


def _resolve_series(arg: str | None):
    from .paths import SeriesLayout
    if arg is not None:
        p = Path(arg)
        if p.is_dir() and (p / "project.yaml").is_file():
            return SeriesLayout(root=p.resolve())
        here = Path.cwd() / arg
        if here.is_dir() and (here / "project.yaml").is_file():
            return SeriesLayout(root=here.resolve())
    return load_series()


if __name__ == "__main__":
    raise SystemExit(main())
