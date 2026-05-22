from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple

from .models import AggStats, Price, Record
from .pricing import build_model_lookup, cost_for_record, normalize_model


def record_total_tokens(record: Record) -> int:
    if record.total_tokens is not None:
        return record.total_tokens
    return (
        record.input_tokens
        + record.output_tokens
    )


def aggregate_records(
    records: Iterable[Record],
    daily: bool,
    price_index: Dict[str, Price],
    merge_models: bool = False,
) -> Tuple[Dict[Tuple[str, str], AggStats], List[str], bool]:
    aggregated: Dict[Tuple[str, str], AggStats] = {}
    missing_price_models: List[str] = []
    missing_price_seen: Set[str] = set()
    missing_cache = False
    model_lookup = build_model_lookup(price_index)
    for record in records:
        date_key = record.timestamp.date().isoformat() if daily else "ALL"
        model_key = "ALL" if merge_models else record.model
        key = (date_key, model_key)
        stats = aggregated.get(key)
        if stats is None:
            stats = AggStats()
            aggregated[key] = stats
        stats.api_calls += 1
        stats.input_tokens += record.input_tokens
        stats.output_tokens += record.output_tokens
        if record.cache_refill_tokens is None:
            stats.cache_refill_missing = True
            missing_cache = True
        else:
            stats.cache_refill_tokens += record.cache_refill_tokens
        if record.cache_hit_tokens is None:
            stats.cache_hit_missing = True
            missing_cache = True
        else:
            stats.cache_hit_tokens += record.cache_hit_tokens
        stats.total_tokens += record_total_tokens(record)
        normalized = normalize_model(record.model, price_index, model_lookup)
        price = price_index.get(normalized) if normalized else None
        if price is None and record.model not in missing_price_seen:
            missing_price_seen.add(record.model)
            missing_price_models.append(record.model)
        stats.cost_usd += cost_for_record(record, price)
    return aggregated, missing_price_models, missing_cache
