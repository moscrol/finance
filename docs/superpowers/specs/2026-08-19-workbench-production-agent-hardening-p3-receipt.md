# P3 收据 — 终态写入覆盖：审计 + G5 + G6 + 子研究隔离取舍

- 日期：2026-08-19
- 树：`/Users/a77/fwp-wt-runtime-hardening` @ `88249857` + 未提交
- 前置：P2 收据
- **没改** `claim_terminal_run` / `QueryPublishGuard.close` / `add_artifact` / `SubResearchCoordinator` 的执行语义

## 审计结论（仍成立）

`add_artifact` 不看 `run.status`。G5 已让旁路先认领。G7 进程重启仍不支持。

## G5 / G6（此前切片）

- G5：lane / cancel / fail / legacy ask 与连续路径对齐，先 `_claim_terminal_run`。
- G6：`QueryLedger` sidecar `late_result_discarded`；guard 仍只在 `episode_tool_batch` 构造。

## 子研究：不接第二扇 guard

`SubResearchCoordinator.run` **同步排空**：`as_completed` 全部消费完才返回，`with ThreadPoolExecutor` 再 join。注释写死：改成 fire-and-forget 必须重开 spec 排空档。

因此：

| 层 | 晚到隔离 |
|---|---|
| 工具批次 / query cache | `QueryPublishGuard`（唯一生产构造点） |
| 子研究分支 | 同步排空；`run` 返回时分支线程已结束 |
| repair 工具 | 走同一 tool batch / guard |
| 卡住的分支 vs deadline | **取舍：保排空，不杀线程。** 卡住会拖住本次 `run()`，避免线程还活着就往 `evidence_sink` 里追加 |

spec 验收「一条分支卡住、主任务按 deadline 收敛」和「关闭时无后台分支泄漏」不能同时用杀线程做到。本轮钉住现有选择，不伪造 deadline 抢跑。

新测试：

- `test_cancelled_coordinator_does_not_launch_workers`
- `test_cancelled_branch_start_does_not_call_worker`
- `test_coordinator_run_does_not_return_while_branch_threads_are_alive`
- `test_sub_research_coordinator_does_not_grow_a_second_publish_guard`

进程内 repair 失败保 draft：已有 `test_adapter_keeps_the_answer_when_a_repair_comes_back_empty`。

## 命令与读数

```bash
.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_runtime_coverage_boundaries.py \
  intelligence/tests/test_root_budget_invariants.py \
  intelligence/tests/test_episode_phase.py \
  intelligence/tests/test_episode_seam_ladder.py \
  intelligence/tests/test_episode_session.py \
  intelligence/tests/test_episode_finalizer.py \
  intelligence/tests/test_continuous_turn_adapter.py \
  intelligence/tests/test_run_store.py \
  intelligence/tests/test_p1b_runtime.py \
  intelligence/tests/test_repair_coordinator.py \
  intelligence/tests/test_episode_progress.py \
  intelligence/tests/test_mode_governor.py \
  intelligence/tests/test_conversation_orchestrator.py::test_cancel_does_not_overwrite_artifacts_after_lost_claim \
  intelligence/tests/test_sub_research.py
```

`316 passed in 2.22s`
机器收据：`~/.finance-runtime/test-receipts/20260819T140712Z-88249857.json`

dirty=true。未提交 / 未推 / 不合 main。

## 下一步

P3 覆盖已收口到「声明的取舍」。再往下是 **P4**（SLO / 发布门），或你确认要改子研究排空策略。G7 继续标 capability gap。
