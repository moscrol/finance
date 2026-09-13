# 工单 #33 · 市场级历史回补 314 天：参照标注全量导出 + 上证 K 线 + 个股聚合，三件一起才解得开样本量

- 优先级：**P1**（中单；三件里创始人那件是关键路径）。
- 来源：2026-09-08 评审第 3 条「四条线撞同一堵墙，墙后面躺着 314 天没人用」+ 复核补的两个依赖（见 §1.2）。
- 分支：`feat/market-history-backfill-314`（代码两件）；参照导出是创始人的活，不在分支里。
- 不动：`schema.sql`；`fact_market_daily` 已有的 416 行一个字节不改（回补只写 2023-09-01 → 2024-12-19 的新行）。

## 0. 执行状态

| 项 | 状态 |
|---|---|
| A. 参照标注全量导出（创始人） | ⏳ 待创始人从数据中台导出 `reviews/overview`（2021-09-13 起） |
| B. 上证指数 K 线回补 314 天 | ⏳ 待派（源已在用：`akshare:stock_zh_index_daily:sh000001`，与现有 413 行同源同级） |
| C. 个股聚合回补 314 天 | ⏳ 待派（算子已在用：#640 / #642 的 `compute_*_local`） |
| C'. 申万一级历史 314 天（C 的子依赖） | ⏳ 待派（`sync_akshare_sw_l1_daily._fetch_hist_by_code` 已能取全史） |
| D. 官方日程 2023 / 2024（事件定价吃到 N 的前提） | ⏳ 待派（照 `references/calendars/official_release_schedule.2025.json` 的形状录两年） |

## 1. 事实

### 1.1 墙在哪 [实测 2026-09-08 真库]

| 表 | 起点 → 终点 | 交易日 |
|---|---|---|
| `fact_stock_daily` | 2023-09-01 → 2026-09-07 | **730** |
| `fact_market_daily` | 2024-12-20 → 2026-09-07 | 416 |
| `fact_sw_l1_daily` | 2024-12-30 → 2026-09-07 | 410 |
| `fact_theme_limit_stock_daily` | 2025-01-02 → | 398 |
| `fact_stock_high_daily` | 2025-01-02 → | 408 |
| `history_reference_stages`（授课框架参照） | 2024-11-15 → 2026-09-04 | 440 |

早于 `fact_market_daily` 起点的 **314 个交易日**：`fact_stock_daily` 1,573,960 行，来源全部 `mootdx`，`close` / `open` / `high` / `low` 100%、`amount` 100%、`pct_chg` 99.99%。

这 416 天同时是：授课框架 402 个有标签日（训练 243 / 验证 159）的上限、事件定价市场类 N=13–20 的分母、
「缩量右底训练期只 8 天一天没赢过」「主流主升 2.0 三段只一段来源对」的原因、王朝链只有 4 个完整周期的原因。

### 1.2 只回补价格解不开的两件（评审原文没写，复核补的）

1. **授课框架一致率的分母不是 `fact_market_daily`，是参照标注。** 训练 / 验证 = `history_reference_stages` 里
   `train_until` 两侧的日子；参照现只载 440 天。平台上有 2021-09-13 起的 `cycle_stage`（slice1 spec §9.17），
   09-07 拉全量触发 429（`retry-after ≈ 72h`），定的正路是创始人从数据中台导出。**没有 A，B + C 对一致率、缩量右底样本量、
   第三份 holdout 一个都不起作用。**
2. **上证指数序列不在个股表里。** `index_stage` 的 A 类输入（`sh_index_close`、周均线、偏离度、10 日涨幅、本腿涨幅）全靠指数 K 线，
   #642 从个股聚合市场级指标的算子给不出。好消息：现有 413 行的 `sh_index_source` 就是 `akshare:stock_zh_index_daily:sh000001`，
   `sync_akshare_index_daily(start_date=…)` 支持起止日——同源同级，不是新接一个源。

### 1.3 回补段与 fupanhui 段不是一级来源（评审的 caveat，成立）

`fact_market_daily.source` 现在三种：`fupanhui:reviews` 246 / `feishu:daily` 159 / `local:overview` 3。回补行统一写
`local:overview-backfill`，`strength_source = local:top5pct-backfill`，`stock_high_source = local:high-ohlc-backfill`，
`market_stage` / `stage_day` / `ice_point` / `note` 留 NULL（供应商编辑字段，不冒充）。校准时按 `source` 分层：
授课框架 `stage_bands_derived_from` 已记来源指纹，加一列 `source_mix`；事件定价的形状基准按 `source` 分桶各出一次。

## 2. 要做的事

### A. 参照标注全量导出（创始人；关键路径）

- 从复盘会数据中台导出 `reviews/overview` 逐日记录，2021-09-13 → 2024-11-14（现有 440 天之前的部分），字段照
  `scripts/fupanhui_review_overview_pull.py` 落的 JSON 形状（`cycle_stage / external_cycle / internal_cycle / is_ice_point / 量能比 / up_rate_ma5 / …`）。
- 载入：`scripts/teaching_framework.py load-reference --json <导出文件> --labels-db <旁路库>`（已有命令，幂等）。
- **holdout 纪律先写死再载**：训练 ≤ 2024-12-31（含回补段）/ 验证 2025 全年 / **holdout 2026 只读一次**，读完写进收据；
  `calibrate-stages --train-until 2024-12-31`。09-07 那 29 次验证集咨询（`docs/verification/2026-09-08-teaching-framework-mcnemar.md` §3）
  不能再发生在 holdout 上。

