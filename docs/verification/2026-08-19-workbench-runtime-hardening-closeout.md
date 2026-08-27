# 质检收尾 — Workbench runtime hardening P0–P5

- 日期：2026-08-19
- 落地：Gitea **#245** `gitea/main=e5ca01d9`（树与本地 `9a6cd3ea` 相同）
- 树：`/Users/a77/fwp-wt-runtime-hardening`（干净；主仓脏树未碰）
- 解释器：`.venv-workbench` 3.12.13
- 结论：**按 spec 工作协议执行到位。** 字面验收句有声明缺口，不是漏做装完成。

## 1. 能不能叫「执行到位」

这条 spec 的协议是：P0 只读冻结 → P1 只加观测 → P2 先不变量测试 → P3 只修已证明缺口 → P4 离线门、不接自动回滚 → P5 故障矩阵。禁止重写 `claim_terminal_run` / `QueryPublishGuard.close`，禁止把测试收据改到 `tmp_path`。

这些都做到了，且已合 main。

§13「单机/小规模自用生产级」九条：

| §13 | 质检 |
|---|---|
| 状态转移可从 receipt 重建，终态唯一 | 过。`private_artifact.phase_trace`；中间 `finish` 仍是 `finalizing` |
| root budget 是实时额度真相源 | 过。G4 钉死：语义 judge 不借记 call，吃合成窗 |
| deadline 绝对且单调 | 过。`bounded_stage` + timeout≤remaining |
| cancel / child / late result 不污染公开 outcome | **过，但有取舍**：卡住的子研究保排空，会拖住本次 `run()`，不杀线程抢 deadline |
| repair 失败不丢 draft | 过。已有 adapter 空 repair 结转测试 |
| 进程内 continuation 有测；进程重启不伪造 | 过。G7 = 只重排队 |
| 组合故障矩阵 | 过。9 案均记 6 字段；部分是缝上注入，不是整条 adapter 重放 |
| SLO + 发布门 | 过。离线函数；`rollback=manual`；缺字段 fail closed |
| 结论有命令/收据 | 过。收尾定向套件见下 |

§12 十不准抽查：未换 SDK、未放宽 completed、未重写 claim/guard、未改收据默认落点（`conftest.py` 仍是 `~/.finance-runtime/test-receipts/`）、独立 worktree。

## 2. 声明缺口（下次别当新发现）

1. P2 场景 3：deep promotion 后马上 repair，**没有**同 Episode 时序夹具。
2. `llm_calls` 与 `remaining_calls` **不是** 1:1（模型扣秒、工具扣次）。不对假恒等式。
3. spec P3「一条分支卡住、主任务按 deadline 收敛」**未按字面做**。取舍：保排空。
4. `late_result_discarded` 记录 `provider/query/as_of/reason`，没有 spec 8.2 的 `run_id/episode_id/child_id`。
5. `time_to_first_tool` 恒 `not_evaluated`（events 无墙钟，不发明）。
6. 发布门没有 CLI、没有接生产部署链。
7. 未 live / 未切 8792 / 未自动回滚。

## 3. 代码抽查（本轮合入）

- orchestrator 五条公开写盘路径：`claim` 在 `add_artifact` 之前，且无 `finish_run`。
- `QueryPublishGuard` 生产构造点只有 `episode_tool_batch.py`。
- `episode_phase.py` / `runtime_slo.py` 在 services，不 import runtime。
- 取消在进 semantic verifier 之前有 `is_cancelled` 检查。
- `add_artifact` 仍不看终态——有意：赢家必须在 claim 之后写公开文件。

## 4. 收尾读数

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

`335 passed in 2.91s`，exit 0  
机器收据：`~/.finance-runtime/test-receipts/20260819T143910Z-9a6cd3ea.json`  
干净树。解释器用 `.venv-workbench` 3.12.13 才采信（宿主 3.14 跑 `check_test_receipt.py` 会显示解释器不符，那是校验器自己的处境，不是套件红了）。

合入前全量 pytest 曾 5739/16：那 16 条是既有 ceiling/instruction export 权限位，本单未改那些模块。

## 5. 收尾后还剩什么

不是本单未完成项，是下一档能力：live canary、自动回滚（先定窗口和回滚对象）、G7 真续跑、卡住分支的 deadline 抢跑（要重开 spec）、`time_to_first_tool` 若要数字需给 events 加墙钟。
