"""Tier-3 spot-check smoke: one autonovel skill end-to-end on Codex CLI.

Per REWRITE-PLAN §13 PR 8, the Codex/Gemini adapters get adapter-level
golden-file tests in Tier 1 plus a single end-to-end spot check in
Tier 3 to validate the rendered files are actually loadable by the
runtime.

Mirrors the shape of `tests/smoke/test_foundation_smoke.py::test_gen_canon`
on Claude — the cheapest foundation command to exercise. Installs the
generic commands through the Codex adapter into a redirected
`CODEX_HOME=<tmp>/.codex/skills`, copies the user's `auth.json` over so
subscription auth survives, then asks `codex exec` to invoke the
`autonovel-gen-canon` skill against the fixture series.

Auto-skips when `codex` is not on `$PATH`, when no `auth.json` is
available to copy in, or when the test box is the autonovel CI runner
(both Claude- and Codex-flavoured smoke tests cost real spend; PR 8's
acceptance is "spot-check green on Codex" so once a green run is
recorded in STATE.md the suite can stay opt-in).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from autonovel.adapters import installer
from autonovel.adapters.codex import CodexAdapter


FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

# Same shape as the Claude smoke API-key opt-in: subscription auth is
# primary, but a developer reproducing a billing/rate-limit bug can flip
# this to keep `OPENAI_API_KEY` on the subprocess env.
API_KEY_OPT_IN = "AUTONOVEL_SMOKE_USE_API_KEY"

PLACEHOLDER_CANON = (
    "# Canon\n\n"
    "Hard facts true across all books in this series. Each entry is a single\n"
    "verifiable claim; commands reference it by the headline in brackets.\n\n"
    "<!-- Seeded by /autonovel:gen-canon; grown by /autonovel:promote-canon. -->\n"
)


def _codex_binary() -> Path | None:
    found = shutil.which("codex")
    return Path(found) if found else None


def _real_codex_home() -> Path:
    explicit = os.environ.get("CODEX_HOME")
    if explicit:
        return Path(explicit)
    return Path.home() / ".codex"


def _codex_subprocess_env(codex_home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["CODEX_HOME"] = str(codex_home)
    use_api_key = env.get(API_KEY_OPT_IN, "").strip().lower() in {"1", "true", "yes"}
    if not use_api_key:
        env.pop("OPENAI_API_KEY", None)
        env.pop("ANTHROPIC_API_KEY", None)
    return env


@pytest.mark.smoke
@pytest.mark.genre("historical")
def test_codex_runs_gen_canon(tmp_path: Path) -> None:
    codex = _codex_binary()
    if codex is None:
        pytest.skip(
            "`codex` CLI not on $PATH. Install Codex CLI "
            "(npm i -g @openai/codex-cli) and run `codex login` before this "
            "smoke test. Subscription auth is preferred; see "
            "AUTONOVEL_SMOKE_USE_API_KEY for the OPENAI_API_KEY escape hatch."
        )

    real_home = _real_codex_home()
    real_auth = real_home / "auth.json"
    if not real_auth.is_file():
        pytest.skip(
            f"no auth.json at {real_auth}. `codex login` first, or set "
            "CODEX_HOME to a directory that has one."
        )

    series = tmp_path / "tiny-series-historical"
    shutil.copytree(FIXTURES / "tiny-series-historical", series)

    # Redirected Codex home, with skills installed and auth copied.
    fake_home = tmp_path / ".codex"
    fake_home.mkdir(parents=True, exist_ok=True)
    shutil.copy2(real_auth, fake_home / "auth.json")
    if (real_home / "config.toml").is_file():
        shutil.copy2(real_home / "config.toml", fake_home / "config.toml")
    installer.install(CodexAdapter(), install_root=fake_home / "skills")

    # Reset gen-canon's target so the test asserts content was generated.
    target = series / "shared" / "canon.md"
    target.write_text(PLACEHOLDER_CANON, encoding="utf-8")

    prompt = (
        "Run the autonovel-gen-canon skill end-to-end against the series in "
        "the current working directory. Follow the SKILL.md instructions "
        "exactly, including the autonovel preamble and postamble."
    )

    result = subprocess.run(
        [
            str(codex),
            "exec",
            "--full-auto",
            "--skip-git-repo-check",
            "-C", str(series),
            prompt,
        ],
        cwd=series,
        capture_output=True,
        text=True,
        timeout=900,
        env=_codex_subprocess_env(fake_home),
    )

    assert result.returncode == 0, (
        f"codex returned {result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    text = target.read_text(encoding="utf-8")
    assert text.lstrip().startswith("# Canon"), "missing top-level heading"
    bullets = [ln for ln in text.splitlines() if ln.strip().startswith("- ")]
    assert len(bullets) >= 3, f"need at least 3 canon bullets; got {len(bullets)}"
    # Sanity: the placeholder comment got replaced with real content.
    assert _word_count(text) >= 80, f"canon body too short: {_word_count(text)} words"


def _word_count(text: str) -> int:
    body = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return len(body.split())
