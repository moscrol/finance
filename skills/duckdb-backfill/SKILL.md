---
name: duckdb-backfill
metadata:
  pattern: tool-wrapper
  also: [pipeline]
description: "DuckDB market_feature_store 历史日回补与验收。触发：断档回补（某天/几天的复盘没抓、夜跑失败补数）、回补 duckdb、补单表缺口、修 fact_* 覆盖、fupanhui 429 后续跑、验收回补是否与基线对齐。当日全量复盘走 daily-full-review。"
---

> 红线在前；模块顺序、命令、已知语义坑见 `references/backfill-runbook.md`。

# DuckDB 历史日回补（duckdb-backfill）

## 红线（违反任一条 = 该日回补作废重来）

1. **历史日只用日期参数化源。** `daily-full` / `daily-update` / `sync-stock-daily-snapshot`（东财快照）/ `sync-sw-l1-daily` 的 realtime 分支是「取最新」语义，只在交易日当天盘后写；写到历史日 = 把今天盘中价写成那天收盘（2026-09-07 两张表同时中招）。历史日的源：个股 mootdx `sync-stock-daily`（北交所缺口用东财 hist kline）、申万 `index_hist_sw`、复盘会各模块带 `--trade-date`。
2. **fupanhui 配额是全机共享的单一资源。** 同一时刻一个写者、一个探针（多个 agent 同时抓 = 同一份配额）；板块日线用 `sync-sector-daily-local`（0 请求，回测误差 0.001%）；成分 `sync-sector-stocks` 用 `chunk=1 sleep>=1.0`。收到 429 立刻停手，按 `retry-after` 静默到期再单发探针——09-07 二次突发后被报价 `retry-after=251318s`（≈2.9 天），密集探测续期惩罚。
3. **日历行最后写。** `fact_market_daily` 当日行一落库就进 `check-daily` 的 20 日日历；GAP_TABLES 齐了才跑 `sync-market-overview` / `sync-index-daily` / `sync-market-deviation`，否则当晚 cross-day-gate FAIL、S7 不换名，好数据也进不了生产库。
4. **每步写完回读值，不数行。** `sync-market-overview` 撞 429 会把整行写成 NULL 仍 rc=0；`sync-limit-advance` 0 行也报 ok。回读用第 8 步的 `qa_backfill_align.py`。
5. **写锁。** 开工 `python3 scripts/check_db_lock.py`；18:30 前释放（S7 `probe_no_active_writer` 拒开工）。DuckDB 写是本地状态，不提交 `*.duckdb` 与 exports，源码改动分开提交。

## 标准流程（历史日 D；多日时逐日做完再做下一日，后一日的边际量依赖前一日全量板块额）

| 步 | 做什么 | 完成判据 |
|---|---|---|
| 0 | `git status --short && git branch --show-current && git worktree list`；`python3 skills/duckdb-backfill/scripts/audit_coverage.py` | 说得出缺哪几张表、哪几天 |
| 1 | 单发探针 `GET /api/v1/client/reviews/latest-date`；429 → 记 `retry-after`，静默 | 状态码非 429 |
| 2 | 不吃配额的两张先做：mootdx `sync-stock-daily --start-date D`（北交所缺口东财 hist kline）；`sync-sw-l1-daily` hist 模式 | `fact_stock_daily` ≥ 基线 98%；申万 31 行且 `pre_close` = 前日 `close` |
| 3 | 复盘会轻表，按 runbook 顺序：sectors → mainline-daily → mainline-sector-daily → theme-flow-daily → limit-heat → limit-advance → stock-high → public-assets `--plan full` | 每表回读：行数 > 0 且价格/涨幅/成交额非空 |
| 4 | `sync-sector-stocks` 逐板块（`chunk=1 sleep=1.0 only_missing`），断点续跑到等于宇宙数 | `fact_sector_stock_daily` 覆盖 = `fact_sector_universe_daily` 板块数 |
| 5 | `sync-sector-daily-local --trade-date D` | 板块日线 = 宇宙数；与 `ops_sector_search_payload_daily.pct_chg` 逐板块一致 |
| 6 | 头部：`sync-market-overview` → `sync-index-daily` → `sync-market-deviation`；回读 `total_amount` / `advancers` | 非空；空壳则退避后重跑 |
| 7 | `python3 -m scripts.compute_features --trade-date D` | 派生层五张表都有当日行 |
| 8 | 验收四件（下节） | 四件全绿 |

