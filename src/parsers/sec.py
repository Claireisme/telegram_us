from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
import xml.etree.ElementTree as ET


SMART_MONEY_FORMS = {"13F-HR", "13F-HR/A", "SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A"}
INSIDER_FORMS = {"3", "3/A", "4", "4/A", "5", "5/A"}


@dataclass(frozen=True)
class SecFilingSummary:
    cik: str
    entity_name: str
    investor_name: str
    form: str
    accession_number: str
    filing_date: str
    report_date: str
    primary_document: str
    description: str
    source_url: str

    @property
    def filing_family(self) -> str:
        if self.form in SMART_MONEY_FORMS:
            return "smart_money"
        if self.form in INSIDER_FORMS:
            return "insider"
        return "other"


@dataclass(frozen=True)
class ThirteenFHolding:
    issuer: str
    cusip: str
    value_thousands: int
    shares: int
    share_type: str
    put_call: str = ""

    @property
    def market_value(self) -> int:
        return self.value_thousands


@dataclass(frozen=True)
class Form4Transaction:
    ticker: str
    company_name: str
    insider_name: str
    title: str
    transaction_code: str
    acquired_disposed: str
    shares: float
    price: float
    transaction_date: str
    filed_date: str
    is_director: bool = False
    is_officer: bool = False
    is_ten_percent_owner: bool = False

    @property
    def value(self) -> float:
        return self.shares * self.price

    @property
    def is_open_market_buy_or_sell(self) -> bool:
        return self.transaction_code in {"P", "S"} and self.shares > 0

    @property
    def action_text(self) -> str:
        if self.transaction_code == "P":
            return "公开市场买入"
        if self.transaction_code == "S":
            return "公开市场卖出"
        if self.acquired_disposed == "A":
            return "取得"
        if self.acquired_disposed == "D":
            return "处置"
        return "交易"


def extract_recent_filings(
    submissions: dict[str, Any],
    entity: dict[str, Any],
    limit: int = 20,
) -> list[SecFilingSummary]:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accession_numbers = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    primary_documents = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])

    wanted_forms = set(entity.get("forms") or [])
    results: list[SecFilingSummary] = []
    for index, form in enumerate(forms):
        if wanted_forms and form not in wanted_forms:
            continue
        accession_number = accession_numbers[index]
        primary_document = primary_documents[index]
        cik = str(entity["cik"])
        accession_path = accession_number.replace("-", "")
        source_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/{primary_document}"
        results.append(
            SecFilingSummary(
                cik=cik,
                entity_name=entity.get("display_name") or entity.get("name") or submissions.get("name", ""),
                investor_name=entity.get("investor_name", ""),
                form=form,
                accession_number=accession_number,
                filing_date=_get(filing_dates, index),
                report_date=_get(report_dates, index),
                primary_document=primary_document,
                description=_get(descriptions, index),
                source_url=source_url,
            )
        )
        if len(results) >= limit:
            break
    return results


def estimate_delay_days(report_date: str, filing_date: str) -> str:
    try:
        report = date.fromisoformat(report_date)
        filed = date.fromisoformat(filing_date)
    except ValueError:
        return "未知"
    return str((filed - report).days)


def build_smart_money_summary(filing: SecFilingSummary) -> dict[str, str]:
    delay_days = estimate_delay_days(filing.report_date, filing.filing_date)
    period = filing.report_date or "未知报告期"
    if filing.form.startswith("13F"):
        summary = f"{filing.entity_name} 提交 {filing.form}，报告期为 {period}。"
        interpretation = "这类文件适合用来观察季度持仓方向，但披露天然滞后，后续需要解析信息表才能看到具体增减仓。"
    else:
        summary = f"{filing.entity_name} 提交 {filing.form}，可能涉及重要持股比例变化。"
        interpretation = "13D/13G 更适合追踪大股东持股变化，通常比季度 13F 更接近事件型披露。"
    return {
        "period": period,
        "delay_days": delay_days,
        "key_change_summary": summary,
        "plain_language_summary": interpretation,
    }


def find_13f_information_table_document(index_json: dict[str, Any]) -> str:
    items = index_json.get("directory", {}).get("item", [])
    xml_candidates = [
        item.get("name", "")
        for item in items
        if item.get("name", "").lower().endswith(".xml")
        and item.get("name", "") != "primary_doc.xml"
    ]
    if not xml_candidates:
        return ""
    return xml_candidates[0]


