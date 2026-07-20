#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings
from src.storage.db import GeneratedPostRecord, RadarDB
from src.telegram.sender import TelegramSendError, send_message


MAX_NEW_POSTS_PER_RUN = 100


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the MVP disclosure pipeline.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--sec-only", action="store_true", help="Only run SEC smart-money filings.")
    mode.add_argument("--form4-only", action="store_true", help="Only run Form 4 insider trades.")
    mode.add_argument("--congress-only", action="store_true", help="Only run congressional disclosures.")
    parser.add_argument("--dry-run", action="store_true", help="Preview output without writing to DB.")
    parser.add_argument("--sec-limit", type=int, default=2, help="SEC filings per tracked entity.")
    parser.add_argument("--form4-limit", type=int, default=3, help="Form 4 filings per tracked issuer.")
    parser.add_argument("--congress-limit", type=int, default=10, help="Congressional PTR filings per run.")
    parser.add_argument("--form4-min-value", type=float, default=100_000, help="Minimum Form 4 value in USD.")
    parser.add_argument("--include-sales", action="store_true", help="Include Form 4 open-market sales.")
    parser.add_argument("--auto-send", action="store_true", help="Automatically send newly generated candidates.")
    parser.add_argument("--send-interval-seconds", type=int, default=30, help="Seconds to wait between auto-sent posts.")
    parser.add_argument("--use-settings", action="store_true", help="Read send mode options from web admin settings.")
    args = parser.parse_args()
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    app_settings = _load_app_settings() if args.use_settings else {}
    send_mode = app_settings.get("send_mode", "auto" if args.auto_send else "manual")
    if args.use_settings:
        args.include_sales = app_settings.get("include_sales", "false") == "true"
        args.send_interval_seconds = _setting_int(
            app_settings.get("send_interval_seconds", str(args.send_interval_seconds)),
            default=args.send_interval_seconds,
            minimum=0,
        )
        args.auto_send = send_mode == "auto"

    if args.auto_send and args.dry_run:
        raise SystemExit("--auto-send cannot be used with --dry-run")

    commands = []
    if not args.form4_only and not args.congress_only:
        commands.append(_source_command("sec_smart_money", "sec", _sec_command(args)))
    if not args.sec_only and not args.congress_only:
        commands.append(_source_command("sec_form4", "sec_form4", _form4_command(args)))
    if not args.sec_only and not args.form4_only:
        commands.append(_source_command("congress", "house_financial_disclosure", _congress_command(args)))
    if not args.dry_run and not args.sec_only and not args.form4_only and not args.congress_only:
        commands.append(_source_command("options_flow", "options_flow", _options_command()))

    for source_name, db_source, command in commands:
        _run_tracked(source_name, db_source, command, dry_run=args.dry_run)

    if args.auto_send:
        _auto_send_new_candidates(started_at, args.send_interval_seconds)
    elif send_mode == "semi_auto":
        _approve_new_candidates(started_at)


def _load_app_settings() -> dict[str, str]:
    settings = Settings.load()
    db = RadarDB(settings.database_path)
    try:
        db.init_schema()
        return db.get_settings()
    finally:
        db.close()


def _sec_command(args) -> list[str]:
    command = [
        sys.executable,
        "-B",
        "scripts/sec_recent.py",
        "--limit",
        str(args.sec_limit),
        "--render",
        "--compare-13f",
    ]
    if not args.dry_run:
        command.extend(["--db", "--skip-seen"])
    return command


def _form4_command(args) -> list[str]:
    command = [
        sys.executable,
        "-B",
        "scripts/form4_recent.py",
        "--limit",
        str(args.form4_limit),
        "--min-value",
        str(args.form4_min_value),
        "--render",
    ]
    if args.include_sales:
        command.append("--include-sales")
    if not args.dry_run:
        command.extend(["--db", "--skip-seen"])
    return command


def _congress_command(args) -> list[str]:
    command = [
        sys.executable,
        "-B",
        "scripts/congress_recent.py",
        "--limit",
        str(args.congress_limit),
        "--render",
    ]
    if not args.dry_run:
        command.extend(["--db", "--skip-seen"])
    return command


