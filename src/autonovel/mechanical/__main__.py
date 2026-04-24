"""`python -m autonovel.mechanical <subcmd>` — deterministic helpers for commands.

Subcommands:
  slop <path>                 JSON slop-score of a prose file.
  period-bans <path> <bans>   JSON hits of bans list against a prose file.
  apply-cuts <chapter> <cuts> Apply a cuts.json file to a chapter in place.

All subcommands print a single JSON object to stdout. Commands invoke
this via the `bash` tool, read the JSON, and fold it into their own work.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .cuts import VALID_TYPES, apply_cuts
from .slop import period_ban_hits, slop_score


def _cmd_slop(args: argparse.Namespace) -> int:
    text = Path(args.path).read_text(encoding="utf-8")
    report = slop_score(text)
    json.dump(report.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_period_bans(args: argparse.Namespace) -> int:
    text = Path(args.path).read_text(encoding="utf-8")
    bans_text = Path(args.bans_path).read_text(encoding="utf-8")
    bans = [line for line in bans_text.splitlines() if line.strip() and not line.strip().startswith("#")]
    hits = period_ban_hits(text, bans)
    json.dump({"hits": hits, "total": sum(c for _, c in hits)}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_apply_cuts(args: argparse.Namespace) -> int:
    cuts_data = json.loads(Path(args.cuts_path).read_text(encoding="utf-8"))
    cuts = cuts_data.get("cuts", [])
    overall_fat = int(cuts_data.get("overall_fat_percentage", 0))
    types = set(args.types) if args.types else None
    if types:
        invalid = types - VALID_TYPES
        if invalid:
            print(f"error: unknown types {sorted(invalid)}", file=sys.stderr)
            return 2
    stats = apply_cuts(
        Path(args.chapter_path),
        cuts,
        types=types,
        min_fat=args.min_fat,
        overall_fat_percentage=overall_fat,
        dry_run=args.dry_run,
    )
    json.dump(stats.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if stats.failed == 0 else 3


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m autonovel.mechanical")
    sub = p.add_subparsers(dest="subcmd")

    s = sub.add_parser("slop", help="Score a prose file for AI-slop patterns.")
    s.add_argument("path")
    s.set_defaults(func=_cmd_slop)

    b = sub.add_parser("period-bans", help="Count banned-word hits.")
    b.add_argument("path")
    b.add_argument("bans_path")
    b.set_defaults(func=_cmd_period_bans)

    a = sub.add_parser("apply-cuts", help="Apply a cuts.json file to a chapter in place.")
    a.add_argument("chapter_path")
    a.add_argument("cuts_path")
    a.add_argument("--types", nargs="+", choices=sorted(VALID_TYPES))
    a.add_argument("--min-fat", type=int, default=0)
    a.add_argument("--dry-run", action="store_true")
    a.set_defaults(func=_cmd_apply_cuts)

    args = p.parse_args(argv)
    if not hasattr(args, "func"):
        p.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
