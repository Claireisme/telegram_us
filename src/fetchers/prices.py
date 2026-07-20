from __future__ import annotations

import csv
import io
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Protocol


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
STOOQ_DAILY_URL = "https://stooq.com/q/d/l/"


class PriceFetchError(RuntimeError):
    """Raised when a market price request cannot be parsed."""


@dataclass(frozen=True)
class DailyClose:
    date: str
    close: float
    source: str


@dataclass(frozen=True)
class PricePerformance:
    ticker: str
    start_close: float
    latest_close: float
    change_percent: float
    source: str

    @property
    def summary(self) -> str:
        return (
            f"{self.ticker} 从交易日附近收盘价 ${self.start_close:.2f} "
            f"到最新收盘价 ${self.latest_close:.2f}，约 {self.change_percent:+.1f}%"
        )


class PriceProvider(Protocol):
    source_name: str

    def daily_closes(self, ticker: str, start_date: str, end_date: str) -> list[DailyClose]:
        ...


class MarketDataClient:
    def __init__(self, user_agent: str, alpha_vantage_api_key: str = "") -> None:
        self.providers: list[PriceProvider] = [YahooChartProvider(user_agent)]
        if alpha_vantage_api_key:
            self.providers.append(AlphaVantageProvider(user_agent, alpha_vantage_api_key))
        self.providers.append(StooqProvider(user_agent))

    def daily_closes(self, ticker: str, start_date: str, end_date: str = "") -> list[DailyClose]:
        errors = []
        resolved_end_date = end_date or date.today().isoformat()
        for provider in self.providers:
            try:
                closes = provider.daily_closes(ticker, start_date, resolved_end_date)
            except Exception as exc:
                errors.append(f"{provider.source_name}: {exc}")
                continue
            if closes:
                return closes
            errors.append(f"{provider.source_name}: no closes")
        raise PriceFetchError("; ".join(errors) or f"no price provider available for {ticker}")

    def price_performance_since(self, ticker: str, start_date: str, end_date: str = "") -> PricePerformance:
        closes = self.daily_closes(ticker, start_date, end_date)
        if len(closes) < 2:
            raise PriceFetchError(f"not enough daily closes for {ticker}")
        start_close = closes[0].close
        latest_close = closes[-1].close
        if start_close <= 0:
            raise PriceFetchError(f"invalid start close for {ticker}: {start_close}")
        return PricePerformance(
            ticker=ticker.upper(),
            start_close=start_close,
            latest_close=latest_close,
            change_percent=((latest_close / start_close) - 1) * 100,
            source=closes[-1].source,
        )


class YahooChartProvider:
    source_name = "Yahoo Finance"

    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent or "USStockRadar contact@example.com"

    def daily_closes(self, ticker: str, start_date: str, end_date: str) -> list[DailyClose]:
        payload = self._fetch_chart(ticker, start_date, end_date)
        return _extract_yahoo_closes(payload, self.source_name)

    def _fetch_chart(self, ticker: str, start_date: str, end_date: str) -> dict[str, Any]:
        start = _date_to_utc_timestamp(start_date)
        end = _date_to_utc_timestamp(end_date) + 86400
        query = urllib.parse.urlencode(
            {
                "period1": start,
                "period2": end,
                "interval": "1d",
                "events": "history",
            }
        )
        url = f"{YAHOO_CHART_URL.format(ticker=urllib.parse.quote(ticker.upper()))}?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent}, method="GET")
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))


class AlphaVantageProvider:
    source_name = "Alpha Vantage"

    def __init__(self, user_agent: str, api_key: str) -> None:
        self.user_agent = user_agent or "USStockRadar contact@example.com"
        self.api_key = api_key

    def daily_closes(self, ticker: str, start_date: str, end_date: str) -> list[DailyClose]:
        query = urllib.parse.urlencode(
            {
                "function": "TIME_SERIES_DAILY",
                "symbol": ticker.upper(),
                "outputsize": "full",
                "apikey": self.api_key,
            }
        )
        request = urllib.request.Request(
            f"{ALPHA_VANTAGE_URL}?{query}",
            headers={"User-Agent": self.user_agent},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return _extract_alpha_vantage_closes(payload, start_date, end_date, self.source_name)


class StooqProvider:
    source_name = "Stooq"

    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent or "USStockRadar contact@example.com"

    def daily_closes(self, ticker: str, start_date: str, end_date: str) -> list[DailyClose]:
        query = urllib.parse.urlencode(
            {
                "s": f"{ticker.lower()}.us",
                "i": "d",
                "d1": start_date.replace("-", ""),
                "d2": end_date.replace("-", ""),
            }
        )
        request = urllib.request.Request(
            f"{STOOQ_DAILY_URL}?{query}",
            headers={"User-Agent": self.user_agent},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            text = response.read().decode("utf-8", errors="replace")
        return _extract_stooq_closes(text, self.source_name)


def _extract_yahoo_closes(payload: dict[str, Any], source_name: str = "Yahoo Finance") -> list[DailyClose]:
    chart = payload.get("chart") or {}
    error = chart.get("error")
    if error:
        raise PriceFetchError(str(error))
    result = chart.get("result") or []
    if not result:
        raise PriceFetchError("empty chart result")
    timestamps = result[0].get("timestamp") or []
    quote = ((result[0].get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    daily_closes = []
    for timestamp, close in zip(timestamps, closes):
        if close is None:
            continue
        daily_closes.append(
            DailyClose(
                date=datetime.fromtimestamp(int(timestamp), tz=timezone.utc).date().isoformat(),
                close=float(close),
                source=source_name,
            )
        )
    return daily_closes


def _extract_alpha_vantage_closes(
    payload: dict[str, Any],
    start_date: str,
    end_date: str,
    source_name: str = "Alpha Vantage",
) -> list[DailyClose]:
    if "Error Message" in payload:
        raise PriceFetchError(payload["Error Message"])
    if "Note" in payload:
        raise PriceFetchError(payload["Note"])
    series = payload.get("Time Series (Daily)") or {}
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    closes = []
    for raw_date, values in series.items():
        current = date.fromisoformat(raw_date)
        if start <= current <= end:
            closes.append(
                DailyClose(
                    date=raw_date,
                    close=float(values["4. close"]),
                    source=source_name,
                )
            )
    return sorted(closes, key=lambda item: item.date)


def _extract_stooq_closes(text: str, source_name: str = "Stooq") -> list[DailyClose]:
    stripped = text.lstrip()
    if stripped.startswith("<"):
        raise PriceFetchError("Stooq returned HTML challenge instead of CSV")
    rows = csv.DictReader(io.StringIO(text))
    closes = []
    for row in rows:
        close = row.get("Close")
        raw_date = row.get("Date")
        if not close or not raw_date or close == "N/D":
            continue
        closes.append(DailyClose(date=raw_date, close=float(close), source=source_name))
    return closes


def _date_to_utc_timestamp(raw_date: str) -> int:
    parsed = datetime.combine(datetime.fromisoformat(raw_date).date(), time.min, tzinfo=timezone.utc)
    return int(parsed.timestamp())
