# 美股异动雷达从 0 启动方案

## 0. 项目定位

频道名：美股异动雷达

一句话定位：面向中文美股用户，自动追踪美股期权异动、聪明钱调仓、国会议员交易、内幕交易和机构披露，用清楚漂亮的 Telegram 推送帮助用户快速看懂市场资金动向。

核心原则：

- [ ] 数据公开、来源可追溯
- [ ] 推送简洁，一眼看懂
- [ ] 自动化优先，人工审核兜底
- [ ] 明确披露延迟，不包装成实时跟单
- [ ] 只做信息整理和数据提醒，不做买卖建议

频道内容结构：

- [ ] 期权异动：高频内容，负责日活和阅读量
- [ ] 聪明钱调仓：低频内容，负责信任和转发
- [ ] 国会议员交易：中频内容，负责话题性
- [ ] 内幕交易/Form 4：中高频内容，负责事件线索
- [ ] 盘后榜单：每日沉淀，负责留存
- [ ] 周报/月报：复盘内容，负责品牌感和付费转化

## 1. 第一阶段目标：MVP

目标：先做出一个可运行的半自动版本，每天能稳定产出 8-15 条高质量 Telegram 推送。

MVP 完成标准：

- [ ] 创建 Telegram 频道
- [ ] 创建 Telegram Bot
- [ ] 配置 Bot 发送权限
- [ ] 完成频道头像、简介、置顶公告
- [ ] 完成 5 类推送模板
- [ ] 完成期权异动筛选规则
- [ ] 完成聪明钱人物/机构追踪名单
- [x] 完成第一版数据源选择
- [ ] 完成半自动推送脚本
- [ ] 完成每日盘后榜单模板
- [ ] 连续试运营 7 天
- [ ] 根据阅读量和互动数据调整模板

## 2. 品牌与频道基础

### 2.1 频道简介

候选简介：

美股异动雷达，追踪美股期权大单、聪明钱调仓、国会议员交易、内幕交易和机构披露。所有内容仅基于公开数据整理，不构成投资建议。

待办：

- [x] 确认频道简介
- [ ] 设计频道头像
- [ ] 设计频道封面/品牌色
- [ ] 设置频道用户名
- [ ] 设置评论区讨论群
- [ ] 设置投稿/反馈入口

### 2.2 置顶公告

置顶公告草稿：

欢迎来到美股异动雷达。

本频道追踪：

- 期权异动
- 聪明钱调仓
- 国会议员交易披露
- SEC 13F / 13D / 13G / Form 4
- 每日盘后异动榜

重要说明：

1. 所有内容来自公开披露和市场数据。
2. 13F、国会议员交易等信息存在披露延迟。
3. 期权异动可能是方向交易、对冲、价差组合或做市行为。
4. 本频道不提供投资建议，不承诺收益。

待办：

- [x] 确认置顶公告文案
- [ ] 加入免责声明
- [ ] 加入广告合作联系方式
- [ ] 加入数据源说明链接

## 3. 人物与机构追踪名单

### 3.1 核心人物

- [ ] Warren Buffett / Berkshire Hathaway
- [ ] Nancy Pelosi
- [ ] Paul Pelosi
- [ ] Duan Yongping / 段永平
- [ ] Bill Ackman
- [ ] Michael Burry
- [ ] Stanley Druckenmiller
- [ ] David Tepper
- [ ] Ray Dalio
- [ ] Carl Icahn
- [ ] Seth Klarman
- [ ] Li Lu / 李录
- [ ] Terry Smith
- [ ] Cathie Wood
- [ ] Ken Griffin

### 3.2 国会议员重点名单

- [ ] Nancy Pelosi
- [ ] Dan Crenshaw
- [ ] Josh Gottheimer
- [ ] Michael McCaul
- [ ] Debbie Wasserman Schultz
- [ ] Ro Khanna
- [ ] Markwayne Mullin
- [ ] Tommy Tuberville
- [ ] Sheldon Whitehouse
- [ ] Marjorie Taylor Greene

说明：国会议员名单后续根据历史交易活跃度、媒体关注度和披露质量动态增删。

### 3.3 机构追踪名单

