# feat/event-calendar-serving

## 这个分支做什么
把 `fact_event_daily` 接到 `finance_query`，并给「周末/下周大事」减掉默认 A 股契约。

## 当前状态
P0 `26b8f548` + P1 `6e861654` 已推。#347 open。
正在修存量红：`producer_fallback` 机械检查不再继承调用方 PYTHONPATH。
P1 已 live（`run_20260823_235609_843297`）：跨市场、剥 A 股、稿含英伟达/杰克逊霍尔。

## 未验证 / 已知边界
- 未切 8792。合 main ≠ 生产生效。
- PCE/IR 不在复盘会日历；P2 未做。

## 下一步
1. 全量 pytest / ruff 绿后合 #347。
2. 不要切 8792，除非用户明示。

## 踩过的坑
sidecar 启动器会把 PYTHONPATH / 判官 env 留在 shell。全量门禁必须卸掉，否则判官走真 Grok、机械检查测到另一棵树。
「周末发酵」会抢发酵预取。`__source_date` 必须走 `updated_at`。

## 已验证
P0/P1 离线 + 8797 产品路径。backoff 用例在污染 PYTHONPATH 下已绿。
