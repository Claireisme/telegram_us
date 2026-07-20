# 美股异动雷达：Form 4 内幕交易解析

状态：MVP 可用

## 1. 已实现能力

- [x] 从追踪发行人列表读取公司 CIK
- [x] 使用 SEC company submissions 拉取最近 Form 4 / Form 4-A
- [x] 从 accession index 找到真实 ownership XML
- [x] 解析内部人姓名、职务、交易代码、股数、价格、日期
- [x] 过滤公开市场买入/卖出：交易代码 `P` 和 `S`
- [x] 按同一公司、同一人、同一天、同一方向聚合多笔成交
- [x] 按交易金额阈值筛选
- [x] 渲染成 Telegram 推送文案

## 2. 关键文件

- `config/tracked_issuers.json`：追踪发行人配置
- `src/parsers/sec.py`：Form 4 XML 解析与聚合
- `scripts/form4_recent.py`：命令行测试脚本

## 3. 使用方式

默认只看公开市场买入，最低金额 $100,000：

```bash
python3 -B scripts/form4_recent.py --issuer META --limit 5 --render
```

包含公开市场卖出：

```bash
python3 -B scripts/form4_recent.py --issuer META --limit 5 --min-value 100000 --include-sales --render
```

查看原始简表，不渲染 Telegram 文案：

```bash
python3 -B scripts/form4_recent.py --issuer META --limit 5 --include-sales
```

## 4. 推送策略

第一版建议：

- 公开市场买入：优先推送
- CEO/CFO/董事长/董事大额买入：高优先级
- 公开市场卖出：默认进入候选队列，不自动推送
- 10b5-1 计划卖出：后续识别后降权
- 股权奖励、期权行权、税务扣缴：默认不推送

当前脚本策略：

- 默认只输出 `P`，即公开市场买入
- 加 `--include-sales` 后输出 `S`，即公开市场卖出
- 默认最低交易金额为 `$100,000`
- 同一天拆分成交会聚合为一条

## 5. 已验证样例

已用 META 的 SEC Form 4 做真实验证：

- 能解析 `ownership.xml`
- 能识别交易代码 `S`
- 能读取交易股数、均价、金额
- 能把同一高管同一天多笔交易聚合成一条
- 能渲染为频道模板

示例输出：

```text
🧾 [内幕交易] META 公开市场卖出

公司：META｜Meta Platforms, Inc.
人物：Olivan Javier
职务：Chief Operating Officer
方向：公开市场卖出
数量：1,942 股
金额：约 $1.3M
均价：$661
交易日期：2026-07-13
披露日期：2026-07-15

🔎 筛选原因：
Chief Operating Officer 公开市场卖出，交易金额约 $1.3M。

🧠 一句话解读：
公开市场卖出可能来自减持、税务或资产配置需求，不应直接等同于看空。

🔗 来源：SEC EDGAR Form 4
https://www.sec.gov/Archives/edgar/data/1326801/example-index.html

📡 #内幕交易 #Form4 #META

⚠️ 非投资建议
```

## 6. 当前限制

- 暂未识别 10b5-1 交易计划。
- 暂未解析 derivative transactions，例如期权行权细节。
- 暂未按 CEO/CFO/董事长等职务做评分。
- 暂未写入数据库和去重表。
- 暂未接入 Telegram 自动发送队列。

## 7. 下一步

- [ ] 增加职务权重评分
- [ ] 增加 10b5-1 计划识别
- [ ] 增加数据库写入和去重
- [ ] 建立审核队列
- [ ] 将高质量公开市场买入接入 Telegram 自动推送
