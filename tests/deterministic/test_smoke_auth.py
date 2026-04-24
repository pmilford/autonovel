"""Tier-1: smoke-test conftest routes through subscription auth by default.

Direct unit test of `auth_aware_env` — no subprocess, no API cost.

The invariant this protects: when both `ANTHROPIC_API_KEY` and a
`claude login` OAuth session exist on the same machine, Claude Code prefers
the API key. autonovel's policy is subscription-first, so the smoke
subprocess must not see `ANTHROPIC_API_KEY` unless the developer explicitly
asks for it via `AUTONOVEL_SMOKE_USE_API_KEY=1`.
"""

from __future__ import annotations

from tests.smoke.conftest import API_KEY_OPT_IN, auth_aware_env


def test_api_key_stripped_by_default() -> None:
    env = auth_aware_env({
        "ANTHROPIC_API_KEY": "sk-ant-fake",
        "ANTHROPIC_AUTH_TOKEN": "token-fake",
        "PATH": "/usr/bin",
    })
    assert "ANTHROPIC_API_KEY" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    assert env["PATH"] == "/usr/bin"


def test_opt_in_preserves_api_key() -> None:
    env = auth_aware_env({
        "ANTHROPIC_API_KEY": "sk-ant-fake",
        API_KEY_OPT_IN: "1",
    })
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-fake"


def test_opt_in_accepts_truthy_values() -> None:
    for flag in ("1", "true", "TRUE", "yes", "Yes"):
        env = auth_aware_env({
            "ANTHROPIC_API_KEY": "k",
            API_KEY_OPT_IN: flag,
        })
        assert env["ANTHROPIC_API_KEY"] == "k", f"opt-in rejected for {flag!r}"


def test_opt_in_unset_means_stripped() -> None:
    env = auth_aware_env({
        "ANTHROPIC_API_KEY": "k",
        API_KEY_OPT_IN: "0",
    })
    assert "ANTHROPIC_API_KEY" not in env


def test_no_api_key_is_fine() -> None:
    # Most common case on a subscription-auth dev machine.
    env = auth_aware_env({"PATH": "/usr/bin"})
    assert "ANTHROPIC_API_KEY" not in env
    assert env["PATH"] == "/usr/bin"


def test_auth_aware_env_defaults_to_os_environ(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-default")
    monkeypatch.delenv(API_KEY_OPT_IN, raising=False)
    env = auth_aware_env()
    assert "ANTHROPIC_API_KEY" not in env


def test_auth_aware_env_respects_opt_in_from_os_environ(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-default")
    monkeypatch.setenv(API_KEY_OPT_IN, "1")
    env = auth_aware_env()
    assert env["ANTHROPIC_API_KEY"] == "sk-default"
