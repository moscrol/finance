# 在途交接 · refactor/harness-sub-research-projection

更新：2026-09-02 · **P2 子研究消息投影已实施、离线全绿，未开 PR、未合 main、未切 8792。** 等用户确认。

## 一句话

`ResearchHarness` 九方法 → 十方法：`project_sub_research(branches, refused_reason, evidence) -> str`。
`ContinuousAgentEpisode._append_sub_research_message` 的 `SUB_RESEARCH_RESULTS` JSON 整段进 harness；
分支类型用结构 Protocol `BranchOutcome` 接（runtime 的 `BranchResult` 天然满足，services 不 import
runtime）。这一刀之后 **Episode 里不再有任何一段领域对模型说的话**，`agent_episode` 从
`episode_protocol` 只剩常量 + `finish_rejection_fields`。前序 P0–P2 govern_mode 已全部合 main（`b8cc9a73`）。

spec：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`
收据：`docs/verification/2026-09-02-research-harness-loop-decouple.md`（P2 子研究节）

## 改动面

| 文件 | 动作 |
|---|---|
| `intelligence/services/research_harness.py` | `BranchOutcome`（结构类型）+ `project_sub_research` |
| `intelligence/runtime/agent_episode.py` | `_append_sub_research_message` 静态→实例、取 harness；去 4 个 import |
| `intelligence/tests/test_research_harness.py` | 32 → 34（投影逐字段等价 + 棘轮） |
| `_run_sub_research` / `SubResearchCoordinator` | **零改动**（起分支、排空、记事件是底座） |

## 红线遵守自证

- 文案逐字搬运；模型可见字节零改动（`test_agent_episode` 深档分支用例仍绿）；durable 事件零改动。
- `services/` 不 import `runtime/`（结构类型替代 import）；生产装配零改动；8792 未碰。

## 下一步（按序）

1. 用户确认 → 开 PR 合 main。
2. **P2 `repair_policy`**（先画状态机）：入口清单见 spec §9——`resume()` 修复轮、`_recover_finalization`、
   `apply_unreachable_downgrade` / `unreachable_repair_goal`、`grant_for_transient_model_retry`。
   要先把「什么时候允许再来一轮」（预算，底座）与「修什么、修复提示怎么写、修完算不算进步」（领域）两类边画清。
3. **P2 空池回退**（`_maybe_execute_empty_pool_fallback`）。
4. **小刀**：`glm_agent_runtime` / `continuous_sub_research` 改成直接构造 `FinanceResearchHarness(...)`
   传 `harness=`，删掉 Episode 构造器上的 `mode_governor` / `mode_signals` 转交壳。
5. **P2'-live**：8792 切到含 harness 的 revision 后，参考 loop 当第四臂跑 09-01 同题。烧配额，另拍。
