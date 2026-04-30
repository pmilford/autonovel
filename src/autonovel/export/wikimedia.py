"""Wikimedia Commons public-domain art provider.

Free, no API key, no rate limit anxiety, fully lawful for any use
(public-domain images on Commons are PD by definition; the
attribution metadata still gets recorded for credit). Best fit for
historical fiction where a period-appropriate painting is on-genre.

The catch: you get a real painting (not an AI-generated original).
The user has to crop / scale to cover dimensions, which we do via
Pillow.

Public API:

    search_images(query, *, limit=10) -> list[ImageCandidate]
    fetch_image_metadata(file_title) -> ImageDetails
    download_and_crop(image_details, *, target_size, output_path)
        -> CroppedImage

CLI subcommand: `autonovel mechanical wikimedia-search` and
`wikimedia-fetch` invoke these from the slash-command body.

No SDK needed — the Wikimedia API is plain HTTPS GET with JSON
responses. We use httpx (already a top-level autonovel dep).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote


WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "autonovel/0.2 (https://github.com/pmilford/autonovel; novel-writing pipeline)"


@dataclass
class ImageCandidate:
    """One result from `search_images()`. Lightweight — does not
    download the actual image; just enough metadata to rank."""
    title: str            # `File:...jpg` form (used to fetch details)
    page_id: int
    snippet: str = ""     # search-result snippet (HTML; may include <span>)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "page_id": self.page_id,
            "snippet": self.snippet,
        }


@dataclass
class ImageDetails:
    """Full metadata for one Commons image. Pulled by
    `fetch_image_metadata()`."""
    title: str
    url: str               # direct media URL (PNG/JPG/SVG)
    descriptionurl: str    # the Commons file-description page
    width: int
    height: int
    mime: str              # image/jpeg, image/png, image/svg+xml
    size_bytes: int
    license_short: str = ""  # "PD-art-100", "CC0", etc.
    license_url: str = ""
    artist: str = ""        # raw HTML; caller normalises
    description: str = ""

    @property
    def is_public_domain(self) -> bool:
        """Lawful-for-any-use guard. Strict — if the license isn't
        explicitly PD or CC0, return False even though many other
        CC variants permit reuse with attribution.
        """
        token = (self.license_short or "").lower()
        return any(s in token for s in (
            "pd-", "publicdomain", "public domain", "cc0", "cc-zero",
        ))

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "descriptionurl": self.descriptionurl,
            "width": self.width,
            "height": self.height,
            "mime": self.mime,
            "size_bytes": self.size_bytes,
            "license_short": self.license_short,
            "license_url": self.license_url,
            "artist": self.artist,
            "description": self.description,
            "is_public_domain": self.is_public_domain,
        }


@dataclass
class CroppedImage:
    output_path: Path
    original: ImageDetails
    crop_box: tuple[int, int, int, int]  # left, top, right, bottom in source coords
    final_size: tuple[int, int]
    attribution_line: str  # "Artist (Year), via Wikimedia Commons. License: PD-art-100"

    def to_dict(self) -> dict:
        return {
            "output_path": str(self.output_path),
            "original_title": self.original.title,
            "original_url": self.original.url,
            "crop_box": list(self.crop_box),
            "final_size": list(self.final_size),
            "attribution_line": self.attribution_line,
            "license_short": self.original.license_short,
            "license_url": self.original.license_url,
        }


# ----------------------------------------------------- HTTP


def _http_get_json(params: dict, *, client=None) -> dict:
    """Single-shot GET against the Wikimedia API. `client` is the
    httpx.Client seam for tests."""
    import httpx
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if client is None:
        with httpx.Client(timeout=30, follow_redirects=True) as c:
            r = c.get(WIKIMEDIA_API, params=params, headers=headers)
    else:
        r = client.get(WIKIMEDIA_API, params=params, headers=headers)
    r.raise_for_status()
    return r.json()


def _http_get_bytes(url: str, *, client=None) -> bytes:
    import httpx
    headers = {"User-Agent": USER_AGENT}
    if client is None:
        with httpx.Client(timeout=120, follow_redirects=True) as c:
            r = c.get(url, headers=headers)
    else:
        r = client.get(url, headers=headers)
    r.raise_for_status()
    return r.content


# ----------------------------------------------------- search


def search_images(query: str, *, limit: int = 10,
                    client=None) -> list[ImageCandidate]:
    """Search Wikimedia Commons for images matching `query`. Filters
    to file namespace (only File:... results)."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srnamespace": 6,       # File: namespace
        "srlimit": limit,
        "format": "json",
        "formatversion": 2,
    }
    data = _http_get_json(params, client=client)
    out: list[ImageCandidate] = []
    for hit in data.get("query", {}).get("search", []):
        title = hit.get("title")
        page_id = hit.get("pageid")
        if not title or page_id is None:
            continue
        out.append(ImageCandidate(
            title=title, page_id=int(page_id),
            snippet=hit.get("snippet", ""),
        ))
    return out


