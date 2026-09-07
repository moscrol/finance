# duckdb-backfill 回补 Runbook

> 本文件由 `skills/duckdb-backfill/SKILL.md` 外置（ADK Reviewer/Generator 模式：检查内容与检查方式解耦 + 渐进披露）。红线与验收四件在 SKILL.md；这里是模块顺序、命令、已知坑。

## 历史日回补：模块清单与顺序（2026-09-07 定形）

单日 D 的完整清单。顺序有两条硬依赖：成分（4）先于本地板块日线（5）；头部（6）在 GAP_TABLES 齐之后（日历行最后写）。多日按日串行，后一日的 `diff_ratio` 依赖前一日全量板块额。

| 步 | 模块 | 命令（均 `python3 -m market_feature_store.cli …`） | 源语义 | fupanhui 请求 |
|---|---|---|---|---|
| 2 | 全A日线 | `sync-stock-daily --start-date D --offset 4`（mootdx 逐只 TCP；北交所常只回 ~150/340 只）；北交所缺口用东财历史 K 线 `push2his.eastmoney.com/api/qt/stock/kline/get`（`klt=101 fqt=0`，逐只 ≥4s 节流，`source='eastmoney:hist_kline'`）——**仓内暂无 CLI**，09-07 用的是临时脚本，收进 `market_feature_store/sync/` 是待办 | 日期参数化（mootdx 裸收盘，见坑③） | 0 |
| 2 | 申万一级 | `sync-sw-l1-daily --trade-date D`（hist 模式；坑①） | `index_hist_sw` 日期参数化 | 0 |
| 3 | 板块宇宙 | `sync-sectors --trade-date D` | 发布快照 + `ops_sector_search_payload_daily`（有 pct_chg/strength/stock_count，**无 amount**） | 1 |
| 3 | 主线 | `sync-mainline-daily --trade-date D` → `sync-mainline-sector-daily --trade-date D` | 公开 API | ~2 |
| 3 | 题材资金流 | `sync-theme-flow-daily --trade-date D` | 公开 API | 1 |
| 3 | 涨停题材 | `sync-limit-heat --trade-date D` | CDP | ~2 |
| 3 | 连板晋级 | `sync-limit-advance --trade-date D`（0 行也报 ok，回读 `fact_limit_advance_daily`） | CDP | 1 |
| 3 | 新高 | `sync-stock-high --trade-date D --page-size 200` | CDP | ~5 |
| 3 | 公开资产 | `sync-fupanhui-public-assets --trade-date D --plan full` | 公开 API | ~10 |
| 4 | 板块成分 | `sync_fact_sector_stock_daily(trade_date=D, only_missing=True, chunk=1, sleep=1.0)`，跑到 = 宇宙数 | fupanhui | 403（1/s） |
| 5 | 板块日线 | `sync-sector-daily-local --trade-date D` | 本地聚合成分 + payload | 0 |
| 6 | 市场总览 | `sync-market-overview --trade-date D --days 60`，回读 `total_amount`/`advancers`（坑②） | reviews/market+summary+cycle | 3 |
| 6 | 上证日线 | `sync-index-daily --trade-date D` | akshare | 0 |
| 6 | 周均线/偏离 | `sync-market-deviation --trade-date D`（CDP hover 偶发失败，见下「已知问题」） | CDP | 1 |
| 7 | 派生层 | `python3 -m scripts.compute_features --trade-date D` | 本地 | 0 |

反例（都在 2026-09-07 发生过）：`cli daily-full --trade-date D` 一把跑历史日——个股写成东财盘中快照、申万写成 realtime、`sync-sector-daily` 29 秒 403 次 kline 请求触发 429、`sync-market-overview` 第二次撞 429 把首轮的值覆写成 NULL。

## 已知语义坑（回补前必读）

