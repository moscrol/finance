# 分支级 trace：逐批派发账 + 预算账进收据（2026-09-07 上午）

上文：`2026-09-07-branch-budget-repair-fuse.md`（同题四遍撞出三道顶，#615–#617）。那份收据 §5 留的下一步是
「分支起步用 quick 档的 4 次每批帽，可能是分支慢的原因之一，**先量分支内每批派发数再动**」。
本文是「先量」这一步的代码侧：让分支内部逐批派发账与预算账进收据，**不动 quick 每批帽、不动任何预算数字、不跑 28 题**。

## 0. 为什么先补 trace 而不是直接改帽

对 #615–#618 这条线做过一次六层巡检（09-07 上午），L6 可观测的结论是：现有收据够说明「终局发生了什么」，
但分支内部「每批点了几个、几个被帽拒、分支还剩多少秒」由原始 trace 算不出来，收据里的 28/17 次调用是人工整理的。
核对代码后这条要分两半说：

- **已经落盘的**：每支分支的 `status / evidence_count / llm_calls / tool_calls` 进了父臂 `sub_research` 的
  `tool_result.telemetry`（`research_harness.py` 把 telemetry 写进 audit 底稿）和 durable `branch_completed` 事件。
  分支合计数其实可以重算。
- **真没落盘的**：分支自己那个 `ContinuousAgentEpisode` 没接 `event_sink`，它的 `outcome.events`
  在 `ContinuousSubResearchWorker.run` 里被整段丢掉，`BranchResult` 只保留 `traces`。
  逐批 `tool_request` / `tool_error(tool_budget_exhausted)`、`remaining_slots_at_dispatch`、
  `_BranchBudgetView` 的 `allocated / remaining` 都在这一步消失。

所以「分支慢是不是每批帽 4 咬的」这个问题，当前 trace 回答不了；改帽前先让它能回答。

## 1. 改了什么（4 个 runtime 文件，standard / deep / max 的任何数字都没动）

| 处 | 改动 |
|---|---|
| `runtime/sub_research.py` | 新增 `BranchBatch`（一批的派发账：requested / succeeded / rejected_by_cap / timed_out / errored / rejected_other / tools + 派发时钟三元组）、`BranchBudgetReceipt`（allocated_calls / consumed_calls / allocated_seconds / remaining_seconds / batch_call_cap）、纯函数 `branch_batches_from_events(events)`；`BranchResult` 加 `stop_reason / batches / budget` 三个可选字段；协调器 `_run_one` 从 `_BranchBudgetView` 读出预算账挂上（worker 自报无效，与 `tool_calls` 同一纪律） |
| `runtime/continuous_sub_research.py` | worker 返回前把 `outcome.events` 切成 `batches`、带出 `stop_reason`（此前 partial 分支「为什么停」只能从 gaps 文案猜） |
| `runtime/sub_research_tool.py` | 新增 `branch_telemetry(branch)`：一支分支进收据的全部字段。有账写全，没账（取消 / worker 异常）不写键 |
| `runtime/agent_episode.py` | PLAN 路径与工具路径的 `branch_completed / branch_failed` payload 都改用 `branch_telemetry`——此前两处各写一份，字段已经漂开（事件有 tokens、telemetry 没有） |

派发账从**事件**重算而不是 worker 自述：每一批 `requested == succeeded + rejected_by_cap + timed_out + errored + rejected_other`
恒成立，对不上就是事件流本身缺条。`rejected_by_cap` 对应 `tool_budget_exhausted`，事件里每批帽与分支剩余次数两种来源同码，
靠同批的 `remaining_slots_at_dispatch` 分：剩余 ≥ requested 而仍被拒，就是帽咬的。

事件本体仍**不进**父账本：父臂一条 `tool_result` 的审计底稿装不下三支分支的整条事件流；进的是摘要。

## 2. 测试（6 新，5 个变异各击杀 ≥1）

