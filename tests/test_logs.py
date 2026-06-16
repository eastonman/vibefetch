from __future__ import annotations

import json
import os
import tempfile
import unittest
from typing import Iterable

from vibefetch.logs import parse_omp_records


def write_jsonl(path: str, entries: Iterable[object]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")


class OmpLogTests(unittest.TestCase):
    def test_parse_omp_records_reads_assistant_usage_from_session_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            session_dir = os.path.join(root, "agent", "sessions", "project")
            os.makedirs(session_dir)
            session_path = os.path.join(session_dir, "session.jsonl")
            write_jsonl(
                session_path,
                [
                    {
                        "type": "message",
                        "timestamp": "2026-06-16T04:09:52.372Z",
                        "message": {
                            "role": "assistant",
                            "provider": "ysyx",
                            "model": "gpt-5.5",
                            "usage": {
                                "input": 100,
                                "output": 25,
                                "cacheRead": 30,
                                "cacheWrite": 10,
                                "totalTokens": 165,
                            },
                        },
                    }
                ],
            )

            records = parse_omp_records(root)

            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(record.provider, "omp")
            self.assertEqual(record.model, "gpt-5.5")
            self.assertEqual(record.input_tokens, 140)
            self.assertEqual(record.output_tokens, 25)
            self.assertEqual(record.cache_refill_tokens, 110)
            self.assertEqual(record.cache_hit_tokens, 30)
            self.assertEqual(record.total_tokens, 165)
            self.assertEqual(record.billable_input_tokens, 100)
            self.assertEqual(record.billable_cache_creation_tokens, 10)
            self.assertEqual(record.timestamp.isoformat(), "2026-06-16T12:09:52.372000+08:00")

    def test_parse_omp_records_strips_provider_prefix_from_model(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            session_dir = os.path.join(root, "agent", "sessions")
            os.makedirs(session_dir)
            session_path = os.path.join(session_dir, "session.jsonl")
            write_jsonl(
                session_path,
                [
                    {
                        "type": "message",
                        "timestamp": "2026-06-16T04:09:52.372Z",
                        "message": {
                            "role": "assistant",
                            "provider": provider,
                            "model": f"{provider}/gpt-5.5",
                            "usage": {
                                "input": 1,
                                "output": 1,
                                "cacheRead": 0,
                                "cacheWrite": 0,
                                "totalTokens": 2,
                            },
                        },
                    }
                    for provider in ("veriops", "ysyx")
                ],
            )

            records = parse_omp_records(root)

            self.assertEqual([record.model for record in records], ["gpt-5.5", "gpt-5.5"])

    def test_parse_omp_records_ignores_non_assistant_and_missing_usage_messages(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            session_dir = os.path.join(root, "sessions")
            os.makedirs(session_dir)
            session_path = os.path.join(session_dir, "session.jsonl")
            write_jsonl(
                session_path,
                [
                    {
                        "type": "message",
                        "timestamp": "2026-06-16T04:09:43.511Z",
                        "message": {"role": "user", "model": "gpt-5.5"},
                    },
                    {
                        "type": "message",
                        "timestamp": "2026-06-16T04:09:52.372Z",
                        "message": {"role": "assistant", "model": "gpt-5.5"},
                    },
                    {
                        "type": "model_change",
                        "timestamp": "2026-06-16T04:09:39.239Z",
                        "model": "ysyx/gpt-5.5",
                    },
                ],
            )

            self.assertEqual(parse_omp_records(root), [])

    def test_parse_omp_records_keeps_nonzero_usage_without_total_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            session_dir = os.path.join(root, "agent", "sessions")
            os.makedirs(session_dir)
            session_path = os.path.join(session_dir, "session.jsonl")
            write_jsonl(
                session_path,
                [
                    {
                        "type": "message",
                        "timestamp": "2026-06-16T04:09:52.372Z",
                        "message": {
                            "role": "assistant",
                            "model": "gpt-5.5",
                            "usage": {
                                "input": 12,
                                "output": 3,
                                "cacheRead": 4,
                                "cacheWrite": 1,
                            },
                        },
                    }
                ],
            )

            records = parse_omp_records(root)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].input_tokens, 17)
            self.assertEqual(records[0].total_tokens, None)

    def test_parse_omp_records_ignores_zero_token_error_messages(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            session_dir = os.path.join(root, "agent", "sessions")
            os.makedirs(session_dir)
            session_path = os.path.join(session_dir, "session.jsonl")
            write_jsonl(
                session_path,
                [
                    {
                        "type": "message",
                        "timestamp": "2026-06-16T04:08:03.335Z",
                        "message": {
                            "role": "assistant",
                            "model": "gpt-5.5",
                            "usage": {
                                "input": 0,
                                "output": 0,
                                "cacheRead": 0,
                                "cacheWrite": 0,
                                "totalTokens": 0,
                            },
                            "stopReason": "error",
                        },
                    }
                ],
            )

            self.assertEqual(parse_omp_records(root), [])


if __name__ == "__main__":
    unittest.main()
