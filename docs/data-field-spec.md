# 美股异动雷达：数据字段标准

状态：第一版

目的：

- 明确每类推送需要哪些字段。
- 明确哪些字段必须有，哪些字段可选。
- 方便后续抓取、数据库、文案生成和 Telegram 推送模块统一数据结构。

## 1. 通用字段

所有推送都应包含：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `post_type` | string | 是 | 推送类型，例如 `option_flow`、`smart_money` |
| `source_name` | string | 是 | 数据来源名称 |
| `source_url` | string | 否 | 原始数据链接 |
| `detected_at` | datetime | 是 | 系统发现时间 |
| `event_date` | date | 否 | 事件发生日期 |
| `ticker` | string | 否 | 股票代码 |
| `company_name` | string | 否 | 公司名称 |
| `theme_tags` | array[string] | 否 | 主题标签，例如 AI、芯片、能源 |
| `confidence` | string | 是 | `high`、`medium`、`low` |
| `importance_score` | number | 是 | 0-100，用于排序和是否推送 |
| `plain_language_summary` | string | 是 | 动态一句话解读 |
| `risk_note` | string | 是 | 默认 `⚠️ 非投资建议` |

通用 JSON 示例：

```json
{
  "post_type": "option_flow",
  "source_name": "options_api",
  "source_url": "https://example.com/source",
  "detected_at": "2026-07-19T20:35:00Z",
  "event_date": "2026-07-19",
  "ticker": "NVDA",
  "company_name": "NVIDIA",
  "theme_tags": ["AI", "芯片"],
  "confidence": "medium",
  "importance_score": 86,
  "plain_language_summary": "有资金押注 NVDA 未来一个月继续走强，但这类大单也可能是对冲或组合交易的一部分。",
  "risk_note": "⚠️ 非投资建议"
}
```

## 2. 期权异动字段

`post_type`: `option_flow`

必填字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `ticker` | string | 股票代码 |
| `company_name` | string | 公司名称 |
| `underlying_price` | number | 标的现价 |
| `option_type` | string | `call` 或 `put` |
| `direction_text` | string | 看涨、看跌、对冲、分歧 |
| `expiration_date` | date | 到期日 |
| `strike_price` | number | 行权价 |
| `contract_symbol` | string | 期权合约代码 |
| `premium` | number | 成交权利金金额，美元 |
| `volume` | number | 成交量 |
| `open_interest` | number | 未平仓量 |
| `volume_oi_ratio` | number | 成交量 / 未平仓量 |
| `trade_price` | number | 期权成交价 |
| `side_estimate` | string | `ask`、`bid`、`mid`、`unknown` |
| `expiration_days` | number | 距到期天数 |
| `trigger_reason` | string | 触发原因 |
| `level` | string | `高`、`中`、`低` |

可选字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `implied_volatility` | number | 隐含波动率 |
| `iv_rank` | number | IV Rank |
| `delta` | number | Delta |
| `earnings_date` | date | 下一次财报日期 |
| `is_near_earnings` | boolean | 是否临近财报 |
| `sector` | string | 行业 |
| `market_cap` | number | 市值 |
| `news_catalyst` | string | 相关新闻催化 |
| `is_multi_leg_likely` | boolean | 是否疑似多腿交易 |

JSON 示例：

```json
{
  "post_type": "option_flow",
  "ticker": "NVDA",
  "company_name": "英伟达",
  "underlying_price": 172.35,
  "option_type": "call",
  "direction_text": "看涨",
  "expiration_date": "2026-08-21",
  "strike_price": 180,
  "contract_symbol": "NVDA260821C00180000",
  "premium": 4800000,
  "volume": 12400,
  "open_interest": 3100,
  "volume_oi_ratio": 4.0,
  "trade_price": 6.2,
  "side_estimate": "ask",
  "expiration_days": 33,
  "trigger_reason": "成交量约为未平仓量的 4.0 倍，单笔权利金超过 $500K，且距离财报窗口较近。",
  "level": "高",
  "theme_tags": ["AI", "芯片"],
  "confidence": "medium",
  "importance_score": 86,
  "plain_language_summary": "有资金押注 NVDA 未来一个月继续走强，但这类大单也可能是对冲或组合交易的一部分。",
  "risk_note": "⚠️ 非投资建议"
}
```

