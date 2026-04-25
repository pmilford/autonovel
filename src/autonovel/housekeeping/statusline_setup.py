"""`autonovel statusline-setup` — wire the statusline + permissions into
the active series's `.claude/settings.json`.

Series-local. Does not touch the user's global `~/.claude/settings.json`.
Merges with anything already present (preserving unrelated keys; adding
to the `permissions.allow` list rather than overwriting).

Why permissions: Claude Code prompts the user before every Read/Write/
Bash/etc. that hasn't been pre-approved. Running the autonovel
foundation chain triggers ~10+ approvals (Read on every file the
commands declare, Write on every output, plus Bash for the
`autonovel _begin` and `_end` invocations). Pre-approving the tools
autonovel actually uses cuts the noise to zero without granting
blanket Bash access.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..paths import SeriesLayout


# The autonovel-managed pieces of the project-local settings file.
# `statusLine.command` shells to `autonovel statusline`; the helper
# auto-falls-back to env vars when stdin JSON isn't piped.
DEFAULT_STATUSLINE = {
    "type": "command",
    "command": "autonovel statusline",
    "padding": 0,
}

# Tools every autonovel command needs. Bash is *scoped*: we whitelist
# autonovel itself, common interpreters, and a handful of POSIX
# read-only utilities so commands like /autonovel:apply-cuts that shell
# to `python -m autonovel.mechanical` work without prompts. Anything
# riskier (rm, dd, sudo, ssh) is intentionally NOT pre-approved.
DEFAULT_ALLOW = [
    "Read",
    "Write",
    "Task",
    "WebSearch",
    "WebFetch",
    "Bash(autonovel:*)",
    "Bash(autonovel _begin:*)",
    "Bash(autonovel _end:*)",
    "Bash(python:*)",
    "Bash(python3:*)",
    "Bash(uv:*)",
    "Bash(git status:*)",
    "Bash(git diff:*)",
    "Bash(git log:*)",
    "Bash(git mv:*)",
    "Bash(mv:*)",
    "Bash(cp:*)",
    "Bash(ls:*)",
    "Bash(cat:*)",
    "Bash(head:*)",
    "Bash(tail:*)",
    "Bash(wc:*)",
    "Bash(grep:*)",
    "Bash(find:*)",
    "Bash(mkdir:*)",
]


@dataclass
class SetupResult:
    settings_path: Path
    created: bool   # True if the file did not exist before
    statusline_added: bool
    permissions_added: int  # how many entries we added to allow list
    permissions_already_present: int  # how many were already there


def setup(series: SeriesLayout, *, force: bool = False) -> SetupResult:
    """Write or merge the series-local `.claude/settings.json`. Idempotent
    — running twice produces the same file."""
    settings_dir = series.root / ".claude"
    settings_path = settings_dir / "settings.json"
    settings_dir.mkdir(parents=True, exist_ok=True)

    existing: dict = {}
    created = not settings_path.exists()
    if not created:
        try:
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                raise ValueError("top-level settings must be a JSON object")
        except Exception as e:
            if not force:
                raise SetupError(
                    f"{settings_path} exists but is not a valid JSON object: {e}. "
                    f"Pass --force to overwrite, or fix the file by hand."
                )
            existing = {}

    merged = dict(existing)

    # Status line: only set if absent, or always overwrite when --force.
    statusline_added = False
    if "statusLine" not in merged or force:
        merged["statusLine"] = dict(DEFAULT_STATUSLINE)
        statusline_added = True

    # Permissions: merge into existing allow list rather than overwrite.
    perms = dict(merged.get("permissions") or {})
    allow = list(perms.get("allow") or [])
    already = sum(1 for p in DEFAULT_ALLOW if p in allow)
    added = 0
    for p in DEFAULT_ALLOW:
        if p not in allow:
            allow.append(p)
            added += 1
    perms["allow"] = allow
    merged["permissions"] = perms

    settings_path.write_text(
        json.dumps(merged, indent=2) + "\n", encoding="utf-8"
    )
    return SetupResult(
        settings_path=settings_path,
        created=created,
        statusline_added=statusline_added,
        permissions_added=added,
        permissions_already_present=already,
    )


class SetupError(RuntimeError):
    pass
