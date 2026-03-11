from __future__ import annotations

from typing import Dict, List, Tuple

from .models import AggStats
from .utils import format_cost, format_int


def format_cache_hit_rate(
    input_tokens: int, cache_hit_tokens: int, cache_hit_missing: bool
) -> str:
    if cache_hit_missing or input_tokens <= 0:
        return "N/A"
    return f"{(cache_hit_tokens / input_tokens) * 100:.2f}%"


def render_table(aggregated: Dict[Tuple[str, str], AggStats], daily: bool) -> str:
    headers = [
        "date" if daily else "period",
        "model",
        "api_calls",
        "input_tokens",
        "output_tokens",
        "cache_refill_tokens",
        "cache_hit_tokens",
        "cache_hit_rate",
        "total_tokens",
        "cost",
    ]
    rows: List[List[str]] = []
    total_stats = AggStats()
    use_daily_all_for_totals = daily and any(
        model == "ALL" for (_, model) in aggregated.keys()
    )
    for (date_key, model), stats in sorted(aggregated.items()):
        cache_refill = (
            "N/A"
            if stats.cache_refill_missing
            else format_int(stats.cache_refill_tokens)
        )
        cache_hit = (
            "N/A" if stats.cache_hit_missing else format_int(stats.cache_hit_tokens)
        )
        cache_hit_rate = format_cache_hit_rate(
            stats.input_tokens, stats.cache_hit_tokens, stats.cache_hit_missing
        )
        rows.append(
            [
                date_key,
                model,
                format_int(stats.api_calls),
                format_int(stats.input_tokens),
                format_int(stats.output_tokens),
                cache_refill,
                cache_hit,
                cache_hit_rate,
                format_int(stats.total_tokens),
                format_cost(stats.cost_usd),
            ]
        )
        if use_daily_all_for_totals and model != "ALL":
            continue
        total_stats.api_calls += stats.api_calls
        total_stats.input_tokens += stats.input_tokens
        total_stats.output_tokens += stats.output_tokens
        total_stats.cache_refill_tokens += stats.cache_refill_tokens
        total_stats.cache_hit_tokens += stats.cache_hit_tokens
        total_stats.total_tokens += stats.total_tokens
        total_stats.cost_usd += stats.cost_usd
        if stats.cache_refill_missing:
            total_stats.cache_refill_missing = True
        if stats.cache_hit_missing:
            total_stats.cache_hit_missing = True
    if not rows:
        return "No records found."
    total_row = [
        "TOTAL",
        "ALL",
        format_int(total_stats.api_calls),
        format_int(total_stats.input_tokens),
        format_int(total_stats.output_tokens),
        format_int(total_stats.cache_refill_tokens),
        "N/A"
        if total_stats.cache_hit_missing
        else format_int(total_stats.cache_hit_tokens),
        format_cache_hit_rate(
            total_stats.input_tokens,
            total_stats.cache_hit_tokens,
            total_stats.cache_hit_missing,
        ),
        format_int(total_stats.total_tokens),
        format_cost(total_stats.cost_usd),
    ]
    widths = [len(h) for h in headers]
    for row in rows + [total_row]:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))
    align_right = {2, 3, 4, 5, 6, 7, 8, 9}
    lines = []
    header_line = "  ".join(
        headers[i].rjust(widths[i]) if i in align_right else headers[i].ljust(widths[i])
        for i in range(len(headers))
    )
    lines.append(header_line)
    lines.append("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        lines.append(
            "  ".join(
                row[i].rjust(widths[i]) if i in align_right else row[i].ljust(widths[i])
                for i in range(len(row))
            )
        )
    lines.append("  ".join("-" * widths[i] for i in range(len(headers))))
    lines.append(
        "  ".join(
            total_row[i].rjust(widths[i])
            if i in align_right
            else total_row[i].ljust(widths[i])
            for i in range(len(total_row))
        )
    )
    return "\n".join(lines)
