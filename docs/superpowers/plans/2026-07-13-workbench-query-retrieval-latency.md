# Workbench Query Understanding and Retrieval Latency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让通用市场问题不再被整句误识别为题材，并让 Workbench 在严格证据门不降级的前提下，于 60 秒内返回正常或保守降级答案。

**Architecture:** 新增确定性的 `QueryEnvelope` 作为路由、AnswerPlan 和 RAG 的共同问题理解结果；新增 `ExecutionBudget`，把同一个单调时钟截止时间传给技能、BM25、一次可选的 BGE-m3 语义召回和最终合成。检索采用 BM25 优先、语义召回最多一次、相关性先于证据硬度，并通过 `stage.progress` 事件把真实阶段显示到 UI。

**Tech Stack:** Python 3.11 dataclass、pytest、FastAPI/SSE、现有 BM25 + BGE-m3 Hybrid RAG、React 19、TypeScript、Vitest、pnpm 10。

---

## File map

- Create `intelligence/services/query_understanding.py`: 唯一的问题对象、题型和时间范围解析器。
- Create `intelligence/tests/test_query_understanding.py`: 问题信封的正反例。
- Modify `intelligence/services/answer_model.py`: 删除“完整问句即题材”兜底。
- Modify `intelligence/services/answer_orchestrator.py`: 把 `QueryEnvelope` 挂入 `QuestionPlan`。
- Modify `intelligence/workbench_skills/router.py`: 自动路由使用 envelope；手动选择仍被尊重。
- Modify `intelligence/tests/test_answer_model.py`: 题材名安全回退回归。
- Modify `intelligence/tests/test_answer_orchestrator.py`: QuestionPlan 与通用市场模式回归。
- Modify `intelligence/tests/test_workbench_skill_router.py`: 自动/混合/手动 owner 路由回归。
- Create `intelligence/services/execution_budget.py`: 单调时钟截止时间和子调用 timeout 计算。
- Create `intelligence/tests/test_execution_budget.py`: 截止时间数学与边界测试。
- Modify `intelligence/services/ask.py`: 接收 envelope/budget，跳过无对象 RAG，传递剩余 timeout。
- Modify `intelligence/workbench_skills/contracts.py`: 将 budget 放入 skill context。
- Modify `intelligence/workbench_skills/research_owner.py`: owner 与通用 Ask 共用同一 deadline。
- Modify `intelligence/services/closed_loop_retrieval.py`: BM25 优先、最多一次语义召回、fail-fast、相关性门禁。
- Modify `intelligence/services/kb_rag.py`: 浮点 timeout、非 fresh 遥测、dense 初始化计数。
- Modify `intelligence/tests/test_closed_loop_retrieval.py`: 调用次数、mode、fail-fast、相关性回归。
- Modify `intelligence/tests/test_kb_rag.py`: timeout 与 dense 遥测回归。
- Modify `intelligence/services/conversation_orchestrator.py`: 创建并传递 60 秒 budget，发出阶段事件，超时走确定性答案。
- Modify `intelligence/api/app.py`: conversation supervisor 留出终态落盘缓冲，硬超时也保留可读提示。
- Modify `intelligence/tests/test_conversation_orchestrator.py`: deadline、owner、fallback、阶段事件回归。
- Modify `intelligence/tests/test_workbench_api.py`: supervisor 超时消息非空回归。
- Modify `intelligence/webapp/src/types.ts`: live stage 类型。
- Modify `intelligence/webapp/src/streamEvents.ts`: 消费 `stage.progress`。
- Modify `intelligence/webapp/src/App.tsx`: 订阅阶段事件。
- Modify `intelligence/webapp/src/components/MessageBubble.tsx`: 显示当前人话阶段。
- Modify `intelligence/webapp/src/displayText.ts`: 五阶段中文标签。
- Modify `intelligence/webapp/src/components/components.test.tsx`: stage reducer 与 UI 回归。
- Rebuild `intelligence/api/static/`: 提交与源码一致的生产前端 bundle。
- Modify `scripts/smoke_workbench_self_use.py`: 在摘要中记录端到端 elapsed 和阶段序列，供真实 UI 验收留证。

### Task 1: Add deterministic QueryEnvelope and remove full-query theme fallback

**Files:**
- Create: `intelligence/services/query_understanding.py`
- Create: `intelligence/tests/test_query_understanding.py`
- Modify: `intelligence/services/answer_model.py:971-978`
- Modify: `intelligence/tests/test_answer_model.py:18-55`

- [ ] **Step 1: Write the failing QueryEnvelope tests**

```python
from intelligence.services.entity_anchor import EntityAnchor
from intelligence.services.query_understanding import understand_query


GENERIC_LIFECYCLE_QUERY = (
    "如果一个A股题材连续上涨，但板块成交占比开始下降，我应该怎么判断"
    "它是健康分歧还是行情高潮？"
)


def test_generic_market_pattern_has_no_invented_subject() -> None:
    envelope = understand_query(GENERIC_LIFECYCLE_QUERY)
    assert envelope.subject_kind == "market_pattern"
    assert envelope.subject is None
    assert envelope.question_type == "general_finance_qa"
    assert envelope.decision_goal == "区分健康分歧与行情高潮"


def test_known_alias_and_entity_are_explicit_subjects() -> None:
    theme = understand_query("液冷题材连续上涨但成交占比下降，怎么看？")
    new_theme = understand_query("请研究空芯光纤题材的产业链")
    company = understand_query(
        "英维克怎么看",
        anchor=EntityAnchor(entity="英维克", ticker="002837.SZ", concepts=("液冷",)),
    )
    assert (theme.subject_kind, theme.subject, theme.matched_by) == (
        "theme", "液冷", "alias"
    )
    assert (new_theme.subject_kind, new_theme.subject, new_theme.matched_by) == (
        "theme", "空芯光纤", "explicit"
    )
    assert (company.subject_kind, company.subject, company.matched_by) == (
        "company", "英维克", "entity"
    )


def test_empty_or_unknown_query_never_becomes_a_theme() -> None:
    assert understand_query("").subject is None
    assert understand_query("帮我看看这个").subject is None
```

- [ ] **Step 2: Run the tests and confirm the missing module failure**

Run: `python3 -m pytest intelligence/tests/test_query_understanding.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: intelligence.services.query_understanding`.

- [ ] **Step 3: Implement the focused query-understanding module**

