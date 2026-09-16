# 工单 #51：同步失败连带丢掉 L2——守卫排在 L2 之前，已丢两个交易日

> 单类型：夜跑编排顺序变更（小单，半天）+ 一道回归闸。
> 主仓：金融。优先级 **P1**（正在流血：已丢 2 个交易日的 L2，每天继续丢）。
> 分支：`fix/sync-code-root`（与代码根修复同支落地，未另开）。
> 来源：`fix/sync-code-root` 删 `all)` 分支时，全量红把这条不变量顶了出来。

> **状态（2026-09-12）：核心已落，验收未闭合。** 提交 `1771a692`。
> - ✅ 验收 1「守卫红时 L2 仍跑」/ 2「守卫绿时行为不变」/ 3「顺序有回归钉」/ 4「旧测试改写不删」
>   ——`run_l2_branch` 已提到守卫之前；新增 `_run_nightly_finalize` 行为夹具（真启动脚本 +
>   假执行器 + `zsh -x` xtrace），四条行为测试；变异测试双向证明会咬。旧测试更名
>   `test_nightly_attempts_l2_before_the_sync_guard`，断言与 docstring 一并翻转。
> - ✅ 验收 5「装机副本同改并实跑」——已外科式打入 `/Users/a77/.local/bin/nightly_full_review.sh`
>   （备份 `*.bak-pre-l2order-20260912211157`），三用例真跑 + 反向对照通过。**没跑安装脚本整份覆盖。**
> - ⚠️ 验收 6「9-10 / 9-11 两天补数」——**9-10 完整补回；9-11 只补回 limitup 33 行**，
>   `top100` 判 failed（`input_count=0`）。原因见下方「前提被证伪」。
> - ✅ §4 三问已答，读数与证据见
>   `docs/verification/2026-09-12-l2-independence-production-writeback.md`。
> - **夜跑仍不宣告恢复**：9-11 行情未补 → 其 L2 另一半补不了；且 `is_trading_day` 的
>   误判未修，下一个「同步失败的交易日」L2 仍会静默 `exit 0`（顺序修复挡不住它）。

> **前提被证伪（重要）：§0 说「L2 不依赖同步段产物」，实测只对一半成立。**
> `process_l2_archive.py:189-190`——`limitup = duck_limitup_codes(prev)` 只依赖**前一交易日**，
> 这半确实独立；但 `top100 = duck_top_turnover_codes(date)` 读的是**当日**成交额排名，
> 也就是 `fact_stock_daily`，是**同日硬依赖**。行情缺失日的 L2 天然只能补一半，
> 另一半必须等当日行情入库后重跑。本单的修复方向没错，但「完全独立」是过强的说法。

## 0. 一句话

L2（资金流）不依赖同步段产物，但 `finalize)` 里质检守卫排在 `run_l2_branch` **之前**，
于是同步一失败就连带丢掉当天的 L2——**这条不变量在生产路径上从未成立过**。

## 1. 读数（2026-09-12 实测，可复跑）

```sql
SELECT max(trade_date) FROM feature_l2_capital_flow_daily;   -- 2026-09-09
SELECT max(trade_date) FROM feature_l2_quant_orders_daily;   -- 2026-09-09
SELECT max(trade_date) FROM fact_market_daily;               -- 2026-09-10
```

| 项 | 值 |
|---|---|
| L2 两表 max | **2026-09-09**（9-10、9-11 全丢） |
| 主库行情 max | 2026-09-10（9-11 丢） |
| 独立 L2 定时任务 | **无**（`launchctl list` 无 l2 / moneyflow 项） |

L2 比行情多丢一天：9-10 的行情是当晚 22:15 手动补进去的，而 20:40 的 finalize
早已在守卫处中止，事后无人重跑 finalize，于是 9-10 的 L2 段根本没执行。

## 2. 这条不变量原本写在哪、为什么失效

`tests/test_pipeline_p0.py` 曾有 `test_nightly_script_attempts_l2_before_sync_failure_exit`，
断言 **`all)` 分支内** `run_l2_branch` 排在「同步失败就退出」之前，docstring 写明
「一次 CDP 掉线不该连带丢掉当天的 L2」。

但：

