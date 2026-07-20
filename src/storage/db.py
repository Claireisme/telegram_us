from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS filings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    cik TEXT NOT NULL,
    accession_number TEXT NOT NULL,
    form_type TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    filing_date TEXT,
    report_date TEXT,
    source_url TEXT,
    status TEXT NOT NULL DEFAULT 'seen',
    first_seen_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source, accession_number)
);

CREATE TABLE IF NOT EXISTS generated_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_key TEXT NOT NULL UNIQUE,
    post_type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    source TEXT,
    source_url TEXT,
    status TEXT NOT NULL DEFAULT 'candidate',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sent_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_post_id INTEGER,
    telegram_message_id TEXT,
    channel_id TEXT,
    sent_at TEXT NOT NULL,
    FOREIGN KEY(generated_post_id) REFERENCES generated_posts(id)
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_key TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    ticker TEXT,
    company_name TEXT,
    actor_name TEXT,
    action TEXT,
    transaction_date TEXT,
    filing_date TEXT,
    value_usd REAL,
    source_url TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_filings_form_date ON filings(form_type, filing_date);
CREATE INDEX IF NOT EXISTS idx_generated_posts_status ON generated_posts(status, created_at);
CREATE INDEX IF NOT EXISTS idx_trades_ticker_date ON trades(ticker, transaction_date);
"""


@dataclass(frozen=True)
class FilingRecord:
    source: str
    cik: str
    accession_number: str
    form_type: str
    entity_name: str
    filing_date: str
    report_date: str
    source_url: str
    status: str = "seen"


@dataclass(frozen=True)
class GeneratedPostRecord:
    id: int
    event_key: str
    post_type: str
    title: str
    body: str
    source: str
    source_url: str
    status: str
    created_at: str
    updated_at: str


class RadarDB:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self.conn.close()

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self._ensure_default_settings()
        self.conn.commit()

    def _ensure_default_settings(self) -> None:
        defaults = {
            "send_mode": "manual",
            "include_sales": "false",
            "send_interval_seconds": "30",
            "scheduler_interval_minutes": "60",
            "scheduler_duration_days": "7",
        }
        now = _utc_now()
        for key, value in defaults.items():
            self.conn.execute(
                """
                INSERT OR IGNORE INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, value, now),
            )

    def has_filing(self, source: str, accession_number: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM filings WHERE source = ? AND accession_number = ?",
            (source, accession_number),
        ).fetchone()
        return row is not None

    def upsert_filing(self, record: FilingRecord) -> None:
        now = _utc_now()
        self.conn.execute(
            """
            INSERT INTO filings (
                source, cik, accession_number, form_type, entity_name,
                filing_date, report_date, source_url, status, first_seen_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, accession_number) DO UPDATE SET
                form_type = excluded.form_type,
                entity_name = excluded.entity_name,
                filing_date = excluded.filing_date,
                report_date = excluded.report_date,
                source_url = excluded.source_url,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                record.source,
                record.cik,
                record.accession_number,
                record.form_type,
                record.entity_name,
                record.filing_date,
                record.report_date,
                record.source_url,
                record.status,
                now,
                now,
            ),
        )
        self.conn.commit()

    def has_generated_post(self, event_key: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM generated_posts WHERE event_key = ?",
            (event_key,),
        ).fetchone()
        return row is not None

    def upsert_generated_post(
        self,
        event_key: str,
        post_type: str,
        title: str,
        body: str,
        source: str = "",
        source_url: str = "",
        status: str = "candidate",
    ) -> None:
        now = _utc_now()
        self.conn.execute(
            """
            INSERT INTO generated_posts (
                event_key, post_type, title, body, source, source_url,
                status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_key) DO UPDATE SET
                title = excluded.title,
                body = excluded.body,
                source = excluded.source,
                source_url = excluded.source_url,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (event_key, post_type, title, body, source, source_url, status, now, now),
        )
        self.conn.commit()

    def list_generated_posts(
        self,
        status: str = "candidate",
        limit: int = 20,
    ) -> list[GeneratedPostRecord]:
        rows = self.conn.execute(
            """
            SELECT id, event_key, post_type, title, body, source, source_url,
                   status, created_at, updated_at
            FROM generated_posts
            WHERE status = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (status, limit),
        ).fetchall()
        return [_post_from_row(row) for row in rows]

    def list_recent_posts(self, limit: int = 20) -> list[GeneratedPostRecord]:
        rows = self.conn.execute(
            """
            SELECT id, event_key, post_type, title, body, source, source_url,
                   status, created_at, updated_at
            FROM generated_posts
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_post_from_row(row) for row in rows]

    def list_generated_posts_since(
        self,
        status: str,
        since: str,
        limit: int = 20,
    ) -> list[GeneratedPostRecord]:
        rows = self.conn.execute(
            """
            SELECT id, event_key, post_type, title, body, source, source_url,
                   status, created_at, updated_at
            FROM generated_posts
            WHERE status = ?
              AND created_at >= ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (status, since, limit),
        ).fetchall()
        return [_post_from_row(row) for row in rows]

    def get_generated_post(self, post_id: int) -> GeneratedPostRecord | None:
        row = self.conn.execute(
            """
            SELECT id, event_key, post_type, title, body, source, source_url,
                   status, created_at, updated_at
            FROM generated_posts
            WHERE id = ?
            """,
            (post_id,),
        ).fetchone()
        return _post_from_row(row) if row else None

    def update_generated_post_status(self, post_id: int, status: str) -> None:
        now = _utc_now()
        self.conn.execute(
            "UPDATE generated_posts SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, post_id),
        )
        self.conn.commit()

    def record_sent_post(
        self,
        generated_post_id: int,
        telegram_message_id: str,
        channel_id: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO sent_posts (
                generated_post_id, telegram_message_id, channel_id, sent_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (generated_post_id, telegram_message_id, channel_id, _utc_now()),
        )
        self.conn.commit()

    def record_trade(
        self,
        event_key: str,
        source: str,
        ticker: str,
        company_name: str,
        actor_name: str,
        action: str,
        transaction_date: str,
        filing_date: str,
        value_usd: float,
        source_url: str,
    ) -> None:
        now = _utc_now()
        self.conn.execute(
            """
            INSERT OR IGNORE INTO trades (
                event_key, source, ticker, company_name, actor_name,
                action, transaction_date, filing_date, value_usd, source_url, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_key,
                source,
                ticker,
                company_name,
                actor_name,
                action,
                transaction_date,
                filing_date,
                value_usd,
                source_url,
                now,
            ),
        )
        self.conn.commit()

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (key,),
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value, _utc_now()),
        )
        self.conn.commit()

    def get_settings(self) -> dict[str, str]:
        rows = self.conn.execute("SELECT key, value FROM app_settings").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def count_posts_by_status(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS count FROM generated_posts GROUP BY status"
        ).fetchall()
        return {row["status"]: row["count"] for row in rows}

    def count_posts_since_days(self, days: int) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM generated_posts
            WHERE julianday(created_at) >= julianday('now', ?)
            """,
            (f"-{days} days",),
        ).fetchone()
        return int(row["count"])

    def count_sent_since_days(self, days: int) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM sent_posts
            WHERE julianday(sent_at) >= julianday('now', ?)
            """,
            (f"-{days} days",),
        ).fetchone()
        return int(row["count"])

    def daily_post_counts(self, days: int = 14) -> list[tuple[str, int, int]]:
        rows = self.conn.execute(
            """
            SELECT date(created_at) AS day,
                   COUNT(*) AS generated_count,
                   SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) AS sent_count
            FROM generated_posts
            WHERE julianday(created_at) >= julianday('now', ?)
            GROUP BY date(created_at)
            ORDER BY day DESC
            """,
            (f"-{days} days",),
        ).fetchall()
        return [
            (row["day"], int(row["generated_count"]), int(row["sent_count"] or 0))
            for row in rows
        ]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _post_from_row(row: sqlite3.Row) -> GeneratedPostRecord:
    return GeneratedPostRecord(
        id=row["id"],
        event_key=row["event_key"],
        post_type=row["post_type"],
        title=row["title"],
        body=row["body"],
        source=row["source"] or "",
        source_url=row["source_url"] or "",
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
