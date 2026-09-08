<!-- 由 scripts/gen_runtime_catalog.py 从源码生成，不要手改。
     再生成：python3 scripts/gen_runtime_catalog.py ；校验：--check（pytest test_runtime_catalog 也会比对）。 -->

# ResearchHarness 接缝目录

loop 只在这些方法上调领域 harness（`research_harness.ResearchHarness`）。签名与首段 docstring 直接取自 Protocol 源码，顺序即源码顺序。改接缝先改 Protocol，本表随之再生成；接缝的取舍见 `docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md` §4。

16 个方法

## `assemble_prompt`

```python
def assemble_prompt(self, task_frame: 'TaskFrame', context: 'ResearchRunContext', registry: 'ResearchToolRegistry') -> 'tuple[str, str]'
```

开场 ``(system, user)``。system 在一次 episode 内字节稳定。

## `steering_message`

```python
def steering_message(self, kind: 'SteeringKind', *, detail: 'str') -> 'str'
```

loop 在驳回 / 关闭研究阶段时注入给模型的那段话（user 角色正文）。

## `interpret_plan`

```python
def interpret_plan(self, content: 'str', *, previous_plan: 'ResearchPlan | None', task_id: 'str') -> 'PlanParseResult'
```

这条模型输出是不是一份合法 PLAN（含相对上一份的修订合法性）。

## `govern_mode`

```python
def govern_mode(self, *, task_frame: 'TaskFrame', plan: 'ResearchPlan', context: 'ResearchRunContext', can_branch: 'bool') -> 'ModeGovernance'
```

PLAN 到手后裁研究深度：出裁决值与一段给模型的话。

## `project_sub_research`

```python
def project_sub_research(self, *, branches: 'Iterable[BranchOutcome]', refused_reason: 'str', evidence: 'tuple[AgentEvidence, ...]') -> 'str'
```

子研究分支回来后给主 episode 模型看的那段话（``SUB_RESEARCH_RESULTS``）。

## `project_tool_result`

```python
def project_tool_result(self, observation: 'ToolObservation', *, evidence_so_far: 'tuple[AgentEvidence, ...]', seen_prose: 'Set[str]') -> 'ToolResultProjection'
```

一次成功观察：审计留什么、模型看什么。

## `project_tool_error`

```python
def project_tool_error(self, *, tool: 'str', error: 'str', detail: 'str') -> 'dict[str, object]'
```

一次失败 / 被拒 / 超时的工具调用给模型看的结构化结果。

## `halt_after_tool_batch`

```python
def halt_after_tool_batch(self, *, context: 'ResearchRunContext', batch_errors: 'Iterable[str | None]') -> 'str | None'
```

一批工具跑完后是否立刻停止研究。返回停机理由；``None`` = 继续。

## `fallback_after_empty_batch`

```python
def fallback_after_empty_batch(self, batch: 'Iterable[ToolCallOutcome]', *, context: 'ResearchRunContext', registry: 'ResearchToolRegistry', authorized_tools: 'frozenset[str]', events: 'Iterable[object]', in_repair: 'bool') -> 'FallbackCall | None'
```

一批工具跑完、下一次问模型之前：要不要替模型补发一次查询，补什么。

## `retrieval_complete`

```python
def retrieval_complete(self, *, context: 'ResearchRunContext', registry: 'ResearchToolRegistry', successful_tools: 'set[str]') -> 'bool'
```

已授权的取证面是否全部拿到——是则不必再派工具，可以进合成。

## `admit_finish`

```python
def admit_finish(self, content: 'object', *, context: 'ResearchRunContext', evidence: 'tuple[AgentEvidence, ...]', registry: 'ResearchToolRegistry') -> 'FinishAdmission'
```

模型的终局输出能不能发。

## `classify_repair_need`

```python
def classify_repair_need(self, outcome: 'AgentOutcome', structural: 'VerifiedEpisodeOutcome', *, rejected_claims: 'tuple[str, ...]', semantic_gap_outputs: 'tuple[str, ...]') -> 'RepairNeed'
```

主轮终局过完结构 / 语义验证之后：这次失败该修什么、属于哪一类。

## `warrant_repair`

```python
def warrant_repair(self, *, progress: 'ProgressSnapshot', cycle: 'int', research_tier: 'str') -> 'RepairWarrant'
```

这个 tier 还容忍第 ``cycle`` 轮吗；上一轮有没有独立证据进展。不看预算。

## `downgrade_unreachable`

```python
def downgrade_unreachable(self, goal: 'RepairGoal', *, contract: 'ResearchTaskContract') -> 'RepairDowngrade'
```

授予已定、开场之前：哪些 evidence 口径的必填格这一轮结构性补不上。

## `repair_goal_message`

```python
def repair_goal_message(self, goal: 'RepairGoal', *, tools_open: 'bool') -> 'str'
```

修复轮开场给模型的那段话（``REPAIR_GOAL`` 正文，user 角色）。

## `admit_repair_result`

```python
def admit_repair_result(self, *, admission: 'FinishAdmission', previous: 'AgentOutcome', performed_tool_action: 'bool') -> 'RepairVerdict'
```

修复轮的终局已被 ``admit_finish`` 接受——那它算不算修好了。

