# 美股异动雷达：数据库与去重层

状态：MVP 可用

## 1. 用途

数据库用于解决三个问题：

- 记录已经发现的 SEC 披露，避免重复处理同一份文件。
- 记录已经生成的 Telegram 候选推送，避免重复推送。
- 记录内部人交易事件，为后续审核队列和复盘统计做准备。

## 2. 技术选择

第一版使用 SQLite：

- 无需单独部署数据库服务。
- 适合本地 MVP 和小规模定时任务。
- 后续可以迁移到 Postgres。

默认路径：

```text
data/radar.db
```

环境变量：

```text
DATABASE_PATH=data/radar.db
```

## 3. 初始化

```bash
python3 -B scripts/init_db.py
```

## 4. 核心表

- `filings`：SEC/披露文件记录
- `generated_posts`：生成的候选推送
- `sent_posts`：已发送 Telegram 消息
- `trades`：内部人交易事件

## 5. 去重规则

SEC 披露：

```text
source + accession_number
```

生成内容：

```text
event_key
```

Form 4 交易事件：

```text
sec_form4 + accession_number + ticker + insider_name + transaction_code + transaction_date
```

## 6. 使用方式

记录 SEC 13F 披露和生成内容：

```bash
python3 -B scripts/sec_recent.py --entity Berkshire --limit 1 --render --compare-13f --db
```

跳过已记录 SEC 披露：

```bash
python3 -B scripts/sec_recent.py --entity Berkshire --limit 1 --render --compare-13f --db --skip-seen
```

记录 Form 4 交易和生成内容：

```bash
python3 -B scripts/form4_recent.py --issuer META --limit 1 --include-sales --render --db
```

跳过已记录 Form 4 交易：

```bash
python3 -B scripts/form4_recent.py --issuer META --limit 1 --include-sales --render --db --skip-seen
```

## 7. 已验证

- [x] 初始化 SQLite 数据库
- [x] SEC 13F 披露写入 `filings`
- [x] SEC 13F 推送写入 `generated_posts`
- [x] 第二次运行 `--skip-seen` 可跳过同一 13F accession
- [x] Form 4 交易写入 `trades`
- [x] Form 4 推送写入 `generated_posts`
- [x] 第二次运行 `--skip-seen` 可跳过同一交易事件

## 8. 下一步

- [x] 建立审核队列
- [x] 增加 CLI 查看候选推送
- [x] 增加 approve/reject 状态流转
- [x] 将 approved 候选推送接入 Telegram 发送
- [x] 写入 sent_posts
- [x] 增加运行日志
