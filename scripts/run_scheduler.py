#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings
from src.storage.db import RadarDB


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the disclosure pipeline on a local interval.")
    parser.add_argument("--interval-minutes", type=int, help="Override backend interval setting.")
    parser.add_argument("--duration-days", type=int, help="Override backend duration setting.")
    parser.add_argument("--sec-limit", type=int, default=2, help="SEC filings per tracked entity each run.")
    parser.add_argument("--form4-limit", type=int, default=3, help="Form 4 filings per tracked issuer each run.")
    parser.add_argument("--max-runs", type=int, help="Optional safety/test limit for number of cycles.")
    args = parser.parse_args()

    app_settings = _load_app_settings()
    interval_minutes = _setting_int(
        args.interval_minutes,
        app_settings.get("scheduler_interval_minutes", "60"),
        default=60,
        minimum=5,
    )
    duration_days = _setting_int(
        args.duration_days,
        app_settings.get("scheduler_duration_days", "7"),
        default=7,
        minimum=1,
    )

    started_at = datetime.now(timezone.utc)
    end_at = started_at + timedelta(days=duration_days)
    run_count = 0
    _save_scheduler_state(
        scheduler_status="running",
        scheduler_started_at=started_at.isoformat(timespec="seconds"),
        scheduler_end_at=end_at.isoformat(timespec="seconds"),
        scheduler_last_run_at="",
        scheduler_next_run_at=started_at.isoformat(timespec="seconds"),
    )
    print(
        "scheduler start: "
        f"interval={interval_minutes}m duration={duration_days}d "
        f"until={end_at.isoformat(timespec='seconds')}"
    )

    while datetime.now(timezone.utc) < end_at:
        run_count += 1
        cycle_started = datetime.now(timezone.utc)
        _save_scheduler_state(
            scheduler_status="running",
            scheduler_last_run_at=cycle_started.isoformat(timespec="seconds"),
            scheduler_next_run_at="抓取中",
        )
        print(f"scheduler cycle {run_count} start: {cycle_started.isoformat(timespec='seconds')}")
        _run_pipeline(sec_limit=args.sec_limit, form4_limit=args.form4_limit)
        print(f"scheduler cycle {run_count} complete")

        if args.max_runs and run_count >= args.max_runs:
            _save_scheduler_state(scheduler_status="stopped", scheduler_next_run_at="")
            print(f"scheduler stop: reached max-runs={args.max_runs}")
            return

        next_run_at = cycle_started + timedelta(minutes=interval_minutes)
        sleep_seconds = max(0.0, (next_run_at - datetime.now(timezone.utc)).total_seconds())
        if datetime.now(timezone.utc) + timedelta(seconds=sleep_seconds) >= end_at:
            break
        _save_scheduler_state(
            scheduler_status="running",
            scheduler_next_run_at=next_run_at.isoformat(timespec="seconds"),
        )
        print(f"scheduler next run: {next_run_at.isoformat(timespec='seconds')}")
        time.sleep(sleep_seconds)

    _save_scheduler_state(scheduler_status="stopped", scheduler_next_run_at="")
    print("scheduler stop: duration reached")


def _load_app_settings() -> dict[str, str]:
    settings = Settings.load()
    db = RadarDB(settings.database_path)
    try:
        db.init_schema()
        return db.get_settings()
    finally:
        db.close()


def _save_scheduler_state(**values: str) -> None:
    settings = Settings.load()
    db = RadarDB(settings.database_path)
    try:
        db.init_schema()
        for key, value in values.items():
            db.set_setting(key, value)
    finally:
        db.close()


def _setting_int(raw_override: int | None, raw_setting: str, default: int, minimum: int) -> int:
    if raw_override is not None:
        return max(minimum, raw_override)
    try:
        return max(minimum, int(raw_setting))
    except ValueError:
        return default


def _run_pipeline(sec_limit: int, form4_limit: int) -> None:
    command = [
        sys.executable,
        "-B",
        "scripts/run_pipeline.py",
        "--use-settings",
        "--sec-limit",
        str(sec_limit),
        "--form4-limit",
        str(form4_limit),
    ]
    print(f"run: {' '.join(command)}")
    result = subprocess.run(command, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    from src.observability.logging import run_with_logging

    run_with_logging("run_scheduler", main)