```python
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from intelligence.services.entity_anchor import EntityAnchor

SubjectKind = Literal["company", "theme", "market_pattern", "unknown"]
MatchedBy = Literal[
    "ticker", "entity", "candidate", "alias", "quoted", "explicit", "generic"
]

THEME_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "theme_research_specs.json"
)
_DATE_RE = re.compile(r"\b20\d{2}[-/.年]\d{1,2}(?:[-/.月]\d{1,2}日?)?\b")
_QUOTED_RE = re.compile(r"[“《\"]([^”》\"]{2,40})[”》\"]")
_TICKER_RE = re.compile(r"\b\d{6}(?:\.(?:SH|SZ|BJ))?\b", re.I)
_EXPLICIT_THEME_RE = re.compile(
    r"(?:研究|分析|看看|深挖)\s*([\u4e00-\u9fffA-Za-z0-9+.-]{2,16})"
    r"(?:题材|板块|产业链|方向)"
)
_MARKET_PATTERN_TERMS = (
    "连续上涨", "成交占比", "涨停家数", "指数上涨", "背离", "健康分歧", "行情高潮"
)


@dataclass(frozen=True)
class QueryEnvelope:
    question_type: str
    subject_kind: SubjectKind
    subject: str | None
    decision_goal: str
    timeframe: str | None
    matched_by: MatchedBy
    confidence: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@lru_cache(maxsize=1)
def _theme_aliases() -> tuple[str, ...]:
    try:
        doc = json.loads(THEME_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    aliases = [
        str(alias).strip()
        for pack in doc.get("packs", [])
        if isinstance(pack, dict)
        for alias in pack.get("aliases", [])
        if str(alias).strip()
    ]
    return tuple(sorted(dict.fromkeys(aliases), key=len, reverse=True))


def _decision_goal(query: str) -> str:
    if "健康分歧" in query or "行情高潮" in query:
        return "区分健康分歧与行情高潮"
    if "背离" in query:
        return "解释市场背离"
    return "形成条件化判断"


def understand_query(
    query: str,
    *,
    matched_theme: str | None = None,
    anchor: EntityAnchor | None = None,
) -> QueryEnvelope:
    text = str(query or "").strip()
    timeframe_match = _DATE_RE.search(text)
    timeframe = timeframe_match.group(0) if timeframe_match else None
    if anchor is not None:
        return QueryEnvelope(
            "stock_deep_dive", "company", anchor.entity,
            _decision_goal(text), timeframe,
            "ticker" if anchor.matched_by == "code" else "entity", 1.0,
        )
    if matched_theme:
        return QueryEnvelope(
            "theme_analysis", "theme", matched_theme.strip(),
            _decision_goal(text), timeframe, "candidate", 0.98,
        )
    for alias in _theme_aliases():
        if alias.casefold() in text.casefold():
            return QueryEnvelope(
                "theme_analysis", "theme", alias,
                _decision_goal(text), timeframe, "alias", 0.92,
            )
    quoted = _QUOTED_RE.search(text)
    if quoted:
        return QueryEnvelope(
            "theme_analysis", "theme", quoted.group(1).strip(),
            _decision_goal(text), timeframe, "quoted", 0.72,
        )
    if sum(term in text for term in _MARKET_PATTERN_TERMS) >= 2:
        return QueryEnvelope(
            "general_finance_qa", "market_pattern", None,
            _decision_goal(text), timeframe, "generic", 0.9,
        )
    explicit = _EXPLICIT_THEME_RE.search(text)
    if explicit:
        return QueryEnvelope(
            "theme_analysis", "theme", explicit.group(1).strip(),
            _decision_goal(text), timeframe, "explicit", 0.8,
        )
    if _TICKER_RE.search(text):
        return QueryEnvelope(
            "stock_deep_dive", "company", _TICKER_RE.search(text).group(0),
            _decision_goal(text), timeframe, "ticker", 0.82,
        )
    return QueryEnvelope(
        "general_finance_qa", "unknown", None,
        _decision_goal(text), timeframe, "generic", 0.4 if text else 0.1,
    )
```

In `answer_model._theme_name`, replace the final line with:

```python
    return matched_theme or "未命名题材"
```

Add this regression to `ThemeResearchSpecTests`:

```python
    def test_generic_question_is_not_reused_as_theme_name(self) -> None:
        query = "如果一个A股题材连续上涨，怎么区分健康分歧和行情高潮？"
        spec = resolve_theme_research_spec(query)
        self.assertEqual(spec.theme, "未命名题材")
        self.assertNotEqual(spec.theme, query)
```

- [ ] **Step 4: Run focused tests and verify green**

Run: `python3 -m pytest intelligence/tests/test_query_understanding.py intelligence/tests/test_answer_model.py -q`

Expected: PASS; no test may assert that the full query is a theme.

- [ ] **Step 5: Commit the problem-understanding boundary**

```bash
git add intelligence/services/query_understanding.py intelligence/services/answer_model.py intelligence/tests/test_query_understanding.py intelligence/tests/test_answer_model.py
git commit -m "fix: separate market patterns from explicit themes"
```

### Task 2: Make QuestionPlan and skill routing consume QueryEnvelope

**Files:**
- Modify: `intelligence/services/answer_orchestrator.py:90-225`
- Modify: `intelligence/workbench_skills/router.py:35-180`
- Modify: `intelligence/services/conversation_orchestrator.py:515-550`
- Modify: `intelligence/tests/test_answer_orchestrator.py`
- Modify: `intelligence/tests/test_workbench_skill_router.py`
- Modify: `intelligence/tests/test_conversation_orchestrator.py`

- [ ] **Step 1: Write failing planning and routing tests**

Add to `test_answer_orchestrator.py`:

```python
def test_market_pattern_plan_uses_base_finance_without_research_spec() -> None:
    plan = plan_answer_question(
        "如果一个A股题材连续上涨，但板块成交占比下降，"
        "怎么判断健康分歧还是行情高潮？"
    )
    assert plan.query_envelope.subject_kind == "market_pattern"
    assert plan.query_envelope.subject is None
    assert plan.question_type == QUESTION_GENERAL
    assert plan.research_spec is None
```

Add to `test_workbench_skill_router.py`:

```python
def test_auto_market_pattern_cannot_select_theme_owner() -> None:
    query = "题材连续上涨但成交占比下降，是健康分歧还是行情高潮？"
    envelope = understand_query(query)
    result = route_skills(
        query,
        "ask",
        "auto",
        [],
        registry={"theme-research": definition("theme-research", "题材")},
        llm_complete=llm_response(
            '{"skill_ids":["theme-research"],"reasons":{"theme-research":"题材"}}'
        ),
        query_envelope=envelope,
    )
    assert result.selections == ()
    assert result.base_finance_fallback is True


def test_manual_theme_owner_is_still_respected_for_market_pattern() -> None:
    query = "题材连续上涨但成交占比下降，是健康分歧还是行情高潮？"
    result = route_skills(
        query,
        "ask",
        "manual",
        ["theme-research"],
        registry={"theme-research": definition("theme-research", "题材")},
        query_envelope=understand_query(query),
    )
    assert [item.skill_id for item in result.selections] == ["theme-research"]
```

- [ ] **Step 2: Run focused tests and confirm field/signature failures**

Run: `python3 -m pytest intelligence/tests/test_answer_orchestrator.py intelligence/tests/test_workbench_skill_router.py -q`

