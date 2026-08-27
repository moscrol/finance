# 在途交接 · fix/tool-call-id-correlation

更新：2026-08-28 凌晨 · **R-20260827-15 工单 P0 已实施并离线验收，PR 待开/待合。**

## 一句话

episode durable 事件面 `tool_result` / `tool_error` 补 `call_id` 与
`tool_request` 共键（工单
`docs/superpowers/specs/2026-08-27-tool-call-correlation-workorder.md`），
改动面 = `agent_episode.py` 两处 `ledger.add` 展开 + 四个测试钉。

## 离线验收读数（对分支尖成立）

- TDD：判据 1/2 两钉**先红**（2F 实录）→ 实施后整文件 **109P**。
- 变异 4/4 逐个精确击杀（各自只红对应的钉，复原后 4P）：
  M1 去 result call_id → 判据 1 红；M2 call_id=name → 判据 1+2 红；
  M3 泄漏进模型内容 → 红线钉红；M4 消费侧硬取键 → 容缺钉红。
- ruff 绿；全量 pytest 收据见台账 `R-20260827-15` 行（合并批次时以
  `check_test_receipt.py --expect-revision` 复核）。
- **离线绿≠confirmed**：须一次 live run 回读 events 配对（工单 §7），
  需等 8792 切到含本修复的 revision 之后。

## 红线遵守自证

`call_id` 只进 `ledger.add` 展开——`public_observation` / 错误 `payload`
是模型视图底稿，未写入（变异 3 有测试守）。模型可见字节零改动
（同夹具 `messages` 内容断言覆盖成功与异常两路径）。

## 本轮发现、未做（后续指针）

- `intelligence/runtime/openai_agents_runtime.py`（sdk_glm/sdk_gpt 后端）的
  `tool_request`(:667)/`tool_result`(:860) 事件**双侧都无 call_id**——同病，
  但属另一后端、另一单变量批次，本单未动。`dsh_stub_runtime`（codex 网关）
  反而是好的：直接用网关 `request_id` 双侧共键。
- PRD 面（`trace.jsonl` 的 input 接线 / `parent_span_id`）见工单 §6 P1 指针。

## 下一步

1. 开 PR / 合并——等用户确认（合 main 红线）。
2. 合并后下一次 8792 切流将把本修复带上线；届时抽一个新 run 回读
   `tool_result` 配对，把台账 `-15` 行翻 confirmed。
