# 美股异动雷达：Web 后台

状态：MVP 可用

## 1. 功能

第一版 Web 后台提供：

- 今日/本周/本月生成数量
- 今日/本周/月发送数量
- candidate / approved / sent / rejected 状态统计
- 最近推送列表
- 查看单条推送全文
- 批准 / 拒绝 / 退回 / 发送
- 发送模式切换
- 是否包含 Form 4 公开市场卖出
- 单条发送间隔秒数
- 抓取间隔分钟
- 持续运行天数
- 抓取记录：每次抓取时间、来源、抓取条数、生成条数和摘要，即使 0 条也会记录
- 查看运行日志和错误日志

## 2. 启动

```bash
python3 -B scripts/admin_server.py
```

默认地址：

```text
http://127.0.0.1:8787
```

## 3. 环境变量

```text
ADMIN_HOST=127.0.0.1
ADMIN_PORT=8787
ADMIN_PASSWORD=建议设置一个强密码
```

如果 `ADMIN_PASSWORD` 为空，后台不会要求登录。此时务必保持：

```text
ADMIN_HOST=127.0.0.1
```

不要直接暴露到公网。

## 4. 三种发送模式

### manual

只生成候选，不自动发。

```text
candidate -> 人工 approve/reject/send
```

### semi_auto

本轮新生成候选会自动变成 approved，但仍需手动点击发送。

```text
candidate -> approved -> 人工 send
```

### auto

本轮新生成候选会自动发送。

```text
candidate -> sent
```

安全规则：

- 只处理本轮 pipeline 新生成的内容。
- 不会自动发送历史积压 candidate。
- 发送失败会恢复为 candidate。

## 5. 让 cron 使用后台设置

宝塔/cron 推荐命令：

```bash
cd /path/to/美股异动雷达
python3 -B scripts/run_pipeline.py --use-settings --sec-limit 2 --form4-limit 3 >> logs/cron.log 2>&1
```

这样你在后台切换手动/半自动/自动后，下一次 cron 会自动使用新设置。

## 6. 本地持续调度

如果不想配置 cron，可以直接运行本地调度器：

```bash
python3 -B scripts/run_scheduler.py
```

调度器会读取后台设置：

- 抓取间隔分钟：每隔多久运行一次 pipeline。
- 持续运行天数：从启动调度器开始，持续跑多少天。
- 发送模式：手动、半自动、自动发送。
- 单条发送间隔秒数：自动发送时，每两条新内容之间等待多久。

调度器启动后会先立即抓取一次，然后按间隔循环。停止方式：

```text
Ctrl + C
```

## 7. 宝塔部署建议

第一阶段建议只在本机访问后台：

```text
ADMIN_HOST=127.0.0.1
```

如果要通过域名访问：

- 设置 `ADMIN_PASSWORD`
- 用宝塔 Nginx 反代到 `127.0.0.1:8787`
- 域名开启 HTTPS
- 最好额外加 IP 白名单或 Basic Auth

## 8. 已验证

- [x] 后台首页可访问
- [x] 能显示统计数据
- [x] 能显示最近推送
- [x] 能切换发送模式
- [x] 能设置本地调度参数
- [x] 能查看日志
- [x] 能查看抓取记录
- [x] 能调用已有 Telegram 发送逻辑
