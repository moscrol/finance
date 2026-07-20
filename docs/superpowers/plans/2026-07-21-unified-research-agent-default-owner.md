# Unified Research Agent 默认 Owner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把未命中确定性头部或显式工作流的金融长尾问题统一交给受约束 Research Agent，避免语义 skill router 用不匹配模板终结回答。

**Architecture:** 保留结构化行情、专项 owner、EvidenceAtom 和 grounded verifier 的硬边界；把 ownerless research 的默认控制权交给 GenericResearchOwner。Research Agent 先形成任务契约和假设，再在共享 deadline/ledger/trace 中选择白名单工具，completion gate 通过后交给动态 grounded presenter。

**Tech Stack:** Python 3.11、dataclasses、现有 `ResearchDeadline`、`QueryLedger`、`ProviderTrace`、`AnswerSpec`、pytest；不引入新 Agent 框架，不改 8792 正式 runtime。

---

## Task 1: 锁定 owner 兼容性和 ownerless 默认入口

**Files:**
- Modify: `intelligence/workbench_skills/contracts.py`
- Modify: `intelligence/workbench_skills/registry.py`
- Modify: `intelligence/services/conversation_orchestrator.py:1243-1332,1689-1805`
- Test: `intelligence/tests/test_conversation_orchestrator.py`
- Test: `intelligence/tests/test_workbench_skill_router.py`

- [x] **Step 1: 写失败测试。**

增加三个断言：

```python
def test_ownerless_research_skips_semantic_skill_router(monkeypatch):
    called = False
    def forbidden_route(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("ownerless research must use generic owner")
    # 使用没有 route-table owner 的 event_forecast/market_forecast query fixture
    # 运行 orchestrator，断言 called is False 且 trace 有 generic_research_owner。

def test_daily_agent_cannot_own_market_forecast():
    # 注入 daily-agent SkillOutput(answer_contract=...)
    # 断言 orchestrator 丢弃它并把 question_type 保持为 market_forecast。

def test_existing_explicit_daily_agent_workflow_still_runs():
    # “今天研究什么”仍允许 daily-agent 作为 workflow owner。
```

- [x] **Step 2: 扩展 skill metadata。**

在 `SkillDefinition` 增加默认字段 `role: Literal["workflow", "research_profile", "terminal_owner"] = "workflow"`、`accepted_question_types: tuple[str, ...] = ()` 和 `can_own_answer: bool = False`。日报技能标为 `workflow/can_own_answer=True`，专项 ResearchOwner 标为 `terminal_owner` 并填写各自 question type。

- [x] **Step 3: 扩大 generic_owner_requested。**

在 orchestrator 中把条件改为：`decision.lane == "research"`、`turn_intent.answer_owner is None`、不是 `market_technical`/`external_market` 等确定性 Ask head，并且没有用户手动选 skill。该分支设置 `route_skills` 不调用，直接创建 GenericResearchOwner contract。

- [x] **Step 4: 添加终端 contract 兼容闸门。**

在消费 `owner_output` 前检查：workflow 只能在 workflow lane；terminal owner 的 `question_type` 必须等于 controller question type；`None` 或不一致时丢弃输出并回退 GenericResearchOwner/Ask。trace 记录 `owner_contract_rejected`、expected/actual 和 reason。

- [x] **Step 5: 运行测试并提交。**

Run: `python3 -m pytest -q intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_workbench_skill_router.py -k 'ownerless or daily_agent or market_forecast or workflow'`

Expected: 新测试通过，原有 workflow/专项 owner 测试不回归。

```bash
git add intelligence/workbench_skills/contracts.py intelligence/workbench_skills/registry.py intelligence/services/conversation_orchestrator.py intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_workbench_skill_router.py
git commit -m "fix: make generic research the ownerless default"
```

## Task 2: 让 GenericResearchOwner 能处理行情和情景长尾

**Files:**
- Modify: `intelligence/services/conversation_orchestrator.py:125-267`
- Modify: `intelligence/services/ask.py:1140-1320`
- Modify: `intelligence/services/agent_research.py:461-480,638-749`
- Modify: `intelligence/services/research_state.py:93-266`
- Test: `intelligence/tests/test_generic_research_owner.py`
- Test: `intelligence/tests/test_agent_research.py`

- [x] **Step 1: 写失败测试。**

覆盖：`market_forecast` contract 必须有 `rebound_case`、`decline_case`、`invalidation`；forecast generic owner 必须预取一次结构化市场数据；finish 在必需情景没有证据时不能标 completed；空结果连续两次后报 gap。

- [x] **Step 2: 扩展通用 contract。**

在 `_build_generic_research_contract()` 增加 `market_forecast`/`event_forecast`/`comparison` 的 profile 和 required outputs；能力允许 `market_data`、`web_search`、`news_search`、`graph_lookup`，但仍由 registry 白名单钳制。问题主体为空时使用 `A股市场`，不得把整句问题写成 subject。

- [x] **Step 3: 注入结构化 market_data。**

把 generic owner 当前只对 `market_cause` 注册的 `market_data` 扩展到 `market_forecast`，返回最新市场总览与必要的多日窗口。预取结果进入同一 `ResearchState` 和 ProviderTrace，不再让 Agent 自己决定是否取得真值底座。

- [x] **Step 4: 扩展 Agent 动作协议。**

在 action args 中支持可选 `hypothesis_ids` 和 `stance`（support/contradict/context）；代码只接受当前 state 中存在的 hypothesis id，并用 `dataclasses.replace` 为 accepted evidence 写入 supports/contradicts。把系统提示中的“一句话判断”改成“覆盖任务要求的简洁分析草稿”，assessment 上限提高到 1600 字。

