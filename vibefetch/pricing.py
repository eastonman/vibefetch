from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Dict, Optional, Tuple

from .models import Price, Record


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
            input_cost_per_token=float(value.get("input_cost_per_token") or 0.0),
            output_cost_per_token=float(value.get("output_cost_per_token") or 0.0),
            cache_creation_input_token_cost=float(
                value.get("cache_creation_input_token_cost") or 0.0
            ),
            cache_read_input_token_cost=float(
                value.get("cache_read_input_token_cost") or 0.0
            ),
        )
    return index


def normalize_model(model: str, price_index: Dict[str, Price]) -> Optional[str]:
    if model in price_index:
        return model
    lowered = model.lower()
    lowered_index = {k.lower(): k for k in price_index.keys()}
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
