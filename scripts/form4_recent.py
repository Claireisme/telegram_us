#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings
from src.fetchers.sec import SecClient
from src.models.events import InsiderTradeEvent
from src.parsers.sec import (
    aggregate_form4_transactions,
    build_form4_plain_summary,
    build_form4_screen_reason,
    extract_recent_filings,
    find_form4_ownership_document,
    format_dollar_amount,
    format_share_count,
    parse_form4_transactions,
)
from src.posts.render import render_insider_trade
from src.storage.db import FilingRecord, RadarDB
from src.storage.entities import load_tracked_issuers


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch recent SEC Form 4 filings for tracked issuers.")
    parser.add_argument("--limit", type=int, default=3, help="Max Form 4 filings per issuer.")
    parser.add_argument("--min-value", type=float, default=100_000, help="Minimum transaction value in USD.")
    parser.add_argument("--include-sales", action="store_true", help="Include open-market sale transactions.")
    parser.add_argument("--render", action="store_true", help="Render Telegram-style posts.")
    parser.add_argument("--db", action="store_true", help="Record seen filings, trades, and generated posts in SQLite.")
    parser.add_argument("--skip-seen", action="store_true", help="Skip trades already recorded in SQLite.")
    parser.add_argument("--issuer", help="Filter by ticker/company substring.")
    args = parser.parse_args()

    settings = Settings.load()
    client = SecClient(user_agent=settings.sec_user_agent)
    db = RadarDB(settings.database_path) if args.db or args.skip_seen else None
    if db:
        db.init_schema()
    issuers = load_tracked_issuers()
    if args.issuer:
        needle = args.issuer.lower()
        issuers = [
            issuer for issuer in issuers
            if needle in issuer.get("ticker", "").lower()
            or needle in issuer.get("company_name", "").lower()
        ]

    try:
        for issuer in issuers:
            entity = {
                "cik": issuer["cik"],
                "display_name": issuer["company_name"],
                "investor_name": "",
                "forms": ["4", "4/A"],
            }
            submissions = client.get_company_submissions(str(issuer["cik"]))
            filings = extract_recent_filings(submissions, entity, limit=args.limit)
            if not filings:
                print(f"{issuer['ticker']}: no recent Form 4 filings")
                continue

            for filing in filings:
                index_json = client.get_filing_index(filing.cik, filing.accession_number)
                document_name = find_form4_ownership_document(index_json, filing.primary_document)
                if not document_name:
                    print(f"{issuer['ticker']} | {filing.filing_date} | {filing.accession_number} | no XML document")
                    continue
                xml_text = client.get_filing_document(filing.cik, filing.accession_number, document_name)
                transactions = parse_form4_transactions(xml_text, filed_date=filing.filing_date)
                filtered = [
                    transaction for transaction in transactions
                    if transaction.is_open_market_buy_or_sell
                    and transaction.value >= args.min_value
                    and (args.include_sales or transaction.transaction_code == "P")
                ]
                filtered = [
                    transaction for transaction in aggregate_form4_transactions(filtered)
                    if transaction.value >= args.min_value
                ]
                if db:
                    db.upsert_filing(
                        FilingRecord(
                            source="sec",
                            cik=filing.cik,
                            accession_number=filing.accession_number,
                            form_type=filing.form,
                            entity_name=filing.entity_name,
                            filing_date=filing.filing_date,
                            report_date=filing.report_date,
                            source_url=filing.source_url,
                        )
                    )
                if not filtered:
                    print(f"{issuer['ticker']} | {filing.filing_date} | {filing.accession_number} | no matching P/S transactions")
                    continue

                for transaction in filtered:
                    ticker = transaction.ticker or issuer["ticker"]
                    company_name = transaction.company_name or issuer["company_name"]
                    event_key = _trade_event_key(filing.accession_number, transaction)
                    if db and args.skip_seen and db.has_generated_post(event_key):
                        print(f"skip seen trade: {ticker} | {transaction.insider_name} | {transaction.transaction_date}")
                        continue

                    rendered_text = ""
                    if args.render:
                        event = InsiderTradeEvent(
                            ticker=ticker,
                            company_name=company_name,
                            insider_name=transaction.insider_name,
                            title=transaction.title,
                            buy_or_sell=transaction.action_text,
                            shares=format_share_count(transaction.shares),
                            value=format_dollar_amount(transaction.value),
                            average_price=format_dollar_amount(transaction.price),
                            transaction_date=transaction.transaction_date,
                            filed_date=transaction.filed_date,
                            screen_reason=build_form4_screen_reason(transaction),
                            plain_language_summary=build_form4_plain_summary(transaction),
                            source_name="SEC EDGAR Form 4",
                            source_url=filing.source_url,
                        )
                        rendered_text = render_insider_trade(event)
                        print(rendered_text)
                        print("\n---\n")
                    else:
                        print(
                            " | ".join(
                                [
                                    ticker,
                                    company_name,
                                    transaction.insider_name,
                                    transaction.title,
                                    transaction.action_text,
                                    format_share_count(transaction.shares),
                                    format_dollar_amount(transaction.value),
                                    transaction.transaction_date,
                                    transaction.filed_date,
                                    filing.source_url,
                                ]
                            )
                        )

                    if db:
                        db.record_trade(
                            event_key=event_key,
                            source="sec_form4",
                            ticker=ticker,
                            company_name=company_name,
                            actor_name=transaction.insider_name,
                            action=transaction.action_text,
                            transaction_date=transaction.transaction_date,
                            filing_date=transaction.filed_date,
                            value_usd=transaction.value,
                            source_url=filing.source_url,
                        )
                        if rendered_text:
                            db.upsert_generated_post(
                                event_key=event_key,
                                post_type="insider_trade",
                                title=f"{ticker} {transaction.action_text}",
                                body=rendered_text,
                                source="sec_form4",
                                source_url=filing.source_url,
                            )
    finally:
        if db:
            db.close()


def _trade_event_key(accession_number: str, transaction) -> str:
    parts = [
        "sec_form4",
        accession_number,
        transaction.ticker,
        transaction.insider_name,
        transaction.transaction_code,
        transaction.transaction_date,
    ]
    return ":".join(part.replace(":", "_") for part in parts)


if __name__ == "__main__":
    from src.observability.logging import run_with_logging

    run_with_logging("form4_recent", main)
