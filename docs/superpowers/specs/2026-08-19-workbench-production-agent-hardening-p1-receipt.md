# P1 观测接缝收据 — Episode phase projection

- 日期：2026-08-19
- 树：`/Users/a77/fwp-wt-runtime-hardening` @ `88249857` + 未提交 P1
- 前置：`docs/superpowers/specs/2026-08-19-workbench-production-agent-hardening-p0-receipt.md`
- 本轮只加观测，不改公开答案 / repair 准入 / durable `events[]`

## 做了什么

第五个 sidecar：`intelligence/services/episode_phase.py`

- 不进 `DURABLE_EVENT_KINDS`，不改 `project_durable_events` 的 `events[]` 形状
- `finish` 事件映射为 `finalizing`，公开终态只来自 adapter 的 `public_outcome`
- 非法转移和终态后再记：写进 `anomalies`，不抛进主循环（与 `episode_projection` 同一条 artifact 边界）
- `ContinuousTurnAdapter._run_episode` 在 structural / repair / semantic / 公开终态点上记相；`private_artifact["phase_trace"]` 始终出现

## 命令与读数

```bash
.venv-workbench/bin/python -m pytest -q \
  intelligence/tests/test_episode_phase.py \
  intelligence/tests/test_episode_seam_ladder.py \
  intelligence/tests/test_episode_session.py \
  intelligence/tests/test_episode_finalizer.py \
  intelligence/tests/test_continuous_turn_adapter.py \
  intelligence/tests/test_run_store.py \
  intelligence/tests/test_p1b_runtime.py \
  intelligence/tests/test_repair_coordinator.py \
  intelligence/tests/test_episode_progress.py
```

`267 passed in 1.99s`（P0 的 259 + 本轮 8）
机器收据：`~/.finance-runtime/test-receipts/20260819T124928Z-88249857.json`
dirty=true（未提交 `episode_phase` / adapter 接线）——只对本机此刻有效。

ruff：上述改动文件 All checks passed。

## 未做（按 spec 顺序，不要跳）

- P2 通用预算不变量测试（G3/G4）
- P3 覆盖边界：`add_artifact` 终态闸（G5）、`late_result_discarded` 统一口径（G6）
- 进程重启续 Episode（G7，保持「不支持」）
- 提交 / 推送 / 合 main
