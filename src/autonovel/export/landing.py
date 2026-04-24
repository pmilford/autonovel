"""Landing page renderer.

Given a template and a substitution map, emit an `index.html` with
OpenGraph / Twitter-card / structured-data metadata filled in. Pure
string substitution — no LLM.

Placeholders in the template are `@TITLE@` style so they survive
being inside CSS `@import` URLs and JSON-LD blocks without collisions
with curly-brace or dollar-sign syntax.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping


REQUIRED_KEYS = (
    "TITLE",
    "AUTHOR",
    "SERIES_NAME",
    "TAGLINE",
    "BLURB",
    "COVER_PATH",
    "BACKGROUND_PATH",
    "URL",
    "PDF_URL",
    "EPUB_URL",
    "AUDIOBOOK_URL",
    "SERIES_NAV",
)


def render_template(template: str, values: Mapping[str, str]) -> str:
    """Substitute every `@KEY@` in `template` with `values[KEY]`.

    Missing keys are replaced with the empty string — the template
    tolerates missing optional fields (no audiobook → empty button).
    Extra keys are ignored.
    """
    out = template
    for key in REQUIRED_KEYS:
        out = out.replace(f"@{key}@", values.get(key, ""))
    return out


def render_landing(
    template_path: Path | str,
    output_path: Path | str,
    values: Mapping[str, str],
) -> Path:
    template = Path(template_path).read_text(encoding="utf-8")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_template(template, values), encoding="utf-8")
    return out


def series_nav_html(books: list[tuple[str, str]], active_book: str | None = None) -> str:
    """Build the right-column series navigation HTML.

    `books` is a list of `(book_name, book_url)` pairs. The active book
    is rendered with the primary-button style; others use the outline style.
    Returns an empty string if there's only one book — no navigation
    needed in that case.
    """
    if len(books) <= 1:
        return ""
    lines = ['<nav class="series-nav">']
    for name, url in books:
        css_class = "btn btn-primary" if name == active_book else "btn"
        lines.append(f'    <a href="{url}" class="{css_class}">{name}</a>')
    lines.append("</nav>")
    return "\n".join(lines)
