from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_channel_id: str
    sec_user_agent: str
    database_path: Path
    log_path: Path
    error_log_path: Path
    admin_host: str
    admin_port: int
    admin_password: str
    app_env: str = "development"
    dry_run: bool = True

    @classmethod
    def load(cls) -> "Settings":
        _load_dotenv(PROJECT_ROOT / ".env")
        dry_run_raw = os.getenv("DRY_RUN", "true").lower()
        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_channel_id=os.getenv("TELEGRAM_CHANNEL_ID", ""),
            sec_user_agent=os.getenv("SEC_USER_AGENT", "USStockRadar contact@example.com"),
            database_path=PROJECT_ROOT / os.getenv("DATABASE_PATH", "data/radar.db"),
            log_path=PROJECT_ROOT / os.getenv("LOG_PATH", "logs/radar.log"),
            error_log_path=PROJECT_ROOT / os.getenv("ERROR_LOG_PATH", "logs/errors.log"),
            admin_host=os.getenv("ADMIN_HOST", "127.0.0.1"),
            admin_port=int(os.getenv("ADMIN_PORT", "8787")),
            admin_password=os.getenv("ADMIN_PASSWORD", ""),
            app_env=os.getenv("APP_ENV", "development"),
            dry_run=dry_run_raw in {"1", "true", "yes", "on"},
        )