Expected: FAIL because `QuestionPlan.query_envelope` and `route_skills(..., query_envelope=...)` do not exist.

- [ ] **Step 3: Wire the envelope into planning and automatic routing**

In `answer_orchestrator.py`, add the field, serialization and optional anchor:

```python
from intelligence.services.entity_anchor import EntityAnchor
from intelligence.services.query_understanding import QueryEnvelope, understand_query

@dataclass(frozen=True)
class QuestionPlan:
    query: str
    question_type: str
    depth: str
    confidence: float
    query_envelope: QueryEnvelope
    required_lenses: list[str] = field(default_factory=list)
    retrieval_plan: list[str] = field(default_factory=list)
    quality_gates: list[str] = field(default_factory=list)
    output_contract: list[str] = field(default_factory=list)
    missing_data_policy: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    research_spec: ThemeResearchSpec | None = None
    base_finance_mode: BaseFinanceMode | None = None
```

In `to_dict()` add:

```python
            "query_envelope": self.query_envelope.to_dict(),
```

Change the planner signature and classification block:

```python
def plan_answer_question(
    query: str,
    matched_theme: str | None = None,
    *,
    question_type_override: str | None = None,
    anchor: EntityAnchor | None = None,
) -> QuestionPlan:
    raw_query = str(query or "").strip()
    envelope = understand_query(raw_query, matched_theme=matched_theme, anchor=anchor)
    if not raw_query:
        return QuestionPlan(
            query=raw_query,
            question_type=QUESTION_GENERAL,
            depth=DEPTH_QUICK,
            confidence=0.1,
            query_envelope=envelope,
            required_lenses=["先要求用户补充题材、个股、日期或材料"],
            retrieval_plan=[],
            quality_gates=["不能在问题为空时编造分析对象"],
            output_contract=["请用户补充问题"],
            missing_data_policy=["问题为空，必须追问"],
            warnings=["empty query"],
        )
    q = _normalize(raw_query)
    if question_type_override is not None and question_type_override not in QUESTION_TYPES:
        raise ValueError("unknown question type override")
    if question_type_override is not None:
        question_type, confidence = question_type_override, 1.0
    elif envelope.subject_kind == "market_pattern":
        question_type, confidence = QUESTION_GENERAL, envelope.confidence
    elif envelope.subject_kind in {"company", "theme"}:
        question_type, confidence = envelope.question_type, envelope.confidence
    else:
        question_type, confidence = _classify_question_type(raw_query, q)
```

Construct `research_spec` only from an explicit subject:

```python
    research_spec = (
        resolve_theme_research_spec(raw_query, envelope.subject)
        if question_type in {
            QUESTION_THEME_ANALYSIS,
            QUESTION_NEWS_IMPACT,
            QUESTION_STOCK_DEEP_DIVE,
        }
        else None
    )
```

In `router.py`, add `query_envelope: QueryEnvelope | None = None` to `route_skills`. Build an automatic-only registry before `_rule_candidates` and before the LLM candidate list:

```python
    automatic_registry = active_registry
    if query_envelope is not None and query_envelope.subject_kind == "market_pattern":
        automatic_registry = {
            skill_id: definition
            for skill_id, definition in active_registry.items()
            if skill_id != "theme-research"
        }
    rules = _rule_candidates(query, task_type, automatic_registry)
```

Use `automatic_registry` for LLM candidates and parse validation. Continue using `active_registry` for manual IDs.

In `TurnOrchestrator.run_turn`, build once before routing and pass it through:

```python
            routing_envelope = understand_query(contextual_query)
            route = self.route_skills(
                contextual_query,
                "ask",
                skill_mode,
                selected_skill_ids,
                registry=self.skill_registry.definitions,
                query_envelope=routing_envelope,
            )
```

Add `query_envelope` to the `route_skills` trace payload so inspector evidence can distinguish a rule decision from an invented topic.

- [ ] **Step 4: Run planner, router and conversation regressions**

Run: `python3 -m pytest intelligence/tests/test_answer_orchestrator.py intelligence/tests/test_workbench_skill_router.py intelligence/tests/test_conversation_orchestrator.py -q`

Expected: PASS, including existing manual, auto, hybrid and owner tests.

- [ ] **Step 5: Commit the shared routing contract**

```bash
git add intelligence/services/answer_orchestrator.py intelligence/workbench_skills/router.py intelligence/services/conversation_orchestrator.py intelligence/tests/test_answer_orchestrator.py intelligence/tests/test_workbench_skill_router.py intelligence/tests/test_conversation_orchestrator.py
git commit -m "fix: route workbench turns from structured query intent"
```

### Task 3: Add a shared monotonic ExecutionBudget contract

**Files:**
- Create: `intelligence/services/execution_budget.py`
- Create: `intelligence/tests/test_execution_budget.py`
- Modify: `intelligence/services/ask.py:140-245`
- Modify: `intelligence/workbench_skills/contracts.py:185-225`
- Modify: `intelligence/tests/test_workbench_skill_router.py:35-75`

- [ ] **Step 1: Write the failing budget tests**

```python
from intelligence.services.execution_budget import ExecutionBudget


def test_child_timeout_never_exceeds_request_or_remaining_budget() -> None:
    budget = ExecutionBudget(started_at=100.0, deadline_at=160.0)
    assert budget.remaining_seconds(now=120.0) == 40.0
    assert budget.child_timeout(90.0, reserve=10.0, now=120.0) == 30.0
    assert budget.child_timeout(5.0, reserve=10.0, now=120.0) == 5.0


def test_exhausted_budget_returns_zero_child_timeout() -> None:
    budget = ExecutionBudget(started_at=100.0, deadline_at=110.0)
    assert budget.exhausted(now=111.0) is True
    assert budget.child_timeout(30.0, reserve=2.0, now=111.0) == 0.0
```

- [ ] **Step 2: Run the test and confirm the missing module failure**

Run: `python3 -m pytest intelligence/tests/test_execution_budget.py -q`

Expected: FAIL during collection because `execution_budget.py` is absent.

- [ ] **Step 3: Implement the budget and add it to request contracts**

```python
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionBudget:
    started_at: float
    deadline_at: float

    @classmethod
    def start(cls, total_seconds: float) -> "ExecutionBudget":
        started_at = time.monotonic()
        return cls(started_at, started_at + max(0.0, total_seconds))

    def remaining_seconds(self, *, now: float | None = None) -> float:
        current = time.monotonic() if now is None else now
        return max(0.0, self.deadline_at - current)

    def child_timeout(
        self,
        requested: float,
        *,
        reserve: float = 0.0,
        now: float | None = None,
    ) -> float:
        available = max(0.0, self.remaining_seconds(now=now) - max(0.0, reserve))
        return min(max(0.0, requested), available)

    def exhausted(self, *, now: float | None = None) -> bool:
        return self.remaining_seconds(now=now) <= 0.0
```

Add to `AskOptions`:

```python
    execution_budget: ExecutionBudget | None = field(
        default=None, repr=False, compare=False
    )
```

