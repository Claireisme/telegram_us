#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings
from src.storage.db import GeneratedPostRecord, RadarDB
from src.telegram.sender import TelegramSendError, send_message


def main() -> None:
    parser = argparse.ArgumentParser(description="Send approved posts to Telegram.")
    parser.add_argument("--limit", type=int, default=5, help="Max approved posts to send.")
    parser.add_argument("--post-id", type=int, help="Send one approved post by id.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without sending.")
    parser.add_argument("--mark-sent-on-dry-run", action="store_true", help="For testing only.")
    args = parser.parse_args()

    settings = Settings.load()
    dry_run = args.dry_run or settings.dry_run
    db = RadarDB(settings.database_path)
    try:
        db.init_schema()
        posts = _load_posts(db, args.post_id, args.limit)
        if not posts:
            print("no approved posts to send")
            return

        for post in posts:
            _send_one(db, settings, post, dry_run=dry_run, mark_sent_on_dry_run=args.mark_sent_on_dry_run)
    finally:
        db.close()


def _load_posts(db: RadarDB, post_id: int | None, limit: int) -> list[GeneratedPostRecord]:
    if post_id is None:
        return db.list_generated_posts(status="approved", limit=limit)
    post = db.get_generated_post(post_id)
    if post is None:
        raise SystemExit(f"post not found: {post_id}")
    if post.status != "approved":
        raise SystemExit(f"post {post_id} is {post.status}, not approved")
    return [post]


def _send_one(
    db: RadarDB,
    settings: Settings,
    post: GeneratedPostRecord,
    dry_run: bool,
    mark_sent_on_dry_run: bool,
) -> None:
    print(f"send post {post.id}: {post.title}")
    try:
        result = send_message(
            bot_token=settings.telegram_bot_token,
            channel_id=settings.telegram_channel_id,
            text=post.body,
            dry_run=dry_run,
        )
    except TelegramSendError as exc:
        raise SystemExit(str(exc)) from exc

    if dry_run and not mark_sent_on_dry_run:
        print(f"dry-run: post {post.id} not marked sent")
        return

    message_id = _extract_message_id(result)
    db.record_sent_post(
        generated_post_id=post.id,
        telegram_message_id=message_id,
        channel_id=settings.telegram_channel_id or "dry-run",
    )
    db.update_generated_post_status(post.id, "sent")
    print(f"post {post.id}: approved -> sent")


def _extract_message_id(result: dict) -> str:
    if result.get("dry_run"):
        return "dry-run"
    message = result.get("result") or {}
    message_id = message.get("message_id")
    return "" if message_id is None else str(message_id)


if __name__ == "__main__":
    from src.observability.logging import run_with_logging

    run_with_logging("send_approved", main)
