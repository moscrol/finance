# Prediction Ledger: finance-workspace-private

- last_updated: 2026-08-04（含词表对齐与仪器覆盖矩阵）
- 配套文件：[trace-profile.md](trace-profile.md)（同址、同为被审方资产）
- 消费方：`agent-run-triage` skill 的 `Prior prediction closure` 段

## 这份文件是什么

每条**修复建议**都必须带一条可证伪的 `verification_prediction`（「改完之后会看到什么」）。
本文件是这些预测的**唯一事实源**，报告里的 closure 段只是它的一次切片。

住址固定在 `<project>/docs/prediction-ledger.md`，因为本项目会被多个 harness
（Claude / Codex / Grok）分诊。**若各 harness 把结论留在自己的报告里，闭环会静默断裂且不报错。**

### 开工动作（不是收尾附录）

对本项目开一次新分诊时，**第一步**先读下面「Open」表，用本次 trace 回填
`confirmed` / `refuted`，再开始新归因。顺序不能反 —— 否则新证据会被本次结论污染。

### 记账规则

- `refuted` 是本账本最有价值的输出，**不要粉饰成 `pending`**。前者是「上次判错了层」的硬证据并驱动升格；后者只是「还没测」。
- 同类 `fix_type` 连续 ≥3 次 `refuted` → 停止再堆同类修补，升格质疑 `HARNESS`/架构层。streak 按**本项目**累计，不跨项目。
- `fix_type` 只能取：`SYSTEM_PROMPT_FIX` / `TOOL_DESCRIPTION_FIX` / `ROUTING_FIX` / `DATA_CONTRACT_FIX` / `HARNESS_FIX` / `EVAL_ONLY` / `NO_SYSTEM_FIX`。
- 只记引用、hash 和最短摘录。用户题面、答案正文、股票池、凭据不进本文件（本文件进 git）。

## Open（pending）

| ID | 来源 | fix_type | verification_prediction | 怎么验 | outcome |
|---|---|---|---|---|---|
| `R-20260804-02` | 收口审计 §修复2 | `EVAL_ONLY` | 真 Codex rollout 中 `function_call_output` 归入 `observe`，与 workbench 的 `validate→observe` 对齐；第一个工具结果处不再出现**词表性**分叉 | 取一份真 rollout JSONL 跑 `normalize_harness_trace --kind codex-rollout`，检查首个工具结果的 step | `pending` |
| `R-20260804-04` | 收口审计 §修复A | `HARNESS_FIX` | 新 run 中仅 `headless_timeout` 的 case **不再**出现 `runtime_invalid_actions:N` | **需 codex CLI + 凭据**跑一次真 headless run，比对 `protocol_issues` 与 `runtime_result.payload.issues` | `pending`（两段各自已验，端到端未验，见下） |
| `R-20260804-07` | 设计评审 G2 词表对齐 | `EVAL_ONLY` | 下一份 triage 报告的 `first_bad_step` 可与本仓 `first_divergence_step` **直接比较，无需翻译**；L1=`tool` 的 finding 在本仓可表达 | 下次对本项目开分诊时，检查报告的 L1 值是否落在本仓 `STEPS` 内 | `pending` |
| `R-20260804-08` | 设计评审 §仪器覆盖矩阵 | `HARNESS_FIX` | 补齐埋点后，`configure → intent → plan` 三步在 workbench 与 codex **两侧都非空**，`first_divergence_step` 首次具备行为含义 | 见 [trace-profile.md](trace-profile.md) §8 缺口表 | `pending`（**workbench 侧 3/3 已达标，codex 侧 1/3**） |

> **`R-20260804-04` 为什么不结案。** 两段分别实测通过，但**组合结论未端到端验证**：
>
> | 段 | 断言 | 证据 |
> |---|---|---|
> | A | `count_invalid_actions(('headless_timeout',)) == 0` | 实测（单元） |
> | B | `usage.invalid_actions=1` ⇒ `protocol_issues == ['runtime_invalid_actions:1']` | 实测（端到端合成 run） |
>
> A∧B 蕴含「codex 超时 ⇒ 不再出现 `runtime_invalid_actions`」，但**中间那跳
> （codex runtime 由 stdout issues 得出 usage）只有 code_reading 支撑**，因为本机
> 无 codex CLI、无 provider 凭据。按证据纪律，以 code_reading 为主要支撑的结论不声明
> high —— 保持 `pending`，等一次真 headless run。

