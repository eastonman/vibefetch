from __future__ import annotations

import unittest

from vibefetch.pricing import build_price_index, normalize_model


class PricingTests(unittest.TestCase):
    def test_build_price_index_defaults_malformed_numeric_fields_to_zero(self) -> None:
        index = build_price_index(
            {
                "model-a": {
                    "input_cost_per_token": "not-a-number",
                    "output_cost_per_token": 0.2,
                    "cache_creation_input_token_cost": None,
                    "cache_read_input_token_cost": "0.05",
                }
            }
        )

        price = index["model-a"]
        self.assertEqual(price.input_cost_per_token, 0.0)
        self.assertEqual(price.output_cost_per_token, 0.2)
        self.assertEqual(price.cache_creation_input_token_cost, 0.0)
        self.assertEqual(price.cache_read_input_token_cost, 0.05)

    def test_normalize_model_matches_case_insensitive_provider_suffix(self) -> None:
        index = build_price_index(
            {
                "gpt-5.4": {
                    "input_cost_per_token": 0.1,
                    "output_cost_per_token": 0.2,
                }
            }
        )

        self.assertEqual(normalize_model("openai/GPT-5.4", index), "gpt-5.4")


if __name__ == "__main__":
    unittest.main()
