# 2026-09-12 · 工单 #51 生产侧收口：三问答案、装机补丁、9-10/9-11 补数

代码侧见 PR #739（`gitea/main@c703e068`）。本文记生产侧三件事的**实测读数**，
以及一条把工单前提证伪掉的发现。

## 0. 一句话

L2 顺序修好了、装机副本也打了补丁并真跑验证过，**9-10 完整补回，9-11 只补回一半**——
因为 `top100` 扫描名单来自**当日行情表**，而 9-11 的行情本身就没入库。工单
「L2 不依赖同步段产物」这条前提**只对 limitup 那一半成立**。

## 1. §4 三问的答案（都带实测）

### Q1：行情缺失日跑 L2，写出来的数据算不算数？

**下游算数，但 L2 自己跑不完整。**

下游三个消费者 `market_moneyflow.py` / `workbench_overview.py` / `render_moneyflow_html.py`
读 `feature_l2_*` 全是独立查询（`FROM feature_l2_capital_flow_daily` + `trade_date` 过滤
或 `max(trade_date)` 探针），**没有一条 SQL JOIN 连到 `fact_stock_daily` / `fact_sector_daily`**
（三个文件里的 `join` 全是 Python/JS 的 `.join()` 字符串拼接）；`pct_change` 本身就存在
L2 表里，不靠行情表补。所以「有 L2 无行情」的行不会把下游打挂。

唯一要留意的软后果：`market_moneyflow` 用 `max(trade_date)` 当「最新一天」，
行情缺失日的 L2 行会成为展示的最新日，届时榜单有资金流而无行情上下文。

**但这只是问题的一半。** 见 §2：`top100` 名单本身来自当日行情，行情缺失日它根本扫不出候选。

### Q2：非交易日与 L2 日包缺失怎么区分？

**现在区分不了，而且守卫前移后这个洞才真正被踩到。**

`market_feature_store/trading_days.py::is_trading_day_detailed` 的判定序是
① 环境变量覆盖 → ② 周末 → ③ 未来 → ④ **当日 `fact_stock_daily` 行数 ≥ `MIN_DAILY_ROWS`(3000)**
→ ⑤ DuckDB 读不到才回退工作日近似（`approximate=True`）。

第 ④ 步的坑：库**可读**但当天 0 行时，`0 >= 3000` 为假，函数返回
`(False, approximate=False)`——**自信地把同步失败的真交易日判成非交易日**，
连「这是近似值」的标记都不给。实测（真库 `db/market_feature_store.duckdb`）：

| 日期 | 星期 | `fact_stock_daily` 行数 | `is_trading_day` | `approximate` |
|---|---|---|---|---|
| 2026-09-09 | 三 | 5551 | True | False |
| 2026-09-10 | 四 | 5550 | True | False |
| **2026-09-11** | **五** | **0** | **False** | **False** ← 真交易日被判错 |
| 2026-09-12 | 六 | 0 | False | False（周末，正确） |

两处消费它的地方都会因此走错：

1. `scripts/moneyflow/run_l2_pipeline.sh`：判 `IS_TRADE=0` → 打印「非交易日，跳过 L2
   流水线」并 **`exit 0`**。也就是说在同步失败的日子里，L2 会「跳过并报成功」。
2. `scripts/moneyflow/write_to_duckdb.py:186`：非交易日不落 `failed`，失败被静默吞掉。

**这条必须与 #51 一起看**：把 L2 提到守卫之前，L2 确实被调用了，但同步失败那天
`is_trading_day` 仍会判错，于是 L2 静默 `exit 0`。**顺序修好 ≠ 那天就有数据了。**
本次补 9-11 是靠 `L2_FORCE_TRADE_DAY=1`（判定序第 ① 步的逃生口）绕过去的。

建议（未做，另立单）：`is_trading_day` 要能分辨「0 行是因为非交易日」与「0 行是因为
没同步」——工作日 + 当天 0 行 + 邻近交易日有数据时，至少该回 `approximate=True`
而不是 `(False, False)`，让调用方 fail closed 而不是静默跳过。

### Q3：挂账暂停开关还在不在路径上？

**不在，而且是有意的，不是欠账。**

装机副本自己写着：「源是闲鱼日包（百度分享），不再打 ClickHouse，也不再认
`l2-paused.flag`」。同一句话也出现在**主检出树的未提交改动里**
（`git status` 显示该文件为 `M`）——即闲鱼日包迁移是一条**尚未合入的在途工作**，
装机副本跟的是它，不是 `gitea/main`。

所以这不是「装机副本落后」，而是**仓与生产在这块已经分叉**：`gitea/main` 仍保留
`L2_PAUSED_FLAG`，生产没有。本次补丁刻意**不**把挂账开关带进装机副本
（详见 §3）。这条分叉本身该收口，但要由 L2 迁移那条线的负责人决定往哪边收，
不在本单顺手改。

