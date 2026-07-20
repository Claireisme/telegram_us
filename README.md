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
