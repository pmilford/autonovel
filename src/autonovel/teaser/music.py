"""Text-to-music backend for the cohesive trailer bed (Phase 9).

Real trailers ride **one continuous** score (teaser-craft §0/§7). Until
now that bed had to be a file the user supplied to
``teaser-assemble --audio``; this module generates it from a prompt — by
default the teaser spine's ``score_direction`` — so the teaser can score
itself, then the result is laid under the whole cut (ducked beneath the
dialogue) exactly as a user-supplied track would be.

Same disciplines as ``backends.py``: key resolution (``--token`` → env →
``.env``), an injectable HTTP client seam for tests, and a typed
``RenderError``. Providers:

  - **``stub``** — offline, zero-key: writes a valid **silent** WAV of the
    requested length (stdlib ``wave``), so the whole flow (generate → bed →
    assemble) can be rehearsed for $0 before spending a real call.
  - **``musicgen``** — Hugging Face Inference API (``facebook/musicgen-*``),
    free tier with an ``HF_TOKEN``; returns audio bytes.
  - **``elevenlabs``** — ElevenLabs music/sound API (``ELEVENLABS_API_KEY``).

Python does HTTP + a silent-WAV writer only; no LLM, no quality judgement.
"""

from __future__ import annotations

import os
import wave
from pathlib import Path
from typing import Any

from .backends import RenderError, resolve_key as _resolve_key

# Provider → env var names for the key (mirrors backends.ENV_VARS).
MUSIC_ENV: dict[str, tuple[str, ...]] = {
    "musicgen": ("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN"),
    "elevenlabs": ("ELEVENLABS_API_KEY", "ELEVEN_API_KEY"),
}

MUSIC_KEY_HELP: dict[str, str] = {
    "musicgen": "free Hugging Face token at https://huggingface.co/settings/tokens "
                "(HF_TOKEN) — runs facebook/musicgen-small on the Inference API",
    "elevenlabs": "key at https://elevenlabs.io (ELEVENLABS_API_KEY)",
}

MUSIC_PROVIDERS = ("stub", "musicgen", "elevenlabs")

# Provider → output file extension.
_EXT = {"stub": "wav", "musicgen": "flac", "elevenlabs": "mp3"}

_DEFAULT_PROMPT = "cinematic trailer score, single building cue, orchestral, tense, no vocals"


def music_key(provider: str, *, token: str | None = None) -> str | None:
    """Resolve a music backend key (token → env → .env)."""
    if token:
        return token
    # reuse backends' .env loader via resolve_key against a temp mapping
    if provider == "stub":
        return None
    for name in MUSIC_ENV.get(provider, ()):
        val = os.environ.get(name)
        if val:
            return val
    # fall through to the shared .env loader (loads once) and retry
    _resolve_key("__noop__")  # triggers _load_dotenv_once
    for name in MUSIC_ENV.get(provider, ()):
        val = os.environ.get(name)
        if val:
            return val
    return None


def needs_key(provider: str) -> bool:
    return provider in ("musicgen", "elevenlabs")


def output_ext(provider: str) -> str:
    return _EXT.get(provider, "wav")


def _write_silent_wav(path: Path, seconds: float, *, rate: int = 44100) -> None:
    """Write a valid stereo 16-bit silent WAV of ``seconds`` (offline stub
    bed; lets the generate→assemble chain be tested for $0)."""
    frames = max(1, int(rate * max(0.1, seconds)))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00\x00\x00" * frames)  # L+R 16-bit zero


def _musicgen_bytes(prompt: str, *, key: str, duration_s: float, model: str | None,
                    client: Any) -> bytes:
    """Hugging Face Inference API text-to-music → audio bytes."""
    mdl = model or "facebook/musicgen-small"
    url = f"https://api-inference.huggingface.co/models/{mdl}"
    headers = {"Authorization": f"Bearer {key}"}
    payload = {"inputs": prompt,
               "parameters": {"duration": int(max(1, duration_s))}}
    resp = client.post(url, headers=headers, json=payload)
    status = getattr(resp, "status_code", 200)
    if status in (401, 403):
        raise RenderError("musicgen: auth failed — check HF_TOKEN", kind="auth")
    if status == 402:
        raise RenderError("musicgen: payment required (HF quota)", kind="payment")
    if status >= 400:
        raise RenderError(f"musicgen: HTTP {status}", kind="http")
    return resp.content


def _elevenlabs_bytes(prompt: str, *, key: str, duration_s: float, client: Any) -> bytes:
    url = "https://api.elevenlabs.io/v1/sound-generation"
    headers = {"xi-api-key": key}
    payload = {"text": prompt, "duration_seconds": float(max(0.5, min(22.0, duration_s)))}
    resp = client.post(url, headers=headers, json=payload)
    status = getattr(resp, "status_code", 200)
    if status in (401, 403):
        raise RenderError("elevenlabs: auth failed — check ELEVENLABS_API_KEY", kind="auth")
    if status >= 400:
        raise RenderError(f"elevenlabs: HTTP {status}", kind="http")
    return resp.content


def generate_bed(
    prompt: str,
    out_path: Path,
    *,
    provider: str = "stub",
    duration_s: float = 30.0,
    token: str | None = None,
    model: str | None = None,
    client: Any = None,
) -> Path:
    """Generate one music bed from ``prompt`` to ``out_path`` and return it.

    ``stub`` writes a silent WAV offline (no key). The real backends POST to
    a text-to-music API via the injectable ``client`` (an httpx-like object;
    one real ``httpx.Client`` is opened when none is given). Raises
    ``RenderError`` (typed) on auth/payment/HTTP failure or a missing key.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prompt = (prompt or "").strip() or _DEFAULT_PROMPT

    if provider == "stub":
        _write_silent_wav(out_path, duration_s)
        return out_path

    key = music_key(provider, token=token)
    if not key:
        raise RenderError(
            f"{provider}: no API key — {MUSIC_KEY_HELP.get(provider, 'set the key')}",
            kind="auth")

    if client is None:  # pragma: no cover - real network path
        import httpx
        client = httpx.Client(timeout=180, follow_redirects=True)

    if provider == "musicgen":
        data = _musicgen_bytes(prompt, key=key, duration_s=duration_s,
                               model=model, client=client)
    elif provider == "elevenlabs":
        data = _elevenlabs_bytes(prompt, key=key, duration_s=duration_s, client=client)
    else:
        raise RenderError(f"unknown music provider: {provider}", kind="unsupported")
    out_path.write_bytes(data)
    return out_path