1. 定时链是 sync plist（走 S7）+ finalize plist，**根本不经过 `all)`**；
   `finalize)` 里一直是守卫在前。`gitea/main` 上同样如此——不是本次改动造成的。
2. `all)` 同时直调同步器、绕开 staging 直写生产库，已在
   `fix/sync-code-root` 删除（安全原因，不可回退）。
3. 所以那条断言锚在一个**只在手动路径上成立、且该路径本身不安全**的位置。
   测试已改名为 `test_nightly_still_wires_l2_and_records_the_guard_before_l2_gap`，
   如实记录当前顺序并指向本单。

## 3. 要做什么

把 `run_l2_branch` 提到 `finalize)` 的守卫**之前**，让 L2 与同步段成为真正独立的
两条 DAG 分支；守卫继续只管生成段与方法飞轮。

## 4. 先回答这三个问题再动手（本单的真正难点）

> **✅ 2026-09-12 已答，带实测读数**：
> `docs/verification/2026-09-12-l2-independence-production-writeback.md` §1。
> 摘要——(1) 下游不 JOIN 行情表，算数；但 L2 自己在行情缺失日跑不完整。
> (2) 区分不了：`is_trading_day` 第 ④ 步用当日 `fact_stock_daily` 行数 ≥3000 判定，
> 库可读但 0 行时返回 `(False, approximate=False)`，把同步失败的真交易日**自信地**判成
> 非交易日；后果是 `run_l2_pipeline.sh` 静默 `exit 0`、`write_to_duckdb.py` 不落 failed。
> 逃生口 `L2_FORCE_TRADE_DAY=1`。**这条未修，另立单。**
> (3) 不在路径上，且是**有意**的（闲鱼日包迁移，仍是主检出树里的未提交改动）；
> 仓与生产在这块已分叉，收口方向由 L2 迁移那条线决定。

1. **行情缺失日跑 L2，写出来的数据算不算数？** L2 表按 `trade_date` 独立成行，
   但下游若用行情表做关联，会出现「有 L2 无行情」的日子。要么确认下游容忍，
   要么给这些行留标记。
2. **非交易日与 L2 日包缺失怎么区分？** 现有 `write_to_duckdb.py --fail` 只在实际
   交易日落 failed。守卫前移后，这个判断不能再依赖同步段是否成功。
3. **挂账暂停开关还在不在路径上？** `L2_PAUSED_FLAG` 在仓内源里有、**装机副本里没有**
   （见 `fix/sync-code-root` 交接）。先把装机副本这三组差异收口，否则改完的行为
   在生产上不成立。

## 5. 验收条件（可证伪，缺一不可）

| # | 判据 | 怎么验 | 期望 |
|---|---|---|---|
| 1 | 守卫红时 L2 仍跑 | 造一个同步缺数日，跑 finalize | L2 段执行并留记录，守卫仍中止生成段 |
| 2 | 守卫绿时行为不变 | 正常日跑 finalize | 与改动前逐步一致 |
| 3 | 顺序有回归钉 | 改回「守卫在前」 | 测试转红；还原转绿 |
| 4 | 旧测试同步更新 | `test_nightly_still_wires_l2_and_records_the_guard_before_l2_gap` | 其第 2 条断言按新顺序改写，docstring 一并改，**不许直接删** |
| 5 | 装机副本 | 同改并干净 shell 实跑 | 与仓内源行为一致（注意它另有三组差异） |
| 6 | 补数 | 9-10 / 9-11 两天的 L2 | 按 `run_l2_pipeline.sh <date>` 逐日回补，读数写进验收 |
| 7 | 全量 | 冻结提交、干净 detached 树 | ruff 绿；pytest 读数与失败项如实记录 |

## 6. 不要做

- 不要靠恢复 `all)` 来「顺便」拿回这条不变量——那条路绕开 staging 直写生产库。
- 不要在守卫红时连生成段一起放行：本单只让 L2 独立，不动生成段的门。
- 不要把「L2 跑了」当成「L2 有数据」：日包缺失时它应如实记 failed，不补空行。

## 7. 取号说明

全分支扫描（`refs/heads` + `refs/remotes/gitea`）显示 36–43、46–50 已占，
其中 #50 是同批立的生成段代码根单，故本单用 **51**。
