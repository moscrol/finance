from __future__ import annotations

from datetime import date

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.closed_loop_retrieval import retrieve_closed_loop
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.kb_rag import RetrievalTelemetry, WikiHit, WikiRagResult
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    InformationCutoff,
    ResearchRunContext,
)
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolSpec,
)
from intelligence.services.task_frame import TaskFrame


def _frame() -> TaskFrame:
    return TaskFrame(
        raw_question="这一周行情下跌的主要原因是什么",
        user_goal="解释本周市场下跌原因",
        question_type="market_cause",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="本周",
        required_outputs=("causal_chain",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="time_aligned_market_causal",
        confidence=0.95,
    )


def test_old_positional_research_context_construction_still_works() -> None:
    built = build_episode_context(
        _frame(),
        task_id="old-positional",
        capabilities=("news_search",),
    )

    context = ResearchRunContext(
        built.contract,
        built.deadline,
        built.policy,
        "trace-parent",
        "2026-07-26",
        "2026-07-25",
        "previous turn",
    )

    assert context.trace_parent_id == "trace-parent"
    assert context.information_cutoff.source == "runtime_default"


def test_episode_context_freezes_latest_available_information_cutoff() -> None:
    context = build_episode_context(
        _frame(),
        task_id="cutoff-context",
        capabilities=("news_search",),
        today="2026-07-26",
        latest_data_date="2026-07-24",
    )

    assert context.information_cutoff == InformationCutoff(
        date(2026, 7, 24),
        "latest_available",
    )


def test_future_dated_evidence_never_enters_model_observation() -> None:
    cutoff = InformationCutoff(date(2026, 7, 24), "requested")
    context = build_episode_context(
        _frame(),
        task_id="cutoff-observation",
        capabilities=("news_search",),
        information_cutoff=cutoff,
    )

    def runner(_query, _context):
        evidence = [
            AgentEvidence(
                tool="news_search",
                title="截止日前消息",
                detail="2026-07-24 已发布",
                source="https://example.com/valid",
                source_date="2026-07-24",
            ),
            AgentEvidence(
                tool="news_search",
                title="未来消息",
                detail="2026-07-25 才发布",
                source="https://example.com/future",
                source_date="2026-07-25",
            ),
        ]
        return (
            evidence,
            "截止日前消息：2026-07-24 已发布；未来消息：2026-07-25 才发布",
            ProviderTrace(
                provider="scripted_news",
                capability="news_search",
                status="success",
                result_count=2,
            ),
        )

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="news_search",
                capability="news_search",
                description="scripted news",
                cost="external",
                freshness="current",
                runner=runner,
            ),
        )
    )

    result = registry.execute(
        "news_search",
        "市场下跌原因",
        context=context,
        step_id="step-1",
    )

    assert [item.title for item in result.evidence] == ["截止日前消息"]
    assert "未来消息" not in result.observation
    assert result.trace.requested_date == "2026-07-24"
    assert result.trace.served_date == "2026-07-25"
    assert ProviderTrace.from_dict(result.trace.to_dict()) == result.trace


def test_closed_loop_discards_future_knowledge_hit_before_bucketing() -> None:
    calls = 0

    def retrieve(query: str) -> WikiRagResult:
        nonlocal calls
        calls += 1
        hits = (
            [
                WikiHit(
                    page_id="future",
                    file_path="wiki/sources/future.md",
                    title="液冷未来订单",
                    score=0.99,
                    excerpt="液冷未来订单",
                    best_chunk_id="future::0",
                    source_date="2026-07-25",
                )
            ]
            if calls == 1
            else []
        )
        return WikiRagResult(
            ok=bool(hits),
            hits=hits,
            telemetry=RetrievalTelemetry(
                status="ok" if hits else "empty",
                hit_count=len(hits),
            ),
            command=query,
        )

    result = retrieve_closed_loop(
        "液冷订单",
        anchor=None,
        retrieve=retrieve,
        information_cutoff=InformationCutoff(
            date(2026, 7, 24),
            "requested",
        ),
    )

    assert result.conclusion == []
    assert [item.hit.title for item in result.discarded] == ["液冷未来订单"]
    assert any("future_of_cutoff" in warning for warning in result.warnings)
