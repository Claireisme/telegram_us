#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import sleep

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings
from src.fetchers.options import OptionsFetchError
from src.fetchers.options import PolygonOptionsClient
from src.fetchers.options import TradierOptionsClient
from src.fetchers.options import TrackedOption
from src.fetchers.options import load_option_watchlist
from src.fetchers.options import load_tracked_options
from src.fetchers.prices import MarketDataClient
from src.fetchers.prices import PriceFetchError
from src.models.events import OptionFlowEvent
from src.posts.render import render_option_flow
from src.storage.db import RadarDB


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch recent options activity from configured providers.")
    parser.add_argument("--limit", type=int, default=100, help="Recent trades per tracked option contract.")
    parser.add_argument("--min-premium", type=float, default=500_000, help="Minimum notional premium in USD.")
    parser.add_argument(
        "--mode",
        choices=["free", "trades"],
        default="free",
        help="free uses previous-day aggregates; trades uses tick-level trades and may require a paid plan.",
    )
    parser.add_argument("--top", type=int, default=5, help="Maximum option flow posts to generate.")
    parser.add_argument(
        "--scan",
        choices=["watchlist", "tracked"],
        default="watchlist",
        help="watchlist discovers contracts by underlying; tracked only checks config/tracked_options.json.",
    )
    parser.add_argument(
        "--candidates-per-side",
        type=int,
        default=4,
        help="Candidate contracts to check per underlying and Call/Put side in watchlist scan.",
    )
    parser.add_argument(
        "--api-delay",
        type=float,
        default=12.5,
        help="Seconds to wait between Polygon calls in watchlist scan; keep near 12 for free plan limits.",
    )
    parser.add_argument("--render", action="store_true", help="Render Telegram-style option flow posts.")
    parser.add_argument("--db", action="store_true", help="Record fetch status and generated posts in SQLite.")
    args = parser.parse_args()

    settings = Settings.load()
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db = RadarDB(settings.database_path) if args.db else None
    if db:
        db.init_schema()

    try:
        polygon = PolygonOptionsClient(settings.polygon_api_key)
        tradier = TradierOptionsClient(settings.tradier_access_token, settings.tradier_base_url)
        price_client = MarketDataClient(settings.sec_user_agent, settings.alpha_vantage_api_key)
        generated_count = 0
        summaries = []

        if not settings.polygon_api_key and not settings.tradier_access_token:
            message = "options providers not configured: set POLYGON_API_KEY or TRADIER_ACCESS_TOKEN"
            print(message)
            if db:
                _record_run(db, started_at, 0, 0, message)
            return

        tracked_options = _tracked_options(args, polygon, price_client)
        for index, tracked in enumerate(tracked_options):
            if settings.tradier_access_token:
                _check_tradier_chain(tradier, tracked)
            if not settings.polygon_api_key:
                continue
            if args.scan == "watchlist" and args.api_delay > 0 and index > 0:
                sleep(args.api_delay)
            try:
                summary = (
                    polygon.recent_trades(tracked, limit=args.limit)
                    if args.mode == "trades"
                    else polygon.previous_day_bar(tracked)
                )
            except OptionsFetchError as exc:
                print(f"{tracked.option_symbol}: {exc}")
                continue
            summaries.append(summary)
            print(
                " | ".join(
                    [
                        summary.provider,
                        summary.underlying,
                        summary.option_symbol,
                        f"{summary.side} {summary.expiration} ${summary.strike}",
                        f"notional ${summary.premium:,.0f}",
                        f"volume {summary.total_volume}",
                        summary.data_mode,
                    ]
                )
            )

        candidates = sorted(
            [summary for summary in summaries if summary.premium >= args.min_premium],
            key=lambda summary: summary.premium,
            reverse=True,
        )[: args.top]

        theme_tags_by_symbol = {tracked.option_symbol: tracked.theme_tags for tracked in tracked_options}
        side_by_symbol = {tracked.option_symbol: tracked.side for tracked in tracked_options}
        price_by_underlying: dict[str, str] = {}
        for summary in candidates:
            price_by_underlying.setdefault(summary.underlying, _latest_underlying_price(price_client, summary.underlying))
            body = render_option_flow(
                OptionFlowEvent(
                    ticker=summary.underlying,
                    company_name=summary.underlying,
                    theme_tags=theme_tags_by_symbol.get(summary.option_symbol, []),
                    direction_emoji="🟢" if summary.side == "Call" else "🔴",
                    direction_text="看涨" if summary.side == "Call" else "看跌",
                    option_type=summary.side,
                    expiration_date=summary.expiration,
                    strike_price=summary.strike,
                    contract_side=side_by_symbol.get(summary.option_symbol, summary.side[:1].upper()),
                    premium=f"${summary.premium:,.0f}",
                    premium_label=_premium_label(summary),
                    volume=str(summary.total_volume),
                    open_interest="暂未提供",
                    level=_activity_level(summary.premium),
                    underlying_price=price_by_underlying[summary.underlying],
                    trigger_reason=_trigger_reason(summary),
                    plain_language_summary=_plain_summary(summary),
                    source_name=summary.provider,
                    source_url="https://polygon.io/options",
                )
            )
            if args.render:
                print(body)
                print("\n---\n")
            if db:
                db.upsert_generated_post(
                    event_key=f"options_flow:{summary.option_symbol}:{started_at}",
                    post_type="option_flow",
                    title=f"{summary.underlying} {summary.side} 期权异动",
                    body=body,
                    source="options_flow",
                    source_url="https://polygon.io/options",
                )
            generated_count += 1

        if db:
            _record_run(
                db,
                started_at,
                len(summaries),
                generated_count,
                _summary_text(summaries, generated_count),
            )
    finally:
        if db:
            db.close()


