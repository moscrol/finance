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

- [x] **Step 1: 写失败测试**

把无 marker 市场散文加入证据外“算力方向”，断言 `quality_gate_rejected`；补一条市场复盘启用 Grounded Presenter 后可进入现有 grounded 链的测试。

- [x] **Step 2: 验证测试先失败**

Run: `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_p0_hardening.py intelligence/tests/test_grounded_presenter_general.py`

Expected: 旧豁免使 unsupported prose 测试失败。

- [x] **Step 3: 最小实现**

删除 market-review 对 `validate_llm_answer` error 的过滤；允许 `promote_grounded_answer` 处理 market review。grounded 链失败时不再启动旧散文调用，保留结构化 AnswerSpec。

- [x] **Step 4: 验证通过**

运行 Task 1 的两个测试文件，预期全绿。

### Task 2: Atomic LLM attempt reservation

**Files:**
- Modify: `intelligence/services/llm_refine.py`
- Test: `intelligence/tests/test_p1b_runtime.py`

- [x] **Step 1: 写失败测试**

构造 `max_calls=1`、两个失败 provider，断言只执行一次 `urlopen`；补并发预占测试。

- [x] **Step 2: 验证测试先失败**

Run: `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_p1b_runtime.py -k 'budget'`

Expected: fallback 或并发调用超过上限。

- [x] **Step 3: 最小实现**

给 `LLMCallLedger` 增加锁和累计 reservation；四个 `_post_chat*` 在网络前预占，完成时记录；预算拒绝抛 typed exception，公共入口转为稳定降级原因。

- [x] **Step 4: 验证通过**

运行预算相关测试，预期 HTTP 次数不超过上限且账本统计正确。

### Task 3: Absolute agent deadline

**Files:**
- Modify: `intelligence/services/agent_research.py`
- Modify: `intelligence/services/ask.py`
- Modify: `intelligence/services/llm_refine.py`
- Test: `intelligence/tests/test_agent_research.py`
- Test: `intelligence/tests/test_p1b_runtime.py`

- [x] **Step 1: 写失败测试**

根 deadline 过期或 `total_seconds=0` 时，complete/tool 都不得执行；剩余 0.2 秒时传给 complete 的 timeout 不得大于剩余值。

- [x] **Step 2: 验证测试先失败**

Run: `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_agent_research.py -k 'deadline or zero_budget'`

Expected: 旧实现仍调用一次 LLM，timeout 为 15。

- [x] **Step 3: 最小实现**

`run_agent_loop` 使用绝对 `ResearchDeadline`，逐调用计算剩余时间；`llm_refine.complete/chat_with_tools` 去掉最少一秒钳制；Ask 传入 turn deadline。

- [x] **Step 4: 验证通过**

运行 agent 与 runtime 定向测试，预期零预算零副作用。

### Task 4: Evidence round-trip

**Files:**
- Modify: `intelligence/workbench_skills/research_owner.py`
- Modify: `intelligence/services/answer_model.py`
- Test: `intelligence/tests/test_workbench_research_owner_skills.py`
- Test: `intelligence/tests/test_answer_model.py`

- [x] **Step 1: 写失败测试**

构造含 candidate fact、content hash 和 source revision 的 AnswerSpec，经跨轮 merge 后断言字段保留并进入 EvidenceAtom provenance。

- [x] **Step 2: 验证测试先失败**

Run: `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_workbench_research_owner_skills.py intelligence/tests/test_answer_model.py -k 'round_trip or provenance'`

- [x] **Step 3: 最小实现**

合并 `candidate_facts`，反序列化 provenance 字段，并在派生 atom 时传播。

- [x] **Step 4: 验证通过**

运行两组契约测试，预期字段完整。

### Task 5: Query single-flight and public projection

**Files:**
- Modify: `intelligence/services/query_ledger.py`
- Modify: `intelligence/services/web_research.py`
- Modify: `intelligence/services/agent_research.py`
- Modify: `intelligence/services/conversation_orchestrator.py`
- Test: `intelligence/tests/test_p1b_runtime.py`
- Test: `intelligence/tests/test_conversation_orchestrator.py`

- [x] **Step 1: 写失败测试**

用 barrier 验证不同 key 同时进入 fetch；验证不同 limit 不复用；验证 graph citation 不暴露 relation 路径；验证重复 citation 去重。

- [x] **Step 2: 验证测试先失败**

Run: `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_p1b_runtime.py intelligence/tests/test_conversation_orchestrator.py -k 'query_ledger or citation'`

- [x] **Step 3: 最小实现**

QueryLedger 改为 per-key Future，Web key 加入行为参数；AgentEvidence 分离公开标签与内部 locator；citation sanitizer 执行稳定去重。

- [x] **Step 4: 验证通过**

运行 Task 5 测试，预期同 key 单执行、不同 key 并行、公开引用无内部路径。

### Task 6: Regression verification

**Files:**
- Modify: `docs/superpowers/plans/2026-07-19-deep-research-runtime-hardening.md`

- [x] **Step 1: 定向测试**

