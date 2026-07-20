"""GenericResearchOwner 的契约、白名单和 completion gate 回归。"""

from __future__ import annotations

import pytest

from intelligence.services import agent_research, answer_model, ask, generic_research_owner
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolSpec,
    UnknownResearchTool,
)


def _contract(*, required_direct: bool = True) -> ResearchTaskContract:
    return ResearchTaskContract(
        task_id="run-test",
        question="某公司最近怎么看",
        subject="某公司",
        subject_kind="company",
        question_type="general_finance_qa",
        required_outputs=(
            RequiredOutput(
                "direct_assessment",
                "直接判断",
                ("web_search",),
                required_direct,
            ),
            RequiredOutput(
                "supporting_evidence",
                "可回查来源",
                ("web_search",),
                True,
            ),
        ),
        allowed_capabilities=("web_search",),
        research_tier="quick",
    )


def _context(contract: ResearchTaskContract) -> ResearchRunContext:
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(30.0, synthesis_reserve=20.0),
        policy=ResearchPolicy.for_tier("quick"),
        trace_parent_id=contract.task_id,
    )


def _registry() -> ResearchToolRegistry:
    def web_runner(query: str, _context: agent_research.AgentToolContext):
        evidence = [
            agent_research.AgentEvidence(
                tool="web_search",
                title="官方近期披露",
                detail=f"与 {query} 相关的可回查摘要",
                source="https://example.test/source",
            )
        ]
        return evidence, "命中 1 条", ProviderTrace(
            provider="test:web",
            capability="web_search",
            status="success",
            result_count=1,
        )

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="web_search",
                capability="web_search",
                description="测试网页工具",
                cost="external",
                freshness="current",
                runner=web_runner,
            ),
        )
    )


def test_research_task_contract_round_trips_required_outputs() -> None:
    contract = _contract()
    assert ResearchTaskContract.from_dict(contract.to_dict()) == contract


def test_registry_rejects_unregistered_tool() -> None:
    with pytest.raises(UnknownResearchTool):
        _registry().resolve("shell_exec")


def test_owner_completes_required_outputs_after_grounded_tool_observation() -> None:
    actions = iter(
        [
            '{"tool":"web_search","args":{"query":"某公司最新公告"},"reason":"先查当前事实"}',
            '{"tool":"finish","args":{"sufficient":true,"gaps":[]},"reason":"必要输出已覆盖"}',
        ]
    )

    def complete(_messages, **_kwargs):
        return next(actions), "test", ""

    contract = _contract()
    result = generic_research_owner.run_generic_research(
        contract,
        context=_context(contract),
        registry=_registry(),
        run_id=contract.task_id,
        complete_fn=complete,
    )
    assert result.completion.status == "completed"
    assert all(item.status == "fulfilled" for item in result.completion.outputs)
    assert result.traces[0].parent_id == contract.task_id


def test_finish_true_cannot_hide_missing_required_output() -> None:
    actions = iter(
        ['{"tool":"finish","args":{"sufficient":true,"gaps":[]},"reason":"过早结束"}']
    )

    def complete(_messages, **_kwargs):
        return next(actions), "test", ""

    contract = _contract()
    result = generic_research_owner.run_generic_research(
        contract,
        context=_context(contract),
        registry=_registry(),
        run_id=contract.task_id,
        complete_fn=complete,
    )
    assert result.completion.status == "partial"
    assert any(item.status == "missing" for item in result.completion.outputs)


def test_contract_rejects_unknown_tier() -> None:
    payload = _contract().to_dict()
    payload["research_tier"] = "unbounded"
    with pytest.raises(ValueError):
        ResearchTaskContract.from_dict(payload)


def test_two_empty_observations_stop_on_no_information_gain() -> None:
    def empty_runner(query: str, _context: agent_research.AgentToolContext):
        return [], "无命中", ProviderTrace(
            provider="test:web",
            capability="web_search",
            status="empty",
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="web_search",
                capability="web_search",
                description="测试空结果工具",
                cost="external",
                freshness="current",
                runner=empty_runner,
            ),
        )
    )
    actions = iter(
        [
            '{"tool":"web_search","args":{"query":"一次"},"reason":"查证"}',
            '{"tool":"web_search","args":{"query":"二次"},"reason":"改写"}',
        ]
    )

    def complete(_messages, **_kwargs):
        return next(actions), "test", ""

    result = generic_research_owner.run_generic_research(
        _contract(),
        context=_context(_contract()),
        registry=registry,
        run_id="empty-run",
        complete_fn=complete,
    )
    assert result.loop.stop_reason == "no_information_gain"
    assert len(result.loop.steps) == 2


def test_ask_owner_path_skips_fixed_answer_template(monkeypatch) -> None:
    def fake_web(query: str, _context: agent_research.AgentToolContext):
        return [
            agent_research.AgentEvidence(
                tool="web_search",
                title="候选来源",
                detail=f"关于 {query} 的摘要",
                source="https://example.test/owner",
            )
        ], "命中候选来源", ProviderTrace(
            provider="test:web",
            capability="agent_loop",
            status="success",
            result_count=1,
        )

    actions = iter(
        [
            '{"tool":"web_search","args":{"query":"某公司最新公告"},"reason":"查当前事实"}',
            '{"tool":"finish","args":{"sufficient":true,"gaps":[]},"reason":"完成"}',
        ]
    )

    monkeypatch.setattr(
        agent_research,
        "build_default_tools",
        lambda _retrieve: {"web_search": fake_web},
    )
    monkeypatch.setattr(agent_research, "build_graph_tools", lambda _knowledge: {})
    monkeypatch.setattr(
        agent_research.llm_refine,
        "complete",
        lambda _messages, **_kwargs: (next(actions), "test", ""),
    )
    result = ask.answer_query(
        ask.AskOptions(
            query="某公司最近怎么看",
            clarify=False,
            synthesize=False,
            research_task_contract=_contract(),
        )
    )
    assert result.answer_spec is not None
    assert result.answer_spec.presentation_kind == "generic_research"
    rendered = answer_model.render_answer_spec(result.answer_spec)
    assert "题材怎么理解" not in rendered
    assert "公司证据" not in rendered
    assert "候选来源" in rendered
