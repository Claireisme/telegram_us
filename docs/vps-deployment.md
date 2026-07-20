# 美股异动雷达：VPS/宝塔第一阶段部署

状态：适用于第一阶段部署。

## 1. 部署目标

第一阶段先用 VPS/宝塔跑 Python 项目：

```text
cron 定时任务
  -> scripts/run_pipeline.py
  -> SEC 13F / Form 4 抓取
  -> SQLite 去重
  -> generated_posts 候选推送
  -> 手动审核
  -> Telegram 发送
```

优点：

- 当前代码可以直接跑。
- 不需要重构成 Cloudflare Workers。
- SQLite 和本地日志都能正常使用。

## 2. 环境要求

- Python 3.10+ 推荐
- 可访问 `data.sec.gov`
- 可访问 `www.sec.gov`
- 可访问 `api.telegram.org`
- 服务器时间建议使用 UTC 或保持 NTP 同步

当前项目尽量只使用 Python 标准库，暂时不需要安装第三方包。

## 3. 初始化

进入项目目录：

```bash
cd /path/to/美股异动雷达
```

复制环境变量：

```bash
cp .env.example .env
```

先填写 SEC User-Agent：

```text
SEC_USER_AGENT=USStockRadar your-email@example.com
DATABASE_PATH=data/radar.db
LOG_PATH=logs/radar.log
ERROR_LOG_PATH=logs/errors.log
DRY_RUN=true
```

初始化数据库：

```bash
python3 -B scripts/init_db.py
```

## 4. 试跑

不写数据库，只预览输出：

```bash
python3 -B scripts/run_pipeline.py --dry-run --sec-limit 1 --form4-limit 1
```

写数据库并跳过已见：

```bash
python3 -B scripts/run_pipeline.py --sec-limit 1 --form4-limit 1
```

写数据库、跳过去重，并自动发送本轮新增候选：

```bash
python3 -B scripts/run_pipeline.py --sec-limit 1 --form4-limit 1 --auto-send
```

注意：`--auto-send` 只会发送本次 pipeline 开始之后新生成的 `candidate`，不会发送历史堆积候选。

只跑 13F/13D/13G：

```bash
python3 -B scripts/run_pipeline.py --sec-only
```

只跑 Form 4：

```bash
python3 -B scripts/run_pipeline.py --form4-only
```

包含 Form 4 公开市场卖出：

```bash
python3 -B scripts/run_pipeline.py --form4-only --include-sales
```

## 5. 宝塔计划任务

宝塔面板：

1. 进入「计划任务」
2. 任务类型选择「Shell 脚本」
3. 周期按需要选择
4. 脚本内容填写：

```bash
cd /path/to/美股异动雷达
python3 -B scripts/run_pipeline.py --sec-limit 2 --form4-limit 3 >> logs/cron.log 2>&1
```

建议频率：

- SEC 13F/13D/13G：每天 1-2 次即可
- Form 4：美股交易日每 1-3 小时一次
- 第一阶段可以统一每 2 小时跑一次

如果你希望自动发频道，可以改成：

```bash
cd /path/to/美股异动雷达
python3 -B scripts/run_pipeline.py --sec-limit 2 --form4-limit 3 --auto-send >> logs/cron.log 2>&1
```

如果使用 Web 后台切换模式，cron 推荐改成：

```bash
cd /path/to/美股异动雷达
python3 -B scripts/run_pipeline.py --use-settings --sec-limit 2 --form4-limit 3 >> logs/cron.log 2>&1
```

更保守的做法是先只自动发 Form 4 买入，不包含卖出：

```bash
cd /path/to/美股异动雷达
python3 -B scripts/run_pipeline.py --form4-only --form4-limit 3 --auto-send >> logs/cron.log 2>&1
```

## 6. 审核和发送

查看候选：

```bash
python3 -B scripts/review_queue.py list --status candidate --limit 20
```

查看全文：

```bash
python3 -B scripts/review_queue.py show 1
```

批准：

```bash
python3 -B scripts/review_queue.py approve 1
```

频道还没创建时 dry-run：

```bash
python3 -B scripts/send_approved.py --post-id 1 --dry-run
```

频道创建后真实发送：

```bash
python3 -B scripts/send_approved.py --post-id 1
```

## 6.1 Web 后台

启动：

```bash
python3 -B scripts/admin_server.py
```

访问：

```text
http://127.0.0.1:8787
```

生产环境建议设置：

```text
ADMIN_PASSWORD=一个强密码
ADMIN_HOST=127.0.0.1
ADMIN_PORT=8787
```

## 7. Telegram 配置

创建频道和 Bot 后，在 `.env` 填写：

```text
TELEGRAM_BOT_TOKEN=你的 Bot Token
TELEGRAM_CHANNEL_ID=@你的频道username
DRY_RUN=false
```

注意：

- Bot 必须加入频道。
- Bot 必须是管理员。
- Bot 需要发布消息权限。

## 8. 日志

查看运行日志：

```bash
tail -n 100 logs/radar.log
```

查看错误日志：

```bash
tail -n 100 logs/errors.log
```

查看 cron 重定向日志：

```bash
tail -n 100 logs/cron.log
```

## 9. 备份

第一阶段最重要的是备份 SQLite：

```bash
cp data/radar.db backups/radar-$(date +%F).db
```

建议每天备份一次。

## 10. 当前限制

- 还没有 Web 审核后台，需要 CLI 审核。
- 已支持 `--auto-send` 自动发送本轮新增候选，但第一周建议先低频试跑。
- 还没有日志轮转，长期运行需要清理日志。
- 还没有期权异动 API，当前主要是 SEC 披露线。
