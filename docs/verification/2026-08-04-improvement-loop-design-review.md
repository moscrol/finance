# Improvement Loop 设计评审：与 agent-run-triage skill 的接缝

- 日期：2026-08-04
- 被评审对象：`Agent Improvement Loop 集成设计`（2026-08-04，状态「待用户审阅」）
- 标尺：`agent-run-triage` skill（`SKILL.md` + `references/taxonomy.md` + `references/report-template.md`）
- 结论：设计方向成立；与 skill 之间有 **7 处词表/契约不一致**，其中 1 处**在评审时已经在漏**

## 先确认：设计引用的文件都存在

`run_store.py`、`trace-profile.md`、`synthesis_health.py`、`normalize_harness_trace.py`、
`acceptance_verdict.py`、`forecast_learning.py`、`users/README.md`、
`2026-08-03-shared-layer-audit-handoff.md` —— 8 个引用逐个核对，全部真实存在。

## 已对齐（不需改）

| 项 | 状态 |
|---|---|
| 每条建议必带 `fix_type` | ✓ |
| 架构升格线：同类 `fix_type` 连续 ≥3 次 `refuted` → 升格质疑 HARNESS/架构 | ✓ 设计 §8 与 skill 证据纪律逐字同义 |
| 原始 trace 不可变，诊断结果写 sidecar | ✓ |
| `INSUFFICIENT_TRACE` 不等于已确认 HARNESS 根因 | ✓ |
| trace-profile 作为分诊开工第一站 | ✓ 本仓已在实践 |
| LLM 只生成候选，不拥有晋升权 | ✓ 设计原则 4 |

## 不一致清单

### G1（评审时已在漏）：skill 强制的账本住址不存在

skill 规定 pending 预测记在 `<project>/docs/prediction-ledger.md`，与 trace-profile
同址、跨 harness 固定，并明确警告**缺了会「静默断裂且不报错」**。

评审时实测：该文件在本仓与主 worktree**均不存在**，而 2026-08-04 的收口已产生
至少 4 条 pending 预测无处安放。

设计 §6.3 提议把账本放 `intelligence/users/<user>/improvement/`，§15 Q1 仍在问放哪。

**处置（已执行）**：建 [prediction-ledger.md](../prediction-ledger.md)，并采用**分账**而非二选一：

| 账本 | 位置 | 进 git | 内容 |
|---|---|---|---|
| 预测账本 | `docs/prediction-ledger.md` | 是 | `finding_id` / `fix_type` / `verification_prediction` / `outcome` / streak |
| 改进账本 | `intelligence/users/<user>/improvement/` | 否 | evidence 引用、run 绑定、eval candidate、审批 |

join key = `finding_id`。分账理由是本仓红线：改进账本必然带 run_id 与题面，不能进
git；但预测账本必须进 git，否则跨 harness 找不到。

### G2（已执行）：L1 词表 9 步 vs 本仓 7 步

skill 固定 L1 为九步；本仓 `normalize_harness_trace.STEPS` 只有七步，缺 `plan` 与 `tool`。

后果：skill 的 L0×L2 自洽表含「L1=`tool` 却配 `context-handling-error-*`」这类禁止
组合，而本仓**根本表达不出 L1=`tool`**，该自检在本侧跑不起来。

**处置（已执行）**：`STEPS` 扩到九步，新增 `VOCABULARY = "triage-l1-9"`，产物
`schema_version` 升 `normalized-harness-trace-2` 并带 `vocabulary` 字段。
由 `test_step_vocabulary_matches_the_triage_skill_l1_pipeline` 守住。

### G3（未处置）：M2 五个 step 字段，设计与本仓各只取一个

skill 报告模板要求五个字段**各自独立**填写，且「两个填了同一 step 须说明为何确实
是同一步，而非图省事合并」：

`ablation_activation_step` / `first_divergence_step` / `first_failure_step` /
`failure_surfaced_step` / `reconvergence_step`

