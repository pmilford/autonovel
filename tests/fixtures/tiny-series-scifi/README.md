# tiny-series-scifi

Genre fixture for Tier-3 smoke tests. Created by
`autonovel test-fixture new scifi`.

**Genre:** scifi

## What this fixture exercises

Replace this paragraph with one or two sentences describing the genre
quirk the smoke test asserts on (per §12a contract). Examples:

  - mystery: fair-play clue seeding; red-herring ledger.
  - fantasy: Sanderson's-laws hard-rule check on the magic system.
  - thriller: ticking-clock / stakes-escalation per chapter.

## Filling out the seeds

The scaffolder created an empty series shell. Edit before running the
smoke test:

  - `project.yaml` — set `period`, `genre`, default thresholds.
  - `seed.txt` (book and series) — the initial concept.
  - `shared/world.md`, `shared/characters.md` — minimal seed lore.
  - `shared/period_bans.txt` — only if period-sensitive (historical /
    period fantasy).

## Running the test

```bash
autonovel test-fixture run scifi
# or directly:
pytest tests/smoke/test_scifi_smoke.py -q -m smoke
```
