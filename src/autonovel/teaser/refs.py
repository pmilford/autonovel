"""Reference-image consistency plan for a teaser (PRD §10; teaser-craft §6).

Character/location identity drifts across separately-generated clips. The
fix is a **canonical reference image** per recurring subject, fed as the
reference / first frame of every clip with that subject, plus the exact
same appearance string in every prompt. This module answers the
mechanical half of that workflow — *which* reference images a teaser
needs, *where* they live, *which shots* use each, and which already exist
— so the user never has to `ls`/`grep` the refs dir
(``feedback_no_shell_in_user_workflow``).

It plans; it does not generate. Images come from the existing art
pipeline (`/autonovel:art-curate`), a shared `shared/art_references/`
plate, or the Phase-3.5 Pollinations render adapter. Quality is never
judged here — only presence on disk (a filesystem fact).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .shots import Teaser

# Image extensions we treat as a usable reference plate.
_IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def slug(name: str) -> str:
    """A filesystem-safe slug for a subject name (e.g. 'Jakob Fugger'
    → 'jakob_fugger'). Used to default a ref path and to match an
    existing plate in shared/art_references/."""
    s = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    return s.strip("_") or "subject"


@dataclass
class RefEntry:
    subject: str
    appearance: str            # the canonical (first-seen) appearance string
    ref_path: str              # the path shots reference (or the default)
    shots: list[str] = field(default_factory=list)
    exists: bool = False
    source: str = "missing"    # "teaser" | "art_references" | "missing"
    appearance_variants: int = 1  # >1 ⇒ drift (also flagged by critique)
    suggested_ref: str | None = None  # a matching shared plate, when found

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "appearance": self.appearance,
            "ref_path": self.ref_path,
            "shots": list(self.shots),
            "exists": self.exists,
            "source": self.source,
            "appearance_variants": self.appearance_variants,
            "suggested_ref": self.suggested_ref,
        }


@dataclass
class RefsPlan:
    entries: list[RefEntry] = field(default_factory=list)

    @property
    def missing(self) -> list[RefEntry]:
        return [e for e in self.entries if not e.exists]

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_count": len(self.entries),
            "missing_count": len(self.missing),
            "entries": [e.to_dict() for e in self.entries],
        }


def _find_shared_plate(art_references_dir: Path | None, subj_slug: str) -> Path | None:
    if not art_references_dir or not art_references_dir.is_dir():
        return None
    for ext in _IMG_EXTS:
        cand = art_references_dir / f"{subj_slug}{ext}"
        if cand.exists():
            return cand
    # Looser match: any image whose stem contains the slug.
    for p in sorted(art_references_dir.iterdir()):
        if p.suffix.lower() in _IMG_EXTS and subj_slug in p.stem.lower():
            return p
    return None


def plan_refs(
    teaser: Teaser,
    base_dir: Path | None = None,
    art_references_dir: Path | None = None,
) -> RefsPlan:
    """Build the per-subject reference-image plan.

    ``base_dir`` is the teaser directory (paths in ``reference_image`` are
    resolved against it to test existence). ``art_references_dir`` is an
    optional shared plate library (e.g. ``shared/art_references/``) used as
    a fallback source. Pure structure + filesystem-existence; no LLM.
    """
    # Group shots by named subject, preserving first-seen order.
    order: list[str] = []
    grouped: dict[str, list] = {}
    for s in teaser.shots:
        if not s.subject_name:
            continue
        if s.subject_name not in grouped:
            grouped[s.subject_name] = []
            order.append(s.subject_name)
        grouped[s.subject_name].append(s)

    entries: list[RefEntry] = []
    for name in order:
        group = grouped[name]
        appearances = [g.subject_appearance.strip() for g in group if g.subject_appearance]
        appearance = appearances[0] if appearances else ""
        variants = len(set(appearances))
        ref_paths = [g.reference_image for g in group if g.reference_image]
        ref_path = ref_paths[0] if ref_paths else f"refs/{slug(name)}.png"

        exists = False
        source = "missing"
        suggested: str | None = None
        if base_dir is not None and (base_dir / ref_path).exists():
            exists, source = True, "teaser"
        else:
            plate = _find_shared_plate(art_references_dir, slug(name))
            if plate is not None:
                exists, source = True, "art_references"
                suggested = str(plate)

        entries.append(RefEntry(
            subject=name, appearance=appearance, ref_path=ref_path,
            shots=[g.id for g in group], exists=exists, source=source,
            appearance_variants=max(1, variants), suggested_ref=suggested,
        ))
    return RefsPlan(entries=entries)
