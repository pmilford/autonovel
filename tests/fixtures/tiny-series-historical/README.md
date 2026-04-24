# tiny-series-historical

Minimal fixture for Tier-3 smoke tests that exercise commands against a real
Claude Code runtime. Three chapters of a 1520 Venice investigation plot; big
enough to exercise period guardrails and research-citation behaviours, small
enough to cost ~$0.50 on Haiku and ~$5 on Sonnet per full sweep.

Used by:
- `tests/smoke/test_draft_smoke.py` (PR 2) — `/autonovel:draft 1`.
- `tests/smoke/test_historical_research.py` (PR 5) — live-search research.
