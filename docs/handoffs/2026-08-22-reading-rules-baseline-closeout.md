# 2026-08-22 判读基线收口

原分支 `feat/reading-rules-baseline-batch1`（主仓脏树，未碰）。
收口分支 `feat/reading-rules-baseline-r2`，树 `/Users/a77/fwp-wt-reading-rules-baseline`。

## 做了什么

- `git rebase --onto gitea/main 1df6844d`：9 笔重放。`1df6844d`（L2 开关）cherry 已是 `-`，丢掉。
- 唯一冲突：`market_timeseries.py` 进口。main 侧已有 `retrieval_cache` / `DOUBLE_RED_SQL` 等，与 `reading_baseline` 并保留。
- `#222` 已在 main。补两钉：episode payload 两套键同在；legacy 合成「本轮视角约束」后缀后判读基线仍在且更靠前。旧测试少传 `registry` 已跟上。
- `edd5c5ba`（晨汇 U+FFFD / matcher≠页面）**不进本单**：与判读基线无关，main 上也还没有，另开 docs 单。

## 没做（如实）

| 项 | 原因 |
|---|---|
| G1a 封板时间数据块 | 只解决 SPT-A06 半边；与 G1b 一起做全才激活 |
| G1b `open_times` 空壳 | 要你在场，CDP + 登录态对 fupanhui payload |
| 总开关 A/B、live | 从未 live |
| `user_framework`、B 类 4 条 | 原设计故意未建 |

清单与缺口：`docs/learning/reading-rules-inventory-2026-08-19.md`。

## 验证

`intelligence/tests` 5482 passed / 11 skipped。收据 `~/.finance-runtime/test-receipts/20260822T100609Z-05e22f8f.json`（含未提交共存钉时跑的）。

## 主仓那棵树

`/Users/a77/finance-workspace-private` 仍停在旧分支，脏区是复盘/台账，不是本单。不要在那 rebase。
