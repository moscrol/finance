# docs/8792-dfc25221-cutover

## 这个分支做什么
只回写。记录 2026-08-21 的「sidecar live 四跑 → 切 8792 到 `dfc25221b07b`」，改台账 + 三份 handoff + 补两条规程坑。**无代码改动。**

## 当前状态
未提交/未推。生产**已经切了**（不在本分支里，是已发生的运维事实）：`48369a313ff5` → `dfc25221b07b`，回滚指针 `~/.finance-runtime/finance-workspace-48369a313ff5`。
readiness 13/13 + `missing_critical=[]`；health 三读 `rev=dfc25221b07b / dirty=false / code_matches_repo=true`；长电 `run_20260821_013544_521745` degrade=0 / secret=0 / 89.0s / `fact_stock_daily`×4。备份 `~/backups/gitea-20260821-post286.tar.gz`（1.2G）。

## 未验证 / 已知边界
- **live 只证了一半**。四跑 `unattempted_claim_count` 全 `0`，证的是「有收据**不**改口」。Q1 的改口路径、Q3 的减句回退**一次都没触发**——自然题跑不出那两个形状。`R-20260820-09`/`-10` 因此保持 `pending`，没升 `confirmed`。
- 每题 n=1（电网 n=2），**没过方差门**。P0 `-06`/`-07`/`-08` 各拿到一次 live 正面读数，同样仍 `pending`。
- 切换后只跑了长电一题，没跑批次门禁四件套（本次无代码增量，增量 = 已合的 #285）。

## 下一步
1. 本分支 push + 开 docs PR（**未做，等用户拍**）。
2. 要给 `-09`/`-10` 攒 live 证据，得**构造**会触发的形状，别再拿自然题跑。
3. 回滚一行：`ln -sfh ~/.finance-runtime/finance-workspace-48369a313ff5 /Users/a77/finance-workspace-runtime` + bootout/bootstrap。

## 踩过的坑
- **入口选错会整轮打空，而且看起来像跑过了**：`live_probe ask` 走 `/api/runs`，落中立泳道，产物**没有** `continuous-episode.json`，P1 护栏一个字段都不产。必须走 `POST /api/conversations/{id}/messages`（`skill_mode=auto`、`perspective_mode=neutral`）。第一跑就是这么白跑的。
- **`capability` 有两套词表，别拿错的那套下反证**：`contract.evidence_plan.requirements` 里写的是 `news_search`，`traces` 里发的才是 `directional_news`。看见前者就断言「红线判据选错了」会得出相反结论。
- **电网题首跑没复现原始现场**（模型只调 1 次 `market_data`，压根没碰资讯），补跑才出 `directional_news/future_of_cutoff`。这题必须跑够两次。
- 链切五步第④步的命令**写死主仓路径**，主检出停在 `feat/reading-rules-baseline-batch1` 时没有 `scripts/audit_deploy_ledger.py`，会静默漏记账本。改用新快照内同名脚本。
- **收据 schema 漂了**：`smoke_workbench_self_use.py` 现版本不再发 `source_revision`/`code_root`/`grounded`/`question`/`user`。照 08-19 那份抄字段会读出「rev 为空」的假红——revision 以 health 三读为准。

## 已验证
live 四跑：锂矿 `run_20260821_012059_353272`、铝 `run_20260821_012508_762073`、电网 `run_20260821_012745_516002`（未复现）+ `run_20260821_013054_035436`（复现）。产物在 `~/.finance-runtime/live-probe-traceability/users/live-probe/runs/`。切后收据 `~/.finance-runtime/live-probe-traceability/20260821-post-dfc25221-changdian.json`。

## 工具沉淀
两条坑已写进 `docs/workflows/acceptance-workflow.md` §4 与「坑」节。未抽脚本：live venue 的选择要看被测代码挂在哪条链上，是语义判断。
