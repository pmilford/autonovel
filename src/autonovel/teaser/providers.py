"""Video-provider capability table.

**Data, not logic** — provider capabilities are fast-moving (versions,
audio, clip caps, consistency primitives all shift monthly; see
``docs/prd-movie-teaser-mode.md`` §7). Keeping them as a plain table
means updating a capability never touches generation logic.

Phase 1 only needs each provider's *native clip cap*, whether it has
*native audio*, whether it exposes a *separate negative-prompt field*,
its *consistency primitive*, and a *render dialect* key. Phase 2 fills
in per-dialect render rules; until then every dialect renders via the
``generic`` path (see ``render_prompt``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderProfile:
    name: str
    max_clip_s: float       # native clip length cap (seconds)
    audio: bool             # native synchronised audio (dialogue + SFX)
    separate_negative: bool  # supports a dedicated negative-prompt field
    consistency: str        # short label of the consistency primitive
    dialect: str            # render-dialect key (Phase 2 refines)
    # --- render-backend capabilities (Phase 4: real free backends) ---
    kinds: tuple[str, ...] = ("video",)   # which media this backend renders
    needs_key: bool = False               # requires an API key/token
    min_interval_s: float = 0.0           # polite default delay between calls
    free_note: str = ""                   # one-line free-tier summary


# Conservative, research-grounded values (PRD §7; backend rows verified
# 2026-06-06, see docs/teaser-render-providers.md). These move fast — the
# table is data, not logic, so a capability change never touches code.
PROVIDERS: dict[str, ProviderProfile] = {
    # `generic` = provider-agnostic default for planning; an 8 s cap is a
    # safe middle (Veo 4/6/8, Runway 5/10, Luma 5).
    "generic": ProviderProfile(
        "generic", 8.0, True, True, "reference-image", "generic",
        kinds=("image", "video"),
    ),
    # Pollinations: the free no-key promise is DEAD for video (every
    # generate endpoint now needs a Bearer key; video models cost real
    # Pollen). Kept only for free `flux` keyframe IMAGES — and even those
    # now need a free account token. images-only here.
    "pollinations": ProviderProfile(
        "pollinations", 5.0, False, False, "keyframe", "generic",
        kinds=("image",), needs_key=False, min_interval_s=15.0,
        free_note="free flux keyframe images (free account token; ~1 req/15s)",
    ),
    # Offline placeholder backend — synthesizes a PNG keyframe per shot
    # locally (Pillow). NO network, NO key, NO quota. Validate the whole
    # render→cut-list→assemble chain for free BEFORE spending a real
    # backend's limited free generations.
    "stub": ProviderProfile(
        "stub", 8.0, False, False, "none", "generic",
        kinds=("image",), needs_key=False, min_interval_s=0.0,
        free_note="offline placeholder keyframes — no network/key/quota; "
                  "validate the pipeline before spending grok",
    ),
    # Gemini native image generation ("Nano Banana"): reference-conditioned,
    # photoreal stills. THE image backend for character consistency — every
    # shot is conditioned on the subject's canonical reference portrait, so a
    # face holds across separately-generated keyframes. Models (June 2026):
    #   gemini-3.1-flash-image-preview  Nano Banana 2 (default; ~$0.045/img, 4K)
    #   gemini-2.5-flash-image          Nano Banana   (~$0.039/img)
    #   gemini-3-pro-image              Nano Banana Pro (~$0.134/img; best text)
    "gemini": ProviderProfile(
        "gemini", 8.0, False, True, "reference-images", "generic",
        kinds=("image",), needs_key=True, min_interval_s=1.0,
        free_note="Gemini image (Nano Banana 2/Pro); reference-conditioned "
                  "photoreal stills, ~$0.04–0.13/img; key: GEMINI_API_KEY",
    ),
    # xAI Grok Imagine — DEFAULT free video backend: native dialogue +
    # music + SFX, no credit card, 5 free gens/day + $25 signup credit.
    "grok": ProviderProfile(
        "grok", 15.0, True, False, "image-to-video", "generic",
        kinds=("video",), needs_key=True, min_interval_s=1.0,
        free_note="5 free gens/day + $25 signup, no card; native dialogue+music",
    ),
    # kie.ai reseller — one key fronts Veo3/Kling2.6/Grok/Seedance, all
    # with audio. 80 free credits, never expire, no card.
    "kie": ProviderProfile(
        "kie", 10.0, True, True, "model-dependent", "generic",
        kinds=("video",), needs_key=True, min_interval_s=1.0,
        free_note="80 free credits (no card); Veo3/Kling/Grok/Seedance w/ audio",
    ),
    # Veo via Gemini API / Vertex — premium scriptable, native audio.
    # Free only on a new account's $300 GCP credit (Vertex path).
    "veo": ProviderProfile(
        "veo", 8.0, True, True, "3-reference-images", "veo",
        kinds=("video",), needs_key=True, min_interval_s=2.0,
        free_note="$300 GCP new-account credit (Vertex); native audio, top quality",
    ),
    # Magic Hour — recurring free (100 credits/day + 400 signup), no card,
    # but SILENT video (layer an audio bed in teaser-assemble).
    "magichour": ProviderProfile(
        "magichour", 10.0, False, False, "single-reference", "generic",
        kinds=("video",), needs_key=True, min_interval_s=1.0,
        free_note="400 signup + 100 credits/day forever, no card; silent",
    ),
    # fal.ai — $20 one-time signup credit, no card; many models (audio
    # depends on the chosen model).
    "fal": ProviderProfile(
        "fal", 10.0, True, True, "model-dependent", "generic",
        kinds=("image", "video"), needs_key=True, min_interval_s=1.0,
        free_note="$20 one-time signup credit, no card; image (flux-kontext/"
                  "pulid reference-conditioned) + model-dependent video audio",
    ),
    # Flow (labs.google/flow) on a Google AI Pro sub — highest quality +
    # native audio, but GUI-ONLY: no API. teaser-render treats it as a
    # MANUAL backend (print instructions, watch the clips dir).
    "flow": ProviderProfile(
        "flow", 8.0, True, False, "scene-builder", "veo",
        kinds=("video",), needs_key=False, min_interval_s=0.0,
        free_note="manual (Flow GUI, ~50 Veo-Fast clips/mo on AI Pro); import MP4s",
    ),
    "sora": ProviderProfile("sora", 12.0, True, False, "characters+input_reference", "sora"),
    "runway": ProviderProfile("runway", 10.0, False, False, "single-reference", "runway"),
    "kling": ProviderProfile("kling", 10.0, True, True, "face/char-ref", "generic"),
    "luma": ProviderProfile("luma", 5.0, False, False, "keyframes", "luma"),
}

DEFAULT_PROVIDER = "generic"


def get(name: str | None) -> ProviderProfile:
    """Return the named provider profile, falling back to ``generic``."""
    if not name:
        return PROVIDERS[DEFAULT_PROVIDER]
    return PROVIDERS.get(name, PROVIDERS[DEFAULT_PROVIDER])


def known_providers() -> list[str]:
    return sorted(PROVIDERS)
