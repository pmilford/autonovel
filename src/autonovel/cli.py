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
from .housekeeping import doctor, lifecycle, rollback, scaffold, status, test_fixture
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