## 验收交付物（四件，缺一不收）

验收方独立复算每一件，不抄执行方数字；四条命令的**原始输出**贴进 `docs/handoffs/inflight/<分支>.md`。

1. `python3 scripts/check_daily_review_data.py D --phase data` → `RESULT: COMPLETE`
2. `python3 -m market_feature_store.cli check-daily --trade-date D --json skills/daily-full-review/state/quality-D.json` → `"ok": true`
3. `python3 skills/duckdb-backfill/scripts/qa_backfill_align.py D [--json …]` → `RESULT: PASS`（只读零网络；WARN 逐条说明为什么可接受）
4. 双红名单：第 3 件输出的 `double-red` 行

第 1、2 件回答「有没有」，第 3 件回答「像不像基线」：行数、来源语义、`pre_close`/`pct_chg` 链、金额量纲、字段空值、板块 payload 对账、日历副作用。三者缺任一都出现过「行数全对、值是空壳」的静默降级。

## local 计划：不发任何 fupanhui 请求的日更 / 补日链路（2026-09-07 起）

fupanhui 账号风控后的生产链路。`run_review_sync.py --date D --plan local`（或逐步 `--only`）：

`stock-daily`（东财快照，仅当日）→ `index-daily` → `sw-l1-daily` → `carry-forward-universe`（名单冻结：把最近一份
published 宇宙按当日重发，provider=`local:carry`）→ `stitch-sector-stocks --max-baseline-age-days 180`（最后一份 fupanhui
成分 × 当日东财真值）→ `sector-daily-local` → `compute-limit-stats-local`（题材涨停/明细/连板/龙头，不计 ST）→
`compute-market-overview-local`（沪深总额/涨家数/涨跌停/量能/前三行业/新高家数/周均线）→
`compute-market-editorial-local`（编辑层自家替代版：强度=涨幅前 5% 个股、强度状态 2/5/8 阈值、量能状态四档、冰点 JSON）→
`compute-stock-high-local`（新高名单，按日内最高价）→ `features`。

- 历史日补数同一条链，个股用 mootdx（`sync-stock-daily --start-date D --end-date D`），不用东财快照。
- **顺序按日串行**：后一日的板块边际量用前一日全量板块额，09-03 没补完不要跑 09-04。
- 名单没抓全的那天（identity 变了、成分 0 行，如 2026-09-03）用 `carry-forward-universe --supersede --base-date <最后完整日>`
  冻回最后一份完整名单，原快照留 `superseded`；否则 stitch 把变动板块留给已不存在的 provider。
- `sector-daily-local` 对无成分板块 fail closed（不把「没抓到」写成 0）。北交所个股缺行会让 BJ 密集的小板块整块 pending
  （09-03/09-04 各 9 个），先补齐个股再跑。
- 门禁带 `--plan local`：期望表由 `consumption_registry.tables_for_plan('local')` 派生，fupanhui 独有的表（主线×3、资金流、
  新高、公开资产）和 `strength_*` 字段不算缺。cross-day `check-daily --plan local` 同理。
- 编辑层替代版与 fupanhui 历史对照（15 日）：强度均涨幅相对误差中位 1.8%、强度状态一致 14/15、量能状态一致 15/15；新高名单按裸价
  `high`，与 fupanhui 前复权口径差 ~12%。这些是**自家口径**，fupanhui 值恢复可读时只作对照（`qa_local_vs_fupanhui.py` 编辑层段）。
- 仍留空：**周期阶段 `market_stage`**（价格趋势规则粗粒度一致率仅 58%，不进日报标题；405 个有标签日可作训练集另立单）、
  主线题材、summary/keywords、核心个股、资金流。

## 剥离 fupanhui：双轨切换门（2026-09-07 起）

定位：fupanhui 是**参照源**，不是抓取源头。加工字段用自己的底数据（东财/mootdx 个股、申万官方）按公开规则算，
`scripts/qa_local_vs_fupanhui.py` 每天把自算值和库里的 fupanhui 值逐日比，某族读数连续稳定在门内才把该族的源切到本地。
规则口径与实测读数见 runbook「自算口径（双轨实测）」。

- 已对上（08-14～09-02 十四个干净日全部过门）：涨家数、沪深成交额、涨停/跌停家数、量比/MA20/量能比、前三行业、
  板块涨停数、涨停明细、连板 boards、龙头高度。
