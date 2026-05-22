from __future__ import annotations

import unittest

from vibefetch.models import AggStats
from vibefetch.table import _build_table_rows


class TableTests(unittest.TestCase):
    def test_total_row_marks_cache_refill_as_na_when_any_record_is_missing_it(self) -> None:
        _, total_row = _build_table_rows(
            {
                ("ALL", "model-a"): AggStats(
                    api_calls=1,
                    input_tokens=10,
                    output_tokens=2,
                    cache_refill_tokens=0,
                    cache_hit_tokens=3,
                    total_tokens=12,
                    cache_refill_missing=True,
                )
            },
            daily=False,
        )

        self.assertEqual(total_row["cache_refill_tokens"], "N/A")
        self.assertEqual(total_row["cache_hit_tokens"], "3")


if __name__ == "__main__":
    unittest.main()
