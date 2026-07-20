#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings
from src.models.events import (
    CongressTradeEvent,
    DailyRadarEvent,
    InsiderTradeEvent,
    OptionFlowEvent,
    PositionChange,
    SmartMoneyFilingEvent,
)
from src.posts.render import (
    render_congress_trade,
    render_daily_radar,
    render_insider_trade,
    render_option_flow,
    render_smart_money,
)
from src.telegram.sender import send_message


def build_sample(post_type: str) -> str:
    if post_type == "option_flow":
        event = OptionFlowEvent(
            ticker="NVDA",
            company_name="英伟达",
            theme_tags=["AI", "芯片"],
            direction_emoji="🟢",
            direction_text="看涨",
            option_type="Call",
            expiration_date="2026-08-21",
            strike_price="180",
            contract_side="C",
            premium="$4.8M",
            volume="12,400",
            open_interest="3,100",
            level="高",
            underlying_price="$172.35",
            trigger_reason="成交量约为未平仓量的 4.0 倍，单笔权利金超过 $500K，且距离财报窗口较近。",
            plain_language_summary="有资金押注 NVDA 未来一个月继续走强，但这类大单也可能是对冲或组合交易的一部分。",
            source_name="样例数据",
        )
        return render_option_flow(event)

    if post_type == "smart_money":
        event = SmartMoneyFilingEvent(
            entity_name="Berkshire Hathaway",
            investor_name="Warren Buffett",
            filing_type="13F",
            period="2026 Q2",
            filed_date="2026-08-14",
            delay_days="45",
            new_positions=[
                PositionChange("XYZ", "Example Co", "$1.2B"),
                PositionChange("ABC", "Sample Inc", "$620M"),
            ],
            increased_positions=[
                PositionChange("OXY", "Occidental Petroleum", "$15.0B", "+18.4%", "4.7%"),
                PositionChange("CVX", "Chevron", "$19.5B", "+9.7%", "6.1%"),
            ],
            reduced_positions=[
                PositionChange("AAPL", "Apple", "$65.0B", "-4.2%", "21.4%"),
                PositionChange("BAC", "Bank of America", "$22.0B", "-7.9%", "7.2%"),
            ],
            key_change_summary="能源仓位继续上升，科技股权重小幅下降，整体风格仍偏防御。",
            plain_language_summary="巴菲特这次调仓更像是在提高现金流和能源敞口，而不是大幅转向成长股。",
            source_name="SEC EDGAR",
            source_url="https://www.sec.gov/edgar/search/",
        )
        return render_smart_money(event)

    if post_type == "congress_trade":
        event = CongressTradeEvent(
            member_name="Nancy Pelosi",
            owner="Paul Pelosi",
            ticker="MSFT",
            company_name="微软",
            buy_or_sell="买入",
            asset_type="股票",
            amount_range="$250K - $500K",
            transaction_date="2026-07-02",
            disclosure_date="2026-07-18",
            delay_days="16",
            price_performance="MSFT 约 +3.6%",
            plain_language_summary="这笔交易发生在披露日前约两周，市场会关注其与 AI、云业务和财报预期的关系。",
            source_name="样例数据",
        )
        return render_congress_trade(event)

    if post_type == "insider_trade":
        event = InsiderTradeEvent(
            ticker="CRM",
            company_name="Salesforce",
            insider_name="Jane Example",
            title="Director",
            buy_or_sell="公开市场买入",
            shares="20,000",
            value="$5.1M",
            average_price="$255.30",
            transaction_date="2026-07-15",
            filed_date="2026-07-17",
            screen_reason="公开市场买入，金额超过 $1M，且买入人属于董事会成员。",
            plain_language_summary="高管公开市场买入通常比股权奖励更值得关注，但仍需结合公司基本面和交易背景判断。",
            source_name="SEC EDGAR Form 4",
            source_url="https://www.sec.gov/edgar/search/",
        )
        return render_insider_trade(event)

    if post_type == "daily_radar":
        event = DailyRadarEvent(
            date="2026-07-19",
            options_top_5=[
                "NVDA｜看涨大单，$180C 成交放大",
                "TSLA｜短期期权爆量，Call/Put 分歧明显",
                "AMD｜财报前 Call 成交升温",
                "PLTR｜价外 Call 异动，风险偏好增强",
                "SPY｜Put 放量，疑似指数对冲",
            ],
            smart_money_updates=[
                "Pelosi 关联账户披露 MSFT 买入",
                "某大型基金更新 13G，增持半导体标的",
                "CRM 董事披露公开市场买入",
            ],
            daily_commentary="AI 和半导体方向仍是期权资金最集中的主线，但指数 Put 同时放量，说明部分资金在追涨和防守之间摇摆。",
            watchlist=["NVDA", "AMD", "MSFT", "TSLA", "SPY"],
            source_name="样例汇总",
        )
        return render_daily_radar(event)

    raise ValueError(f"Unsupported post type: {post_type}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send or preview sample Telegram posts.")
    parser.add_argument(
        "--type",
        choices=["option_flow", "smart_money", "congress_trade", "insider_trade", "daily_radar"],
        default="option_flow",
        help="Sample post type to render.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print message instead of sending.")
    args = parser.parse_args()

    settings = Settings.load()
    text = build_sample(args.type)
    dry_run = args.dry_run or settings.dry_run
    result = send_message(
        bot_token=settings.telegram_bot_token,
        channel_id=settings.telegram_channel_id,
        text=text,
        dry_run=dry_run,
    )
    if dry_run:
        print("\n---")
        print("dry-run: message rendered only")
    else:
        print(result)


if __name__ == "__main__":
    from src.observability.logging import run_with_logging

    run_with_logging("send_sample", main)
