"""Tier-1 tests for `export/wikimedia.py` and the
`autonovel mechanical wikimedia-search/-fetch` CLI subcommands.

Network calls are stubbed via a fake httpx.Client so the tests run
offline. Real Commons API responses (captured 2026-04-30) shape
the fixtures so structural changes upstream get caught.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from autonovel.export import wikimedia


# ----------------------------------------------------- HTTP stubs


@dataclass
class _FakeResponse:
    _payload: dict | bytes
    status_code: int = 200

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        if isinstance(self._payload, bytes):
            raise ValueError("not JSON")
        return self._payload

    @property
    def content(self) -> bytes:
        if isinstance(self._payload, bytes):
            return self._payload
        return json.dumps(self._payload).encode()


@dataclass
class _FakeClient:
    """Stub for httpx.Client. routes maps URL → payload."""
    routes: dict[str, _FakeResponse] = field(default_factory=dict)
    default: _FakeResponse | None = None
    calls: list[tuple[str, dict]] = field(default_factory=list)

    def get(self, url: str, *, params: dict | None = None,
            headers: dict | None = None) -> _FakeResponse:
        self.calls.append((url, dict(params or {})))
        # If params has `srsearch` (search) or `titles` (metadata),
        # route based on key. Otherwise this is a media-URL fetch.
        if params:
            key_value = params.get("srsearch") or params.get("titles")
            if key_value and key_value in self.routes:
                return self.routes[key_value]
        if url in self.routes:
            return self.routes[url]
        if self.default is not None:
            return self.default
        raise RuntimeError(f"unstubbed request: {url} {params}")


# ----------------------------------------------------- search


def test_search_images_returns_candidates() -> None:
    client = _FakeClient(routes={
        "Venice 1500 painting": _FakeResponse({
            "query": {
                "search": [
                    {"title": "File:Venice_de_Barbari_1500.jpg",
                     "pageid": 12345, "snippet": "<span>de Barbari panoramic"},
                    {"title": "File:Bellini_Doge_Loredan.jpg",
                     "pageid": 67890, "snippet": "Bellini portrait"},
                ]
            }
        })
    })
    candidates = wikimedia.search_images(
        "Venice 1500 painting", limit=5, client=client,
    )
    assert len(candidates) == 2
    assert candidates[0].title == "File:Venice_de_Barbari_1500.jpg"
    assert candidates[0].page_id == 12345
    assert "de Barbari" in candidates[0].snippet


def test_search_images_empty_response() -> None:
    client = _FakeClient(routes={
        "no-such-thing": _FakeResponse({"query": {"search": []}})
    })
    assert wikimedia.search_images("no-such-thing", client=client) == []


# ----------------------------------------------------- metadata


def _details_response(*, license_short: str = "PD-art-100") -> _FakeResponse:
    return _FakeResponse({
        "query": {
            "pages": [{
                "title": "File:Test.jpg",
                "imageinfo": [{
                    "url": "https://upload.wikimedia.org/test.jpg",
                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Test.jpg",
                    "width": 4096, "height": 3072,
                    "mime": "image/jpeg", "size": 1500000,
                    "extmetadata": {
                        "LicenseShortName": {"value": license_short},
                        "LicenseUrl": {"value": "https://example.org/lic"},
                        "Artist": {"value": "<a>Albrecht Dürer</a>"},
                        "ImageDescription": {"value": "Portrait of Jakob Fugger."},
                    }
                }]
            }]
        }
    })


def test_fetch_metadata_extracts_license_artist_dimensions() -> None:
    client = _FakeClient(routes={"File:Test.jpg": _details_response()})
    details = wikimedia.fetch_image_metadata("File:Test.jpg", client=client)
    assert details is not None
    assert details.url.endswith(".jpg")
    assert details.width == 4096
    assert details.height == 3072
    assert details.license_short == "PD-art-100"
    # HTML in artist field is preserved (caller does the strip in
    # download_and_crop's attribution line).
    assert "Dürer" in details.artist


def test_fetch_metadata_missing_page() -> None:
    client = _FakeClient(routes={
        "File:Nonexistent.jpg": _FakeResponse({
            "query": {"pages": [{"title": "File:Nonexistent.jpg",
                                  "missing": True}]}
        })
    })
    assert wikimedia.fetch_image_metadata(
        "File:Nonexistent.jpg", client=client,
    ) is None


def test_is_public_domain_detects_PD_and_CC0() -> None:
    pd_details = wikimedia.fetch_image_metadata.__wrapped__ if hasattr(
        wikimedia.fetch_image_metadata, "__wrapped__") else None
    # Test the predicate directly.
    for license_short in ("PD-art-100", "Public domain", "CC0", "CC-zero"):
        d = wikimedia.ImageDetails(
            title="x", url="x", descriptionurl="x", width=1, height=1,
            mime="image/jpeg", size_bytes=1, license_short=license_short,
        )
        assert d.is_public_domain, f"failed for {license_short}"


def test_is_public_domain_rejects_cc_by_and_others() -> None:
    for license_short in ("CC-BY-SA-4.0", "CC-BY-3.0", "GFDL", ""):
        d = wikimedia.ImageDetails(
            title="x", url="x", descriptionurl="x", width=1, height=1,
            mime="image/jpeg", size_bytes=1, license_short=license_short,
        )
        assert not d.is_public_domain, f"failed for {license_short}"


# ----------------------------------------------------- download + crop


def _make_test_jpeg_bytes(width: int = 600, height: int = 800) -> bytes:
    """Generate a minimal in-memory JPEG of the given dimensions."""
    PIL = pytest.importorskip("PIL")
    from PIL import Image
    img = Image.new("RGB", (width, height), (128, 64, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def test_download_and_crop_writes_png_with_target_aspect(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image
    raw = _make_test_jpeg_bytes(width=800, height=400)  # 2:1 source
    media_url = "https://upload.wikimedia.org/test.jpg"
    client = _FakeClient(routes={media_url: _FakeResponse(raw)})
    details = wikimedia.ImageDetails(
        title="File:Test.jpg",
        url=media_url,
        descriptionurl="https://commons.wikimedia.org/wiki/File:Test.jpg",
        width=800, height=400,
        mime="image/jpeg", size_bytes=len(raw),
        license_short="PD-art-100",
        artist="<a>Renata Calvi</a>",
    )
    output = tmp_path / "art" / "variants" / "cover_01.png"
    result = wikimedia.download_and_crop(
        details,
        target_size=(1024, 1536),  # 2:3 cover aspect
        output_path=output,
        client=client,
    )
    assert output.is_file()
    img = Image.open(output)
    assert img.size == (1024, 1536)
    assert "Renata Calvi" in result.attribution_line
    assert "PD-art-100" in result.attribution_line


def test_download_and_crop_refuses_non_pd_by_default(tmp_path: Path) -> None:
    raw = _make_test_jpeg_bytes()
    details = wikimedia.ImageDetails(
        title="File:CC-BY.jpg",
        url="https://upload.wikimedia.org/cc.jpg",
        descriptionurl="https://commons.wikimedia.org/wiki/File:CC-BY.jpg",
        width=800, height=600,
        mime="image/jpeg", size_bytes=len(raw),
        license_short="CC-BY-4.0",
    )
    client = _FakeClient(routes={
        "https://upload.wikimedia.org/cc.jpg": _FakeResponse(raw)
    })
    with pytest.raises(ValueError, match="not PD/CC0"):
        wikimedia.download_and_crop(
            details, target_size=(100, 100),
            output_path=tmp_path / "x.png", client=client,
        )


def test_download_and_crop_allow_non_pd_overrides(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    raw = _make_test_jpeg_bytes()
    details = wikimedia.ImageDetails(
        title="File:CC-BY.jpg",
        url="https://upload.wikimedia.org/cc.jpg",
        descriptionurl="https://commons.wikimedia.org/wiki/File:CC-BY.jpg",
        width=800, height=600,
        mime="image/jpeg", size_bytes=len(raw),
        license_short="CC-BY-4.0",
        artist="Some Photographer",
    )
    client = _FakeClient(routes={
        "https://upload.wikimedia.org/cc.jpg": _FakeResponse(raw)
    })
    output = tmp_path / "out.png"
    result = wikimedia.download_and_crop(
        details, target_size=(200, 300),
        output_path=output, client=client,
        allow_non_pd=True,
    )
    assert output.is_file()
    assert "CC-BY-4.0" in result.attribution_line


# ----------------------------------------------------- HTML strip


def test_strip_html_removes_tags_and_collapses_whitespace() -> None:
    raw = '<a href="x">Albrecht  <b>Dürer</b></a>\n  (1471–1528)'
    assert wikimedia._strip_html(raw) == "Albrecht Dürer (1471–1528)"


def test_strip_html_handles_empty() -> None:
    assert wikimedia._strip_html("") == ""
    assert wikimedia._strip_html(None) == ""  # type: ignore[arg-type]


# ----------------------------------------------------- CLI


def test_cli_wikimedia_search_basic(monkeypatch: pytest.MonkeyPatch,
                                       tmp_path: Path) -> None:
    """The CLI invokes search_images directly; we monkey-patch the
    helper to return a deterministic result instead of mocking
    httpx for a full subprocess test."""
    fake = [
        wikimedia.ImageCandidate(title="File:A.jpg", page_id=1, snippet="a"),
        wikimedia.ImageCandidate(title="File:B.jpg", page_id=2, snippet="b"),
    ]

    def fake_search(query: str, *, limit: int = 10, client=None):
        return fake[:limit]

    monkeypatch.setattr(wikimedia, "search_images", fake_search)
    # Reach into the CLI handler directly.
    from autonovel.mechanical.__main__ import _cmd_wikimedia_search
    import argparse
    args = argparse.Namespace(query="Venice", limit=2, detailed=False)
    import io as _io
    import contextlib
    out = _io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = _cmd_wikimedia_search(args)
    assert rc == 0
    payload = json.loads(out.getvalue())
    assert payload["query"] == "Venice"
    assert len(payload["results"]) == 2
    assert payload["results"][0]["title"] == "File:A.jpg"