# ----------------------------------------------------- metadata


def fetch_image_metadata(file_title: str, *,
                           client=None) -> ImageDetails | None:
    """Pull full image metadata for one File:... title. Returns
    None when Commons doesn't have the page or the image lacks
    required fields."""
    params = {
        "action": "query",
        "titles": file_title,
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": 2048,    # request a high-res derivative
        "format": "json",
        "formatversion": 2,
    }
    data = _http_get_json(params, client=client)
    pages = data.get("query", {}).get("pages", [])
    if not pages:
        return None
    page = pages[0]
    if page.get("missing") or not page.get("imageinfo"):
        return None
    info = page["imageinfo"][0]
    extmd = info.get("extmetadata") or {}
    license_short = (extmd.get("LicenseShortName") or {}).get("value", "")
    license_url = (extmd.get("LicenseUrl") or {}).get("value", "")
    artist = (extmd.get("Artist") or {}).get("value", "")
    description = (extmd.get("ImageDescription") or {}).get("value", "")
    return ImageDetails(
        title=page.get("title") or file_title,
        url=info.get("url", ""),
        descriptionurl=info.get("descriptionurl", ""),
        width=int(info.get("width") or 0),
        height=int(info.get("height") or 0),
        mime=info.get("mime", ""),
        size_bytes=int(info.get("size") or 0),
        license_short=license_short,
        license_url=license_url,
        artist=artist,
        description=description,
    )


# ----------------------------------------------------- crop / save


def download_and_crop(details: ImageDetails, *,
                       target_size: tuple[int, int],
                       output_path: Path,
                       client=None,
                       allow_non_pd: bool = False) -> CroppedImage:
    """Download the image, center-crop to `target_size`, save as PNG.

    Refuses non-public-domain images unless `allow_non_pd=True`.
    The default is strict because the helper exists to give the
    user a no-friction lawful path; if the user wants a CC-BY image
    they should pass `--allow-non-pd` explicitly and add the
    attribution line manually.
    """
    if not details.is_public_domain and not allow_non_pd:
        raise ValueError(
            f"Image is licensed `{details.license_short!r}` — not PD/CC0. "
            f"Pass --allow-non-pd to use it anyway (you must record "
            f"attribution per the license)."
        )
    raw = _http_get_bytes(details.url, client=client)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from PIL import Image
    except ImportError as e:
        raise RuntimeError(
            "Pillow not installed. Install via `pipx inject autonovel "
            "Pillow` or `pip install autonovel[export]`."
        ) from e

    import io
    img = Image.open(io.BytesIO(raw))
    img = img.convert("RGB")  # drop alpha; cover output is opaque

    # Scale-then-center-crop so the target_size aspect is preserved
    # without distortion. The "letterbox" alternative (scale to fit,
    # pad with black) reads less polished for cover art.
    src_w, src_h = img.size
    tgt_w, tgt_h = target_size
    src_aspect = src_w / src_h
    tgt_aspect = tgt_w / tgt_h
    if src_aspect > tgt_aspect:
        # Source wider than target → crop sides.
        new_h = src_h
        new_w = int(round(src_h * tgt_aspect))
        left = (src_w - new_w) // 2
        crop_box = (left, 0, left + new_w, src_h)
    else:
        # Source taller than target → crop top/bottom.
        new_w = src_w
        new_h = int(round(src_w / tgt_aspect))
        top = (src_h - new_h) // 2
        crop_box = (0, top, src_w, top + new_h)
    cropped = img.crop(crop_box).resize(target_size, Image.LANCZOS)
    cropped.save(output_path, "PNG")

    artist_clean = _strip_html(details.artist) or "Unknown"
    attribution = (
        f"{artist_clean}, via Wikimedia Commons. "
        f"License: {details.license_short or 'public domain'}. "
        f"Source: {details.descriptionurl}"
    )
    return CroppedImage(
        output_path=output_path,
        original=details,
        crop_box=crop_box,
        final_size=target_size,
        attribution_line=attribution,
    )


def _strip_html(text: str) -> str:
    """Extract human-readable text from Commons' HTML-laden
    metadata fields. Conservative: drops tags, preserves text."""
    import re
    out = re.sub(r"<[^>]+>", " ", text or "")
    out = re.sub(r"\s+", " ", out).strip()
    return out
