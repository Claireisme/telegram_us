from __future__ import annotations

import unittest

from src.fetchers.options import TrackedOption
from src.fetchers.options import _summarize_polygon_bar
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
        self.assertEqual(summary.data_mode, "trades")

    def test_summarize_polygon_previous_day_bar(self) -> None:
        tracked = TrackedOption(
            underlying="QQQ",
            option_symbol="O:QQQ260821C00600000",
            tradier_option_symbol="QQQ260821C00600000",
            expiration="2026-08-21",
            strike="600",
            side="C",
            theme_tags=["科技"],
        )

        summary = _summarize_polygon_bar(tracked, {"c": 1.25, "v": 4000, "n": 125})

        self.assertEqual(summary.provider, "Polygon Options")
        self.assertEqual(summary.price, 1.25)
        self.assertEqual(summary.total_volume, 4000)
        self.assertEqual(summary.trade_count, 125)
        self.assertEqual(summary.premium, 500000.0)
        self.assertEqual(summary.data_mode, "previous_day_bar")


if __name__ == "__main__":
    unittest.main()
