from __future__ import annotations

import datetime as dt
import sys
from typing import Dict, Iterable, List, Tuple, Optional

from .aggregate import record_total_tokens
from .models import Record


def render_chart(
    records: Iterable[Record],
    chart_models: Optional[List[str]],
    chart_top: int,
    mode: str,
) -> None:
    try:
        import plotext as plt
    except ImportError:
        print("plotext not installed; skipping chart.", file=sys.stderr)
        return
    if mode not in {"hourly", "daily"}:
        raise ValueError(f"Unsupported chart mode: {mode}")
    buckets: Dict[Tuple[dt.datetime, str], int] = {}
    for record in records:
        if mode == "hourly":
            bucket = record.timestamp.replace(minute=0, second=0, microsecond=0)
        else:
            bucket = record.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        key = (bucket, record.model)
        buckets[key] = buckets.get(key, 0) + record_total_tokens(record)
    if not buckets:
        print(f"No {mode} stats available for chart.", file=sys.stderr)
        return
    bucket_times = sorted({bucket for bucket, _ in buckets.keys()})
    if not bucket_times:
        print(f"No {mode} stats available for chart.", file=sys.stderr)
        return
    start_bucket = min(bucket_times)
    end_bucket = max(bucket_times)
    all_buckets: List[dt.datetime] = []
    current = start_bucket
    step = dt.timedelta(hours=1) if mode == "hourly" else dt.timedelta(days=1)
    while current <= end_bucket:
        all_buckets.append(current)
        current += step
    if mode == "hourly":
        bucket_labels = [bucket.strftime("%Y-%m-%d %H:00") for bucket in all_buckets]
    else:
        bucket_labels = [bucket.strftime("%Y-%m-%d") for bucket in all_buckets]

    model_totals: Dict[str, int] = {}
    for (_, model), tokens in buckets.items():
        model_totals[model] = model_totals.get(model, 0) + tokens
    if chart_models:
        models = [m for m in chart_models if m in model_totals]
    else:
        models = [
            model
            for model, _ in sorted(
                model_totals.items(), key=lambda item: item[1], reverse=True
            )
        ][: max(chart_top, 1)]
    if not models:
        print("No models selected for chart.", file=sys.stderr)
        return

    series = {model: [0 for _ in all_buckets] for model in models}
    bucket_index = {bucket: idx for idx, bucket in enumerate(all_buckets)}
    for (bucket, model), tokens in buckets.items():
        if model not in series:
            continue
        series[model][bucket_index[bucket]] += tokens

    max_tokens = 0
    for values in series.values():
        if values:
            max_tokens = max(max_tokens, max(values))
    if max_tokens >= 1_000_000:
        scale_div = 1_000_000
        scale_suffix = "M"
    elif max_tokens >= 1_000:
        scale_div = 1_000
        scale_suffix = "K"
    else:
        scale_div = 1
        scale_suffix = ""

    color_cycle = [
        "red",
        "green",
        "blue",
        "cyan",
        "magenta",
        "orange",
        "gray",
        "red+",
        "green+",
        "blue+",
        "cyan+",
        "magenta+",
        "orange+",
        "gray+",
    ]
    color_map = {
        model: color_cycle[i % len(color_cycle)] for i, model in enumerate(models)
    }
    legend_lines = ["", "Legend:"]
    for model in models:
        color = color_map[model]
        legend_lines.append(f"{plt.colorize('■', color)} {plt.colorize(model, color)}")

    plt.clear_figure()
    ylabel = f"Tokens ({scale_suffix})" if scale_suffix else "Tokens"
    chart_title = f"{ylabel} per Hour" if mode == "hourly" else f"{ylabel} per Day"
    plt.title(chart_title)
    plt.xlabel("Time" if mode == "hourly" else "Date")
    term_width, term_height = plt.terminal_size()
    if term_width and term_height:
        target_height = max(10, min(term_height, term_width // 4))
        plt.plotsize(term_width, target_height)

    x_positions = list(range(len(all_buckets)))
    stacked_values = [
        [value / scale_div for value in series[model]] for model in models
    ]
    plt.stacked_bar(
        x_positions,
        stacked_values,
        color=[color_map[model] for model in models],
    )
    plt.xticks(x_positions, bucket_labels)
    print("\n".join(legend_lines))
    plt.show()
