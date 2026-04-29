"""`python -m autonovel.mechanical <subcmd>` — deterministic helpers for commands.

Subcommands:
  slop <path>                      JSON slop-score of a prose file.
  period-bans <path> <bans>        JSON hits of bans list against a prose file.
  apply-cuts <chapter> <cuts>      Apply a cuts.json file to a chapter in place.
  spine-width --pages N [...]      Cover canvas spec (spine + canvas + px).
  audio-validate <script> [<v>]    Validate a parsed audiobook script.
  audio-chunk <script> <voices>    Pack segments into TTS-budget chunks.
  audio-marks <rows> [--pause S]   Compute cumulative chapter marks.
  scenes <path> [--full]           Split a chapter into scenes by *** / --- breaks.
  motifs <book> [--format]         Per-chapter motif density (reads books/<book>/motifs.md).
  chapter-summary <book> [--format] One-line-per-chapter overview (date/POV/score/cast/plot).
  build-epub-md <chapters_dir>     Concatenate ch_NN.md → one ePub-ready markdown.
  build-tex <chapters_dir> [--art] Build chapters_content.tex from md.
  build-front-matter-tex <book>    Build front_matter.tex from preface.md + introduction.md.
  render-novel-tex <template> [-s KEY=V ...]  Substitute @KEY@ placeholders (safer than sed).
  typeset-filename <slug> <kind>   Print canonical timestamped + latest filenames.

All subcommands print a single JSON object to stdout. Commands invoke
this via the `bash` tool, read the JSON, and fold it into their own work.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .audio import (
    chapter_marks,
    chunk_segments,
    format_chapter_marks_mp4chaps,
    load_script,
    validate_script,
)
from .chapter_summary import render_markdown_table, summarize_chapters
from .cliches import cliche_density, cliche_hits
from .cuts import VALID_TYPES, apply_cuts
from .epub import build_epub_md
from .front_matter import build_front_matter_tex
from .latex import build_chapters_tex
from .dashboard import (
    build_dashboard,
    render_markdown as render_dashboard_md,
)
from .dialogue import (
    build_report as build_dialogue_report,
    render_markdown as render_dialogue_md,
)
from .entity_track import (
    build_report as build_entity_report,
    render_markdown as render_entity_md,
)
from .period_register import (
    build_report as build_period_report,
    render_markdown as render_period_md,
)
from .pov_bleed import (
    build_report as build_pov_bleed_report,
    render_markdown as render_pov_bleed_md,
)
from .series_arc import (
    build_report as build_series_arc_report,
    render_markdown as render_series_arc_md,
)
from .show_dont_tell import (
    build_report as build_show_dont_tell_report,
    render_markdown as render_show_dont_tell_md,
)
from .motifs import build_report as build_motif_report, render_markdown as render_motif_md
from .summary_query import (
    QueryError,
    filter_rows as summary_filter_rows,
    render_markdown as render_summary_query_md,
)
from .scenes import split_scenes
from .sensory import channel_balance
from .slop import period_ban_hits, slop_score
from .spine import cover_spec
from .typeset import latest_filename, output_filename, render_novel_tex


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


def _cmd_spine_width(args: argparse.Namespace) -> int:
    spec = cover_spec(
        trim_w=args.trim_w,
        trim_h=args.trim_h,
        pages=args.pages,
        paper=args.paper,
        bleed=args.bleed,
        dpi=args.dpi,
        spine_override=args.spine_override,
    )
    json.dump(spec.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_audio_validate(args: argparse.Namespace) -> int:
    script = load_script(Path(args.script_path))
    voices = None
    if args.voices_path:
        voices = json.loads(Path(args.voices_path).read_text(encoding="utf-8"))
    problems = validate_script(script, voices)
    json.dump(problems.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if problems.ok else 4


def _cmd_audio_chunk(args: argparse.Namespace) -> int:
    script = load_script(Path(args.script_path))
    voices = json.loads(Path(args.voices_path).read_text(encoding="utf-8"))
    chunks = chunk_segments(
        script["segments"],
        voices,
        max_chars=args.max_chars,
    )
    json.dump(
        {
            "chapter": script.get("chapter"),
            "total_chunks": len(chunks),
            "total_chars": sum(c.chars for c in chunks),
            "chunks": [c.to_dict() for c in chunks],
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


def _cmd_audio_marks(args: argparse.Namespace) -> int:
    rows_data = json.loads(Path(args.rows_path).read_text(encoding="utf-8"))
    rows = [(int(r["chapter"]), str(r["title"]), float(r["duration"])) for r in rows_data]
    marks = chapter_marks(rows, pause=args.pause)
    payload: dict = {"marks": [m.to_dict() for m in marks]}
    if args.format == "ffmetadata":
        payload["ffmetadata"] = format_chapter_marks_mp4chaps(marks)
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_cliches(args: argparse.Namespace) -> int:
    text = Path(args.path).read_text(encoding="utf-8")
    hits = cliche_hits(text)
    payload = {
        "hits": [h.to_dict() for h in hits],
        "total": sum(h.count for h in hits),
        "density_per_1000_words": round(cliche_density(text), 3),
        "word_count": len(text.split()),
    }
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_sensory(args: argparse.Namespace) -> int:
    text = Path(args.path).read_text(encoding="utf-8")
    report = channel_balance(text, dominance_threshold=args.dominance_threshold)
    json.dump(report.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_scenes(args: argparse.Namespace) -> int:
    text = Path(args.path).read_text(encoding="utf-8")
    scenes = split_scenes(text)
    payload = {
        "path": args.path,
        "scene_count": len(scenes),
        "total_words": sum(s["word_count"] for s in scenes),
        # `text` field is heavy and the LLM judge in evaluate.md
        # already has the chapter file open; emit only the lightweight
        # index per scene by default. `--full` opts back in to the prose.
        "scenes": [
            ({k: v for k, v in s.items() if k != "text"} if not args.full else s)
            for s in scenes
        ],
    }
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_dialogue(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    report = build_dialogue_report(book_root)
    if args.format == "json":
        json.dump({"book_root": str(book_root), **report.to_dict()},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_dialogue_md(report, book=book_root.name,
                                              show_hits=not args.summary_only))
    return 0


def _cmd_period_register(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    series_root = Path(args.series_root) if args.series_root else None
    report = build_period_report(book_root, series_root=series_root)
    if args.format == "json":
        json.dump({"book_root": str(book_root), **report.to_dict()},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_period_md(report, book=book_root.name,
                                            show_hits=not args.summary_only))
    return 0


def _cmd_show_dont_tell(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    report = build_show_dont_tell_report(book_root)
    if args.format == "json":
        json.dump({"book_root": str(book_root), **report.to_dict()},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_show_dont_tell_md(
            report, book=book_root.name,
            show_hits=not args.summary_only,
        ))
    return 0


def _cmd_series_arc(args: argparse.Namespace) -> int:
    series_root = Path(args.series_root)
    report = build_series_arc_report(series_root, threshold=args.threshold)
    if args.format == "json":
        json.dump(report.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_series_arc_md(report))
    return 0


def _cmd_pov_bleed(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    series_root = Path(args.series_root) if args.series_root else None
    report = build_pov_bleed_report(book_root, series_root=series_root)
    if args.format == "json":
        json.dump({"book_root": str(book_root), **report.to_dict()},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_pov_bleed_md(report, book=book_root.name,
                                               show_hits=not args.summary_only))
    return 0


def _cmd_summary_query(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    rows = summarize_chapters(book_root)
    try:
        filtered = summary_filter_rows(rows, args.where or "")
    except QueryError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.format == "json":
        json.dump(
            {
                "book_root": str(book_root),
                "expr": args.where,
                "matched": len(filtered),
                "rows": [
                    {
                        "chapter": r.chapter,
                        "pov": r.pov,
                        "story_time": r.story_time,
                        "score": r.score,
                        "word_count": r.word_count,
                        "location": r.location,
                        "plot": r.plot,
                        "cast": r.cast,
                        "status": r.status,
                    } for r in filtered
                ],
            },
            sys.stdout, indent=2,
        )
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_summary_query_md(
            filtered, expr=args.where, book=book_root.name,
        ))
    return 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    report = build_dashboard(book_root, threshold=args.threshold)
    if args.format == "json":
        json.dump(report.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_dashboard_md(report, threshold=args.threshold))
    return 0


def _cmd_entity_track(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    series_root = Path(args.series_root) if args.series_root else None
    report = build_entity_report(book_root, series_root=series_root)
    if args.format == "json":
        json.dump({"book_root": str(book_root), **report.to_dict()},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_entity_md(report, book=book_root.name))
    return 0


def _cmd_motifs(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    report = build_motif_report(book_root)
    if args.format == "json":
        json.dump({"book_root": str(book_root), **report.to_dict()},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_motif_md(report, book=book_root.name))
    return 0


def _cmd_chapter_summary(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    rows = summarize_chapters(book_root)
    if args.format == "json":
        json.dump(
            {"book_root": str(book_root),
             "chapter_count": len(rows),
             "rows": [r.to_dict() for r in rows]},
            sys.stdout, indent=2,
        )
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown_table(rows))
    return 0


def _cmd_build_front_matter_tex(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    output = Path(args.output) if args.output else None
    content, titles = build_front_matter_tex(book_root, output=output)
    json.dump(
        {
            "sections": titles,
            "bytes": len(content),
            "output": str(output) if output else None,
            "wrote": output is not None and content != "",
        },
        sys.stdout, indent=2,
    )
    sys.stdout.write("\n")
    return 0


def _cmd_render_novel_tex(args: argparse.Namespace) -> int:
    template = Path(args.template).read_text(encoding="utf-8")
    subs: dict[str, str] = {}
    for kv in (args.substitutions or []):
        if "=" not in kv:
            print(f"error: substitutions must be KEY=VALUE; got {kv!r}", file=sys.stderr)
            return 2
        key, _, value = kv.partition("=")
        subs[key] = value
    rendered = render_novel_tex(template, subs)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    json.dump({"output": str(output), "bytes": len(rendered),
               "substitutions_applied": sorted(subs.keys())},
              sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_typeset_filename(args: argparse.Namespace) -> int:
    """Print the canonical timestamped filename. Used by typeset.md
    so the bash side doesn't have to do its own date math."""
    name = output_filename(args.slug, args.kind)
    latest = latest_filename(args.slug, args.kind)
    json.dump({"timestamped": name, "latest": latest},
              sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_build_epub_md(args: argparse.Namespace) -> int:
    chapters_dir = Path(args.chapters_dir)
    output = Path(args.output) if args.output else None
    content, reports = build_epub_md(chapters_dir, output=output)
    json.dump(
        {
            "chapters": len(reports),
            "bytes": len(content),
            "output": str(output) if output else None,
            "reports": [
                {
                    "chapter": r.chapter,
                    "title": r.title,
                    "word_count": r.word_count,
                }
                for r in reports
            ],
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


def _cmd_build_tex(args: argparse.Namespace) -> int:
    chapters_dir = Path(args.chapters_dir)
    art_dir = Path(args.art_dir) if args.art_dir else None
    output = Path(args.output) if args.output else None
    plates_manifest = Path(args.plates_manifest) if args.plates_manifest else None
    plates_root = Path(args.plates_root) if args.plates_root else None
    content, reports = build_chapters_tex(
        chapters_dir,
        art_dir=art_dir,
        output=output,
        plates_manifest=plates_manifest,
        plates_root=plates_root,
    )
    json.dump(
        {
            "chapters": len(reports),
            "bytes": len(content),
            "output": str(output) if output else None,
            "reports": [
                {
                    "chapter": r.chapter,
                    "title": r.title,
                    "ornament": str(r.ornament) if r.ornament else None,
                }
                for r in reports
            ],
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


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

    sw = sub.add_parser("spine-width", help="Cover spine + canvas calculator.")
    sw.add_argument("--trim-w", dest="trim_w", type=float, default=5.5)
    sw.add_argument("--trim-h", dest="trim_h", type=float, default=8.5)
    sw.add_argument("--pages", type=int, required=True)
    sw.add_argument("--paper", default="cream")
    sw.add_argument("--bleed", type=float, default=0.125)
    sw.add_argument("--dpi", type=int, default=300)
    sw.add_argument("--spine-override", dest="spine_override", type=float, default=None)
    sw.set_defaults(func=_cmd_spine_width)

    av = sub.add_parser("audio-validate", help="Validate a chapter script JSON.")
    av.add_argument("script_path")
    av.add_argument("voices_path", nargs="?", default=None)
    av.set_defaults(func=_cmd_audio_validate)

    ac = sub.add_parser("audio-chunk", help="Pack script segments into TTS-budget chunks.")
    ac.add_argument("script_path")
    ac.add_argument("voices_path")
    ac.add_argument("--max-chars", dest="max_chars", type=int, default=4500)
    ac.set_defaults(func=_cmd_audio_chunk)

    am = sub.add_parser("audio-marks", help="Compute chapter timestamps.")
    am.add_argument("rows_path")
    am.add_argument("--pause", type=float, default=2.0)
    am.add_argument("--format", choices=["json", "ffmetadata"], default="json")
    am.set_defaults(func=_cmd_audio_marks)

    cl = sub.add_parser("cliches", help="Bigram-cliche scan; complements slop.")
    cl.add_argument("path")
    cl.set_defaults(func=_cmd_cliches)

    sens = sub.add_parser("sensory", help="Per-channel keyword balance (visual/auditory/...).")
    sens.add_argument("path")
    sens.add_argument("--dominance-threshold", type=float, default=0.70,
                      help="Single-channel fraction above which the channel is flagged dominant (default 0.70).")
    sens.set_defaults(func=_cmd_sensory)

    sc = sub.add_parser("scenes", help="Split a chapter into scenes by *** / --- breaks.")
    sc.add_argument("path")
    sc.add_argument("--full", action="store_true",
                    help="Include each scene's full prose in the output (heavy; default off).")
    sc.set_defaults(func=_cmd_scenes)

    mt = sub.add_parser("motifs",
                        help="Per-chapter motif density tracker (reads books/<book>/motifs.md).")
    mt.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    mt.add_argument("--format", choices=("markdown", "json"), default="markdown",
                    help="Output format (default: markdown table).")
    mt.set_defaults(func=_cmd_motifs)

    dlg = sub.add_parser("dialogue",
                          help="Per-chapter dialogue-mechanics linter (adverb tags, said-bookisms, stutters).")
    dlg.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    dlg.add_argument("--format", choices=("markdown", "json"), default="markdown")
    dlg.add_argument("--summary-only", action="store_true",
                      help="Skip the per-hit lines block; emit only the per-chapter table.")
    dlg.set_defaults(func=_cmd_dialogue)

    pr = sub.add_parser("period-register",
                         help="Per-chapter period-bans hits across the whole book.")
    pr.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    pr.add_argument("--series-root", default=None,
                     help="Series root for shared/period_bans.txt (default: book_root.parent.parent).")
    pr.add_argument("--format", choices=("markdown", "json"), default="markdown")
    pr.add_argument("--summary-only", action="store_true")
    pr.set_defaults(func=_cmd_period_register)

    sdt = sub.add_parser("show-dont-tell",
                          help="Per-chapter pre-flight scanner for tell-candidate lines.")
    sdt.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    sdt.add_argument("--format", choices=("markdown", "json"), default="markdown")
    sdt.add_argument("--summary-only", action="store_true",
                      help="Skip the per-line block; emit only the per-chapter table.")
    sdt.set_defaults(func=_cmd_show_dont_tell)

    sa = sub.add_parser("series-arc",
                         help="Series-arc score across ≥2 books — completion, cross-book cast, story-time discipline, unresolved threads.")
    sa.add_argument("series_root", help="Path to the series root (parent of books/).")
    sa.add_argument("--threshold", type=float, default=7.0,
                     help="Chapter score threshold for ≥thr count (default 7.0).")
    sa.add_argument("--format", choices=("markdown", "json"), default="markdown")
    sa.set_defaults(func=_cmd_series_arc)

    pb = sub.add_parser("pov-bleed",
                         help="Heuristic POV-bleed scan — flag interiority lines naming non-POV characters.")
    pb.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    pb.add_argument("--series-root", default=None,
                     help="Series root for shared/characters.md (default: book_root.parent.parent).")
    pb.add_argument("--format", choices=("markdown", "json"), default="markdown")
    pb.add_argument("--summary-only", action="store_true")
    pb.set_defaults(func=_cmd_pov_bleed)

    sq = sub.add_parser("summary-query",
                        help="Filter the chapter-summary table by a small DSL (pov / score / story_time / cast / etc.).")
    sq.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    sq.add_argument("--where", default=None,
                    help="Filter expression, e.g. 'pov == \"Lucia\" and score < 7.0'.")
    sq.add_argument("--format", choices=("markdown", "json"), default="markdown",
                    help="Output format (default: markdown).")
    sq.set_defaults(func=_cmd_summary_query)

    db = sub.add_parser("dashboard",
                        help="Per-book dashboard re-renders eval log + augments mechanical dimensions; no LLM call.")
    db.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    db.add_argument("--threshold", type=float, default=7.0,
                    help="Chapter score threshold for sub-threshold streak (default 7.0).")
    db.add_argument("--format", choices=("markdown", "json"), default="markdown",
                    help="Output format (default: markdown).")
    db.set_defaults(func=_cmd_dashboard)

    et = sub.add_parser("entity-track",
                        help="Per-chapter named-entity tracker (reads books/<book>/entities.md or shared/canon.md).")
    et.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    et.add_argument("--series-root", default=None,
                    help="Series root for canon.md fallback (default: parent of book_root's parent).")
    et.add_argument("--format", choices=("markdown", "json"), default="markdown",
                    help="Output format (default: markdown table).")
    et.set_defaults(func=_cmd_entity_track)

    em = sub.add_parser("build-epub-md",
                        help="Concatenate ch_NN.md files into one pandoc-ready markdown.")
    em.add_argument("chapters_dir")
    em.add_argument("--output", default=None,
                    help="Write the combined markdown to this path; otherwise stdout-JSON only.")
    em.set_defaults(func=_cmd_build_epub_md)

    cs = sub.add_parser("chapter-summary",
                        help="One-line-per-chapter overview (date / POV / score / cast / plot).")
    cs.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    cs.add_argument("--format", choices=("markdown", "json"), default="markdown",
                    help="Output format (default: markdown table).")
    cs.set_defaults(func=_cmd_chapter_summary)

    fm = sub.add_parser("build-front-matter-tex",
                        help="Concatenate preface.md + introduction.md into front_matter.tex.")
    fm.add_argument("book_root", help="Path to the book dir (the parent of preface.md).")
    fm.add_argument("--output", default=None, help="Write to this path; otherwise stdout-JSON only.")
    fm.set_defaults(func=_cmd_build_front_matter_tex)

    rt = sub.add_parser("render-novel-tex",
                        help="Substitute @KEY@ placeholders in a novel.tex template (replaces fragile sed).")
    rt.add_argument("template", help="Path to the novel.tex template.")
    rt.add_argument("--output", required=True, help="Destination path for the rendered .tex.")
    rt.add_argument("--substitution", "-s", dest="substitutions", action="append",
                    help="KEY=VALUE pair. Repeat for multiple. KEY substitutes @KEY@ in the template.")
    rt.set_defaults(func=_cmd_render_novel_tex)

    tf = sub.add_parser("typeset-filename",
                        help="Print canonical typeset output filename `<slug>_<YYYYMMDD>_<HHMM>.<kind>` plus latest.")
    tf.add_argument("slug", help="Book slug (will be normalised).")
    tf.add_argument("kind", help="Extension without dot (`pdf` or `epub`).")
    tf.set_defaults(func=_cmd_typeset_filename)

    bt = sub.add_parser("build-tex", help="Build chapters_content.tex from a chapters dir.")
    bt.add_argument("chapters_dir")
    bt.add_argument("--art-dir", dest="art_dir", default=None)
    bt.add_argument("--output", default=None)
    bt.add_argument("--plates-manifest", dest="plates_manifest", default=None,
                    help="Path to plates.yaml; user-supplied images get woven in.")
    bt.add_argument("--plates-root", dest="plates_root", default=None,
                    help="Base directory plate `file:` paths are resolved against "
                         "(default: parent of --plates-manifest).")
    bt.set_defaults(func=_cmd_build_tex)

    args = p.parse_args(argv)
    if not hasattr(args, "func"):
        p.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
