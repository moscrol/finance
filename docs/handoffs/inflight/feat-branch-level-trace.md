# 在途交接 · feat/branch-level-trace（基座 gitea/main `504cbbc9`）

## 这个分支做什么
09-07 四遍读数收据 §5 的「先量分支内每批派发数再动帽」——量的那一步。分支 Episode 的 `outcome.events`
此前在 `ContinuousSubResearchWorker.run` 被丢掉，父臂只剩合计数。现在每支分支带 `stop_reason`、逐批派发账
`batches`（requested / succeeded / rejected_by_cap / timed_out / errored / rejected_other + 派发时钟）、预算账
`budget`（allocated / consumed / remaining + `batch_call_cap`），同时进 `sub_research` 的 `tool_result.telemetry`
与 durable `branch_completed`。收据 `docs/verification/2026-09-07-branch-level-trace.md`。

## 决策与被否方案
- 派发账从事件重算 / 否 worker 自报——每批 `requested == 五类之和` 可校验，自报不可。
- 预算账由协调器从 `_BranchBudgetView` 读 / 否 worker 填——与 `tool_calls` 同一纪律，LyingWorker 测试钉住。
- 进摘要不进事件本体 / 否把分支整条事件流塞进父账本——父臂一条 `tool_result` 装不下三支。
- 事件与 telemetry 共用 `branch_telemetry` / 否各写一份——两处此前已漂（tokens 只在事件里）。
- 没账不写键 / 否写 0——取消 / 异常分支的「没测到」不能长得像「测到是零」。
- **不动** quick 每批帽 4、不动任何档位数字、不跑 28 题。

## 当前状态
提交 `66de98c2`（代码 + 6 测试 + 收据 + 本文）；`test_sub_research*.py` 33P/0F，邻接套件 272P/0F，ruff 全仓过；
5 个变异各击杀 ≥1（表在收据 §2）；干净树全量 7986P/0F/76S，`check_test_receipt.py` 可采信。**未合、未切 8792。**

## 未验证 / 已知边界
- live 没跑：`batches` 在真分支上长什么样还没见过；测试里的 5 点 4 成 1 拒是脚本模型。
- `rejected_by_cap` 把「每批帽」与「分支剩余次数」两种 `tool_budget_exhausted` 记同一个数，靠同批 `remaining_slots_at_dispatch` 分。
- 事件 payload 变大（每支分支多一个 `batches` 列表）；projection / progress 只读 `branch_id`，不受影响，但 UI 侧若整段渲染 payload 会变长。

## 下一步
1. 合入 → 切 8792 → 同一道 `theme_track` 题（固态 vs 钠电）重跑一遍，读 `branch_completed.batches`。判据在收据 §4。
2. 有读数后再决定动不动帽 4；没有读数不动。
3. 分层预留（判官 / 合成额度先扣）是下一刀，接缝 `api/app._deployment_execution_policy`。

## 踩过的坑
- `EpisodeEvent.payload` 走 `_json_freeze`：list 变 tuple，测试比对 `to_dict()` 时按 list 写，比对事件时别按 tuple。
- 用主树 `.venv-workbench/bin/python` 跑新树测试可行（无 editable 安装，加载哪份代码由 cwd 定）。