- 只出读数不设门：新高（要 OHLC，本 skill 的 `sync-stock-daily --ohlc-only` 补）、市场强度 top5（定义未知）。
- 自算不了、只能低频参照或自定义：板块分类与成分（名单）、周期阶段、主线题材、summary/keywords、核心个股、资金流类。

```bash
python3 skills/duckdb-backfill/scripts/qa_local_vs_fupanhui.py                      # 最近 15 个完整日
python3 skills/duckdb-backfill/scripts/qa_local_vs_fupanhui.py --start D1 --end D2 --json /tmp/dt.json
```

脚本会把「底数据坏日」（我们的沪深成交额与 fupanhui 差 >10%）单列并剔出统计——那是回补问题，按本 skill 用
`sync-stock-daily --start-date D --end-date D --refresh` 重抓那一天。

## 只读审计与 QA 脚本

- `scripts/audit_coverage.py`：按 `fact_market_daily` 日历审各 fact 表覆盖缺口。
- `scripts/qa_backfill_align.py`：目标日 vs 最近 N 个完整日基线逐项对齐（只读、零网络、可验 staging `--db`）。
- `scripts/qa_local_vs_fupanhui.py`：自算 vs fupanhui 双轨对账（只读、零网络），剥离切换门。
- `scripts/verify_backfill.py`：题材表完整性 + 抽样回源对账（吃配额，429 期间不跑）。
- `scripts/qa_fupanhui_public_assets.py`：公开资产结构门 + API 抽查。
- `scripts/run_missing_dates.py` / `run_stock_high_missing.py`：按缺失日逐日跑的驱动器，带超时、skip 文件、连续失败阈值。

## CDP proxy 前置

`sync-sectors`、`sync-market-overview`、`sync-market-deviation`、`sync-sector-daily`、`sync-limit-heat`、`sync-stock-high`、`sync-limit-advance` 走 CDP proxy（`localhost:3456`，携带 Chrome 里的 fupanhui 登录态）：

```bash
cat ~/Library/Application\ Support/Google/Chrome/DevToolsActivePort   # Chrome 已开 remote debugging
node ~/.claude/skills/web-access/scripts/cdp-proxy.mjs                 # 启动
curl -s http://localhost:3456/targets                                   # 验证
```

## 复盘会公开资产（2026-08-13 起）

十类公开 API 资产（keywords/相似日/龙头高度/外盘/龙虎榜/监管/核心个股/竞价/事件/研报目录/题材挖掘）由 `sync-fupanhui-public-assets` 一步同步，无需 CDP。

```bash
python3 -m market_feature_store.cli sync-fupanhui-public-assets --align --sleep 0.2          # 按其它日表窗口补缺口
python3 -m market_feature_store.cli sync-fupanhui-public-assets --align --only leader_height --refresh
python3 skills/duckdb-backfill/scripts/qa_fupanhui_public_assets.py                          # 结构门 + API 抽查
python3 skills/duckdb-backfill/scripts/backfill_dragon_seats_full.py --start-date 2025-01-02 --end-date 2026-05-19
```

三条硬约束（实测事故换来的）：外盘/核心股等主键 = 请求的 A 股日历日，不信接口回写的 `trade_date`；龙头高度按请求日 as-of UPSERT，趋势图历史点只填洞；验收对源头抽查，不只数行数。恒定宇宙（core 50 / global_index 5 / global_stock 194）已进 `check_daily` 断档 + 行数收缩门禁；auction / events / mapping / regulation_event 天然稀疏，靠 ops `empty` 台账区分「接口没有」和「没同步」。

## 收尾对齐（新表/新列入库后逐条过）

1. **门禁**：稳定每日有的表进 `market_feature_store/quality.py` 的 `GAP_TABLES`；宇宙恒定的再进 `ROW_ANOMALY_TABLES`。棘轮：历史空的先补齐再进门禁。
2. **消费层**：在 `intelligence/services/finance_query.py` 的 `_DATASETS` 注册成 dataset，否则 agent 够不着（2026-08-13 实测龙虎榜等入库多轮但从未注册）。暂不注册要在收尾里写明原因。
3. **质检**：对源头抽查对账，不只 `COUNT(*)`。

## Iteration rule

回补路径一旦挂起、报假成功、或需要人工救援：**先改本 skill 或 runbook，再继续**。教训写进 `references/backfill-runbook.md`「已知语义坑」和本文红线——交接记录不会被下一个 agent 开工时读到。
