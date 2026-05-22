from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Dict, Optional, Tuple

from .models import Price, Record


def _safe_float(value: object) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_pricing(
    url: str, timeout: float, cache_path: str
) -> Tuple[Dict[str, dict], str]:
    cache_path = os.path.expanduser(cache_path)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = json.load(response)
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        return data, "fetched"
    except Exception as exc:  # noqa: BLE001
        is_timeout = isinstance(exc, socket.timeout)
        if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, socket.timeout):
            is_timeout = True
        if os.path.exists(cache_path):
            if is_timeout:
                with open(cache_path, "r", encoding="utf-8") as handle:
                    return json.load(handle), "cache_timeout"
            with open(cache_path, "r", encoding="utf-8") as handle:
                return json.load(handle), "cache_error"
        raise


def build_price_index(pricing: Dict[str, dict]) -> Dict[str, Price]:
    index: Dict[str, Price] = {}
    for key, value in pricing.items():
        if not isinstance(value, dict):
            continue
        index[key] = Price(
            input_cost_per_token=_safe_float(value.get("input_cost_per_token")),
            output_cost_per_token=_safe_float(value.get("output_cost_per_token")),
            cache_creation_input_token_cost=_safe_float(
                value.get("cache_creation_input_token_cost")
            ),
            cache_read_input_token_cost=_safe_float(
                value.get("cache_read_input_token_cost")
            ),
        )
    return index


def build_model_lookup(price_index: Dict[str, Price]) -> Dict[str, str]:
    return {key.lower(): key for key in price_index.keys()}


def normalize_model(
    model: str,
    price_index: Dict[str, Price],
    lowered_index: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    if model in price_index:
        return model
    if lowered_index is None:
        lowered_index = build_model_lookup(price_index)
    lowered = model.lower()
    if lowered in lowered_index:
        return lowered_index[lowered]
    if "/" in model:
        candidate = model.split("/")[-1]
        if candidate in price_index:
            return candidate
        lowered_candidate = candidate.lower()
        if lowered_candidate in lowered_index:
            return lowered_index[lowered_candidate]
    return None


def cost_for_record(record: Record, price: Optional[Price]) -> float:
    if price is None:
        return 0.0
    cache_hit = 0 if record.cache_hit_tokens is None else record.cache_hit_tokens
    input_cost = record.billable_input_tokens * price.input_cost_per_token
    output_cost = record.output_tokens * price.output_cost_per_token
    cache_refill_cost = (
        record.billable_cache_creation_tokens * price.cache_creation_input_token_cost
    )
    cache_hit_cost = cache_hit * price.cache_read_input_token_cost
    return input_cost + output_cost + cache_refill_cost + cache_hit_cost
