# 工单 #29 · 运行底座 P2：Durable 存储 + 意图/结算 + 恢复 + 配置快照 + 版本号（预立单）

> 母单：#27 `2026-09-07-runtime-base-endstate-design.md` §6.3、§7（切流）。前置：P1（#28）合入；§12 第 1 题（存储后端）与第 3 题（重启后只登记 / 自动恢复）拍板——未拍板按推荐：JSONL、只登记。
> 分支：`feat/runtime-base-p2-durable-store`。状态：⏳ 预立单，P1 合入后展开为逐步工单。
> 判据：INV-R2 / INV-R3 成立；`RuntimeHandle` 四类验收场景改回 08-15 原文（含**进程重启**）。

## 范围（正文以母单 §6.3 八条为准，此处只列不许漂的边界）

1. `services/episode_store.py`：`EpisodeStore` Protocol + `MemoryEpisodeStore` + `JsonlEpisodeStore`（`~/.finance-runtime/episodes/<episode_id>/{events.jsonl,state.json}`，`state.json` 用 `os.replace` 原子替换；撕裂末行整行丢弃）。SQLite 留接口不实现。
2. `EpisodeState` 完整状态，每次 phase 转移覆写；恢复只读它 + 事件点查，不重放推断、不从缺席推断。
3. 效果三明治：`model_intent{turn_id, reserved_sequence, timeout_asked}` 新增；`tool_request` 保持为意图并加 `replay`（来自 **`ToolSpec.replay: Literal["safe","never"] = "safe"`**——本单唯一的 harness 接触点，只加字段，12 个只读工具默认 safe，写工具将来注册时必须显式 never）；`tool_result / tool_error / model_turn / model_error` 是结算。意图 append 后 fsync，结算不 fsync。
4. `ContinuousAgentEpisode.restore(episode_id, store)`：pi §4.5 三行策略（模型意图无结算 → 捕获的重试策略允许则再试否则合成 `model_error{interrupted}`；工具意图无结算 → 双 `safe` 才重跑否则合成 `tool_error{interrupted}`；`cancel` 已 durable → 合成 `finish{stop_reason=cancelled}`）；合成事件用意图预留的 sequence。
5. `configure` 在 continuous 臂发完整快照；`restore` 只读快照不读活对象。
6. `EPISODE_LOG_VERSION = 1`；`EpisodeEvent.ignorable`；未登记且非 ignorable 的 kind → `unknown_required_kind` 拒绝。
7. `EpisodeFinalizer.recover` 的兜底 prompt 发 `prompt_assembled{source: finalizer}`（P0 已知边界 a）。
8. 接线：`GLMAgentRuntime.start` 构造 store；`continuous-episode.json` 改从 store 读（形状不变）；启动时 `list_open()` 只登记进 readiness。

## 验收（母单 §6.3 末段 + §10）

Tier A 每 phase × 每 crash 前缀（意图前 / 意图后结算前 / 结算后）构造 → 丢弃对象 → `restore` → 与不间断结果一致；写序 oracle 装在 `store.append` 断言「意图 seq < 效果开始 < 结算 seq」；`Memory` 与 `Jsonl` 同场景字节同结果；8792 单独切流 + 手工 `kill -9` 在飞 episode 一次，重启后 `list_open()` 可见且 `restore` 给出合成 finish。

## 不做

多进程写者、跨机复制、provider stream 续传、自动后台恢复（先手动）、SQLite 实现。
