# 在途交接 · refactor/harness-tool-result-projection

更新：2026-09-02 · **P1c 已实施、离线全绿，Gitea PR #527 已开（http://127.0.0.1:3300/a77/finance-workspace-private/pulls/527），叠在 P1b（PR #526）之上，未合 main、未切 8792。** 堆叠链：P1b 未合前本分支不能单独合（`git rev-list --left-right --count` 左侧为 0）。

## 一句话

`ResearchHarness` 六方法 → 八方法：`project_tool_result`（一次成功观察 → 审计底稿 + 模型正文 +
去重账本新状态）与 `project_tool_error`（失败 → 模型看的结构化结果）。这是 dsh `tools/result`
（definition-owned `finalizeContent`）的位置，也是第二条 loop「是同一台机器」的最后一块硬前置：
**模型看到的一切工具结果、审计留下的一切工具底稿，字节都来自 harness**。loop 只管账。

spec：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`（§4 #6 → P1c 已实施）
收据：`docs/verification/2026-09-02-research-harness-loop-decouple.md`（P1c 节）

## 改动面

| 文件 | 动作 |
|---|---|
| `intelligence/services/research_harness.py` | `ToolResultProjection{audit_payload, model_content, seen_prose}`；Protocol + 默认实现各加两方法（成功分支 ~40 行逐字搬入） |
| `intelligence/runtime/agent_episode.py` | `_EpisodeToolAccumulator` 加 `harness` 字段（默认金融，`run()` 传 `self._harness`）；成功分支只剩证据去重 → 问 harness → 记事件 → 追加消息；`_append_tool_error` payload 取 harness；去 import `prune_tool_observation` / `budget_tool_observation` |
| `intelligence/tests/test_research_harness.py` | 24 → 29 |

## 离线读数（对分支尖成立，`.venv-workbench` 规程壳）

见收据 P1c 节。定向 314P/2S；全量见收据表。ruff 绿；`layer_audit` ERROR 0。

**边界实测**：loop 在最后一条工具消息叠 `runtime_budget`（底座预算可见性，spec §4 #9 不抽）。
模型看到的 = harness 正文 + 这一个键；测试 `set(facing) == {"ok","view","runtime_budget"}` 钉死。

## 红线遵守自证

- 模型可见字节零改动（投影逐字搬运；`test_agent_episode` 对工具消息正文的既有断言全绿）。
- durable `tool_result` / `tool_error` payload 零改动（`call_id` / timing 仍由 loop 叠加）。
- `services/` 不 import `runtime/`。生产构造零改动。8792 未碰。

## 下一步（按序）

1. 用户确认 → 先合 #526（P1b）再合 #527（本分支；堆叠链不能改序）。
2. **P2**：修复协调（`_recover_finalization` / `_repair_model_complete` / `RepairGoal` / `apply_unreachable_downgrade` / `EpisodeFinalizer`）、mode 治理与子研究消息投影（`_append_sub_research_message` 里剩下的三个序号函数）、空池回退。这些持状态、改控制流，先画状态机再切。
3. **P2'**：`finance-base-ab/pi-shape/packages/agent_core` 里写只调八方法 + registry 的最小 loop，跑 09-01 同题（硬门沿用 09-01：首轮 `task_frame_hash` / `input_tokens`±3 / `financial_data`）。

## 顺手发现（不属本单）

- 工具壳 `cat <&3` 楔死复现一次（定向 pytest 5 分钟无输出，`ps` 见 `cat` 子进程），杀掉重跑无污染——与台账 08-27 记录同形。
