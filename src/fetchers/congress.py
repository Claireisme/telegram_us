from __future__ import annotations

import io
import re
import subprocess
import tempfile
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


@dataclass(frozen=True)
class HousePtrTransaction:
    document_id: str
    chamber: str
    member_name: str
    owner: str
    asset_name: str
    ticker: str
    asset_type: str
    transaction_code: str
    action_text: str
    transaction_date: str
    notification_date: str
    amount_range: str
    description: str
    source_url: str


class HouseDisclosureClient:
    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent

    def fetch_filings(self, year: int) -> list[CongressionalFiling]:
        payload = self._download(HOUSE_ZIP_URL.format(year=year))
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            xml_name = f"{year}FD.xml"
            xml_payload = archive.read(xml_name)
        return parse_house_financial_disclosure_xml(xml_payload)

    def fetch_ptr_transactions(self, filing: CongressionalFiling) -> list[HousePtrTransaction]:
        payload = self._download(filing.source_url)
        text = extract_pdf_text(payload)
        return parse_house_ptr_text(filing, text)

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


def extract_pdf_text(payload: bytes) -> str:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(payload))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        pass

    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(io.BytesIO(payload)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except ImportError:
        pass

    with tempfile.NamedTemporaryFile(suffix=".pdf") as pdf_file:
        pdf_file.write(payload)
        pdf_file.flush()
        result = subprocess.run(
            ["pdftotext", "-layout", pdf_file.name, "-"],
            check=False,
            capture_output=True,
            text=True,
        )
    if result.returncode == 0:
        return result.stdout
    raise RuntimeError("PDF text extraction requires pypdf, pdfplumber, or pdftotext.")


def parse_house_ptr_text(filing: CongressionalFiling, text: str) -> list[HousePtrTransaction]:
    normalized = "\n".join(line.strip() for line in text.replace("\x00", "").splitlines() if line.strip())
    chunks = re.split(r"\n(?=[A-Z]{2}\s+)", normalized)
    transactions = []
    for chunk in chunks:
        transaction = _parse_house_ptr_transaction_chunk(filing, chunk)
        if transaction:
            transactions.append(transaction)
    return transactions


def _parse_house_ptr_transaction_chunk(
    filing: CongressionalFiling,
    chunk: str,
) -> HousePtrTransaction | None:
    ticker_match = re.search(r"\(([A-Z][A-Z0-9.\-]{0,9})\)\s*\[([A-Z]{2})\]", chunk)
    detail_match = re.search(
        r"\n([PSE])\s+(\d{2}/\d{2}/\d{4})\s*(\d{2}/\d{2}/\d{4})\s*(\$[\d,]+)\s*-\s*(?:\n)?(\$[\d,]+)",
        chunk,
    )
    if not ticker_match or not detail_match:
        return None

    first_line = chunk.splitlines()[0]
    owner, _, asset_prefix = first_line.partition(" ")
    asset_name = _clean_asset_name(
        " ".join(
            [
                asset_prefix,
                chunk.split(ticker_match.group(0), 1)[0].split("\n", 1)[-1],
            ]
        )
    )
    transaction_code = detail_match.group(1)
    description_match = re.search(r"\b(Purchased|Sold|Exchanged|Received|Disposed|Acquired)\b.+", chunk)
    return HousePtrTransaction(
        document_id=filing.document_id,
        chamber=filing.chamber,
        member_name=filing.member_name,
        owner=owner,
        asset_name=asset_name,
        ticker=ticker_match.group(1),
        asset_type=_asset_type_label(ticker_match.group(2)),
        transaction_code=transaction_code,
        action_text=_transaction_action_label(transaction_code),
        transaction_date=_normalize_house_date(detail_match.group(2)),
        notification_date=_normalize_house_date(detail_match.group(3)),
        amount_range=f"{detail_match.group(4)} - {detail_match.group(5)}",
        description=description_match.group(0).strip() if description_match else "",
        source_url=filing.source_url,
    )


def _clean_asset_name(raw: str) -> str:
    cleaned = re.sub(r"\s+", " ", raw).strip()
    cleaned = re.sub(r"\s*\([A-Z][A-Z0-9.\-]{0,9}\)\s*\[[A-Z]{2}\].*", "", cleaned)
    return cleaned


def _asset_type_label(code: str) -> str:
    return {
        "OP": "期权",
        "ST": "股票",
        "CS": "普通股",
        "CB": "公司债",
    }.get(code, code)


def _transaction_action_label(code: str) -> str:
    return {
        "P": "买入",
        "S": "卖出",
        "E": "交换",
    }.get(code, code)


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
