# 美股异动雷达：第一版数据源选择

状态：MVP 方案已定

目标：先用可落地、低成本、来源可信的数据跑通频道，再逐步升级期权实时异动能力。

## 1. 数据源结论

MVP 采用“三层数据源”：

1. 官方公开源：用于 SEC、13F、13D、13G、Form 4、国会议员披露。
2. 低成本行情源：用于补充股价、涨跌幅、基础市场数据。
3. 期权数据过渡方案：先半自动/延迟数据，后接专业 API。

第一版不追求一开始就做到毫秒级期权异动，而是先做到：

- [ ] 披露类数据准确
- [ ] 推送格式漂亮
- [ ] 期权异动筛选规则稳定
- [ ] 每天能持续发出高质量内容
- [ ] 后续可无缝替换为专业期权 API

## 2. MVP 数据源清单

### 2.1 SEC 披露

用途：

- 13F
- 13D
- 13G
- Form 4
- 机构和内部人披露

第一版选择：

- [x] SEC Developer Resources
- [x] SEC EDGAR index files
- [x] SEC company submissions JSON
- [x] SEC filing documents

原因：

- 官方来源，可信度最高。
- 免费。
- 适合自动化抓取。
- 能覆盖聪明钱调仓和内幕交易。

注意：

- 必须遵守 SEC fair access 规则。
- 请求频率控制在 SEC 建议范围内。
- HTTP 请求需要设置清楚的 User-Agent。
- 13F 天然存在披露延迟，不能包装成实时持仓。

第一版实现方式：

- [ ] 使用每日 EDGAR index 扫描新文件
- [ ] 针对追踪 CIK 拉取 company submissions JSON
- [ ] 下载 13F 信息表
- [ ] 解析 Form 4 XML
- [ ] 存储 filing 原文链接
- [ ] 对比上一次持仓生成变化

### 2.2 众议院交易披露

用途：

- 众议员 periodic transaction reports
- Pelosi 等重点人物披露

第一版选择：

- [x] U.S. House Clerk Financial Disclosure Reports

原因：

- 官方来源。
- 页面提供按年份下载披露报告。
- 适合先做定时检测和解析。

注意：

- 披露文件可能是 PDF、HTML 或结构不完全统一。
- 金额是区间，不是精确金额。
- 交易通常有披露延迟。

第一版实现方式：

- [x] 下载当年披露索引
- [x] 过滤目标人物
- [x] 解析 PTR 文件交易明细
- [x] 匹配股票代码和交易方向
- [ ] 补充交易日至今表现
- [x] 生成披露索引候选推送
- [x] 生成交易明细候选推送

### 2.3 参议院交易披露

用途：

- 参议员 periodic transaction reports
- Senate financial disclosure reports

第一版选择：

- [x] U.S. Senate eFD / Senate Public Financial Disclosure Database

原因：

- 官方来源。
- Senate Ethics 页面明确 PTR 披露要求。
- 可作为国会交易追踪的必要补充。

注意：

- 参议院站点可能有人机验证或下载限制。
- 自动化抓取难度可能高于 House。
- 如果官方源解析成本过高，第二阶段可接 Quiver/Capitol Trades 等第三方 API。

第一版实现方式：

- [x] 接入官方搜索入口可用性检查
- [ ] 建立目标人物名单
- [ ] 每日检查是否有新披露
- [ ] 解析文件并进入审核队列

### 2.4 基础行情

用途：

- 当前价
- 交易日至今表现
- 披露日至今表现
- 标的名称
- 行业/主题标签辅助

第一版选择：

- [x] Yahoo Finance 非官方接口/库作为临时方案
- [x] Stooq 作为备选
- [x] Alpha Vantage 免费/低价 API 作为备选

原因：

- MVP 阶段成本低。
- 足够生成“交易日至今表现”等基础字段。
- 后续可替换为 Polygon、Finnhub、IEX 等专业源。

注意：

- Yahoo Finance 没有稳定官方公开 API，适合 MVP，不适合作为长期唯一依赖。
- 免费 API 有频率限制。
- 行情数据要做缓存，避免重复请求。

第一版实现方式：

- [x] 优先用低成本行情源补充日线收盘价
- [x] 当前价可以延迟，不追求实时
- [ ] 每天盘后批量更新 prices 表
- [x] 对推送涉及标的实时补充最新价

当前实现：

- Yahoo Finance chart 接口作为第一优先级，用于日线收盘价和交易日至今表现。
- Alpha Vantage `TIME_SERIES_DAILY` 作为可选备选源，配置 `ALPHA_VANTAGE_API_KEY` 后启用。
- Stooq CSV 作为最后备选；如果返回浏览器验证页，系统会识别失败并自动降级。
- `scripts/price_check.py` 可用于本地或服务器验证单个标的行情链路。

