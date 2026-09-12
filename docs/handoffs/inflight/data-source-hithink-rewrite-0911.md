# data-source/hithink-rewrite-0911 · 09-11 主表修复（同花顺换源）

## 这个分支做什么

东财快照 2026-09-11 的 `fact_stock_daily` 用同花顺官方 `daily-k-10d` dump 重建。
QC 审查与修订要求、对账证据、处置表、干跑报告全在
`/Users/a77/.finance-runtime/db-repair/hithink-20260911/`（review.md / repair-plan.md /
before.json / dryrun-report.json）；工作树在同目录 `tree/`。

## 现状

- 修复模块 `market_feature_store/sync/repair_hithink_stock_day.py` + CLI
  `repair-stock-daily-hithink`（默认走 staging 原子换库；`--child` 子进程模式）+
  `sync_daily_full.run_daily_full_staged` 加 `kind` 参数（收据不冒充 daily-full）。
- 测试 8+1 条过；ruff 过。提交见 `git log`（本交接与代码同批）。
- **干跑已通过**：真库克隆上 5,547 写 / 6 保留 / 当日 5,553 / 其他日期指纹全等 /
  唯一白名单漂移 600176 amount −0.0001 亿。

## 关键口径（改代码前必读）

- pct_chg 必须 DECIMAL 半进——浮点 round 在 .xx5 边界错 0.01（5 行实测）。
- amount=round4(turnover/1e8)、volume=round0(volume/100)、name/换手率保留旧行。
- 北交所 3 只（920045/920161/920375）量额双差原因未核实：**整行保留**。
- 302132.SZ 是东财漏收不是新股（dump 连续 10 根 bar）；688801.SH 才是新股，
  pre_close/pct_chg 保留发行价口径。

## 下一步（顺序）

1. 用户授权后跑正式换库（命令见 repair-plan.md「剩余步骤 1」——**必须
   `MARKET_FEATURE_STORE_DB` 指向真生产库**，DB_PATH 按包根解析）。
2. 派生：`feature_stock_technical_daily` 09-11 重算（compute_features.py）；
   `fact_market_daily` 复盘会口径不重算、声明口径差。
3. 并跑表补齐（打上游 API，按端点日期语义，见 review.md 要求 5）。
4. 合并等用户确认 + 本机等价 CI。
