"""Phase-2 follow-up to `import_book.py`: reverse-engineer a stub
foundation from imported prose.

When a user imports an externally-written manuscript (`autonovel
import-book` / `/autonovel:import-book`) they typically don't have
a paired foundation. The drafting tools won't fire (the book is in
`edit-imported` mode), but eval / brief / revise / panel / review
all read foundation files (`voice.md`, `shared/characters.md`,
`outline.md`). Without those, the tools either fall back to weak
defaults or produce thin output.

This module extracts the cheapest mechanical signal — candidate
character names — from imported prose, and either:

  - writes a stub `shared/characters.md` listing each candidate as
    `**Name** — TBD: role`, OR
  - if `shared/characters.md` already exists, appends a clearly-
    delimited "Candidate cast (auto-detected)" section so the
    user can review before merging.

What this module deliberately does NOT do (per
`feedback_avoid_brittle_python.md`):

  - Auto-derive `voice.md` Part 2 (register / signature
    constructions / POV style). Mechanical heuristics for register
    drift fast and aren't a substitute for the LLM-side
    `/autonovel:voice-discovery`. The book template's voice.md
    stub plus a clear "next step" guidance string is the right
    shape.
  - Auto-write `outline.md` from inferred chapter beats. That
    needs per-chapter summaries, which need LLM. Pointing the
    user at `/autonovel:summarize-chapter --all` followed by
    `/autonovel:gen-outline` is the honest answer.

Pure mechanical. No LLM. No network. Tier-1 testable.

Public API:

    extract_character_candidates(book_root, *, min_occurrences=3,
                                   max_candidates=20) -> list[Candidate]
    reverse_engineer(series_root, book_root, *, dry_run=False) -> Result
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .mechanical.frontmatter import strip_yaml_frontmatter
from .paths import iter_chapter_files


# Tokens we always reject as character candidates. Sentence-initial
# capitalisation ("The morning broke...") would otherwise produce
# spurious top hits. Kept short on purpose — domain vocabulary
# belongs in per-book config, not Python (per
# feedback_avoid_brittle_python.md). This list is structural English
# and a few weekday/month names that are sentence-internal-cap
# common.
_CHARACTER_NAME_REJECT: frozenset[str] = frozenset({
    # Sentence-initial common starters.
    "The", "And", "But", "He", "She", "It", "They", "His", "Her",
    "I", "We", "You", "Their", "Then", "Now", "Here", "There", "What",
    "When", "Where", "Why", "How", "Who", "If", "So", "As", "Was",
    "Were", "Are", "Is", "Be", "Been", "Being", "Had", "Has", "Have",
    "Did", "Do", "Does", "This", "That", "These", "Those", "Some",
    "All", "No", "Not", "Or", "Of", "In", "On", "At", "By", "For",
    "With", "From", "After", "Before", "Until", "Since", "Through",
    "Inside", "Outside", "Above", "Below", "Across", "Against", "Yes",
    "Yet", "Still", "Even", "Just", "Only", "Once", "Twice", "Again",
    "Often", "Sometimes", "Never", "Always", "Maybe", "Perhaps",
    "Suddenly", "Slowly", "Quickly", "Carefully", "Finally", "First",
    "Second", "Third", "Last", "Each", "Every", "Both", "Either",
    "Neither", "Whose", "Which", "While", "Although", "Because",
    "Though", "Unless", "Whether", "Up", "Down", "Out", "Over",
    "Under", "Round", "Away", "Back", "Forward", "Today", "Tomorrow",
    "Yesterday", "Tonight",
    # Months / weekdays — almost always sentence-internal noise, not
    # character names.
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
    "Saturday", "Sunday",
    # Common honorifics that drift to first position in tagless
    # dialogue. Real characters surface via the bare name.
    "Mr", "Mrs", "Ms", "Miss", "Dr", "Sir", "Madam", "Lord", "Lady",
})


@dataclass
class CharacterCandidate:
    name: str
    occurrences: int
    sample_chapters: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "occurrences": self.occurrences,
            "sample_chapters": self.sample_chapters,
        }


@dataclass
class ReverseEngineerResult:
    candidates: list[CharacterCandidate]
    characters_md_action: str   # "wrote", "appended", "skipped-exists", "skipped-empty"
    characters_md_path: Path | None
    next_steps: list[str]
    dry_run: bool

    def to_dict(self) -> dict:
        return {
            "candidates": [c.to_dict() for c in self.candidates],
            "characters_md_action": self.characters_md_action,
            "characters_md_path": (
                str(self.characters_md_path)
                if self.characters_md_path else None
            ),
            "next_steps": self.next_steps,
            "dry_run": self.dry_run,
        }


# ----------------------------------------------------- extraction


_CAP_TOKEN_RE = re.compile(r"\b([A-Z][a-zA-Z]+)\b")
# Multi-word names ("Jakob Fugger", "Maximilian I") surface as their
# constituent parts under this match; the user merges them in the
# generated stub. Single-token matching is the simpler shape and
# avoids the bug class where greedy multi-word matching steals
# bare-name occurrences ("Jakob" in "Then Jakob laughed" gets eaten
# into a "Then Jakob" multi-word capture, suppressing the bare-name
# count).


def extract_character_candidates(book_root: Path, *,
                                   min_occurrences: int = 3,
                                   max_candidates: int = 20
                                   ) -> list[CharacterCandidate]:
    """Walk every chapter under `book_root/chapters/`, count
    capitalised tokens (single, two-word, or three-word), filter
    sentence-initial-only matches, drop the structural-English
    rejection list, and return the top N occurring at least
    `min_occurrences` times.
    """
    chapters_dir = book_root / "chapters"
    if not chapters_dir.is_dir():
        return []
    counts: Counter[str] = Counter()
    chapters_seen: dict[str, set[int]] = {}

    for ch_path in iter_chapter_files(chapters_dir):
        try:
            ch_num = int(ch_path.stem.split("_")[-1])
        except ValueError:
            continue
        text = strip_yaml_frontmatter(ch_path.read_text(encoding="utf-8"))
        for m in _CAP_TOKEN_RE.finditer(text):
            token = m.group(1).strip()
            if token in _CHARACTER_NAME_REJECT:
                continue
            counts[token] += 1
            chapters_seen.setdefault(token, set()).add(ch_num)

    # Sentence-initial filtering would have dropped Jakob in
    # "Jakob walked. Jakob spoke." which is exactly the third-person
    # narration shape we want to detect. The reject list above is
    # the correct seam — common sentence-starters like "Suddenly" or
    # "The" go there, not into a positional heuristic. Bigger noise-
    # tokens that slip past surface as candidates the user
    # reviews — this is a candidate generator, not a quality gate.
    out: list[CharacterCandidate] = []
    for token, n in counts.most_common():
        if n < min_occurrences:
            continue
        out.append(CharacterCandidate(
            name=token,
            occurrences=n,
            sample_chapters=sorted(chapters_seen[token]),
        ))
        if len(out) >= max_candidates:
            break
    return out


# ----------------------------------------------------- characters.md


_AUTO_BLOCK_HEADER = (
    "## Candidate cast (auto-detected from imported prose)"
)


def render_characters_md_stub(candidates: list[CharacterCandidate]) -> str:
    """The full file contents when `shared/characters.md` does not
    yet exist. Emits a real (auto-flagged) stub the user can
    refine in place."""
    parts: list[str] = []
    parts.append("# Characters\n")
    parts.append(
        "_Auto-generated from imported prose — review and edit. "
        "After this is filled in with real roles + relationships, "
        "run `/autonovel:voice-discovery` to populate Part 4 of "
        "voice.md (per-character voice fingerprints)._\n"
    )
    parts.append(_AUTO_BLOCK_HEADER + "\n")
    if not candidates:
        parts.append(
            "_No high-frequency capitalised names found in the "
            "imported prose. If your protagonist has a one-word name "
            "that mostly appears sentence-initially in third-person "
            "narration, the heuristic missed them — list them here "
            "manually._\n"
        )
    else:
        for c in candidates:
            parts.append(
                f"- **{c.name}** — TBD: role. "
                f"({c.occurrences} occurrences across "
                f"{len(c.sample_chapters)} chapter(s).)"
            )
        parts.append("")
    return "\n".join(parts) + "\n"


def render_characters_md_appendix(candidates: list[CharacterCandidate]) -> str:
    """The block to append when `shared/characters.md` already
    exists. Distinguishable from hand-written content by the
    auto-detected heading."""
    parts: list[str] = []
    parts.append("\n" + _AUTO_BLOCK_HEADER + "\n")
    parts.append(
        "_Auto-detected from imported prose. Merge the entries you "
        "recognise into the canonical sections above; delete the "
        "ones that aren't characters; remove this whole block when "
        "you're done._\n"
    )
    for c in candidates:
        parts.append(
            f"- **{c.name}** ({c.occurrences} occurrences across "
            f"{len(c.sample_chapters)} chapter(s))"
        )
    return "\n".join(parts) + "\n"


def reverse_engineer(series_root: Path, book_root: Path, *,
                      dry_run: bool = False
                      ) -> ReverseEngineerResult:
    """Run the Phase-2 foundation reverse-engineering for one
    book's imported chapters. Idempotent: appending an auto-detected
    block to an existing `shared/characters.md` will keep adding
    blocks if you re-run. The next-steps list tells the user what
    to do next (voice-discovery / summarize-chapter / gen-outline)
    in the right order."""
    candidates = extract_character_candidates(book_root)
    characters_md = series_root / "shared" / "characters.md"
    action = "skipped-empty"
    out_path: Path | None = None
    if not candidates:
        action = "skipped-empty"
    elif not characters_md.is_file():
        out_path = characters_md
        action = "wrote"
        if not dry_run:
            characters_md.parent.mkdir(parents=True, exist_ok=True)
            characters_md.write_text(
                render_characters_md_stub(candidates), encoding="utf-8",
            )
    else:
        existing = characters_md.read_text(encoding="utf-8")
        if _AUTO_BLOCK_HEADER in existing:
            # Idempotent guard: don't keep appending the same block.
            action = "skipped-exists"
        else:
            out_path = characters_md
            action = "appended"
            if not dry_run:
                characters_md.write_text(
                    existing.rstrip() + "\n"
                    + render_characters_md_appendix(candidates),
                    encoding="utf-8",
                )

    next_steps: list[str] = [
        f"Open `{characters_md}` and refine the auto-detected cast.",
        "Run `/autonovel:summarize-chapter <N>` for each chapter "
        "(or `--all`) to backfill the per-chapter `*.summary.md` "
        "files. These are the load-bearing continuity surface for "
        "evaluate / brief / revise.",
        "Run `/autonovel:voice-discovery --book <name>` to populate "
        "`voice.md` Part 2 (book-specific fingerprint) and Part 4 "
        "(per-character voice) from the imported prose. Pure-mechanical "
        "voice derivation isn't reliable; the LLM judge is the right "
        "tool here.",
        "Run `/autonovel:gen-outline --book <name>` once chapter "
        "summaries are in place — it'll synthesise an outline.md "
        "from the prose, not from a seed.",
        "Once the foundation is settled, `/autonovel:evaluate --full "
        "--book <name>` gives you the full quality picture against "
        "the imported prose.",
    ]
    return ReverseEngineerResult(
        candidates=candidates,
        characters_md_action=action,
        characters_md_path=out_path,
        next_steps=next_steps,
        dry_run=dry_run,
    )
