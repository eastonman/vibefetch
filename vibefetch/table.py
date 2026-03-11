from __future__ import annotations

import io
import shutil
from typing import Dict, List, Sequence, Tuple

from .models import AggStats
from .utils import format_cost, format_int

_COLUMN_ORDER = [
    "period",
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

_RIGHT_ALIGN = {
    "api_calls",
    "input_tokens",
    "output_tokens",
    "cache_refill_tokens",
    "cache_hit_tokens",
    "cache_hit_rate",
    "total_tokens",
    "cost",
}


def format_cache_hit_rate(
    input_tokens: int,
    cache_hit_tokens: int,
    cache_hit_missing: bool,
) -> str:
    if cache_hit_missing or input_tokens <= 0:
        return "N/A"
    return f"{(cache_hit_tokens / input_tokens) * 100:.2f}%"


def _column_label(key: str, daily: bool, multiline: bool = True) -> str:
    if key == "period":
        return "date" if daily else "period"
    labels_single = {
        "api_calls": "api_calls",
        "input_tokens": "input_tokens",
        "output_tokens": "output_tokens",
        "cache_refill_tokens": "cache_refill_tokens",
        "cache_hit_tokens": "cache_hit_tokens",
        "cache_hit_rate": "cache_hit_rate",
        "total_tokens": "total_tokens",
        "cost": "cost_usd",
    }
    return labels_single.get(key, key)


def _row_pair(row: Dict[str, str]) -> Tuple[List[str], List[str]]:
    line1 = [
        row["period"],
        row["model"],
        row["api_calls"],
        row["input_tokens"],
        row["output_tokens"],
        row["total_tokens"],
        row["cost"],
    ]
    line2 = [
        "",
        "",
        row["cache_refill_tokens"],
        row["cache_hit_tokens"],
        row["cache_hit_rate"],
        "",
        "",
    ]
    return line1, line2


def _truncate_model_name(name: str, width: int) -> str:
    max_len = 34 if width >= 160 else 28 if width >= 120 else 22 if width >= 92 else 16
    if len(name) <= max_len:
        return name
    if max_len <= 3:
        return name[:max_len]
    return name[: max_len - 3] + "..."


def _apply_table_hints(
    rows: List[Dict[str, str]],
    total_row: Dict[str, str],
    daily: bool,
    width: int,
) -> Tuple[List[Dict[str, str]], Dict[str, str]]:
    adapted_rows: List[Dict[str, str]] = []
    for row in rows:
        current = dict(row)
        if daily and current["model"] != "ALL":
            current["period"] = ""
        current["model"] = _truncate_model_name(current["model"], width)
        adapted_rows.append(current)

    adapted_total = dict(total_row)
    adapted_total["model"] = _truncate_model_name(adapted_total["model"], width)
    return adapted_rows, adapted_total


def _build_table_rows(
    aggregated: Dict[Tuple[str, str], AggStats],
    daily: bool,
) -> Tuple[List[Dict[str, str]], Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    total_stats = AggStats()
    use_daily_all_for_totals = daily and any(
        model == "ALL" for (_, model) in aggregated.keys()
    )

    for (date_key, model), stats in sorted(aggregated.items()):
        row = {
            "period": date_key,
            "model": model,
            "api_calls": format_int(stats.api_calls),
            "input_tokens": format_int(stats.input_tokens),
            "output_tokens": format_int(stats.output_tokens),
            "cache_refill_tokens": (
                "N/A" if stats.cache_refill_missing else format_int(stats.cache_refill_tokens)
            ),
            "cache_hit_tokens": (
                "N/A" if stats.cache_hit_missing else format_int(stats.cache_hit_tokens)
            ),
            "cache_hit_rate": format_cache_hit_rate(
                stats.input_tokens, stats.cache_hit_tokens, stats.cache_hit_missing
            ),
            "total_tokens": format_int(stats.total_tokens),
            "cost": format_cost(stats.cost_usd),
        }
        rows.append(row)

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

    total_row = {
        "period": "TOTAL",
        "model": "ALL",
        "api_calls": format_int(total_stats.api_calls),
        "input_tokens": format_int(total_stats.input_tokens),
        "output_tokens": format_int(total_stats.output_tokens),
        "cache_refill_tokens": format_int(total_stats.cache_refill_tokens),
        "cache_hit_tokens": (
            "N/A" if total_stats.cache_hit_missing else format_int(total_stats.cache_hit_tokens)
        ),
        "cache_hit_rate": format_cache_hit_rate(
            total_stats.input_tokens,
            total_stats.cache_hit_tokens,
            total_stats.cache_hit_missing,
        ),
        "total_tokens": format_int(total_stats.total_tokens),
        "cost": format_cost(total_stats.cost_usd),
    }
    return rows, total_row


def _render_table_rich(
    rows: List[Dict[str, str]],
    total_row: Dict[str, str],
    selected_columns: Sequence[str],
    daily: bool,
    width: int,
) -> str:
    from rich import box
    from rich.console import Console
    from rich.table import Table

    table = Table(
        box=box.ASCII2,
        expand=False,
        pad_edge=False,
        collapse_padding=True,
        show_edge=True,
        show_header=False,
        show_lines=False,
        highlight=False,
    )
    table.add_column(_column_label("period", daily, multiline=False), no_wrap=True, min_width=10)
    table.add_column("model", no_wrap=True, min_width=12)
    table.add_column("api_calls", justify="right", no_wrap=True, min_width=6)
    table.add_column("input", justify="right", no_wrap=True, min_width=7)
    table.add_column("output", justify="right", no_wrap=True, min_width=7)
    table.add_column("total", justify="right", no_wrap=True, min_width=7)
    table.add_column("cost", justify="right", no_wrap=True, min_width=6)

    header1 = [
        _column_label("period", daily, multiline=False),
        "model",
        "api_calls",
        "input",
        "output",
        "total",
        "cost",
    ]
    header2 = ["", "", "cache_refill", "cache_hit", "hit_rate", "", ""]
    table.add_row(*header1, style="bold")
    table.add_row(*header2, style="bold")
    table.add_section()

    for idx, row in enumerate(rows):
        if daily and idx > 0 and row["period"]:
            table.add_section()
        line1, line2 = _row_pair(row)
        table.add_row(*line1)
        table.add_row(*line2)
        if idx < len(rows) - 1:
            next_starts_new_day = daily and bool(rows[idx + 1]["period"])
            if not next_starts_new_day:
                table.add_row("", "", "", "", "", "", "")
    table.add_section()
    total1, total2 = _row_pair(total_row)
    table.add_row(*total1, style="bold")
    table.add_row(*total2, style="bold")

    buffer = io.StringIO()
    console = Console(
        file=buffer,
        width=width,
        color_system=None,
        force_terminal=False,
        highlight=False,
    )
    console.print(table)
    return buffer.getvalue().rstrip()


def _render_table_plain(
    rows: List[Dict[str, str]],
    total_row: Dict[str, str],
    selected_columns: Sequence[str],
    daily: bool,
    width: int,
) -> str:
    headers = [
        _column_label("period", daily, multiline=False),
        "model",
        "api_calls",
        "input",
        "output",
        "total",
        "cost",
    ]
    widths = [len(header) for header in headers]

    lines_for_width: List[List[str]] = [headers, ["", "", "cache_refill", "cache_hit", "hit_rate", "", ""]]
    for row in rows + [total_row]:
        line1, line2 = _row_pair(row)
        lines_for_width.append(line1)
        lines_for_width.append(line2)
    for line in lines_for_width:
        for idx, cell in enumerate(line):
            widths[idx] = max(widths[idx], len(cell))

    lines: List[str] = []
    lines.append(
        "  ".join(
            headers[i].rjust(widths[i]) if i >= 2 else headers[i].ljust(widths[i])
            for i in range(len(headers))
        )
    )
    lines.append("  ".join("-" * width for width in widths))
    lines.append(
        "  ".join(
            lines_for_width[1][i].rjust(widths[i]) if i >= 2 else lines_for_width[1][i].ljust(widths[i])
            for i in range(len(headers))
        )
    )
    lines.append("  ".join("-" * width for width in widths))
    for idx, row in enumerate(rows):
        if daily and idx > 0 and row["period"]:
            lines.append("  ".join("-" * width for width in widths))
        line1, line2 = _row_pair(row)
        lines.append(
            "  ".join(
                line1[i].rjust(widths[i]) if i >= 2 else line1[i].ljust(widths[i])
                for i in range(len(headers))
            )
        )
        lines.append(
            "  ".join(
                line2[i].rjust(widths[i]) if i >= 2 else line2[i].ljust(widths[i])
                for i in range(len(headers))
            )
        )
        if idx < len(rows) - 1:
            next_starts_new_day = daily and bool(rows[idx + 1]["period"])
            if not next_starts_new_day:
                lines.append("  ".join("".ljust(widths[i]) for i in range(len(headers))))
    lines.append("  ".join("-" * width for width in widths))
    total1, total2 = _row_pair(total_row)
    lines.append(
        "  ".join(
            total1[i].rjust(widths[i]) if i >= 2 else total1[i].ljust(widths[i])
            for i in range(len(headers))
        )
    )
    lines.append(
        "  ".join(
            total2[i].rjust(widths[i]) if i >= 2 else total2[i].ljust(widths[i])
            for i in range(len(headers))
        )
    )
    return "\n".join(lines)


def render_table(aggregated: Dict[Tuple[str, str], AggStats], daily: bool) -> str:
    rows, total_row = _build_table_rows(aggregated, daily)
    if not rows:
        return "No records found."

    width = shutil.get_terminal_size(fallback=(120, 40)).columns
    selected_columns = list(_COLUMN_ORDER)
    rows, total_row = _apply_table_hints(rows, total_row, daily, width)

    try:
        return _render_table_rich(rows, total_row, selected_columns, daily, width)
    except Exception:  # noqa: BLE001
        return _render_table_plain(rows, total_row, selected_columns, daily, width)
