---
name: top-gainers-feishu
metadata:
  pattern: pipeline
description: 【已被 stock-technicals 取代，未暴露】强势股飞书入库与已入库强势股的均线回踩查询；飞书 2026-09-11 退役后跑不通，强势股回踩请用 stock-technicals，只看排行用 top-gainers。注意：本目录只为保留旧口径与历史脚本，不要再路由到这里。
superseded_by: stock-technicals
---

> **⚠ 2026-09-11 飞书整体退役（#727）后的实际可用性**：区间强势/均线回踩的筛选口径已按用户要求保留（#729）。
> 但它**读写的都是飞书强势股表**（`query_ma.py` 读、`write.py` 写），行情走 iFinD——当前**跑不通**。
> 只读算不入库的同类需求，用 `top-gainers` 与 `market_feature_store.cli weighted-gainers`。

# 强势股筛选入库

## 触发条件

- **入库模式**：用户说"强势股入库""涨幅入库""区间强势""涨幅筛选入库"并给出日期区间时触发
- **查询模式**：用户说"查询强势股""强势股均线""强势股回踩"时触发

## 查询模式（触发词：查询强势股）

运行脚本即可，脚本自动输出对齐表格：

```bash
python3 /Users/lbq/Desktop/c c/金融/skills/top-gainers-feishu/scripts/query_ma.py
```

均线取当日（最新交易日）值。直接将脚本输出展示给用户。

---

## 入库模式（触发词：强势股入库 + 日期区间）

入库模式 7 步流程（解析日期 → 并行查 iFinD 个股涨幅 + AKShare 板块 → 过滤涨幅>50% → 分批查申万行业与概念板块 → 整理核心题材/行业上榜 → 写飞书查重 → 输出入库摘要）见 `references/ingestion-flow.md`，逐步执行。
