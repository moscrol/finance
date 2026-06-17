---
name: sector-data
description: 抓取 fupanhui.com 227个板块数据，写入飞书多维表格和电子表格，验证后筛选成交额>500、涨幅>0、边际量>10%的板块，输出条件格式公式。触发：边际量、/sector-data、板块数据、抓取板块
---

# sector-data Skill

每天从 fupanhui.com 抓取板块数据，写入飞书，筛选量价齐升板块。

## 依赖

- web-access skill：CDP proxy（localhost:3456）
- `~/.claude/shared/feishu_utils.py`：飞书 API 工具
- `~/.claude/shared/feishu_config.json`：飞书凭证和表ID

## 输入

日期（可选），格式 `YYYY-MM-DD`。不传则获取最新交易日。

## 执行流程

执行流程 5 阶段（CDP 抓取 227 板块 search+kline 取 amount/diff_ratio → 写 Bitable `sector_daily` → 写电子表格边际量列 → 双向回读验证 → 筛选 amount>500 且 pct_chg>0 且 diff_ratio>10 并输出条件格式公式）见 `references/execution-flow.md`，逐步执行。

## 关键约束

- 飞书日期格式严格为 `YY-MM-DD`（20-12-31 表示 2020年12月31日）
- Bitable 字段值必须是字符串类型
- 重名板块（小金属）在飞书中用 `板块(tsCode)` 格式去重（括号非下划线），名称匹配时需兼容此格式
- diff_ratio 为 null 时（当日数据未就绪），电子表格该单元格留空
- 电子表格表头可能被锁定（90218错误），先尝试写表头，失败则只写数据行并提示用户手动补表头
- CDP eval 中用 `fetch()`（返回 Promise），非 `XMLHttpRequest`
- 长 JS 代码先写入文件再用 `curl -d "$(cat /tmp/file.js)"` 调用，避免 shell 转义问题
- 条件格式 OR() 公式按每15个板块拆分为多条规则，单条过长会静默失效
- Bitable 验证必须在 batch_update 之后重新 fetch_all_records()，不能用写入前的缓存数据
- `sectors/search` 的 `strength` 字段不是成交额，amount 只能从 kline API 获取
- 板块 universe 必须以当日 `sectors/search` 返回的 `ts_code` 为准，不要只依赖硬编码列表；历史回填曾因硬编码列表缺少 `886063.TI` 导致 `PEEK材料` 多个日期漏填
