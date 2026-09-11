# feat/knevo-r4r5-absorption · 2026-09-11 · Knevo q17 Q8/Q4/Q6 回灌（R4/R5 收窄 + R7 试用）

树 `~/fwp-wt-knevo-r45`，基线 `gitea/main=dd1ad32b`。来源：用户转来的复核笔记
`~/agent-memory/00_inbox/2026-09-11-knevo-new-corpus-absorption-review.md`，**指令是执行它**。

## 落了什么

| | 落点 | 一句话 |
|---|---|---|
| 候选一（R4 收窄） | `services/judgment_delta.py` + `evidence_window.select_agent_evidence` | 材料侧：同事件合并（出处写进证据链末尾）+ 反证保底置顶 `counter_floor=2`；表达侧：材料型判断题注入「保留判据/反证优先/待验证问题/裁判变量接下一步」契约 |
| 候选二（R5 收窄） | `services/pricing_split.py` + `market_midterm.midterm_intent_for` | 产业证据变化 / 定价状态两问分答；**先接线**：`is_pricing_state_query` 成为 D6 门控第三个放宽口，「液冷还能追吗」这才拿得到拥挤度分位 |
| 候选三（R7 试用） | `research_task_planner.detect_decision_surface` | 审批/招标/扩产类问句先问「谁有决定权→公开约束→可行动作→哪份材料能区分」；只接管 forecast/relation/comparison 没接走的问句 |

两条引擎同注入（`episode_protocol`、`ask_synthesis`，`AskOptions.include_judgment_delta_guidance`
/ `include_pricing_split_guidance`），收据 `judgment_delta` / `pricing_split` 在
`continuous_turn_adapter`。

## 刻意没做（别当缺口捡回来）

1. **缺件不进 `missing_outputs`**：会触发修复轮、改预算行为。先用收据量效果，再决定要不要接
   `track_contract.is_contract_rewrite_only` 那条表达槽路径。
2. **没跑同题对照实验**：程序核对只能证明「有没有分开答」，证不了「解释是否变好」。臂与题面已写进
   `docs/learning/knevo-distill/absorption-plan-2026-09-11.md#实验清单`。**开跑前先探活模型网关**
   ——验收批次与生产共用配额，一次深 episode 能触发 75 分钟 cooldown。
3. **收窄掉的初版定义**：R4 的「摘要引擎/单条主矛盾/按非主线丢弃」、R5 的「六项满足四项」投票阈值，
   理由在 absorption-plan「R4/R5 的收窄」段，**不是漏做**。q16 的仓位/止损数字仍在 Q-002 排队。

## 怎么验

`pytest intelligence/tests/test_{judgment_delta,pricing_split,research_task_planner}.py`。

关键是两条**反向对照**：`test_counter_floor_off_drops_the_counter_evidence`（关掉保底，弱源反证
掉出窗口）与 `test_merging_alone_saves_the_counter_but_does_not_rank_it_first`（合并只腾位、
不决定次序）。删掉任一条新子句这两条就红——没有它们，「反证留下了」可能只是运气。
R1a 的六句负例在 `test_r1a_negative_examples_stay_closed` 钉着，防止放宽把 D6 变成常开。

## 下一步

跑实验清单 → 读收据（`material_digest.role_counts` / `violations`）→ 有效再考虑上修复硬门、
把 R7 并进 event_forecast 支。question-bank 的「回灌落地仍欠」在实验出结论前不改：接线 ≠ 验证。
