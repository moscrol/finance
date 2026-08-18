# 2026-08-18 全量复盘补跑（当日完成）+ L2 挂账开关

## 结论

22:04:18 finalize 打出「全量复盘完成 date=2026-08-18」，报告产物全部落盘
（`复盘/daily/2026-08-18/`、`复盘/index.html`、exports/、strategy matrices）。
生产库 `fact_market_daily` 覆盖到 2026-08-18。

## 时间线（均为 08-18）

- 02:25 finalize：same-day 守卫拦下（当时 18 张表全无 08-18 数据，根因见下）
- 18:30 S7 staging sync：跑完 24 分钟后败于 duckdb 撞锁——
  homebrew Python 3.14 进程（PID 62525，疑似 pit-snapshot）持有主库写锁，
  子进程 `IO Error: Conflicting lock`，质量门未全绿不换名
- 20:06 kickstart 第一轮重跑：same-day 门 COMPLETE，但 cross-day 门拦截——
  7 张 fact 表断档（core/dragon_tiger/leader_height/global_index/global_stock/dragon_summary/dragon_seat 停在 08-14）
- 20:4x 诊断：`run_review_sync.py` 丢失 public-assets 步。
  该步只存在于救援快照 `12512daa`（⛔ 不可整支合并），从未进 main
- 20:4x 范围回补：`sync-fupanhui-public-assets --start-date 2026-08-17 --end-date 2026-08-17`
  （第一轮 4 子任务 SSL 抖动失败，重试全过）+ `--trade-date 2026-08-18` 单日（范围模式按
  fact_market_daily 迭代，当时还没有 08-18）。7 张表全部补到 08-18
- 20:56 kickstart 第二轮 S7：双门全绿，21:34 原子换名 `run_id=ad4c312586aa`
- 21:38 kickstart finalize：sync 守卫过，L2 分支失败（limitup/top100/quant failed，
  `feature_l2_*` 实际自 08-07 就断供）→ 21:39 L2 门拦下生成段
- 22:00 按 77 指示 L2 挂账停抓，落地开关（见下）
- 22:03 第三次 finalize：L2 分支被 flag 跳过，生成段 14 步全跑完
- 22:04 最终硬门过，`=== 全量复盘完成 date=2026-08-18 phase=finalize ===`

## 改动（本分支）

1. `scripts/check_daily_review_data.py`：新增 `L2_PAUSED=1` 环境变量短路
   `check_l2`——跳过但打印「L2 已挂账暂停……欠账待鉴权恢复后回补」，不静默。
   对照验证：带变量 rc=0，不带 rc=2（failed 仍拦截）。
   注意与既有 `L2_ALLOW_ALL_EMPTY` 的语义区分：那是「complete 但 0 行=当日确无数据」放行，
   救不了 status=failed。
2. `skills/daily-full-review/scripts/nightly_full_review.sh`（仓内源）
   + `~/.local/bin/nightly_full_review.sh`（launchd 实际执行的部署副本，两份必须同步改）：
   `run_l2_branch` 顶部检查 `$WORKSPACE/state/l2-paused.flag`，存在则
   export L2_PAUSED=1、moneyflow_rc=0、l2_rc=0 直接返回。
3. `skills/daily-full-review/scripts/run_review_sync.py`：按救援快照 `12512daa` 原样装回
   public-assets 步（theme-flow-daily 之后、features 之前，heavy_timeout），
   防止明晚 cross-day 门再次拦截。
4. `state/l2-paused.flag`：挂账 flag（含暂停时间与原因注释）。

测试：`test_pipeline_p0 / test_non_trading_day_l2_guard / test_review_gate_lock_retry`
35 passed。

## L2 恢复路径（鉴权就绪后）

1. `rm state/l2-paused.flag`（夜跑即恢复抓取）
2. 欠账回补：`run_l2_pipeline.sh <date>` 按交易日逐日跑（欠账 ≥08-08，含 08-18）
3. 回补后核对 `ops_pipeline_run_daily` 三步 status=complete 且
   `check_daily_review_data.py <date> --phase l2` 不带 L2_PAUSED 也过

## 遗留

- 本分支未合 main，等 77 确认；部署副本已直接改，功能即时生效
- 明晚 18:30 起链路应自愈：public-assets 步回归 + L2 flag 跳过
- agent-memory 已写一行交接（`20_projects/finance-workspace-private.md`）
