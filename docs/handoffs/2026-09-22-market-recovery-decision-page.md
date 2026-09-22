# 2026-09-22 决策一页 · 09-21 行情恢复：五问 + 三份合同

> session S4 · `market-recovery-bridge-and-contracts` · 这是 #61。
> 桥分支 `fix/market-recovery-0921 @ f66d5b597` → PR #859 · 合同分支 `fix/market-recovery-contracts-0922 @ 93b4a90c6` → PR #861（含桥）· 基线 `gitea/main @ f24a61a8a`。
> 本会话零写库、零 staging、零发布；写库每一步等用户口令。写完不改；答案与后续状态看 `inflight/fix-market-recovery-contracts-0922.md`。

## 一句话现状

生产库 09-21 **整日零行**（`fact_market_daily` 最后 = 09-18）。唯一需要外部输入的个股 bar（5553 根）已封存并通过纯构造；其余按 `plan=local` 本地派生，**零复盘会请求**。卡住的不是数据，是五个口径没人拍板。

## 五问（要用户拍的）

| # | 问 | 实测证据（封存原件离线审计，rc=0） | 建议 | 不这么选的后果 |
|---|---|---|---|---|
| 1 | **名称**：接受「具名时刻展示名 + `name_source` + `name_observed_at`」当 `stock_name` 合同，ST/新股判定只用当日名？ | 380 差异 = 6 空格 + 344 简称/全称 + 30 XD/XR/DR 前缀且**方向相反**（20 对照侧有 / 10 具名侧有）；ST/新股分类差异 0 | **接受**（`sync_local_sector_members` 已改优先当日名） | 继续拿几个月前基线名喂过滤，除权前缀判错 |
| 2 | **换手率**：`turnover` 长期 NULL 直到拿到官方流通股本（东财 snapshot f8 是候选），只留 `observed_turnover_pct`？还是接受供应商值当真值？ | 21 条差异 >0.011pp，最大 3.75pp；`internal_denominator_mismatches=0`——两边各自内部自洽，差在分母口径 | **保持 NULL + 观测列**；要真值另立官方分母来源 | 把未核验分母写进事实表 |
| 3 | **历史范围**：官方名册从哪来（需用户在 Chrome 点「允许」恢复 CDP 取数）？还是先按 5565 声明范围恢复、产物固定 `official_historical_universe_verified=false`？ | 双向反例：`689009.SH` 有具名 bar 却不在当前名单；`000016.SZ` 等 9 只在名单却不在全域批次 | **先按 5565 恢复**，名册作后续门 | 等名册则 09-21 继续零行 |
| 4 | **停牌分母**：恢复路径启用冻结身份分母（`denominator_basis=frozen_identity`），12 只停牌留分母、不造 bar、不计涨跌家数？ | 5565 = 5553 ⊎ 12；涨跌平 4536/936/81；日更硬约束 2 会剔无值成员抬高涨停占比（测试锁 2/4=50%，非 2/3≈66.7%） | **启用** | 09-21 涨停占比虚高 |
| 5 | **写库路线**：按 local 计划 16 步重跑 09-21：先写 `fact_stock_daily` → `carry-forward-universe` → `stitch-sector-stocks --max-baseline-age-days 180` → 本地派生 → `features`；新隔离 staging → 逐表回读 → same-day/cross-day/L2 三门复跑 → 另授发布权才原子换库？ | 复盘会成分停 09-02；宇宙 09-17/18 `provider_source=local:carry`；验收 = `tables_for_plan(registry,"local")` 33 张；同花顺 12 张停 09-08（PID 92660 在补，非本轨） | **同意路线，每步单独口令** | — |

## 三份合同（都在合同分支）

| 合同 | 文件（提交） | 管什么 | 状态 |
|---|---|---|---|
| 输入合同 | `2026-09-22-market-recovery-input-contract.md`（`f2d935a02`） | 固定输入身份：278 文件 manifest、5 个 SHA、5565 范围、12 只缺 bar、两只复牌具名前收、股/手单位、半分舍入 | 只读取证；`capture_validated` ≠ `production_ready` |
| 纯候选合同 | `2026-09-22-market-recovery-pure-candidate.md`（代码 `7311a7738`） | `hithink_recovery_candidate.py` 纯构造器：5565 → 5553 候选 + 12 处置；三个 false 标志固定 | 88 测试；6 类变异抓红；不连网不写文件 |
| 字段/分母合同 | `2026-09-22-market-recovery-field-contracts.md`（代码 `f464badf8`） | 上表五项；`recovery_coverage.py` 纯函数 + `audit_recovery_metadata.py` 离线审计（产物 sha256 `abfa67b2…`）；两处下游口径对齐 | 4 处变异抓红；`remaining_gates` 五道门写进产物 |

## 两张 PR 与门禁

- **#859 桥**：7 文件 +1190；merge-tree 对 `gitea/main@f24a61a8a` clean。
- **#861 合同**：18 文件（含桥）；先合 #859 后自动缩到 11 文件；merge-tree clean。干净 tip `93b4a90c6` 全仓 ruff 绿、`pytest -q` 12684 passed / 85 skipped / 2 xfailed / 0 failed（21m26s，与另两个会话的全仓 pytest 并跑）。
- 未跑前端 / E2E（两枝均不触碰 webapp）。合并等用户确认。
- 证据目录 `~/.finance-runtime/reviews/market-recovery-bridge-and-contracts-20260922/`（gate.log、两树 ruff/pytest 日志、PR 正文）。

## 还没关的门

- 官方名册、除权完备性、官方流通股本：三个 `*_verified=false`。
- same-day / cross-day / L2 三门最近 `rc=2`，未复跑。
- 生产库 mtime 09-22 08:08 已变，02:26 保全收据过期；写库前重取基线，且要与夜间 staging 抢同一把 run mutex。
