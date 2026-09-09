# 工单 #30 · 运行底座 P3：收件箱

> 母单：#27 `2026-09-07-runtime-base-endstate-design.md` §6.4。前置：P2（#29）合入；§12 第 4 题（Workbench `steer` 端点本轮做不做）拍板——未拍板按推荐：底座 + CLI 先做，端点等 Alpha 反馈。
> 分支：`feat/runtime-base-p3-inbox`（叠 #638；已合并删除，树已清）。状态：✅ 已合入 `gitea/main`（PR #677 → `9f2718a2`，2026-09-08 21:11，合入顺序 #620 → #624 → #638 → #677；09-09 回写，落地记录见下）。**范围第 5 条 CLI 未做**，见落地记录。
> 判据：INV-R5 成立；`derive_messages` 仍逐字节相等（收件箱消息是 durable 事件，天然进派生）。

## 落地记录（2026-09-08 落地，2026-09-09 回写）

提交 `c044cf2b`（13 文件，+1064 / −14）：新 `intelligence/services/episode_inbox.py`、`intelligence/tests/test_episode_inbox.py`、`intelligence/tests/conformance/test_inv_r5_inbox.py`；改 `runtime/agent_episode.py`、`runtime/glm_agent_runtime.py`（`GLMAgentRuntime.steer` 是唯一外部入口）、`services/episode_messages.py`、`services/episode_event_lanes.py`、`services/research_harness.py`（`admit_inbox_message`）、`eval/normalize_harness_trace.py`、conformance `backends.py`；目录 `docs/runtime/events.md` / `docs/runtime/harness-seams.md` 再生成（durable 34 种、接缝 17 方法，`--check` 一致）。随后 `fea87b02` 前向合并 `main@5985d878` 消除双 merge-base。

**范围对账**：1 ✅ `Inbox` 两队列 + 三事实 durable（正文只在 `inbox_inserted` 落一份，`inbox_claimed` 只带 id，派生按 id 回找）；2 ✅ `admit_inbox_message`（子研究回灌也过它，harness 看 `source`；拒收走 `inbox_discarded{reason}`）；3 ✅ 子研究回灌走箱 `target=next_step`；4 ✅ `cancel(keep_inbox)` 落为 `Inbox.keep_on_cancel`，清箱挂 `_EpisodeLedger.add("finish")`（与 `done` 同出口），`resume()` 重开；**5 ❌ CLI `python3 -m intelligence.cli steer` 未做**——main 上 `intelligence/cli.py` 无 `steer`（09-09 实测），§12 第 4 题的「等 Alpha」只覆盖 Workbench 端点，CLI 在推荐范围内，待补（并进 P4 #684 或单开小单）。

**验收对账**：INV-R5 conformance 14 条 + 单元 8 条绿，变异（停机点不认领 / finish 不清箱 / 请求前不认领）各红 2 / 4 / 2；既有 runtime 套件 428 绿，严格派生全程开着；「steer 到达 vs 模型停下」两序形状已给（P4 升公共件）；ruff 0、pre-commit 11 道过。全量读数见 PR #677 正文。

**已知边界**（原交接 `docs/handoffs/inflight-archive-2026-09-08/feat-runtime-base-p3-inbox.md`）：`wakeup` 只记账（同步 loop 无空闲态，等 P4 `step()`）；`restore` 不处理箱里未决 `inserted`（P4「restore vs 在飞驱动」一起收）；子研究回灌从「批后立刻」挪到「下次请求前」，可能排在收口指令之后，未 live 对照；参考 loop 未接收件箱（声明表 R5 只给 continuous）。**8792 未切流**（09-09 实测仍在 0060da5c），切后 `steer` 探针一次。

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
