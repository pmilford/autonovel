---
name: autonovel:landing
description: Render a responsive landing page with og:image + structured data for one book.
argument-hint: "--book <short-name> [--template <path>] [--url <canonical-url>]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - landing/template.html
  - books/{book}/outline.md
  - books/{book}/seed.txt
  - books/{book}/art/cover_titled.png
writes:
  - books/{book}/landing/index.html
  - books/{book}/landing/cover.png
  - books/{book}/landing/cover_bg.png
context_mode: book
---

<purpose>
Replace `landing/index.html` (deleted this PR; its substantive layout
moves to `landing/template.html` as a generic template). One command
produces a responsive, metadata-rich landing page per book, wired with:

  - Open Graph (`og:image` / `og:type=book` / `og:description`).
  - Twitter card (`summary_large_image`).
  - JSON-LD `Book` structured data for search-engine pickup.
  - Series navigation across books (auto-suppressed for single-book
    series).

Standard tier — writing the tagline and blurb is a prose task.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` is required. Optional
   `--template <path>` (defaults to `landing/template.html` at the
   series root) and `--url <canonical-url>` (the URL where this
   landing page will be hosted; used for og:url and structured data).

2. Use `file_read` on `project.yaml`, `books/{book}/outline.md`, and
   `books/{book}/seed.txt`. Resolve title + author + series_name from
   `project.yaml`. Resolve the current year for copyright.

3. Draft a `tagline` (one sentence, pulled from the seed or outline
   — maximum ~20 words, present tense, no spoilers beyond the
   inciting situation) and a `blurb` (~150 words, covers act-one
   setup + the protagonist's problem, no spoilers past the first
   turn). These two fields are the only creative output of the
   command — everything else is structured.

4. Use `bash: cp books/{book}/art/cover_titled.png
   books/{book}/landing/cover.png`. Also copy the (un-titled) cover
   as `cover_bg.png` — the template uses it as a faded background at
   15% opacity. If `cover_titled.png` doesn't exist yet, fall back to
   `cover.png`; if neither exists, stop with a
   "run `/autonovel:cover-composite --book {book}` first" message.

5. Build the series navigation: list every book in
   `project.yaml :: books` and their expected landing URLs
   (`<base-url>/<book-name>/` by default). Use
   `python3 -c "from autonovel.export.landing import series_nav_html;
   ..."` to emit the HTML snippet.

6. Render the page via `bash`:
   ```
   python3 -c "from autonovel.export.landing import render_landing; render_landing('{template}', 'books/{book}/landing/index.html', {'TITLE': '...', 'AUTHOR': '...', 'TAGLINE': '...', 'BLURB': '...', 'COVER_PATH': 'cover.png', 'BACKGROUND_PATH': 'cover_bg.png', 'URL': '{url}', 'PDF_URL': 'novel.pdf', 'EPUB_URL': 'novel.epub', 'AUDIOBOOK_URL': 'full_audiobook.mp3', 'SERIES_NAME': '...', 'SERIES_NAV': '<generated>'})"
   ```
   The call is intentionally single-line (bash-separator gotcha).

7. Print the output path, the tagline, and the first ~200 chars of
   the blurb — enough for the user to eyeball the tone without
   opening a browser.
</workflow>

<acceptance>
- `books/{book}/landing/index.html` is a valid HTML5 document.
- The rendered page contains the book's title, author, tagline, and
  blurb, plus `og:image`, `twitter:card`, and `application/ld+json`
  metadata.
- When the series has only one book, the series-nav section is
  empty (no orphan link to a phantom series).
</acceptance>
