#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings
from src.fetchers.congress import (
    HOUSE_DISCLOSURE_URL,
    SENATE_DISCLOSURE_URL,
    HouseDisclosureClient,
    HousePtrTransaction,
    SenateDisclosureClient,
    filter_periodic_transaction_reports,
)
from src.fetchers.prices import PriceFetchError
from src.fetchers.prices import MarketDataClient
from src.models.events import CongressionalDisclosureEvent
from src.models.events import CongressTradeEvent
from src.posts.render import render_congressional_disclosure
from src.posts.render import render_congress_trade
from src.storage.db import FilingRecord, RadarDB


@dataclass(frozen=True)
class RenderedHousePost:
    event_key: str
    title: str
    body: str
    transaction: HousePtrTransaction | None = None


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch recent congressional disclosure indexes.")
    parser.add_argument("--year", type=int, default=datetime.now().year, help="Disclosure year.")
    parser.add_argument("--limit", type=int, default=10, help="Max House PTR filings to process.")
    parser.add_argument("--all-members", action="store_true", help="Do not filter by tracked member last names.")
    parser.add_argument("--house-only", action="store_true", help="Only check House disclosures.")
    parser.add_argument("--senate-only", action="store_true", help="Only check Senate disclosure access.")
    parser.add_argument("--render", action="store_true", help="Render Telegram-style candidate posts.")
    parser.add_argument("--db", action="store_true", help="Record filings and generated posts in SQLite.")
    parser.add_argument("--skip-seen", action="store_true", help="Skip filings already recorded in SQLite.")
    args = parser.parse_args()

    settings = Settings.load()
    db = RadarDB(settings.database_path) if args.db or args.skip_seen else None
    if db:
        db.init_schema()

    try:
        if not args.senate_only:
            _handle_house(args, settings, db)
        if not args.house_only:
            _handle_senate(settings)
    finally:
        if db:
            db.close()


def _handle_house(args, settings: Settings, db: RadarDB | None) -> None:
    client = HouseDisclosureClient(user_agent=settings.sec_user_agent)
    price_client = MarketDataClient(
        user_agent=settings.sec_user_agent,
        alpha_vantage_api_key=settings.alpha_vantage_api_key,
    )
    filings = client.fetch_filings(args.year)
    tracked_last_names = set() if args.all_members else _tracked_house_last_names()
    matches = filter_periodic_transaction_reports(filings, tracked_last_names, limit=args.limit)
    if not matches:
        print(f"House {args.year}: no matching PTR filings")
        return

    for filing in matches:
        if db and args.skip_seen and db.has_filing(filing.source, filing.document_id):
            print(f"skip seen House PTR: {filing.member_name} | {filing.document_id}")
            continue

        rendered_posts: list[RenderedHousePost] = []
        if args.render:
            rendered_posts = _render_house_posts(client, price_client, filing)
            for post in rendered_posts:
                print(post.body)
                print("\n---\n")
        else:
            _print_house_summary(client, price_client, filing)

        if db:
            db.upsert_filing(
                FilingRecord(
                    source=filing.source,
                    cik=filing.chamber,
                    accession_number=filing.document_id,
                    form_type=filing.filing_type,
                    entity_name=filing.member_name,
                    filing_date=filing.filing_date,
                    report_date=filing.year,
                    source_url=filing.source_url,
                )
            )
            for post in rendered_posts:
                db.upsert_generated_post(
                    event_key=post.event_key,
                    post_type="congress_trade",
                    title=post.title,
                    body=post.body,
                    source=filing.source,
                    source_url=filing.source_url,
                )
                if post.transaction:
                    transaction = post.transaction
                    db.record_trade(
                        event_key=post.event_key,
                        source=filing.source,
                        ticker=transaction.ticker,
                        company_name=transaction.asset_name,
                        actor_name=transaction.member_name,
                        action=transaction.action_text,
                        transaction_date=transaction.transaction_date,
                        filing_date=filing.filing_date,
                        value_usd=transaction.estimated_value_usd,
                        source_url=transaction.source_url,
                    )


def _handle_senate(settings: Settings) -> None:
    client = SenateDisclosureClient(user_agent=settings.sec_user_agent)
    try:
        resolved_url = client.check_access()
    except Exception as exc:
        print(f"Senate disclosure access check failed: {exc}")
        return
    print(f"Senate disclosure official search available: {resolved_url or SENATE_DISCLOSURE_URL}")


