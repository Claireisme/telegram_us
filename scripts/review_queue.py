#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings
from src.storage.db import RadarDB


VALID_STATUSES = {"candidate", "approved", "rejected", "sent"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Review generated Telegram post candidates.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List generated posts by status.")
    list_parser.add_argument("--status", default="candidate", choices=sorted(VALID_STATUSES))
    list_parser.add_argument("--limit", type=int, default=20)

    show_parser = subparsers.add_parser("show", help="Show one generated post body.")
    show_parser.add_argument("post_id", type=int)

    approve_parser = subparsers.add_parser("approve", help="Mark a post as approved.")
    approve_parser.add_argument("post_id", type=int)

    reject_parser = subparsers.add_parser("reject", help="Mark a post as rejected.")
    reject_parser.add_argument("post_id", type=int)

    reset_parser = subparsers.add_parser("reset", help="Reset a post back to candidate.")
    reset_parser.add_argument("post_id", type=int)

    args = parser.parse_args()
    settings = Settings.load()
    db = RadarDB(settings.database_path)
    try:
        db.init_schema()
        if args.command == "list":
            _list_posts(db, args.status, args.limit)
        elif args.command == "show":
            _show_post(db, args.post_id)
        elif args.command == "approve":
            _set_status(db, args.post_id, "approved")
        elif args.command == "reject":
            _set_status(db, args.post_id, "rejected")
        elif args.command == "reset":
            _set_status(db, args.post_id, "candidate")
    finally:
        db.close()


def _list_posts(db: RadarDB, status: str, limit: int) -> None:
    posts = db.list_generated_posts(status=status, limit=limit)
    if not posts:
        print(f"no posts with status={status}")
        return
    for post in posts:
        print(
            " | ".join(
                [
                    str(post.id),
                    post.status,
                    post.post_type,
                    post.title,
                    post.created_at,
                ]
            )
        )


def _show_post(db: RadarDB, post_id: int) -> None:
    post = db.get_generated_post(post_id)
    if post is None:
        raise SystemExit(f"post not found: {post_id}")
    print(f"id: {post.id}")
    print(f"status: {post.status}")
    print(f"type: {post.post_type}")
    print(f"title: {post.title}")
    print(f"source: {post.source}")
    if post.source_url:
        print(f"source_url: {post.source_url}")
    print("\n--- body ---\n")
    print(post.body)


def _set_status(db: RadarDB, post_id: int, status: str) -> None:
    post = db.get_generated_post(post_id)
    if post is None:
        raise SystemExit(f"post not found: {post_id}")
    db.update_generated_post_status(post_id, status)
    print(f"post {post_id}: {post.status} -> {status}")


if __name__ == "__main__":
    from src.observability.logging import run_with_logging

    run_with_logging("review_queue", main)
