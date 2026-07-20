# 美股异动雷达：Telegram 发送流程

状态：dry-run MVP 可用，真实发送等待频道和 Bot 配置。

## 1. 当前结论

即使 Telegram 频道还没创建，也可以先使用 dry-run 验证发送内容。

流程：

```text
generated_posts(candidate)
  -> review_queue approve
  -> generated_posts(approved)
  -> send_approved dry-run preview
  -> 创建频道和 Bot 后真实 send
  -> sent_posts
  -> generated_posts(sent)
```

## 2. 频道还没创建时

批准一条候选：

```bash
python3 -B scripts/review_queue.py approve 1
```

预览将要发送的内容：

```bash
python3 -B scripts/send_approved.py --post-id 1 --dry-run
```

dry-run 不会：

- 访问 Telegram API
- 要求 Bot Token
- 要求 Channel ID
- 写入 `sent_posts`
- 把状态改成 `sent`

## 3. 创建 Telegram 频道后

在 Telegram 里搜索 `@BotFather`：

1. 发送 `/newbot`
2. 创建 Bot
3. 保存 Bot Token
4. 把 Bot 加入频道
5. 设置 Bot 为管理员
6. 给 Bot 发布消息权限

然后创建 `.env`：

```bash
cp .env.example .env
```

填写：

```text
TELEGRAM_BOT_TOKEN=你的 Bot Token
TELEGRAM_CHANNEL_ID=@你的频道 username 或频道 ID
DRY_RUN=false
```

## 4. 真实发送

先批准：

```bash
python3 -B scripts/review_queue.py approve 1
```

发送所有 approved：

```bash
python3 -B scripts/send_approved.py --limit 5
```

发送指定一条：

```bash
python3 -B scripts/send_approved.py --post-id 1
```

发送成功后会：

- 写入 `sent_posts`
- 把 `generated_posts.status` 从 `approved` 改为 `sent`

## 5. 已验证

- [x] approved 内容可 dry-run 预览
- [x] dry-run 不标记为 sent
- [x] dry-run 不需要 Telegram 频道
- [x] 发送脚本可读取 approved 队列
- [x] 发送成功后的状态更新逻辑已实现

## 6. 下一步

- [x] 创建 Telegram 频道
- [x] 创建 Telegram Bot
- [x] 配置 `.env`
- [x] 用一条 approved 内容做真实发送测试
- [x] 支持 pipeline `--auto-send`

## 7. 自动发送

自动发送本轮新增候选：

```bash
python3 -B scripts/run_pipeline.py --sec-limit 2 --form4-limit 3 --auto-send
```

安全规则：

- 只发送本次 pipeline 开始后新生成的候选。
- 不发送历史 candidate。
- 发送成功后状态变为 `sent`。
- 发送失败会恢复为 `candidate`，方便排查后重试。
