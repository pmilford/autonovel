# Testing

Autonovel has four tiers of tests, only the first two of which run in
plain CI.

| Tier | Runs in CI | Costs money | What it covers |
|---|---|---|---|
| 1 — deterministic | yes | no | Frontmatter shape, mechanical regex modules, adapter golden files, housekeeping CLI, validators |
| 2 — command contracts | yes | no | `reads:` / `writes:` declared in frontmatter actually appear in the command body; placeholders resolve |
| 3 — smoke | opt-in | yes | Real runtime invocation against a fixture series; one assertion per command/genre |
| 4 — Bells regression | opt-in (manual) | yes | `/autonovel:evaluate` on frozen Bells chapters within ±0.5 of reference scores |

Tier 3+4 are gated by `@pytest.mark.smoke` / `@pytest.mark.regression`
and skip cleanly when the runtime CLI (`claude`, `codex`, or `gemini`)
is not on `$PATH`.

## Running locally

```bash
# Tier 1 + 2 only — fast, free, runs on every commit.
pytest tests/deterministic tests/contracts -q

# Tier 3 — uses your subscription auth via Claude Code (default).
claude login   # one-time
pytest tests/smoke -q -m smoke

# One genre fixture's smoke test.
autonovel test-fixture run mystery
# or directly:
pytest tests/smoke/test_mystery_smoke.py -q -m smoke

# Tier 4 — Bells regression. Skips until populated; see below.
pytest tests/smoke -q -m "smoke and regression"
```

## Auth policy for smoke tests

Smoke tests bill against your Claude Code subscription
(Claude Max / Team / Pro) by default. The `tests/smoke/conftest.py`
fixture strips `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` from the
subprocess env so the runtime falls through to the OAuth session left
behind by `claude login`.

Escape hatch — set `AUTONOVEL_SMOKE_USE_API_KEY=1` to bill via API key
instead:

```bash
AUTONOVEL_SMOKE_USE_API_KEY=1 ANTHROPIC_API_KEY=sk-ant-... \
  pytest tests/smoke -q -m smoke
```

Rough per-sweep cost (subscription auth: free against your plan):
~$5 on Sonnet and ~$0.50 on Haiku for a full eight-genre Tier-3 sweep.

## Flakiness policy (live web search)

Per `REWRITE-PLAN.md` §12.4, smoke tests that hit live web search are
permitted to flake. The policy:

1. Each `@pytest.mark.smoke` test is auto-rerun once on failure
   (via `pytest-rerunfailures` and the hook in `tests/conftest.py`).
2. A test that flips fail→pass is logged to `tests/flakiness.jsonl`
   so we can spot tests that have degraded to worthless.
3. A test that fails *both* attempts is a real signal.
4. Genre keyword lists in tests are intentionally generous so ordinary
   web-search drift does not fail them.

## Adding a new genre fixture

See [`adding-a-genre-fixture.md`](adding-a-genre-fixture.md) and
`REWRITE-PLAN.md` §12a. The short version:

```bash
autonovel test-fixture new my-western
# Edit tests/fixtures/tiny-series-my-western/{seed.txt, shared/*}
# Edit tests/smoke/test_my_western_smoke.py to assert a genre quirk.
autonovel test-fixture run my-western
```

## Tier-4 Bells regression

The Tier-4 harness at `tests/fixtures/bells-reference/` is scaffolded
but empty — it skips until a human copies chapters from the
`autonovel/bells` branch and freezes `scores.json`. See
`tests/fixtures/bells-reference/README.md` for the populate steps.

When populated, `pytest tests/smoke -m "smoke and regression"` runs
two guards:

- A deterministic `slop_penalty` drift check (tolerant to ±0.1).
- An LLM-judged `overall_score` drift check (tolerant to ±0.5).

## Adapter coverage

Tier 1 has golden-file tests for every adapter
(`test_adapter.py`, `test_adapter_codex.py`, `test_adapter_gemini.py`).
Tier 2 contract tests run unchanged against every adapter.

Tier 3 currently exercises Claude Code end-to-end, with one Codex
spot-check (`test_codex_smoke.py`) and one Gemini spot-check
(`test_gemini_smoke.py`). Both auto-skip when their runtime binary is
absent.
