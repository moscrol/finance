"""升档记账搬到底座之后：领域裁决、底座记账，services/ 不再有账本写入。

金标（数字 24 / 240 / 192、幂等、quick 原样返回）由既有测试钉着，只是改指新家：
`test_mode_governor.py` 三例 + `test_root_budget_invariants.py` + `test_runtime_fault_matrix.py`
（`apply_mode_promotion`）、`test_forecast_residual_budget.py`（`maybe_promote_forecast_residual`）、
`test_agent_episode.py` 的 Episode 级 deep 升档（loop 真把裁决落了账）。本文件补三样：

1. **棘轮**：`intelligence/services/**` 里任何一处 `.grant(` / `.promote_caps(` /
   `.consume_call(` / `.consume_seconds(` 调用都算回焊（账本自身的定义文件除外）。
2. **harness 不碰账本**：`govern_mode` 批了 deep，账本一格不动；只有 loop 调
   `apply_mode_promotion` 之后 caps 才变。
3. **两条 loop 同一个函数**：Episode 与 HarnessReferenceLoop 的源码都经
   `apply_mode_promotion`，且都不再读 `governance.context`。
"""

from __future__ import annotations

import ast
from datetime import date
import json
from pathlib import Path
from uuid import uuid4

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.runtime.harness_reference_loop import HarnessReferenceLoop
from intelligence.runtime.tier_promotion import apply_mode_promotion
from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.mode_governor import ModeSignals
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    InformationCutoff,
    InMemoryRootBudgetLedger,
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
    release_root_budget,
    root_budget_for_policy,
)
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.services.research_plan import ResearchPlan
from intelligence.services.research_tool_registry import ResearchToolRegistry, ToolSpec
from intelligence.services.task_frame import TaskFrame

_INTELLIGENCE = Path(__file__).resolve().parents[1]
_SERVICES = _INTELLIGENCE / "services"
_RUNTIME = _INTELLIGENCE / "runtime"
_LEDGER_MUTATORS = frozenset({"grant", "promote_caps", "consume_call", "consume_seconds"})
# 账本自己的定义（Protocol + InMemory 实现）住在这里，方法体互调不算「领域碰账本」。
_LEDGER_HOME = "research_contract.py"


def _ledger_mutator_calls(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in _LEDGER_MUTATORS:
            hits.append(f"{path.relative_to(_INTELLIGENCE)}:{node.lineno}:.{func.attr}(")
    return hits


def test_services_layer_never_writes_the_root_ledger() -> None:
    """M5 那条纪律的全仓棘轮：领域层只申请，底座授予。"""

    offenders: list[str] = []
    for path in sorted(_SERVICES.rglob("*.py")):
        if path.name == _LEDGER_HOME:
            continue
        offenders.extend(_ledger_mutator_calls(path))
    assert not offenders, "services/ 直接写账本（应搬到 runtime/）：\n" + "\n".join(offenders)


def test_ledger_mutators_live_in_runtime_promotion_and_repair_budget() -> None:
    """反向：升档与修复的记账点真在底座——否则上面那条可能是「谁都不记账」的假绿。"""

    promotion_hits = _ledger_mutator_calls(_RUNTIME / "tier_promotion.py")
    assert any(".promote_caps(" in hit for hit in promotion_hits)
    assert any(".grant(" in hit for hit in promotion_hits)
    repair_hits = _ledger_mutator_calls(_RUNTIME / "repair_budget.py")
    assert any(".grant(" in hit for hit in repair_hits)


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="比较本周市场驱动并检查反方证据",
        user_goal="判断本周驱动与反方",
        question_type="general_finance_qa",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="本周",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.9,
    )


def _deep_plan() -> ResearchPlan:
    return ResearchPlan(
        task_summary="比较两类证据后回答用户问题",
        answer_elements=("直接判断", "依据"),
        hypotheses=("主假设",),
        evidence_needs=("盘面", "新闻"),
        candidate_actions=("查询结构化数据",),
        open_gaps=(),
        requested_mode="deep",
    )


