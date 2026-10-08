# 研究过程合同 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 资料含义与同一作者合同进入真实开场、观察、修订与恢复，保留既有loop及权限，部署后验整篇。

**Architecture:** 深化已有FinanceResearchHarness与两个结果owner；GLM和headless共享结果投影，纯作者Module负责唯一format。结果资格是数据，不授予事实/权限或整篇证明；不新增总控。

**Tech Stack:** 现有Python dataclasses/mappings、ToolRunResult/ToolObservation、ResearchRunContext、ContinuousAgentEpisode、HeadlessToolGateway、JsonlEpisodeStore、locked venv与现有捕获模型Adapter。

---

设计见同日research-process-contract-design.md。继承f584作者Task1；此前ordinary-finish计划的Task2/3并入本计划B，不自动独立续跑。只一名source writer。原用户部署授权持续有效，judge off/预算/时间/资料范围不变；任何实质发现先修，不带红发布。

## Task A：结果owner语义与共享真实投影

**Files:** Modify `intelligence/services/episode_tools.py` D4/FinanceQuery projection；`finance_query.py`仅读取现有dataset/field语义所需的纯入口；`research_tool_registry.py`已有结果类型/传播；`research_harness.py`真实投影；`runtime/headless_tool_gateway.py`单一消费接线。Test `intelligence/tests/test_research_source_context.py`（create）、`test_headless_tool_gateway.py`及`test_finance_query_basis.py`。只有必要时新增一个纯语义Module，不定义新公共总控。

- [ ] 真owner→registry→Harness和headless RED。测试用本地夹具，不读生产库。实际响应在失败/partial/stale仍保留原状态与范围，两个消费者共享同一query_basis/source_context；缺资格保持unknown，不以旧结果默认认证。

```python
projection = harness.project_tool_result(observation, evidence_so_far=observation.evidence,
                                        seen_prose=frozenset())
model = json.loads(projection.model_content)
assert model['status'] == observation.trace.status
assert model['query_basis'] == observation.query_basis
assert model['source_context'] == observation.source_context
```

- [ ] 在现有类型尾部添加默认空source_context（如实际需要）；producer从typed snapshot/spec生成，不从prose解析。未知source不造kind/qualification；source_context不进入evidence或owned认证。D4 v1 descriptor/query_basis/refs保持；不同观测日期数≠连续、群组行数≠唯一实体、量价≠指数贡献。FinanceQuery所选聚合含义来自dataset/field原owner。
- [ ] headless复用Harness投影，删除独立payload拼装；保留transport budgets/request_id/取消/当前grant。记录响应后确认送达，不依赖尚未发生的CLI消费。无事实结果仍保留已知execution context，不用len(evidence)改status。
- [ ] 初始资料角色沿已有输入集中说明；不扩KB/memory/PLAN/progress配置。真实截断/空查/资料限定及先验不升格反例跨消费者通过；only-path tests+Ruff+pathspeccommit。独立Spec→Standards后才能B。

## Task B：开场、修订、收尾与恢复共享作者合同

**Files:** Modify `intelligence/services/episode_protocol.py`、`research_harness.py`、`runtime/agent_episode.py`、`runtime/episode_finalizer.py`、`runtime/episode_restore.py`仅必要现有字段/接线；headless runtime仅真正消费需要时。Create `intelligence/tests/test_finish_authoring_runtime.py`；复用material/owned/restore邻域。

- [ ] 真实Episode捕获client RED，第一system无相反旧模板、动态user的finish_format来自finish_author_contract。新普通无ref仍可完成自由parts，legacy合法payload无receipt；material/prior_evidence原owner不变。

```python
request = capture.request_messages[0]
assert 'ordinary_answer_parts_v1' in json.dumps(request, ensure_ascii=False)
assert to_provider(derive_messages(native_events_before_request)) == request
```

- [ ] 初始/tool/invalid/unsupported/REPAIR_GOAL/finalizer从同owner取描述，去重复模板而非追加新的相反提示。实际有context/source/ACK才可ref；没有catalogue不假ref、不强制固定章节。
- [ ] 原生restore/repair/carry RED→GREEN：旧未终态保旧合同，新回合修订共享新合同；撤cap、收cutoff、未知ref、缺ACK/源仍拒。选定draft及receipt保持同hash，不用savedformat授源，不新增override/第二账本。

```python
assert restored_event_bytes.startswith(original_event_prefix_bytes)
assert carried.draft == previous.draft
assert carried.owned_answer == previous.owned_answer
```

- [ ] 资料角色/语义envelope不替自由文签质量；现method/prior事实门、时间/权限与source-floor负控不弱化。更新`docs/agent-product-door.md`与runtime同提交。适用caller邻域、Ruff与规范门禁后pathspeccommit，Spec→Standards及全变更独立复审。

## Task C：固定候选工程门禁与实际发布

**Files:** 仅实际需要的交接/产品门/现能力图谱节点；复用现有`run_main_gate.sh`、switch脚本与发布证明工具，不复制新的发布框架。

- [ ] 固定clean HEAD/tree/source hashes；新全仓Python收据用check_test_receipt --require-full-scope对账，frontend六步、registry五项与应触发CI全部绿。旧定向/旧revision读数不转签。
- [ ] 正常PR推送/attach，按既有上线授权normal merge；actualmain独立门禁与新快照、locked解释器、FP/ready/ledger/备份收据。main变动先核真实合并结果，原已证bd66门禁不重跑。
- [ ] 完成后才覆写本枝inflight/日期快照及现能力节点；Pi/River他人源码、harness-reference脏BUILD不动。不增加自动化或新任务。

## Task D：上线后唯一首答与整篇内容验收

**Files:** 运行目录`research-control-1009/`新登记/冻结/独审，复用已审first-answer helpers；不追加旧封存。

- [ ] 在真实新版本部署后登记一次原题首答：source/RAG固定、原GLM/预算/judge off；actual request/source/物理attempt全部纳入，准备失败0turn与成功首答分开。新用户目录不修改真实个人ledger；记忆消费收益另有明确样本，不能从无记录探针猜结论。
- [ ] freeze每件原文与索引；独立新上下文审原问覆盖、事实日期/计数/集合/贡献/反证、自由推理和公开缺口。工程、送达、采用、整篇四结论独立。
- [ ] 若仍NOT_PASSED，保留原答且从首次分叉继续定位；不重抽同版、不扩大规则词表。仅根据证据进入相关检索策略的下一设计/实现循环，不以单题签总体胜率。
