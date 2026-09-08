# 工单 #40：两处数据洞补数——`fact_market_daily` 2026-08-17 指数四列空、`fact_stock_daily` 2025-09-18/19 `pct_chg` 缺 1.3% / 21%

> 日期：2026-09-08
> 上游：PR #662 `feat/fill-rate-gate`（第四层拦截：逐列填充率闸；`fill-rate-baseline.json` 首次钉出这两处，`reason` 写「待查…此前无人知道」）；工单 #32 `2026-09-07-stock-daily-misdated-snapshot-workorder.md`（同一张表的上一轮修数：mootdx `sync-stock-daily --refresh` + fupanhui 核心 50 只当真值验收——**方法照抄**）；`docs/verification/2026-09-07-event-pricing-slice1.md`（「主库 2026-08-17 指数涨跌幅 NULL」）
> 优先级：**P1**——两处都在历史读数的路径上：08-17 那天授课框架 `index_stage`（周均线 × 偏离度）与事件定价的市场锚点都出 `gap`；2025-09-19 缺 21% 个股涨跌幅会让任何跨那天的个股类标签（`limit_up / new_high_1y` 的前瞻序列）分母悄悄少一截
> 规模：小单（半天到一天）
> 分支：`fix/data-holes-0817-20250919`
> 依赖：无代码依赖。**与 #662 协调**：本单修好后要把 `fill-rate-baseline.json` 里对应条目删掉——#662 未合则在其 PR 里留一条评论指向本单收据，合了就直接改基线
> 红线：**不编数**。补数只接受两种来源：① 重新同步原始源（mootdx / fupanhui / akshare）拿到的行；② 从**同表相邻交易日的原始字段**确定性派生且派生规则写进 `source` 列。两者都拿不到 → 留 NULL，基线条目改成「已查，源无此数」而不是删掉

---

## 0. 一句话

#662 的填充率闸第一次把两处从没人知道的洞量了出来。09-08 只读探针复核：`fact_market_daily` 2026-08-17 行**存在**（`total_amount=23857.9`、`market_stage=底部横盘阶段`、`source=fupanhui:reviews`、`updated_at=2026-08-17 16:27:44`），但 `sh_index_close / sh_index_pct_chg / sh_week_ma / sh_deviation_pct` 四列 NULL——像是 16:27 抓复盘会页时指数字段还没出、之后再没刷过；`fact_stock_daily` 2025-09-19 共 5135 行，`close / amount` 100%，`pct_chg` 只有 4064 行（79.14%），**缺的 1071 行全在 SZ**（SH 2276/2276，SZ 1788/2859），2025-09-18 同形缺 65 行，`source=mootdx`。

---

## 1. 读数 [实测 2026-09-08，`db/market_feature_store.duckdb` 只读]

```sql
-- 洞一
select trade_date, sh_index_close, sh_index_pct_chg, sh_week_ma, sh_deviation_pct, total_amount, source, updated_at
from fact_market_daily where trade_date between '2026-08-14' and '2026-08-19';
-- 08-14 3927.176 / 0.0054 / 3940.3 / -0.33 | 08-17 NULL×4, total_amount 23857.9 | 08-18 3990.304 / 0.192 / 3945.04 / 1.15 | 08-19 3894.422 / -2.40 / 3937.11 / -1.08

-- 洞二
select trade_date, count(*), count(pct_chg), count(close), count(amount) from fact_stock_daily
where trade_date between '2025-09-17' and '2025-09-22' group by 1;
-- 09-17 5135/5129 | 09-18 5134/5069 | 09-19 5135/4064 | 09-22 5131/5131 ；close/amount 全满
select substr(stock_ts_code,-2), count(*), count(pct_chg) from fact_stock_daily where trade_date='2025-09-19' group by 1;
-- SH 2276/2276 ；SZ 2859/1788
```

写入口径（`AGENTS.md`「写入正门是 `python3 -m market_feature_store.cli daily-full`」；单表子命令：`sync-index-daily`、`sync-market-deviation`、`sync-stock-daily`、`fill-stock-daily-fallback`；派生：`scripts/backfill_market_deviation.py`）。`fact_sector_daily` 是 VIEW，不在本单。

---

## 2. 两刀

### 2.1 洞一｜`fact_market_daily` 2026-08-17 四列

1. **先试原始源**：对 08-17 重跑复盘会同步 `python3 -m market_feature_store.cli sync-market-overview --trade-date 2026-08-17 --refresh`（用 `CDP` / 串行，遵守 `fix/fupanhui-session-hygiene` 的 429 纪律）。拿到 `sh_index_close / sh_index_pct_chg` 即写入，`source` 保持 `fupanhui:reviews`，`updated_at` 变、`recorded_at`（#27）不变。
2. 复盘会页拿不到 → `sync-index-daily --trade-date 2026-08-17`（akshare 上证指数日线；工单 #33 同源）写 `sh_index_close`，`sh_index_pct_chg` 由 08-14 收盘派生并在 `source` 标 `akshare:index_daily`。
3. 两列有值后**重算派生列**：`sync-market-deviation --start-date 2026-08-17 --end-date 2026-08-21 --refresh`（或等价的 `scripts/backfill_market_deviation.py`）——周均线用到 08-17 的后续几天：08-18 / 08-19 的 `sh_week_ma` 当时是拿含 NULL 的窗口算的，要一并重算并逐日记录变化量。
4. 验收前后对比：08-17 四列非 NULL；08-18 ~ 08-21 `sh_week_ma / sh_deviation_pct` 的变化逐日列出（预期小幅变动，写出来）。

