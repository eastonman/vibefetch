from __future__ import annotations

import datetime as dt
import json
from typing import Iterable, Optional

from .constants import LOCAL_TZ


def iter_jsonl(path: str) -> Iterable[dict]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return


def parse_timestamp(value: object) -> Optional[dt.datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return dt.datetime.fromtimestamp(float(value), tz=LOCAL_TZ)
        except (ValueError, OSError):
            return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=LOCAL_TZ)
    return parsed.astimezone(LOCAL_TZ)


def safe_int(value: object) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def format_int(value: int) -> str:
    return f"{value:,}"


def format_cost(value: float) -> str:
    return f"{value:,.6f}"


def parse_date(text: Optional[str]) -> Optional[dt.date]:
    if text is None:
        return None
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise SystemExit(f"Invalid date: {text}")
