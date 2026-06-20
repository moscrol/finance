# Market Overview 复盘步骤

> 本文件由 `skills/market-overview/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）；正文与原 SKILL.md 逐字节一致。

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

### ~~Step 4: Write to Feishu~~（已废弃）

> **已废弃。** 复盘数据统一走 `daily-full` → DuckDB 路径，不再写入飞书 Bitable。

### ~~Step 5: Verify & Patch~~（已废弃）

> **已废弃。** 用 `audit_coverage.py` 检查 DuckDB 覆盖替代。

### Step 6: Clean Up

关闭本次任务创建的浏览器标签页。

### Step 7: 同步涨家数走势

```bash
python3 /Users/lbq/Desktop/c c/金融/skills/advancers-chart/scripts/sync.py
```