def find_form4_ownership_document(index_json: dict[str, Any], primary_document: str = "") -> str:
    primary_name = primary_document.rsplit("/", 1)[-1]
    items = index_json.get("directory", {}).get("item", [])
    xml_names = [
        item.get("name", "")
        for item in items
        if item.get("name", "").lower().endswith(".xml")
    ]
    if primary_name in xml_names:
        return primary_name
    for name in xml_names:
        lower_name = name.lower()
        if "form4" in lower_name or "ownership" in lower_name:
            return name
    return xml_names[0] if xml_names else ""


def parse_13f_information_table(xml_text: str) -> list[ThirteenFHolding]:
    root = ET.fromstring(xml_text.encode("utf-8"))
    holdings: list[ThirteenFHolding] = []
    for info_table in _find_all_by_local_name(root, "infoTable"):
        issuer = _text_by_local_name(info_table, "nameOfIssuer")
        cusip = _text_by_local_name(info_table, "cusip")
        value = _int_text(_text_by_local_name(info_table, "value"))
        shares = _int_text(_text_by_local_name(info_table, "sshPrnamt"))
        share_type = _text_by_local_name(info_table, "sshPrnamtType")
        put_call = _text_by_local_name(info_table, "putCall")
        if issuer and cusip:
            holdings.append(
                ThirteenFHolding(
                    issuer=issuer,
                    cusip=cusip,
                    value_thousands=value,
                    shares=shares,
                    share_type=share_type,
                    put_call=put_call,
                )
            )
    return holdings


def parse_form4_transactions(xml_text: str, filed_date: str = "") -> list[Form4Transaction]:
    root = ET.fromstring(xml_text.encode("utf-8"))
    issuer = _first_by_local_name(root, "issuer")
    ticker = _text_by_local_name(issuer, "issuerTradingSymbol") if issuer is not None else ""
    company_name = _text_by_local_name(issuer, "issuerName") if issuer is not None else ""

    owner = _first_by_local_name(root, "reportingOwner")
    insider_name = _text_by_local_name(owner, "rptOwnerName") if owner is not None else ""
    relationship = _first_by_local_name(owner, "reportingOwnerRelationship") if owner is not None else None
    title = _text_by_local_name(relationship, "officerTitle") if relationship is not None else ""
    is_director = _bool_text(_text_by_local_name(relationship, "isDirector")) if relationship is not None else False
    is_officer = _bool_text(_text_by_local_name(relationship, "isOfficer")) if relationship is not None else False
    is_ten_percent_owner = (
        _bool_text(_text_by_local_name(relationship, "isTenPercentOwner"))
        if relationship is not None
        else False
    )
    if not title:
        title = _relationship_title(is_director, is_officer, is_ten_percent_owner)

    transactions: list[Form4Transaction] = []
    for transaction in _find_all_by_local_name(root, "nonDerivativeTransaction"):
        transaction_code = _text_by_path(transaction, ["transactionCoding", "transactionCode"])
        acquired_disposed = _text_by_path(
            transaction,
            ["transactionAmounts", "transactionAcquiredDisposedCode", "value"],
        )
        shares = _float_text(_text_by_path(transaction, ["transactionAmounts", "transactionShares", "value"]))
        price = _float_text(_text_by_path(transaction, ["transactionAmounts", "transactionPricePerShare", "value"]))
        transaction_date = _text_by_path(transaction, ["transactionDate", "value"])
        if not transaction_code:
            continue
        transactions.append(
            Form4Transaction(
                ticker=ticker,
                company_name=company_name,
                insider_name=insider_name,
                title=title,
                transaction_code=transaction_code,
                acquired_disposed=acquired_disposed,
                shares=shares,
                price=price,
                transaction_date=transaction_date,
                filed_date=filed_date,
                is_director=is_director,
                is_officer=is_officer,
                is_ten_percent_owner=is_ten_percent_owner,
            )
        )
    return transactions


def aggregate_form4_transactions(transactions: list[Form4Transaction]) -> list[Form4Transaction]:
    grouped: dict[tuple[str, str, str, str, str], list[Form4Transaction]] = {}
    for transaction in transactions:
        key = (
            transaction.ticker,
            transaction.insider_name,
            transaction.transaction_code,
            transaction.transaction_date,
            transaction.filed_date,
        )
        grouped.setdefault(key, []).append(transaction)

    aggregated: list[Form4Transaction] = []
    for items in grouped.values():
        first = items[0]
        total_shares = sum(item.shares for item in items)
        total_value = sum(item.value for item in items)
        average_price = total_value / total_shares if total_shares else 0.0
        aggregated.append(
            Form4Transaction(
                ticker=first.ticker,
                company_name=first.company_name,
                insider_name=first.insider_name,
                title=first.title,
                transaction_code=first.transaction_code,
                acquired_disposed=first.acquired_disposed,
                shares=total_shares,
                price=average_price,
                transaction_date=first.transaction_date,
                filed_date=first.filed_date,
                is_director=first.is_director,
                is_officer=first.is_officer,
                is_ten_percent_owner=first.is_ten_percent_owner,
            )
        )
    return sorted(aggregated, key=lambda item: item.value, reverse=True)