## 2. 把工单前提证伪掉的发现

工单 §0 的前提是「L2（资金流）不依赖同步段产物」。实测**只对一半成立**
（`scripts/moneyflow/process_l2_archive.py:189-190`）：

```python
limitup = duck_limitup_codes(prev)            # 用【前一交易日】的涨停名单
top100  = duck_top_turnover_codes(date, n=TOP_N)  # 用【当日】成交额排名 → fact_stock_daily
```

- `limitup` 只依赖**前一日**，所以同步失败当天照样扫得出来 → **这半确实独立**。
- `top100` 是**同日硬依赖**：当日行情没入库，候选名单为空，`write_to_duckdb.py` 的
  `_require_valid_stats` 会以 `input_count=0, no candidates scanned` 判 failed。

9-11 实测正是这样：`2026-09-11 prev=2026-09-10 limitup=33 top100=0`。

**结论**：#51 的修复方向没错（limitup 半边与逐笔日包的转存/解包都能救回来），
但「L2 与同步完全独立」是过强的说法。行情缺失日的 L2 **天然只能补一半**，
另一半必须等当日行情入库后重跑。

## 3. 装机副本补丁（#51 验收 5）

对象 `/Users/a77/.local/bin/nightly_full_review.sh`（finalize 的 launchd
`ProgramArguments` 指向它，**不是仓内文件**——所以 PR #739 合入本身不改变夜跑行为）。

备份：`nightly_full_review.sh.bak-pre-l2order-20260912211157`（同目录）。

**外科式**：只把 `run_l2_branch` 及其结算挪到守卫之前，**刻意保留**该副本与仓内源的
既有差异——moneyflow 根用 `$DATA_ROOT`、无 `L2_PAUSED_FLAG`、无三处
`skip_method_flywheel` 留痕。**没有跑安装脚本整份覆盖**（那会抹掉闲鱼日包迁移的在途状态）。

`zsh -n` / `bash -n` 均通过。干净 shell 真跑验证（沙箱根 + 假 python / 假 moneyflow /
假 osascript 记录谁被调用，`zsh -x` xtrace 查有无嵌套 S7）：

| 用例 | 退出码 | L2 跑了 | 生成段跑了 | 调用 S7 |
|---|---|---|---|---|
| 守卫失败 rc=1 | 1 | **是** | 否 | 否 |
| 守卫通过 rc=0 | 0 | 是 | 是 | 否 |
| 守卫过但 L2 失败 | 1 | 是 | 否 | 否 |

**反向对照**（证明不是空过）：拿补丁前的备份跑「守卫失败」同一用例 →
`rc=1，L2 跑了=否`。补丁前确实被连坐，补丁后不再被连坐。

## 4. 补数读数（#51 验收 6）

`run_l2_pipeline.sh <date>`，生产口径（`FINANCE_DATA_ROOT` = 主检出树，因为装机副本
用的就是它）。

| 日期 | limitup | top100 | quant | 结果 |
|---|---|---|---|---|
| 2026-09-10 | 48 | 100 | 38 | ✅ 完整（`ops_pipeline_run_daily` 三步均 complete） |
| 2026-09-11 | 33 | **0** | 未写 | ⚠️ **半补**：top100 `failed`（`input_count=0, no candidates scanned`） |

- 9-11 需 `L2_FORCE_TRADE_DAY=1` 才跑得起来（原因见 Q2）。
- 9-11 首次转存报 `share/transfer failed errno=4`，**重试即成功**（`async=1`，
  `ensure_transferred` 对「已在 inbox」幂等跳过）。别把这个 errno 当成日包缺失。
- 失败**已如实记账**，不是静默绿：`ops_pipeline_run_daily` 有
  `2026-09-11 / l2-moneyflow / top100 / failed`。
- `ops_sync_run` 佐证 9-11 根本没有同步记录（最后一条成功是 9-10 22:17 的手动补跑）。

**9-11 的 top100 与 quant 仍欠着**，要先把 9-11 的行情补进 `fact_stock_daily`
（走 `/daily-full-review` 或 `duckdb-backfill`，有副作用、需人工发起），再重跑
`run_l2_pipeline.sh 2026-09-11`。

## 5. 仍未闭合

1. **9-11 行情未补** → 连带 9-11 的 L2 top100 / quant 补不了。
2. **`is_trading_day` 的误判未修**（Q2）：下一个「同步失败的交易日」仍会让 L2 静默
   `exit 0`。顺序修复挡不住它。建议另立单。
3. **仓与生产在 L2 挂账开关上的分叉未收口**（Q3）：闲鱼日包迁移仍是主检出树里的
   未提交改动，装机副本跟着它走。
4. 生成段代码根 → 工单 #50（未开分支）。
