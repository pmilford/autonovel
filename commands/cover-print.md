---
name: autonovel:cover-print
description: Compose a print-ready wraparound cover + the thumbnail matrix.
argument-hint: "--book <short-name> --pages <N> [--paper cream|white] [--trim-w 5.5] [--trim-h 8.5] [--spine-override <inches>] [--preview] [--blurb-file <path>] [--typographic-only [--bg-color #RRGGBB]]"
model_tier: light
allowed-tools:
  - file_read
  - bash
reads:
  - project.yaml
  - books/{book}/art/cover.png
  - books/{book}/art/cover_titled.png
writes:
  - books/{book}/art/cover_print.png
  - books/{book}/art/thumbnails/*.png
context_mode: book
---

<purpose>
Replace `gen_cover_print.py`. Produces the printer-grade wraparound
(back cover + spine + front cover on one canvas with bleed) and the
thumbnail matrix (Amazon KDP full-size, two web thumbnails, a
square for audiobook platforms).

Spine width is computed from the page count + paper stock via
`autonovel mechanical spine-width`. A printer-supplied
override (`--spine-override <inches>`) wins when present.

Light tier — PIL only, no LLM. Improvement over pre-rewrite: one
invocation yields the full KDP/Lulu wraparound AND all thumbnails;
previously those were two scripts run separately.

**Typographic-only mode** (`--typographic-only`) skips the
`books/{book}/art/cover.png` requirement entirely and produces a
title-and-author-on-solid-color cover. The right path when the
user has no image-API key, isn't running local Stable Diffusion,
and doesn't want to use Pollinations — the typographic look is a
recognised cover convention (NYRB Classics, Penguin Black
Classics, Faber poetry editions). `--bg-color #RRGGBB` overrides
the background; default is a paper-stock-matched off-white. Free,
zero-key, runs in under a second.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book` and `--pages` are required; everything
   else has defaults from `project.yaml :: print` (falling back to
   `5.5 × 8.5 cream` + `0.125` bleed + `300` dpi + no preview). Missing
   required args → usage error and stop.

2. Use `file_read` on `project.yaml` to resolve title/author/subtitle
   (same precedence as `/autonovel:cover-composite`).

   - **Default mode**: confirm `books/{book}/art/cover.png` exists;
     if not, stop with a run-art-pick reminder (or "switch to
     `--typographic-only` if you don't have art").
   - **Typographic-only mode** (`--typographic-only`): skip the
     cover.png check. The cover layer is a solid color (paper-
     stock-matched off-white by default; `--bg-color #RRGGBB`
     overrides). Title + author + optional subtitle are composed
     onto the wraparound canvas via Pillow's text rendering, with
     the back-cover blurb (if `--blurb-file` provided) on the
     opposite panel. No image dependency.

3. Use `bash` to compute the cover spec:
   `autonovel mechanical spine-width --pages <N> --paper <P>`
   plus the trim + bleed flags as passed. Capture the JSON output and
   echo spine + canvas dimensions in the summary so the user can
   eyeball them before hitting the printer.

4. Use `bash` to run the print-cover renderer:
   ```
   python3 -c "from autonovel.export.cover import print_cover, thumbnail_matrix; p, spec = print_cover(series_root='.', book='{book}', art_path='books/{book}/art/cover.png', title='{title}', author='{author}', subtitle='{subtitle}', blurb=open('{blurb_file}').read() if '{blurb_file}' else '', pages={pages}, paper='{paper}', trim_w={trim_w}, trim_h={trim_h}, spine_override={spine_override}, preview={preview}); thumbnail_matrix(titled_cover='books/{book}/art/cover_titled.png', art_dir='books/{book}/art')"
   ```
   This call is intentionally single-line — bash parses newlines as
   statement separators (documented gotcha carried from
   `/autonovel:apply-cuts`). If `books/{book}/art/cover_titled.png`
   doesn't exist yet, print a note that the thumbnail matrix is being
   generated from `cover.png` instead and continue.

5. Print a one-screen summary:
   - Spine: `{spine_w:.3f}" @ {pages} pages ({paper})`
   - Canvas: `{canvas_w:.3f}" × {canvas_h:.3f}"`
   - Files written (print canvas + four thumbnails) with byte counts.
   - If `--preview` was set, note that the red lines are trim guides
     and the green lines are the spine — the print file is not
     preview-safe and should be regenerated without `--preview`
     before upload.
</workflow>

<acceptance>
- `books/{book}/art/cover_print.png` exists at the computed canvas
  dimensions (or `cover_preview.png` if `--preview` was set).
- The thumbnail matrix is written under `books/{book}/art/thumbnails/`
  with at least the `amazon`, `thumbnail_lg`, `thumbnail_sm`, and
  `square` targets.
- A `--spine-override` value is reflected 1:1 in the `Spine:` summary
  line.
- No LLM call is made.
</acceptance>
