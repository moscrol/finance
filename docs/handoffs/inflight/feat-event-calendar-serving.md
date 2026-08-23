# feat/event-calendar-serving

## 这个分支做什么
把 `fact_event_daily` 接到 `finance_query`，并给「周末/下周大事」减掉默认 A 股契约。

## 当前状态
P0 已提交 `26b8f548`，Gitea #347 open、fast-forward 可合。
P1 已写未提交：周历题 `market_scope=跨市场`；进场预取 `event_daily`；检索词剥默认「A股」。
8797 sidecar 用本树测过 P0（`run_20260823_234417_073940`）：模型自己调了 `event_daily`，稿里有英伟达/杰克逊霍尔；`news_search` 仍带「A股」。

## 未验证 / 已知边界
- P1 尚未再走产品路径 live。
- 未切 8792。合 main ≠ 生产生效。
- PCE/IR/贝森特不在复盘会日历；P2 空槽诚实未做。

## 下一步
1. 8797 再量同一题：检索词无默认「A股」；开场预取含英伟达或「库无行」。
2. 门禁绿才合 #347（含 P1 commit）。不要从脏主检出合。
3. 不要切 8792，除非用户明示。

## 踩过的坑
「周末发酵」会命中发酵预取，「板块未锚定」抢走盘面总览。周历检测必须压过 `is_fermentation_query`。
`__source_date` 必须走 `updated_at`，不能走发生日。

## 已验证
P0：`test_finance_query.py` 事件窗 + registry 整链。
P1 离线：`test_task_frame.py` + `test_asof_prefetch_calendar.py` + ruff 绿。