## 3. 聪明钱调仓字段

`post_type`: `smart_money_filing`

必填字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `entity_name` | string | 披露主体 |
| `investor_name` | string | 关联人物 |
| `filing_type` | string | `13F`、`13D`、`13G` |
| `period` | string | 报告期 |
| `filed_date` | date | 披露日期 |
| `delay_days` | number | 披露延迟 |
| `new_positions` | array[object] | 新增持仓 |
| `increased_positions` | array[object] | 增持 |
| `reduced_positions` | array[object] | 减持 |
| `exited_positions` | array[object] | 清仓 |
| `key_change_summary` | string | 重点变化 |

持仓变化对象：

| 字段 | 类型 | 说明 |
|---|---|---|
| `ticker` | string | 股票代码 |
| `company_name` | string | 公司名称 |
| `market_value` | number | 持仓市值 |
| `change_percent` | number | 变化比例 |
| `portfolio_weight` | number | 组合占比 |

JSON 示例：

```json
{
  "post_type": "smart_money_filing",
  "entity_name": "Berkshire Hathaway",
  "investor_name": "Warren Buffett",
  "filing_type": "13F",
  "period": "2026 Q2",
  "filed_date": "2026-08-14",
  "delay_days": 45,
  "new_positions": [
    {"ticker": "XYZ", "company_name": "Example Co", "market_value": 1200000000, "change_percent": null, "portfolio_weight": 0.8}
  ],
  "increased_positions": [
    {"ticker": "OXY", "company_name": "Occidental Petroleum", "market_value": 15000000000, "change_percent": 18.4, "portfolio_weight": 4.7}
  ],
  "reduced_positions": [
    {"ticker": "AAPL", "company_name": "Apple", "market_value": 65000000000, "change_percent": -4.2, "portfolio_weight": 21.4}
  ],
  "exited_positions": [],
  "key_change_summary": "能源仓位继续上升，科技股权重小幅下降。",
  "confidence": "high",
  "importance_score": 92,
  "plain_language_summary": "巴菲特这次调仓更像是在提高现金流和能源敞口，而不是大幅转向成长股。",
  "risk_note": "⚠️ 非投资建议"
}
```

## 4. 国会议员交易字段

`post_type`: `congress_trade`

必填字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `member_name` | string | 国会议员姓名 |
| `owner` | string | 本人、配偶、子女、共同账户等 |
| `ticker` | string | 股票代码 |
| `company_name` | string | 公司名称 |
| `buy_or_sell` | string | 买入、卖出 |
| `asset_type` | string | 股票、期权、债券、基金 |
| `amount_range` | string | 披露金额区间 |
| `transaction_date` | date | 交易日期 |
| `disclosure_date` | date | 披露日期 |
| `delay_days` | number | 披露延迟 |
| `price_performance` | string | 交易日至披露日或当前表现 |

可选字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `party` | string | 党派 |
| `state` | string | 州 |
| `committee_roles` | array[string] | 委员会角色 |
| `sector` | string | 行业 |
| `policy_relevance` | string | 是否与政策领域相关 |

JSON 示例：

```json
{
  "post_type": "congress_trade",
  "member_name": "Nancy Pelosi",
  "owner": "Paul Pelosi",
  "ticker": "MSFT",
  "company_name": "微软",
  "buy_or_sell": "买入",
  "asset_type": "股票",
  "amount_range": "$250K - $500K",
  "transaction_date": "2026-07-02",
  "disclosure_date": "2026-07-18",
  "delay_days": 16,
  "price_performance": "MSFT 约 +3.6%",
  "party": "Democratic",
  "state": "CA",
  "committee_roles": [],
  "sector": "科技",
  "policy_relevance": "AI、云计算、政府采购",
  "confidence": "high",
  "importance_score": 88,
  "plain_language_summary": "这笔交易发生在披露日前约两周，市场会关注其与 AI、云业务和财报预期的关系。",
  "risk_note": "⚠️ 非投资建议"
}
```

## 5. 内幕交易 / Form 4 字段

`post_type`: `insider_trade`

