# 美股异动雷达：审核队列 CLI

状态：MVP 可用

## 1. 用途

审核队列用于半自动运营：

```text
抓取数据 -> 生成候选推送 -> 人工审核 -> 批准/拒绝 -> 后续发送到 Telegram
```

当前审核队列直接使用 `generated_posts.status` 字段。

## 2. 状态

- `candidate`：候选，等待审核
- `approved`：已批准，等待发送
- `rejected`：已拒绝，不发送
- `sent`：已发送

## 3. 查看候选

```bash
python3 -B scripts/review_queue.py list --status candidate --limit 20
```

输出示例：

```text
2 | candidate | insider_trade | META 公开市场卖出 | 2026-07-20T10:44:08+00:00
1 | candidate | smart_money_filing | Berkshire Hathaway 13F-HR | 2026-07-20T10:43:45+00:00
```

## 4. 查看全文

```bash
python3 -B scripts/review_queue.py show 1
```

## 5. 批准

```bash
python3 -B scripts/review_queue.py approve 1
```

## 6. 拒绝

```bash
python3 -B scripts/review_queue.py reject 1
```

## 7. 重置为候选

```bash
python3 -B scripts/review_queue.py reset 1
```

## 8. 已验证

- [x] 可列出 candidate 候选推送
- [x] 可展示单条推送全文
- [x] 可将 candidate 改为 approved
- [x] 可将 approved 重置回 candidate
- [x] 使用现有 SQLite 数据库运行

## 9. 下一步

- [x] 增加发送 approved 推送到 Telegram 的命令
- [x] 发送成功后更新状态为 `sent`
- [x] 写入 `sent_posts`
- [ ] 支持批量 approve/reject
- [ ] 支持按 post_type 过滤
