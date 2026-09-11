# 工具面收尾三件——工单 #39 收据

> 日期：2026-09-08 · 工单 `docs/superpowers/specs/2026-09-08-tool-surface-closeout-workorder.md`（PR #666 分支）

## ① #567 工具窗地板：前向合并完成，等用户拍

- `feat/tool-window-floors` ← `gitea/main@8e452e72`，合并提交 `a961958f`。冲突两处按「都留」解：`MIN_WINDOW_SECONDS` 六条齐全（`kb_search 20 / evidence_search 30` 实测尾巴、`web_search / news_search / web_fetch 5.0` 零授予护栏、`sub_research` 设计常数），测试改名 `test_production_registry_declares_three_kinds_of_floor`。本机 `merge-tree` 对 main clean。
- 数字重核：`scripts/offline_tool_duration_floor.py` 普查（`users/*/runs/*/continuous-episode.json` 全量）——`web_search n=8 p50 2.72 / p95 4.755 / max 5.03`、`news_search n=64 p50 1.527 / p95 8.68`、`web_fetch` **仍无成功样本**。与 #567 注释里的读数完全一致（普查输入自 09-03 起没有新增网络工具成功样本），三条 5.0 维持：`web_search` 压住 p95；`news_search` 有意不按 p95（会遮掉大量 p50 1.5s 的成功窗）；`web_fetch` 仍是 [推断]。
- 目标套件 97P（`test_episode_tool_batch / test_sub_research_tool / test_tool_contract_gate / test_tool_behavior_contract`）；干净树全量门禁见下。

## ② #568 deep 不经 PLAN：前向合并完成，**候选口两臂未跑**

- `feat/deep-observable-without-plan` ← main，无冲突（`13ec7107`）；改动只在 `mode_governor.py` + 其测试，22P。
- 两臂 n=3 **未跑**：工单要求先看 `quota-pool-state.json`，本机 `~/.finance-runtime` 下**没有这个文件**（`find -name quota-pool-state.json` 空），无法判定 5h 窗余量；且候选口 8799 未起。**不出结论**，六格表留空等窗口——需要跑时按工单 §2.2 起 8799 同题两臂。

## ③ `sub_research` 分支 × 全局 8 worker 争用

**能从已有收据算出的部分**（父臂侧）：`tool_result.payload.queued_ms` 是每条工具在全局线程池里排队的毫秒数（`episode_tool_batch.py:164`）。扫 `users/*/runs/*/continuous-episode.json`（mtime ≥ 09-03，60 个 run）：

| 集合 | n（tool_result） | p50 | p95 | max | > 1s 占比 |
|---|---:|---:|---:|---:|---:|
| 有 `sub_research` 分支的 run（父臂事件流） | 297 | **0 ms** | **8 ms** | 262 ms | 0.0% |
| 无分支的 run | 235 | 2 ms | 29 ms | 189 ms | 0.0% |

父臂侧：分支在跑时父臂自己的工具排队 p95 8 ms——**争用不是变量**（工单 §2.3 判据：p95 < 1s 关闭此项）。

**算不出的部分**（分支侧）：分支内部的 `tool_result` 事件在 worker 返回时被丢，`BranchBatch` 的三元组是预算 / 时钟快照（`remaining_slots_at_dispatch / stage_timeout_granted / episode_remaining_at_dispatch`），不含排队时间。按工单 §2.3 第 2 步补字段：`BranchBatch.queue_wait_ms_max`——本批 `tool_result / tool_error.queued_ms` 的最大值，由 `branch_batches_from_events` 从事件重算（不由 worker 自报），没测到留 None、`to_dict` 不写键。新测试 `test_branch_batches_record_max_queue_wait_from_results_not_from_worker_claims`（含变异说明：只挂 `tool_result` 不挂 `tool_error` → 红）；既有 `test_continuous_branch_worker_reports_per_batch_dispatch_and_the_cap_that_bit` 断言加该键（真跑线程池时值存在且 < 1s）。**池大小、×3、帽 4 全部未动。**

下一发带分支的 live 探针之后，`branch_completed.batches[*].queue_wait_ms_max` 就有分支侧读数；若 p95 ≥ 分支单批工具 p50 的 20%，再按工单写候选处置交拍。

## 门禁

| 分支 | ruff | pytest（干净树全量） | 收据 |
|---|---|---|---|
| `feat/tool-window-floors` @ `a961958f` | 见 `/tmp/gate-p567.log` | 见同文件 | 合入前回填 |
| `feat/deep-observable-without-plan` @ `13ec7107` | 见 `/tmp/gate-p568.log` | 见同文件 | 合入前回填 |
| `feat/branch-batch-queue-wait`（本收据所在） | 0 | 目标套件 54P；全量合入前跑 | — |

## 未做

- #568 两臂 live（额度文件缺、候选口未起）。
- #659 n=6 验收（留作者）。
