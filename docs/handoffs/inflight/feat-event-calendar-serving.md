# feat/event-calendar-serving

## 这个分支做什么
把 `fact_event_daily` 接到 `finance_query`，并落 8792 vs 手调的质量分层 spec。

## 当前状态
P0 v1.1：B1 `__source_date` 改走 `updated_at`；B2 last-touch/UTC 写入 spec+#7；B3 验收用主检出 venv。
待提交。底 `gitea/main@8688545b`。P1/P2 未做，且必须先有 #6。

## 未验证 / 已知边界
- 未 live、未切 8792。
- `served_date` 仍是结果集最晚 `event_date`（可晚于 cutoff）。
- 复盘会日历不是官方日程；PCE/IR 不在这张表。

## 下一步
1. 用户点头后 pathspec 提交、开 PR，不合 main。
2. P1 另开树：跨市场周历不得继承 `market_scope=A股`。

## 踩过的坑
`time_field <= cutoff` 对日历致命：发生日 ≠ 信息日。只给 `event_daily` 开 `allow_future_time_range` + `cutoff_column=updated_at`。

## 已验证
`pytest test_finance_query.py` 43P；truncation+dedupe 18P；registry 1P；ruff 绿。
生产库 cutoff=08-21、窗 08-24..28 返回英伟达 / AGIC / Jackson Hole。