Add at the end of `SkillExecutionContext`:

```python
    execution_budget: ExecutionBudget | None = None
```

Update the exact field-list assertion in `test_workbench_skill_router.py` to include `execution_budget` after `conversation_context`.

- [ ] **Step 4: Run budget and contract tests**

Run: `python3 -m pytest intelligence/tests/test_execution_budget.py intelligence/tests/test_workbench_skill_router.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the deadline primitive**

```bash
git add intelligence/services/execution_budget.py intelligence/services/ask.py intelligence/workbench_skills/contracts.py intelligence/tests/test_execution_budget.py intelligence/tests/test_workbench_skill_router.py
git commit -m "feat: add shared workbench execution budget"
```

### Task 4: Replace nine Hybrid subprocesses with budgeted layered retrieval

**Files:**
- Modify: `intelligence/services/closed_loop_retrieval.py`
- Modify: `intelligence/tests/test_closed_loop_retrieval.py`

- [ ] **Step 1: Replace old retry expectations with mode/budget/fail-fast tests**

Use this fake signature throughout the test file:

```python
def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
    calls.append((query, mode, timeout))
    return _response(query, [])
```

Add these cases:

```python
def test_generic_query_without_subject_skips_wiki_retrieval() -> None:
    calls: list[tuple[str, str, float]] = []
    result = retrieve_closed_loop(
        "题材连续上涨但成交占比下降",
        anchor=None,
        subject=None,
        retrieve=lambda query, mode, timeout: calls.append((query, mode, timeout)),
    )
    assert calls == []
    assert "no explicit subject" in " ".join(result.warnings)


def test_empty_subject_path_uses_three_bm25_calls_and_at_most_one_hybrid() -> None:
    calls: list[tuple[str, str, float]] = []
    budget = ExecutionBudget(started_at=0.0, deadline_at=60.0)

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        calls.append((query, mode, timeout))
        return _response(query, [])

    result = retrieve_closed_loop(
        "液冷怎么看", anchor=None, subject="液冷", retrieve=retrieve,
        budget=budget, now=lambda: 1.0,
    )
    assert [mode for _, mode, _ in calls].count("bm25") == 3
    assert [mode for _, mode, _ in calls].count("hybrid") == 1
    assert result.dense_initializations == 1


def test_nonrecoverable_status_stops_rewrites() -> None:
    calls: list[str] = []

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        calls.append(query)
        return WikiRagResult(telemetry=RetrievalTelemetry(status="timeout"))

    result = retrieve_closed_loop(
        "液冷怎么看", anchor=None, subject="液冷", retrieve=retrieve
    )
    assert len(calls) == 1
    assert result.attempts[0].status == "timeout"


def test_irrelevant_hard_source_is_discarded_before_authority_check() -> None:
    calls = 0

    def retrieve(query: str, mode: str, timeout: float) -> WikiRagResult:
        nonlocal calls
        calls += 1
        hit = _hit("半导体设备公告", 0.8, hardness="hard") if calls == 1 else None
        return _response(query, [hit] if hit else [])

    result = retrieve_closed_loop(
        "液冷怎么看", anchor=None, subject="液冷", retrieve=retrieve
    )
    assert result.conclusion == []
    assert any(item.hit.title == "半导体设备公告" for item in result.discarded)
```

Update three pre-existing cases to the new two-stage evidence rule: in `test_closed_loop_uses_entity_code_broad_terms_and_counter_queries`, construct “液冷服务器” and “温控设备” with `hardness="hard"`; in `test_relevant_hit_is_scale_independent_for_rrf_scores`, replace the conclusion assertion with `assert [item.hit.title for item in result.clues] == ["液冷需求"]`; in `test_hard_evidence_can_enter_conclusion_at_lower_score`, use query `"液冷公告影响"` so relevance and source hardness are both satisfied.

- [ ] **Step 2: Run the focused tests and confirm signature/behavior failures**

Run: `python3 -m pytest intelligence/tests/test_closed_loop_retrieval.py -q`

Expected: FAIL because the old retriever accepts one argument and deliberately makes up to nine Hybrid calls.

- [ ] **Step 3: Implement the layered retrieval contract**

Change the public types:

```python
RetrievalMode: TypeAlias = Literal["bm25", "hybrid"]
Retrieve: TypeAlias = Callable[[str, RetrievalMode, float], WikiRagResult]

@dataclass(frozen=True)
class RetrievalAttempt:
    aperture: RetrievalAperture
    query: str
    mode: RetrievalMode
    status: str
    hit_count: int
    timeout_seconds: float

@dataclass
class ClosedLoopRetrievalResult:
    # preserve existing buckets, attempts, warnings and telemetry
    dense_initializations: int = 0
```

Use one query per aperture and only one semantic fallback:

```python
def retrieve_closed_loop(
    query: str,
    *,
    anchor: EntityAnchor | None,
    subject: str | None,
    retrieve: Retrieve,
    budget: ExecutionBudget | None = None,
    semantic_min_seconds: float = 15.0,
    now: Callable[[], float] = time.monotonic,
) -> ClosedLoopRetrievalResult:
    result = ClosedLoopRetrievalResult()
    explicit_subject = anchor.entity if anchor is not None else str(subject or "").strip()
    if not explicit_subject:
        result.warnings.append("wiki-rag skipped: no explicit subject")
        return result

    entries: list[tuple[str, WikiHit]] = []
    narrow_query = _narrow_queries(explicit_subject, anchor)[0]
    narrow_hits, stop = _run_one(
        "narrow", narrow_query, "bm25", retrieve, result, budget, now
    )
    entries.extend(("narrow", hit) for hit in narrow_hits)
    if not stop:
        broad_query = _broad_queries(explicit_subject, anchor, narrow_hits)[0]
        broad_hits, stop = _run_one(
            "broad", broad_query, "bm25", retrieve, result, budget, now
        )
        entries.extend(("broad", hit) for hit in broad_hits)
    if not stop:
        counter_query = _counter_queries(explicit_subject, anchor, narrow_hits)[0]
        counter_hits, stop = _run_one(
            "counter", counter_query, "bm25", retrieve, result, budget, now
        )
        entries.extend(("counter", hit) for hit in counter_hits)

    _bucket_hits(
        entries,
        result,
        relevance_terms=_relevance_terms(explicit_subject, anchor, narrow_hits),
        broad_relevance_terms=_relevance_terms(explicit_subject, anchor, narrow_hits),
    )
    remaining = budget.remaining_seconds(now=now()) if budget is not None else 90.0
    if not stop and not result.conclusion and remaining >= semantic_min_seconds:
        semantic_hits, _ = _run_one(
            "narrow", narrow_query, "hybrid", retrieve, result, budget, now
        )
        result.dense_initializations += 1
        _bucket_hits(
            [("narrow", hit) for hit in semantic_hits],
            result,
            relevance_terms=_relevance_terms(explicit_subject, anchor, semantic_hits),
            broad_relevance_terms=_relevance_terms(explicit_subject, anchor, semantic_hits),
        )
    return result
