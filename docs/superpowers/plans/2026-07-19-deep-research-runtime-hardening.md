# Deep Research Runtime Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让金融研究 Workbench 的事实门禁、LLM 预算、agent deadline、证据继承和检索去重成为可测试的硬约束。

**Architecture:** 复用现有 Grounded Composer 作为市场复盘可信出口；把预算与 deadline 下沉到实际副作用边界；以 round-trip 契约和 per-key single-flight 消除跨层状态丢失及重复查询。

**Tech Stack:** Python 3.11、dataclasses、ContextVar、threading/Future、pytest。

---

### Task 1: Market review grounded exit

**Files:**
- Modify: `intelligence/services/ask_synthesis.py`
- Modify: `intelligence/services/ask_types.py`
- Test: `intelligence/tests/test_p0_hardening.py`
- Test: `intelligence/tests/test_grounded_presenter_general.py`

- [ ] **Step 1: 写失败测试**

把无 marker 市场散文加入证据外“算力方向”，断言 `quality_gate_rejected`；补一条市场复盘启用 Grounded Presenter 后可进入现有 grounded 链的测试。

- [ ] **Step 2: 验证测试先失败**

Run: `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_p0_hardening.py intelligence/tests/test_grounded_presenter_general.py`

Expected: 旧豁免使 unsupported prose 测试失败。

- [ ] **Step 3: 最小实现**

删除 market-review 对 `validate_llm_answer` error 的过滤；允许 `promote_grounded_answer` 处理 market review。grounded 链失败时不再启动旧散文调用，保留结构化 AnswerSpec。

- [ ] **Step 4: 验证通过**

运行 Task 1 的两个测试文件，预期全绿。

### Task 2: Atomic LLM attempt reservation

**Files:**
- Modify: `intelligence/services/llm_refine.py`
- Test: `intelligence/tests/test_p1b_runtime.py`

- [ ] **Step 1: 写失败测试**

构造 `max_calls=1`、两个失败 provider，断言只执行一次 `urlopen`；补并发预占测试。

- [ ] **Step 2: 验证测试先失败**

Run: `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_p1b_runtime.py -k 'budget'`

Expected: fallback 或并发调用超过上限。

- [ ] **Step 3: 最小实现**

给 `LLMCallLedger` 增加锁和累计 reservation；四个 `_post_chat*` 在网络前预占，完成时记录；预算拒绝抛 typed exception，公共入口转为稳定降级原因。

- [ ] **Step 4: 验证通过**

运行预算相关测试，预期 HTTP 次数不超过上限且账本统计正确。

### Task 3: Absolute agent deadline

**Files:**
- Modify: `intelligence/services/agent_research.py`
- Modify: `intelligence/services/ask.py`
- Modify: `intelligence/services/llm_refine.py`
- Test: `intelligence/tests/test_agent_research.py`
- Test: `intelligence/tests/test_p1b_runtime.py`

- [ ] **Step 1: 写失败测试**

根 deadline 过期或 `total_seconds=0` 时，complete/tool 都不得执行；剩余 0.2 秒时传给 complete 的 timeout 不得大于剩余值。

- [ ] **Step 2: 验证测试先失败**

Run: `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_agent_research.py -k 'deadline or zero_budget'`

Expected: 旧实现仍调用一次 LLM，timeout 为 15。

- [ ] **Step 3: 最小实现**

`run_agent_loop` 使用绝对 `ResearchDeadline`，逐调用计算剩余时间；`llm_refine.complete/chat_with_tools` 去掉最少一秒钳制；Ask 传入 turn deadline。

- [ ] **Step 4: 验证通过**

运行 agent 与 runtime 定向测试，预期零预算零副作用。

### Task 4: Evidence round-trip

**Files:**
- Modify: `intelligence/workbench_skills/research_owner.py`
- Modify: `intelligence/services/answer_model.py`
- Test: `intelligence/tests/test_workbench_research_owner_skills.py`
- Test: `intelligence/tests/test_answer_model.py`

- [ ] **Step 1: 写失败测试**

构造含 candidate fact、content hash 和 source revision 的 AnswerSpec，经跨轮 merge 后断言字段保留并进入 EvidenceAtom provenance。

- [ ] **Step 2: 验证测试先失败**

Run: `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_workbench_research_owner_skills.py intelligence/tests/test_answer_model.py -k 'round_trip or provenance'`

- [ ] **Step 3: 最小实现**

合并 `candidate_facts`，反序列化 provenance 字段，并在派生 atom 时传播。

- [ ] **Step 4: 验证通过**

运行两组契约测试，预期字段完整。

### Task 5: Query single-flight and public projection

**Files:**
- Modify: `intelligence/services/query_ledger.py`
- Modify: `intelligence/services/web_research.py`
- Modify: `intelligence/services/agent_research.py`
- Modify: `intelligence/services/conversation_orchestrator.py`
- Test: `intelligence/tests/test_p1b_runtime.py`
- Test: `intelligence/tests/test_conversation_orchestrator.py`

- [ ] **Step 1: 写失败测试**

用 barrier 验证不同 key 同时进入 fetch；验证不同 limit 不复用；验证 graph citation 不暴露 relation 路径；验证重复 citation 去重。

- [ ] **Step 2: 验证测试先失败**

Run: `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_p1b_runtime.py intelligence/tests/test_conversation_orchestrator.py -k 'query_ledger or citation'`

- [ ] **Step 3: 最小实现**

QueryLedger 改为 per-key Future，Web key 加入行为参数；AgentEvidence 分离公开标签与内部 locator；citation sanitizer 执行稳定去重。

- [ ] **Step 4: 验证通过**

运行 Task 5 测试，预期同 key 单执行、不同 key 并行、公开引用无内部路径。

### Task 6: Regression verification

**Files:**
- Modify: `docs/superpowers/plans/2026-07-19-deep-research-runtime-hardening.md`

- [ ] **Step 1: 定向测试**

Run: `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_p0_hardening.py intelligence/tests/test_p1b_runtime.py intelligence/tests/test_agent_research.py intelligence/tests/test_answer_model.py intelligence/tests/test_workbench_research_owner_skills.py intelligence/tests/test_grounded_presenter_general.py intelligence/tests/test_conversation_orchestrator.py`

- [ ] **Step 2: 静态检查**

Run: `.venv-workbench/bin/python -m py_compile intelligence/services/ask_synthesis.py intelligence/services/llm_refine.py intelligence/services/agent_research.py intelligence/services/query_ledger.py intelligence/services/answer_model.py intelligence/workbench_skills/research_owner.py`

- [ ] **Step 3: 全量测试**

Run: `.venv-workbench/bin/python -m pytest -q`

- [ ] **Step 4: 检查差异**

Run: `git diff --check && git status --short`

Expected: 无 whitespace error，不包含既存未跟踪行情文件。

