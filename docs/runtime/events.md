<!-- 由 scripts/gen_runtime_catalog.py 从源码生成，不要手改。
     再生成：python3 scripts/gen_runtime_catalog.py ；校验：--check（pytest test_runtime_catalog 也会比对）。 -->

# 运行底座事件目录

车道：durable 进重放日志与对账权威；live 只走实时出口。阶段来自 `episode_phase`，L1 步来自 `normalize_harness_trace`（评测口径），投影剔正文的字段来自 `episode_messages.MODEL_VISIBLE_TEXT_FIELDS`（对外 artifact 只留 sha256 与字符数）。

durable 30 种 · live 3 种

| kind | 车道 | 阶段 | L1 步 | 投影剔正文字段 | 发射文件 |
|---|---|---|---|---|---|
| `branch_completed` | durable | research | observe | — | `intelligence/runtime/agent_episode.py` |
| `branch_failed` | durable | research | observe | — | `intelligence/runtime/agent_episode.py` |
| `branch_started` | durable | research | retrieve | — | `intelligence/runtime/agent_episode.py` |
| `branch_tool` | durable | research | — | — | `intelligence/runtime/agent_episode.py` |
| `configure` | durable | planning | configure | — | `intelligence/runtime/codex_headless_runtime.py` |
| `finalization` | durable | finalizing | synthesize | — | `intelligence/runtime/agent_episode.py`, `intelligence/runtime/harness_reference_loop.py`, `intelligence/runtime/headless_tool_gateway.py` |
| `finalization_recovery_outcome` | durable | finalizing | — | — | `intelligence/runtime/agent_episode.py` |
| `finalization_recovery_started` | durable | finalizing | synthesize | — | `intelligence/runtime/agent_episode.py` |
| `finish` | durable | finalizing | stop | — | `intelligence/runtime/agent_episode.py`, `intelligence/runtime/codex_headless_runtime.py`, `intelligence/runtime/dsh_stub_runtime.py`, `intelligence/runtime/harness_reference_loop.py`, `intelligence/runtime/openai_agents_runtime.py` |
| `history_compacted` | durable | — | — | folded[].model_content | `intelligence/runtime/agent_episode.py` |
| `invalid_action` | durable | research | observe | — | `intelligence/runtime/agent_episode.py`, `intelligence/runtime/harness_reference_loop.py` |
| `mode_decision` | durable | planning | plan | — | `intelligence/runtime/agent_episode.py`, `intelligence/runtime/harness_reference_loop.py` |
| `model_error` | durable | research | — | — | `intelligence/runtime/agent_episode.py`, `intelligence/runtime/harness_reference_loop.py` |
| `model_input` | durable | — | intent | content | `intelligence/services/episode_messages.py` |
| `model_turn` | durable | research | — | — | `intelligence/runtime/agent_episode.py`, `intelligence/runtime/dsh_stub_runtime.py`, `intelligence/runtime/harness_reference_loop.py`, `intelligence/runtime/openai_agents_runtime.py` |
| `plan` | durable | planning | plan | — | `intelligence/runtime/agent_episode.py`, `intelligence/runtime/codex_headless_runtime.py`, `intelligence/runtime/harness_reference_loop.py` |
| `prefetch` | durable | — | — | — | `intelligence/runtime/agent_episode.py` |
| `prompt_assembled` | durable | — | configure | system, user | `intelligence/services/episode_messages.py` |
| `repair_goal` | durable | repair | plan | — | `intelligence/runtime/agent_episode.py`, `intelligence/runtime/harness_reference_loop.py`, `intelligence/runtime/openai_agents_runtime.py` |
| `repair_model_retry` | durable | repair | — | — | `intelligence/runtime/agent_episode.py` |
| `repair_reentry` | durable | repair | — | — | `intelligence/runtime/agent_episode.py`, `intelligence/runtime/openai_agents_runtime.py` |
| `root_budget_overdraft` | durable | — | observe | — | `intelligence/runtime/headless_tool_gateway.py` |
| `runtime_result` | durable | — | observe | — | `intelligence/runtime/agent_episode.py`, `intelligence/runtime/codex_headless_runtime.py`, `intelligence/runtime/openai_agents_runtime.py` |
| `task` | durable | planning | intent | — | `intelligence/runtime/agent_episode.py`, `intelligence/runtime/codex_headless_runtime.py`, `intelligence/runtime/dsh_stub_runtime.py`, `intelligence/runtime/harness_reference_loop.py`, `intelligence/runtime/openai_agents_runtime.py` |
| `tool_budget_state` | durable | — | observe | model_content | `intelligence/services/episode_messages.py` |
| `tool_closed` | durable | research | — | — | `intelligence/runtime/openai_agents_runtime.py` |
| `tool_error` | durable | research | observe | model_content | `intelligence/runtime/agent_episode.py`, `intelligence/runtime/harness_reference_loop.py`, `intelligence/runtime/headless_tool_gateway.py`, `intelligence/runtime/openai_agents_runtime.py` |
| `tool_menu` | durable | — | — | — | `intelligence/runtime/agent_episode.py`, `intelligence/runtime/harness_reference_loop.py` |
| `tool_request` | durable | research | tool | — | `intelligence/runtime/agent_episode.py`, `intelligence/runtime/harness_reference_loop.py`, `intelligence/runtime/headless_tool_gateway.py`, `intelligence/runtime/openai_agents_runtime.py` |
| `tool_result` | durable | research | observe | model_content | `intelligence/runtime/agent_episode.py`, `intelligence/runtime/harness_reference_loop.py`, `intelligence/runtime/headless_tool_gateway.py`, `intelligence/runtime/openai_agents_runtime.py` |
| `tool/error` | live | — | — | — | — |
| `tool/pre_execute` | live | — | — | — | — |
| `tool/result` | live | — | — | — | — |
