# 美股异动雷达：Security Master

状态：MVP 可用

## 1. 用途

SEC 13F 信息表通常提供 CUSIP 和 issuer name，但不稳定提供 ticker。频道推送如果直接展示 CUSIP，用户很难一眼看懂。

Security Master 用来把：

```text
CUSIP 037833100｜APPLE INC
```

转换成：

```text
AAPL｜Apple
```

## 2. 关键文件

- `config/security_master.json`：内置 CUSIP 映射
- `src/storage/security_master.py`：映射读取和查询
- `scripts/sec_recent.py`：13F 渲染时应用映射

## 3. 降级规则

如果命中映射：

```text
AAPL｜Apple｜$958.3M｜-6.6%
```

如果未命中映射：

```text
CUSIP 037833100｜APPLE INC｜$958.3M｜-6.6%
```

这样映射不完整也不会阻断推送。

## 4. 当前覆盖

第一版重点覆盖：

- Berkshire Hathaway 最新 13F 中出现的主要标的
- 常见科技大票
- 常见金融、能源、消费和传媒标的

已包含示例：

- AAPL
- MSFT
- NVDA
- GOOG
- GOOGL
- AMZN
- META
- TSLA
- OXY
- CVX
- BAC
- DAL
- KHC
- MCO
- NUE
- STZ

## 5. 后续升级

- [ ] 增加更完整的 CUSIP 覆盖
- [ ] 接入 OpenFIGI 或专业行情源补全映射
- [ ] 增加 ticker 变更和并购退市处理
- [ ] 给每个标的补充 sector 和 theme
- [ ] 将映射写入数据库表 `securities`

