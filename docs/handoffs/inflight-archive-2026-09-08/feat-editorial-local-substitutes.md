# feat/editorial-local-substitutes

## 这个分支做什么
用户（2026-09-07 18:53）：「编辑层做自家替代版，fupanhui 可以做对照…要检查下质量是否能和之前对齐」。本分支：

1. **编辑层自家替代版** `compute-market-editorial-local`（`compute_local_stats.compute_market_editorial_local`）：
   - 强度：涨幅前 5% 个股（不含北交所、剔停牌）的均涨幅 / 成交额 / 占沪深总额比 / 与昨日强度额的边际；`strength_source='local:top5pct'`。
     fupanhui 的 "top5" 集合没逆向出来（按阈值、按前 N 只都对不齐），这是**自家口径**，15 日对照均涨幅相对误差中位 1.8%。
   - 强度状态阈值 2/5/8（冰点/正常/强势/沸点）：从 fupanhui 405 个有标签日反推，一致率 99.75%。
   - 量能状态四档（85/100/120）：247 个当前口径日一致率 100%。冰点 JSON：量能比分区 78/85/95（fupanhui JSON 自述），不做周期资格判断。
   - **周期阶段留空**：价格趋势规则粗粒度（上行/下行/横盘）一致率只 58%，不放进日报标题。405 个有标签日可作训练集另立单。
2. **新高名单** `compute-stock-high-local`：`fact_stock_high_daily` 按日内最高价 `high` 判 20/60/120 日、1/2/3 年、历史新高（primary = 最长周期）。
   与 fupanhui 前复权口径差 ~12%（只作参考）。日报有 5 处读这张表。
3. 两步进 `plans.local`（market-overview-local 之后、features 之前）；same-day gate 在 local 下重新检查 `strength_*`。
4. **申万实时成交额单位修复**：akshare `index_realtime_sw` 是百万元、hist 是亿；realtime 分支 `/100`。09-07 的 31 行已用修复后口径重写
   （全A/申万 成交额比 0.0102 → 1.0218）。
5. `qa_backfill_align.py --plan`（对齐检查按计划裁剪表/字段）；`qa_local_vs_fupanhui.py` 新增编辑层对照段。

## 质量对齐读数（生产库）
- 09-07 `qa_backfill_align.py 2026-09-07 --plan local`：行数/来源/链式/量纲/板块覆盖对齐；剩余差异：`fact_sector_period_rank_daily` 10/40（等 09-03/09-04 补齐后重算）、
  9 只 mootdx 停牌占位行 amount=0（东财快照不写停牌股，口径差异，不是缺数）、`turnover` 由 99% 空→0%（东财快照现在带换手率，是改善）、
  成分表 `fund_flow_*` 全空（资金流无源，已知）。
- 双轨 08-13～09-02：十族 PASS、坏底数据日 无；编辑层：强度均涨幅误差中位 1.8%、强度状态 14/15、量能状态 15/15。
- 09-07 `check_daily_review_data --plan local` → COMPLETE（含 strength 字段）。
- 门禁：ruff 绿；pytest 见 PR；`registry-check` 通过。

## 验收标准
1. `compute-market-editorial-local --trade-date 2026-09-07` 幂等重跑读数不变；`fact_market_daily` 09-07 `strength_source='local:top5pct'`、`market_stage IS NULL`。
2. `SELECT COUNT(*) FROM fact_stock_high_daily WHERE trade_date='2026-09-07'` = 373，`source='local:high-ohlc'`。
3. `qa_local_vs_fupanhui.py --start 2026-08-13 --end 2026-09-02` 编辑层段：强度状态一致 ≥13/15，量能状态 15/15。
4. `pytest tests/test_compute_local_stats.py`（8）+ `tests/test_sync_akshare_sw_l1_daily.py`（4）通过。
5. `SELECT SUM(amount) FROM fact_sw_l1_daily WHERE trade_date='2026-09-07'` ≈ 1.9 万亿（不是 190 万亿）。

## 不在本单
周期阶段建模；主线题材 / keywords / 核心个股替代版；名单换源；北交所 hist kline 进 CLI；08-12 北交所东财快照 close 疑似有误。