```

Implement the single-attempt helper exactly once:

```python
def _run_one(
    aperture: RetrievalAperture,
    query: str,
    mode: RetrievalMode,
    retrieve: Retrieve,
    result: ClosedLoopRetrievalResult,
    budget: ExecutionBudget | None,
    now: Callable[[], float],
) -> tuple[list[WikiHit], bool]:
    timeout_seconds = (
        10.0
        if budget is None
        else budget.child_timeout(10.0, reserve=5.0, now=now())
    )
    if timeout_seconds <= 0:
        result.warnings.append("wiki-rag skipped: execution budget exhausted")
        result.attempts.append(
            RetrievalAttempt(aperture, query, mode, "timeout", 0, 0.0)
        )
        return [], True
    response = retrieve(query, mode, timeout_seconds)
    result.telemetry = response.telemetry
    result.attempts.append(
        RetrievalAttempt(
            aperture,
            query,
            mode,
            response.telemetry.status,
            len(response.hits),
            timeout_seconds,
        )
    )
    if response.warning and response.warning not in result.warnings:
        result.warnings.append(response.warning)
    nonrecoverable = response.telemetry.status in {"skipped", "error", "timeout"}
    nonfresh = response.telemetry.index_freshness in {"stale", "unknown"}
    return (response.hits if response.ok else []), nonrecoverable or nonfresh
```

Change `_bucket_hits` so every positive hit first requires `direct_overlap`. In particular, move the counter and hard-source branches below:

```python
        if not direct_overlap or hit.score <= 0:
            result.discarded.append(item)
            continue
        if typed_aperture == "counter":
            result.counter_clues.append(item)
            result.clues.append(item)
            continue
        if hard_source:
            result.conclusion.append(item)
        else:
            result.clues.append(item)
```

Seed `_bucket_hits` deduplication from all existing buckets so the one Hybrid fallback cannot duplicate a BM25 hit.

- [ ] **Step 4: Run retrieval tests and confirm the dense cap**

Run: `python3 -m pytest intelligence/tests/test_closed_loop_retrieval.py -q`

Expected: PASS; the empty explicit-subject path has 4 subprocess calls rather than 9 model-loading calls, and `dense_initializations <= 1`.

- [ ] **Step 5: Commit the cost-aware retrieval policy**

```bash
git add intelligence/services/closed_loop_retrieval.py intelligence/tests/test_closed_loop_retrieval.py
git commit -m "perf: budget closed-loop retrieval to one dense query"
```

### Task 5: Propagate remaining timeout through kb_rag and Ask

**Files:**
- Modify: `intelligence/services/kb_rag.py:130-450`
- Modify: `intelligence/services/ask.py:740-1225`
- Modify: `intelligence/services/answer_orchestrator.py:162-225`
- Modify: `intelligence/tests/test_kb_rag.py`
- Modify: `intelligence/tests/test_answer_orchestrator.py`

- [ ] **Step 1: Write failing adapter and Ask integration tests**

Add these methods to `KbRagTelemetryTests` in `test_kb_rag.py`:

```python
    def test_zero_timeout_fails_fast_without_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            with mock.patch(
                "subprocess.run",
                side_effect=AssertionError("must not spawn"),
            ):
                result = kb_rag.retrieve("液冷", root / "wiki", timeout=0.0)
        self.assertEqual(result.telemetry.status, "timeout")
        self.assertEqual(result.telemetry.dense_initializations, 0)

    def test_hybrid_telemetry_counts_one_dense_initialization(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = self._setup_repo(td)
            (root / ".rag_index").mkdir()
            proc = mock.Mock(returncode=0, stdout="[]", stderr="")
            with mock.patch("subprocess.run", return_value=proc):
                result = kb_rag.retrieve(
                    "液冷", root / "wiki", mode="hybrid", timeout=3.5
                )
        self.assertEqual(result.telemetry.dense_initializations, 1)
```

Add an Ask regression using `unittest.mock.patch`:

```python
def test_market_pattern_skips_subject_rag_and_theme_modules(self) -> None:
    query = (
        "如果一个A股题材连续上涨，但板块成交占比下降，"
        "怎么判断健康分歧还是行情高潮？"
    )
    with mock.patch("intelligence.services.ask.kb_rag.retrieve") as retrieve, mock.patch(
        "intelligence.services.ask.run_module"
    ) as run_module:
        result = answer_query(AskOptions(query=query, compose=False))
    retrieve.assert_not_called()
    run_module.assert_not_called()
    self.assertEqual(result.question_plan.query_envelope.subject_kind, "market_pattern")
```

- [ ] **Step 2: Run tests and verify telemetry/integration failures**

Run: `python3 -m pytest intelligence/tests/test_kb_rag.py intelligence/tests/test_answer_orchestrator.py -q`

Expected: FAIL because timeout is not preflighted, telemetry lacks the field, and Ask still sends the generic query into W/modules.

- [ ] **Step 3: Implement adapter telemetry and Ask wiring**

Add to `RetrievalTelemetry`:

```python
    dense_initializations: int = 0
```

At the start of `retrieve`, after mode assignment, only handle an already exhausted timeout:

```python
    if timeout <= 0:
        res.warning = "wiki-rag 请求预算已耗尽，已跳过"
        tel.status = "timeout"
        tel.warning = res.warning
        tel.dense_initializations = 0
        return res
```

Change the `timeout` annotation to `float`; `subprocess.run` already accepts float seconds. Set `tel.dense_initializations = 1 if mode in {"dense", "hybrid", "rerank"} else 0` immediately before `subprocess.run`, after wiki/script/index preflight has succeeded. This records an actual model-start attempt rather than merely a requested mode. Before strict filtering removes non-fresh hits, set `tel.index_freshness` from the raw validated hits so closed-loop fail-fast can see stale/unknown state.

In `answer_query`, resolve the entity anchor before calling `plan_answer_question`, then call:

```python
    question_plan = plan_answer_question(
        options.query,
        result.matched_theme,
        question_type_override=options.question_type_override,
        anchor=anchor,
    )
    envelope = question_plan.query_envelope
```

Replace the W-source condition and callback with:

```python
    should_retrieve_subject = (
        options.use_wiki_rag
        and envelope.subject_kind in {"company", "theme"}
        and envelope.subject is not None
    )
    if should_retrieve_subject:
        loop = closed_loop_retrieval.retrieve_closed_loop(
            options.query,
            anchor=anchor,
            subject=envelope.subject,
            budget=options.execution_budget,
            retrieve=lambda retrieval_query, mode, timeout: kb_rag.retrieve(
                retrieval_query,
                resolved_kb_wiki,
                k=options.wiki_rag_k,
                mode=mode,
                timeout=min(timeout, float(options.wiki_rag_timeout)),
                excerpt_chars=options.wiki_rag_excerpt,
                index_dir=options.wiki_rag_index_dir,
                require_fresh=True,
            ),
        )
```

For `market_pattern`, set `wiki_stats["warning"] = "no explicit subject; subject RAG skipped"` and skip module fan-out. Preserve deterministic market snapshot and Base Finance rendering.

Add `dense_initializations` to `ClosedLoopRetrievalResult.inspector_dict()` and `wiki_stats`.

- [ ] **Step 4: Run retrieval, Ask and AnswerPlan suites**

Run: `python3 -m pytest intelligence/tests/test_kb_rag.py intelligence/tests/test_closed_loop_retrieval.py intelligence/tests/test_answer_orchestrator.py -q`

Expected: PASS; generic patterns make zero W/module calls, named themes make at most one dense call.

- [ ] **Step 5: Commit the adapter integration**

```bash
git add intelligence/services/kb_rag.py intelligence/services/ask.py intelligence/services/answer_orchestrator.py intelligence/tests/test_kb_rag.py intelligence/tests/test_answer_orchestrator.py
git commit -m "perf: propagate retrieval budget through ask"
```

### Task 6: Enforce the 60-second Workbench answer budget with readable fallback

**Files:**
- Modify: `intelligence/services/conversation_orchestrator.py:445-915`
- Modify: `intelligence/workbench_skills/router.py:93-180`
- Modify: `intelligence/workbench_skills/research_owner.py:45-70`
- Modify: `intelligence/api/app.py:65-260,337-430`
- Modify: `intelligence/tests/test_conversation_orchestrator.py`
- Modify: `intelligence/tests/test_workbench_api.py`
- Modify: `intelligence/tests/test_workbench_research_owner_skills.py`

- [ ] **Step 1: Write failing deadline propagation and fallback tests**

Add to `test_conversation_orchestrator.py`:

```python
def test_turn_passes_one_budget_to_router_skill_and_ask(tmp_path) -> None:
    observed: list[ExecutionBudget] = []

    def answer_spy(options: AskOptions) -> AskResult:
        assert options.execution_budget is not None
        observed.append(options.execution_budget)
        assert options.llm_timeout <= 30
        return _ask_result(options.query)

    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation("预算传播")
    run_id, message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "指数上涨但涨停家数下降、成交额放大，怎么理解？",
    )
    TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        answer_query_fn=answer_spy,
        skill_registry=SkillRegistry(),
        answer_deadline_seconds=60.0,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=message_id,
        query="指数上涨但涨停家数下降、成交额放大，怎么理解？",
        skill_mode="auto",
        selected_skill_ids=[],
    )
    assert len(observed) == 1
    assert observed[0].deadline_at - observed[0].started_at == 60.0