def _render_house_posts(
    client: HouseDisclosureClient,
    price_client: MarketDataClient,
    filing,
) -> list[RenderedHousePost]:
    try:
        transactions = client.fetch_ptr_transactions(filing)
    except Exception as exc:
        print(f"House PTR detail parse failed: {filing.document_id} | {exc}")
        transactions = []

    if not transactions:
        event = CongressionalDisclosureEvent(
            chamber=filing.chamber,
            member_name=filing.member_name,
            filing_type=filing.filing_type,
            state_district=filing.state_district,
            filing_year=filing.year,
            filed_date=filing.filing_date,
            document_id=filing.document_id,
            source_name="U.S. House Clerk Financial Disclosure",
            source_url=filing.source_url,
        )
        return [
            RenderedHousePost(
                event_key=filing.event_key,
                title=f"{filing.member_name} {filing.filing_type}",
                body=render_congressional_disclosure(event),
            )
        ]

    posts = []
    for index, transaction in enumerate(transactions, start=1):
        event = CongressTradeEvent(
            member_name=transaction.member_name,
            owner=transaction.owner,
            ticker=transaction.ticker,
            company_name=transaction.asset_name,
            buy_or_sell=transaction.action_text,
            asset_type=transaction.asset_type,
            amount_range=transaction.amount_range,
            transaction_date=transaction.transaction_date,
            disclosure_date=filing.filing_date,
            delay_days=_delay_days(transaction.transaction_date, filing.filing_date),
            price_performance=_price_performance(price_client, transaction),
            plain_language_summary=_congress_plain_summary(transaction),
            description=transaction.description,
            option_contract=transaction.option_contract,
            option_quantity=str(transaction.option_quantity) if transaction.option_quantity else "",
            option_type=transaction.option_type,
            option_strike=transaction.option_strike,
            option_expiration=transaction.option_expiration,
            source_name="U.S. House Clerk Financial Disclosure",
            source_url=transaction.source_url,
        )
        event_key = _house_trade_event_key(filing, index, transaction)
        posts.append(
            RenderedHousePost(
                event_key=event_key,
                title=f"{transaction.member_name} {transaction.ticker} {transaction.action_text}",
                body=render_congress_trade(event),
                transaction=transaction,
            )
        )
    return posts


def _print_house_summary(client: HouseDisclosureClient, price_client: MarketDataClient, filing) -> None:
    try:
        transactions = client.fetch_ptr_transactions(filing)
    except Exception as exc:
        print(f"House PTR detail parse failed: {filing.document_id} | {exc}")
        transactions = []

    if not transactions:
        print(
            " | ".join(
                [
                    filing.chamber,
                    filing.member_name,
                    filing.filing_type,
                    filing.state_district,
                    filing.filing_date,
                    filing.document_id,
                    filing.source_url,
                ]
            )
        )
        return

    for transaction in transactions:
        print(
            " | ".join(
                [
                    filing.chamber,
                    transaction.member_name,
                    transaction.owner,
                    transaction.ticker,
                    transaction.asset_type,
                    transaction.action_text,
                    transaction.amount_range,
                    transaction.transaction_date,
                    _price_performance(price_client, transaction),
                    transaction.option_contract or transaction.description,
                    transaction.source_url,
                ]
            )
        )


def _house_trade_event_key(filing, index: int, transaction) -> str:
    parts = [
        filing.event_key,
        str(index),
        transaction.ticker,
        transaction.transaction_code,
        transaction.transaction_date,
        transaction.amount_range,
    ]
    return ":".join(part.replace(":", "_") for part in parts)


def _price_performance(price_client: MarketDataClient, transaction: HousePtrTransaction) -> str:
    try:
        return price_client.price_performance_since(transaction.ticker, transaction.transaction_date).summary
    except (PriceFetchError, OSError, ValueError) as exc:
        return f"待补充（行情获取失败：{exc}）"


def _congress_plain_summary(transaction) -> str:
    if transaction.asset_type == "期权":
        return (
            f"这是一笔国会议员披露的 {transaction.ticker} 期权{transaction.action_text}，"
            "金额为区间披露，需结合原始 PDF 和披露延迟谨慎解读。"
        )
    return (
        f"这是一笔国会议员披露的 {transaction.ticker} {transaction.action_text}，"
        "金额为区间披露，不应直接等同于实时交易信号。"
    )


def _delay_days(transaction_date: str, filing_date: str) -> str:
    try:
        start = datetime.fromisoformat(transaction_date).date()
        end = datetime.fromisoformat(filing_date).date()
    except ValueError:
        return "未知"
    return str((end - start).days)


def _tracked_house_last_names() -> set[str]:
    path = PROJECT_ROOT / "config" / "tracked_congress_members.json"
    members = json.loads(path.read_text(encoding="utf-8"))
    return {
        item.get("last_name", "")
        for item in members
        if item.get("chamber") in {"house", "both"}
    }


if __name__ == "__main__":
    from src.observability.logging import run_with_logging

    run_with_logging("congress_recent", main)