- [ ] Berkshire Hathaway
- [ ] Pershing Square
- [ ] Scion Asset Management
- [ ] Duquesne Family Office
- [ ] Appaloosa Management
- [ ] Bridgewater Associates
- [ ] Icahn Enterprises
- [ ] Baupost Group
- [ ] Himalaya Capital
- [ ] ARK Invest
- [ ] Citadel Advisors
- [ ] Renaissance Technologies
- [ ] Tiger Global
- [ ] Coatue Management
- [ ] Soros Fund Management

## 4. 数据源规划

### 4.1 免费/低成本数据源

- [ ] SEC EDGAR：13F、13D、13G、Form 4
- [ ] House Clerk：众议院 Periodic Transaction Reports
- [ ] Senate Financial Disclosures：参议院交易披露
- [ ] Yahoo Finance：基础行情
- [ ] Stooq：基础行情备选
- [ ] Nasdaq earnings calendar：财报日期参考
- [ ] 公司 IR 页面：特殊公告和持仓线索

### 4.2 付费/专业数据源候选

- [ ] Polygon：股票和期权行情
- [ ] Intrinio：期权链和 unusual activity
- [ ] Tradier：期权行情和交易数据
- [ ] Finnhub：股票行情和公司数据
- [ ] Quiver Quantitative：国会议员交易、政府合约、游说数据
- [ ] Capitol Trades：国会议员交易
- [ ] WhaleWisdom：13F 数据
- [ ] sec-api.io：SEC 文件解析
- [ ] Unusual Whales：期权异动参考
- [ ] Barchart：期权异动参考

### 4.3 数据源优先级

第一阶段：

- [x] SEC EDGAR
- [x] House/Senate 披露
- [x] Yahoo/Stooq 基础行情
- [x] 手动参考期权异动平台

第二阶段：

- [ ] 接入一个稳定的期权数据 API
- [ ] 接入国会议员交易 API
- [ ] 建立本地数据库
- [ ] 建立推送去重机制

第三阶段：

- [ ] 建立自有期权异动筛选器
- [ ] 建立历史回测模块
- [ ] 建立用户自定义提醒 Bot
- [ ] 建立付费会员数据面板

## 5. 推送模板

### 5.1 期权异动模板

```text
[期权异动] {ticker} {方向}资金异动

标的：{ticker} {company_name}
方向：{call_or_put}
合约：{expiry} ${strike}{C_or_P}
成交金额：约 {premium}
成交量/OI：{volume} / {open_interest}
异动强度：{level}
股价：${spot_price}
触发原因：{trigger_reason}

一句话解读：
{plain_language_summary}

注意：期权异动不等于方向确定，可能是对冲、组合交易或做市行为。
```

待办：

- [x] 确认期权异动模板
- [x] 确认是否使用 emoji
- [ ] 确认是否加入图表截图
- [ ] 确认是否加入行情链接

### 5.2 聪明钱调仓模板

```text
[聪明钱调仓] {investor_name} 最新持仓变化

披露主体：{entity_name}
文件类型：{filing_type}
报告期：{period}
披露日期：{filed_date}
披露延迟：约 {delay_days} 天

新增：{new_positions}
增持：{increased_positions}
减持：{reduced_positions}
清仓：{exited_positions}

重点变化：
{key_change_summary}

一句话解读：
{plain_language_summary}

注意：13F 披露存在延迟，不代表当前实时持仓。
```

待办：

- [x] 确认聪明钱调仓模板
- [ ] 确认展示前 5 还是前 10 个变化
- [ ] 确认是否加入持仓占比
- [ ] 确认是否加入季度对比图

### 5.3 国会议员交易模板

```text
[国会交易] {member_name} 披露 {ticker} 交易

人物：{member_name}
关联人：{owner}
标的：{ticker} {company_name}
交易方向：{buy_or_sell}
金额区间：{amount_range}
交易日期：{transaction_date}
披露日期：{disclosure_date}
披露延迟：{delay_days} 天

交易日至今表现：
{price_performance}

一句话解读：
{plain_language_summary}

注意：国会议员交易披露通常存在延迟，金额为区间披露。
```

待办：

