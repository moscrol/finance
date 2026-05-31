---
name: market-overview
description: 每日市场复盘（fupanhui API+飞书入库）。触发词：帮我复盘、复盘、看一下今天的市场、市场总览、今日行情、市场数据、fupanhui。
---

# Market Overview

## 触发条件

用户要求复盘、查看市场总览、今日行情、市场数据，或提到 fupanhui.com 时触发。支持指定任意交易日（含历史日期）。

## Overview

通过 fupanhui.com 内部 REST API 获取 A 股市场数据，输出结构化每日总结，并写入飞书 Bitable。

## 数据源

通过 CDP proxy 在已登录的浏览器标签页内调用 XHR，自动携带 session cookie。

```python
def fetch_api(target, api_path):
    js = ("(function(){var x=new XMLHttpRequest();"
          "x.open('GET','" + api_path + "',false);"
          "x.send();return x.responseText;})()")
    r = cdp_eval(target, js)
    return json.loads(r.get("value", "{}"))
```

### API 端点

| 用途 | 端点 |
|------|------|
| 最新交易日 | `/api/v1/client/reviews/latest-date?mode=auto`（字段 `latest_date`） |
| 市场数据 | `/api/v1/client/reviews/market?trade_date=YYYY-MM-DD&days=120&mode=auto` |
| AI 摘要 | `/api/v1/client/reviews/summary?trade_date=YYYY-MM-DD` |
| 市场周期 | `/api/v1/client/reviews/cycle?trade_date=YYYY-MM-DD` |
| 板块数据 | `/api/v1/client/reviews/sector?trade_date=YYYY-MM-DD` |
| 日历 | `/api/v1/client/calendar/month?year=YYYY&month=M` |

### market API 关键字段

```
data.volume        → 成交额、量能比
data.sentiment     → 涨跌停、涨跌家数
data.industry_spread
  .top3_total_pct  → 前三占比
  .top3_industries → [{rank, name, ratio}]
data.sector_strength → 板块强度列表
data.strength      → 市场强度
data.new_high      → 新高统计
```

## Steps

### Step 1: Open Page & Fetch Data

Load web-access skill，打开 fupanhui.com 任意页面获取 cookie，然后调用 API。

如果用户指定了历史日期，将 MM-DD 转为 YYYY-MM-DD（当前年份，超过今天则用前一年）。不指定则用 `latest-date` API 获取最新交易日。

调用以下 API 获取完整数据：
1. `/api/v1/client/reviews/market?trade_date=YYYY-MM-DD` — 量能、情绪、行业聚散
2. `/api/v1/client/reviews/summary?trade_date=YYYY-MM-DD` — AI 摘要
3. `/api/v1/client/reviews/sector?trade_date=YYYY-MM-DD` — 板块涨幅、行业特征

### Step 2: Extract 周均线 & 偏离度

导航到市场数据页面，hover K 线图获取 tooltip：

```bash
curl -s "http://localhost:${CDP_PROXY_PORT:-3456}/navigate?target=<targetId>&url=https://fupanhui.com/workspace/data/market"
```

等待 4 秒后，hover 第一个 canvas（上证指数 K 线）右侧蜡烛：

```javascript
var canvas = document.querySelectorAll("canvas")[0];
var rect = canvas.getBoundingClientRect();
var x = rect.x + rect.width * 0.97;
var y = rect.y + rect.height * 0.5;
canvas.dispatchEvent(new PointerEvent("pointermove", {clientX: x, clientY: y, bubbles: true, pointerId: 1, pointerType: "mouse"}));
canvas.dispatchEvent(new MouseEvent("mousemove", {clientX: x, clientY: y, bubbles: true}));
```

等待 500ms 后读取 tooltip，提取 `周均线: (\d+\.\d+)` 和 `偏离: ([+-]?\d+\.\d+%)`。

**验证（必须）**：用 API 返回的上证日收盘价计算偏离度 `(日收 - 周均线) / 周均线 * 100`，与 tooltip 偏离度数值比对，误差 > 0.05pp 说明 hover 位置偏左取到了非最后一根蜡烛，需重新提取。

