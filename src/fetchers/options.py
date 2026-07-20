from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


POLYGON_BASE_URL = "https://api.polygon.io"


class OptionsFetchError(RuntimeError):
    """Raised when an options data provider cannot return usable data."""


@dataclass(frozen=True)
class TrackedOption:
    underlying: str
    option_symbol: str
    tradier_option_symbol: str
    expiration: str
    strike: str
    side: str
    theme_tags: list[str]

    @property
    def display_side(self) -> str:
        return "Call" if self.side.upper() == "C" else "Put"


@dataclass(frozen=True)
class OptionTradeSummary:
    provider: str
    underlying: str
    option_symbol: str
    expiration: str
    strike: str
    side: str
    price: float
    size: int
    premium: float
    trade_count: int
    total_volume: int
    data_mode: str = "trades"


class PolygonOptionsClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def recent_trades(self, tracked: TrackedOption, limit: int = 100) -> OptionTradeSummary:
        if not self.api_key:
            raise OptionsFetchError("POLYGON_API_KEY is not configured")
        query = urllib.parse.urlencode(
            {
                "limit": limit,
                "order": "desc",
                "sort": "timestamp",
                "apiKey": self.api_key,
            }
        )
        url = f"{POLYGON_BASE_URL}/v3/trades/{urllib.parse.quote(tracked.option_symbol)}?{query}"
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OptionsFetchError(f"Polygon HTTP {exc.code}: {_short_error_body(body)}") from exc
        except urllib.error.URLError as exc:
            raise OptionsFetchError(f"Polygon network error: {exc}") from exc
        results = payload.get("results") or []
        if not results:
            raise OptionsFetchError(f"Polygon returned no trades for {tracked.option_symbol}")
        return _summarize_polygon_trades(tracked, results)

    def previous_day_bar(self, tracked: TrackedOption) -> OptionTradeSummary:
        if not self.api_key:
            raise OptionsFetchError("POLYGON_API_KEY is not configured")
        query = urllib.parse.urlencode({"apiKey": self.api_key})
        url = f"{POLYGON_BASE_URL}/v2/aggs/ticker/{urllib.parse.quote(tracked.option_symbol)}/prev?{query}"
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OptionsFetchError(f"Polygon HTTP {exc.code}: {_short_error_body(body)}") from exc
        except urllib.error.URLError as exc:
            raise OptionsFetchError(f"Polygon network error: {exc}") from exc
        results = payload.get("results") or []
        if not results:
            raise OptionsFetchError(f"Polygon returned no previous day bar for {tracked.option_symbol}")
        return _summarize_polygon_bar(tracked, results[0])


class TradierOptionsClient:
    def __init__(self, access_token: str, base_url: str) -> None:
        self.access_token = access_token
        self.base_url = base_url.rstrip("/")

    def option_chain(self, tracked: TrackedOption) -> dict[str, Any]:
        if not self.access_token:
            raise OptionsFetchError("TRADIER_ACCESS_TOKEN is not configured")
        query = urllib.parse.urlencode(
            {
                "symbol": tracked.underlying,
                "expiration": tracked.expiration,
                "greeks": "true",
            }
        )
        request = urllib.request.Request(
            f"{self.base_url}/markets/options/chains?{query}",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OptionsFetchError(f"Tradier HTTP {exc.code}: {_short_error_body(body)}") from exc
        except urllib.error.URLError as exc:
            raise OptionsFetchError(f"Tradier network error: {exc}") from exc
        options = (payload.get("options") or {}).get("option") or []
        if isinstance(options, dict):
            options = [options]
        for item in options:
            if item.get("symbol") == tracked.tradier_option_symbol:
                return item
        raise OptionsFetchError(f"Tradier chain did not include {tracked.tradier_option_symbol}")


def load_tracked_options(path: Path) -> list[TrackedOption]:
    raw_items = json.loads(path.read_text(encoding="utf-8"))
    return [
        TrackedOption(
            underlying=item["underlying"],
            option_symbol=item["option_symbol"],
            tradier_option_symbol=item.get("tradier_option_symbol", item["option_symbol"].removeprefix("O:")),
            expiration=item["expiration"],
            strike=str(item["strike"]),
            side=item["side"],
            theme_tags=list(item.get("theme_tags") or []),
        )
        for item in raw_items
    ]


def _summarize_polygon_trades(tracked: TrackedOption, trades: list[dict[str, Any]]) -> OptionTradeSummary:
    total_volume = sum(int(item.get("size") or 0) for item in trades)
    latest = trades[0]
    latest_price = float(latest.get("price") or 0)
    latest_size = int(latest.get("size") or 0)
    return OptionTradeSummary(
        provider="Polygon Options",
        underlying=tracked.underlying,
        option_symbol=tracked.option_symbol,
        expiration=tracked.expiration,
        strike=tracked.strike,
        side=tracked.display_side,
        price=latest_price,
        size=latest_size,
        premium=latest_price * latest_size * 100,
        trade_count=len(trades),
        total_volume=total_volume,
        data_mode="trades",
    )


def _summarize_polygon_bar(tracked: TrackedOption, bar: dict[str, Any]) -> OptionTradeSummary:
    close_price = float(bar.get("c") or 0)
    volume = int(bar.get("v") or 0)
    transactions = int(bar.get("n") or 0)
    return OptionTradeSummary(
        provider="Polygon Options",
        underlying=tracked.underlying,
        option_symbol=tracked.option_symbol,
        expiration=tracked.expiration,
        strike=tracked.strike,
        side=tracked.display_side,
        price=close_price,
        size=volume,
        premium=close_price * volume * 100,
        trade_count=transactions,
        total_volume=volume,
        data_mode="previous_day_bar",
    )


def _short_error_body(body: str, limit: int = 300) -> str:
    compact = " ".join(body.split())
    return compact[:limit]
