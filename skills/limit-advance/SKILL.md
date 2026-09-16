---
name: limit-advance
metadata:
  pattern: pipeline
description: 连板晋级梯队抓取与展示（fupanhui API）。触发词：晋级、连板晋级、晋级梯队。注意：入库走 CLI sync-fupanhui-limit-advance-daily，本 skill 只抓取+展示。
---

# 连板晋级筛选

## 触发条件

用户说"晋级"或要求查看连板晋级数据时触发。

## Step 1: 抓取并展示

```bash
python3 /Users/lbq/Desktop/c c/金融/skills/limit-advance/scripts/scrape.py [日期] [--min-boards=N]
```

- 日期可选，格式 MM-DD（如 05-07），默认最新交易日
- `--min-boards=3`（默认）筛选3板以上

脚本通过 fupanhui 内部 API 获取连板梯队数据（`/api/v1/client/limit/ladder`），无需页面 DOM 解析。输出对齐表格 + 时间轴甘特图。

直接将脚本输出展示给用户。

## 入库

抓取归本 skill，入库归流水线：
`python3 -m market_feature_store.cli sync-fupanhui-limit-advance-daily --trade-date D`
写 `fact_limit_advance_presence`（daily-full 里已经有这一步）。
原 Step 2「写入飞书连板晋级表」随飞书自建应用于 2026-09-11 退役而**不再执行**
（那张表最后一次写入是 2026-06-03）；`write.py` / `check_coverage.py` / `dedup_fields.py`
**保留在仓内**（见 #729），写入步因凭证退役失效，其去重 / 覆盖度核对逻辑仍可参考。

## 注意事项

- 禁止跳日期——必须逐日串行
- min_boards 默认 3，只写 3 板及以上晋级股
