from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


SEC_DATA_BASE = "https://data.sec.gov"
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"


class SecFetchError(RuntimeError):
    """Raised when a SEC request fails."""


@dataclass(frozen=True)
class SecClient:
    user_agent: str
    min_interval_seconds: float = 0.12

    def __post_init__(self) -> None:
        if not self.user_agent or "@" not in self.user_agent:
            raise ValueError("SEC_USER_AGENT should include a contact email.")
        object.__setattr__(self, "_last_request_at", 0.0)

    def get_json(self, url: str) -> dict[str, Any]:
        raw = self._request(url)
        return json.loads(raw.decode("utf-8"))

    def get_text(self, url: str) -> str:
        return self._request(url).decode("utf-8", errors="replace")

    def get_company_submissions(self, cik: str) -> dict[str, Any]:
        padded_cik = cik.zfill(10)
        return self.get_json(f"{SEC_DATA_BASE}/submissions/CIK{padded_cik}.json")

    def get_filing_index(self, cik: str, accession_number: str) -> dict[str, Any]:
        accession_path = accession_number.replace("-", "")
        url = f"{SEC_ARCHIVES_BASE}/{int(cik)}/{accession_path}/index.json"
        return self.get_json(url)

    def get_filing_document(self, cik: str, accession_number: str, document_name: str) -> str:
        accession_path = accession_number.replace("-", "")
        url = f"{SEC_ARCHIVES_BASE}/{int(cik)}/{accession_path}/{document_name}"
        return self.get_text(url)

    def _request(self, url: str) -> bytes:
        self._respect_rate_limit()
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Host": urllib.parse.urlparse(url).netloc,
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise SecFetchError(f"SEC HTTP {exc.code} for {url}: {body[:500]}") from exc
        except urllib.error.URLError as exc:
            raise SecFetchError(f"SEC network error for {url}: {exc}") from exc

    def _respect_rate_limit(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_at
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)
        object.__setattr__(self, "_last_request_at", time.monotonic())
