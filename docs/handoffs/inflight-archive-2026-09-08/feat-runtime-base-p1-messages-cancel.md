# feat/runtime-base-p1-messages-cancel · 运行底座 P1（工单 #28）

更新：2026-09-07 · 树 `/Users/a77/fwp-wt-runtime-base` · 叠在 `spec/runtime-base-endstate`（PR #620，未合）之上

## 做什么
母单 #27 §6.2：`EpisodeMessage` 自己的消息类型 / `CancelSignal` 类型化取消 / `tool_not_dispatched` 与 `tool_timeout` 分码。用户「开单执行」，§12 未拍板按推荐。工单正文 `2026-09-07-runtime-base-p1-messages-cancel-workorder.md`（含落地记录）。

## 当前状态
- 三刀已提交：`0b3a0e94`（A 消息类型）、`c6807038`（B/C/D）。目录 `--check` 一致。
- 门禁：提交前一轮 8017P/4F → 4 条全是接缝改动的既有断言（`probe_tool_arguments` 拿内部消息当 dict、`test_workbench_api` 断言谓词对象同一），已改；提交后干净树全量正在跑，读数看 `~/.finance-runtime/test-receipts/` 最新收据（revision `c6807038`）。
- **模型可见改动只有一格**：零授权未派发 `error: tool_timeout → tool_not_dispatched`（detail 仍 `stage_timeout_granted=0`）。其余线格式逐字节不变（并跑对照 + 全套严格派生断言为证）。
- P2–P4 预立单 #29–#31 已登记 INDEX，等 P1 合入后展开。

## 已做
- PR #624（base `spec/runtime-base-endstate`）已开，冲突探测 clean。
- live 探针已跑（`finance-base-ab/out/reference-loop-0907-p1/`，模型 `gpt-5.6-sol`）：两臂 `model_finish`、同答案 1741.44、system 哈希同、首轮都点 `financial_data`、零工具错误；`tool_not_dispatched` 未触发（实授窗 529 s）。对照唯一红 = 首轮 token 差 693，用 `prompt_assembled` 哈希判出是台架 shim 不绑 `sub_research` 的既有不对称（非 P1，见工单 F）。

## 卡点 / 需要用户的
1. #620（P0）→ #624（P1）合并确认；#620 合后 #624 rebase 到 main。
2. 仓外：`finance-base-ab/shape_lib/reference_loop_arm.py` 的 shim 要不要也绑 `sub_research`（否则契约授 `sub_research` 时 ±3 门永远红）——不在本仓，等你定。

## 下一步
1. P2 开工前置：§12 第 1 / 3 题拍板（JSONL / 只登记）；P2 顺带把 `RuntimeHandle.dump()`（含 `derive_mismatches`）落进私有产物。

## 不要做
- 不改 `AgentModelClient` 协议；不改 `ToolCallStatus` 枚举；不改 90/60/30；不改 harness 说明书文本（`episode_protocol` 未提及 `tool_timeout`，无接触点）。
- 不在本分支切 8792。
