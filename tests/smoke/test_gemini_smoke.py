"""Tier-3 spot-check smoke: one autonovel command end-to-end on Gemini CLI.

Mirrors `test_codex_smoke.py`. Skips cleanly when `gemini` is not on
`$PATH`. PR 8's acceptance for Gemini is "spot-check green on Gemini" —
once a green run is recorded in STATE.md, this test stays opt-in.

Auth and command-discovery convention details for Gemini CLI may need
refinement once the binary is actually exercised; the structure here
matches the Codex test on the assumption that Gemini supports a
non-interactive `gemini -p` mode and reads commands from
`~/.gemini/commands/`.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from autonovel.adapters import installer
from autonovel.adapters.gemini import GeminiAdapter


FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

API_KEY_OPT_IN = "AUTONOVEL_SMOKE_USE_API_KEY"

PLACEHOLDER_CANON = (
    "# Canon\n\n"
    "Hard facts true across all books in this series. Each entry is a single\n"
    "verifiable claim; commands reference it by the headline in brackets.\n\n"
    "<!-- Seeded by /autonovel:gen-canon; grown by /autonovel:promote-canon. -->\n"
)


def _gemini_binary() -> Path | None:
    found = shutil.which("gemini")
    return Path(found) if found else None


def _gemini_subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    use_api_key = env.get(API_KEY_OPT_IN, "").strip().lower() in {"1", "true", "yes"}
    if not use_api_key:
        env.pop("GEMINI_API_KEY", None)
        env.pop("GOOGLE_API_KEY", None)
    return env


@pytest.mark.smoke
@pytest.mark.genre("historical")
def test_gemini_runs_gen_canon(tmp_path: Path) -> None:
    gemini = _gemini_binary()
    if gemini is None:
        pytest.skip(
            "`gemini` CLI not on $PATH. Install Gemini CLI "
            "(https://github.com/google-gemini/gemini-cli) and run "
            "`gemini auth` before this smoke test."
        )

    series = tmp_path / "tiny-series-historical"
    shutil.copytree(FIXTURES / "tiny-series-historical", series)

    # Project-local install. Gemini CLI also reads `~/.gemini/commands/`,
    # but we keep it local to avoid polluting the user's global install.
    installer.install(GeminiAdapter(), install_root=series / ".gemini" / "commands")

    target = series / "shared" / "canon.md"
    target.write_text(PLACEHOLDER_CANON, encoding="utf-8")

    result = subprocess.run(
        [str(gemini), "-p", "/autonovel:gen-canon"],
        cwd=series,
        capture_output=True,
        text=True,
        timeout=900,
        env=_gemini_subprocess_env(),
    )

    assert result.returncode == 0, (
        f"gemini returned {result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    text = target.read_text(encoding="utf-8")
    assert text.lstrip().startswith("# Canon")
    bullets = [ln for ln in text.splitlines() if ln.strip().startswith("- ")]
    assert len(bullets) >= 3
    assert _word_count(text) >= 80


def _word_count(text: str) -> int:
    body = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return len(body.split())
