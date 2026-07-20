# 美股异动雷达

面向中文美股用户的 Telegram 自动推送项目，追踪期权异动、聪明钱调仓、国会议员交易、内幕交易和盘后异动榜。

## 当前阶段

MVP 骨架：

- 配置读取
- 推送模板渲染
- Telegram Bot 发送模块
- 样例推送 dry-run

## 本地运行

复制环境变量：

```bash
cp .env.example .env
```

填写：

```text
TELEGRAM_BOT_TOKEN=你的 Bot Token
TELEGRAM_CHANNEL_ID=@你的频道 username 或频道 ID
```

安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

预览样例推送：

```bash
python3 scripts/send_sample.py --type option_flow --dry-run
```

真实发送：

```bash
python3 scripts/send_sample.py --type option_flow
```

注意：真实发送前需要把 Bot 加入频道并设置为管理员。

## 数据库

初始化 SQLite：

```bash
python3 -B scripts/init_db.py
```

SEC 13F 写库并去重：

```bash
python3 -B scripts/sec_recent.py --entity Berkshire --limit 1 --render --compare-13f --db --skip-seen
```

Form 4 写库并去重：

```bash
python3 -B scripts/form4_recent.py --issuer META --limit 1 --include-sales --render --db --skip-seen
```

期权异动检查：

```bash
python3 -B scripts/options_recent.py --db --render
```

默认免费模式会扫描 `config/options_watchlist.json` 中的重点标的，生成近月、近价 Call/Put 候选，并按前一交易日估算名义成交额取 Top 异动。当前 watchlist 包含 SPY、QQQ、NVDA、TSLA、AAPL、MSFT、META、AMZN、AMD、MU、SNDK、TQQQ、SOXL。

配置 `--db` 时，免费模式默认启用队列扫描：每次运行最多消耗 4 次 Polygon 请求，把剩余任务保存在 SQLite，适合由 supervisor 每分钟调度一次。遇到 429 会暂停本次运行并保留队列，下次继续。

```bash
python3 -B scripts/options_recent.py --db --render --request-budget 4
```

如需一次性批量扫描，可关闭队列，但免费套餐容易触发 429：

```bash
python3 -B scripts/options_recent.py --no-queue --db --render
```

如需接入真实期权数据，在 `.env` 配置：

```text
POLYGON_API_KEY=你的 Polygon API Key
TRADIER_ACCESS_TOKEN=你的 Tradier Access Token
TRADIER_BASE_URL=https://api.tradier.com/v1
```

未配置 key 时，期权抓取会记录为 0 条，方便在后台确认调度仍在运行。

默认 `options_recent.py` 使用免费计划友好的 previous-day aggregate bar，用于盘后/延迟期权异动观察。逐笔成交模式需要更高权限，可显式使用：

```bash
python3 -B scripts/options_recent.py --mode trades --db --render
```

如需只检查 `config/tracked_options.json` 中的固定合约，可显式使用：

```bash
python3 -B scripts/options_recent.py --scan tracked --db --render
```

## 审核队列

查看候选推送：

```bash
python3 -B scripts/review_queue.py list --status candidate --limit 20
```

查看单条全文：

```bash
python3 -B scripts/review_queue.py show 1
```

批准或拒绝：

```bash
python3 -B scripts/review_queue.py approve 1
python3 -B scripts/review_queue.py reject 1
```

## 发送 Approved 推送

频道还没创建时，先 dry-run：

```bash
python3 -B scripts/review_queue.py approve 1
python3 -B scripts/send_approved.py --post-id 1 --dry-run
python3 -B scripts/review_queue.py reset 1
```

频道和 Bot 配好后，真实发送：

```bash
python3 -B scripts/send_approved.py --limit 5
```

## 日志

查看运行日志：

```bash
tail -n 50 logs/radar.log
```

查看错误日志：

```bash
tail -n 50 logs/errors.log
```

后台也提供“抓取记录”，会显示每次 pipeline/数据源抓取时间、抓取条数、生成条数和内容简介。

## 定时任务入口

预览全流程：

```bash
python3 -B scripts/run_pipeline.py --dry-run --sec-limit 1 --form4-limit 1
```

写库并去重：

```bash
python3 -B scripts/run_pipeline.py --sec-limit 2 --form4-limit 3
```

写库、去重，并自动发送本轮新增候选：

```bash
python3 -B scripts/run_pipeline.py --sec-limit 2 --form4-limit 3 --auto-send
```

宝塔/cron 可使用：

```bash
cd /path/to/美股异动雷达
python3 -B scripts/run_pipeline.py --sec-limit 2 --form4-limit 3 >> logs/cron.log 2>&1
```

自动发频道的 cron：

```bash
cd /path/to/美股异动雷达
python3 -B scripts/run_pipeline.py --sec-limit 2 --form4-limit 3 --auto-send >> logs/cron.log 2>&1
```

## Web 后台

启动后台：

```bash
python3 -B scripts/admin_server.py
```

默认访问：

```text
http://127.0.0.1:8787
```

让 pipeline 使用后台设置：

```bash
python3 -B scripts/run_pipeline.py --use-settings --sec-limit 2 --form4-limit 3
```

本地持续运行调度器：

```bash
python3 -B scripts/run_scheduler.py
```

调度器会读取 Web 后台里的：

- 发送模式
- 是否包含 Form 4 公开市场卖出
- 单条发送间隔秒数
- 抓取间隔分钟
- 持续运行天数

停止调度器：

```text
Ctrl + C
```