- [x] 确认国会议员交易模板
- [ ] 确认是否单独追踪 Pelosi
- [ ] 确认是否展示交易日至今涨跌幅
- [ ] 确认是否加入历史胜率统计

### 5.4 内幕交易/Form 4 模板

```text
[内幕交易] {insider_name} {action} {ticker}

公司：{ticker} {company_name}
人物：{insider_name}
职务：{title}
方向：{buy_or_sell}
数量：{shares}
金额：约 {value}
交易日期：{transaction_date}
披露日期：{filed_date}

一句话解读：
{plain_language_summary}

注意：内幕交易披露不等于股价方向判断，需结合交易类型和背景。
```

待办：

- [x] 确认内幕交易模板
- [ ] 过滤自动奖励/期权行权
- [ ] 只推公开市场买入/卖出
- [ ] 给 CEO/CFO/董事长更高权重

### 5.5 每日盘后榜单模板

```text
[盘后雷达] 今日美股异动榜 {date}

期权异动 Top 5：
1. {ticker_1} - {reason_1}
2. {ticker_2} - {reason_2}
3. {ticker_3} - {reason_3}
4. {ticker_4} - {reason_4}
5. {ticker_5} - {reason_5}

聪明钱/披露更新：
{smart_money_updates}

今日最值得复盘：
{daily_commentary}

注意：仅为公开数据整理，不构成投资建议。
```

待办：

- [x] 确认盘后榜单模板
- [ ] 确认固定发布时间
- [ ] 确认是否加入图片版榜单
- [ ] 确认是否同步发到 X/小红书

## 6. 期权异动筛选规则

第一版筛选条件：

- [ ] 成交金额大于 500,000 美元
- [ ] 成交量 / 未平仓量大于 3
- [ ] 到期日小于 90 天
- [ ] 标的股日均成交量足够高
- [ ] 排除明显流动性不足的小票
- [ ] 排除明显多腿价差组合
- [ ] 财报前 14 天内提高权重
- [ ] 标的属于 AI、芯片、军工、医药、加密、能源、科技巨头时提高权重
- [ ] 与国会议员交易或聪明钱持仓重合时提高权重

异动强度评分：

- [ ] 金额权重
- [ ] 成交量/OI 权重
- [ ] 到期日权重
- [ ] 距离现价程度权重
- [ ] 是否临近财报
- [ ] 是否有新闻催化
- [ ] 是否与名人/机构持仓重合

## 7. 自动化架构

第一版架构：

```text
数据源
  -> 抓取任务
  -> 解析与标准化
  -> 筛选规则
  -> 去重
  -> 生成中文文案
  -> 人工审核
  -> Telegram Bot 推送
  -> 日志与统计
```

组件待办：

- [x] 初始化项目代码仓库
- [x] 配置 Python/Node 运行环境
- [x] 创建配置文件
- [x] 创建数据库
- [x] 创建 Telegram Bot 推送模块
- [x] 创建 SEC 抓取模块
- [x] 创建 Form 4 内幕交易解析模块
- [ ] 创建国会议员交易抓取模块
- [ ] 创建期权异动抓取模块
- [ ] 创建行情补充模块
- [x] 创建文案生成模块
- [x] 创建审核队列
- [x] 创建定时任务
- [x] 创建错误告警
- [x] 创建运行日志

## 8. 数据库设计草案

核心表：

- [x] tracked_entities：追踪人物/机构
- [x] securities：CUSIP -> ticker/company 映射
- [x] filings：SEC/国会披露文件
- [x] holdings：持仓明细
- [x] trades：交易披露
- [x] option_flows：期权异动
- [x] prices：行情快照
- [x] generated_posts：生成的推送内容
- [x] sent_posts：已发送记录
- [x] post_metrics：阅读量和互动数据

## 9. 频道运营节奏

每日节奏：

- [ ] 盘前：发布重点观察 3-5 条
- [ ] 盘中：发布强异动 5-15 条
- [ ] 盘后：发布每日异动榜 1 条
- [ ] 突发：SEC/国会/内幕交易重要披露即时推送

每周节奏：

