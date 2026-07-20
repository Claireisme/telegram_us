from __future__ import annotations

import io
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime
from xml.etree import ElementTree


HOUSE_DISCLOSURE_URL = "https://disclosures-clerk.house.gov/FinancialDisclosure/ViewReport"
HOUSE_ZIP_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
HOUSE_PTR_PDF_URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"
SENATE_DISCLOSURE_URL = "https://efdsearch.senate.gov/search/"


@dataclass(frozen=True)
class CongressionalFiling:
    source: str
    chamber: str
    prefix: str
    last_name: str
    first_name: str
    suffix: str
    filing_type: str
    state_district: str
    year: str
    filing_date: str
    document_id: str
    source_url: str

    @property
    def member_name(self) -> str:
        parts = [self.first_name, self.last_name]
        if self.suffix:
            parts.append(self.suffix)
        return " ".join(part for part in parts if part).strip()

    @property
    def event_key(self) -> str:
        return f"{self.source}:{self.chamber}:{self.year}:{self.document_id}"


class HouseDisclosureClient:
    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent

    def fetch_filings(self, year: int) -> list[CongressionalFiling]:
        payload = self._download(HOUSE_ZIP_URL.format(year=year))
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            xml_name = f"{year}FD.xml"
            xml_payload = archive.read(xml_name)
        return parse_house_financial_disclosure_xml(xml_payload)

    def _download(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()


class SenateDisclosureClient:
    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent

    def check_access(self) -> str:
        request = urllib.request.Request(SENATE_DISCLOSURE_URL, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.geturl()


def parse_house_financial_disclosure_xml(payload: bytes) -> list[CongressionalFiling]:
    root = ElementTree.fromstring(payload.decode("utf-8-sig").encode("utf-8"))
    filings = []
    for member in root.findall("Member"):
        year = _text(member, "Year")
        doc_id = _text(member, "DocID")
        filings.append(
            CongressionalFiling(
                source="house_financial_disclosure",
                chamber="House",
                prefix=_text(member, "Prefix"),
                last_name=_text(member, "Last"),
                first_name=_text(member, "First"),
                suffix=_text(member, "Suffix"),
                filing_type=_filing_type_label(_text(member, "FilingType")),
                state_district=_text(member, "StateDst"),
                year=year,
                filing_date=_normalize_house_date(_text(member, "FilingDate")),
                document_id=doc_id,
                source_url=HOUSE_PTR_PDF_URL.format(year=year, doc_id=doc_id),
            )
        )
    return filings


def filter_periodic_transaction_reports(
    filings: list[CongressionalFiling],
    last_names: set[str],
    limit: int,
) -> list[CongressionalFiling]:
    normalized_last_names = {name.lower() for name in last_names if name}
    ptr_filings = [filing for filing in filings if filing.filing_type == "Periodic Transaction Report"]
    if normalized_last_names:
        ptr_filings = [filing for filing in ptr_filings if filing.last_name.lower() in normalized_last_names]
    ptr_filings.sort(key=lambda filing: filing.filing_date or "", reverse=True)
    return ptr_filings[:limit]


def _text(element: ElementTree.Element, tag: str) -> str:
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _filing_type_label(code: str) -> str:
    return {
        "P": "Periodic Transaction Report",
        "A": "Annual Report",
        "C": "Candidate Report",
        "D": "Termination Report",
        "W": "Extension",
        "X": "Amendment",
    }.get(code, code or "Unknown")


def _normalize_house_date(raw: str) -> str:
    if not raw:
        return ""
    try:
        return datetime.strptime(raw, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return raw
