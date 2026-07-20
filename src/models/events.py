from __future__ import annotations

from dataclasses import dataclass, field


RiskNote = "⚠️ 非投资建议"


@dataclass(frozen=True)
class PositionChange:
    ticker: str
    company_name: str
    market_value: str
    change_text: str = ""
    portfolio_weight: str = ""


@dataclass(frozen=True)
class OptionFlowEvent:
    ticker: str
    company_name: str
    theme_tags: list[str]
    direction_emoji: str
    direction_text: str
    option_type: str
    expiration_date: str
    strike_price: str
    contract_side: str
    premium: str
    volume: str
    open_interest: str
    level: str
    underlying_price: str
    trigger_reason: str
    plain_language_summary: str
    source_name: str = ""
    source_url: str = ""
    risk_note: str = RiskNote


@dataclass(frozen=True)
class SmartMoneyFilingEvent:
    entity_name: str
    investor_name: str
    filing_type: str
    period: str
    filed_date: str
    delay_days: str
    new_positions: list[PositionChange] = field(default_factory=list)
    increased_positions: list[PositionChange] = field(default_factory=list)
    reduced_positions: list[PositionChange] = field(default_factory=list)
    key_change_summary: str = ""
    plain_language_summary: str = ""
    source_name: str = ""
    source_url: str = ""
    risk_note: str = RiskNote


@dataclass(frozen=True)
class CongressTradeEvent:
    member_name: str
    owner: str
    ticker: str
    company_name: str
    buy_or_sell: str
    asset_type: str
    amount_range: str
    transaction_date: str
    disclosure_date: str
    delay_days: str
    price_performance: str
    plain_language_summary: str
    source_name: str = ""
    source_url: str = ""
    risk_note: str = RiskNote


@dataclass(frozen=True)
class CongressionalDisclosureEvent:
    chamber: str
    member_name: str
    filing_type: str
    state_district: str
    filing_year: str
    filed_date: str
    document_id: str
    source_name: str = ""
    source_url: str = ""
    risk_note: str = RiskNote


@dataclass(frozen=True)
class InsiderTradeEvent:
    ticker: str
    company_name: str
    insider_name: str
    title: str
    buy_or_sell: str
    shares: str
    value: str
    average_price: str
    transaction_date: str
    filed_date: str
    screen_reason: str
    plain_language_summary: str
    source_name: str = ""
    source_url: str = ""
    risk_note: str = RiskNote


@dataclass(frozen=True)
class DailyRadarEvent:
    date: str
    options_top_5: list[str]
    smart_money_updates: list[str]
    daily_commentary: str
    watchlist: list[str]
    source_name: str = ""
    source_url: str = ""
    risk_note: str = RiskNote
