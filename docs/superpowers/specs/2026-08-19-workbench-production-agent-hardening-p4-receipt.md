# P4 收据 — SLO 投影 + 离线发布门

- 日期：2026-08-19
- 树：`/Users/a77/fwp-wt-runtime-hardening` @ `88249857` + 未提交
- 前置：P3 收据
- **没改** `gate_receipt.RECEIPT_KEYS` / `claim_terminal_run` / `QueryPublishGuard.close`
- **没接** 自动回滚（`evaluate_release_gate` 固定 `rollback: "manual"`）

## 原理（为什么是投影，不是第二条遥测管线）

SLO 是「用已有收据算出的运营视图」，不是再写一份 event log。

| 方案 | 做什么 | 这里为什么不用 |
|---|---|---|
| 拉模式投影（本轮） | 从 run / report / private_artifact 抽字段再聚合 | 缺字段保持 `not_evaluated`，不发明墙钟 |
| 推模式埋点 | 循环里再打一套 metrics | 会变成第五套事实源，和 phase sidecar 抢权威 |
| 自动回滚开关 | 超阈值就切版本 | spec 要求先固定窗口/对象；本轮只做离线门 |

`not_evaluated` ≠ `0`：没测到「首次工具耗时」填 0，看起来像「工具瞬间返回」，会把 canary 洗绿。已评估队列里完成率真是 0，才允许数字 `0.0`。

`cancelled_rate` 按 C1 计：公开 status 是 `failed`，取消看 `stop_reason=cancelled`。按 `status==cancelled` 会计成永远 0。

## 做了什么

- 新建 `intelligence/services/runtime_slo.py`（services 层，不 import runtime）
- 新建 `intelligence/tests/test_runtime_slo.py`
- 发布门 7 项：revision 一致、身份完整、tool 配对、无终态冲突、预算可观察、回归绿、canary（degraded / provider_error / late_result）
- 缺 canary 字段 → 该项 `not_evaluated` → 整门 **fail closed**
- `time_to_first_tool` 恒为 `None`（durable events 没有墙钟，不发明）
- 棘轮：`RECEIPT_KEYS` 冻结；G6 字符串允许 SLO **读** `late_result_discarded_count`，写入点仍只有 `query_ledger.py`

## 命令与读数

与 P3 定向套件同一次跑，另加本轮文件：

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
  intelligence/tests/test_sub_research.py \
  intelligence/tests/test_runtime_slo.py \
  intelligence/tests/test_runtime_fault_matrix.py
```

`335 passed in 2.57s`（P3 的 316 + P4 9 + P5 10）
机器收据：`~/.finance-runtime/test-receipts/20260819T141858Z-88249857.json`

dirty=true。未提交 / 未推 / 不合 main。

## 下一步

P5 故障矩阵已在同一次套件里绿。总路线 P0–P5 代码与收据齐。仍未 live / 未 A/B。G7 进程重启继续标 capability gap。
