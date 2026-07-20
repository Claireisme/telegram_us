#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import sleep

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings
from src.fetchers.options import OptionsFetchError
from src.fetchers.options import OptionUnderlying
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


OPTIONS_QUEUE_KEY = "options_flow_queue"
OPTIONS_QUEUE_DEFAULT_BUDGET = 4


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
    parser.add_argument(
        "--queue",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Process watchlist scan as a persisted rate-limited queue in free mode.",
    )
    parser.add_argument(
        "--request-budget",
        type=int,
        default=OPTIONS_QUEUE_DEFAULT_BUDGET,
        help="Maximum Polygon requests to consume in one queued free-mode run.",
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

        if db and args.mode == "free" and args.scan == "watchlist" and args.queue:
            _run_queued_free_scan(args, db, started_at, polygon, price_client)
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


def _run_queued_free_scan(
    args,
    db: RadarDB,
    started_at: str,
    polygon: PolygonOptionsClient,
    price_client: MarketDataClient,
) -> None:
    queue = _load_queue(db)
    if not queue:
        queue = _build_discovery_tasks()
    request_budget = max(1, args.request_budget)
    requests_used = 0
    fetched_count = 0
    generated_count = 0
    generated_titles = []
    rate_limited = False

    while queue and requests_used < request_budget:
        task = queue.pop(0)
        action = task.get("action")
        try:
            if action == "discover":
                requests_used += 1
                queue.extend(_discover_contract_tasks(task, args, polygon, price_client))
            elif action == "check":
                requests_used += 1
                summary, tracked = _check_contract_task(task, polygon)
                fetched_count += 1
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
                if summary.premium >= args.min_premium and generated_count < args.top:
                    body = _render_summary(summary, tracked, price_client)
                    title = f"{summary.underlying} {summary.side} 期权异动"
                    db.upsert_generated_post(
                        event_key=f"options_flow:{summary.option_symbol}:{datetime.now(timezone.utc).date().isoformat()}",
                        post_type="option_flow",
                        title=title,
                        body=body,
                        source="options_flow",
                        source_url="https://polygon.io/options",
                    )
                    generated_count += 1
                    generated_titles.append(title)
                    if args.render:
                        print(body)
                        print("\n---\n")
        except OptionsFetchError as exc:
            print(f"{_task_label(task)}: {exc}")
            if _is_rate_limited(exc):
                queue.insert(0, task)
                rate_limited = True
                break

    _save_queue(db, queue)
    if not queue:
        _save_queue(db, _build_discovery_tasks())
    summary = _queue_summary(queue, requests_used, fetched_count, generated_count, generated_titles, rate_limited)
    _record_run(
        db,
        started_at,
        fetched_count,
        generated_count,
        summary,
        status="rate_limited" if rate_limited else "success",
    )


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


def _load_queue(db: RadarDB) -> list[dict]:
    raw = db.get_setting(OPTIONS_QUEUE_KEY, "[]")
    try:
        queue = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(queue, list):
        return []
    return [item for item in queue if isinstance(item, dict)]


def _save_queue(db: RadarDB, queue: list[dict]) -> None:
    db.set_setting(OPTIONS_QUEUE_KEY, json.dumps(queue, ensure_ascii=False))


def _build_discovery_tasks() -> list[dict]:
    watchlist_path = PROJECT_ROOT / "config" / "options_watchlist.json"
    if not watchlist_path.exists():
        return []
    tasks = []
    for underlying in load_option_watchlist(watchlist_path):
        for contract_type in ["call", "put"]:
            tasks.append(
                {
                    "action": "discover",
                    "ticker": underlying.ticker,
                    "contract_type": contract_type,
                    "theme_tags": underlying.theme_tags,
                }
            )
    return tasks


def _discover_contract_tasks(
    task: dict,
    args,
    polygon: PolygonOptionsClient,
    price_client: MarketDataClient,
) -> list[dict]:
    ticker = str(task["ticker"]).upper()
    latest_price = _latest_price_value(price_client, ticker)
    if latest_price <= 0:
        print(f"{ticker}: unable to load underlying price; skipped")
        return []
    underlying = _underlying_from_task(task)
    today = datetime.now(timezone.utc).date()
    contracts = polygon.list_contracts(
        underlying,
        contract_type=str(task["contract_type"]),
        min_strike=latest_price * 0.75,
        max_strike=latest_price * 1.35,
        min_expiration=today.isoformat(),
        max_expiration=(today + timedelta(days=120)).isoformat(),
    )
    selected = _select_candidate_contracts(contracts, latest_price, args.candidates_per_side)
    print(f"{ticker} {task['contract_type']}: discovered {len(selected)} candidate contracts")
    return [{"action": "check", "tracked": _tracked_to_dict(item)} for item in selected]


def _check_contract_task(task: dict, polygon: PolygonOptionsClient):
    tracked = _tracked_from_dict(task["tracked"])
    return polygon.previous_day_bar(tracked), tracked


def _render_summary(summary, tracked: TrackedOption, price_client: MarketDataClient) -> str:
    return render_option_flow(
        OptionFlowEvent(
            ticker=summary.underlying,
            company_name=summary.underlying,
            theme_tags=tracked.theme_tags,
            direction_emoji="🟢" if summary.side == "Call" else "🔴",
            direction_text="看涨" if summary.side == "Call" else "看跌",
            option_type=summary.side,
            expiration_date=summary.expiration,
            strike_price=summary.strike,
            contract_side=tracked.side.upper(),
            premium=f"${summary.premium:,.0f}",
            premium_label=_premium_label(summary),
            volume=str(summary.total_volume),
            open_interest="暂未提供",
            level=_activity_level(summary.premium),
            underlying_price=_latest_underlying_price(price_client, summary.underlying),
            trigger_reason=_trigger_reason(summary),
            plain_language_summary=_plain_summary(summary),
            source_name=summary.provider,
            source_url="https://polygon.io/options",
        )
    )


def _underlying_from_task(task: dict) -> OptionUnderlying:
    return OptionUnderlying(
        ticker=str(task["ticker"]).upper(),
        theme_tags=list(task.get("theme_tags") or []),
    )


def _tracked_to_dict(tracked: TrackedOption) -> dict:
    return {
        "underlying": tracked.underlying,
        "option_symbol": tracked.option_symbol,
        "tradier_option_symbol": tracked.tradier_option_symbol,
        "expiration": tracked.expiration,
        "strike": tracked.strike,
        "side": tracked.side,
        "theme_tags": tracked.theme_tags,
    }


def _tracked_from_dict(item: dict) -> TrackedOption:
    return TrackedOption(
        underlying=str(item["underlying"]),
        option_symbol=str(item["option_symbol"]),
        tradier_option_symbol=str(item.get("tradier_option_symbol") or str(item["option_symbol"]).removeprefix("O:")),
        expiration=str(item["expiration"]),
        strike=str(item["strike"]),
        side=str(item["side"]),
        theme_tags=list(item.get("theme_tags") or []),
    )


def _task_label(task: dict) -> str:
    if task.get("action") == "check":
        return str((task.get("tracked") or {}).get("option_symbol") or "options check")
    return f"{task.get('ticker', 'options')} {task.get('contract_type', 'discover')}"


def _is_rate_limited(exc: OptionsFetchError) -> bool:
    return "HTTP 429" in str(exc) or "maximum requests per minute" in str(exc)


def _queue_summary(
    queue: list[dict],
    requests_used: int,
    fetched_count: int,
    generated_count: int,
    titles: list[str],
    rate_limited: bool,
) -> str:
    prefix = "Polygon 免费额度触顶，已暂停并保留队列。" if rate_limited else "期权队列扫描完成本轮批次。"
    detail = f"本次消耗 {requests_used} 次请求，检查 {fetched_count} 个合约，生成 {generated_count} 条候选，队列剩余 {len(queue)} 项。"
    if titles:
        return f"{prefix}{detail} {'；'.join(titles[:3])}"
    return f"{prefix}{detail}"


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


def _record_run(
    db: RadarDB,
    started_at: str,
    fetched_count: int,
    generated_count: int,
    summary: str,
    status: str = "success",
) -> None:
    db.record_fetch_run(
        source="options_flow",
        status=status,
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
