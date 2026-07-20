from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


class PriceFetchError(RuntimeError):
    """Raised when a market price request cannot be parsed."""


@dataclass(frozen=True)
class PricePerformance:
    ticker: str
    start_close: float
    latest_close: float
    change_percent: float

    @property
    def summary(self) -> str:
        return (
            f"{self.ticker} 从交易日附近收盘价 ${self.start_close:.2f} "
            f"到最新收盘价 ${self.latest_close:.2f}，约 {self.change_percent:+.1f}%"
        )


class YahooChartClient:
    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent or "USStockRadar contact@example.com"

    def price_performance_since(self, ticker: str, start_date: str) -> PricePerformance:
        payload = self._fetch_chart(ticker, start_date)
        closes = _extract_closes(payload)
        if len(closes) < 2:
            raise PriceFetchError(f"not enough daily closes for {ticker}")
        start_close = closes[0]
        latest_close = closes[-1]
        if start_close <= 0:
            raise PriceFetchError(f"invalid start close for {ticker}: {start_close}")
        return PricePerformance(
            ticker=ticker.upper(),
            start_close=start_close,
            latest_close=latest_close,
            change_percent=((latest_close / start_close) - 1) * 100,
        )

    def _fetch_chart(self, ticker: str, start_date: str) -> dict[str, Any]:
        start = datetime.combine(datetime.fromisoformat(start_date).date(), time.min, tzinfo=timezone.utc)
        end = datetime.now(timezone.utc) + timedelta(days=1)
        query = urllib.parse.urlencode(
            {
                "period1": int(start.timestamp()),
                "period2": int(end.timestamp()),
                "interval": "1d",
                "events": "history",
            }
        )
        url = f"{YAHOO_CHART_URL.format(ticker=urllib.parse.quote(ticker.upper()))}?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent}, method="GET")
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))


def _extract_closes(payload: dict[str, Any]) -> list[float]:
    chart = payload.get("chart") or {}
    error = chart.get("error")
    if error:
        raise PriceFetchError(str(error))
    result = chart.get("result") or []
    if not result:
        raise PriceFetchError("empty chart result")
    quote = ((result[0].get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    return [float(value) for value in closes if value is not None]
