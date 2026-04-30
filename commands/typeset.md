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
  - books/{book}/typeset/chapters_combined.md
  - books/{book}/typeset/front_matter.tex
  - books/{book}/typeset/novel.tex
  - books/{book}/typeset/*.pdf
  - books/{book}/typeset/*.epub
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

2. Use `file_read` on `project.yaml` to pull the book's display
   metadata. Resolution rules (matches `BookEntry.display_title()` /
   `display_author()` in `src/autonovel/project.py`):

   - **title**: `books[<name>].title` if set, else the series-level
     `series_name`, else the book's short name.
   - **subtitle**: `books[<name>].subtitle` if set, else empty
     (typeset omits the subtitle line entirely when empty).
   - **author**: `books[<name>].author` if set, else the
     series-level `author` (top-level field in `project.yaml`),
     else "Anonymous".

   Set these via `/autonovel:title --book {book}` (proposes, picks,
   or sets explicitly — the command writes to `project.yaml`
   without you needing to hand-edit YAML).

   The TeX includes `books/{book}/art/cover.png` (full-bleed cover
   page) and the per-chapter `ornament_ch*.png` files via
   `\IfFileExists` — missing art degrades gracefully, the build still
   completes.

3. Build `chapters_content.tex` via `bash`:
   `autonovel mechanical build-tex books/{book}/chapters
   --art-dir books/{book}/art --output
   books/{book}/typeset/chapters_content.tex
   --plates-manifest books/{book}/typeset/plates.yaml`.

3a. Build `front_matter.tex` via `bash`:
    `autonovel mechanical build-front-matter-tex books/{book}
    --output books/{book}/typeset/front_matter.tex`.
    The helper checks for `books/{book}/preface.md` (hand-authored),
    `books/{book}/introduction.md` (typically written by
    `/autonovel:introduction --from auto`), and
    `books/{book}/glossary.md` (typically written by
    `/autonovel:glossary --from auto`); when none exist, it writes
    nothing and the chapter file `\IfFileExists{}` guard in novel.tex
    silently skips the include. When any exist, each becomes a
    `\chapter*{...}` block (unnumbered, in the TOC, in the
    `\frontmatter` zone — before chapter 1). Render order is fixed:
    Preface → Introduction → Glossary (so the glossary sits closest
    to chapter 1 for reader flip-back). Parse the JSON output —
    print the section names that landed as part of the summary.

3b. Build `back_matter.tex` via `bash`:
    `autonovel mechanical build-back-matter-tex books/{book}
    --output books/{book}/typeset/back_matter.tex`. Reads
    `books/{book}/appendix.md` (typically written by
    `/autonovel:appendix --from auto`); when absent, writes nothing
    and the `\IfFileExists{}` guard in novel.tex silently skips the
    include. The `## Sub-heading` lines inside appendix.md (Timeline,
    Bios, Sources, Notes) get promoted to `\section*{}` so the
    back-matter renders with proper section breaks. Sits in the
    `\backmatter` zone — after the last chapter, before the
    colophon. Parse the JSON output — print the section names that
    landed.
   The `--plates-manifest` flag is best-effort — if the file
   doesn't exist (no user-imported plates), the build still
   succeeds. If it does exist, every entry's image gets woven into
   the LaTeX at its declared `placement` (`before-chapter`,
   `chapter-start`, or `after-chapter`) with caption + attribution.
   Parse the JSON output — print the per-chapter titles + which
   ornaments + which user plates were wired in as part of the
   summary.

4. PDF path (unless `--epub-only`):
   a. **Render the per-book novel.tex** via the safer Python helper
      (no sed):
      ```
      autonovel mechanical render-novel-tex \
        typeset/novel.tex \
        --output books/{book}/typeset/novel.tex \
        -s TITLE='<title>' \
        -s AUTHOR='<author>' \
        -s SERIES_NAME='<series_name>'
      ```
      Resolve `<title>` / `<author>` from `project.yaml` step 2 (see
      title fallbacks there). The helper does pure string replacement
      — no shell interpretation, no escape-needed for `/` or `&` in
      titles — replacing the previous `sed -i` which was fragile on
      titles containing those characters and was the likely cause of
      the "first PDF run didn't work" symptom reported 2026-04-25.
   b. **Resolve the timestamped output names** for this build:
      ```
      autonovel mechanical typeset-filename {book} pdf
      ```
      Parse the JSON output: `timestamped` is the per-build name
      (e.g. `the-inquisitor_20260425_1540.pdf`); `latest` is the
      convenience pointer (e.g. `the-inquisitor_latest.pdf`).
   c. Use `bash` to run tectonic and copy the result to the
      timestamped + latest filenames:
      ```
      (cd books/{book}/typeset && tectonic novel.tex)
      cp books/{book}/typeset/novel.pdf \
         books/{book}/typeset/<timestamped>
      cp books/{book}/typeset/novel.pdf \
         books/{book}/typeset/<latest>
      ```
      Tectonic produces `novel.pdf` from `novel.tex`; we copy to both
      destinations so a writer can keep every build (timestamped) AND
      always know which file is the most recent (latest). Tectonic
      is the only typesetter supported — it downloads dependencies
      on first run and is hermetic across platforms.
   d. On tectonic failure, print the last ~30 lines of the log and
      stop. Partial `novel.pdf` left by tectonic stays in place for
      inspection; the timestamped + latest copies are NOT written
      (they should only point at successful builds).

5. ePub path (unless `--pdf-only`):
   a. **Build the combined markdown.** Use `bash` to run
      `autonovel mechanical build-epub-md books/{book}/chapters
      --output books/{book}/typeset/chapters_combined.md`. This
      enumerates only `ch_NN.md` files (NOT `ch_NN.summary.md`,
      which would otherwise leak the per-chapter continuity
      handoff — POV, threads_opened, threads_closed — into the
      reader's ePub), strips YAML frontmatter from each chapter
      (so `book: …`, `word_count: …` don't render as visible
      prose), and emits a canonical `# Chapter N: <title>` heading
      per chapter so pandoc reliably sees one top-level division
      per chapter (which makes ePub chapter navigation actually
      work). Bug both fixed 2026-04-25.

   b. **Resolve the timestamped output names** for the ePub build:
      ```
      autonovel mechanical typeset-filename {book} epub
      ```
      Same JSON shape as step 4b — `timestamped` and `latest`.

   c. **Run pandoc** against the combined file plus front/back
      matter, writing to the timestamped name first; copy to
      `latest` after pandoc succeeds:
      ```
      pandoc -o books/{book}/typeset/<timestamped> \
        --metadata-file=books/{book}/typeset/metadata.yaml \
        --css=typeset/epub_style.css \
        --epub-cover-image=books/{book}/art/cover_titled.png \
        --top-level-division=chapter \
        --toc \
        typeset/epub_front_matter.md \
        <preface-arg> \
        <introduction-arg> \
        books/{book}/typeset/chapters_combined.md \
        typeset/epub_back_cover.md \
        typeset/epub_colophon.md
      cp books/{book}/typeset/<timestamped> \
         books/{book}/typeset/<latest>
      ```
      `--top-level-division=chapter` + `--toc` produce a clean
      per-chapter ePub spine with proper TOC entries (without
      these flags pandoc sometimes treats `# …` headings as
      sections instead of chapters, which is why earlier ePubs
      had unclear chapter marking).

      `<preface-arg>` and `<introduction-arg>` are the literal
      paths `books/{book}/preface.md` and
      `books/{book}/introduction.md` when those files exist (test
      with `[ -f books/{book}/preface.md ]` etc.); when a file
      doesn't exist, omit the argument entirely (don't pass an
      empty path to pandoc — it errors). Pandoc reads each `# …`
      heading inside preface.md / introduction.md as a top-level
      division, so they appear in the spine and TOC alongside
      the chapters.

      The metadata.yaml for this book is assembled on the fly from
      `project.yaml` + `typeset/epub_metadata.yaml` (template) and
      written to `books/{book}/typeset/metadata.yaml` before the
      pandoc call.

   d. If `pandoc` isn't installed, stop with a single-line install
      hint. The PDF path can still have succeeded before this step;
      report what got built.

6. Print a one-screen summary naming the timestamped filename
   AND the `latest` pointer for each artefact, plus size of the
   PDF, page count if discoverable (parse `pdfinfo` against
   the timestamped PDF), ePub size, and a warning if either
   output is missing. Format:

   ```
   PDF:  books/{book}/typeset/<book>_20260425_1540.pdf  (412 KB, 247 pages)
         books/{book}/typeset/<book>_latest.pdf  (alias)
   ePub: books/{book}/typeset/<book>_20260425_1540.epub  (387 KB)
         books/{book}/typeset/<book>_latest.epub  (alias)
   ```

   The timestamped filenames let the writer keep every build for
   side-by-side comparison across revisions; `<book>_latest.*` is
   always the most recent successful build, so opening the same
   file repeatedly works without chasing timestamps.
</workflow>

<acceptance>
- Unless `--epub-only`, both `books/{book}/typeset/<book>_<YYYYMMDD>_<HHMM>.pdf`
  and `books/{book}/typeset/<book>_latest.pdf` exist and are valid
  PDFs (≥ 4 KB sanity floor). The two files have identical bytes.
- Unless `--pdf-only`, the corresponding `.epub` pair exists.
- `books/{book}/typeset/chapters_content.tex` reflects the current
  chapter set — re-running the command after changing a chapter
  updates the PDF.
- No chapter file is modified; the book's working tree is untouched
  outside `books/{book}/typeset/`.
- `<book>_latest.pdf` / `<book>_latest.epub` always point at the
  most recent successful build (i.e. were re-copied this run).
- Failed tectonic runs leave the partial `novel.pdf` in place for
  inspection but DO NOT update the timestamped or latest names —
  those names should only refer to successful builds.
</acceptance>