def _standard_context(episode_id: str) -> ResearchRunContext:
    policy = ResearchPolicy.for_tier("standard")
    return ResearchRunContext(
        contract=ResearchTaskContract(
            task_id=episode_id,
            question="比较本周市场驱动并检查反方证据",
            subject="A股市场",
            subject_kind="market",
            question_type="general_finance_qa",
            required_outputs=(),
            allowed_capabilities=("finance_query", "news_search"),
            research_tier="standard",
        ),
        deadline=ResearchDeadline.from_timeout(
            policy.total_seconds, synthesis_reserve=policy.synthesis_reserve
        ),
        policy=policy,
        trace_parent_id=episode_id,
        information_cutoff=InformationCutoff(date(2026, 7, 24), "requested"),
        root_budget=root_budget_for_policy(policy, episode_id=episode_id),
    )


def test_govern_mode_decides_deep_without_touching_the_ledger() -> None:
    """裁决与记账分两步：harness 批了 deep，账本仍是 standard 的 8/90；loop 落账后才是 24/240。"""

    episode_id = f"tier-promotion-{uuid4().hex[:12]}"
    context = _standard_context(episode_id)
    root = context.root_budget
    assert root is not None
    try:
        harness = FinanceResearchHarness(
            mode_signals=lambda _frame, _plan: ModeSignals(evidence_domains=("盘面", "新闻"))
        )
        governance = harness.govern_mode(
            task_frame=_frame(), plan=_deep_plan(), context=context, can_branch=False
        )
        assert governance.decision.approved and governance.decision.effective_mode == "deep"
        assert root.hard_calls_cap == 8 and root.hard_seconds_cap == 90.0
        assert context.policy.tier == "standard"

        promoted = apply_mode_promotion(context, governance.decision)

        assert promoted.policy.tier == "deep"
        assert promoted.root_budget is root
        assert root.hard_calls_cap == 24 and root.hard_seconds_cap == 240.0
        assert root.remaining_calls == 24 and root.remaining_seconds == 192.0
    finally:
        release_root_budget(episode_id)


