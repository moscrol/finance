# feat/event-calendar-serving

## 这个分支做什么
把 `fact_event_daily` 接到 `finance_query`，并给「周末/下周大事」减掉默认 A 股契约。

## 当前状态
P0 `26b8f548` + P1 `6e861654` + PYTHONPATH 隔离 `1f200ce3` 已在分支。
启动器 env 曾把全量打成 6 红（`RAG_INDEX_DIR` 审生产索引、预热超时 360、`FINANCE_WS` 块外对照）。测试已锁隔离。全量 **6142 绿 / 5 skip**，提交后合 #347。

## 未验证 / 已知边界
- 未切 8792。合 main ≠ 生产生效。
- PCE/IR 不在复盘会日历；P2 未做。
- 前端叶子未跑：本单零 webapp diff。

## 下一步
1. 合 #347。不要切 8792，除非用户明示。

## 踩过的坑
sidecar 会留 PYTHONPATH / 判官 / `FINANCE_WS` / `RAG_INDEX_DIR` / `RAG_WORKER_PREWARM_TIMEOUT`。
门禁要卸判官；路径类测试必须自己钉夹具，不能靠 unset。
「周末发酵」会抢发酵预取。`__source_date` 必须走 `updated_at`。

## 已验证
P0/P1 离线 + 8797 产品路径。
启动器路径 env 仍在、判官卸掉：全量 6142 绿 / 5 skip。
启动器 env 下指纹/就绪/预热/paths + 本单夹具 88 绿。
