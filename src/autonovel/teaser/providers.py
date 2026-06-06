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


# Conservative, research-grounded values (PRD §7, 2026-06-05). Re-verify
# before relying — these move fast.
PROVIDERS: dict[str, ProviderProfile] = {
    # `generic` = provider-agnostic default for Phase 1; an 8 s cap is a
    # safe middle (Veo 4/6/8, Runway 5/10, Luma 5, Pollinations ~5).
    "generic": ProviderProfile("generic", 8.0, True, True, "reference-image", "generic"),
    # Free no-auth default backend (PRD §22): image+video+audio, Wan-Fast
    # keyframes for consistency.
    "pollinations": ProviderProfile("pollinations", 5.0, True, False, "keyframe", "generic"),
    "veo": ProviderProfile("veo", 8.0, True, True, "3-reference-images", "veo"),
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
