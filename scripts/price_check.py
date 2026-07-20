#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings
from src.fetchers.prices import MarketDataClient
from src.fetchers.prices import PriceFetchError


def main() -> None:
    parser = argparse.ArgumentParser(description="Check daily price data from configured low-cost providers.")
    parser.add_argument("ticker", help="Ticker symbol, for example AAPL.")
    parser.add_argument("--start-date", required=True, help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", default="", help="End date in YYYY-MM-DD format. Defaults to today.")
    args = parser.parse_args()

    settings = Settings.load()
    client = MarketDataClient(
        user_agent=settings.sec_user_agent,
        alpha_vantage_api_key=settings.alpha_vantage_api_key,
    )
    try:
        performance = client.price_performance_since(args.ticker, args.start_date, args.end_date)
    except PriceFetchError as exc:
        raise SystemExit(str(exc)) from exc
    print(performance.summary)
    print(f"source: {performance.source}")


if __name__ == "__main__":
    from src.observability.logging import run_with_logging

    run_with_logging("price_check", main)
