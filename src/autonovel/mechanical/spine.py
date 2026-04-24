"""Spine-width and cover-canvas calculator.

Pure function over (trim_w, trim_h, pages, paper, bleed). No I/O.

Spine-width rule of thumb, in inches-per-page:
  cream (55#)     — 0.0025 (Lulu, KDP cream)
  white (50#)     — 0.0020 (KDP white)
  uncoated-60     — 0.0027
  coated-70       — 0.0030

These are the same constants the pre-rewrite `gen_cover_print.py` used
(cream at 0.0025) generalized to the common paper stocks KDP + Lulu +
IngramSpark expose in their cover templates. A printer-supplied exact
spine-width overrides the computed value.
"""

from __future__ import annotations

from dataclasses import dataclass


PAPER_INCHES_PER_PAGE: dict[str, float] = {
    "cream": 0.0025,
    "white": 0.0020,
    "uncoated-60": 0.0027,
    "coated-70": 0.0030,
}

DEFAULT_BLEED = 0.125  # inches, standard for KDP / IngramSpark / Lulu
DEFAULT_DPI = 300


@dataclass(frozen=True)
class CoverSpec:
    """Resolved cover canvas dimensions."""

    trim_w: float
    trim_h: float
    pages: int
    paper: str
    spine_w: float
    bleed: float
    canvas_w: float
    canvas_h: float
    dpi: int

    @property
    def px_w(self) -> int:
        return int(round(self.canvas_w * self.dpi))

    @property
    def px_h(self) -> int:
        return int(round(self.canvas_h * self.dpi))

    @property
    def px_spine(self) -> int:
        return int(round(self.spine_w * self.dpi))

    @property
    def px_bleed(self) -> int:
        return int(round(self.bleed * self.dpi))

    def to_dict(self) -> dict:
        return {
            "trim_w": self.trim_w,
            "trim_h": self.trim_h,
            "pages": self.pages,
            "paper": self.paper,
            "spine_w": round(self.spine_w, 4),
            "bleed": self.bleed,
            "canvas_w": round(self.canvas_w, 4),
            "canvas_h": round(self.canvas_h, 4),
            "dpi": self.dpi,
            "px_w": self.px_w,
            "px_h": self.px_h,
            "px_spine": self.px_spine,
            "px_bleed": self.px_bleed,
        }


def spine_width(pages: int, paper: str = "cream") -> float:
    """Return spine width in inches for a given page count + paper stock."""
    if pages < 1:
        raise ValueError(f"pages must be >= 1; got {pages}")
    key = paper.lower()
    if key not in PAPER_INCHES_PER_PAGE:
        raise ValueError(
            f"unknown paper stock {paper!r}; valid: {sorted(PAPER_INCHES_PER_PAGE)}"
        )
    return pages * PAPER_INCHES_PER_PAGE[key]


def cover_spec(
    *,
    trim_w: float = 5.5,
    trim_h: float = 8.5,
    pages: int = 300,
    paper: str = "cream",
    bleed: float = DEFAULT_BLEED,
    dpi: int = DEFAULT_DPI,
    spine_override: float | None = None,
) -> CoverSpec:
    """Resolve a full cover canvas spec.

    If `spine_override` is given (e.g. the value a printer returns from
    their own spine calculator), it is used verbatim; otherwise
    `spine_width(pages, paper)` is computed.
    """
    if trim_w <= 0 or trim_h <= 0:
        raise ValueError("trim dimensions must be positive")
    if bleed < 0:
        raise ValueError("bleed must be non-negative")
    if dpi < 72:
        raise ValueError(f"dpi must be >= 72; got {dpi}")
    sw = spine_override if spine_override is not None else spine_width(pages, paper)
    canvas_w = bleed + trim_w + sw + trim_w + bleed
    canvas_h = bleed + trim_h + bleed
    return CoverSpec(
        trim_w=trim_w,
        trim_h=trim_h,
        pages=pages,
        paper=paper,
        spine_w=sw,
        bleed=bleed,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        dpi=dpi,
    )
