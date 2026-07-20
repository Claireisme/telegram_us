# 美股异动雷达：推送模板规范

状态：已确认，自动化系统按本文件生成推送。

## 1. 总体风格

- 使用轻量 emoji，提高 Telegram 可读性。
- 每条内容先给标题，底部统一放来源、标签和风险提示。
- 字段顺序固定，方便用户形成阅读习惯。
- 每条保留动态生成的“一句话解读”。
- 公开频道每条使用极短风险提示：`⚠️ 非投资建议`
- 完整免责声明放在置顶公告。

## 2. Emoji 规范

通用：

- `🔗` 信息来源
- `📡` 标签行，放在风险提示上方
- `🔎` 触发原因/重点变化/筛选原因
- `🧠` 一句话解读
- `⚠️` 风险提示

分类：

- `🟢` 看涨/买入/增持
- `🔴` 看跌/卖出/减持
- `🧭` 聪明钱调仓
- `🏛️` 国会议员交易
- `🧾` SEC/Form 4/内幕交易
- `🌙` 盘后雷达
- `🔥` Top 榜单
- `👀` 明日观察
- `📊` 表现/统计
- `🆕` 新增
- `📈` 增持/上涨
- `📉` 减持/下跌

## 3. 一句话解读规则

一句话解读必须动态生成，不使用完全固定套话。

生成原则：

- 不超过 1-2 句。
- 不喊单。
- 不承诺方向。
- 说明“为什么值得关注”。
- 至少保留一个谨慎解释，例如对冲、披露延迟、组合交易、金额区间、历史不代表未来。

按类型生成：

- 期权异动：解释异动强度、可能交易意图、是否临近事件。
- 聪明钱调仓：解释仓位变化代表的风格变化。
- 国会交易：解释交易与行业、政策、财报或市场叙事的关系。
- 内幕交易：解释公开市场买入/卖出的信号质量。
- 盘后雷达：总结当天资金主线和市场分歧。

## 4. 风险提示规则

公开频道：

- 每条末尾统一放：`⚠️ 非投资建议`
- 置顶公告放完整风险说明。

Bot 私聊提醒：

- 后续可实现“每个用户每天第一次推送前提示一次风险”。
- 该能力不属于公开频道本身能力，需要用户主动 `/start` Bot。

完整风险说明：

```text
本频道内容仅基于公开披露、公开市场数据和第三方数据整理，不构成任何投资建议、买卖建议或收益承诺。期权交易风险极高，13F、国会议员交易、内幕交易等披露信息可能存在延迟、误差或不完整。请独立判断，自行承担风险。
```

## 5. 正式模板：期权异动

```text
{direction_emoji} [期权异动] {ticker} {direction_text}资金异动

标的：{ticker}｜{company_name}
方向：{call_or_put}
合约：{expiry} ${strike}{C_or_P}
成交金额：约 {premium}
成交量/OI：{volume} / {open_interest}
异动强度：{level}
股价：${spot_price}

🔎 触发原因：
{trigger_reason}

🧠 一句话解读：
{plain_language_summary}

🔗 来源：{source_name}
{source_url}

📡 #期权异动 #{ticker} #{theme_tag}

⚠️ 非投资建议
```

## 6. 正式模板：聪明钱调仓

```text
🧭 [聪明钱调仓] {entity_name} 最新持仓变化

披露主体：{entity_name}
关联人物：{investor_name}
文件类型：{filing_type}
报告期：{period}
披露日期：{filed_date}
披露延迟：约 {delay_days} 天

🆕 新增：
{new_positions}

📈 增持：
{increased_positions}

📉 减持：
{reduced_positions}

🔎 重点变化：
{key_change_summary}

🧠 一句话解读：
{plain_language_summary}

🔗 来源：{source_name}
{source_url}

📡 #聪明钱 #{filing_type} #{person_tag}

⚠️ 非投资建议
```

## 7. 正式模板：国会议员交易

```text
🏛️ [国会交易] {member_name} 关联账户披露 {ticker} 交易

人物：{member_name}
关联人：{owner}
标的：{ticker}｜{company_name}
交易方向：{buy_or_sell}
交易类型：{asset_type}
金额区间：{amount_range}
交易日期：{transaction_date}
披露日期：{disclosure_date}
披露延迟：{delay_days} 天

📊 交易日至今表现：
{price_performance}

🧠 一句话解读：
{plain_language_summary}

🔗 来源：{source_name}
{source_url}

📡 #国会交易 #{person_tag} #{ticker}

⚠️ 非投资建议
```

## 8. 正式模板：内幕交易 / Form 4

```text
🧾 [内幕交易] {ticker} {insider_action_summary}

公司：{ticker}｜{company_name}
人物：{insider_name}
职务：{title}
方向：{buy_or_sell}
数量：{shares} 股
金额：约 {value}
均价：${average_price}
交易日期：{transaction_date}
披露日期：{filed_date}

🔎 筛选原因：
{screen_reason}

🧠 一句话解读：
{plain_language_summary}

🔗 来源：{source_name}
{source_url}

📡 #内幕交易 #Form4 #{ticker}

⚠️ 非投资建议
```

## 9. 正式模板：每日盘后雷达

```text
🌙 [盘后雷达] 今日美股异动榜｜{date}

🔥 期权异动 Top 5：
{options_top_5}

🧭 聪明钱/披露更新：
{smart_money_updates}

🔎 今日最值得复盘：
{daily_commentary}

👀 明日观察：
{watchlist}

🔗 来源：{source_name}
{source_url}

📡 #盘后雷达 #期权异动 #聪明钱

⚠️ 非投资建议
```
