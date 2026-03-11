from __future__ import annotations

import datetime as dt
import glob
import json
import os
from typing import Dict, Iterable, List, Optional

from .models import Record
from .utils import iter_jsonl, parse_timestamp, safe_int


def discover_claude_files(root: str) -> List[str]:
    root = os.path.expanduser(root)
    files = []
    history = os.path.join(root, "history.jsonl")
    if os.path.exists(history):
        files.append(history)
    files.extend(
        glob.glob(os.path.join(root, "projects", "**", "*.jsonl"), recursive=True)
    )
    return files


def discover_codex_files(root: str) -> List[str]:
    root = os.path.expanduser(root)
    files = []
    history = os.path.join(root, "history.jsonl")
    if os.path.exists(history):
        files.append(history)
    files.extend(
        glob.glob(os.path.join(root, "sessions", "**", "*.jsonl"), recursive=True)
    )
    return files


def discover_gemini_files(root: str) -> List[str]:
    root = os.path.expanduser(root)
    return glob.glob(
        os.path.join(root, "tmp", "**", "chats", "session-*.json"), recursive=True
    )


def usage_delta(curr: Dict[str, object], prev: Optional[Dict[str, object]]) -> Dict[str, int]:
    if prev is None:
        return {k: safe_int(v) for k, v in curr.items()}
    delta: Dict[str, int] = {}
    for key, value in curr.items():
        now_val = safe_int(value)
        before_val = safe_int(prev.get(key))
        diff = now_val - before_val
        if diff < 0:
            diff = 0
        delta[key] = diff
    return delta


# Normalize vendor-specific fields into a stable schema:
# - input_tokens: total input (cached + uncached)
# - cache_refill_tokens: uncached input (KV refill)
# - cache_hit_tokens: cached input
# - billable_input_tokens / billable_cache_creation_tokens: pricing inputs
def _normalize_claude_usage(
    model: str, timestamp: dt.datetime, usage: Dict[str, object]
) -> Record:
    base_input = safe_int(usage.get("input_tokens"))
    cache_creation_raw = usage.get("cache_creation_input_tokens")
    cache_read_raw = usage.get("cache_read_input_tokens")
    cache_creation = 0 if cache_creation_raw is None else safe_int(cache_creation_raw)
    cache_read = 0 if cache_read_raw is None else safe_int(cache_read_raw)
    input_total = base_input + cache_creation + cache_read
    cache_refill_tokens = base_input + cache_creation
    cache_hit_tokens = None if cache_read_raw is None else cache_read
    total_tokens = usage.get("total_tokens")
    return Record(
        provider="claude",
        model=str(model),
        timestamp=timestamp,
        input_tokens=input_total,
        output_tokens=safe_int(usage.get("output_tokens")),
        cache_refill_tokens=cache_refill_tokens,
        cache_hit_tokens=cache_hit_tokens,
        total_tokens=(None if total_tokens is None else safe_int(total_tokens)),
        billable_input_tokens=base_input,
        billable_cache_creation_tokens=cache_creation,
    )


def _normalize_codex_usage(
    model: str, timestamp: dt.datetime, usage: Dict[str, object]
) -> Record:
    input_total = safe_int(usage.get("input_tokens"))
    cache_hit_raw = usage.get("cached_input_tokens")
    cache_hit = 0 if cache_hit_raw is None else safe_int(cache_hit_raw)
    uncached = input_total if cache_hit_raw is None else max(0, input_total - cache_hit)
    total_tokens = usage.get("total_tokens")
    return Record(
        provider="codex",
        model=str(model),
        timestamp=timestamp,
        input_tokens=input_total,
        output_tokens=safe_int(usage.get("output_tokens")),
        cache_refill_tokens=uncached,
        cache_hit_tokens=(None if cache_hit_raw is None else cache_hit),
        total_tokens=(None if total_tokens is None else safe_int(total_tokens)),
        billable_input_tokens=uncached,
        billable_cache_creation_tokens=0,
    )


def _normalize_gemini_usage(
    model: str, timestamp: dt.datetime, tokens: Dict[str, object]
) -> Record:
    input_total = safe_int(tokens.get("input"))
    cache_hit_raw = tokens.get("cached")
    cache_hit = 0 if cache_hit_raw is None else safe_int(cache_hit_raw)
    uncached = input_total if cache_hit_raw is None else max(0, input_total - cache_hit)
    total_tokens = tokens.get("total")
    return Record(
        provider="gemini",
        model=str(model),
        timestamp=timestamp,
        input_tokens=input_total,
        output_tokens=safe_int(tokens.get("output")),
        cache_refill_tokens=uncached,
        cache_hit_tokens=(None if cache_hit_raw is None else cache_hit),
        total_tokens=(None if total_tokens is None else safe_int(total_tokens)),
        billable_input_tokens=uncached,
        billable_cache_creation_tokens=0,
    )


def parse_claude_records(root: str) -> List[Record]:
    records: List[Record] = []
    for path in discover_claude_files(root):
        for obj in iter_jsonl(path):
            message = obj.get("message")
            if not isinstance(message, dict):
                continue
            usage = message.get("usage")
            if not isinstance(usage, dict):
                continue
            model = message.get("model") or message.get("model_name") or "unknown"
            timestamp = parse_timestamp(obj.get("timestamp") or message.get("timestamp"))
            if timestamp is None:
                continue
            records.append(_normalize_claude_usage(str(model), timestamp, usage))
    return records


def parse_codex_records(root: str) -> List[Record]:
    records: List[Record] = []
    for path in discover_codex_files(root):
        current_model = "unknown"
        prev_total: Optional[Dict[str, object]] = None
        for obj in iter_jsonl(path):
            obj_type = obj.get("type")
            if obj_type == "turn_context":
                payload = obj.get("payload") or {}
                model = payload.get("model")
                if model:
                    current_model = str(model)
                continue
            if obj_type != "event_msg":
                continue
            payload = obj.get("payload") or {}
            if payload.get("type") != "token_count":
                continue
            info = payload.get("info")
            if not isinstance(info, dict):
                continue
            total_usage = info.get("total_token_usage")
            if isinstance(total_usage, dict):
                usage = usage_delta(total_usage, prev_total)
                prev_total = total_usage
            else:
                usage = info.get("last_token_usage")
                if not isinstance(usage, dict):
                    continue
            timestamp = parse_timestamp(obj.get("timestamp"))
            if timestamp is None:
                continue
            records.append(_normalize_codex_usage(current_model, timestamp, usage))
    return records


def parse_gemini_records(root: str) -> List[Record]:
    records: List[Record] = []
    for path in discover_gemini_files(root):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        messages = payload.get("messages")
        if not isinstance(messages, list):
            continue
        for message in messages:
            if not isinstance(message, dict):
                continue
            if message.get("type") != "gemini":
                continue
            tokens = message.get("tokens")
            if not isinstance(tokens, dict):
                continue
            timestamp = parse_timestamp(message.get("timestamp"))
            if timestamp is None:
                continue
            model = message.get("model") or payload.get("model") or "unknown"
            records.append(_normalize_gemini_usage(str(model), timestamp, tokens))
    return records


def filter_by_date(
    records: Iterable[Record], date_from: Optional[dt.date], date_to: Optional[dt.date]
) -> List[Record]:
    filtered = []
    for record in records:
        if record.model == "<synthetic>":
            continue
        day = record.timestamp.date()
        if date_from and day < date_from:
            continue
        if date_to and day > date_to:
            continue
        filtered.append(record)
    return filtered
