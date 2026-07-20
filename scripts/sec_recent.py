#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings
from src.fetchers.sec import SecClient
from src.models.events import SmartMoneyFilingEvent
from src.models.events import PositionChange
from src.parsers.sec import (
    build_smart_money_summary,
    compare_13f_holdings,
    extract_recent_filings,
    find_13f_information_table_document,
    format_market_value,
    holding_change_text,
    parse_13f_information_table,
)
from src.posts.render import render_smart_money
from src.storage.db import FilingRecord, RadarDB
from src.storage.entities import load_tracked_entities
from src.storage.security_master import SecurityMaster


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch recent SEC filings for tracked entities.")
    parser.add_argument("--limit", type=int, default=5, help="Max matching filings per entity.")
    parser.add_argument("--render", action="store_true", help="Render Telegram-style sample posts.")
    parser.add_argument("--compare-13f", action="store_true", help="Compare latest 13F with previous 13F.")
    parser.add_argument("--db", action="store_true", help="Record seen filings and generated posts in SQLite.")
    parser.add_argument("--skip-seen", action="store_true", help="Skip filings already recorded in SQLite.")
    parser.add_argument("--entity", help="Filter by entity display/name substring.")
    args = parser.parse_args()

    settings = Settings.load()
    client = SecClient(user_agent=settings.sec_user_agent)
    db = RadarDB(settings.database_path) if args.db or args.skip_seen else None
    if db:
        db.init_schema()
    entities = load_tracked_entities()
    security_master = SecurityMaster.load()
    if args.entity:
        needle = args.entity.lower()
        entities = [
            entity for entity in entities
            if needle in entity.get("name", "").lower()
            or needle in entity.get("display_name", "").lower()
            or needle in entity.get("investor_name", "").lower()
        ]

    try:
        for entity in entities:
            submissions = client.get_company_submissions(str(entity["cik"]))
            request_limit = max(args.limit, 2) if args.compare_13f else args.limit
            filings = extract_recent_filings(submissions, entity, limit=request_limit)
            if not filings:
                print(f"{entity.get('display_name', entity['name'])}: no matching filings")
                continue

            for filing in filings[:args.limit]:
                if db and args.skip_seen and db.has_filing("sec", filing.accession_number):
                    print(f"skip seen filing: {filing.entity_name} | {filing.form} | {filing.accession_number}")
                    continue

                rendered_text = ""
                if args.render and filing.filing_family == "smart_money":
                    summary = build_smart_money_summary(filing)
                    new_positions: list[PositionChange] = []
                    increased_positions: list[PositionChange] = []
                    reduced_positions: list[PositionChange] = []
                    if args.compare_13f and filing.form.startswith("13F"):
                        comparable = [item for item in filings if item.form.startswith("13F")]
                        if len(comparable) >= 2 and filing == comparable[0]:
                            changes = _load_13f_changes(client, comparable[0], comparable[1], security_master)
                            new_positions = changes["new"]
                            increased_positions = changes["increased"]
                            reduced_positions = changes["reduced"]
                            summary["key_change_summary"] = (
                                "已解析 13F 信息表，并与上一期按 CUSIP 和持股数量进行对比。"
                            )
                            summary["plain_language_summary"] = (
                                "这次推送展示的是季度披露中的持仓变化，适合观察大资金方向，但 13F 仍有披露延迟。"
                            )

                    event = SmartMoneyFilingEvent(
                        entity_name=filing.entity_name,
                        investor_name=filing.investor_name,
                        filing_type=filing.form,
                        period=summary["period"],
                        filed_date=filing.filing_date,
                        delay_days=summary["delay_days"],
                        new_positions=new_positions,
                        increased_positions=increased_positions,
                        reduced_positions=reduced_positions,
                        key_change_summary=summary["key_change_summary"],
                        plain_language_summary=summary["plain_language_summary"],
                        source_name="SEC EDGAR",
                        source_url=filing.source_url,
                    )
                    rendered_text = render_smart_money(event)
                    print(rendered_text)
                    print("\n---\n")
                else:
                    print(
                        " | ".join(
                            [
                                filing.entity_name,
                                filing.investor_name,
                                filing.form,
                                filing.filing_date,
                                filing.report_date,
                                filing.accession_number,
                                filing.source_url,
                            ]
                        )
                    )

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
                    if rendered_text:
                        db.upsert_generated_post(
                            event_key=f"sec:{filing.accession_number}",
                            post_type="smart_money_filing",
                            title=f"{filing.entity_name} {filing.form}",
                            body=rendered_text,
                            source="sec",
                            source_url=filing.source_url,
                        )
    finally:
        if db:
            db.close()


def _load_13f_changes(
    client: SecClient,
    current,
    previous,
    security_master: SecurityMaster,
) -> dict[str, list[PositionChange]]:
    current_holdings = _load_13f_holdings(client, current)
    previous_holdings = _load_13f_holdings(client, previous)
    previous_by_cusip = {holding.cusip: holding for holding in previous_holdings}
    changes = compare_13f_holdings(current_holdings, previous_holdings, limit=5)
    return {
        "new": [_to_position_change(holding, None, security_master) for holding in changes["new"]],
        "increased": [
            _to_position_change(holding, previous_by_cusip.get(holding.cusip), security_master)
            for holding in changes["increased"]
        ],
        "reduced": [
            _to_position_change(holding, previous_by_cusip.get(holding.cusip), security_master)
            for holding in changes["reduced"]
        ],
    }


def _load_13f_holdings(client: SecClient, filing) -> list:
    index_json = client.get_filing_index(filing.cik, filing.accession_number)
    document_name = find_13f_information_table_document(index_json)
    if not document_name:
        return []
    xml_text = client.get_filing_document(filing.cik, filing.accession_number, document_name)
    return parse_13f_information_table(xml_text)


def _to_position_change(holding, previous, security_master: SecurityMaster) -> PositionChange:
    security = security_master.get_by_cusip(holding.cusip)
    ticker = security.ticker if security else f"CUSIP {holding.cusip}"
    company_name = security.company_name if security else holding.issuer
    return PositionChange(
        ticker=ticker,
        company_name=company_name,
        market_value=format_market_value(holding.market_value),
        change_text=holding_change_text(holding, previous),
    )


if __name__ == "__main__":
    from src.observability.logging import run_with_logging

    run_with_logging("sec_recent", main)
