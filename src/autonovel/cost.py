"""Cost + token aggregation over `.autonovel/command-log.jsonl`.

Background: until 2026-04-28 the command log captured *what* ran
but not *how expensive* each run was. Author asked about cost
visibility on a real book run; this module rolls up the
per-command token / cost fields the postamble now writes into a
per-book / per-tier / per-command summary.

Caveats:
- Token counts and cost figures are LLM-self-reported (whatever
  the runtime's usage report surfaces). Treat as estimates, not
  invoices.
- Mechanical-only commands leave the fields None and are
  classified `mechanical` here — they're free and shouldn't
  inflate any summed-cost number.
- Cost is sum-only here. The pricing table that maps
  (model, tier) → USD/1Mtok lives next to the runtime adapter
  config; this module accepts whatever cost the postamble wrote.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import command_log


@dataclass
class CostBucket:
    """One row of the cost rollup — a (book, tier, model) cell."""
    runs: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0
    cost_known_runs: int = 0           # rows that carried a non-None cost
    cost_unknown_runs: int = 0         # rows with token data but no cost

    def add(self, entry: command_log.LogEntry) -> None:
        self.runs += 1
        if entry.input_tokens is not None:
            self.input_tokens += entry.input_tokens
        if entry.output_tokens is not None:
            self.output_tokens += entry.output_tokens
        if entry.cache_read_tokens is not None:
            self.cache_read_tokens += entry.cache_read_tokens
        if entry.cache_creation_tokens is not None:
            self.cache_creation_tokens += entry.cache_creation_tokens
        if entry.cost_usd is not None:
            self.cost_usd += entry.cost_usd
            self.cost_known_runs += 1
        elif entry.input_tokens is not None or entry.output_tokens is not None:
            self.cost_unknown_runs += 1


@dataclass
class CostReport:
    total: CostBucket
    by_book: dict[str, CostBucket]
    by_tier: dict[str, CostBucket]
    by_command: dict[str, CostBucket]
    mechanical_runs: int               # rows with no token data at all
    error_runs: int                    # status != "ok"
    log_path: str

    def to_dict(self) -> dict:
        def _bucket_dict(b: CostBucket) -> dict:
            return {
                "runs": b.runs,
                "input_tokens": b.input_tokens,
                "output_tokens": b.output_tokens,
                "cache_read_tokens": b.cache_read_tokens,
                "cache_creation_tokens": b.cache_creation_tokens,
                "cost_usd": round(b.cost_usd, 4),
                "cost_known_runs": b.cost_known_runs,
                "cost_unknown_runs": b.cost_unknown_runs,
            }
        return {
            "log_path": self.log_path,
            "mechanical_runs": self.mechanical_runs,
            "error_runs": self.error_runs,
            "total": _bucket_dict(self.total),
            "by_book": {k: _bucket_dict(v) for k, v in self.by_book.items()},
            "by_tier": {k: _bucket_dict(v) for k, v in self.by_tier.items()},
            "by_command": {k: _bucket_dict(v)
                            for k, v in self.by_command.items()},
        }


# ---------------------------------------------------------- public entry


def build_report(log_path: Path) -> CostReport:
    """Roll up every entry in `command-log.jsonl` into the summary
    shape above. No filtering; every row contributes."""
    entries = command_log.read_all(log_path)
    total = CostBucket()
    by_book: dict[str, CostBucket] = {}
    by_tier: dict[str, CostBucket] = {}
    by_command: dict[str, CostBucket] = {}
    mechanical_runs = 0
    error_runs = 0
    for e in entries:
        if e.status != "ok":
            error_runs += 1
        if (e.input_tokens is None and e.output_tokens is None
                and e.cost_usd is None):
            mechanical_runs += 1
            # Mechanical entries still count under by_book / by_command
            # so the user can see *which* commands ran, just with zero
            # cost. by_tier picks them up under "mechanical".
            tier_key = e.tier or "mechanical"
        else:
            tier_key = e.tier or "unknown"
        total.add(e)
        if e.book:
            by_book.setdefault(e.book, CostBucket()).add(e)
        by_tier.setdefault(tier_key, CostBucket()).add(e)
        by_command.setdefault(e.command, CostBucket()).add(e)
    return CostReport(
        total=total,
        by_book=by_book,
        by_tier=by_tier,
        by_command=by_command,
        mechanical_runs=mechanical_runs,
        error_runs=error_runs,
        log_path=str(log_path),
    )


# ---------------------------------------------------------- render


def render_markdown(report: CostReport) -> str:
    parts: list[str] = []
    parts.append("# Cost summary")
    parts.append("")
    if report.total.runs == 0:
        parts.append("_No commands logged yet._")
        return "\n".join(parts) + "\n"

    t = report.total
    parts.append(
        f"**{t.runs} run(s)** · "
        f"in {t.input_tokens:,} tok · out {t.output_tokens:,} tok · "
        f"cache-read {t.cache_read_tokens:,} tok · "
        f"**${t.cost_usd:.2f}**"
        + (
            f" (across {t.cost_known_runs} cost-tagged runs; "
            f"{t.cost_unknown_runs} runs had tokens but no cost field)"
            if t.cost_unknown_runs else ""
        )
    )
    if report.mechanical_runs:
        parts.append(
            f"\n_{report.mechanical_runs} run(s) were mechanical "
            f"(no LLM call) — counted but $0._"
        )
    if report.error_runs:
        parts.append(f"\n_{report.error_runs} run(s) ended with "
                      "non-`ok` status._")

    if report.by_book:
        parts.append("")
        parts.append("## By book")
        parts.append("")
        parts.append("| Book | Runs | In tok | Out tok | Cost USD |")
        parts.append("|---|---|---|---|---|")
        ranked = sorted(report.by_book.items(),
                         key=lambda kv: -kv[1].cost_usd)
        for book, b in ranked:
            parts.append(
                f"| {book} | {b.runs} | {b.input_tokens:,} | "
                f"{b.output_tokens:,} | ${b.cost_usd:.2f} |"
            )

    if report.by_tier:
        parts.append("")
        parts.append("## By tier")
        parts.append("")
        parts.append("| Tier | Runs | In tok | Out tok | Cost USD |")
        parts.append("|---|---|---|---|---|")
        # Force a consistent order: heavy, standard, light, mechanical, then alphabetical.
        priority = {"heavy": 0, "standard": 1, "light": 2,
                     "mechanical": 3, "unknown": 4}
        ranked = sorted(report.by_tier.items(),
                         key=lambda kv: (priority.get(kv[0], 5), kv[0]))
        for tier, b in ranked:
            parts.append(
                f"| {tier} | {b.runs} | {b.input_tokens:,} | "
                f"{b.output_tokens:,} | ${b.cost_usd:.2f} |"
            )

    if report.by_command:
        parts.append("")
        parts.append("## Top commands by cost")
        parts.append("")
        parts.append("| Command | Runs | In tok | Out tok | Cost USD |")
        parts.append("|---|---|---|---|---|")
        ranked = sorted(report.by_command.items(),
                         key=lambda kv: (-kv[1].cost_usd, -kv[1].runs))
        for cmd, b in ranked[:20]:
            parts.append(
                f"| {cmd} | {b.runs} | {b.input_tokens:,} | "
                f"{b.output_tokens:,} | ${b.cost_usd:.2f} |"
            )

    return "\n".join(parts) + "\n"