| 测试 | 钉什么 | 变异 → 红 |
|---|---|---|
| `test_branch_batches_are_cut_at_model_turns_and_classify_every_tool_error` | 一条 `model_turn` 开一批；五类 error 码分类；无工具的模型轮不算批；末批无后继 `model_turn` 也入账；缺席时钟字段不写键 | 去掉末尾 `flush()` → 1F；`tool_budget_exhausted` 分类改掉 → 2F |
| `test_continuous_branch_worker_reports_per_batch_dispatch_and_the_cap_that_bit` | max 档分支拿 10 次 / 150s；模型一轮点 5 个 → 4 成功 1 `rejected_by_cap`，`remaining_slots_at_dispatch=10`，`batch_call_cap=4`（quick 标签的帽，不是 max 的 8） | worker 不带 `batches` → 1F |
| `test_branch_budget_receipt_comes_from_child_ledger_not_worker_claims` | worker 自报 99/99/9999 被协调器用子账本真值 8/1/60 覆盖 | 协调器不挂 `budget` → 2F |
| `test_failed_or_cancelled_branches_carry_no_budget_or_batches` | worker 异常的分支 `budget is None`、`batches == ()`；类型守门 | — |
| `test_telemetry_carries_budget_and_per_batch_dispatch_only_when_measured` | telemetry 有账写全、没账不写键；`branch_telemetry` 与 telemetry 逐字同源 | telemetry 去掉 `budget` → 2F |
| `test_branch_completed_event_carries_budget_and_batches_from_the_tool_path` | 工具路径的 durable `branch_completed` 带 `stop_reason / budget / batches`；同一 run 的 `sub_research` `tool_result.telemetry` 也带 | 同上 |

读数（解释器 `.venv-workbench/bin/python`，树 `~/fwp-wt-branch-trace` @ `504cbbc9` + 本改动）：
`test_sub_research.py` + `test_sub_research_tool.py` 33P/0F（基线 27）；邻接 10 个套件 272P/0F；
`ruff check .` 全仓通过；全量 pytest **7986P / 0F / 76S / 1 xfail**——脏树先跑一遍（286s），提交 `66de98c2` 后
干净树复跑同数（293s），`check_test_receipt.py --expect-revision HEAD --base-drift-max 5` 判「可采信」
（revision 一致 / 干净树 / 依赖指纹一致 / 基座漂移 0）。

## 3. 顺手核对的三条审查措辞（写进这里，免得下一个人再发现一遍）

1. **「max 没有贯穿子环路」要说准**：分支的**数值**预算随档位走（#615，max 10 次 / 150s，本次测试实测 `allocated_calls=10, allocated_seconds=150`）；
   钉死成 quick 的是**标签**，且是三层叠加——`sub_research._request` 的 `ResearchPolicy("quick", …)`、
   `continuous_sub_research` 契约的 `research_tier="quick"`、harness 的 `ModeSignals(user_mode="quick")`。
   标签真正改变的行为查到两条：`batch_call_cap` 只认 `tier == "max"` 才给 8（分支拿 4）；`ask.py` 把「任务档位=quick」写进分支模型的提示词。
   `derive_stage_caps` 按数值算，不受标签影响。
2. **「关键数字靠人工整理」分两半**：分支合计数早已落盘（见 §0）；没落盘的是分支内逐批账——本 PR 补的就是这一半。
3. **「repair 输入输出不能重算」不成立**：父臂修复轮的 `repair_goal`（`RepairGoal.to_dict()`，含 `unreachable_without_tools`）、
   `repair_reentry`（时钟三元组）、`model_turn(phase=repair)`（含模型回文）都在 durable 事件里。审查这条可以撤。

另：8792 当前进程（PID 56492，cwd `finance-workspace-d65ed0155eb9`）env 为 `WORKBENCH_RESEARCH_TIER=max`、
`WORKBENCH_TOOL_AUTHORIZATION=all`、`WORKBENCH_TOOL_MENU_HIDE=off`；代码默认三者皆关。`capability_switchboard.json`
注明 `sub_research` 只在 `AUTHORIZATION=all` 下进授权——max 档能力与 sub_research 可用性被同一个粗粒度 env 绑在一起，
这是「应由 registry + 显式 tier grant 控制」那条建议的具体形态。

## 4. 未做 / 下一步

- **未切 8792、未重跑那道题**。切流走既有 `scripts/audit_deploy_ledger.py record --action switch` 流程，回滚锚照旧；
  切完用同一道 `theme_track` 题（固态 vs 钠电）重跑一遍，读 `branch_completed.batches[*].rejected_by_cap` 与
  `budget.remaining_seconds`：若 `rejected_by_cap` 普遍 >0 且 `remaining_slots_at_dispatch ≥ requested`，帽 4 就是咬人的那道；
  若 `remaining_seconds ≈ 0` 而 `rejected_by_cap = 0`，慢的不是帽，是每批的工具本身（看 `stage_timeout_granted` 与 `timed_out`）。
- 在没有那份读数前，quick 每批帽 4 不动。
- 分层预留（发分支前先扣出判官 / 合成的 LLM 调用额度）是下一刀，接缝在 `api/app._deployment_execution_policy` 那本共享账。
- A/B/C 28 题仍等用户拍。
