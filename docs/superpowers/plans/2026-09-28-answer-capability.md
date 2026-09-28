# 8792 Answer Capability Implementation Plan

> **For agentic workers:** Use subagent-driven-development for the independent routing task and staged review. Steps below are the execution checklist; user has approved execution.
状态：实现、分阶段复核、工程门禁与自然对照已完成；整体自然回答质量未通过，分支保留待验收，未合并/部署。结论及精确收据见 `docs/verification/2026-09-28-answer-capability-evaluation.md`。

**Goal:** 让8792按用户任务选路、按证据继续研究，并交付有依据的实际答案。

**Architecture:** 保持现有生产循环与TaskFrame真本源；实体解析只锚主体，语义任务由Controller选择。金融方法按需指导，工具说明去重，终局错误沿原Episode和预算分型恢复。

**Tech Stack:** Python 3.12、现有 FastAPI Workbench、pytest、共享 `.venv-workbench`。

## Task 1: 任务语义与主体解耦

Files: `intelligence/services/turn_controller.py`, `route_table.py`, corresponding controller/quick-fact tests.

- [x] 用有主体的原始自然查数请求及现有resolver夹具复现：Controller正确回复quick_fact时仍必须真正送达它并生成fact_value/as_of_date/evidence_boundary。覆盖明确日期、主题、真正深挖、材料范围和模型不可用。
- [x] 只把“实体存在→默认研究题型”的确定性捷径降为候选；保留明确工作流/材料/日期控制。沿现有六字段协议处理模型回复，不新增第二分类器。
- [x] Controller系统说明明确主体/日期/权限锁定，但任务类型是建议；成功合法路由经 `_rebase_frame_for_decision` 回写唯一TaskFrame。
- [x] quick_fact 使用现有research入口和事实输出；调整过时的knowledge车道断言，并跑相邻回归。

Test intent:
```python
decision = decide_turn(query, resolver=resolver, llm_complete=quick_fact_reply)
assert decision.lane == "research"
assert decision.task_frame.required_outputs == ("fact_value", "as_of_date", "evidence_boundary")
```

## Task 2: 按需研究指导与工具正文去重

Files: `judgment_delta.py`, `episode_protocol.py`, `research_tool_registry.py`, `research_harness.py`, `runtime/agent_episode.py`, related tests.

- [x] 删除指导里的逐字标题、固定前缀与无反证套话；保留按判断增量选材、强反证、未知与多条争论。收据的标题解析明确只作旧格式观测，不作缺件评分。
- [x] `retrieval_stages_rule` 改为可选路径；未做不相关阶段无需写缺口，用户要求且实际无法回答的项仍写gap。
- [x] `prompt_block(..., include_descriptions=True)` 默认兼容文本调用方；原生工具模式显式False，正文仅名称/能力/成本/时效，完整contract仍在tool definitions。
- [x] 用真实装配测试比较工具集合/schema不变，正文不重复长描述；保留schema与权限的负例。

Projection shape:
```python
label = f"- {spec.name}（{spec.capability}，{spec.cost}，{spec.freshness}）"
# Full text remains the default; native-schema runtimes request the compact projection.
```

## Task 3: 终局修复继续工作

Files: `research_harness.py`, `runtime/agent_episode.py`, `runtime/harness_reference_loop.py`, relevant protocol/runtime tests.

- [x] 脚本模型复现：先非法JSON，再未知引用，之后真实工具结果和合法终稿。检查tools开放、观察保留、取证次数和原截止。
- [x] 复用既有拒绝码区分格式与缺证方向，生成相应反馈；同类重复失败收口，不同方向的首次补救受总次数和原预算限制。
- [x] 不改变伪造哈希/材料越界的拒绝，不在finalization_started、取消或余额耗尽后继续取证；参考循环同步最小行为接缝。
- [x] 跑生产循环/参考循环符合性与相邻修复回归，确保新日志能区分实际修复动作。

Expected behavior:
```text
format rejection -> repair representation or obtain missing evidence
evidence rejection -> obtain authorized evidence or report precise gap
integrity rejection -> stop
closed/cancelled/exhausted -> preserve original finalization boundary
```

## Task 4: 合并验证与自然对照

Files: existing tests/conformance and eval/probe machinery; docs/agent-product-door.md; dated evidence report.

- [x] 规格审查通过后进行代码质量审查并修正发现；汇总受影响回归，保存命令、revision与依赖条件。
- [x] 用 `scripts/launch_workbench_sidecar.sh` 建候选与基线隔离服务，同一生产模型配置、独立用户和Episode目录。先health核身份，再按真实conversations入口发题。
- [x] 对照覆盖查数、材料推理/财务传导、比较、消息影响、历史追问、失败恢复；按现有rubric核事实/任务覆盖/推理/耗时，不数标题判优。
- [x] 对求证指导/自主视角仅做受控实验，有重复收益才扩大；失败原样留证，停止本次启动的sidecar。
- [x] 更新产品门、能力图谱指针及handoff；pathspec提交、推送并建立PR。记录未验边界与合并/上线待办。

Commands use `/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest` and `-m ruff`; do not update the shared environment or run duplicate full gates while another owner is testing.

交付：[WIP PR #956](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/956)；生产未变。能力图谱两条既有节点与项目单行索引已回写，9条分支路径/符号断言通过。
