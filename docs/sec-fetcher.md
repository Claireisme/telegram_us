# 美股异动雷达：SEC 抓取模块

状态：MVP 可用

## 1. 已实现能力

- [x] 读取追踪机构配置
- [x] 使用 SEC company submissions JSON 拉取最新披露
- [x] 筛选目标表单：13F-HR、13D、13G
- [x] 找到 accession 目录中的 13F 信息表 XML
- [x] 解析 13F holdings
- [x] 对比最新一期和上一期 13F
- [x] 按持股数量判断新增、增持、减持
- [x] 渲染成 Telegram 推送文案

## 2. 关键文件

- `config/tracked_entities.json`：追踪机构/人物配置
- `src/fetchers/sec.py`：SEC 官方数据请求
- `src/parsers/sec.py`：SEC submissions 和 13F 信息表解析
- `scripts/sec_recent.py`：命令行测试脚本

## 3. 使用方式

查看 Berkshire 最近一条匹配披露：

```bash
python3 -B scripts/sec_recent.py --entity Berkshire --limit 1
```

渲染成 Telegram 文案：

```bash
python3 -B scripts/sec_recent.py --entity Berkshire --limit 1 --render
```

解析 13F 信息表并和上一期对比：

```bash
python3 -B scripts/sec_recent.py --entity Berkshire --limit 1 --render --compare-13f
```

## 4. 当前限制

- 13F 信息表里通常没有 ticker，当前通过内置 `security_master` 映射常见 CUSIP。
- 如果 CUSIP 未命中映射，会降级展示为 `CUSIP xxxxxxxxx`。
- 13D/13G 目前只发现文件，尚未深度解析持股比例变化。
- Form 4 已实现 MVP 解析，详见 `docs/form4-parser.md`。
- 暂未写入数据库，当前是命令行输出。

## 5. 已验证结果

已用 Berkshire Hathaway 的 SEC 数据做真实验证：

- CIK：`1067983`
- 最新匹配表单：`13F-HR`
- 报告期：`2026-03-31`
- 披露日期：`2026-05-15`
- 披露延迟：约 `45` 天
- 能成功解析 13F 信息表，并与上一期按持股数量对比。

## 6. 下一步建议

- [x] 加入 CUSIP -> ticker 映射
- [x] 实现 Form 4 XML 解析
- [ ] 实现 13D/13G 重点字段解析
- [ ] 将披露结果写入 SQLite
- [ ] 增加去重，避免重复推送同一份文件
- [ ] 接入审核队列
