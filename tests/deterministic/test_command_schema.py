"""Tier-1 JSON-schema validation for every commands/*.md frontmatter.

The existing `adapters.base.validate_frontmatter` does field-level
checks but isn't a complete schema — it doesn't catch typos in
optional field names (e.g. `arguemnt-hint:`) or wrong types on
optional fields. The JSON schema at
`src/autonovel/validators/command_schema.json` is the canonical
shape contract; this test runs it against every shipped command.

Catches:
  - typos in field names (additionalProperties: false)
  - wrong types (string where list expected, etc.)
  - invalid enum values (model_tier, context_mode, allowed-tools)
  - command names that don't match the autonovel: namespace pattern
  - empty descriptions / argument-hints / required-list violations
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# jsonschema is a [test] extra; the test is conditional so a fresh
# clone without the extra still loads cleanly.
jsonschema = pytest.importorskip("jsonschema")

import yaml

from autonovel.adapters.installer import _commands_source_dir


_COMMANDS_DIR = _commands_source_dir()
_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "src" / "autonovel" / "validators" / "command_schema.json"
)


def _load_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    assert m is not None, f"no frontmatter block in {path}"
    return yaml.safe_load(m.group(1)) or {}


def _all_command_files() -> list[Path]:
    return sorted(_COMMANDS_DIR.glob("*.md"))


# -------------------------------------------------- schema sanity


def test_schema_file_loads_as_valid_json_schema() -> None:
    schema = _load_schema()
    # The Draft202012Validator validates the schema *itself* — catches
    # malformed schema drafts.
    jsonschema.Draft202012Validator.check_schema(schema)


def test_schema_uses_strict_additional_properties() -> None:
    """A typo guard: schema must reject unknown frontmatter keys."""
    schema = _load_schema()
    assert schema.get("additionalProperties") is False


# -------------------------------------------------- per-command validation


@pytest.mark.parametrize("path", _all_command_files(),
                          ids=lambda p: p.stem)
def test_every_command_frontmatter_matches_schema(path: Path) -> None:
    schema = _load_schema()
    fm = _parse_frontmatter(path)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(fm), key=lambda e: list(e.path))
    if errors:
        msg_lines = [f"frontmatter validation failed for {path.name}:"]
        for e in errors:
            msg_lines.append(
                f"  - at {list(e.path) or '<root>'}: {e.message}"
            )
        pytest.fail("\n".join(msg_lines))


def test_at_least_one_command_uses_each_required_field() -> None:
    """Sanity: the shipped commands must collectively use every
    schema-declared field. Catches the case where a field is in the
    schema but no command uses it (dead documentation)."""
    schema = _load_schema()
    declared = set(schema["properties"].keys())
    seen: set[str] = set()
    for path in _all_command_files():
        fm = _parse_frontmatter(path)
        seen.update(fm.keys())
    missing = declared - seen
    assert not missing, (
        f"schema declares fields no shipped command uses: "
        f"{sorted(missing)}"
    )
