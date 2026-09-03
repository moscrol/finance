# 2026-08-24 复盘会事件日历 serving 已合 main

## 合入
- PR：http://127.0.0.1:3300/a77/finance-workspace-private/pulls/347
- merge：`3fc47e91`（head `7764c150`）
- **未切 8792。** 合 main ≠ 生产生效。

## 进 main 的行为
- P0：`event_daily` → `fact_event_daily`；`__source_date` 走 `updated_at`。
- P1：周历题默认 `跨市场`，剥检索词里的默认「A股」，进场预取日历（空窗也记账）。
- 门禁卫生：机械检查丢掉继承的 `PYTHONPATH`；路径/RAG 夹具钉自己的索引，不读启动器 `FINANCE_WS` / `RAG_INDEX_DIR` / 预热超时。

## 门禁
干净树全量 **6142 passed / 5 skipped**（启动器路径 env 仍在，判官卸掉）。本单零 webapp diff，前端叶子未跑。

## 不要做
- 不要切 8792，除非用户再明示。
- 不要从脏主检出 `feat/reading-rules-baseline-batch1` rebase / 合本单。
- P2（空日程不得 complete）未做；PCE/IR 不在复盘会日历。