def _deep_plan_turn() -> ModelTurn:
    return ModelTurn(
        json.dumps(
            {
                "kind": "PLAN",
                "task_summary": "判断市场主线并给出反方",
                "answer_elements": ["direct_assessment"],
                "hypotheses": ["半导体可能是持续主线"],
                "evidence_needs": ["盘面结构", "新闻驱动"],
                "candidate_actions": ["market_data"],
                "open_gaps": ["缺少反方证据"],
                "requested_mode": "deep",
                "revision": 1,
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )


def _tool_turn() -> ModelTurn:
    return ModelTurn(
        "", (ModelToolCall("call-1", "market_data", {"query": "当前市场结构"}),), "scripted", ""
    )


def _finish_turn() -> ModelTurn:
    return ModelTurn(
        json.dumps(
            {
                "status": "completed",
                "draft": "当前更接近条件化修复，持续性取决于量能。",
                "gaps": [],
                "bindings": [
                    {"output_id": "direct_assessment", "evidence_hashes": ["evidence-1"], "gap": ""}
                ],
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )


class _ScriptedModel:
    def __init__(self, turns: list[ModelTurn]) -> None:
        self._turns = iter(turns)

    def complete(self, *, messages, tools, timeout):
        del messages, tools, timeout
        return next(self._turns)


def _registry() -> ResearchToolRegistry:
    def runner(query: str, _context: AgentToolContext):
        del query
        return (
            [
                AgentEvidence(
                    tool="market_data",
                    title="A股市场总览",
                    detail="上涨家数增加，成交保持活跃",
                    source="本地行情",
                    source_date="2026-07-21",
                    evidence_tier="L4",
                    content_hash="evidence-1",
                )
            ],
            "raw market observation",
            ProviderTrace(
                provider="test:market",
                capability="market_data",
                status="success",
                source_trade_date="2026-07-21",
                result_count=1,
            ),
        )

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="结构化行情与市场时序",
                cost="local",
                freshness="current",
                runner=runner,
            ),
        )
    )


def _loop_context(task_id: str) -> ResearchRunContext:
    """standard 档 + 自带一本 InMemory 账本（不进全局注册表，无需 release）。"""

    policy = ResearchPolicy.for_tier("standard")
    return ResearchRunContext(
        contract=ResearchTaskContract(
            task_id=task_id,
            question="目前市场怎么看",
            subject="A股市场",
            subject_kind="market_pattern",
            question_type="market_forecast",
            required_outputs=(
                RequiredOutput("direct_assessment", "direct_assessment", ("market_data",), True),
            ),
            allowed_capabilities=("market_data",),
            research_tier="standard",
            freshness="current",
            timeframe="最近交易日",
            evidence_plan=EvidencePlan(),
        ),
        deadline=ResearchDeadline.from_timeout(90.0, synthesis_reserve=20.0),
        policy=policy,
        trace_parent_id=task_id,
        today="2026-07-22",
        latest_data_date="2026-07-21",
        root_budget=InMemoryRootBudgetLedger(
            episode_id=task_id,
            initial_calls=6,
            hard_calls_cap=8,
            initial_seconds=70.0,
            hard_seconds_cap=90.0,
        ),
    )


def test_both_loops_promote_to_deep_on_the_same_decision() -> None:
    """行为面：同一份 deep PLAN，两条 loop 都经底座落账——context 升 deep、各自账本 caps
    24/240、`mode_decision` 事件同值。其中任一条 loop 漏调 `apply_mode_promotion`，这里就红。"""

    frame = TaskFrame(
        raw_question="目前市场怎么看",
        user_goal="判断当前市场结构",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("direct_assessment",),
        assumptions=("按A股市场理解",),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )
    script = [_deep_plan_turn(), _tool_turn(), _finish_turn()]

    episode_context = _loop_context("tier-promotion-episode")
    episode_sink: list = []
    episode = ContinuousAgentEpisode(_ScriptedModel(list(script))).run(
        task_frame=frame,
        context=episode_context,
        registry=_registry(),
        _continuation_sink=episode_sink,
    )
    reference_context = _loop_context("tier-promotion-reference")
    reference_sink: list = []
    reference = HarnessReferenceLoop(_ScriptedModel(list(script))).run(
        task_frame=frame,
        context=reference_context,
        registry=_registry(),
        _continuation_sink=reference_sink,
    )

    for outcome, sink, context in (
        (episode, episode_sink, episode_context),
        (reference, reference_sink, reference_context),
    ):
        assert outcome.stop_reason == "model_finish"
        decision = next(e for e in outcome.events if e.kind == "mode_decision").payload
        assert decision["effective_mode"] == "deep" and decision["tool_call_cap"] == 24
        assert sink[0].context.policy.tier == "deep"
        root = context.root_budget
        assert root is not None
        assert root.hard_calls_cap == 24 and root.hard_seconds_cap == 240.0

    # Episode 每条事件都盖 at / task_frame_hash（底座的账），摘掉再比裁决正文。
    stamps = {"at", "task_frame_hash"}
    episode_decision = next(e for e in episode.events if e.kind == "mode_decision").payload
    reference_decision = next(e for e in reference.events if e.kind == "mode_decision").payload
    assert {k: v for k, v in dict(episode_decision).items() if k not in stamps} == {
        k: v for k, v in dict(reference_decision).items() if k not in stamps
    }


def test_both_loops_apply_the_decision_through_the_same_runtime_function() -> None:
    for name in ("agent_episode.py", "harness_reference_loop.py"):
        source = (_RUNTIME / name).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module == "intelligence.runtime.tier_promotion"
            for alias in node.names
        }
        assert "apply_mode_promotion" in imported, name
        assert "apply_mode_promotion(context, governance.decision)" in source, name
        assert "governance.context" not in source, f"{name} 仍在读 harness 落好的 context"