### B. 上证指数 K 线回补 314 天

```bash
python3 -m market_feature_store.cli sync-akshare-index-daily --start-date 2023-09-01 --end-date 2024-12-19   # 以 CLI 实际参数名为准
```

- 写 `sh_index_close / open / high / low / volume / pct_chg`，`sh_index_source = akshare:stock_zh_index_daily:sh000001`；
  `sh_week_ma`（5 日 MA）与 `sh_deviation_pct` 按 `ma5_recompute_backfill` 同一公式回算，`sh_week_ma_source = ma5_recompute_backfill`。
- 行不存在时先插只含 `trade_date` 的骨架行，`source = local:overview-backfill`，其余列等 C 填。

### C. 个股聚合回补 314 天（+ C' 申万一级历史）

逐日调用已有算子（按日期升序，ma20 / 环比要前 19 天；2023-09 开头 19 天这两列 NULL 是正常的滚动窗口，照 2024-12 的先例）：

| 列 | 算子 | 备注 |
|---|---|---|
| `total_amount / advancers / limit_up / limit_down / amount_vs_yesterday_pct / amount_ma20 / volume_ratio / volume_state` | `compute_market_overview_local(td)`（#640） | 沪深总额不含北交所；涨停按 #640 口径（沪深四舍五入 / 北交所向下取整 / 不计 ST）——评审提的边界已在这里处理 |
| `strength_*` | `compute_market_editorial_local(td)`（#642） | 涨幅前 5% 口径 |
| `stock_high_count_*` | `compute_stock_high_local(td)`（#642） | 1y+ 新高要 ≥ 1 年回看：2023-09 → 2024-08 的 1y/2y/3y 列 NULL 并记缺口；20/60/120d 从 2024-03 起可算 |
| `industry_1..3 (+_ratio) / top3_industry_ratio / concentration_state` | 先跑 C'：`sync_akshare_sw_l1_daily` 用 `_fetch_hist_by_code` 补 31 个申万一级 2023-09-01 → 2024-12-29 | 无历史 → 这七列 NULL，**不许用当日成分反推**（成分会漂） |
| `market_stage / stage_day / ice_point / note` | 不算 | 供应商编辑字段；`market_stage` 等 A 的导出 |

- `compute_market_overview_local` 遇到 `source` 非 `local:` 且已有值会跳过——回补段全是新行，不会碰到；但**禁止对 2024-12-20 之后的行加 `--force`**。
- 特征层随后重算 `feature_market_window`（`compute_features`），只算回补段。

### D. 官方日程 2023 / 2024

- `references/calendars/official_release_schedule.2023.json` / `.2024.json`，形状照 2025（`nbs_<year>` / `fomc_<year>` / `nifc_lpr_api`，带 URL、`schedule_published_at`、录入日）。
- 事件定价 `build-calendar` 会自动吃进去；市场类 N 从 13–20 → 约 35–45。**门槛按 spec §8 第 0 条重算**：N=35 仍要 7/35 = 20%（3.6 倍基准）——回补让 N 够看分布，不足以让宏观类单独出阳性，池化另立。

## 3. 验收（能逐条打勾）

1. `fact_market_daily` 行数 416 → 730，`MIN(trade_date) = 2023-09-01`；2024-12-20 之后的 416 行 `updated_at` 与内容逐字节不变（回补前后 `SELECT hash_agg(*)` 相等）。
2. 回补行 `source = 'local:overview-backfill'` 100%；`sh_index_source` 与现有行同值；`market_stage` 在回补段 100% NULL（等 A）。
3. 第四层填充率闸（PR #662）：`fill-rate-baseline.json` 只允许新增 2023-09 开头滚动窗口那 19 天的 `amount_ma20 / amount_vs_yesterday_pct / volume_ratio` 空值日与 `stock_high_count_*` 的 1y+ 缺口，**其余列不得新增空值日**；`--update-fill-rate-baseline` 的 diff 就是验收物。
4. 对照：回补段任取 10 天，`total_amount` 与 akshare 全 A 成交额（或东财历史）相对差 < 1%；`advancers` 与东财涨跌家数差 ≤ 20 只。
5. A 到位后：`history_reference_stages` 覆盖 ≥ 2023-09-01；`calibrate-stages --train-until 2024-12-31` 后八段训练期各 ≥ 30 天（现在缩量右底 8 天）；
   一致率报三列（训练 / 验证 2025 / holdout 2026），holdout 那列在收据里只出现一次。
6. 事件定价 `build-calendar` 后 `cn_cpi_ppi` 市场锚点 ≥ 35，收据每类旁标最小可检出 k/N。
7. 门禁：`.venv-workbench` pytest / ruff 全绿；pre-commit 11 道；`path-literals` 不新增。

## 4. 风险与边界

- akshare 对 2023 年的 `stock_zh_index_daily` 偶有复权口径差，回补前抽 3 天对上交所官网收盘价核。
- mootdx 早段 `pct_chg` 99.99% 非空，那 0.01% 是新股首日；`advancers` 口径「pct_chg > 0」不受影响。
- 申万一级成分在 2023–2024 有调整（2021 版行业分类）；C' 取的是申万自己的指数日线，不涉及成分反推，安全。
- 回补是一次性的历史写入，走 `--start-date/--end-date` 显式区间，不进 nightly；写前备份 `fact_market_daily` 全表 parquet 到 `~/.finance-runtime/db-repair/`。
