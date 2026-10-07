# 2026-10-06 部署：8792 切到 f3b97499aaff（#52 + #54 模型优先）

写完不改。前文：`2026-10-06-model-first-harness.md`（改了什么、为什么、被否方案）。

授权（逐字）：「按照最优方案合并部署。」（10-06）；部署常设授权「我授权同意，你按照最优方案推进就行」（09-26）。

## 合并

- #52 @ `842e4bff9` → 合并提交 `d1966188d`。合并前 `workbench-check` 聚合任务因等待 runner 超过 60 分钟被取消（四叶都绿），重跑该任务后通过。
- #54 改 base 为 main 后 @ `9556f6e35` → 合并提交 `f3b97499a`。main 的树与 #54 head 的树逐字节相同（本机该 head 全量门禁 20598P/0F 可采信）。

## 快照四叶（`~/.finance-runtime/finance-workspace-f3b97499aaff`，树始终干净）

| 叶 | 读数 |
|---|---|
| Python | 20600P / 0F / 0E / 75S / 2X；`check_test_receipt --require-full-scope --expect-revision <origin/main> --base-drift-max 0` 可采信 |
| registry 四项 + crosswalk | 全 exit 0 |
| 前端 | install / lint / typecheck / test（210P）/ build 全 exit 0 |
| E2E | 52 passed |

## 切换与事故

链切五步一次成功（bootout 2 s 卸载、账本 record exit 0、bootstrap 一次成功），但**新快照缺 `.venv-workbench`**：生产启动器用「快照目录/.venv-workbench/bin/python」起 uvicorn，旧快照里有指向主树 venv 的软链，规程 §4 没写这一步。服务 exit 127 循环重启约 4 分钟；补软链（git 忽略，树仍干净）+ `launchctl kickstart -k` 后 35 s 起来。**8792 总停机约 10:54:48–10:59:40，落在交易时段**。规程 §4 已在本 PR 补上软链与可执行检查；同时把取 sha 的远端从 gitea 改成 origin（09-30 起 Gitea 只收备份、会滞后），备份判据改成 Gitea `main` == 新 sha。

## 切后三验

1. readiness 13/13 true。
2. health 三读 `f3b97499aaff` / `source_dirty=false` / `code_matches_repo=true`；监听进程 cwd = 新快照。
3. grounded 探针「长电科技怎么看」：completed，degrade 0，content_degraded 0，judge_unavailable 0，secret_scan 0，模型自报 glm-5.3-flash；口径 `fact_stock_daily`×15、`fact_stock_valuation_hithink`×10；11 次工具，132 s。

另：`audit_deploy_ledger.py check` ok、`homes` 无旧家残留；GitHub→Gitea 定时备份已覆盖新 main。

行为验证：生产 8792 上 D6「2026-07-22 高标股的晋级情况如何，有没有出现空档」走 Episode（6 次工具，model_finish），直接答梯队完整、无空档、晋级率偏低，不再出现内部数据包与套话段。

证据目录：`~/.finance-runtime/model-first-harness-1006/deploy-f3b97499aaff/`（`DEPLOY-RECORD.md`、`switch.log`、`frontend-e2e.log`、探针原件）。

回滚：`ln -sfh ~/.finance-runtime/finance-workspace-765ecbac9ad3 /Users/a77/finance-workspace-runtime` + bootout / bootstrap（旧快照保留，带 venv 软链）。

## 后续要做（从已删除的分支 inflight 移来）

- 新 8792 对 Pi 的独立盲评（沿用 v5 协议与冻结真值；本轮只有自读、每题 n=1）。
- （待核）剩余误报：区间写法「2至5」「121→47」、推算计数、模型自拟阈值；先量误报率再改判据。
- D8 休市补最近交易日；external_market / watchlist_digest / disclosure_scan 是否回 Episode 按同法 A/B；B 盘面包代码清理。
- 观察生产上 PLAN 分支（09-22 起潜伏的 storage_failed 已修）与 180 s 单轮上限下的耗时分布。
