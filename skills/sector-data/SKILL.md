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

### 阶段1：数据抓取

1. 启动 CDP proxy：
```bash
node "$HOME/.claude/skills/web-access/scripts/check-deps.mjs"
```

2. 创建 fupanhui.com 后台 tab：
```bash
curl -s "http://localhost:3456/new?url=https://fupanhui.com/workspace/data/sector-cycle"
```
从返回的 JSON 取 `target` 字段作为 TARGET_ID。

3. 获取227个板块列表（ts_code, name, pct_chg）：
```bash
curl -s -X POST "http://localhost:3456/eval?target=TARGET_ID" \
  -d "(async()=>{const r=await fetch('/api/v1/client/reviews/sectors/search?trade_date=DATE&mode=auto');const d=await r.json();return JSON.stringify(d.data||d);})()"
```
注意：`sectors/search` 返回的 `strength` 不是成交额，必须从 kline API 获取 `amount`。

4. 批量获取每个板块的 kline 数据（amount, diff_ratio, pct_chg），并发15：
在浏览器 tab 中执行 JS，将227个 ts_code 分批并发请求 kline API，取最后一个 kline 的 `amount`、`diff_ratio`、`pct_chg`。JS 写入文件再 curl 调用，避免 shell 转义问题。将结果保存到 `/tmp/sector_DATA_DATE.json`（格式：`{"value": "[{...}]"}`）。

5. 若需最新交易日，调用 `GET /api/v1/client/reviews/latest-date?mode=auto` 获取。

### 阶段2：写入多维表格（Bitable）

目标表 `sector_daily`（`tblXqyf9Av1rGg0n`）。

每条记录字段：板块、`YY-MM-DD涨幅`、`YY-MM-DD成交额`（飞书日期格式 `YY-MM-DD`）。

用 `feishu_utils.py`：
1. `get_token()` → `fetch_all_records()` 获取现有记录（按板块名建索引）
2. 若日期字段不存在 → `create_field()` 创建 `YY-MM-DD涨幅`(type=1) 和 `YY-MM-DD成交额`(type=1)
3. 将数值转为字符串，按板块名匹配 record_id
4. `batch_update()` 写入

### 阶段3：写入电子表格（Spreadsheet）

目标表 `sector_marginal_sheet`（token: `AHqIwJyMKiglO2kokwYcHRjJnWd`，sheet_id: `e8a204`）。

布局：A列=板块名，后续列=各日期边际量，第一行是日期表头。

1. 读取 A 列确认板块顺序：
```
GET /sheets/v2/spreadsheets/{token}/values/{sheet_id}!A2:A228
```
2. 找到下一个空列（读第一行，找第一个空单元格）
3. 写表头和227行数据：
```
PUT /sheets/v2/spreadsheets/{token}/values
{"valueRange": {"range": "{sheet_id}!X1:X228", "values": [["YY-MM-DD"], [diff1], [diff2], ...]}}
```

### 阶段4：验证

1. **Bitable 验证**：重新 `fetch_all_records()` 获取最新记录（不可复用写入前缓存），逐条对比 pct_chg 和 amount，报告匹配数和不匹配项。
2. **电子表格验证**：读回刚写入的列，逐条对比 diff_ratio，报告匹配数和不匹配项。
3. 确认表头日期格式为 YY-MM-DD。

### 阶段5：筛选与公式输出

1. 从源数据筛选：`amount > 500 AND pct_chg > 0 AND diff_ratio > 10`
2. 按 diff_ratio 降序排列，打印表格（板块名、成交额、涨幅、边际量）。
3. 输出条件格式公式（应用于电子表格该日期的列），按每15个板块拆分为多条规则：
```
规则1: =OR($A1="板块1",$A1="板块2",...,$A1="板块15")
规则2: =OR($A1="板块16",$A1="板块17",...,$A1="板块30")
...
```

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