① **`sync_akshare_sw_l1_daily.py` realtime 分支无条件覆盖 end 日**（`:277` 一带）：对历史日跑会把当天盘中值写成那天的收盘（09-03 的 801010 `pre_close` 变成 2695 ≠ 09-02 close 2605.47）。历史日只走 `index_hist_sw`；验收看 `pre_close(D) == close(D-1)` 31/31。
② **`sync_fupanhui_market_daily.sync_fupanhui_market_overview` 空响应写空壳**：只检查响应是 dict，429 错误体也是 dict → 全字段解析成 None，`OVERVIEW_UPSERT_SQL` 无 COALESCE 整行覆写，rc=0。写完回读 `total_amount`/`advancers`；空则退避后重跑。
③ **mootdx `sync-stock-daily` 默认 `qfq=False`**：`pre_close` = 前一根裸收盘，除息日 `pct_chg` 含股息缺口（东财快照的 `pre_close` 已做除息调整，每日约 0.1–0.2% 行 `pre_close ≠ 前收`，mootdx 行是 0%）。`stock_name` 来自 TDX 定长字段，三字名带 `\x00` 填充（`sync_mootdx_stock_daily.py` 写入前需 `rstrip('\x00')`）。qa 脚本对两者分别 WARN / FAIL。
④ **`check-daily` 的 20 日日历 = `fact_market_daily` 最近 20 行，不受 `--trade-date` 约束**：历史日一旦有了 `fact_market_daily` 行而 GAP_TABLES 未齐，当晚 cross-day-gate 连坐 FAIL → `run_review_sync` rc=1 → S7 不换名。头部模块最后跑。
⑤ **东财快照 `sync-stock-daily-snapshot` 只在交易日当天盘后有效**：盘中写实时价、非交易日把上一交易日写到所传日期。qa 脚本对「`source='eastmoney:snapshot'` 且 `updated_at` 日期 ≠ `trade_date`」直接 FAIL。
⑥ **fupanhui 限流是突发触发**：`sync-sector-daily` 一步 403 请求/29 秒必炸；二次突发后 `retry-after=251318s`。模块化 + `sector-daily-local` + 成分 1 req/s 能活；429 期间不跑 `reconcile-sector-daily` / `verify_backfill.py` 的回源抽样。

## Backfill order（多日/大窗口）

1. **Calendar/base facts**
   - `audit_coverage.py` 按 `fact_market_daily`（`total_amount is not null`）日历列缺口。
   - 先补 `fact_stock_daily` / `fact_sw_l1_daily`（不吃配额），再补复盘会侧。
   - 单日 `fact_stock_daily` 增量优先用东财快照 `sync-stock-daily-snapshot`（秒级，**仅当天**）；补历史区间用 mootdx `sync-stock-daily`（见下「单日快照 vs 历史 mootdx」）。
2. **Light tables**
   - `sync-sw-l1-daily` by 45-60 day windows.
   - `sync-limit-advance-range` by quarters; validate `fact_limit_advance_presence`.
3. **Medium table**
   - `stock_high` should run as single-day commands or via `scripts/run_stock_high_missing.py`; avoid silent long range jobs.
4. **Heavy/hang-prone tables**
   - `limit_heat` and `sector_stock` need progress output and timeouts. Use tiny smoke tests first.
   - Do not run all-history `sector_stock` without a resumable per-sector/per-date plan.

## 全A日线 fact_stock_daily：单日快照 vs 历史 mootdx

两条取数路径，按场景选：

- **单日盘后增量 → 东财全市场快照（快，默认）**：`sync-stock-daily-snapshot`。分页拉全 A（约 6 千只，东财单页上限100、约60页）当日 收盘/涨跌幅/昨收/成交额，数十秒写完。`daily-full`/`daily-update` 默认 `--stock-source snapshot` 就走这条，避免 mootdx 逐只 TCP 的十几分钟长尾（个别股超时各卡几分钟）。仅取当日，必须**盘后**、且显式传 `--trade-date`（盘中会写实时价、非交易日会把上一交易日数据写到所传日期）。
- **历史多日回填 → mootdx 逐只（慢，可拉区间）**：`sync-stock-daily --start-date ... --offset N`。快照接口只给当日截面，补历史区间仍必须用 mootdx。`daily-full --stock-source mootdx` 可强制日更也走 mootdx（受 `--skip-long` 控制）。

两条路径同 schema/口径（amount 存「亿」、close 不复权、turnover 留空）；快照 `source='eastmoney:snapshot'`，mootdx `source='mootdx'`。

## Useful commands

