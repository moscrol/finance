# feat/finance-query-regulation

## 这个分支做什么

把监管安全池 / 监管在场名单 / 历史相似日接到 `finance_query`。#396 已合
`gitea/main@7ee2f5d4`。本单在干净树，不碰脏树 `feat/finance-query-technical-daily` 上别人的 WIP。

## 当前状态

树 `/Users/a77/fwp-wt-finance-query-regulation`。三张已写：
- `regulation_pool_daily`：`subset`，不开放小数涨幅/close
- `regulation_event_daily`：快照轴=`effective_date`；`end_date` 只做维度
- `historical_mapping`：`as_of`→物理列 `source_date`；`cutoff_column` 不用 `updated_at`
另修：语义别名时间维，T1b / `dataset_max_date` 按 `time_field` 解析，不按物理列反查。

合 main 未授权。不要切 8792。脏树 WIP 先留着。

## 未验证 / 已知边界

- 全仓 pytest / pre-commit 数字以提交前实测为准。
- 从未 live。`waiting` 0 行。池涨幅要暴露得先改写入侧。
- mapping 不能做 08-12 前回填墙之前的 PIT 重放。

## 下一步

1. 全仓绿后开 PR，等用户合。
2. 不要做 sw_l1.amount 单位换算。
3. 下一批候选仍在 `_UNREGISTERED_TABLES`。

## 踩过的坑

- `updated_at` 几乎全是 2026-08-12 回填墙，不能当信息日。
- 同名用别名，不要换 `similar_date`/`end_date` 当轴。
- 脏树 handoff 被 WIP 砍掉了质检段，不要原样采用。
- close 并非逐日等于行情表（08-24 碰巧相等）。

## 已验证

- 全仓 pytest：**6524 passed / 12 skipped / 0 failed**；ruff 绿。
- 门禁：20 注册 + 20 豁免 + 2 VIEW。
- 生产库三问：08-24 安全池 / 在场名单、08-13 相似日；evidence.source_date 都是快照日。