def test_exhausted_budget_uses_nonempty_deterministic_answer(tmp_path) -> None:
    expired = ExecutionBudget(started_at=0.0, deadline_at=0.0)
    conversation_store = ConversationStore("alice", root=tmp_path / "conversations")
    run_store = RunStore("alice", root=tmp_path / "runs")
    conversation = conversation_store.create_conversation("预算耗尽")
    run_id, message_id = _prepare_turn(
        conversation_store,
        run_store,
        conversation.conversation_id,
        "指数上涨但涨停家数下降，怎么理解？",
    )
    result = TurnOrchestrator(
        repo_root=tmp_path,
        conversation_store=conversation_store,
        run_store=run_store,
        skill_registry=SkillRegistry(),
        budget_factory=lambda: expired,
    ).run_turn(
        conversation_id=conversation.conversation_id,
        run_id=run_id,
        assistant_message_id=message_id,
        query="指数上涨但涨停家数下降，怎么理解？",
        skill_mode="auto",
        selected_skill_ids=[],
    )
    assert result.status == "completed"
    assert result.content.strip()
    assert "时间预算" in " ".join(run_store.load_run(run_id).degrades)
```

Extend the API supervisor test:

```python
    assert messages[-1]["content"] == (
        "本轮研究超过时间预算，未完成的检索已停止。你可以重试；"
        "系统不会把未完成检索写成已验证结论。"
    )
```

- [ ] **Step 2: Run focused tests and confirm missing constructor/context behavior**

Run: `python3 -m pytest intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_workbench_api.py intelligence/tests/test_workbench_research_owner_skills.py -q`

Expected: FAIL because TurnOrchestrator has no deadline/budget factory and owner does not receive the shared budget.

- [ ] **Step 3: Propagate the budget and reserve time for deterministic rendering**

Add constructor arguments:

```python
        answer_deadline_seconds: float = 60.0,
        budget_factory: Callable[[], ExecutionBudget] | None = None,
```

Store them, then start `run_turn` with:

```python
        budget = (
            self.budget_factory()
            if self.budget_factory is not None
            else ExecutionBudget.start(self.answer_deadline_seconds)
        )
```

Pass a routing timeout capped at five seconds. Add `llm_timeout: float = 5.0` to `route_skills`; only the default `llm_refine.complete` adapter receives it, while injected test doubles keep their existing one-argument signature:

```python
    complete = (
        (lambda messages: llm_refine.complete(
            messages,
            timeout=max(1, int(llm_timeout)),
        ))
        if llm_complete is None
        else llm_complete
    )
```

Call the router with:

```python
            route = self.route_skills(
                contextual_query,
                "ask",
                skill_mode,
                selected_skill_ids,
                registry=self.skill_registry.definitions,
                query_envelope=routing_envelope,
                llm_timeout=budget.child_timeout(5.0, reserve=50.0),
            )
```

For every skill future:

```python
                skill_timeout = budget.child_timeout(
                    self.skill_registry.definitions[skill_id].timeout_seconds,
                    reserve=20.0,
                )
                if skill_timeout <= 0:
                    warnings.append(f"Skill {skill_id} 因时间预算不足已跳过")
                    continue
```

Use `future.result(timeout=skill_timeout)` and put `execution_budget=budget` in `SkillExecutionContext`.

In `ResearchOwnerSkill.execute`, pass both:

```python
                execution_budget=context.execution_budget,
                llm_timeout=max(
                    1,
                    int(context.execution_budget.child_timeout(30.0, reserve=3.0) / 2),
                ) if context.execution_budget is not None else 30,
```

Use the same fields for the Base Finance `AskOptions` in `TurnOrchestrator`. Divide the remaining synthesis allowance by two because `synthesize_messages` may retry once; this prevents two network timeouts from exceeding the shared deadline.

If less than three seconds remain before generic Ask, call it with `use_wiki_rag=False`, `use_modules=False`, `compose=False`, and append `workbench_time_budget_exhausted_template_answer`. The existing deterministic renderer must still produce the direct judgment/evidence gap/next verification structure.

In `_terminalize_pending_message`, replace empty content on `executor_timeout` with:

```python
    timeout_content = (
        "本轮研究超过时间预算，未完成的检索已停止。你可以重试；"
        "系统不会把未完成检索写成已验证结论。"
    )
