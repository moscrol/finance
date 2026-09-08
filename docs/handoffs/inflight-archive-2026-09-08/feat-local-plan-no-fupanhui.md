# feat/local-plan-no-fupanhui

## 这个分支做什么
fupanhui 账号风控（2026-09-07 17:49 用户：「我们只能自己处理数据了」）后的日更链路：**`--plan local`，不发任何 fupanhui 请求**。

- `market_feature_store/sync/compute_local_stats.py`（新）
  - `carry_forward_universe`：名单冻结——最近一份 published 宇宙按当日重发，provider=`local:carry`；`--supersede/--base-date`
    用于名单没抓全的那天（09-03 的 fupanhui 快照 22 个板块 expected 变了但成分 0 行），跨 provider 的旧 published 显式标 superseded。
  - `compute_limit_stats_local`：题材涨停热度 / 涨停明细 / 连板梯队 / 龙头高度。口径 = 双轨实测：沪深涨停价四舍五入、
    **北交所向下取整**，**不计 ST**、新股、停牌。只在当日无非 local 来源行时写（fupanhui 历史值不覆盖，`--force` 才覆盖）。
  - `compute_market_overview_local`：沪深总额（不含北交所）/ 涨家数 / 涨跌停 / 量比昨日 / MA20（含当日）/ 量能比 / 前三行业
    （申万份额）/ 新高家数（`high` 列，前复权口径差 ~12%，只作参考）/ 周均线偏离（`ma_recompute`）。不碰周期阶段、强度、summary。
- CLI：`carry-forward-universe`、`compute-limit-stats-local`、`compute-market-overview-local`；`stitch-sector-stocks --max-baseline-age-days`。
- `SectorUniverseStore.published_snapshot(provider_source=None)`：默认取该日唯一 published 快照、不限 provider（消费方不再假设 fupanhui）。
- `consumption_registry.yaml/.py`：`plans.local`（10 步）+ 各数据族 `steps.local`；`tables_for_plan(registry, plan)`。
- `run_review_sync.py`：`build_local_plan`；`--plan` 传给两道门。`check_daily_review_data.py --plan` / `check-daily --plan`：
  期望表按 registry 裁剪，local 不查 `strength_*`。
- `sync_mootdx_stock_daily`：`--skip` 确定性分页（`--ohlc-only` 的「已抓」启发式在先补过单日的库上会把所有股票当已抓——
  今天 3 年回拉第一次就是这样一行没拉，见 runbook）。
- 双轨门 `qa_local_vs_fupanhui.py`：涨家数门放宽到 |Δ|≤10（mootdx 裸前收日）。

## 生产库读数（2026-09-07）
- OHLC 3 年历史已合入：`fact_stock_daily` 3 732 396 行，有 `high` 的 3 709 804 行，最早 2023-09-01；08-13 半日量已用 mootdx 重写（5 204 只，
  余 335 只非 mootdx 宇宙的仍是旧快照行）。
- **09-07 local 链路全绿**：stitch 403/403、板块日线 403、沪深成交额 19 451.9 亿、涨家数 3 167、涨停 93 / 跌停 2、连板 13 只、龙头 6 板、
  features 全族；`check_daily_review_data 2026-09-07 --phase data --plan local` → **COMPLETE**。
- 09-03 / 09-04：universe 已冻回 09-02 名单（原 09-03 fupanhui 快照 superseded），stitch 394/403，`sector-daily-local` fail closed
  （9 个 BJ 密集板块无成分行，缺 ~190 只北交所个股）。`/tmp/local_chain_finish_0903_0904.py` 在守：个股行 ≥5500 后自动跑
  stitch → sector-daily-local → limit-stats(--force) → overview(--force) → features → 门，再重算 09-07 边际量基准。
  北交所依赖 `/tmp/em_bj_scheduler.py`（东财 push2his，20:45 / 22:00 / 08:30 探针；16:40 那次 ConnectionError）。
- 双轨 08-13～09-02：十族全 PASS，坏底数据日 无。
- 门禁：ruff 绿；pytest **8094 passed / 77 skipped / 1 xfailed**（新增 `test_compute_local_stats.py` 5 条）；`registry-check` 通过。

## 验收标准（验收方独立复算）
1. `check_daily_review_data.py 2026-09-07 --phase data --plan local` → COMPLETE；不带 `--plan` 应 INCOMPLETE（fupanhui 独有表缺）。
2. `cli check-daily --trade-date 2026-09-07 --plan local` 在 09-03/09-04 补完后 → ok；补完前只应报这两天的 `fact_sector_daily` 断档。
3. `qa_local_vs_fupanhui.py --start 2026-08-13 --end 2026-09-02` → PASS、坏日无。
4. `pytest tests/test_compute_local_stats.py` 5 passed；`registry-check` 通过；`plan_step_names()['local']` 与 yaml 一致。
5. `SELECT provider_source, status FROM ops_sector_universe_snapshot_daily WHERE trade_date >= '2026-09-03'`：每日恰一份 published，provider `local:carry`。

## 重启用夜跑（用户决定时）
plist `REVIEW_SYNC_PLAN=local`；主树先更新到含本 PR（S7 跑主树代码）；`ops_sector_search_payload_daily` 不再有新行是设计
（sector-daily-local 走等权涨幅）。`~/.finance-runtime/launchd-disabled-20260907.md` 有重启用命令。

## 不在本单
新高前复权口径；市场强度 top5；主线/keywords/核心个股的自家替代版；名单换源（东财/同花顺）；北交所 hist kline 收进 CLI
（现在还是 /tmp 脚本）；08-12 北交所东财快照 close 疑似有误（323 只 pre_close 对不上，见 runbook 待办）。
