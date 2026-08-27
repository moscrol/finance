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

- L2 欠账仍等鉴权：最后 complete=08-07；failed=08-10/08-13/08-18
- 明晚 18:30 才是 public-assets 步第一次被夜跑执行（08-18 成功轮是 CLI 回补后 clone）
- 主仓脏树不要切走；`state/l2-paused.flag` 留着
- 不要为这单切 8792
- agent-memory 已写一行交接（`20_projects/finance-workspace-private.md`）

## 轮次记录

### 检阅批注 · Round 1（2026-08-19，检阅方）
- **判定**：PASS。干净树只拣 `1df6844d`，不要整支落后 518 的分支快进。
- 18:30/20:06 败因是 cross-day 7 表断档，不是撞锁。成功 S7 未跑到 public-assets 步。
- 三文件原 35 绿没有夹住新行为。

### Round 2 收尾（2026-08-19）
- 树 `/Users/a77/fwp-wt-l2-pause-main` `fix/l2-pause-public-assets-onto-main`，基线 `gitea/main`。
- 夹具先红后绿：`test_sync_plan_includes_public_assets_between_theme_flow_and_features`、`test_check_l2_paused_skips_without_touching_db`。
- 相关三文件 + 新夹具 39 passed。未切 8792，未动主仓脏树。
### 检阅批注 · 08-19 夜跑质检（2026-08-20，检阅方）

- **判定**：FAIL / INCOMPLETE。08-19 全量复盘未完成；无报告产物；生产库仍停在 08-18。
- 独立复核：
  - 18:30 S7 开跑 `s7=418515c03833`，`workspace` 工作树 `78391e8e`（`feat/reading-rules-baseline-batch1`），clonefile staging 3.4G
  - **public-assets 步当晚第一次真正夜跑执行**：`>>> public-assets` 524.3s / rc=0；core 50、dragon 74、seats 675、global 5/194 已进 staging。失败子任务：`dragon_summary`、`regulation`（公开 API read timeout）。CLI 设计是「至少一个成功则 ok」，所以整步不重试这两个子任务
  - 19:06 `[staging] 夜跑 sync 未全绿, 不换名`；生产库 mtime 仍 08-18 21:39；`ops_sync_run` 最近成功换名仍是 `ad4c312586aa`（08-18）
  - 20:40 finalize 读**生产** same-day rc=2（18 张表全无 08-19），生成段未跑。`复盘/daily/2026-08-19/`、exports `2026-08-19*`、`quality-2026-08-19.json` 均不存在
  - 亲手读库：生产 18 张 same-day + 7 张 GAP public-assets 均 max=08-18；staging same-day 除 `fact_sw_l1_daily` 外都有 08-19；`fact_dragon_summary_daily` staging 也停在 08-18
  - 官方闸门重跑：生产 08-19 data rc=2；staging data rc=2（只报 sw_l1 0/31）；staging cross-day rc=2（`fact_sw_l1_daily` + `fact_dragon_summary_daily` 断档）
  - `l2-paused.flag` 仍在（08-18 22:00）。L2 特征表 max=08-07。生产上 L2 门把 08-19 判成「非交易日」是因为 `fact_stock_daily` 还没有 08-19 行（`is_trading_day` 用日线≥3000 当日历），不是真休市
  - #217 已在 `gitea/main`（`02be2ca1`）；`run_review_sync.py` 含 public-assets。夜跑吃的是 private 脏树，不是 8792
- 根因（PRIMARY）：`sync-sw-l1-daily --days 20` 两次都 300s timeout、零 stdout。same-day 因此 INCOMPLETE。08-18 同模块 288s 擦边过；300s 轻模块预算对 akshare 31 行业历史拉取系统性偏紧，收尾重试用同一 timeout 救不回来
- 潜伏第二门（换名仍会被拦）：即便补上 sw_l1，cross-day 仍会因 `fact_dragon_summary_daily` 缺 08-19 不换名。蓝绿当晚按设计工作
- 次要：`sector-stocks` 标 partial（20 圈后仍 `missing_tables=fact_sector_daily mismatch=daily_identities`），实际 403/403、52779 行；`fact_sector_daily` 08-19=402，缺「半导体封测」一名，连续性 99.75% 过 95% 门。limit-heat 121 / 涨停 37 / 跌停 144 与上证 -2.40% 的市况一致，不是缺数
- Round 2 指派（修复，未做）：
  1. 在 staging 上单独跑 `sync-sw-l1-daily`（建议 timeout≥600s）+ `sync-fupanhui-public-assets --only dragon_summary`（regulation 不在 GAP，可顺手）
  2. staging 双门绿后再换名，然后 `nightly_full_review.sh finalize`（保留 `l2-paused.flag`）
  3. 不要在 `feat/reading-rules-baseline-batch1` 脏树上改编排；sw-l1 改 heavy_timeout、public-assets 失败子任务纳入收尾重试，另开干净树
  4. 勿把 staging 在双门未绿时换进生产

### 收口 · 08-19 补洞（2026-08-20 10:37；11:06 复验仍 PASS）

- **判定**：上节 FAIL 已被盘中补洞 supersede。生产 `fact_market_daily` max=08-19；日报已落；独立复跑 same-day/cross-day **PASS**（11:06 再打一遍，无漂移）。
- 修复按 Round 2 的 1/2/4 做了（昨收盘兜底而非拉长 timeout；regulation 仍超时未补）。编排债（3）仍未做。
- 正文：`docs/handoffs/2026-08-20-daily-full-review-0819-repair.md`
