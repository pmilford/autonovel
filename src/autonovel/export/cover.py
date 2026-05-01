"""PIL cover renderers.

Two public entry points, each shelled out to by exactly one command:

  - `composite_cover(...)` — e-book cover. Front art + title + author.
  - `print_cover(...)` — print-ready wraparound (back + spine + front)
    with spine width computed from `mechanical.spine.cover_spec`.

Both read the book's canonical art paths and write back into the same
`books/{book}/art/` tree. They share the font-matching helper — EB
Garamond with Liberation Serif fallback via `fc-match`.

PIL is imported lazily so the package imports cleanly even when
Pillow is not installed (relevant for Tier-1 tests that don't touch
the cover path).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..mechanical.spine import CoverSpec, cover_spec
from ..paths import SeriesLayout


def find_font(name: str, style: str = "Regular") -> str | None:
    """Resolve a font file via `fc-match`. Returns the path or None."""
    result = subprocess.run(
        ["fc-match", f"{name}:style={style}", "--format=%{file}"],
        capture_output=True,
        text=True,
        check=False,
    )
    path = result.stdout.strip()
    if path and Path(path).exists():
        return path
    return None


def _resolve_font(role: str, bold: bool = False, italic: bool = False) -> str | None:
    style = "Regular"
    if bold:
        style = "Bold"
    elif italic:
        style = "Italic"
    return find_font("EB Garamond", style) or find_font("Liberation Serif", style)


def _analyze_brightness(img, region: str = "top") -> float:
    w, h = img.size
    if region == "top":
        box = (0, 0, w, h // 4)
    elif region == "bottom":
        box = (0, h * 3 // 4, w, h)
    else:
        box = (0, 0, w, h)
    return sum(img.crop(box).convert("L").getdata()) / max(1, (box[2] - box[0]) * (box[3] - box[1]))


def composite_cover(
    *,
    series_root: Path | str,
    book: str,
    title: str,
    author: str,
    subtitle: str = "A Novel",
    preset: str = "auto",
    output: Path | str | None = None,
) -> Path:
    """E-book cover. Writes `books/{book}/art/cover_titled.png`."""
    from PIL import Image, ImageDraw, ImageFont

    series = SeriesLayout(root=Path(series_root))
    book_layout = series.book(book)
    art_dir = book_layout.root / "art"
    art_path = art_dir / "cover.png"
    if not art_path.exists():
        raise FileNotFoundError(art_path)
    out_path = Path(output) if output else art_dir / "cover_titled.png"

    img = Image.open(art_path).convert("RGBA")
    w, h = img.size

    if preset == "auto":
        avg = (_analyze_brightness(img, "top") + _analyze_brightness(img, "bottom")) / 2
        preset = "dark" if avg < 140 else "light"

    text_color = (255, 250, 240, 255)
    shadow_color = (0, 0, 0, 200)
    band_color = (0, 0, 0, 140)

    # Cover-art typography sizing — user 2026-04-30 reported the
    # title was too large and the translucent band overwhelmed the
    # underlying image. Target proportions match published-book
    # cover convention (Penguin Black Classics, NYRB) where the
    # title is ~6% of cover width and the band sits in the top
    # ~14% so the cover art remains the dominant visual element.
    title_size = max(int(w * 0.06), 28)
    author_size = max(int(w * 0.034), 16)
    subtitle_size = max(int(w * 0.026), 12)

    title_font = _load_font(_resolve_font("title", bold=True), title_size)
    author_font = _load_font(_resolve_font("author"), author_size)
    subtitle_font = _load_font(_resolve_font("subtitle", italic=True), subtitle_size)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    # Top band: 6%–20% (was 4%–38%; the 34%-tall band swallowed the
    # cover image's top third). Bottom band: 84%–96% (was 78%–96%;
    # tightened to leave more art visible).
    draw.rectangle([(0, int(h * 0.06)), (w, int(h * 0.20))], fill=band_color)
    draw.rectangle([(0, int(h * 0.84)), (w, int(h * 0.96))], fill=band_color)

    center_x = w // 2
    # Title centered in the top band (was at 15%, off-center for a
    # 4-38% band; now centered for the 6-20% band).
    _drop_text(draw, (center_x, int(h * 0.13)), title.upper(), title_font, text_color, shadow_color)
    _drop_text(draw, (center_x, int(h * 0.87)), subtitle, subtitle_font, text_color, shadow_color)
    _drop_text(draw, (center_x, int(h * 0.92)), author.upper(), author_font, text_color, shadow_color)

    result = Image.alpha_composite(img, overlay).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(str(out_path), "PNG")
    return out_path


def _load_font(path: str | None, size: int):
    from PIL import ImageFont
    if path:
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _drop_text(draw, pos, text, font, fill, shadow, offset: int = 3) -> None:
    x, y = pos
    draw.text((x + offset, y + offset), text, font=font, fill=shadow, anchor="mt")
    draw.text((x, y), text, font=font, fill=fill, anchor="mt")


def print_cover(
    *,
    series_root: Path | str,
    book: str,
    art_path: Path | str,
    title: str,
    author: str,
    subtitle: str = "A Novel",
    blurb: str = "",
    pages: int,
    paper: str = "cream",
    trim_w: float = 5.5,
    trim_h: float = 8.5,
    bleed: float = 0.125,
    dpi: int = 300,
    spine_override: float | None = None,
    preview: bool = False,
    output: Path | str | None = None,
) -> tuple[Path, CoverSpec]:
    """Print-ready wraparound cover. Writes `books/{book}/art/{stem}_print.png`.

    Returns both the output path and the resolved `CoverSpec` so the
    caller can emit spine + canvas dimensions in its summary.
    """
    from PIL import Image, ImageDraw, ImageFont

    series = SeriesLayout(root=Path(series_root))
    book_layout = series.book(book)
    art_dir = book_layout.root / "art"
    art_path = Path(art_path)

    spec = cover_spec(
        trim_w=trim_w,
        trim_h=trim_h,
        pages=pages,
        paper=paper,
        bleed=bleed,
        dpi=dpi,
        spine_override=spine_override,
    )

    art = Image.open(art_path).convert("RGB")
    art_ratio = art.width / art.height
    canvas_ratio = spec.px_w / spec.px_h
    if art_ratio > canvas_ratio:
        scale_h = spec.px_h
        scale_w = int(spec.px_h * art_ratio)
        art = art.resize((scale_w, scale_h), Image.LANCZOS)
        x_offset = (scale_w - spec.px_w) // 2
        art = art.crop((x_offset, 0, x_offset + spec.px_w, spec.px_h))
    else:
        scale_w = spec.px_w
        scale_h = int(spec.px_w / art_ratio)
        art = art.resize((scale_w, scale_h), Image.LANCZOS)
        y_offset = (scale_h - spec.px_h) // 2
        art = art.crop((0, y_offset, spec.px_w, y_offset + spec.px_h))

    canvas = art.convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    back_left = spec.px_bleed
    back_right = back_left + int(trim_w * dpi)
    spine_left = back_right
    front_left = spine_left + spec.px_spine

    display = find_font("Bebas Neue", "Regular") or _resolve_font("title", bold=True)
    regular = _resolve_font("body")

    title_large = int(trim_w * dpi * 0.10)
    author_size = int(trim_w * dpi * 0.06)
    title_font = _load_font(display, title_large)
    author_font = _load_font(display, author_size)

    front_cx = front_left + int(trim_w * dpi) // 2
    _drop_text(draw, (front_cx, spec.px_bleed + int(trim_w * dpi * 0.3)), title.upper(),
               title_font, (218, 165, 72, 255), (5, 5, 3, 220), offset=5)
    author_y = spec.px_h - spec.px_bleed - int(trim_h * dpi * 0.10)
    _drop_text(draw, (front_cx, author_y), author.upper(), author_font,
               (218, 165, 72, 255), (5, 5, 3, 220), offset=4)

    if spec.px_spine > 30 and display:
        spine_text = f"{title.upper()}   •   {author.upper()}"
        target_w = int(spec.px_h * 0.90)
        spine_size = 8
        for try_size in range(8, 120):
            f = _load_font(display, try_size)
            bbox = f.getbbox(spine_text)
            if (bbox[2] - bbox[0]) > target_w or (bbox[3] - bbox[1]) > int(spec.px_spine * 0.70):
                break
            spine_size = try_size
        spine_font = _load_font(display, spine_size)
        temp = Image.new("RGBA", (spec.px_h, spec.px_spine), (0, 0, 0, 0))
        tdr = ImageDraw.Draw(temp)
        tdr.text((spec.px_h // 2 + 2, spec.px_spine // 2 + 2), spine_text,
                 font=spine_font, fill=(0, 0, 0, 220), anchor="mm")
        tdr.text((spec.px_h // 2, spec.px_spine // 2), spine_text,
                 font=spine_font, fill=(200, 50, 40, 255), anchor="mm")
        temp = temp.rotate(90, expand=True)
        canvas.paste(temp, (spine_left + spec.px_spine // 2 - temp.width // 2,
                            (spec.px_h - temp.height) // 2), temp)

    if blurb and regular:
        blurb_font = _load_font(regular, int(trim_w * dpi * 0.03))
        margin = int(trim_w * dpi * 0.10)
        width = int(trim_w * dpi) - 2 * margin
        words = blurb.split()
        lines: list[str] = []
        cur = ""
        for w_ in words:
            test = f"{cur} {w_}".strip()
            if blurb_font.getbbox(test)[2] > width:
                lines.append(cur)
                cur = w_
            else:
                cur = test
        if cur:
            lines.append(cur)
        line_h = int(blurb_font.size * 1.65)
        y = spec.px_bleed + (int(trim_h * dpi) - len(lines) * line_h) // 2
        for ln in lines:
            draw.text((back_left + margin, y), ln, font=blurb_font, fill=(235, 230, 215, 255))
            y += line_h

    if preview:
        guide = (255, 0, 0, 100)
        spine_guide = (0, 255, 0, 100)
        for x in (back_left, back_right, front_left, front_left + int(trim_w * dpi)):
            draw.line([(x, 0), (x, spec.px_h)], fill=guide, width=2)
        draw.line([(spine_left, 0), (spine_left, spec.px_h)], fill=spine_guide, width=2)

    if output is None:
        stem = art_path.stem
        suffix = "_preview" if preview else "_print"
        out_path = art_dir / f"{stem}{suffix}.png"
    else:
        out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ext = out_path.suffix.lower()
    rgb = canvas.convert("RGB")
    if ext == ".pdf":
        rgb.save(str(out_path), "PDF", resolution=dpi)
    else:
        rgb.save(str(out_path), "PNG", dpi=(dpi, dpi))
    return out_path, spec


def thumbnail_matrix(
    *,
    titled_cover: Path | str,
    art_dir: Path | str,
) -> dict[str, Path]:
    """Resize the e-book cover into the thumbnail sizes retailers expect.

    Writes `art_dir/thumbnails/<target>.png`. Targets:
      - `amazon` — 1600×2400 (Amazon KDP cover standard).
      - `thumbnail_lg` — 800×1200.
      - `thumbnail_sm` — 400×600 (social-share sized).
      - `square` — 800×800 for music-player / audiobook covers.
    """
    from PIL import Image

    targets = {
        "amazon": (1600, 2400),
        "thumbnail_lg": (800, 1200),
        "thumbnail_sm": (400, 600),
        "square": (800, 800),
    }
    src = Image.open(titled_cover).convert("RGB")
    out_dir = Path(art_dir) / "thumbnails"
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for name, (w, h) in targets.items():
        resized = _fit_cover(src, w, h)
        path = out_dir / f"{name}.png"
        resized.save(str(path), "PNG")
        written[name] = path
    return written


def _fit_cover(img, target_w: int, target_h: int):
    """Resize + crop to exactly (target_w, target_h) preserving aspect."""
    from PIL import Image

    src_ratio = img.width / img.height
    dst_ratio = target_w / target_h
    if src_ratio > dst_ratio:
        new_h = target_h
        new_w = int(target_h * src_ratio)
    else:
        new_w = target_w
        new_h = int(target_w / src_ratio)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    x = (new_w - target_w) // 2
    y = (new_h - target_h) // 2
    return resized.crop((x, y, x + target_w, y + target_h))
