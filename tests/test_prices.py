from __future__ import annotations

import unittest

from src.fetchers.prices import PricePerformance
from src.fetchers.prices import _extract_closes


class PriceFetcherTest(unittest.TestCase):
    def test_extract_closes_skips_null_values(self) -> None:
        payload = {
            "chart": {
                "result": [
                    {
                        "indicators": {
                            "quote": [
                                {
                                    "close": [10.0, None, 12.5],
                                }
                            ]
                        }
                    }
                ],
                "error": None,
            }
        }

        self.assertEqual(_extract_closes(payload), [10.0, 12.5])

    def test_price_performance_summary(self) -> None:
        performance = PricePerformance(
            ticker="INTC",
            start_close=100.0,
            latest_close=112.5,
            change_percent=12.5,
        )

        self.assertEqual(
            performance.summary,
            "INTC 从交易日附近收盘价 $100.00 到最新收盘价 $112.50，约 +12.5%",
        )


if __name__ == "__main__":
    unittest.main()
