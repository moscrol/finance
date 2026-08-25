# docs/intraday-l2-sidecar

## 这个分支做什么

把 2026-08-25 摸底**没做完的后三步**落成独立设计稿。第一步（库存表进 `finance_query`）已在 PR #396，不是本单。

## 当前状态

正文：`docs/superpowers/specs/2026-08-26-intraday-l2-sidecar-design.md`（Draft v1）。
树：`/Users/a77/fwp-wt-intraday-l2-sidecar` ← `gitea/main@fe657cbc`。

未实施。P0（盘中 SQL）还没跑——写稿时是凌晨，盘后跑没有判别力。

## 下一步

1. 你拍两扇门，或说「按推荐：A1 + B1」。
2. 下一个交易日 10:00–14:30 跑 P0，收据落 `~/.finance-runtime/intraday-l2-probe/`。
3. 再开 `feat/intraday-l2-sidecar` 做 P1。不要在 #396 那棵树上做。

## 不要做

- 不要和 `market-watch` 四袋稿搞混（那是盘后组件包）。
- 不要再登记 `_DATASETS`。
- 不要改 daily-full 的 `push2delay`。
- 不要等 #396 合 main。