必填字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `ticker` | string | 股票代码 |
| `company_name` | string | 公司名称 |
| `insider_name` | string | 内部人姓名 |
| `title` | string | 职务 |
| `buy_or_sell` | string | 买入、卖出 |
| `transaction_code` | string | Form 4 交易代码，例如 P、S、M、A |
| `shares` | number | 股数 |
| `value` | number | 交易金额 |
| `average_price` | number | 均价 |
| `transaction_date` | date | 交易日期 |
| `filed_date` | date | 披露日期 |
| `screen_reason` | string | 入选原因 |

可选字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `ownership_type` | string | 直接/间接持有 |
| `remaining_shares` | number | 交易后持股 |
| `is_open_market` | boolean | 是否公开市场交易 |
| `is_planned_sale` | boolean | 是否 10b5-1 计划卖出 |
| `insider_weight` | number | CEO/CFO/董事等权重 |

JSON 示例：

```json
{
  "post_type": "insider_trade",
  "ticker": "CRM",
  "company_name": "Salesforce",
  "insider_name": "Jane Example",
  "title": "Director",
  "buy_or_sell": "买入",
  "transaction_code": "P",
  "shares": 20000,
  "value": 5100000,
  "average_price": 255.3,
  "transaction_date": "2026-07-15",
  "filed_date": "2026-07-17",
  "screen_reason": "公开市场买入，金额超过 $1M，且买入人属于董事会成员。",
  "is_open_market": true,
  "is_planned_sale": false,
  "confidence": "high",
  "importance_score": 82,
  "plain_language_summary": "高管公开市场买入通常比股权奖励更值得关注，但仍需结合公司基本面和交易背景判断。",
  "risk_note": "⚠️ 非投资建议"
}
```

## 6. 每日盘后雷达字段

`post_type`: `daily_radar`

必填字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `date` | date | 日期 |
| `options_top_5` | array[object] | 期权异动 Top 5 |
| `smart_money_updates` | array[string] | 披露和聪明钱更新 |
| `daily_commentary` | string | 今日复盘 |
| `watchlist` | array[string] | 明日观察标的 |

Top 5 对象：

| 字段 | 类型 | 说明 |
|---|---|---|
| `rank` | number | 排名 |
| `ticker` | string | 股票代码 |
| `reason` | string | 入选原因 |
| `direction` | string | 看涨、看跌、分歧、对冲 |
| `importance_score` | number | 重要性评分 |

JSON 示例：

```json
{
  "post_type": "daily_radar",
  "date": "2026-07-19",
  "options_top_5": [
    {"rank": 1, "ticker": "NVDA", "reason": "看涨大单，$180C 成交放大", "direction": "看涨", "importance_score": 91},
    {"rank": 2, "ticker": "TSLA", "reason": "短期期权爆量，Call/Put 分歧明显", "direction": "分歧", "importance_score": 87}
  ],
  "smart_money_updates": [
    "Pelosi 关联账户披露 MSFT 买入",
    "CRM 董事披露公开市场买入"
  ],
  "daily_commentary": "AI 和半导体方向仍是期权资金最集中的主线，但指数 Put 同时放量。",
  "watchlist": ["NVDA", "AMD", "MSFT", "TSLA", "SPY"],
  "confidence": "medium",
  "importance_score": 90,
  "plain_language_summary": "今日资金继续围绕 AI 和半导体交易，但指数层面的 Put 放量说明防守需求也在升温。",
  "risk_note": "⚠️ 非投资建议"
}
```

## 7. 推送优先级

默认推送阈值：

- `importance_score >= 85`：即时推送
- `70 <= importance_score < 85`：进入候选队列，人工审核
- `50 <= importance_score < 70`：只进入盘后榜单候选
- `< 50`：不推送

置信度规则：

- `high`：来自官方披露或高质量付费数据源，字段完整。
- `medium`：数据可信，但部分字段需要推断，例如期权买卖方向。
- `low`：数据不完整，只能作为候选，不自动推送。

## 8. 去重规则

去重键建议：

- 期权异动：`ticker + expiration_date + strike_price + option_type + detected_date`
- 13F/13D/13G：`entity_name + filing_type + period + filed_date`
- 国会交易：`member_name + ticker + transaction_date + amount_range`
- Form 4：`ticker + insider_name + transaction_date + transaction_code`
- 盘后雷达：`date`

同一标的短时间内多次异动：

- 30 分钟内不重复推同一合约。
- 如果金额翻倍或出现新方向，可以推更新。
- 多条同方向异动可以合并成一条“连续异动”。