Run: `.venv-workbench/bin/python -m pytest -q intelligence/tests/test_p0_hardening.py intelligence/tests/test_p1b_runtime.py intelligence/tests/test_agent_research.py intelligence/tests/test_answer_model.py intelligence/tests/test_workbench_research_owner_skills.py intelligence/tests/test_grounded_presenter_general.py intelligence/tests/test_conversation_orchestrator.py`

- [x] **Step 2: 静态检查**

Run: `.venv-workbench/bin/python -m py_compile intelligence/services/ask_synthesis.py intelligence/services/llm_refine.py intelligence/services/agent_research.py intelligence/services/query_ledger.py intelligence/services/answer_model.py intelligence/workbench_skills/research_owner.py`

- [x] **Step 3: 全量测试**

Run: `.venv-workbench/bin/python -m pytest -q`

- [x] **Step 4: 检查差异**

Run: `git diff --check && git status --short`

Expected: 无 whitespace error，不包含既存未跟踪行情文件。

## Verification Result

- 相关回归：278 passed。
- 全量：2066 passed、13 failed、1 skipped；13 个失败与修改前相同，来自本地数据分类及 userspace/vault 宿主环境。
- `ruff check`、`py_compile`、`git diff --check` 全部通过。

### Task 7: Ask stage progress and root watchdog

**Files:**
- Modify: `intelligence/services/ask_types.py`
- Modify: `intelligence/services/ask.py`
- Modify: `intelligence/services/conversation_orchestrator.py`
- Test: `intelligence/tests/test_conversation_orchestrator.py`
- Test: `intelligence/tests/test_p1b_runtime.py`

- [x] **Step 1: 写失败测试**

在 orchestrator 测试中注入一个超过 `ResearchExecutionPolicy.max_elapsed_seconds`
的 `answer_query_fn`，断言 turn 在 deadline 后返回 partial、trace 含
`ask_root_timeout`，并断言超时后触发的迟到 progress 不再追加 trace。再直接调用
`answer_query` 的轻量分支，断言 progress callback 收到成对的阶段事件。

- [x] **Step 2: 验证测试先失败**

Run:
`.venv-workbench/bin/python -m pytest -q intelligence/tests/test_conversation_orchestrator.py -k 'ask_watchdog or ask_progress'`

Expected: 旧实现同步等待阻塞函数，且 `AskOptions` 不支持 progress callback。

- [x] **Step 3: 实现控制面 progress 契约**

在 `AskOptions` 增加：

```python
progress_callback: Callable[
    [str, str, dict[str, object]],
    None,
] | None = field(default=None, repr=False, compare=False)
```

在 `ask.py` 增加容错 `_emit_progress()` 和阶段 context manager；只发送阶段名、状态、
耗时及计数，不发送证据正文或内部 locator。

- [x] **Step 4: 实现 orchestrator 根看门狗**

用 `contextvars.copy_context()` 把当前 LLM/Query ledger 传入单工作线程，以根 deadline
剩余时间等待 Future。超时后设置 progress gate、`cancel()` Future、记录
`ask_root_timeout` 并返回 `_deadline_partial_result()`；executor 使用
`shutdown(wait=False, cancel_futures=True)`，不得在退出 context 时反向等待。

- [x] **Step 5: 运行定向与回归测试**

Run:
`.venv-workbench/bin/python -m pytest -q intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_p1b_runtime.py`

Expected: 全部通过。

- [x] **Step 6: 本地事故重放**

停掉旧 8795，以当前 commit 干净启动临时端口；提交事故原问题：
`我希望你基于目前的市场数据，展望一下后面市场会怎么演绎`。

Expected: 120 秒内返回完整答案或明确 partial/gap；trace 能显示最后运行的 Ask 阶段；
readiness 的行情缺口必须如实报告，不得把 process health 当成 ready。

## Task 7 Verification Result

- 根因定位：事故原问题被误分到 `general_finance_qa`，随后通用 closed-loop
  `wiki_rag` 占满根预算；语义 judge 也没有继承同一个绝对 deadline。
- 修复：新增 `market_forecast` 受约束路由；Ask 各阶段发控制面 progress；
  orchestrator 根 watchdog 有限时间返回；wiki 闭环每次子查询共享 stage deadline；
  evidence judge 继承绝对 deadline；头部预测不再自动追加长尾 `web_search` agent 能力。
- 表达收敛：无主题市场预测使用 A 股市场情景树和市场级反证，不再显示题材名、
  公司基本面、公告/L3 等错误模板；D2/D3 公司研究块不进入该车道。
- 定向回归：核心路由/预算/grounding 相关 `239 passed`；Ask/RAG 专项
  `107 passed`。另有 2 个既有 `ask_external_fallback` 分类失败，与修改前基线一致。
- 全量回归抽查：中断前 `1637 passed / 13 failed`；13 个失败与修改前记录一致，
  来自既有外部 fallback 分类以及 userspace/subconscious 宿主目录基线。随后单独运行
  当时的慢集成文件，`2 passed`。
- 真实运行：8795 readiness=`ready`，市场数据截至 `2026-07-17`；事故原问题
  `run_20260719_233025_107642` 在约 1.5 秒完成，controller=`market_forecast`，
  无 agent loop、无 closed-loop RAG，输出基准/上行/下行情景和明确前置缺口。
