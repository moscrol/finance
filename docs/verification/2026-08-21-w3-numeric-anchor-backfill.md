# W3：NUMERIC_UNSUPPORTED 回填按锚定主体反推（2026-08-21）

> 规格：`docs/superpowers/specs/2026-08-21-ceiling-shape-closeout-design.md` W3（形状 D）
> 台账：`R-20260821-09`（R-05 A 臂「候选观察不立案」升级）
> 代码：`fix/numeric-unsupported-anchor-backfill` @ `01c5f783`
> 生产 `:8792` **未切**。live 未部署，不得 `confirmed`。

## 0. 一句话

`NUMERIC_UNSUPPORTED` 不再静态映射到 `market_data`。回填目标 = f(episode 已解析的 `subject_kind`)：个股 → `finance_query`，市场级 → `market_data`，解析不出 → 不回填。

## 1. Before（R-05 A 臂原件）

工件：`probe-r05a-0821` / `run_20260821_185226_491046`。

- `subject=太辰光`，`subject_kind=company`
- 结构核验记 `numeric_unsupported`
- 修复轮回填 `market_data`，观察值是市场总览（上涨 4096 家 / 涨停 79 家）
- 这些市场级数字进了个股公开稿（见 `docs/verification/2026-08-21-r05-stock-contract-mismatch-repro.md` §3）

根因不是模型选错工具，是 harness 的静态映射把「缺一个数」翻译成「去拉市场总览」。

## 2. After（离线）

冻结夹具 `intelligence/tests/fixtures/w3-r05-a-numeric-backfill.json` 只保留主体与 issue code（不进公开稿）。同一 `subject_kind=company` + `NUMERIC_UNSUPPORTED`：

| | before（静态） | after |
|---|---|---|
| 回填能力 | `market_data` | `finance_query` |
| 市场总览污染 | 会进修复目标 | 不进修复目标 |

未整段重跑 252KB `continuous-episode.json`——那是 live 路径，不在本单离线门里。本单重放的是**回填计划**，因为污染的第一刀就是计划把 `market_data` 写进 `repair_goal.missing_evidence_modes`。

## 3. 离线 TDD

先红后绿。公开缝是 `plan_issue_backfill`（unit）和 adapter `handle()` 的 `repair_goal`（消费点）。

| 钉 | 行为 | 测试 |
|---|---|---|
| ① 个股 | `finance_query`，不含 `market_data` | `test_numeric_unsupported_company_backfills_finance_query` + adapter 同名钉 |
| ② 市场 | `market_data`（回归） | `test_numeric_unsupported_market_backfills_market_data` + 既有 W5 市场回填钉 |
| ③ 无主体 | 不回填 | `test_numeric_unsupported_without_subject_does_not_backfill` + adapter skip 钉 |

财务锚 `FINANCIAL_ANCHOR_MISSING → financial_data` 不动。数值缺口解析不出时，旁边的财务锚仍可单独回填。

## 4. 变异（先 commit `01c5f783`，再改已提交态）

把 `numeric_backfill_capability` 里个股分支改回 `market_data`（静态映射）：

- `test_numeric_unsupported_company_backfills_finance_query` 红：`('market_data',) == ('finance_query',)`
- `test_r05_a_arm_replay_company_numeric_does_not_plan_market_data` 红：同上
- adapter 个股钉红：`goal.missing_evidence_modes` 回到 `('market_data',)`

`git checkout -- intelligence/services/episode_issues.py` 还原后 3 条复绿。

## 5. 不做什么

- 不新造主体分类器。`quick_fact` 分不出「茅台多少钱 vs 涨停家数多少」是已知缺口，本单继续复用 `contract.subject_kind`。
- 题材 / `unknown` / 空字符串走 fail closed，不猜 `finance_query`。
- 不改预算、不改判官删除白名单、不部署 8792。

## 6. 复算命令

```bash
# 在 /Users/a77/fwp-wt-w3-numeric-backfill
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest \
  intelligence/tests/test_episode_issues.py \
  intelligence/tests/test_continuous_turn_adapter.py::test_numeric_unsupported_triggers_one_narrow_backfill_turn \
  intelligence/tests/test_continuous_turn_adapter.py::test_numeric_unsupported_company_backfill_asks_finance_query_not_market_data \
  intelligence/tests/test_continuous_turn_adapter.py::test_numeric_unsupported_unknown_subject_skips_backfill \
  -q
```

## 7. 全量门禁

- ruff 全仓绿
- pytest **5894 passed / 0 failed / 13 skipped**（基线 5888 + 本单 6 钉）
- 收据 `~/.finance-runtime/test-receipts/20260821T135845Z-a6c682e1.json`（`dirty=false`，`revision=a6c682e1`，`check_test_receipt.py` 可采信）
