# 美股异动雷达：运行日志与错误告警

状态：MVP 可用

## 1. 用途

运行日志用于排查定时任务和抓取脚本的问题：

- 哪个脚本什么时候开始运行
- 运行参数是什么
- 是否正常完成
- 如果失败，失败原因是什么

## 2. 日志文件

默认路径：

```text
logs/radar.log
logs/errors.log
```

环境变量：

```text
LOG_PATH=logs/radar.log
ERROR_LOG_PATH=logs/errors.log
```

## 3. 已接入脚本

- `scripts/sec_recent.py`
- `scripts/form4_recent.py`
- `scripts/review_queue.py`
- `scripts/send_approved.py`
- `scripts/send_sample.py`
- `scripts/init_db.py`
- `scripts/run_pipeline.py`

## 4. 查看日志

查看最近运行记录：

```bash
tail -n 50 logs/radar.log
```

查看最近错误：

```bash
tail -n 50 logs/errors.log
```

## 5. 已验证

- [x] 正常运行会写入 `logs/radar.log`
- [x] 脚本失败会写入 `logs/errors.log`
- [x] 日志包含脚本名和运行参数
- [x] 日志目录会自动创建

## 6. 当前限制

- 当前错误告警是本地错误日志，不会主动推送到手机。
- 后续可以接 Telegram 私聊 Bot、邮件或 Slack 通知。
- 当前没有日志轮转，长期运行后需要增加轮转策略。

## 7. 下一步

- [ ] 增加日志轮转
- [ ] 增加 Telegram 私聊错误通知
- [ ] 增加定时任务失败重试
- [ ] 增加每日运行摘要
