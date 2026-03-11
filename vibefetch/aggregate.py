from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from .models import AggStats, Price, Record
from .pricing import cost_for_record, normalize_model


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
) -> Tuple[Dict[Tuple[str, str], AggStats], List[str], bool]:
    aggregated: Dict[Tuple[str, str], AggStats] = {}
    missing_price_models: List[str] = []
    missing_cache = False
    for record in records:
        date_key = record.timestamp.date().isoformat() if daily else "ALL"
        key = (date_key, record.model)
        stats = aggregated.get(key)
        if stats is None:
            stats = AggStats()
            aggregated[key] = stats
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
        normalized = normalize_model(record.model, price_index)
        price = price_index.get(normalized) if normalized else None
        if price is None and record.model not in missing_price_models:
            missing_price_models.append(record.model)
        stats.cost_usd += cost_for_record(record, price)
    return aggregated, missing_price_models, missing_cache