## Closed

| ID | 来源 | fix_type | verification_prediction | outcome | evidence |
|---|---|---|---|---|---|
| `R-20260804-01` | 收口审计 §修复1 | `EVAL_ONLY` | 左短右长且左为前缀时 `compare_sequences` 不再抛 `IndexError`，返回 `equivalent_before_divergence`，evidence 含 `continues_on` | `confirmed` | `test_compare_sequences_survives_prefix_on_either_side`；两种传参顺序均返回 `synthesize @ ordinal=3` |
| `R-20260804-03` | 收口审计 §修复4 | `EVAL_ONLY` | 归一化产物能**独立**复现审计表第三列，不必回原始 receipt | `confirmed` | 重跑历史收据，5/5 `finish` 事件带 `status` + `stop_reason`，与 arm 级逐条对齐（`ruihuatai-valuation` 的已知不一致除外） |
| `R-20260804-05` | 收口审计 §修复B | `HARNESS_FIX` | 新 benchmark artifact 的 `diagnostics.events[0].kind == "task"` 且 `sequence == 1`；payload 只有 `task_frame_hash`；题面不出现在 `events` 内 | `confirmed` | 2026-08-04 跑真 benchmark CLI（合成 runtime，真实序列化路径）：`{"kind":"task","sequence":1,"payload":{"task_frame_hash":"432d9856…"}}`，题面确认不在 `events` 内。两条发射路径（`codex_headless_runtime:903`、`agent_episode:155`）均为 sequence 1 |
| `R-20260804-06` | 收口审计 §修复C | `EVAL_ONLY` | 新 run 若产生 `mode_decision` / `branch_*` / `finalization`，归一化后 `unmapped_count` 为 0 且 `mode_decision → plan` | `confirmed` | 同上收据归一化：10 事件 / **0 unmapped**，`mode_decision→plan`、`branch_started→retrieve`、`tool_request→tool`、`tool_error→observe`、`finalization→synthesize`、`finish→stop` 逐条命中 |

## fix_type refuted streak

| fix_type | 连续 refuted | 距升格线 |
|---|---|---|
| `SYSTEM_PROMPT_FIX` | 0 | 3 |
| `TOOL_DESCRIPTION_FIX` | 0 | 3 |
| `ROUTING_FIX` | 0 | 3 |
| `DATA_CONTRACT_FIX` | 0 | 3 |
| `HARNESS_FIX` | 0 | 3 |
| `EVAL_ONLY` | 0 | 3 |

## Residual uncertainty（不是预测，是没结论的观察）

| 观察 | 状态 | 下一步取证 |
|---|---|---|
| `test_live_runner_uses_fresh_context_per_backend_without_cross_arm_state` 在一次全量跑中失败，其余三次（单测 / 整文件 / 第二次全量）均通过 | 未归因 | 连跑 5 次全量记录命中率；若可复现再定位是哪个前序文件泄漏状态。**当前不归因到 2026-08-04 的改动** —— 它的断言不触及任何被改的面 |
| 收据的 arm 级 `stop_reason` 与事件级 `finish.payload.stop_reason` 在 `ruihuatai-valuation` 上不一致（`semantic_repair` vs `model_finish`） | 已记入 [trace-profile.md](trace-profile.md) §2 | 无需修复，属分层语义差异；跨 harness 比较一律用事件级 |

## 溯源说明

`R-20260804-01..08` 来自 2026-08-04 的**代码审计 + 收口 + 设计评审**，不是一次标准
的四阶段 `agent-run-triage` 分诊：没有走 Triage → Static → Dynamic → Synthesis，
没有分配 L0/L1/L2，也没有 3 条以上排名假设。因此这些条目**只有 `fix_type` 和
`verification_prediction` 可用于 streak 统计**，不能当作已确认根因的 PRIMARY 引用。

首次真正的分诊在回填本账本时，应把这一批视为 `no prior triage report` 的历史遗留
条目，只做 outcome 回填，不继承其归因。

对应审计记录：
- [docs/verification/2026-08-03-cross-harness-shared-layer-audit.md](verification/2026-08-03-cross-harness-shared-layer-audit.md)
- [docs/verification/2026-08-04-improvement-loop-design-review.md](verification/2026-08-04-improvement-loop-design-review.md)
- [docs/trace-profile.md](trace-profile.md) §2 字段陷阱、§6 投影契约、§8 仪器覆盖矩阵