```

Read the configured internal deadline once in `app.py` with an invalid-value fallback:

```python
def _answer_deadline_seconds() -> float:
    try:
        configured = float(os.environ.get("WORKBENCH_ANSWER_DEADLINE_SECONDS", "60"))
    except ValueError:
        configured = 60.0
    return max(1.0, configured)


_WORKBENCH_ANSWER_DEADLINE_SECONDS = _answer_deadline_seconds()
```

Add `timeout_sec: float | None = None` to `RunSupervisor._submit` and construct its timer with:

```python
        effective_timeout = self.timeout_sec if timeout_sec is None else timeout_sec
        timer = threading.Timer(
            effective_timeout,
            self._expire,
            args=(store, run_id, key),
        )
```

`submit_conversation` passes `timeout_sec=min(self.timeout_sec, _WORKBENCH_ANSWER_DEADLINE_SECONDS + 5.0)`. Therefore the existing tests that inject `run_timeout_sec=0.05` remain fast, while the normal conversation hard stop is 65 seconds. `_run_conversation_turn` passes `answer_deadline_seconds=_WORKBENCH_ANSWER_DEADLINE_SECONDS` into `TurnOrchestrator`. Generic `/api/runs` jobs retain the existing supervisor timeout.

- [ ] **Step 4: Run all deadline, cancellation and owner tests**

Run: `python3 -m pytest intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_workbench_api.py intelligence/tests/test_workbench_research_owner_skills.py -q`

Expected: PASS; cancellation remains cancelled, owner handoff remains intact, internal budget exhaustion completes with a readable template, and hard supervisor timeout has nonempty content.

- [ ] **Step 5: Commit the end-to-end SLA contract**

```bash
git add intelligence/services/conversation_orchestrator.py intelligence/workbench_skills/router.py intelligence/workbench_skills/research_owner.py intelligence/api/app.py intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_workbench_api.py intelligence/tests/test_workbench_research_owner_skills.py
git commit -m "feat: enforce workbench answer deadline"
```

### Task 7: Stream and display the five real execution stages

**Files:**
- Modify: `intelligence/services/conversation_orchestrator.py`
- Modify: `intelligence/services/ask.py`
- Modify: `intelligence/workbench_skills/contracts.py`
- Modify: `intelligence/workbench_skills/research_owner.py`
- Modify: `intelligence/webapp/src/types.ts:535-560`
- Modify: `intelligence/webapp/src/streamEvents.ts:55-215`
- Modify: `intelligence/webapp/src/App.tsx:80-95`
- Modify: `intelligence/webapp/src/components/MessageBubble.tsx:35-125`
- Modify: `intelligence/webapp/src/displayText.ts:81-95`
- Modify: `intelligence/webapp/src/components/components.test.tsx:1020-1160`
- Rebuild: `intelligence/api/static/index.html`
- Rebuild: `intelligence/api/static/assets/*`

- [ ] **Step 1: Write failing reducer and visible-stage tests**

Add to the stream-event test section:

```tsx
it("tracks the current human-facing research stage", () => {
  const initial = createLiveMessageState({
    conversationId: "conv_recent",
    messageId: "msg_assistant",
    runId: "run_demo",
  });
  const next = applyChatStreamEvent(
    initial,
    makeEnvelope("stage-1", "stage.progress", {
      stage: "evidence_gate",
      status: "running",
      elapsed_ms: 123,
    }),
  );
  expect(next.currentStage).toBe("evidence_gate");
  expect(userFacingStage(next.currentStage!)).toBe("核验证据相关性与时效");
});
```

Render a pending `MessageBubble` whose `live.currentStage` is `semantic_recall` and assert that “补充语义检索” is visible instead of the static “正在检索本轮证据”.

- [ ] **Step 2: Run the frontend test and confirm missing stage state**

Run: `pnpm --dir intelligence/webapp exec vitest run src/components/components.test.tsx`

Expected: FAIL because `LiveMessageState` has no `currentStage` and `stage.progress` is ignored.

- [ ] **Step 3: Emit and consume the stage contract**

Add to `LiveMessageState`:

```typescript
  currentStage: string | null;
```

Initialize it to `null`. Add to `applyChatStreamEvent`:

```typescript
  if (
    event.event_type === "stage.progress" &&
    typeof payload.stage === "string"
  ) {
    return { ...state, currentStage: payload.stage, status: "streaming" };
  }
```

Subscribe in `App.tsx` by adding `"stage.progress"` to `chatEventTypes`.

Use these labels in `displayText.ts`:

```typescript
  understanding: "理解问题与研究对象",
  deterministic_recall: "读取盘面与关键词证据",
  semantic_recall: "补充语义检索",
  evidence_gate: "核验证据相关性与时效",
  synthesis: "组织回答与保守质检",
```

In the pending block of `MessageBubble`, render:

```tsx
{live?.currentStage
  ? userFacingStage(live.currentStage)
  : "正在检索本轮证据"}
```

Add a progress callback to `AskOptions` and `SkillExecutionContext`:

```python
    progress_callback: Callable[[str, str], None] | None = field(
        default=None, repr=False, compare=False
    )
```

Update the exact `SkillExecutionContext` field-list test. Pass the callback through `ResearchOwnerSkill` to `AskOptions`.

In `TurnOrchestrator.run_turn`, define one callback with collision-free event IDs:

```python
        stage_sequence = 0

        def emit_progress(stage: str, status: str) -> None:
            nonlocal stage_sequence
            stage_sequence += 1
            self._emit(
                run_id,
                assistant_message_id,
                f"stage:{stage}:{stage_sequence:02d}",
                "stage.progress",
                {"stage": stage, "status": status, "elapsed_ms": 0},
                conversation_id,
            )
```

Pass `progress_callback=emit_progress` into both `SkillExecutionContext` and Base Finance `AskOptions`. Emit `understanding/running` before building the envelope and `understanding/completed` after routing.

In `answer_query`, insert these exact calls at the deterministic boundary:

```python
    progress = options.progress_callback or (lambda stage, status: None)
    progress("deterministic_recall", "running")
```

The `running` call goes immediately after `question_plan` is assigned. Insert `progress("deterministic_recall", "completed")` immediately before the `# --- W: 知识库 hybrid` block.

In `closed_loop_retrieval._run_one`, call `progress("semantic_recall", "running")` and `progress("semantic_recall", status)` only when `mode == "hybrid"`; add the optional callback to `retrieve_closed_loop` and pass it from Ask. Around `_bucket_hits`, emit `evidence_gate/running` then `evidence_gate/completed`. Immediately before the existing compose block, emit `synthesis/running`; after model or deterministic rendering, emit `synthesis/completed` or `synthesis/degraded` according to `result.synthesis`.

Do not send raw commands, model paths or download logs in stage payloads.

- [ ] **Step 4: Run tests, typecheck and rebuild production assets**

Run: `pnpm --dir intelligence/webapp exec vitest run src/components/components.test.tsx`

Expected: PASS.

Run: `pnpm --dir intelligence/webapp typecheck`

Expected: PASS with zero TypeScript errors.

Run: `pnpm --dir intelligence/webapp build`

Expected: PASS and `intelligence/api/static/index.html` points to newly hashed JS/CSS assets.

- [ ] **Step 5: Commit backend stages, source UI and generated bundle together**

```bash
git add intelligence/services/conversation_orchestrator.py intelligence/services/ask.py intelligence/workbench_skills/contracts.py intelligence/workbench_skills/research_owner.py intelligence/webapp/src/types.ts intelligence/webapp/src/streamEvents.ts intelligence/webapp/src/App.tsx intelligence/webapp/src/components/MessageBubble.tsx intelligence/webapp/src/displayText.ts intelligence/webapp/src/components/components.test.tsx intelligence/api/static
git commit -m "feat: show real workbench answer stages"
```

### Task 8: Add measurable smoke evidence and run the full acceptance gate

**Files:**
- Modify: `scripts/smoke_workbench_self_use.py:330-490`
- Test: `intelligence/tests/test_workbench_conversation_integration.py`
- Test: `intelligence/tests/test_workbench_api.py`
- Test: `intelligence/tests/test_workbench_research_owner_skills.py`
- Test: `intelligence/webapp/src/components/components.test.tsx`

- [ ] **Step 1: Add a failing smoke-summary unit assertion**

Extract a small pure helper in the smoke script and test it in `intelligence/tests/test_workbench_conversation_integration.py`:

```python
from scripts.smoke_workbench_self_use import smoke_metrics


def test_smoke_metrics_report_elapsed_and_unique_stage_order() -> None:
    metrics = smoke_metrics(
        started_at=10.0,
        finished_at=42.5,
        stage_events=["understanding", "deterministic_recall", "understanding", "synthesis"],
    )
    assert metrics == {
        "elapsed_seconds": 32.5,
        "stages": ["understanding", "deterministic_recall", "synthesis"],
    }
```

- [ ] **Step 2: Run the focused test and verify the helper is absent**

Run: `python3 -m pytest intelligence/tests/test_workbench_conversation_integration.py::test_smoke_metrics_report_elapsed_and_unique_stage_order -q`

Expected: FAIL because `smoke_metrics` is not defined.

- [ ] **Step 3: Record elapsed time and stage order without exposing internals**

Add:

```python
def smoke_metrics(
    *,
    started_at: float,
    finished_at: float,
    stage_events: list[str],
) -> dict[str, object]:
    return {
        "elapsed_seconds": round(max(0.0, finished_at - started_at), 3),
        "stages": list(dict.fromkeys(stage_events)),
    }
```

Initialize `stage_events: list[str] = []` beside the existing SSE counters. In `_stream_until_terminal`, add:

```python
                if canonical_type == "stage.progress":
                    event_payload = payload.get("payload")
                    stage = (
                        event_payload.get("stage")
                        if isinstance(event_payload, dict)
                        else None
                    )
                    if not isinstance(stage, str) or not SAFE_SOURCE_COMPONENT.fullmatch(stage):
                        raise SmokeProtocolError("stage_progress")
                    stage_events.append(stage)
```

Include `"stages": list(dict.fromkeys(stage_events))` in the SSE summary returned at both terminal return sites. Change its return annotation to `dict[str, object]`. In `run_smoke`, record `started_at = time.monotonic()` before readiness and merge `smoke_metrics(started_at=started_at, finished_at=time.monotonic(), stage_events=sse_summary["stages"])` into `summary`. Do not include event payloads, prompts, local paths or model configuration.

- [ ] **Step 4: Run automated gates**

Run:

```bash
python3 -m pytest intelligence/tests/test_query_understanding.py intelligence/tests/test_execution_budget.py intelligence/tests/test_answer_model.py intelligence/tests/test_answer_orchestrator.py intelligence/tests/test_closed_loop_retrieval.py intelligence/tests/test_kb_rag.py intelligence/tests/test_workbench_skill_router.py intelligence/tests/test_workbench_research_owner_skills.py intelligence/tests/test_conversation_orchestrator.py intelligence/tests/test_workbench_conversation_integration.py intelligence/tests/test_workbench_api.py -q
```

Expected: PASS with no failed tests.

Run:

```bash
pnpm --dir intelligence/webapp test
pnpm --dir intelligence/webapp typecheck
pnpm --dir intelligence/webapp build
git diff --check
```

Expected: all commands PASS; the final build leaves no uncommitted source/bundle mismatch after staging the generated assets.

- [ ] **Step 5: Run the two real Workbench questions on a temporary port**

Start the branch runtime without touching canonical port 8792:

```bash
WORKBENCH_ANSWER_DEADLINE_SECONDS=60 python3 -m uvicorn intelligence.api.app:app --host 127.0.0.1 --port 8795
```

In a second terminal, run:

```bash
mkdir -p /tmp/workbench-query-retrieval-latency-evidence
python3 scripts/smoke_workbench_self_use.py --base-url http://127.0.0.1:8795 --user local-qa --timeout 75 --output /tmp/workbench-query-retrieval-latency-evidence/generic-theme.json --question "如果一个A股题材连续上涨，但板块成交占比开始下降，我应该怎么判断它是健康分歧还是行情高潮？请给出直接判断、证据、反证和下一步验证。"
```

Then run:

```bash
python3 scripts/smoke_workbench_self_use.py --base-url http://127.0.0.1:8795 --user local-qa --timeout 75 --output /tmp/workbench-query-retrieval-latency-evidence/market-divergence.json --question "A股里，指数上涨但涨停家数下降、成交额放大，这种背离应该怎么理解？请直接给出判断、最关键的证据、可能的反证和下一步验证，不要写成检查清单。"
```

Expected for both summaries:

- `run_status=completed`;
- `elapsed_seconds <= 60`;
- nonempty answer artifact/report;
- stages end with `synthesis`;
- first query has no invented full-query theme and no unrelated AI 算力/半导体 citation;
- retrieval inspector reports `dense_initializations <= 1`;
- no fresh evidence produces a named conservative degrade, not a failed assertion.

Also open the temporary UI and verify the visible stage text changes while the answer is running. Save screenshots/recordings outside Git or in the existing approved test-evidence location; do not commit videos or secrets.

- [ ] **Step 6: Commit smoke instrumentation and prepare the review handoff**

```bash
git add scripts/smoke_workbench_self_use.py intelligence/tests/test_workbench_conversation_integration.py
git commit -m "test: measure workbench answer SLA"
git status --short
git log --oneline origin/main..HEAD
```

Expected: clean worktree; commit list contains the design/plan commits plus focused implementation commits. Stop the temporary 8795 server. Do not merge to `main`, switch canonical runtime or claim hosted-beta readiness without explicit user confirmation.
