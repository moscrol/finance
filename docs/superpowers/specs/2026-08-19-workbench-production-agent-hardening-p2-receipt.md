# P2 收据 — 预算 / deadline 不变量

- 日期：2026-08-19
- 树：`/Users/a77/fwp-wt-runtime-hardening` @ `88249857` + 未提交 P1/P2
- 前置：P0 / P1 收据
- 本轮只加测试，不改 ledger / verifier / promotion 生产实现

## 做了什么

新建 `intelligence/tests/test_root_budget_invariants.py`（10 条），钉 spec §7.2：

| 缺口 | 测试 |
|---|---|
| G3 `initial_calls == policy.max_steps` | 字面量 policy `max_steps=6`，不是硬编码 12 |
| 初始秒数 = `total - reserve` | quick 30−20=10 |
| 未知 tier hard cap | 回退 `max_steps` |
| grant ≤ 未分配余量 | calls 溢出拒绝；`calls_granted=0` 的秒数溢出也拒绝 |
| allocated − remaining 恒等式 | consume + grant 之后仍成立 |
| timeout ≤ remaining | 先拍 `remaining()` 再比，避免两次 `monotonic` 对打 |
| `bounded_stage` 子窗 | 不超过 `parent.expires_at - reserve` |
| 场景 6 | deadline 与 root seconds 可独立耗尽 |
| deep promotion 对齐 | tier / hard 24·240 / remaining 24·192 / `deadline.synthesis_reserve==48` |
| G4 | `episode_semantic_verifier.py` 源码无 `consume_call` / `root_budget` |

另：`test_run_store.py::test_add_artifact_currently_writes_after_terminal_claim` 是 **G5 观测**（P3 覆盖边界），不是预算不变量。

## 刻意没做的对账

`llm_calls` 与 `remaining_calls` **不是** 1:1：模型轮走 `consume_seconds`，工具批次走 `_settle_batch_calls` → `consume_call`。本轮不对那条假恒等式。语义 judge 吃的是合成窗，不借记 call——G4 钉成产品语义，不是漏接。

## 场景 1–5：映射已有测试，不新造重型夹具

| spec §7 验收场景 | 已有证据（gitea/main 即在） |
|---|---|
| 1 首轮烧检索窗 | `test_agent_episode.py::TestOpeningCallBorrowsOnlyTheSurplus`（run 8792 算术） |
| 2 工具批次结束时 root 秒数见底 | `test_continuous_turn_adapter.py` 在首轮 invoke 后 `consume_seconds(remaining)` 并断言 `remaining_seconds==0` |
| 3 promotion 后马上 repair | **本轮未单独串起来**。promotion 原子性在 `test_mode_governor.py`；repair grant 在 `test_repair_coordinator.py`。两者同 Episode 的时序夹具留到有生产事故再加 |
| 4 repair timeout → transient retry | `test_repair_coordinator.py::test_transient_retry_*` + `test_agent_episode.py` 里 `transient-retry-*` |
| 5 工具部分成功、部分 timeout | `test_episode_tool_batch.py::test_exception_timeout_and_empty_result_keep_original_call_order` |
| 6 deadline vs root seconds | 本轮新测 `test_deadline_and_root_seconds_can_exhaust_independently` |

## 命令与读数

可比套件（P1 文件 + 新不变量 + G5，不含 `test_mode_governor` 的既有 19 条）：把 `test_mode_governor.py` 算进同一次 pytest 是为了 promotion 对齐旁证。

```bash
.venv-workbench/bin/python -m pytest -q \
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
  intelligence/tests/test_mode_governor.py
```

`297 passed in 1.92s`（P1 的 267 + 不变量 10 + G5 1 + mode_governor 收集 19）
机器收据：`~/.finance-runtime/test-receipts/20260819T135019Z-88249857.json`
dirty=true（未提交）——只对本机此刻有效。

ruff：新测文件 All checks passed。

## 未做（按 spec 顺序，不要跳）

- 场景 3 的「promotion 后立即 repair」同 Episode 时序夹具
- P3：G5 加闸、G6 `late_result_discarded` 统一口径；进程重启保持「不支持」
- 提交 / 推送 / 合 main
