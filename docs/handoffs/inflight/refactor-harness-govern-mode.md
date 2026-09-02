# 在途交接 · refactor/harness-govern-mode

更新：2026-09-02 13:30 CST · **已闭环：PR #529 已合 `gitea/main=b8cc9a73`，主干门禁可采信（7384P/5F 同基线红、webapp 70P 绿，见 `inflight/main.md` 顶行），8792 未切。** 后续见 `inflight/refactor-harness-sub-research-projection.md`。

## 一句话

`ResearchHarness` 八方法 → 九方法：`govern_mode(task_frame, plan, context, can_branch) ->
ModeGovernance{context, decision, message}`。深度裁决（信号 → 依赖修正 → `ModeGovernor.decide/apply`）
与 `MODE_DECISION` 文案整段从 `ContinuousAgentEpisode._decide_mode` / `_append_mode_decision_message`
搬进 harness；`mode_governor` / `mode_signals` 两个注入件搬到 `FinanceResearchHarness` 构造器。
`HarnessReferenceLoop` 同样经它裁决——**P2' 钉住的最后一条残余（Episode 独有的 `MODE_DECISION`）
归零，有 PLAN 脚本两条 loop 全程消息一致。** 前序 P0–P2' 已全部合 main（`5292175c`）。

spec：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`（§4 #5 → P2 已实施）
收据：`docs/verification/2026-09-02-research-harness-loop-decouple.md`（P2 govern_mode 节）

## 改动面

| 文件 | 动作 |
|---|---|
| `intelligence/services/research_harness.py` | `ModeGovernance` / `ModeSignalsFactory` / `default_mode_signals`；`FinanceResearchHarness.__init__(mode_governor=, mode_signals=)`；`govern_mode` |
| `intelligence/runtime/agent_episode.py` | `_decide_mode` 只剩问 harness → 记 `mode_decision` → 换 context → 更新 continuation；`_append_mode_decision_message` 取 `governance.message`；删 `_default_mode_signals`；构造器 `mode_governor` / `mode_signals` 转交默认 harness，自带 harness 时再传 → `ValueError` |
| `intelligence/runtime/harness_reference_loop.py` | PLAN 后 `govern_mode(can_branch=False)`，消息与 Episode 同位追加，`max_slots` 随升档 context 重算 |
| `intelligence/tests/test_research_harness.py` | 29 → 32 |
| `intelligence/tests/test_harness_reference_loop.py` | 有 PLAN 用例：「差恰一条」→「全程一致」 |
| `glm_agent_runtime.py` / `continuous_sub_research.py` | **零改动**（仍传 mode 注入件给 Episode，由 Episode 转交） |

## 红线遵守自证

- `mode_governor.py` 判定零改动；文案逐字搬运（测试按 JSON 逐字段钉）。
- 模型可见字节零改动；durable `mode_decision` 事件零改动。
- `services/` 不 import `runtime/`；生产装配零改动；8792 未碰。

## 下一步（按序）

1. 用户确认 → 合 PR #529（合后主干门禁顺带复核 `test_agent_review_worker` 低负载下绿）。
2. **P2 子研究**：`_run_sub_research`（需 `SubResearchCoordinator`，持状态）与 `_append_sub_research_message`
   的消息投影（三个序号函数）——这是 Episode 剩下的最后一段「对模型说话」的领域文案。
3. **P2 `repair_policy`**：`_recover_finalization` / `_repair_model_complete` / `RepairGoal` /
   `apply_unreachable_downgrade` / `EpisodeFinalizer`——先画状态机。
4. **P2'-live**：8792 切到含 harness 的 revision 后，参考 loop 当第四臂跑 09-01 同题。烧配额，另拍。

## 顺手发现（不属本单）

- Episode 构造器上的 `mode_governor` / `mode_signals` 现在只是转交壳；两处生产调用方
  （`glm_agent_runtime` / `continuous_sub_research`）若改成直接构造 `FinanceResearchHarness(...)`
  传 `harness=`，这两个形参就能删掉。留给合并后的小刀。
