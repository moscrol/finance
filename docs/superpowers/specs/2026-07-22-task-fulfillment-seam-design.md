# Task Fulfillment Seam 设计

日期：2026-07-22

## 目标

把“流程完成、证据有绑定”和“用户问题已被回答”拆成三个可观测状态，并在最终用户可见答案发布前增加一个小接口、深实现的任务完成模块。它不取代真值闸门，也不把所有判断交给 LLM；它只消费已经形成的 TurnContract、最终正文和 EvidenceAtom，逐项判定 required outputs 是否完成。

## 当前问题

- `conversation_orchestrator.py`、skill router、generic contract、agent finish 和 renderer 分别重建任务语义。
- `generic_research_owner._matches_output()` 主要检查工具类型、ID 和 `sufficient`，不能判断证据是否蕴含 assessment。
- `answer_model.py` / grounding judge 检查 claim 绑定与可核验性，但没有检查原问题是否直接得到回答。
- `scripts/smoke_workbench_self_use.py` 仅以 `run_status == completed` 作为成功条件。

## 设计决定

### 1. 单一外部任务契约

继续复用已有 `TurnIntent`/`ResearchTaskContract` 数据结构，逐步把它投影为不可被下游覆盖的 TurnContract。该契约至少携带：`question_type`、`timeframe`、`as_of`、`required_outputs`、`evidence_plan` 和 `answer_owner`。skill router 只能返回工具/证据 provider 选择，不能修改 required outputs 或 answer owner。

### 2. 深模块接口

新增 `intelligence/services/task_fulfillment.py`，外部接口保持单一：

```python
evaluate_task_fulfillment(
    *,
    question: str,
    required_outputs: tuple[RequiredOutput, ...],
    answer_text: str,
    evidence_registry: EvidenceRegistryView,
    claims: tuple[StructuredClaim, ...] = (),
) -> FulfillmentVerdict
```

第一版先做确定性检查：required output 的正文 span、claim/atom 绑定、明确 gap 和 evidence freshness。语义蕴含 judge 作为可插拔 adapter，不进入第一版硬路径；没有足够证据时允许“针对该 output 的诚实 gap”通过，但不能把来源列表当成 direct assessment。

### 3. 两个检查时点

- 合成前：作为 repair planner 的输入，指出缺失 output。
- Grounded Composer 最终 repair 后、`answer.snapshot(final=true)` 发布前：作为唯一最终答案完成门。

流式过程可以继续发送研究进度，但只有最终 gate 通过才允许终态标为 answer complete；失败时终态为 `partial/degraded/evidence_gap`，不能伪装成 verified。

### 4. 任务完成与真实性分离

保留现有证据绑定、过期证据、题材污染和权限闸门。TaskFulfillmentGate 不负责判断数据真伪，只判断任务输出是否覆盖且与证据 registry 对齐。三态统一投影为：`transport_status`、`research_status`、`answer_status`。

### 5. 失败恢复

agent finish 超时不删除已有证据。只有已有 EvidenceAtom 支持有界 assessment 时才生成 degraded assessment；否则生成绑定到具体 required output 的 gap。定向 repair 只补缺失 output，不重写整篇答案。

## 最小验证集

1. “目前市场的主线是什么，给我你的判断依据”：必须有当前主线判断和同日依据。
2. “明天是反弹还是继续下跌，分别给出理由”：必须有基准偏向、反弹情景、继续下跌情景、失效条件，并检查 `as_of`。
3. “科创50的支撑点位在哪”：现有确定性技术位链必须保持通过。
4. 反例：工具类型正确但内容无关，assessment 任意；不得 `business_status=complete`。
5. 反例：只给候选来源清单；不得 `answer_status=complete`。

## 非目标

- 不为每个长尾问题新增独立 Skill。
- 不在第一版引入全量 NLI 模型或把 rubric 分数直接当线上唯一门禁。
- 不在本分支合并 main 或切换 canonical 8792。

## 验收标准

- 以上五类用例在候选分支有红→绿回归。
- `answer.snapshot(final=true)` 与 answer_status 一致。
- smoke 支持语义失败红灯，并保留 `--transport-only` 调试模式。
- 现有 market_technical 和证据真值闸门无回归。
- 新模块上线后能删除至少一处重复的 completion/fallback 判断，否则重新评估 seam 深度。
