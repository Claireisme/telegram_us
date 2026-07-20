from __future__ import annotations

from src.models.events import (
    CongressTradeEvent,
    CongressionalDisclosureEvent,
    DailyRadarEvent,
    InsiderTradeEvent,
    OptionFlowEvent,
    PositionChange,
    SmartMoneyFilingEvent,
)


def _tags(*tags: str) -> str:
    normalized = []
    for tag in tags:
        clean = tag.strip().replace(" ", "")
        if clean:
            normalized.append(clean if clean.startswith("#") else f"#{clean}")
    return " ".join(normalized)


def _format_positions(items: list[PositionChange]) -> str:
    if not items:
        return "无重点变化"
    lines = []
    for index, item in enumerate(items, start=1):
        details = [item.market_value]
        if item.change_text:
            details.append(item.change_text)
        if item.portfolio_weight:
            details.append(f"占比 {item.portfolio_weight}")
        lines.append(f"{index}. {item.ticker}｜{item.company_name}｜{'｜'.join(details)}")
    return "\n".join(lines)


def _footer(source_name: str, source_url: str, tags: str, risk_note: str) -> str:
    lines = []
    if source_name or source_url:
        if source_url:
            lines.append(f"🔗 来源：{source_name or '查看原始披露'}")
            lines.append(source_url)
        else:
            lines.append(f"🔗 来源：{source_name}")
        lines.append("")
    if tags:
        lines.append(f"📡 {tags}")
        lines.append("")
    lines.append(risk_note)
    return "\n".join(lines)


def render_option_flow(event: OptionFlowEvent) -> str:
    theme_tag = event.theme_tags[0] if event.theme_tags else "美股"
    tags = _tags("期权异动", event.ticker, theme_tag)
    return f"""{event.direction_emoji} [期权异动] {event.ticker} {event.direction_text}资金异动

标的：{event.ticker}｜{event.company_name}
方向：{event.option_type}
合约：{event.expiration_date} ${event.strike_price}{event.contract_side}
{event.premium_label}：约 {event.premium}
成交量/OI：{event.volume} / {event.open_interest}
异动强度：{event.level}
股价：{event.underlying_price}

🔎 触发原因：
{event.trigger_reason}

🧠 一句话解读：
{event.plain_language_summary}

{_footer(event.source_name, event.source_url, tags, event.risk_note)}"""


def render_smart_money(event: SmartMoneyFilingEvent) -> str:
    person_tag = event.investor_name.replace(" ", "")
    tags = _tags("聪明钱", event.filing_type, person_tag)
    return f"""🧭 [聪明钱调仓] {event.entity_name} 最新持仓变化

披露主体：{event.entity_name}
关联人物：{event.investor_name}
文件类型：{event.filing_type}
报告期：{event.period}
披露日期：{event.filed_date}
披露延迟：约 {event.delay_days} 天

🆕 新增：
{_format_positions(event.new_positions)}

📈 增持：
{_format_positions(event.increased_positions)}

📉 减持：
{_format_positions(event.reduced_positions)}

🔎 重点变化：
{event.key_change_summary}

🧠 一句话解读：
{event.plain_language_summary}

{_footer(event.source_name, event.source_url, tags, event.risk_note)}"""


def render_congress_trade(event: CongressTradeEvent) -> str:
    person_tag = event.member_name.replace(" ", "")
    tags = _tags("国会交易", person_tag, event.ticker)
    description_line = f"交易说明：{event.description}" if event.description else ""
    option_line = f"合约详情：{event.option_contract}" if event.option_contract else ""
    detail_lines = "\n".join(line for line in [option_line, description_line] if line)
    return f"""🏛️ [国会交易] {event.member_name} 关联账户披露 {event.ticker} 交易

人物：{event.member_name}
关联人：{event.owner}
标的：{event.ticker}｜{event.company_name}
交易方向：{event.buy_or_sell}
交易类型：{event.asset_type}
金额区间：{event.amount_range}
交易日期：{event.transaction_date}
披露日期：{event.disclosure_date}
披露延迟：{event.delay_days} 天
{detail_lines}

📊 交易日至今表现：
{event.price_performance}

🧠 一句话解读：
{event.plain_language_summary}

{_footer(event.source_name, event.source_url, tags, event.risk_note)}"""


def render_congressional_disclosure(event: CongressionalDisclosureEvent) -> str:
    tags = _tags("国会交易", event.chamber, event.member_name.replace(" ", ""))
    return f"""🏛️ [国会披露] {event.member_name} 新增 {event.filing_type} 披露

来源机构：{event.chamber}
人物：{event.member_name}
披露类型：{event.filing_type}
州/选区：{event.state_district or "未披露"}
披露年份：{event.filing_year}
披露日期：{event.filed_date or "未披露"}
文件编号：{event.document_id}

🔎 筛选原因：
官方披露索引出现新的 periodic transaction report，已进入候选队列等待进一步解析交易明细。

🧠 一句话解读：
这类披露代表相关议员或候选人提交了交易报告，但具体标的、方向和金额仍需以原始文件为准。

{_footer(event.source_name, event.source_url, tags, event.risk_note)}"""


def render_insider_trade(event: InsiderTradeEvent) -> str:
    tags = _tags("内幕交易", "Form4", event.ticker)
    return f"""🧾 [内幕交易] {event.ticker} {event.buy_or_sell}

公司：{event.ticker}｜{event.company_name}
人物：{event.insider_name}
职务：{event.title}
方向：{event.buy_or_sell}
数量：{event.shares} 股
金额：约 {event.value}
均价：{event.average_price}
交易日期：{event.transaction_date}
披露日期：{event.filed_date}

🔎 筛选原因：
{event.screen_reason}

🧠 一句话解读：
{event.plain_language_summary}

{_footer(event.source_name, event.source_url, tags, event.risk_note)}"""


def render_daily_radar(event: DailyRadarEvent) -> str:
    top_lines = "\n".join(f"{index}. {line}" for index, line in enumerate(event.options_top_5, start=1))
    update_lines = "\n".join(f"- {line}" for line in event.smart_money_updates) or "- 暂无重点更新"
    tags = _tags("盘后雷达", "期权异动", "聪明钱")
    return f"""🌙 [盘后雷达] 今日美股异动榜｜{event.date}

🔥 期权异动 Top 5：
{top_lines}

🧭 聪明钱/披露更新：
{update_lines}

🔎 今日最值得复盘：
{event.daily_commentary}

👀 明日观察：
{', '.join(event.watchlist)}

{_footer(event.source_name, event.source_url, tags, event.risk_note)}"""
