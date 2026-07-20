from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SECURITY_MASTER_PATH = PROJECT_ROOT / "config" / "security_master.json"


@dataclass(frozen=True)
class Security:
    cusip: str
    ticker: str
    company_name: str
    exchange: str = ""
    theme_tags: tuple[str, ...] = ()


class SecurityMaster:
    def __init__(self, securities: dict[str, Security]) -> None:
        self._securities = securities

    @classmethod
    def load(cls, path: Path = DEFAULT_SECURITY_MASTER_PATH) -> "SecurityMaster":
        raw = json.loads(path.read_text(encoding="utf-8"))
        securities = {
            _normalize_cusip(cusip): Security(
                cusip=_normalize_cusip(cusip),
                ticker=item["ticker"],
                company_name=item["company_name"],
                exchange=item.get("exchange", ""),
                theme_tags=tuple(item.get("theme_tags", [])),
            )
            for cusip, item in raw.items()
        }
        return cls(securities)

    def get_by_cusip(self, cusip: str) -> Security | None:
        return self._securities.get(_normalize_cusip(cusip))


def _normalize_cusip(cusip: str) -> str:
    return cusip.strip().upper()
