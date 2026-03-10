from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional


@dataclass
class Record:
    provider: str
    model: str
    timestamp: dt.datetime
    input_tokens: int
    output_tokens: int
    cache_refill_tokens: Optional[int]
    cache_hit_tokens: Optional[int]
    total_tokens: Optional[int]


@dataclass
class Price:
    input_cost_per_token: float
    output_cost_per_token: float
    cache_creation_input_token_cost: float
    cache_read_input_token_cost: float


@dataclass
class AggStats:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_refill_tokens: int = 0
    cache_hit_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    cache_refill_missing: bool = False
    cache_hit_missing: bool = False
