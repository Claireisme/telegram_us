from __future__ import annotations

import unittest

from src.fetchers.options import TrackedOption
from src.fetchers.options import _summarize_polygon_trades


class OptionsFetcherTest(unittest.TestCase):
    def test_summarize_polygon_trades(self) -> None:
        tracked = TrackedOption(
            underlying="SPY",
            option_symbol="O:SPY260821C00650000",
            tradier_option_symbol="SPY260821C00650000",
            expiration="2026-08-21",
            strike="650",
            side="C",
            theme_tags=["ETF"],
        )

        summary = _summarize_polygon_trades(
            tracked,
            [
                {"price": 2.5, "size": 20},
                {"price": 2.4, "size": 10},
            ],
        )

        self.assertEqual(summary.provider, "Polygon Options")
        self.assertEqual(summary.side, "Call")
        self.assertEqual(summary.premium, 5000.0)
        self.assertEqual(summary.trade_count, 2)
        self.assertEqual(summary.total_volume, 30)


if __name__ == "__main__":
    unittest.main()
