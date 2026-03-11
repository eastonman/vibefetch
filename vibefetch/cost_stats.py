#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from typing import Dict, List, Optional, Tuple

from .aggregate import aggregate_records
from .chart import render_chart
from .constants import CACHE_PATH, DEFAULT_PRICING_URL
from .logs import (
    filter_by_date,
    parse_claude_records,
    parse_codex_records,
    parse_gemini_records,
)
from .models import AggStats
from .pricing import build_price_index, load_pricing
from .table import render_table
from .utils import parse_date


def parse_args(argv: Optional[List[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Vibe coding cost stats for Claude, Codex, and Gemini logs."
    )
    parser.add_argument("--claude-root", default="~/.claude", help="Claude log root.")
    parser.add_argument("--codex-root", default="~/.codex", help="Codex log root.")
    parser.add_argument("--gemini-root", default="~/.gemini", help="Gemini log root.")
    parser.add_argument("--from", dest="date_from", help="Start date (YYYY-MM-DD).")
    parser.add_argument("--to", dest="date_to", help="End date (YYYY-MM-DD).")
    parser.add_argument("--daily", action="store_true", help="Group stats per day.")
    parser.add_argument(
        "--chart",
        action="store_true",
        help="Alias for --hourly-chart.",
    )
    parser.add_argument(
        "--hourly-chart",
        action="store_true",
        help="Draw an hourly chart in the CLI.",
    )
    parser.add_argument(
        "--daily-chart",
        action="store_true",
        help="Draw a daily chart in the CLI.",
    )
    parser.add_argument(
        "--chart-top",
        type=int,
        default=6,
        help="Max models to include in chart when --chart-models is not provided.",
    )
    parser.add_argument(
        "--chart-models",
        help="Comma-separated list of models to plot in the chart.",
    )
    parser.add_argument(
        "--pricing-url",
        default=os.getenv("LITELLM_PRICING_URL", DEFAULT_PRICING_URL),
        help="LiteLLM pricing JSON URL.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Pricing fetch timeout in seconds.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    date_from = parse_date(args.date_from)
    date_to = parse_date(args.date_to)
    if date_from is None and date_to is None:
        date_to = dt.date.today()
        date_from = date_to - dt.timedelta(days=6)

    records = []
    records.extend(parse_claude_records(args.claude_root))
    records.extend(parse_codex_records(args.codex_root))
    records.extend(parse_gemini_records(args.gemini_root))

    records = filter_by_date(records, date_from, date_to)
    if not records:
        print("No records found.")
        return 0

    try:
        pricing_raw, pricing_source = load_pricing(
            args.pricing_url, args.timeout, CACHE_PATH
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to load pricing data: {exc}", file=sys.stderr)
        return 1

    price_index = build_price_index(pricing_raw)
    aggregated_overall, missing_models, missing_cache = aggregate_records(
        records, daily=False, price_index=price_index, merge_models=False
    )
    aggregated_daily: Optional[Dict[Tuple[str, str], AggStats]] = None
    if args.daily:
        aggregated_daily_totals, _, _ = aggregate_records(
            records, daily=True, price_index=price_index, merge_models=True
        )
        aggregated_daily_per_model, _, _ = aggregate_records(
            records, daily=True, price_index=price_index, merge_models=False
        )
        aggregated_daily = dict(aggregated_daily_per_model)
        aggregated_daily.update(aggregated_daily_totals)

    print(f"Pricing source: {pricing_source}")
    if missing_models:
        print(
            "Missing pricing for models: " + ", ".join(sorted(missing_models)),
            file=sys.stderr,
        )
    if missing_cache:
        print(
            "Cache token fields missing in some records; cache columns show N/A and cache costs treated as 0.",
            file=sys.stderr,
        )
    if args.daily:
        table = render_table(aggregated_daily or {}, daily=True)
    else:
        table = render_table(aggregated_overall, daily=False)
    print(table)

    chart_modes: List[str] = []
    if args.hourly_chart or args.chart:
        chart_modes.append("hourly")
    if args.daily_chart:
        chart_modes.append("daily")
    if chart_modes:
        chart_models = (
            [m.strip() for m in args.chart_models.split(",") if m.strip()]
            if args.chart_models
            else None
        )
        for mode in chart_modes:
            render_chart(records, chart_models, args.chart_top, mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