### Step 3: Output Summary

格式化输出：

```
══════════════════════════════════════
  [日期] 市场总览
══════════════════════════════════════

【阶段】[横盘/探底/反弹/主升/下跌] 第N天 [冰点 if any]

【今日概况】
[AI summary condensed to 2-3 sentences]

【量能】
今日 X亿 | 较昨日 ±X% | 20日均 X亿
相对量能比 X% → [缩量/正常/放量/大幅放量]

【指数】
上证周均线 XXXX.XX | 偏离 ±X.XX%

【情绪】
涨停 X家 | 跌停 X家
涨 X家

【行业聚散】
前三占比：X% → [分散/正常/集中]
1. [sector] X%
2. [sector] X%
3. [sector] X%

【热点方向】
容量：[sector] X亿 | 锐度：[sector] | 宽度：[sector] | 资金：[sector]
```

量能状态范围：`<85%` 缩量 | `85-115%` 正常 | `115-120%` 放量 | `>120%` 大幅放量
集中度范围：`<35%` 分散 | `35-45%` 正常 | `>45%` 集中

### Step 4: Write to Feishu

写入两个飞书 Bitable 表。写入前按日期查重。

详细表结构、字段和写入流程见 `references/feishu_write.md`，凭证从 `~/.claude/shared/feishu_config.json` 读取。

### Step 5: Verify & Patch

```bash
python3 /Users/lbq/Desktop/c c/金融/skills/market-overview/scripts/verify_and_patch.py YY-MM-DD
```

检查白名单字段（`周均线`、`偏离度`）是否为空，空则定向重抓。

### Step 6: Clean Up

关闭本次任务创建的浏览器标签页。

### Step 7: 同步涨家数走势

```bash
python3 /Users/lbq/Desktop/c c/金融/skills/advancers-chart/scripts/sync.py
```

## 批量复盘多日

子 agent 通过 API 抓取（并行），主 agent 串行写入飞书。

### 子 agent prompt 模板

```
在 fupanhui.com 上用内部 API 获取 YYYY-MM-DD 的市场数据：
1. fetch /api/v1/client/reviews/market?trade_date=YYYY-MM-DD
2. fetch /api/v1/client/reviews/summary?trade_date=YYYY-MM-DD
3. fetch /api/v1/client/reviews/sector?trade_date=YYYY-MM-DD
4. navigate to market data page, hover K-line for 周均线/偏离度

返回以下字段（结构化文本）：
- 日期、阶段、天数、冰点（如有）
- AI 摘要（2-3句精简）
- 成交额(亿)、较昨日比(%)、20日均(亿)、相对量能比(%)、量能状态
- 涨停、跌停、涨
- 周均线、偏离度
- 前三占比(%)、集中度、行业1/占比1/行业2/占比2/行业3/占比3
- 行业特征：容量/锐度/宽度/资金 各字段（行业名、成交额、占比）
- 板块涨幅：当日/3日/5日/10日前五（收集所有出现板块的唯一集合）

只返回数据，不要写入任何表格。
```

### 覆盖检查

```bash
python3 /Users/lbq/Desktop/c c/金融/skills/market-overview/scripts/check_coverage.py [月份]
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Writing Feishu records without checking duplicates | Always query by date first, skip if exists |
| Copying AI summary verbatim | Condense to 2-3 key sentences |
| Adding personal market opinion | Report data, don't interpret beyond the reference ranges |
| Reading K-line tooltip before it renders | Wait 500ms after mousemove |
| Missing fields after write | Run verify_and_patch.py |
| Using DOM scraping for industry data | Use market API `.industry_spread` for reliable structured data |
| Assuming API field names | Check actual response keys first (`latest_date` not `trade_date`, `trade_date` not `date`) |
| Hover 位置偏左取到14:30蜡烛 | 用 `width * 0.97`（非0.9），提取后用上证日收交叉验证偏离符号 |
