# G-05 `market_stage` 归一验收

> 分支：`fix/g05-market-stage-normalize`，基线 `gitea/main@7664af48`
> 旁路库：`/Users/a77/finance-workspace-private/db/history_labels.duckdb`
> 主库：`/Users/a77/finance-workspace-private/db/market_feature_store.duckdb`

## 现状量测（v2）

主库 `fact_market_daily` 与旧旁路库 `history_labels` 都是 413 个交易日、12 个类别（含 8 个 NULL 日）。原始成对写法如下：

| canonical 值 | 带「阶段」值 | 原始行数 | 带后缀行数 |
|---|---|---:|---:|
| 下跌 | 下跌阶段 | 16 | 36 |
| 主升 | 主升阶段 | 21 | 32 |
| 反弹 | 反弹阶段 | 9 | 15 |
| 探底 | 探底阶段 | 11 | 22 |
| 顶部横盘 | 顶部横盘阶段 | 15 | 102 |

另有 `底部横盘阶段=41`、`横盘=85`，以及 `market_stage IS NULL=8`；它们没有对应的另一套写法。旁路库原元数据为：

```text
label_version = v2-heat_sector_all_final_nonrt-stock_limit_high_union
source_max_trade_date = 2026-09-02
labels rows = 1,456,438
outcomes rows = 1,657,368
```

`LABEL_VERSION` 的唯一代码定义此前在 `intelligence/services/methodology_backtest/labels.py:90`（本刀改动后为 :93），本刀升为：

```text
v3-heat_sector_all_final_nonrt-stock_limit_high_union-market_stage_normalized
```

## 实施边界

- 新增 `intelligence/services/market_stage.py`，由一个纯函数统一去掉末尾一个「阶段」后缀；空值仍是 `NULL`。
- `labels.py` 在写旁路标签时调用该函数；不写、不改主库 `fact_market_daily`，所以原始事实仍可追溯。
- `river_query.normalize_stage` 保留为旧调用方兼容入口，但改为调用同一个 canonical 函数，不再维护第二套规则。
- 内置规则与 propose 示例改用 canonical 值；旧 v2 收据按版本不可比，必须在 v3 旁路库上重跑。

## v3 重建与规则对账

重建后 labels/outcomes 行数不变，旁路库的 `market_stage` 非空值为：

```text
下跌=52, 主升=53, 反弹=24, 底部横盘=41, 探底=33, 横盘=85, 顶部横盘=117
```

两套写法合并后，四条第五刀种子规则的整体读数均保持不变：

| 规则 | 整体 N / 命中 | v2 整体结论 | v3 整体结论 | 阶段桶变化 |
|---|---:|---|---|---|
| `diff_ratio_turn_up_5d` | 27,186 / 14,712 | `not_distinguishable` | `not_distinguishable` | 13 → 8 |
| `dual_red_streak3_continuation` | 88 / 60 | `not_distinguishable` | `not_distinguishable` | 3 → 2 |
| `first_board_new_high_1y_5d` | 4,790 / 2,288 | `not_distinguishable` | `not_distinguishable` | 12 → 7 |
| `limit_heat_rank_jump_3d` | 13,006 / 7,485 | `not_distinguishable` | `not_distinguishable` | 12 → 7 |

两条第五刀重点读数的变化也已记录：

- `diff_ratio_turn_up_5d`：v2 的「下跌阶段」桶 `n=2,291`、阶段级 `refuted`，与短写法「下跌」合并为 `n=3,194` 后为 `not_distinguishable`。
- `first_board_new_high_1y_5d`：v2 的「顶部横盘」桶 `n=182`、阶段级 `supported`，与「顶部横盘阶段」合并为 `n=1,536` 后为 `not_distinguishable`。

这不是回归：两条原结论本来各自只覆盖一个时期；归一后结论被撤回，正是 G-05 要消除的时期/阶段混杂。

## 可重放命令

```bash
.venv-workbench/bin/python scripts/methodology_backtest.py build-labels \
  --db-path /Users/a77/finance-workspace-private/db/market_feature_store.duckdb \
  --labels-db /Users/a77/finance-workspace-private/db/history_labels.duckdb
.venv-workbench/bin/python scripts/methodology_backtest.py outcomes \
  --db-path /Users/a77/finance-workspace-private/db/market_feature_store.duckdb \
  --labels-db /Users/a77/finance-workspace-private/db/history_labels.duckdb
.venv-workbench/bin/python scripts/methodology_backtest.py scan \
  --rules-dir methodology/rules \
  --labels-db /Users/a77/finance-workspace-private/db/history_labels.duckdb \
  --no-write
```

## 验证

- `intelligence/tests/test_methodology_backtest.py`：68 passed。
- `tests/test_river_query.py`：真实主库 9 passed；读取侧兼容入口与原始两套写法对照通过。
- `scripts/methodology_backtest_selftest.py`：21/21 passed，新增 G-05 归一 + v3 版本断言。
- ruff：修改文件 0 error。
