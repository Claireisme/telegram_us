#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings
from src.storage.db import RadarDB


def main() -> None:
    settings = Settings.load()
    db = RadarDB(settings.database_path)
    try:
        db.init_schema()
    finally:
        db.close()
    print(f"initialized database: {settings.database_path}")


if __name__ == "__main__":
    from src.observability.logging import run_with_logging

    run_with_logging("init_db", main)
