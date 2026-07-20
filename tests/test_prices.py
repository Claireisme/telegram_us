from __future__ import annotations

import unittest

from src.fetchers.prices import DailyClose
from src.fetchers.prices import PriceFetchError
from src.fetchers.prices import PricePerformance
from src.fetchers.prices import _extract_alpha_vantage_closes
from src.fetchers.prices import _extract_stooq_closes
from src.fetchers.prices import _extract_yahoo_closes


class PriceFetcherTest(unittest.TestCase):
    def test_extract_yahoo_closes_skips_null_values(self) -> None:
        payload = {
            "chart": {
                "result": [
                    {
                        "timestamp": [1_704_067_200, 1_704_153_600, 1_704_240_000],
                        "indicators": {
                            "quote": [
                                {
                                    "close": [10.0, None, 12.5],
                                }
                            ]
                        },
                    }
                ],
                "error": None,
            }
        }

        closes = _extract_yahoo_closes(payload)

        self.assertEqual([item.close for item in closes], [10.0, 12.5])
        self.assertEqual(closes[0].source, "Yahoo Finance")

    def test_extract_alpha_vantage_closes_filters_date_range(self) -> None:
        payload = {
            "Time Series (Daily)": {
                "2026-07-17": {"4. close": "212.6700"},
                "2026-07-16": {"4. close": "219.0500"},
                "2026-07-15": {"4. close": "211.2000"},
            }
        }

        closes = _extract_alpha_vantage_closes(payload, "2026-07-16", "2026-07-17")

        self.assertEqual(
            closes,
            [
                DailyClose(date="2026-07-16", close=219.05, source="Alpha Vantage"),
                DailyClose(date="2026-07-17", close=212.67, source="Alpha Vantage"),
            ],
        )

    def test_extract_stooq_closes_from_csv(self) -> None:
        text = "Date,Open,High,Low,Close,Volume\n2026-07-16,10,11,9,10.5,100\n"

        self.assertEqual(
            _extract_stooq_closes(text),
            [DailyClose(date="2026-07-16", close=10.5, source="Stooq")],
        )

    def test_stooq_html_challenge_is_a_fetch_error(self) -> None:
        with self.assertRaises(PriceFetchError):
            _extract_stooq_closes("<!doctype html><script>verify</script>")

    def test_price_performance_summary(self) -> None:
        performance = PricePerformance(
            ticker="INTC",
            start_close=100.0,
            latest_close=112.5,
            change_percent=12.5,
            source="Yahoo Finance",
        )

        self.assertEqual(
            performance.summary,
            "INTC 从交易日附近收盘价 $100.00 到最新收盘价 $112.50，约 +12.5%",
        )


if __name__ == "__main__":
    unittest.main()