- [ ] 周一：本周财报重点观察
- [ ] 周三：期权异动中期复盘
- [ ] 周五：本周聪明钱和异动榜
- [ ] 周末：一篇深度复盘/教学内容

## 10. 冷启动 7 天内容计划

第 1 天：

- [ ] 发布频道介绍和免责声明
- [ ] 发布 3 条期权异动样例
- [ ] 发布 1 条巴菲特持仓复盘

第 2 天：

- [ ] 发布盘前观察
- [ ] 发布 5-10 条期权异动
- [ ] 发布 Pelosi 历史交易复盘

第 3 天：

- [ ] 发布 AI/芯片主题期权异动榜
- [ ] 发布 Form 4 内幕买入案例
- [ ] 发布盘后榜单

第 4 天：

- [ ] 发布 13F 教学内容
- [ ] 发布重点机构持仓变化
- [ ] 发布期权异动复盘

第 5 天：

- [ ] 发布国会议员交易榜
- [ ] 发布财报前异动追踪
- [ ] 发布盘后榜单

第 6 天：

- [ ] 发布一篇“如何看懂期权异动”
- [ ] 发布本周强异动回顾
- [ ] 收集用户反馈

第 7 天：

- [ ] 发布周报
- [ ] 统计阅读量最高的内容类型
- [ ] 调整下一周推送策略

## 11. 商业化规划

免费频道：

- [ ] 期权异动精选
- [ ] 聪明钱快讯
- [ ] 国会议员交易提醒
- [ ] 每日盘后榜单

付费产品：

- [ ] 付费群
- [ ] 自定义提醒 Bot
- [ ] 高级数据表格
- [ ] 历史回测
- [ ] 每周深度报告
- [ ] 机构/API 数据订阅

广告位：

- [ ] 置顶广告
- [ ] 单条广告
- [ ] 周报赞助
- [ ] 工具推荐
- [ ] 券商开户链接
- [ ] 行情软件合作

## 12. 风险与合规

必须避免：

- [ ] 不宣称实时跟单
- [ ] 不承诺收益
- [ ] 不发布未验证内幕消息
- [ ] 不伪造数据源
- [ ] 不把延迟披露包装成实时调仓
- [ ] 不鼓励用户重仓或满仓
- [ ] 不接明显诈骗、资金盘、非法博彩广告

固定免责声明：

```text
本频道内容仅基于公开数据、市场数据和公开披露整理，不构成任何投资建议。期权交易风险极高，披露数据可能存在延迟、误差或不完整。请独立判断，自行承担风险。
```

## 13. 后续执行顺序

第 1 步：频道基础

- [x] 确认频道简介
- [x] 确认置顶公告
- [ ] 确认品牌视觉
- [ ] 创建 Telegram 频道和 Bot

第 2 步：内容模板

- [ ] 定稿 5 类推送模板
- [ ] 生成 20 条样例内容
- [ ] 测试 Telegram 展示效果
- [ ] 根据手机端阅读体验调整排版

第 3 步：数据源

- [x] 确认第一版期权数据源
- [x] 确认 SEC 数据源
- [x] 确认国会议员交易数据源
- [x] 确认行情数据源

第 4 步：自动化 MVP

- [x] 写 Telegram 推送脚本
- [ ] 写数据抓取脚本
- [ ] 写筛选规则
- [x] 写文案生成模块
- [ ] 写人工审核流程
- [x] 跑通第一条 dry-run 推送
- [x] 跑通第一条真实 Telegram 推送
- [x] 支持 pipeline 自动发送

第 5 步：试运营

- [ ] 连续运行 7 天
- [ ] 记录每条阅读量
- [ ] 统计用户反馈
- [ ] 调整推送频率
- [ ] 调整筛选阈值

第 6 步：产品化

- [ ] 建立数据库
- [x] 建立后台面板
- [ ] 建立付费 Bot
- [ ] 建立会员体系
- [ ] 建立广告报价表

## 14. 当前状态

- [x] 确认频道名称：美股异动雷达
- [x] 确认核心方向：聪明钱调仓 + 期权异动
- [x] 确认频道简介
- [x] 确认置顶公告
- [x] 确认第一版推送模板
- [x] 确认第一版数据源
- [ ] 开始搭建自动化 MVP
