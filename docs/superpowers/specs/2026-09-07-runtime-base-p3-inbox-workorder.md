# 工单 #30 · 运行底座 P3：收件箱（预立单）

> 母单：#27 `2026-09-07-runtime-base-endstate-design.md` §6.4。前置：P2（#29）合入；§12 第 4 题（Workbench `steer` 端点本轮做不做）拍板——未拍板按推荐：底座 + CLI 先做，端点等 Alpha 反馈。
> 分支：`feat/runtime-base-p3-inbox`。状态：⏳ 预立单。
> 判据：INV-R5 成立；`derive_messages` 仍逐字节相等（收件箱消息是 durable 事件，天然进派生）。

## 范围

1. `services/episode_inbox.py`：`Inbox`——`send(message: EpisodeMessage, target ∈ {next_turn, next_step}, wakeup)`；`claim(target) -> list[EpisodeMessage]`；durable `inbox_inserted / inbox_claimed / inbox_discarded`（payload 带 `message_id / source`）。loop 每次模型请求前 `claim(next_step)`，模型停下且无工具调用时 `claim(next_turn)`。
2. **harness 接触点（本单唯一新增方法，先过接缝线纪律「有牙」）**：`ResearchHarness.admit_inbox_message(message) -> bool`，默认恒 `True`；拒收走 `inbox_discarded{reason}`。
3. 子研究回灌：`_run_sub_research` 结果不再内联拼进 `messages`，走 `inbox.send(..., target=next_step, source="sub_research")`。
4. 取消与收件箱：`cancel(cause, keep_inbox=False)` 默认清箱并落 `inbox_discarded{reason=cancelled}`。
5. CLI：`python3 -m intelligence.cli steer <episode_id> "<文本>"`；Workbench 端点按 §12 第 4 题。

## 验收

INV-R5 三事实 durable；竞态「steer 到达 vs 模型停下」两序；`test_harness_reference_loop` 并跑仍一致；`derive_messages` 严格模式全绿。

## 不做

不做 lanes / forks；不铸子研究新预算（`_BranchBudgetView` 不变）；不改 90/60/30。
