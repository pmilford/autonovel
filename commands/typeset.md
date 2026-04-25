---
name: autonovel:typeset
description: Build PDF + ePub from a book's chapters and typeset templates.
argument-hint: "--book <short-name> [--pdf-only | --epub-only] [--convert-vectors]"
model_tier: light
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - typeset/novel.tex
  - typeset/epub_front_matter.md
  - typeset/epub_back_cover.md
  - typeset/epub_colophon.md
  - typeset/epub_metadata.yaml
  - typeset/epub_style.css
  - books/{book}/chapters/*.md
  - books/{book}/art/cover.png
  - books/{book}/art/cover_titled.png
  - books/{book}/art/ornament_ch*.png
  - books/{book}/art/svg/*.svg
writes:
  - books/{book}/typeset/chapters_content.tex
  - books/{book}/typeset/novel.tex
  - books/{book}/typeset/novel.pdf
  - books/{book}/typeset/novel.epub
  - books/{book}/typeset/metadata.yaml
context_mode: book
---

<purpose>
Replace `typeset/build_tex.py` and the pre-rewrite tectonic + pandoc
ad-hoc shell steps. One command produces both a print-quality PDF
(tectonic + EB Garamond + drop caps + chapter ornaments) and a
reflowable ePub from the same source.

The `typeset/` directory at the repo root holds the shared templates
(`novel.tex`, `epub_*`). Per-book customisation happens at build time:
this command copies `typeset/novel.tex` into
`books/{book}/typeset/novel.tex`, substitutes `@TITLE@` / `@AUTHOR@` /
`@SERIES_NAME@`, then hands it to `tectonic`.

Light tier — mechanical. No LLM call.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` is required. Optional
   `--pdf-only` / `--epub-only` (default: both), `--convert-vectors`
   (runs `rsvg-convert` on every `books/{book}/art/svg/*.svg` →
   `books/{book}/art/pdf/<stem>.pdf` before building so the ornaments
   use vector versions; skipped if `rsvg-convert` isn't installed).

2. Use `file_read` on `project.yaml` to pull the book's display title,
   author, and subtitle. Fall back to `series_name` + the book's
   short name if explicit title/author aren't set. The TeX includes
   `books/{book}/art/cover.png` (full-bleed cover page) and the
   per-chapter `ornament_ch*.png` files via `\IfFileExists` — missing
   art degrades gracefully, the build still completes.

3. Build `chapters_content.tex` via `bash`:
   `autonovel mechanical build-tex books/{book}/chapters
   --art-dir books/{book}/art --output
   books/{book}/typeset/chapters_content.tex
   --plates-manifest books/{book}/typeset/plates.yaml`.
   The `--plates-manifest` flag is best-effort — if the file
   doesn't exist (no user-imported plates), the build still
   succeeds. If it does exist, every entry's image gets woven into
   the LaTeX at its declared `placement` (`before-chapter`,
   `chapter-start`, or `after-chapter`) with caption + attribution.
   Parse the JSON output — print the per-chapter titles + which
   ornaments + which user plates were wired in as part of the
   summary.

4. PDF path (unless `--epub-only`):
   a. Use `bash: cp typeset/novel.tex books/{book}/typeset/novel.tex`.
   b. Use `bash` with `sed -i` to substitute `@TITLE@`, `@AUTHOR@`,
      `@SERIES_NAME@` placeholders in the copied file. (See the
      `typeset/novel.tex` template — the pre-rewrite version hard-
      coded the Bells title; it now uses placeholders.)
   c. Use `bash: (cd books/{book}/typeset && tectonic novel.tex)`.
      Tectonic is the only typesetter supported — it downloads
      dependencies on first run and is hermetic across platforms.
   d. On failure, print the last ~30 lines of the log and stop.
      Partial PDFs left by tectonic stay in place; the user can
      inspect them.

5. ePub path (unless `--pdf-only`):
   a. Use `bash` with `pandoc` to build the ePub from chapters +
      front/back matter + metadata:
      ```
      pandoc -o books/{book}/typeset/novel.epub \
        --metadata-file=books/{book}/typeset/metadata.yaml \
        --css=typeset/epub_style.css \
        --epub-cover-image=books/{book}/art/cover_titled.png \
        typeset/epub_front_matter.md \
        books/{book}/chapters/ch_*.md \
        typeset/epub_back_cover.md \
        typeset/epub_colophon.md
      ```
      The metadata.yaml for this book is assembled on the fly from
      `project.yaml` + `typeset/epub_metadata.yaml` (template) and
      written to `books/{book}/typeset/metadata.yaml` before the
      pandoc call.
   b. If `pandoc` isn't installed, stop with a single-line install
      hint. The PDF path can still have succeeded before this step;
      report what got built.

6. Print a one-screen summary: size of the PDF, page count if
   discoverable (parse `pdfinfo books/{book}/typeset/novel.pdf`), ePub
   size, and a warning if either output is missing.
</workflow>

<acceptance>
- Unless `--epub-only`, `books/{book}/typeset/novel.pdf` exists and
  is a valid PDF (≥ 4 KB sanity floor).
- Unless `--pdf-only`, `books/{book}/typeset/novel.epub` exists and
  is a valid ePub.
- `books/{book}/typeset/chapters_content.tex` reflects the current
  chapter set — re-running the command after changing a chapter
  updates the PDF.
- No chapter file is modified; the book's working tree is untouched
  outside `books/{book}/typeset/`.
</acceptance>