def compare_13f_holdings(
    current: list[ThirteenFHolding],
    previous: list[ThirteenFHolding],
    limit: int = 5,
) -> dict[str, list[ThirteenFHolding]]:
    current_by_cusip = {holding.cusip: holding for holding in current}
    previous_by_cusip = {holding.cusip: holding for holding in previous}

    new_positions = [
        holding for cusip, holding in current_by_cusip.items()
        if cusip not in previous_by_cusip
    ]
    increased_positions = [
        holding for cusip, holding in current_by_cusip.items()
        if cusip in previous_by_cusip
        and holding.shares > previous_by_cusip[cusip].shares
    ]
    reduced_positions = [
        holding for cusip, holding in current_by_cusip.items()
        if cusip in previous_by_cusip
        and holding.shares < previous_by_cusip[cusip].shares
    ]

    by_value = lambda holding: holding.value_thousands
    return {
        "new": sorted(new_positions, key=by_value, reverse=True)[:limit],
        "increased": sorted(increased_positions, key=by_value, reverse=True)[:limit],
        "reduced": sorted(reduced_positions, key=by_value, reverse=True)[:limit],
    }


def holding_change_text(current: ThirteenFHolding, previous: ThirteenFHolding | None) -> str:
    if previous is None or previous.shares == 0:
        return "新增"
    change = (current.shares - previous.shares) / previous.shares
    return f"{change:+.1%}"


def format_market_value(value: int) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    return f"${value:,.0f}"


def format_share_count(value: float) -> str:
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.2f}"


def format_dollar_amount(value: float) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    return f"${value:,.0f}"


def build_form4_screen_reason(transaction: Form4Transaction) -> str:
    role = transaction.title or "内部人"
    amount = format_dollar_amount(transaction.value)
    if transaction.transaction_code == "P":
        return f"{role} 公开市场买入，交易金额约 {amount}。"
    if transaction.transaction_code == "S":
        return f"{role} 公开市场卖出，交易金额约 {amount}。"
    return f"{role} 披露 Form 4 交易，交易代码为 {transaction.transaction_code}。"


def build_form4_plain_summary(transaction: Form4Transaction) -> str:
    if transaction.transaction_code == "P":
        return "公开市场买入通常比股权奖励更值得关注，但仍需结合公司基本面、交易金额和披露背景判断。"
    if transaction.transaction_code == "S":
        return "公开市场卖出可能来自减持、税务或资产配置需求，不应直接等同于看空。"
    return "Form 4 披露能帮助观察内部人行为，但不同交易代码含义差异很大，需要谨慎解读。"


def _get(items: list[Any], index: int) -> str:
    if index >= len(items):
        return ""
    value = items[index]
    return "" if value is None else str(value)


def _find_all_by_local_name(root: ET.Element, local_name: str) -> list[ET.Element]:
    return [element for element in root.iter() if _local_name(element.tag) == local_name]


def _first_by_local_name(root: ET.Element, local_name: str) -> ET.Element | None:
    for element in root.iter():
        if _local_name(element.tag) == local_name:
            return element
    return None


def _text_by_local_name(root: ET.Element, local_name: str) -> str:
    for element in root.iter():
        if _local_name(element.tag) == local_name:
            return (element.text or "").strip()
    return ""


def _text_by_path(root: ET.Element, local_names: list[str]) -> str:
    current = root
    for local_name in local_names:
        current = _direct_child_by_local_name(current, local_name)
        if current is None:
            return ""
    return (current.text or "").strip()


def _direct_child_by_local_name(root: ET.Element, local_name: str) -> ET.Element | None:
    for child in list(root):
        if _local_name(child.tag) == local_name:
            return child
    return None


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _int_text(value: str) -> int:
    try:
        return int(value.replace(",", "").strip())
    except ValueError:
        return 0


def _float_text(value: str) -> float:
    try:
        return float(value.replace(",", "").strip())
    except ValueError:
        return 0.0


def _bool_text(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


def _relationship_title(is_director: bool, is_officer: bool, is_ten_percent_owner: bool) -> str:
    roles = []
    if is_director:
        roles.append("Director")
    if is_officer:
        roles.append("Officer")
    if is_ten_percent_owner:
        roles.append("10% Owner")
    return " / ".join(roles) or "Insider"