```bash
python3 skills/duckdb-backfill/scripts/audit_coverage.py
python3 -m market_feature_store.cli info
python3 -m market_feature_store.cli check
python3 -m market_feature_store.cli sync-sw-l1-daily --trade-date YYYY-MM-DD --days 60
python3 -m market_feature_store.cli sync-limit-advance-range --start-date YYYY-MM-DD --end-date YYYY-MM-DD --sleep 0.1
python3 skills/duckdb-backfill/scripts/run_stock_high_missing.py --max-days 5 --timeout 180 --max-failures 2 --record-failures
# 全A日线：单日盘后增量（东财快照，秒级）
python3 -m market_feature_store.cli sync-stock-daily-snapshot --trade-date YYYY-MM-DD
# 全A日线：历史区间回填（mootdx 逐只，慢）
python3 -m market_feature_store.cli sync-stock-daily --start-date YYYY-MM-DD --offset 180
# 一键复盘强制用 mootdx 跑全A日线（默认 snapshot）
python3 -m market_feature_store.cli daily-full --trade-date YYYY-MM-DD --stock-source mootdx
```

## Current known state from 2026-06-20

Calendar baseline: `calendar_with_amount` 352 trading days, `2025-01-02` ~ `2026-06-18`.

- **Complete (missing=0)**: `fact_sector_daily` (357 dates), `fact_sector_stock_daily` (352), `fact_stock_daily` (352), `fact_stock_high_daily` (352), `fact_limit_advance_presence` (352), `fact_sw_l1_daily` (354).
- **Partial**: `fact_theme_limit_heat_daily` (343 dates, 9 missing: `2025-05-27`, `2025-06-18`, `2025-07-29~31` 等), `fact_theme_limit_stock_daily` (342 dates, 10 missing).
- **Sparse by design**: `fact_limit_advance_daily` (296 dates, 56 "missing" 多为无连板数据的日期).
- Known stock-high hang dates: `2025-03-05`, `2025-03-06`.
- Known stock-high CDP 500 dates in bad proxy/API sessions: `2025-03-21`, `2025-03-24`, `2025-03-25`, `2025-04-14`, `2025-04-17`, `2025-04-18`, `2025-04-21`, `2025-04-22`, `2025-04-23`, `2025-04-24`, `2025-04-25`, `2025-04-28`, `2025-04-29`, `2025-04-30`.
- Known stock-high timeout dates after proxy ready: `2025-03-21`, `2025-03-26` timed out at 180s via `run_stock_high_missing.py`.
- Stock-high skipped dates are stored in `skills/duckdb-backfill/state/stock_high_skip.txt`; `run_stock_high_missing.py` reads this file by default and `--record-failures` appends newly failed dates.
- Known limit-heat blocker: `sync-limit-heat --trade-date 2025-01-02 --detail-chunk 3 --sleep 0.1` hung with CPU 0 and wrote no rows.
- Known sector-stock behavior: `sync-sector-stocks --trade-date 2025-01-02 --limit 20 --sleep 0.1` wrote 13 sectors / 2066 rows before termination.

## 前置检查清单（跑复盘会侧模块前）

1. **CDP proxy 已启动**：`curl -s http://localhost:3456/targets` 返回 JSON 数组
2. **Chrome 已登录 fupanhui.com**：CDP proxy 依赖 fupanhui 登录态
3. **审计当前覆盖**：`python3 skills/duckdb-backfill/scripts/audit_coverage.py`
4. **写锁空闲**：`python3 scripts/check_db_lock.py`；`ps aux | rg "daily-full|run_review_sync|sync-"` 无别的写者
5. **单发探针**：`curl -s -o /dev/null -w '%{http_code}' https://fupanhui.com/api/v1/client/reviews/latest-date`，429 就停

## 已知问题

- **sync-market-deviation tooltip 提取失败**：hover K 线图 tooltip 偶发失败。Fallback：取最近 5 个交易日上证收盘算 MA5 后 `UPDATE fact_market_daily SET sh_week_ma = <MA5>, sh_deviation_pct = <dev> WHERE trade_date = 'YYYY-MM-DD'`（`sh_week_ma_source` 记 `ma_recompute`）。
- **东财 `push2.eastmoney.com` 偶发 502**：重试可解，或 `--stock-source mootdx`。
- **swsresearch.com SSL 偶发失败**：重试可解。
