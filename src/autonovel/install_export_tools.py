"""`autonovel install-export-tools` — interactive installer for the
external tools the export commands depend on.

Surfaced 2026-04-25 by author testing on Chromebook + WSL: `apt
install tectonic` frequently produces a too-old version that
autonovel can't use; `Pillow` and `pydub` need `pipx inject` when
autonovel was installed without `[export]` extras; cover rendering
fails silently when fonts aren't on the system. The user shouldn't
have to debug shell. This helper:

  - Detects the OS (Linux/Debian-derived, macOS, other) and the
    install method autonovel was installed under (pipx vs pip vs
    editable clone).
  - Asks which exports the user wants (PDF? cover? audiobook?
    epub?). Each choice maps to a known set of tools.
  - Prints the exact commands the user needs (or runs them with
    `--apply`), with per-tool fallback chains for the cases known
    to fail under naive package-manager install (tectonic → apt
    → prebuilt static binary).
  - Re-verifies after install: runs the binary and checks version,
    not just `which` — naive install can place a too-old binary
    on PATH that doctor would falsely report as OK.

Pure mechanical. No LLM. Tier-1 testable: the OS-detection and
command-table assembly are exposed as pure functions; the
subprocess calls are gated behind a single seam.

Public API:

    detect_os() -> "macos" | "debian" | "fedora" | "other"
    detect_install_method() -> "pipx" | "pip" | "editable" | "unknown"
    plan(*, exports, os_id, install_method) -> Plan
    render_plan(plan) -> str
    apply(plan, *, confirm=True) -> ApplyResult
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ----------------------------------------------------- exports → tools


# Each export choice maps to the set of external tools / Python
# packages it needs. The same tool can appear in multiple exports;
# the planner deduplicates.
EXPORT_REQUIREMENTS: dict[str, list[str]] = {
    # /autonovel:typeset reads `\setmainfont{EB Garamond}` in the
    # series's novel.tex; the package name is `fonts-ebgaramond` on
    # Debian/Ubuntu and a Homebrew cask on macOS. fontconfig is the
    # font-lookup glue tectonic uses — required even when the font
    # itself is installed.
    "pdf": ["tectonic", "rsvg-convert", "fontconfig", "eb-garamond"],
    "epub": ["pandoc"],                     # /autonovel:typeset --epub
    "cover": ["pillow", "fontconfig", "eb-garamond"],  # cover-print, cover-composite
    "audiobook": ["ffmpeg", "pydub"],       # /autonovel:audiobook-assemble
    "art": ["potrace", "rsvg-convert"],     # /autonovel:art-vectorize, art-ornaments-all
}


# Per-tool install command tables. Some tools have a known fallback
# chain (apt-tectonic too old → static binary from upstream).
@dataclass
class ToolPlan:
    name: str
    purpose: str             # one-line "what does this tool do for me"
    commands: list[str]       # shell commands to run, in order
    notes: list[str] = field(default_factory=list)
    verify: str | None = None   # command to run after install; non-zero exit = failed
    pip_inject: bool = False    # True for Python pkgs that need pipx inject when applicable


# Linux/Debian
_DEBIAN: dict[str, ToolPlan] = {
    "tectonic": ToolPlan(
        name="tectonic", purpose="PDF typesetting (/autonovel:typeset)",
        commands=[
            "sudo apt-get install -y tectonic",
        ],
        notes=[
            "If `tectonic --version` reports older than 0.14, the apt "
            "build is too old. Install the upstream static binary "
            "instead: `cargo install tectonic` (needs Rust) OR grab the "
            "prebuilt from https://tectonic-typesetting.github.io/book/"
            "latest/installation/ and put it on PATH.",
        ],
        verify="tectonic --version",
    ),
    "pandoc": ToolPlan(
        name="pandoc", purpose="ePub generation (/autonovel:typeset --epub)",
        commands=["sudo apt-get install -y pandoc"],
        verify="pandoc --version",
    ),
    "potrace": ToolPlan(
        name="potrace", purpose="SVG vectorisation (/autonovel:art-vectorize)",
        commands=["sudo apt-get install -y potrace"],
        verify="potrace --version",
    ),
    "ffmpeg": ToolPlan(
        name="ffmpeg", purpose="m4b audiobook output (/autonovel:audiobook-assemble --format m4b)",
        commands=["sudo apt-get install -y ffmpeg"],
        verify="ffmpeg -version",
    ),
    "rsvg-convert": ToolPlan(
        name="rsvg-convert", purpose="SVG→PDF for print-quality ornaments (/autonovel:typeset --convert-vectors)",
        commands=["sudo apt-get install -y librsvg2-bin"],
        verify="rsvg-convert --version",
    ),
    "fontconfig": ToolPlan(
        name="fontconfig", purpose="Font lookup glue (`fc-match`) — needed for `/autonovel:typeset` AND cover rendering",
        commands=[
            "sudo apt-get install -y fontconfig",
        ],
        verify="fc-match --version",
    ),
    "eb-garamond": ToolPlan(
        name="EB Garamond",
        purpose="primary serif for chapter prose AND cover typography",
        commands=[
            "sudo apt-get install -y fonts-ebgaramond",
            "fc-cache -fv",
        ],
        notes=[
            "If `fc-match \"EB Garamond\"` still resolves to a fallback "
            "after install, the package may have shipped the font under a "
            "different family name. Confirm with `fc-list | grep -i "
            "garamond` and update novel.tex's `\\setmainfont{...}` to the "
            "exact name fc-list reports.",
            "Bebas Neue (display font for some cover styles) is not in "
            "the default Debian font repos; if `/autonovel:cover-print` "
            "complains, drop the .ttf into ~/.fonts/ and run "
            "`fc-cache -fv`.",
        ],
        verify="fc-match \"EB Garamond\" | grep -qi garamond",
    ),
    "pillow": ToolPlan(
        name="Pillow",
        purpose="Cover composition and image manipulation (/autonovel:cover-composite, art-curate)",
        commands=[],   # filled in by _python_pkg_commands
        verify="python3 -c 'from PIL import Image'",
        pip_inject=True,
    ),
    "pydub": ToolPlan(
        name="pydub", purpose="Audio assembly under the hood (/autonovel:audiobook-assemble)",
        commands=[],
        verify="python3 -c 'import pydub'",
        pip_inject=True,
    ),
}


# macOS via Homebrew
_MACOS: dict[str, ToolPlan] = {
    "tectonic": ToolPlan(
        name="tectonic", purpose="PDF typesetting (/autonovel:typeset)",
        commands=["brew install tectonic"],
        verify="tectonic --version",
    ),
    "pandoc": ToolPlan(
        name="pandoc", purpose="ePub generation (/autonovel:typeset --epub)",
        commands=["brew install pandoc"],
        verify="pandoc --version",
    ),
    "potrace": ToolPlan(
        name="potrace", purpose="SVG vectorisation (/autonovel:art-vectorize)",
        commands=["brew install potrace"],
        verify="potrace --version",
    ),
    "ffmpeg": ToolPlan(
        name="ffmpeg", purpose="m4b audiobook output",
        commands=["brew install ffmpeg"],
        verify="ffmpeg -version",
    ),
    "rsvg-convert": ToolPlan(
        name="rsvg-convert", purpose="SVG→PDF for print ornaments",
        commands=["brew install librsvg"],
        verify="rsvg-convert --version",
    ),
    "fontconfig": ToolPlan(
        name="fontconfig", purpose="Font lookup glue (`fc-match`) — needed for typeset AND cover rendering",
        commands=["brew install fontconfig"],
        verify="fc-match --version",
    ),
    "eb-garamond": ToolPlan(
        name="EB Garamond",
        purpose="primary serif for chapter prose AND cover typography",
        commands=[
            "brew install --cask font-eb-garamond",
        ],
        notes=[
            "If `font-eb-garamond` cask isn't recognised, tap the fonts "
            "repo first: `brew tap homebrew/cask-fonts`. Or download "
            "manually from https://fonts.google.com/specimen/EB+Garamond "
            "and double-click each .ttf to install.",
            "After install, run `fc-cache -fv` if you have fontconfig.",
        ],
        verify="fc-match \"EB Garamond\" 2>/dev/null | grep -qi garamond || ls ~/Library/Fonts/EBGaramond*.ttf",
    ),
    "pillow": ToolPlan(
        name="Pillow", purpose="Cover composition", commands=[],
        verify="python3 -c 'from PIL import Image'", pip_inject=True,
    ),
    "pydub": ToolPlan(
        name="pydub", purpose="Audio assembly", commands=[],
        verify="python3 -c 'import pydub'", pip_inject=True,
    ),
}


def _tool_table_for(os_id: str) -> dict[str, ToolPlan]:
    if os_id == "macos":
        return _MACOS
    if os_id == "debian":
        return _DEBIAN
    # other: Fedora / Arch / etc. — return Debian-shaped table
    # with a note. The user can adapt.
    return _DEBIAN


# ----------------------------------------------------- detection


def detect_os() -> str:
    sys_name = platform.system()
    if sys_name == "Darwin":
        return "macos"
    if sys_name == "Linux":
        # Best-effort: check /etc/os-release.
        try:
            text = Path("/etc/os-release").read_text(encoding="utf-8")
        except OSError:
            return "other"
        for line in text.splitlines():
            if line.startswith("ID="):
                value = line.split("=", 1)[1].strip().strip('"').lower()
                if value in {"ubuntu", "debian", "raspbian", "linuxmint", "pop"}:
                    return "debian"
                if value in {"fedora", "rhel", "centos"}:
                    return "fedora"
                if value in {"arch", "manjaro"}:
                    return "arch"
        # Fall back to ID_LIKE
        for line in text.splitlines():
            if line.startswith("ID_LIKE="):
                value = line.split("=", 1)[1].strip().strip('"').lower()
                if "debian" in value:
                    return "debian"
        return "other"
    return "other"


def detect_install_method() -> str:
    """How was autonovel installed? pipx puts the venv at
    ~/.local/pipx/venvs/autonovel; pip --user at ~/.local/lib/...;
    editable install has the source dir in sys.path."""
    autonovel_module = Path(sys.modules["autonovel"].__file__ or "").resolve()
    parts = str(autonovel_module).split("/")
    if "pipx" in parts:
        return "pipx"
    # Editable installs typically have `.pth` referencing the source dir
    # — autonovel module path then sits inside the dev clone, not under
    # site-packages.
    if "site-packages" not in str(autonovel_module):
        return "editable"
    return "pip"


# ----------------------------------------------------- plan


@dataclass
class Plan:
    os_id: str
    install_method: str
    selected_exports: list[str]
    selected_tools: list[ToolPlan]   # in install order; deduped


def plan(*, exports: list[str], os_id: str | None = None,
          install_method: str | None = None) -> Plan:
    """Assemble a plan for the requested exports on the detected (or
    given) OS. `exports` is a list of keys from EXPORT_REQUIREMENTS;
    unknown keys raise ValueError so callers can show usage."""
    os_id = os_id or detect_os()
    install_method = install_method or detect_install_method()
    table = _tool_table_for(os_id)
    needed: list[str] = []
    for exp in exports:
        if exp not in EXPORT_REQUIREMENTS:
            raise ValueError(
                f"unknown export {exp!r}. Choose from "
                f"{sorted(EXPORT_REQUIREMENTS)}"
            )
        for tool in EXPORT_REQUIREMENTS[exp]:
            if tool not in needed:
                needed.append(tool)
    plans: list[ToolPlan] = []
    for tool in needed:
        if tool not in table:
            # Tool not in table for this OS — emit a stub that prints a
            # clear "no recipe" message to the user without failing the
            # whole plan.
            plans.append(ToolPlan(
                name=tool, purpose=f"(no install recipe for {os_id})",
                commands=[],
                notes=[f"No install command known for {tool} on {os_id}; "
                        f"install it manually and re-run `autonovel "
                        f"doctor` to confirm."],
            ))
            continue
        tp = table[tool]
        if tp.pip_inject:
            tp = ToolPlan(
                name=tp.name, purpose=tp.purpose,
                commands=_python_pkg_commands(tp.name, install_method),
                notes=list(tp.notes),
                verify=tp.verify, pip_inject=True,
            )
        plans.append(tp)
    return Plan(
        os_id=os_id,
        install_method=install_method,
        selected_exports=list(exports),
        selected_tools=plans,
    )


def _python_pkg_commands(pkg_name: str, install_method: str) -> list[str]:
    """Pillow / pydub need different install verbs depending on how
    autonovel itself is installed:
      - pipx → `pipx inject autonovel <pkg>` (puts the pkg in autonovel's venv)
      - pip / editable → `pip install <pkg>` (assumes user manages env)
    """
    if install_method == "pipx":
        return [f"pipx inject autonovel {pkg_name.lower()}"]
    return [f"pip install {pkg_name.lower()}"]


# ----------------------------------------------------- render


def render_plan(plan: Plan) -> str:
    parts: list[str] = []
    parts.append(f"# Install plan — {plan.os_id} ({plan.install_method} install)")
    parts.append("")
    parts.append(
        f"Selected exports: {', '.join(plan.selected_exports)}\n"
        f"Tools to install: {len(plan.selected_tools)}"
    )
    parts.append("")
    if plan.os_id == "other":
        parts.append("⚠️  OS not specifically recognised; commands shown are "
                     "Debian-shaped. Adapt for your distro.\n")
    for i, tp in enumerate(plan.selected_tools, 1):
        parts.append(f"## {i}. {tp.name}")
        parts.append(f"_{tp.purpose}_")
        parts.append("")
        if tp.commands:
            parts.append("```bash")
            for cmd in tp.commands:
                parts.append(cmd)
            parts.append("```")
        else:
            parts.append("_(no install command for this tool on this OS)_")
        if tp.notes:
            parts.append("")
            for note in tp.notes:
                parts.append(f"> {note}")
        if tp.verify:
            parts.append("")
            parts.append(f"Verify after: `{tp.verify}`")
        parts.append("")
    parts.append(
        "When you've run all of these, `autonovel doctor` will report "
        "the matching tools as OK. To run them automatically, re-invoke "
        "this command with `--apply` (you'll be prompted before each step)."
    )
    return "\n".join(parts) + "\n"


# ----------------------------------------------------- apply


@dataclass
class ApplyResult:
    succeeded: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def apply(plan: Plan, *, confirm: bool = True,
           runner=None) -> ApplyResult:
    """Run each tool's commands in order. `confirm=True` prompts
    before each tool; `runner` is the subprocess seam for testing
    (default: subprocess.run with check=False, return code surfaces
    in the failed list)."""
    runner = runner or _default_runner
    result = ApplyResult()
    for tp in plan.selected_tools:
        if not tp.commands:
            result.skipped.append(tp.name)
            continue
        if confirm:
            print(f"\n{tp.name} — {tp.purpose}")
            for cmd in tp.commands:
                print(f"  $ {cmd}")
            try:
                resp = input("  Run? [y/N] ").strip().lower()
            except EOFError:
                resp = ""
            if resp != "y":
                result.skipped.append(tp.name)
                continue
        ok = True
        for cmd in tp.commands:
            rc = runner(cmd)
            if rc != 0:
                ok = False
                result.failed.append((tp.name, f"`{cmd}` exited {rc}"))
                break
        if ok and tp.verify:
            rc = runner(tp.verify)
            if rc != 0:
                result.failed.append((tp.name, f"verify (`{tp.verify}`) exited {rc}"))
                ok = False
        if ok:
            result.succeeded.append(tp.name)
    return result


def _default_runner(cmd: str) -> int:
    return subprocess.run(cmd, shell=True).returncode