### 2.5 期权异动

用途：

- 大额 Call/Put
- 成交量/OI 异常
- 到期日、行权价、权利金、成交量、未平仓量
- 盘中异动快讯

MVP 过渡选择：

- [x] Alpha Vantage Options Data 作为低成本评估源
- [x] Tradier 作为中低成本候选
- [x] Polygon Options 作为专业升级候选
- [x] 手动参考 Unusual Whales/Barchart/Market Chameleon 等平台，先验证内容方向

原因：

- 期权高质量实时数据成本明显高于 SEC/国会披露。
- MVP 应先验证频道内容、模板和用户反馈。
- 等频道内容跑顺后，再接实时或准实时期权 API。

注意：

- 期权方向经常需要推断，不能写死为确定买入。
- 大单可能是组合腿、对冲、做市，不一定是单边看涨/看跌。
- 没有逐笔实时数据时，只适合做“异动观察”，不适合宣称实时。

第一版实现方式：

- [x] 先手动/半自动收集期权异动样例
- [x] 用字段标准生成推送
- [x] 跑通筛选、文案和 Telegram 展示
- [ ] 对比不同数据源的字段完整度
- [ ] 确认是否购买 Polygon/Tradier/其他专业源

当前实现：

- Polygon Options 已接入最近成交查询入口，配置 `POLYGON_API_KEY` 后可检查 `config/tracked_options.json` 中的合约。
- Tradier 已接入 options chain 检查入口，配置 `TRADIER_ACCESS_TOKEN` 后可验证合约 bid/ask/volume。
- 没有配置 key 时，系统仍会记录一次 `options_flow` 抓取，抓取数和生成数为 0，摘要说明缺少配置。
- 当前先按已配置合约做 MVP 验证，后续再扩展为按标的自动筛选全链异常成交。

## 3. 第一版优先级

### P0：必须先做

- [x] SEC EDGAR
- [x] House Financial Disclosure
- [x] 基础行情源
- [x] Telegram Bot 推送

### P1：尽快接入

- [ ] Senate Financial Disclosure
- [ ] Form 4 XML 解析
- [ ] 13F 持仓对比
- [ ] 国会议员交易解析
- [ ] 日线行情补充

### P2：验证后升级

- [ ] 专业期权 API
- [ ] 实时期权异动
- [ ] 期权成交方向推断
- [ ] 多腿交易过滤
- [ ] 付费 Bot 自定义提醒

## 4. 第一版技术路线

```text
SEC / House / 行情源 / 期权候选数据
  -> fetchers
  -> parsers
  -> normalized events
  -> scoring
  -> post generation
  -> review queue
  -> Telegram send
```

目录建议：

```text
src/
  config/
  fetchers/
    sec.py
    house.py
    senate.py
    prices.py
    options.py
  parsers/
    sec_13f.py
    form4.py
    congress.py
    options_flow.py
  scoring/
    importance.py
  posts/
    render.py
    templates.py
  telegram/
    sender.py
  storage/
    db.py
```

## 5. 数据源升级路径

第 1 周：

- [ ] 使用 SEC/House/基础行情跑通披露类推送
- [ ] 期权异动先用手动样例和低成本数据验证模板

第 2-3 周：

- [ ] 接入 Senate
- [ ] 自动生成每日盘后雷达
- [ ] 收集频道阅读量和反馈

第 4 周：

- [ ] 选择一个期权数据 API
- [ ] 开始自动筛选期权异动
- [ ] 建立付费版 Bot 的数据能力边界

## 6. 官方来源备注

- SEC Developer Resources：SEC 提供 submissions 和 XBRL REST API，并提供 EDGAR 索引文件；SEC 同时要求自动访问遵守 fair access，当前说明包括总请求不超过 10 requests/second。
- House Clerk Financial Disclosure：众议院 Clerk 页面提供金融披露报告和按年份下载入口。
- Senate Ethics Financial Disclosure：参议院 Ethics 页面说明 STOCK Act 下的电子披露系统和 PTR 披露要求，PTR 需在收到交易通知后 30 天内提交，且不晚于交易日后 45 天。
- Tradier Market Data：Tradier 文档说明美股和期权市场数据，非券商账户实时数据能力有限，Sandbox 为延迟数据。
- Polygon Options API：Polygon 提供美国期权市场 REST/WebSocket/flat files 数据，适合专业升级。
- Alpha Vantage Options：提供美国期权数据接口，可作为低成本评估源。
