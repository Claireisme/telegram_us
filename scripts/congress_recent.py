#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings
from src.fetchers.congress import (
    HOUSE_DISCLOSURE_URL,
    SENATE_DISCLOSURE_URL,
    HouseDisclosureClient,
    SenateDisclosureClient,
    filter_periodic_transaction_reports,
)
from src.models.events import CongressionalDisclosureEvent
from src.posts.render import render_congressional_disclosure
from src.storage.db import FilingRecord, RadarDB


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

        rendered_text = ""
        if args.render:
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
            rendered_text = render_congressional_disclosure(event)
            print(rendered_text)
            print("\n---\n")
        else:
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
            if rendered_text:
                db.upsert_generated_post(
                    event_key=filing.event_key,
                    post_type="congressional_disclosure",
                    title=f"{filing.member_name} {filing.filing_type}",
                    body=rendered_text,
                    source=filing.source,
                    source_url=filing.source_url,
                )


def _handle_senate(settings: Settings) -> None:
    client = SenateDisclosureClient(user_agent=settings.sec_user_agent)
    try:
        resolved_url = client.check_access()
    except Exception as exc:
        print(f"Senate disclosure access check failed: {exc}")
        return
    print(f"Senate disclosure official search available: {resolved_url or SENATE_DISCLOSURE_URL}")


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
