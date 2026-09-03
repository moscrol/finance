# 工单：L2 逐笔大单资金流回补——鉴权恢复后补 15 个交易日（P1，前置在用户）

- 状态：**待认领**，但**第一步阻塞在用户**：ClickHouse 数据源鉴权续期是供应商侧人工动作。
- 目标仓：`/Users/a77/finance-workspace-private`
- 来源：2026-08-28 欠账盘点（用户点名：「金融 repo 里要补的 L2，逐笔委托那个」）。
- 优先级：**P1**——缺口每个交易日 +1，且这是策略分析里资金流特征的唯一来源。

## 0. 一句话

Level2 逐笔资金流链路（ClickHouse `db.base32.cn` → 榜单扫描 → DuckDB `feature_l2_*` 两张特征表）因数据源鉴权失效停在 2026-08-07，08-18 起用户指示挂账（`state/l2-paused.flag`）；待凭证续期后删 flag、用 `run_l2_pipeline.sh` 按日回补 15 个交易日（08-10 ~ 08-28）。

## 1. 证据（2026-08-28 实测）

- DuckDB 只读查询：`feature_l2_capital_flow_daily`（limitup + top100 各 39 个交易日）与 `feature_l2_quant_orders_daily` 的 `max(trade_date)` 均为 **2026-08-07**。
- 缺口：`fact_market_daily` 中 08-07 之后有 **15 个交易日**（2026-08-10 ~ 2026-08-28）。
- 挂账 flag：`state/l2-paused.flag`（2026-08-18 22:00 用户指示停抓，`reason=l2-datasource-auth-pending`；文件内写明恢复方式）。
- 鉴权确实还坏着：在途交接 `docs/handoffs/inflight/docs-intraday-l2-sidecar.md` 记录 08-26 `--check-only` 探针实测 Code 516。
- 夜跑行为：`skills/daily-full-review/scripts/nightly_full_review.sh` 的 `run_l2_branch` 检测到 flag 即跳过抓取并放行 L2 质量门（summary 里留痕「L2 已挂账暂停」）——**这是刻意挂账，不是静默故障**。

## 2. 范围

**做**：① 凭证恢复验证；② 删 flag 恢复夜跑；③ 回补 08-10 ~ 08-28 全部 15 个交易日的三类扫描 + DuckDB 落库。

**不做**：不改管线代码；不做盘中/全市场逐笔扫描；不动 `docs-intraday-l2-sidecar.md` 那条盘中 sidecar 线（它依赖同一鉴权，但属另一工单域，鉴权恢复后通知其认领人即可）。

## 3. 步骤

1. **（用户动作，前置）** 供应商侧续期/取新密码 → 更新 `~/.secrets/clickhouse.env`。执行 agent 到这一步只能等，不许绕。
2. 验证鉴权：按 `docs/handoffs/inflight/docs-intraday-l2-sidecar.md` 的 `--check-only` 探针方式验证，不再是 Code 516。
   完成判据：探针返回成功码。
3. 删挂账 flag：`rm state/l2-paused.flag`（flag 文件自述的恢复方式）。
4. 按日回补（**盘后时段运行**；脚本与 daily-full-review 共享锁 `state/locks/daily-full-review.lock`，避开夜跑窗口 18:30 前后；一次一日、从旧到新）：
   ```bash
   cd scripts/moneyflow
   ../../scripts/moneyflow/run_l2_pipeline.sh 2026-08-10
   # …逐日到 2026-08-28（只跑交易日，周末自动无数据）
   ```
   ⚠ fupanhui 无关，此链路的限速红线是：逐股限速 0.3s、名单聚合分批 + 缓存，不做全市场逐笔扫描。ClickHouse 侧若限流，缩小批次或隔日续跑，游标写交接。
   完成判据（每日）：`scripts/moneyflow/outputs/` 出现当日榜单产物，DuckDB 两张表出现当日行。
5. 终验：只读查询两张表 `count(distinct trade_date)`，08-10 ~ 08-28 的 15 个交易日全部在列；当晚夜跑 summary 里 L2 段不再是「挂账暂停」。
6. 通知 `docs-intraday-l2-sidecar.md` 的认领人鉴权已恢复。

## 4. 验收

1. 两张 `feature_l2_*` 表 `max(trade_date) = 2026-08-28` 且 08-10 起无交易日空洞。
2. `state/l2-paused.flag` 已删除，夜跑恢复正常抓取。
3. 交接含：逐日回补结果表（成功/失败/重试）、ClickHouse 侧限流情况。

## 5. 红线

- 凭证只进 `~/.secrets/clickhouse.env`，不进 git、不写明文到任何仓内文件。
- `scripts/moneyflow/outputs/` 产物不提交。
- 仅盘后运行；回补期间不与夜跑/其它 DuckDB 写入并行（共享锁会自动挡，被挡到就换时段，不许删别人的锁）。
