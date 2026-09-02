# 在途交接 · refactor/harness-interpret-turn

更新：2026-09-02 · **P1b 已实施、离线全绿，未开 PR、未合 main、未切 8792。** 等用户确认。

## 一句话

`ResearchHarness` 从四方法扩到六方法：`interpret_plan`（PLAN 识别 + 修订合法性出 loop）与
`steering_message`（三段焊死的领域文案——PLAN 无效回灌、终局无效回灌、finalization 提示——
出 loop）；另两条 loop 修复 prompt 的 `build_episode_input` / `build_episode_instructions`
改取 `assemble_prompt` 两半。行为等价（文案字节钉死、`interpret_plan` 与原两处调用逐字同义）。
前序 P0 + P1a 已由 PR #525 合入 main `71a2c846`（主干门禁可采信，见收据）。

spec：`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`（§4 #4 / #12 → P1b 已实施；§9 P1c 待做）
收据：`docs/verification/2026-09-02-research-harness-loop-decouple.md`（P1b 节）

## 改动面

| 文件 | 动作 |
|---|---|
| `intelligence/services/research_harness.py` | `SteeringKind` Literal；Protocol + 默认实现各加 `steering_message` / `interpret_plan` |
| `intelligence/runtime/agent_episode.py` | PLAN 块 `parse_plan_candidate`+`validate_plan_revision` → `harness.interpret_plan`（try/except/else 拍平一层）；两处回灌文案 + `_begin_finalization`（静态→实例）改取 `harness.steering_message`；去 2 个 import |
| `intelligence/runtime/openai_agents_runtime.py` | 修复轮 `repair_system, repair_user = harness.assemble_prompt(...)`；去 `build_episode_*` import |
| `intelligence/runtime/codex_headless_runtime.py` | 修复 prompt 任务 JSON 取 `assemble_prompt(...)[1]`；去 `build_episode_input` import |
| `intelligence/tests/test_research_harness.py` | 19 → 24：等价 ×2、顺序改成七次调用、有牙 ×2、棘轮扩到 `research_plan` 与 `build_episode_*` |

生产构造零改动（三条 loop 都拿默认 harness）。

## 红线遵守自证

- 未改秒数 / 档位 / reserve；未改 `episode_protocol.py` / `research_plan.py` 判定。
- 模型可见字节零改动：三段文案逐字搬运并按字节钉测试；修复 prompt 两半与原调用同函数。
- durable 事件零改动。`services/` 不 import `runtime/`。8792 / 启动器 / 快照未碰。

## 下一步（按序）

1. 用户确认 → 开 PR 合 main（等价四件套：ruff ✅ pytest 见收据 layer_audit ✅）。
2. **P1c**：`_EpisodeToolAccumulator.consume` 的模型视图投影抽成 `harness.project_tool_result`
   （dsh `tools/result` 位）。字节等价门：durable `tool_result` payload 与 `role=tool` 消息内容。
   事件发射、证据去重、traces 留 loop。
3. **P2'**：`finance-base-ab/pi-shape/packages/agent_core` 里写只调六方法 + registry 的最小 loop，
   跑 09-01 同题。P1c 做完它才「是同一台机器」。

## 顺手发现（不属本单）

- 与 P0/P1a 交接单同：`episode_scope.py` 文首过时；INTEGRITY 的 outcome `stop_reason` 仍写
  `invalid_model_finish`；三条 loop gap 口径不一致。