### 2.2 洞二｜`fact_stock_daily` 2025-09-18 / 09-19 `pct_chg`

1. **先查形状**：缺的 1071 行 SZ 代码是哪一段（`00xxxx` 主板 / `30xxxx` 创业板 / `002`）、是否恰好是当日 mootdx 分页或字段解析的一个批次（与 #32 §0 「东财快照事后补历史日」同族，还是 mootdx 侧 `pct_chg` 字段在该批为空）。用同表 09-17 / 09-22 这些完好日对照，判断是「源缺」还是「解析丢」（换手率那次是解析时被丢了——`fix/eastmoney-turnover-f8` 的形状）。
2. **重同步**：`sync-stock-daily --start-date 2025-09-18 --end-date 2025-09-19 --refresh`（#32 的路径；`--offset/--limit/--skip` 可只对缺行代码段分批），验收用 fupanhui 核心 50 只当真值（#32 方法），并检查 `close / amount` 不因刷新而变（它们本来是满的——变了就是源漂移，停下写交接）。
3. 仍 NULL 的行 → **允许一种派生**：`pct_chg = close / prev_close − 1`，`prev_close` 取同表该股票上一交易日 `close`，仅当上一交易日行存在且 `close > 0`；写入时 `source = 'derived:close_ratio(mootdx)'`。除权除息日这个派生会错——**没有除权表就不派生**：若本仓无该日除权数据源（查 `fact_*` 与 skills），派生只对「前后两日均在且 `amount` 非零」的行做，并把派生行数与代码段写进收据，基线里保留一条 `reason="derived:close_ratio，除权日未校验"` 的已知说明。
4. 09-18 那 65 行同法。

### 2.3 收尾

- 重跑 `scripts/check_daily_review_data.py <date> --update-fill-rate-baseline`（#662 的更新入口；分支未合就在 `feat/fill-rate-gate` 树里跑）把两处条目改成实际状态（删除 / 改 reason）。
- **下游收据重跑**：`methodology/teaching/` 下涉及 2026-08 的 `index_stage` 收据、`methodology/receipts/event_pricing/`（市场锚点 2026-08-17 附近）、`methodology/receipts/` 里 `new_high_1y / limit_up` 相关的个股规则——各自重跑一次，「保持 / 漂移（原因）」进收据；`history_labels.duckdb` 若含 2025-09 个股标签则 `build-labels` 重建。
- 收据 `docs/verification/2026-09-08-data-holes-0817-20250919.md`。

---

## 3. 验收

1. 洞一：08-17 四列非 NULL，`source` 写明来源；08-18 ~ 08-21 派生列变化逐日列出；`recorded_at` 未变。
2. 洞二：09-19 `pct_chg` 填充率 ≥ 99%（`fill-rate-baseline.json` 的 `min_fill_pct`），09-18 同；每一行的 `source` 能区分「重同步」与「派生」；派生行数 + 代码段 + 除权未校验声明进收据。
3. 核心 50 只真值对照：重同步行与 fupanhui 一致（≥ 49/50，不一致逐条列）。
4. `check_daily_review_data.py` 填充率闸对两日绿；基线条目状态与实际一致（不是删了事）。
5. 下游收据重跑清单齐全，每条有「保持 / 漂移」记录。
6. 全程只读探针与写入命令分开列在收据里；没有任何一行 `UPDATE ... SET pct_chg = <常数>` 之类手写值（`git diff` + 收据里的命令清单证明）。

---

## 4. 非目标 / 红线

- ❌ 不编数、不用模型补、不用板块 / 指数涨幅反推个股。
- ❌ 不碰 2026-06-22 / 06-23 北交所行（工单 #32，等 push2his 解封）。
- ❌ 不改 `fact_sector_daily` VIEW、不改 schema。
- ❌ 不在主检出 `/Users/a77/finance-workspace-private` 里跑全量对账（有他人未提交改动）；DuckDB 写入前确认 8792 的日更任务不在同一时刻写库（`launchctl list | grep finance`，避开 16:15 快照与晚间 `daily-full`）。
- `updated_at` 语义是刷新时间、`recorded_at` 是首次入库——补数只动前者（#27 红线）。

---

## 5. 教学注

- **「源缺」与「解析丢」的判法**：同一天同一源里，缺的行如果按代码段 / 分页边界整齐地切开，多半是解析或分页丢；如果散布随机，多半是源本身缺。09-19 缺的全在 SZ、SH 一行不缺，先怀疑前者。换手率那次（`f8` 一直请求着、解析时被丢）就是这个形状。
- **派生补数为什么要带 `source` 标记**：`close/prev_close−1` 在除权日是错的，而本仓没有除权表——这时候唯一诚实的做法是让每一行都能被下游识别为「派生的、未校验除权」，由消费方决定要不要用。把派生值与原始值混在同一列而不标记，是数据仓库里最常见的静默污染。
- **为什么修完要重跑下游收据**：`index_stage`、事件定价、个股规则的四态都是在带洞的数据上算的，修数后结论可能变——变了不是坏事，没跑才是。

---

## 6. 交接要求

- 收据一份；#662 基线条目同步；`inflight/main.md` 一句；若发现第三处洞（填充率闸全历史扫描时可能再冒），**立新单不扩本单**。