现状：`compare_sequences()` 只产 `first_divergence_step`；设计 §7.1 只有
`first_bad_step`。

尤其 skill 要求：`first_failure_step ≠ failure_surfaced_step` 时，两者之差是
**「自我报告失真时长」，必须单独立一条 Finding**。这正是 2026-08-04 发现的
`invalid_actions` 缺陷的形状（真实失败在工具网关预算闸门，系统承认它时已变成
「模型动作违规」）——该框架在我们撞见它之前就为它命名了。

### G4（未处置）：triage outcome 轴没进状态机

skill 有三个互斥 outcome：`ROOT_CAUSE_CONFIRMED` / `ROOT_CAUSE_NOT_CONFIRMED` /
`INSUFFICIENT_TRACE`，且明确区分后两者（前者证据足但假设未分胜负，后者证据不足）。

设计 §8 状态机把它们全部收敛进单一 `triaged` 态。建议在 Finding schema 增
`triage_outcome` 字段。

### G5（未处置）：L0/L1/L2 taxonomy 只进了一半

设计 Finding schema 只有 `finding_type` 与 `fix_type`，缺 `l0`、`l2` leaf、
`violated_authority`。缺 L2 则做不了 skill 要求的「同一 L2 leaf 不得跨
PRIMARY/SECONDARY 重复」自检，也攒不出 taxonomy gap 清单。

### G6（未处置）：同义词三套

| 出处 | 用词 |
|---|---|
| `normalize_harness_trace.compare_sequences()` | `not_established` |
| 2026-08-03 审计文档表格 | `not_evaluable` |
| 设计 §7.2 `assertion_kind` | `not_evaluable` |

建议统一，否则 grep 不到、判分器会漏。

### G7（未处置）：设计使用了非法 `fix_type`

设计 §7.1 示例写 `"fix_type": "CONTROL_FLOW_FIX"`。skill taxonomy 的 `fix_type`
只有 7 个合法值：`SYSTEM_PROMPT_FIX` / `TOOL_DESCRIPTION_FIX` / `ROUTING_FIX` /
`DATA_CONTRACT_FIX` / `HARNESS_FIX` / `EVAL_ONLY` / `NO_SYSTEM_FIX`。
`CONTROL_FLOW_FIX` 不在其中，按该缺陷的性质应为 `HARNESS_FIX`。

## 对设计 §15 五个待决问题的建议

| Q | 建议 | 理由 |
|---|---|---|
| 1 账本放哪 | **分账**（见 G1） | 预测账本进 git 是 skill 硬要求；改进账本含用户态数据不能进 |
| 2 首批范围 | 只接 synthesis/acceptance 失败 | forecast reflection 的时间尺度差一个量级，混入会污染 `fix_type` streak |
| 3 审批界面 | 先 CLI/JSON | 早接 Workbench 页面会让 schema 被 UI 绑架 |
| 4 晋升目标 | 只进 overlay，不动 acceptance 正典 hash | 设计 §14 自己的成功标准 |
| 5 首期禁 semantic candidate | **建议禁** | 2026-08-04 发现的全部缺陷（`invalid_actions` 语义、payload 内的 status、白名单丢 `task`、比较器越界）**都是确定性可判的**，semantic judge 一条都抓不到 |

## 处置状态

| gap | 状态 |
|---|---|
| G1 账本住址 | 已执行：建 `docs/prediction-ledger.md`，采用分账 |
| G2 L1 词表 | 已执行：`STEPS` 扩九步 + `vocabulary` 版本字段 |
| G3 五个 step 字段 | 未处置，需先扩 `compare_sequences()` 返回值 |
| G4 triage outcome | 未处置，属设计侧 schema |
| G5 L0/L2/violated_authority | 未处置，属设计侧 schema |
| G6 同义词统一 | 未处置 |
| G7 非法 fix_type | 未处置，属设计侧 |

G3–G7 属设计文档本身的修订项，本轮未代改。