def _options_command() -> list[str]:
    return [
        sys.executable,
        "-B",
        "scripts/options_recent.py",
        "--db",
    ]


def _source_command(source_name: str, db_source: str, command: list[str]) -> tuple[str, str, list[str]]:
    return (source_name, db_source, command)


def _run_tracked(source_name: str, db_source: str, command: list[str], dry_run: bool) -> None:
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"run: {' '.join(command)}")
    result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    completed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not dry_run and source_name != "options_flow":
        _record_fetch_run(source_name, db_source, started_at, completed_at, result)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _record_fetch_run(
    source_name: str,
    db_source: str,
    started_at: str,
    completed_at: str,
    result: subprocess.CompletedProcess[str],
) -> None:
    settings = Settings.load()
    db = RadarDB(settings.database_path)
    try:
        db.init_schema()
        generated_count = db.count_generated_posts_since(started_at, source=db_source)
        fetched_count = db.count_filings_since(started_at, source=db_source)
        if source_name == "sec_form4":
            generated_count = db.count_generated_posts_since(started_at, source="sec_form4")
            fetched_count = generated_count
        titles = db.list_generated_post_titles_since(started_at, source=db_source, limit=5)
        summary = _fetch_summary(generated_count, titles, result.stdout)
        status = "success" if result.returncode == 0 else "error"
        db.record_fetch_run(
            source=source_name,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            fetched_count=fetched_count,
            generated_count=generated_count,
            summary=summary,
            error="" if result.returncode == 0 else (result.stderr or result.stdout)[-500:],
        )
    finally:
        db.close()


def _fetch_summary(generated_count: int, titles: list[str], stdout: str) -> str:
    if titles:
        return "；".join(titles)
    if generated_count == 0:
        return "本次没有生成新的候选推送。"
    first_lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    return "；".join(first_lines[:3])[:500]


def _setting_int(raw: str, default: int, minimum: int) -> int:
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)


def _auto_send_new_candidates(started_at: str, send_interval_seconds: int) -> None:
    settings = Settings.load()
    db = RadarDB(settings.database_path)
    try:
        db.init_schema()
        posts = db.list_generated_posts_since(status="candidate", since=started_at, limit=MAX_NEW_POSTS_PER_RUN)
        if not posts:
            print("auto-send: no new candidates")
            return
        for index, post in enumerate(posts):
            if index > 0 and send_interval_seconds > 0:
                print(f"auto-send wait: {send_interval_seconds}s")
                time.sleep(send_interval_seconds)
            _send_candidate(db, settings, post)
    finally:
        db.close()


def _approve_new_candidates(started_at: str) -> None:
    settings = Settings.load()
    db = RadarDB(settings.database_path)
    try:
        db.init_schema()
        posts = db.list_generated_posts_since(status="candidate", since=started_at, limit=MAX_NEW_POSTS_PER_RUN)
        if not posts:
            print("semi-auto: no new candidates")
            return
        for post in posts:
            db.update_generated_post_status(post.id, "approved")
            print(f"semi-auto post {post.id}: candidate -> approved")
    finally:
        db.close()


def _send_candidate(db: RadarDB, settings: Settings, post: GeneratedPostRecord) -> None:
    print(f"auto-send post {post.id}: {post.title}")
    db.update_generated_post_status(post.id, "approved")
    try:
        result = send_message(
            bot_token=settings.telegram_bot_token,
            channel_id=settings.telegram_channel_id,
            text=post.body,
            dry_run=settings.dry_run,
        )
    except TelegramSendError as exc:
        db.update_generated_post_status(post.id, "candidate")
        raise SystemExit(str(exc)) from exc

    if settings.dry_run:
        db.update_generated_post_status(post.id, "candidate")
        print(f"auto-send dry-run: post {post.id} restored to candidate")
        return

    message = result.get("result") or {}
    message_id = "" if message.get("message_id") is None else str(message.get("message_id"))
    db.record_sent_post(
        generated_post_id=post.id,
        telegram_message_id=message_id,
        channel_id=settings.telegram_channel_id,
    )
    db.update_generated_post_status(post.id, "sent")
    print(f"post {post.id}: candidate -> sent")


if __name__ == "__main__":
    from src.observability.logging import run_with_logging

    run_with_logging("run_pipeline", main)
