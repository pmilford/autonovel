"""Character-reference manifest + approval status (Phase 5).

`refs.py` answers *which* reference images a teaser needs and whether they
exist on disk. This module adds the **deliberate, per-book layer the user
asked for**: a declared *source* for each recurring subject (a public-
domain painting/sketch, a local image, or "generate"), the constraints
that govern it (period dress, age, likeness), and an **approval gate** —
a subject's reference must be *approved/locked* before any real (paid /
quota-bearing) generation uses it. The offline `stub` backend is exempt,
so the whole flow can be rehearsed for free.

Example, for the Fugger book:

    subjects:
      - subject: JAKOB FUGGER
        source: wikimedia
        source_ref: "File:Albrecht Dürer - Jakob Fugger der Reiche.jpg"
        appearance: "late-middle-age merchant, fur-collared coat, gold cap"
        constraints: "1500s Augsburg; likeness from the Dürer portrait"
        morph: true            # morph the source into each shot's framing
        status: pending         # pending → approved → locked
        ref_path: refs/jakob_fugger.png
      - subject: MATTHAUS SCHWARZ
        source: wikimedia
        source_ref: "File:Schwarz 1526.jpg"   # the Klaidungsbüchlein sketches
        appearance: "young clerk in fashionable doublet"
        status: pending

Mechanical only — it declares, plans, and gates. The *picking* and
*approving* (and the actual fetch/morph) are the LLM/interactive steps in
`/autonovel:teaser-refs`; quality is never judged here
(`feedback_avoid_brittle_python`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import refs as _refs
from .shots import Teaser

SOURCE_KINDS = ("wikimedia", "local", "generate")
STATUSES = ("pending", "approved", "locked")

# next_action codes (one per subject) — what the user/command must do next.
ACTIONS = (
    "declare-source",  # no manifest entry yet
    "fetch-source",    # declared wikimedia/local source, not on disk yet
    "generate",        # source=generate, no plate on disk yet
    "approve",         # plate exists but status is still pending
    "ready",           # exists + approved/locked → usable for real renders
)


KINDS = ("character", "location", "prop")


@dataclass
class CharacterRef:
    subject: str
    source: str = "generate"      # wikimedia | local | generate
    source_ref: str = ""          # "File:..." | local path | ""
    appearance: str = ""          # canonical appearance string (lock it)
    constraints: str = ""         # period/age/likeness notes for the prompt
    morph: bool = True            # morph the source into shot framing vs verbatim
    status: str = "pending"       # pending | approved | locked
    ref_path: str = ""            # teaser-relative path to the approved plate
    kind: str = "character"       # character | location | prop (ordering hint)
    shots: list[str] = field(default_factory=list)  # shot ids this subject is in
    # --- voice (Phase 5.6): the locked voice the video model is steered to
    # produce. `voice` is the base descriptor; `voice_ages` are named age
    # variants (each {name, descriptor, from_year?, to_year?}); `birth_year`
    # lets a shot's story_year auto-select the right variant. ---
    voice: str = ""
    birth_year: int | None = None
    voice_ages: list[dict[str, Any]] = field(default_factory=list)
    # --- appearance age ladder (Phase 7): named age variants of the
    # *visual* appearance string, parallel to voice_ages. Each is
    # {name, appearance, from_year?, to_year?}; a shot's story_year picks
    # the right life-stage so the prompt text matches the age-correct
    # reference image (boy 14 → youth 18 → man 40 → elder 62). The actual
    # lineage-morphed plates are still produced interactively; this is the
    # selection + prompt-sync half. ---
    appearance_ages: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"subject": self.subject, "source": self.source}
        if self.source_ref:
            d["source_ref"] = self.source_ref
        if self.appearance:
            d["appearance"] = self.appearance
        if self.constraints:
            d["constraints"] = self.constraints
        d["morph"] = self.morph
        d["status"] = self.status
        if self.ref_path:
            d["ref_path"] = self.ref_path
        if self.kind != "character":
            d["kind"] = self.kind
        if self.shots:
            d["shots"] = list(self.shots)
        if self.voice:
            d["voice"] = self.voice
        if self.birth_year is not None:
            d["birth_year"] = self.birth_year
        if self.voice_ages:
            d["voice_ages"] = [dict(v) for v in self.voice_ages]
        if self.appearance_ages:
            d["appearance_ages"] = [dict(v) for v in self.appearance_ages]
        return d

    @property
    def approved(self) -> bool:
        return self.status in ("approved", "locked")

    def resolve_voice(self, year: int | None = None) -> str:
        """Resolve the voice descriptor for an in-story ``year`` (Phase
        5.6). With ``year`` and age variants, pick the variant whose
        ``from_year``/``to_year`` window contains it (open-ended bounds
        allowed), else the variant whose ``from_year`` is the latest one
        not after ``year``; fall back to the base ``voice``."""
        base = self.voice
        if year is None or not self.voice_ages:
            return base
        # Exact window match first.
        best: dict[str, Any] | None = None
        best_from = None
        for v in self.voice_ages:
            lo = v.get("from_year")
            hi = v.get("to_year")
            if (lo is None or year >= lo) and (hi is None or year <= hi):
                desc = (v.get("descriptor") or "").strip()
                if desc:
                    return desc
            # Track the latest from_year <= year as a fallback.
            if lo is not None and year >= lo and (best_from is None or lo > best_from):
                best, best_from = v, lo
        if best and (best.get("descriptor") or "").strip():
            return best["descriptor"].strip()
        return base

    def age_variant_name(self, year: int | None = None) -> str:
        """The variant *name* chosen for ``year`` (for reporting)."""
        if year is None or not self.voice_ages:
            return "base"
        for v in self.voice_ages:
            lo, hi = v.get("from_year"), v.get("to_year")
            if (lo is None or year >= lo) and (hi is None or year <= hi):
                return str(v.get("name") or "?")
        return "base"

    def resolve_appearance(self, year: int | None = None) -> str:
        """Resolve the appearance string for an in-story ``year`` (Phase 7),
        mirroring :meth:`resolve_voice`: exact age-window match first, else
        the latest ``from_year`` not after ``year``, else the base
        ``appearance``. Returns "" when nothing is set."""
        base = self.appearance
        if year is None or not self.appearance_ages:
            return base
        best: dict[str, Any] | None = None
        best_from = None
        for v in self.appearance_ages:
            lo = v.get("from_year")
            hi = v.get("to_year")
            if (lo is None or year >= lo) and (hi is None or year <= hi):
                desc = (v.get("appearance") or "").strip()
                if desc:
                    return desc
            if lo is not None and year >= lo and (best_from is None or lo > best_from):
                best, best_from = v, lo
        if best and (best.get("appearance") or "").strip():
            return best["appearance"].strip()
        return base


@dataclass
class RefManifest:
    subjects: list[CharacterRef] = field(default_factory=list)

    def get(self, subject: str) -> CharacterRef | None:
        """Case/spacing-insensitive lookup by subject name (slug match)."""
        want = _refs.slug(subject)
        for cr in self.subjects:
            if _refs.slug(cr.subject) == want:
                return cr
        return None

    def to_dict(self) -> dict[str, Any]:
        return {"subjects": [c.to_dict() for c in self.subjects]}


def load(path: Path) -> RefManifest:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: refs manifest must be a mapping with a "
                         f"`subjects:` list, got {type(raw).__name__}.")
    subs_raw = raw.get("subjects") or []
    subjects: list[CharacterRef] = []
    for entry in subs_raw:
        if not isinstance(entry, dict) or not entry.get("subject"):
            continue
        src = str(entry.get("source", "generate"))
        if src not in SOURCE_KINDS:
            src = "generate"
        status = str(entry.get("status", "pending"))
        if status not in STATUSES:
            status = "pending"
        kind = str(entry.get("kind", "character"))
        if kind not in KINDS:
            kind = "character"
        shots_raw = entry.get("shots") or []
        shots = [str(s) for s in shots_raw] if isinstance(shots_raw, list) else []
        ages_raw = entry.get("voice_ages") or []
        voice_ages = [dict(v) for v in ages_raw if isinstance(v, dict)]
        app_ages_raw = entry.get("appearance_ages") or []
        appearance_ages = [dict(v) for v in app_ages_raw if isinstance(v, dict)]
        birth = entry.get("birth_year")
        subjects.append(CharacterRef(
            subject=str(entry["subject"]),
            source=src,
            source_ref=str(entry.get("source_ref", "")),
            appearance=str(entry.get("appearance", "")),
            constraints=str(entry.get("constraints", "")),
            morph=bool(entry.get("morph", True)),
            status=status,
            ref_path=str(entry.get("ref_path", "")),
            kind=kind,
            shots=shots,
            voice=str(entry.get("voice", "")),
            birth_year=(int(birth) if isinstance(birth, (int, float)) else None),
            voice_ages=voice_ages,
            appearance_ages=appearance_ages,
        ))
    return RefManifest(subjects=subjects)


def dump(manifest: RefManifest, path: Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Character-reference manifest (autonovel teaser, Phase 5).\n"
        "# Declare a source per recurring subject, lock the appearance, and\n"
        "# approve each reference before spending a real render. See\n"
        "# docs/teaser-render-providers.md + /autonovel:teaser-refs.\n"
        "# source: wikimedia (File:... PD art) | local (a path) | generate\n"
        "# status: pending -> approved -> locked\n"
    )
    body = yaml.safe_dump(manifest.to_dict(), sort_keys=False, allow_unicode=True)
    p.write_text(header + body, encoding="utf-8")


def scaffold_from_teaser(
    teaser: Teaser,
    *,
    base_dir: Path | None = None,
    art_references_dir: Path | None = None,
    include_locations: bool = False,
    preserve: "RefManifest | None" = None,
) -> RefManifest:
    """Build a starter manifest from the teaser's auto reference plan —
    one `pending` subject each, appearance pre-filled, source guessed
    (`local` if a plate already exists, else `generate`). With
    ``include_locations`` (Phase 7), distinct settings are scaffolded as
    `kind: location` subjects too, so a period place gets its own locked,
    anachronism-guarded plate.

    **Non-destructive merge (data-loss fix).** When ``preserve`` is given
    (the existing ``refs.yaml`` on a re-scaffold / ``--init --force``), an
    already-declared subject is **kept verbatim** — its source, locked
    appearance/constraints, approval ``status``, voice + age ladders, and
    ``ref_path`` survive; only its ``shots`` list (and any not-yet-set
    fields) refresh from the new plan. Subjects that exist in ``preserve``
    but are no longer in the teaser are also retained, so a hand-locked
    plate is never silently dropped because a shot was renamed.
    """
    plan = _refs.plan_refs(teaser, base_dir=base_dir,
                           art_references_dir=art_references_dir,
                           include_locations=include_locations)
    subjects: list[CharacterRef] = []
    used_slugs: set[str] = set()
    for e in plan.entries:
        used_slugs.add(_refs.slug(e.subject))
        prior = preserve.get(e.subject) if preserve else None
        if prior is not None:
            # Keep the declared/locked entry; just refresh the shot mapping
            # (and backfill an appearance/ref_path if they were never set).
            prior.shots = list(e.shots)
            if not prior.appearance:
                prior.appearance = e.appearance
            if not prior.ref_path:
                prior.ref_path = e.ref_path
            if prior.kind == "character" and e.kind != "character":
                prior.kind = e.kind
            subjects.append(prior)
            continue
        source = "local" if e.exists else "generate"
        source_ref = e.suggested_ref or "" if e.exists else ""
        subjects.append(CharacterRef(
            subject=e.subject,
            source=source,
            source_ref=source_ref,
            appearance=e.appearance,
            ref_path=e.ref_path,
            status="pending",
            kind=e.kind,
            shots=list(e.shots),
        ))
    # Retain declared subjects no longer in the plan (e.g. a renamed shot) so
    # locked work is never lost.
    if preserve is not None:
        for cr in preserve.subjects:
            if _refs.slug(cr.subject) not in used_slugs:
                subjects.append(cr)
    return RefManifest(subjects=subjects)


@dataclass
class RefStatusRow:
    subject: str
    shots: list[str]
    source: str
    source_ref: str
    status: str
    exists: bool
    appearance_variants: int
    next_action: str
    ref_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "shots": list(self.shots),
            "source": self.source,
            "source_ref": self.source_ref,
            "status": self.status,
            "exists": self.exists,
            "appearance_variants": self.appearance_variants,
            "next_action": self.next_action,
            "ref_path": self.ref_path,
        }


@dataclass
class RefStatus:
    rows: list[RefStatusRow] = field(default_factory=list)

    @property
    def ready(self) -> list[RefStatusRow]:
        return [r for r in self.rows if r.next_action == "ready"]

    @property
    def blocked(self) -> list[RefStatusRow]:
        return [r for r in self.rows if r.next_action != "ready"]

    def unapproved_subjects(self) -> list[str]:
        """Subjects used by shots that are NOT yet approved/locked — the
        approval gate for real (quota-bearing) renders."""
        return [r.subject for r in self.rows if r.next_action != "ready"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_count": len(self.rows),
            "ready_count": len(self.ready),
            "blocked_count": len(self.blocked),
            "all_approved": not self.blocked,
            "rows": [r.to_dict() for r in self.rows],
        }


def _next_action(cr: CharacterRef | None, exists: bool) -> str:
    if cr is None:
        return "declare-source"
    if not exists:
        return "fetch-source" if cr.source in ("wikimedia", "local") else "generate"
    if not cr.approved:
        return "approve"
    return "ready"


def build_status(
    teaser: Teaser,
    manifest: RefManifest,
    *,
    base_dir: Path | None = None,
    art_references_dir: Path | None = None,
    include_locations: bool = False,
) -> RefStatus:
    """Merge the teaser's auto plan with the declared manifest and emit a
    per-subject approval status with the one next action each. With
    ``include_locations`` (Phase 7), distinct settings are also tracked."""
    plan = _refs.plan_refs(teaser, base_dir=base_dir,
                           art_references_dir=art_references_dir,
                           include_locations=include_locations)
    rows: list[RefStatusRow] = []
    for e in plan.entries:
        cr = manifest.get(e.subject)
        exists = e.exists
        rows.append(RefStatusRow(
            subject=e.subject,
            shots=e.shots,
            source=cr.source if cr else "undeclared",
            source_ref=cr.source_ref if cr else "",
            status=cr.status if cr else "none",
            exists=exists,
            appearance_variants=e.appearance_variants,
            next_action=_next_action(cr, exists),
            ref_path=(cr.ref_path if (cr and cr.ref_path) else e.ref_path),
        ))
    return RefStatus(rows=rows)
