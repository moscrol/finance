# docs/8792-dfc25221-cutover

## 这个分支做什么
只回写：记录 2026-08-21「sidecar live 四跑 → 切 8792 到 `dfc25221b07b`」，改台账 + 三份 handoff + 补两条规程坑。**无代码改动。**

## 当前状态
已推，**PR #287 open 未合**。基线 `dfc25221`，head `da0999ba`，树干净。
生产**已切**（运维事实，不在本分支里）：`48369a313ff5` → `dfc25221b07b`，**回滚指针 `~/.finance-runtime/finance-workspace-48369a313ff5`**。

## 怎么验收
1. `curl :8792/api/health` → `rev=dfc25221b07b / dirty=false / code_matches_repo=true`
2. `curl :8792/api/readiness` → 13/13 true、`missing_critical=[]`
3. 账本 `$FINANCE_WS/state/deploy-ledger.jsonl` 尾部有 `startup dfc25221b07b 8792` + `switch dfc25221b07b`
4. 长电收据 `~/.finance-runtime/live-probe-traceability/20260821-post-dfc25221-changdian.json`：degrade=0 / secret=0 / 89.0s。备份见 PR #287

## 未验证 / 已知边界
- **live 只证了一半**：四跑 `unattempted_claim_count` 全 `0`，证的是「有收据**不**改口」；Q1 改口路径与 Q3 减句回退**一次都没触发**（自然题跑不出）。`-09`/`-10` 保持 `pending`，未升 `confirmed`。
- 每题 n=1（电网 n=2），**没过方差门**。P0 `-06`/`-07`/`-08` 各一次正面读数，同样仍 `pending`。
- 切后只跑长电一题，未跑批次门禁四件套。
- ⚠ 与 `fix/prefetch-evidence-id`（PR #288）同改 `docs/prediction-ledger.md`，**后合方要 rebase 重解**。

## 下一步
1. 等用户确认合 #287。
2. 给 `-09`/`-10` 攒证据得**构造**触发形状（无资讯 trace + 稿含缺口声称 / repair 塌成残句），别拿自然题跑。
3. 回滚一行：`ln -sfh ~/.finance-runtime/finance-workspace-48369a313ff5 /Users/a77/finance-workspace-runtime` + bootout/bootstrap。

## 踩过的坑
- **入口选错会整轮打空、且看起来像跑过了**：`live_probe ask` 走 `/api/runs` 中立泳道，产物**没有** `continuous-episode.json`，护栏一个字段都不产。第一跑就是这么白跑的。
- **`capability` 有两套词表**：`evidence_plan.requirements` 写 `news_search`，`traces` 发的才是 `directional_news`。看见前者就断言「判据选错」会得出相反结论。
- 电网题**首跑没复现**（只调 1 次 `market_data`），补跑才出 `directional_news/future_of_cutoff`。**必须跑够两次。**
- 链切第④步命令**写死主仓路径**，主检出停在别的分支时没那个脚本，会**静默漏记账本**。改从新快照取。
- **smoke 收据 schema 已漂**：不再发 `source_revision`/`code_root`/`grounded`，照旧收据抄会读出「rev 为空」假红。

## 已验证
四条验收项实测通过。四跑 run_id 见 PR #287；电网那对是 `…012745_516002`（未复现）/ `…013054_035436`（复现）。

## 工具沉淀
两条坑已写进 `docs/workflows/acceptance-workflow.md`。未抽脚本：live venue 要看被测代码挂哪条链，是语义判断。
