"""`autonovel` command-line entry point.

This CLI does housekeeping only — it never calls an LLM. Installing the
`/autonovel:*` runtime commands is handled by the `install` subcommand, which
is stubbed for PR 1 and implemented in PR 2.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .housekeeping import doctor, rollback, scaffold, status
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

    inst = sub.add_parser("install", help="(stub) Install /autonovel:* commands into a CLI runtime.")
    inst.add_argument("--only", default=None, choices=["claude", "codex", "gemini"])
    inst.set_defaults(func=_cmd_install_stub)

    uninst = sub.add_parser("uninstall", help="(stub) Uninstall /autonovel:* commands.")
    uninst.set_defaults(func=_cmd_install_stub)

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


def _cmd_install_stub(args: argparse.Namespace) -> int:
    print(
        "install/uninstall land in PR 2. For now, the autonovel housekeeping\n"
        "CLI (new-series, new-book, status, doctor, rollback, version) is all\n"
        "that's wired up."
    )
    return 0


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
