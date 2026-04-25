# Adding a genre fixture

Autonovel ships eight genre fixtures (historical, sci-fi, literary,
mystery, thriller, romance, fantasy, horror). You can add more without
modifying autonovel itself — extensibility is a first-class feature.

## Why add a fixture

A genre fixture is a tiny series (1–3 chapters of seed content) that
exercises a *genre-characteristic behaviour* of one or more commands.
Examples already in the suite:

- `mystery`: `/autonovel:gen-outline` produces ≥3 red herrings and a
  clue ledger.
- `fantasy`: `/autonovel:gen-world` magic system has costs/limits for
  every listed power.
- `thriller`: every chapter outline carries a stakes-escalation note.
- `romance`: outline covers the four-beat structure and names HEA/HFN.

A new fixture is worth adding when (a) the genre's quirk is not
covered by an existing one, or (b) you want a deterministic harness
to gate future prompt-engineering changes against your specific genre.

## Scaffold

```bash
autonovel test-fixture new my-western
```

This creates:

```
tests/fixtures/tiny-series-my-western/
  project.yaml             # genre=my-western
  README.md                # genre summary stub
  shared/
    world.md               # empty template
    characters.md          # empty template
    canon.md
    events.md
    period_bans.txt        # empty
    sources.bib
    sources.yaml
    research/
  books/
    book-one/
      seed.txt             # placeholder
      voice.md, outline.md, …

tests/smoke/test_my_western_smoke.py
  # Stub test marked @pytest.mark.smoke @pytest.mark.genre("my-western")
```

## Fill in the seed

The scaffolder leaves seed files empty. Edit at minimum:

- `books/book-one/seed.txt` — 1–3 paragraphs setting up POV character,
  what they want, what stands in their way, what changes.
- `shared/world.md` — 4–8 sentences of world context (only what the
  smoke test needs to be meaningful).
- `shared/characters.md` — 1–2 minimal character sketches.
- `shared/period_bans.txt` — only if period-sensitive (historical /
  period fantasy).

If your genre has period-specific vocabulary to forbid, seed
`period_bans.txt` with one banned word/phrase per line.

## Write a real assertion

The stub test asserts only that `world.md` was written and is
non-empty. Replace its body with a *genre-characteristic* assertion
per the `REWRITE-PLAN.md` §12a contract:

> At least one assertion on a genre-characteristic behaviour, not just
> "a file was written".

Look at `tests/smoke/test_mystery_smoke.py` or
`tests/smoke/test_fantasy_smoke.py` for the shape. The test should:

1. Run a single `/autonovel:*` command against the fixture.
2. Assert the runtime exited zero.
3. Assert one or more *structural* properties of the produced file
   (regex shape, section presence, distinct-trial count, etc.) — not
   exact word match on prose.

Generous keyword lists are encouraged. The flakiness policy
(`REWRITE-PLAN.md` §12.4) says ordinary LLM drift should not fail the
test — only gross failure should.

## Run the test

```bash
# Free under your subscription auth (claude login).
autonovel test-fixture run my-western

# Or directly:
pytest tests/smoke/test_my_western_smoke.py -q -m smoke
```

## List what you have

```bash
autonovel test-fixture list
# → mystery, thriller, fantasy, my-western, …
```

The CLI marks each fixture with ✓ if it has a paired smoke test, `·`
if it's scaffolded but the test is missing.

## Where to put your own

The eight shipped fixtures live in this repo at `tests/fixtures/`.
Your custom fixtures can either:

1. Live in the autonovel repo's `tests/fixtures/` (open a PR — we
   ship the matrix).
2. Live in your own series repo at `tests/fixtures/` and run against
   your locally-installed autonovel. The scaffolder finds the repo
   root by walking up from cwd looking for `tests/fixtures/` +
   `tests/smoke/`, so it works in any repo with that shape.

## Contract checklist

A fixture is complete when:

- [ ] `project.yaml` is valid (`autonovel doctor --series tests/fixtures/tiny-series-<name>`).
- [ ] `books/book-one/seed.txt` is non-trivial (≥3 sentences).
- [ ] `shared/world.md` and `shared/characters.md` carry minimum genre context.
- [ ] `tests/smoke/test_<name>_smoke.py` is marked `@pytest.mark.smoke @pytest.mark.genre("<name>")`.
- [ ] The test asserts at least one genre-characteristic property.
- [ ] `README.md` explains what genre quirk this fixture exercises.
- [ ] `pytest tests/smoke/test_<name>_smoke.py --collect-only -q` lists the test.
