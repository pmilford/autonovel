# bells-reference

Tier-4 regression fixture. Holds frozen chapter text plus the scores the
pre-rewrite `evaluate.py` produced on them, so the PR-4 rewrite of
`/autonovel:evaluate` can be checked for drift.

## Layout

```
bells-reference/
├── chapters/        # frozen chapter files (ch_01.md, ch_02.md, ...)
├── scores.json      # frozen reference scores keyed by chapter number
└── README.md        # this file
```

`chapters/` is mostly empty on `master` because the actual Bells
chapters live on the `autonovel/bells` branch (see the Branch model in
`CLAUDE.md`). To populate:

```bash
git show autonovel/bells:chapters/ch_01.md > tests/fixtures/bells-reference/chapters/ch_01.md
# ...for each chapter
```

## scores.json format

```json
{
  "evaluate_version": "pre-rewrite evaluate.py @ <commit>",
  "chapters": {
    "01": {"overall_score": 7.42, "slop_penalty": 0.4, "raw_judge_score": 7.82},
    "02": {"overall_score": 6.93, "slop_penalty": 0.9, "raw_judge_score": 7.83},
    "...": "..."
  }
}
```

## Regression harness

The harness lives at `tests/smoke/test_bells_regression.py`. It is
gated on `@pytest.mark.bells_regression` and on the fixture being
populated — it skips cleanly when `chapters/` is empty. Policy:

- `slop_penalty` is deterministic and drift-checked to `< 0.1` exactly
  (it's a pure-Python regex score; any change reflects a real regex
  change to `src/autonovel/mechanical/slop.py`).
- `overall_score` is LLM-judged and drift-checked to `< 0.5`, as
  specified in `REWRITE-PLAN.md` §12.4.

## When to re-freeze

Re-freeze this file only when `src/autonovel/mechanical/slop.py` or the
evaluate command's prompt materially changes and the drift is
expected. Re-freezing requires approval from a human; an autonomous
run that *wants* to re-freeze must stop and ask.
