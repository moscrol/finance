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
⑤ **东财快照 `sync-stock-daily-snapshot` 只在交易日当天盘后有效**：盘中写实时价、非交易日把上一交易日写到所传日期。
   **2026-09-07 工单 #32 更正**：这条以前只写在文档里，代码不拦，本行原来声称的「qa 脚本对 `updated_at` 日期 ≠ `trade_date` 直接 FAIL」**从未实现过**——
   07-20 / 08-06 整天被写成次日复制、08-13 北交所 335 行被写成次日 10:50 盘中价，三次都没人报警。现在三层拦：
   (a) 快照同步多请求 `f297`（行情自身交易日），与 `--trade-date` 不一致**拒写**（`SnapshotMisdated`；`--allow-misdated` 才放行且 source 标 `-misdated`）；
   (b) `qa_local_vs_fupanhui.py` 全历史扫「相邻日逐股相同 >50%」与「快照行写入时刻晚于下一交易日 09:30」，命中即 FAIL——
       **不能**按「`updated_at` 日期 ≠ `trade_date`」判：凌晨 / 周末补前一交易日是常态（07~08 月 8 天），那些行是对的；
   (c) `check_daily_review_data` data 阶段比当日与前一交易日逐股相同比例，>5% 报缺。
   历史日一律走 mootdx `sync-stock-daily --start-date D --end-date D --refresh`（北交所 mootdx std 客户端不回，用东财 hist kline 临时脚本，见上表）。
⑥ **fupanhui 限流是突发触发**：`sync-sector-daily` 一步 403 请求/29 秒必炸；二次突发后 `retry-after=251318s`。模块化 + `sector-daily-local` + 成分 1 req/s 能活；429 期间不跑 `reconcile-sector-daily` / `verify_backfill.py` 的回源抽样。

## local 计划实跑记录（2026-09-07，生产库）

| 日 | 结果 | 备注 |
|---|---|---|
| 09-07 | 生产库全链绿：stitch 403/403、板块日线 403（等权涨幅，边际量暂以 09-02 为基准）、沪深成交额 19451.9 亿、涨家数 3167、涨停 93 / 跌停 2、连板 13 只、龙头 6 板；same-day `--plan local` COMPLETE | 首个不靠 fupanhui 的完整交易日 |
| 09-03 / 09-04 | stitch 394/403，`sector-daily-local` fail closed（9 个 BJ 密集板块无成分行） | 等东财 hist kline 补齐 ~190 只北交所后重跑 stitch → sector-daily-local → limit-stats(--force) → overview(--force) → features |

坑：`fact_sector_daily` / `fact_sector_stock_daily` 是只暴露 **published** 代际的 VIEW。`carry-forward-universe --supersede`
顶替某日快照后，挂在旧快照上的板块日线/成分行会从视图里消失（代际表还在）；必须紧接着把该日重新派生完，否则那天在视图里是空的。

## 自算口径（双轨实测，2026-08-14～09-02 十四个干净日）

`qa_local_vs_fupanhui.py` 用的规则，也是各族切到本地源时的实现口径：

| 字段 | 规则 | 实测 |
|---|---|---|
| 涨家数 | `COUNT(pct_chg > 0)` 全A | 13/14 日 \|Δ\|≤2 |
| 成交额 | 全A **不含北交所** 的 `SUM(amount)` | 比值 0.9996~1.0010 |
| 涨跌停板幅 | 北交所 30%、创业(30x)/科创(68x) 20%、其余 10%；**ST 现行也是 10%** | 按 5% 会多报 5 只/日 |
| 涨停价取整 | 沪深：四舍五入到分（tie 434/451 向上）；**北交所：向下取整到分**（40/40；16.25×1.3=21.125→21.12） | 用 round 会漏北交所连板 |
| 涨停统计口径 | 不计 ST、不计新股（名字 N/C 开头）、不计停牌（amount=0） | fupanhui 明细 0 只 ST；剔后板块一致率 91.7%→97.9% |
| 量能 | 量比昨日 = 今/昨−1；MA20 **含当日**；量能比 = 今/MA20×100 | 三项逐日一致 |
| 前三行业 | 申万一级成交份额 top3 | 名次 14/14，占比差 ≤0.85pp |
| 连板 boards | 连续收盘涨停天数（同上取整规则） | 150/150 |
| 龙头高度 | 当日 max(boards) | 14/14 |
| 新高 | 日内最高价 `high` > 前 N 日最高；primary 取最长周期 | high 口径 20 日相对误差中位 ~12%（fupanhui 用前复权） |
| 市场强度 | **自家口径**：涨幅前 5% 个股（不含北交所）均涨幅/成交额/占比；状态阈值 2/5/8（冰点/正常/强势/沸点） | 均涨幅误差中位 1.8%；状态 14/15；阈值口径对 405 日 99.75% |
| 量能状态 | 量能比 <85 缩量观望 / <100 正常量能 / <120 主线抱团 / ≥120 放量突破 | 247 个当前口径日 100% |
| 冰点 | 量能比 <78 极冰 / [78,85) 接近冰点 / [85,95) 偏冷 / 其余正常；不做周期资格判断 | fupanhui JSON 自述分区 |
| 周期阶段 | 自训逻辑回归 v1（30 个价格/量能/广度特征，滞回 0.15） | 分块 5 折精确 43.7% / 粗 55.1%；写 `market_stage_source/confidence` |
| 主线题材 | 人气值 = 20 日涨幅×2 + 5 日涨停数 + 5 日均额×0.5 + 5 日双红×0.5，前 4 题材 | fupanhui 主线板块在 20 日涨幅 72 分位、当日涨幅 50 分位、61% 有涨停；Jaccard 0.28（其 14 题材内 0.47） |
| 申万实时成交额 | akshare `index_realtime_sw` 是百万元，hist 是亿；realtime 分支 /100 | 09-07 实测 电子 506527 ↔ 5065 亿 |

底数据坏日的形状：2026-08-13 东财快照写在 08-14 01:53，成交额是次日的 53%（半日量），涨家数差 600。
这类日子 `qa_local_vs_fupanhui.py` 会标出来，用 `sync-stock-daily --start-date D --end-date D --refresh` 重抓。

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
# 给已有东财日线补 open/high/low/volume、拉 3 年历史：只填 OHLC，不碰东财行的收盘/昨收/涨幅/名字（可 --limit 分批续跑让锁）
python3 -m market_feature_store.cli sync-stock-daily --start-date 2023-09-01 --offset 800 --ohlc-only --limit 300 --sleep 0.1
# 重抓东财快照写坏的单日（如 2026-08-13 半日量）：区间掐成一天 + --refresh
python3 -m market_feature_store.cli sync-stock-daily --start-date 2026-08-13 --end-date 2026-08-13 --offset 30 --refresh
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