def _check_tradier_chain(client: TradierOptionsClient, tracked) -> None:
    try:
        item = client.option_chain(tracked)
    except OptionsFetchError as exc:
        print(f"{tracked.tradier_option_symbol}: {exc}")
        return
    bid = item.get("bid")
    ask = item.get("ask")
    volume = item.get("volume")
    print(f"Tradier chain ok: {tracked.tradier_option_symbol} bid={bid} ask={ask} volume={volume}")


def _tracked_options(args, polygon: PolygonOptionsClient, price_client: MarketDataClient) -> list[TrackedOption]:
    if args.mode != "free" or args.scan == "tracked":
        return load_tracked_options(PROJECT_ROOT / "config" / "tracked_options.json")
    watchlist_path = PROJECT_ROOT / "config" / "options_watchlist.json"
    if not watchlist_path.exists():
        return load_tracked_options(PROJECT_ROOT / "config" / "tracked_options.json")
    tracked: list[TrackedOption] = []
    for underlying in load_option_watchlist(watchlist_path):
        latest_price = _latest_price_value(price_client, underlying.ticker)
        if latest_price <= 0:
            print(f"{underlying.ticker}: unable to load underlying price; skipped watchlist scan")
            continue
        min_expiration = datetime.now(timezone.utc).date().isoformat()
        max_expiration = (datetime.now(timezone.utc).date() + timedelta(days=120)).isoformat()
        min_strike = latest_price * 0.75
        max_strike = latest_price * 1.35
        for contract_type in ["call", "put"]:
            try:
                contracts = polygon.list_contracts(
                    underlying,
                    contract_type=contract_type,
                    min_strike=min_strike,
                    max_strike=max_strike,
                    min_expiration=min_expiration,
                    max_expiration=max_expiration,
                )
            except OptionsFetchError as exc:
                print(f"{underlying.ticker} {contract_type}: {exc}")
                continue
            tracked.extend(_select_candidate_contracts(contracts, latest_price, args.candidates_per_side))
            if args.api_delay > 0:
                sleep(args.api_delay)
    return tracked


def _record_run(db: RadarDB, started_at: str, fetched_count: int, generated_count: int, summary: str) -> None:
    db.record_fetch_run(
        source="options_flow",
        status="success",
        started_at=started_at,
        completed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        fetched_count=fetched_count,
        generated_count=generated_count,
        summary=summary,
    )


def _summary_text(summaries, generated_count: int) -> str:
    if not summaries:
        return "本次没有抓到可用期权成交；如未配置 API key，请配置 POLYGON_API_KEY 或 TRADIER_ACCESS_TOKEN。"
    if generated_count == 0:
        return f"检查 {len(summaries)} 个期权合约，未达到推送阈值。"
    return f"检查 {len(summaries)} 个期权合约，生成 {generated_count} 条候选。"


def _select_candidate_contracts(
    contracts: list[TrackedOption],
    underlying_price: float,
    count: int,
) -> list[TrackedOption]:
    def score(contract: TrackedOption) -> tuple[float, str]:
        try:
            strike = float(contract.strike)
        except ValueError:
            strike = underlying_price
        return (abs(strike - underlying_price), contract.expiration)

    return sorted(contracts, key=score)[: max(1, count)]


def _trigger_reason(summary) -> str:
    if summary.data_mode == "trades":
        return (
            f"Polygon 最近 {summary.trade_count} 笔成交中，最新一笔名义金额约 "
            f"${summary.premium:,.0f}，合约成交量合计 {summary.total_volume}。"
        )
    return (
        f"Polygon 前一交易日聚合数据：收盘价 ${summary.price:.2f}，"
        f"成交量 {summary.total_volume}，估算名义成交额约 ${summary.premium:,.0f}。"
    )


def _premium_label(summary) -> str:
    if summary.data_mode == "previous_day_bar":
        return "估算名义成交额"
    return "成交金额"


def _latest_underlying_price(client: MarketDataClient, ticker: str) -> str:
    latest_price = _latest_price_value(client, ticker)
    if latest_price <= 0:
        return "暂未提供"
    return f"${latest_price:.2f}"


def _latest_price_value(client: MarketDataClient, ticker: str) -> float:
    start_date = (datetime.now(timezone.utc) - timedelta(days=14)).date().isoformat()
    try:
        closes = client.daily_closes(ticker, start_date)
    except (PriceFetchError, OSError, ValueError):
        return 0
    if not closes:
        return 0
    return closes[-1].close


def _activity_level(premium: float) -> str:
    if premium >= 2_000_000:
        return "高"
    if premium >= 500_000:
        return "中"
    return "低"


def _plain_summary(summary) -> str:
    if summary.data_mode == "trades":
        return "这是一条基于期权逐笔成交的异动观察，需结合成交方向、组合腿和标的走势谨慎解读。"
    return "这是一条基于免费计划可用的盘后聚合数据观察，不代表实时大单信号，适合先用于延迟异动筛选。"


if __name__ == "__main__":
    from src.observability.logging import run_with_logging

    run_with_logging("options_recent", main)