- [x] **Step 5: 初始化和检查假设覆盖。**

`ResearchState.from_contract()` 初始化 contract 的情景假设；completion evaluator 将“每个必需情景有支持、反驳或明确 gap”纳入 task coverage。LLM 的 `finish(sufficient=true)` 若还有未覆盖必需项，且预算未耗尽，记录 finish rejection 并继续一次循环。

- [x] **Step 6: 运行测试并提交。**

Run: `python3 -m pytest -q intelligence/tests/test_generic_research_owner.py intelligence/tests/test_agent_research.py -k 'forecast or hypothesis or completion or no_information'`

Expected: 情景题不会只返回一个 assessment；预算、白名单、重复查询测试保持通过。

```bash
git add intelligence/services/conversation_orchestrator.py intelligence/services/ask.py intelligence/services/agent_research.py intelligence/services/research_state.py intelligence/tests/test_generic_research_owner.py intelligence/tests/test_agent_research.py
git commit -m "feat: give generic owner scenario and market research tools"
```

## Task 3: 将任务规划、证据完成度和表达出口接通

**Files:**
- Create: `intelligence/services/research_task_planner.py`
- Modify: `intelligence/services/generic_research_owner.py`
- Modify: `intelligence/services/ask.py:1469-1610`
- Modify: `intelligence/services/ask_synthesis.py`
- Test: `intelligence/tests/test_generic_research_owner.py`
- Test: `intelligence/tests/test_answer_orchestrator.py`

- [x] **Step 1: 写失败测试。**

对未知长尾 query 注入合法/非法 planner JSON，断言合法 JSON 只影响子问题和假设，不得扩张 capability；非法 JSON 使用规则 fallback。断言 generic output 的下一步是业务验证动作，不出现“逐条通过语义闸门”等控制面语句。

- [x] **Step 2: 实现受钳制 task planner。**

`research_task_planner.plan_task()` 使用一次短 LLM 调用生成最多 5 个子问题和 4 个假设；schema 失败或超时返回规则 contract。planner 不能新增工具、提升 research tier 或删除硬 required output，所有字段做长度和白名单校验。

- [x] **Step 3: 统一 generic completion projection。**

把 completion status、hypothesis coverage 和 typed gaps 投影到 AnswerSpec 的 claims/next_actions；把“研究 agent 的暂定判断”改成真实判断文本，控制面诊断只进 trace。缺证据时输出“已知、未知、下一验证窗口”，不生成 generic_theme/研究雷达模板。

- [x] **Step 4: 保持 grounded presenter 的表达自由。**

generic contract 只要求证据/推论绑定，不要求固定标题、固定行数或逐句 marker。Grounded verifier 失败时保留 validated brief 和业务化 gap，不调用 Daily Agent 或旧模板作为 fallback。

- [x] **Step 5: 运行测试并提交。**

Run: `python3 -m pytest -q intelligence/tests/test_generic_research_owner.py intelligence/tests/test_answer_orchestrator.py -k 'planner or grounded or dynamic or generic'`

Expected: planner 失败可回退，出口不泄漏控制面，不引入模板回退。

```bash
git add intelligence/services/research_task_planner.py intelligence/services/generic_research_owner.py intelligence/services/ask.py intelligence/services/ask_synthesis.py intelligence/tests/test_generic_research_owner.py intelligence/tests/test_answer_orchestrator.py
git commit -m "feat: connect task planning completion and grounded presentation"
```

## Task 4: 建立长尾能力回归和真实隔离 runtime 验收

**Files:**
- Create: `intelligence/tests/fixtures/long_tail_cases.json`
- Modify: `intelligence/tests/test_conversation_orchestrator.py`
- Modify: `docs/verification/agent-capability-monotonicity-2026-07-20.md`
- Modify: `docs/workbench/canonical-8792-cutover.md`

- [x] **Step 1: 写长尾 fixture。**

至少登记：T+1 情景、开放事件、陌生题材、两跳关系、错误前提、缺关键数字、多对象比较、连续追问、显式日报。每题记录预期 owner、必需证据类型、禁止模板和最大档位。

- [x] **Step 2: 增加端到端断言。**

断言长尾 run 的 route trace 为 generic owner、无 daily-agent/daily-review selection；answer 中有直接回答、证据/缺口和下一验证；trace 中有统一 parent id、budget、completion、grounding 状态。

- [x] **Step 3: 运行后端回归。**

Run: `env -u FORESIGHT_USERS_DIR -u FORESIGHT_USER -u SUBCONSCIOUS_VAULT -u AGENT_MEMORY_VAULT PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q intelligence/tests`

Expected: 全套 intelligence 测试通过，保留已知环境相关跳过，不新增失败。

- [x] **Step 4: 启动隔离 runtime 并跑真实问题。**

使用当前分支构建新的临时 runtime/端口，不修改 8792。运行：`明天你觉得是反弹还是继续下跌，分别给出理由`、`浪潮信息的客户的竞争对手有哪些`、`一个没有现成 skill 的陌生题材怎么判断`。保存 run id、answer、trace 和耗时。

- [x] **Step 5: 更新验收记录并提交。**

将长尾 E2E 结果写入验证文档，明确哪些题型已进入统一 Agent、哪些仍是确定性 head；不把未跑的 8792 切换写成完成。

```bash
git add intelligence/tests/fixtures/long_tail_cases.json intelligence/tests/test_conversation_orchestrator.py docs/verification/agent-capability-monotonicity-2026-07-20.md docs/workbench/canonical-8792-cutover.md
git commit -m "test: add long-tail agent capability regression matrix"
```
