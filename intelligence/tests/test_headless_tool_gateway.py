from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import urllib.error
import urllib.request

import pytest

from intelligence.services.agent_research import AgentEvidence, AgentToolContext
from intelligence.services.evidence_capabilities import EvidencePlan
from intelligence.services.headless_tool_gateway import HeadlessToolGateway
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
)


def _context(*, max_steps: int = 3) -> ResearchRunContext:
    contract = ResearchTaskContract(
        task_id="headless-gateway-test",
        question="目前市场怎么看",
        subject="A股市场",
        subject_kind="market_pattern",
        question_type="market_forecast",
        required_outputs=(
            RequiredOutput(
                "direct_assessment",
                "直接判断",
                ("market_data",),
                True,
            ),
        ),
        allowed_capabilities=("market_data", "news_search"),
        research_tier="quick",
        freshness="current",
        evidence_plan=EvidencePlan(),
        task_frame_hash="frame-hash",
    )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(30.0),
        policy=ResearchPolicy("quick", max_steps, 30.0, 0.0),
        trace_parent_id="headless-gateway-test",
        today="2026-07-25",
        latest_data_date="2026-07-24",
    )


def _registry(calls: list[tuple[str, str]]) -> ResearchToolRegistry:
    def market_runner(query: str, _context: AgentToolContext):
        calls.append(("market_data", query))
        evidence = AgentEvidence(
            tool="market_data",
            title="A股市场总览",
            detail=f"{query}：上涨家数增加",
            source="本地行情",
            source_date="2026-07-24",
            evidence_tier="L4",
            content_hash="market-hash",
        )
        return (
            [evidence],
            "上涨家数增加",
            ProviderTrace(
                provider="test:market",
                capability="market_data",
                status="success",
                source_trade_date="2026-07-24",
                result_count=1,
            ),
        )

    def news_runner(query: str, _context: AgentToolContext):
        calls.append(("news_search", query))
        return (
            [],
            "没有同窗新闻",
            ProviderTrace(
                provider="test:news",
                capability="news_search",
                status="empty",
                result_count=0,
            ),
        )

    return ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="结构化行情",
                cost="local",
                freshness="current",
                runner=market_runner,
                query_scope="episode",
            ),
            ToolSpec(
                name="news_search",
                capability="news_search",
                description="财经新闻",
                cost="external",
                freshness="current",
                runner=news_runner,
            ),
        )
    )


def _unauthorized_call(gateway: HeadlessToolGateway) -> urllib.error.HTTPError:
    request = urllib.request.Request(
        f"{gateway.endpoint}/tool/market_data",
        data=json.dumps({"query": "A股"}).encode("utf-8"),
        headers={
            "Authorization": "Bearer wrong-token",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as raised:
        urllib.request.urlopen(request, timeout=2.0)
    return raised.value


def test_gateway_executes_authorized_registry_tool() -> None:
    calls: list[tuple[str, str]] = []

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=_context(),
    ) as gateway:
        result = gateway.call("market_data", "A股最近五日")
        snapshot = gateway.snapshot()

    assert result["status"] == "success"
    assert result["evidence_hashes"] == ["market-hash"]
    assert calls == [("market_data", "A股最近五日")]
    assert snapshot.evidence[0].content_hash == "market-hash"
    assert snapshot.executed_count == 1
    assert [event.kind for event in snapshot.events] == [
        "tool_request",
        "tool_result",
    ]


def test_gateway_rejects_duplicate_query_without_second_execution() -> None:
    calls: list[tuple[str, str]] = []

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=_context(max_steps=3),
    ) as gateway:
        gateway.call("news_search", "A股 本周 新闻")
        duplicate = gateway.call("news_search", "  a股   本周 新闻  ")
        snapshot = gateway.snapshot()

    assert duplicate["status"] == "rejected"
    assert duplicate["error"] == "duplicate_query"
    assert calls == [("news_search", "A股 本周 新闻")]
    assert snapshot.executed_count == 1
    assert snapshot.duplicate_queries == 1


def test_gateway_rejects_after_finance_tool_budget() -> None:
    calls: list[tuple[str, str]] = []

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=_context(max_steps=1),
    ) as gateway:
        gateway.call("market_data", "市场")
        rejected = gateway.call("news_search", "市场新闻")

    assert rejected["status"] == "rejected"
    assert rejected["error"] == "tool_budget_exhausted"
    assert calls == [("market_data", "市场")]


def test_gateway_rejects_second_successful_episode_snapshot() -> None:
    calls: list[tuple[str, str]] = []

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=_context(max_steps=3),
    ) as gateway:
        gateway.call("market_data", "市场近五日")
        rejected = gateway.call("market_data", "市场近十日")

    assert rejected["error"] == "episode_snapshot_already_collected"
    assert calls == [("market_data", "市场近五日")]


def test_gateway_rejects_before_tool_when_deadline_is_closed() -> None:
    calls: list[tuple[str, str]] = []
    context = replace(_context(), deadline=ResearchDeadline.from_timeout(0.0))

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=context,
    ) as gateway:
        rejected = gateway.call("market_data", "市场")

    assert rejected["error"] == "deadline_exhausted"
    assert calls == []


def test_gateway_redacts_tool_exception_detail() -> None:
    def failing_runner(_query: str, _context: AgentToolContext):
        raise RuntimeError("PRIVATE_TOOL_EXCEPTION_SENTINEL")

    registry = ResearchToolRegistry(
        (
            ToolSpec(
                name="market_data",
                capability="market_data",
                description="结构化行情",
                cost="local",
                freshness="current",
                runner=failing_runner,
            ),
        )
    )

    with HeadlessToolGateway(registry=registry, context=_context()) as gateway:
        result = gateway.call("market_data", "市场")
        snapshot = gateway.snapshot()

    assert result == {
        "status": "error",
        "tool": "market_data",
        "error": "tool_exception",
    }
    assert "PRIVATE_TOOL_EXCEPTION_SENTINEL" not in str(snapshot.to_dict())


def test_gateway_requires_ephemeral_bearer_and_never_writes_it_to_wrapper() -> None:
    calls: list[tuple[str, str]] = []

    with HeadlessToolGateway(
        registry=_registry(calls),
        context=_context(),
    ) as gateway:
        error = _unauthorized_call(gateway)
        wrapper_text = Path(gateway.wrapper_path).read_text(encoding="utf-8")
        environment = gateway.subprocess_environment()
        snapshot_text = json.dumps(
            gateway.snapshot().to_dict(),
            ensure_ascii=False,
        )

        assert error.code == 401
        assert environment["FINANCE_TOOL_GATEWAY_TOKEN"] not in wrapper_text
        assert environment["FINANCE_TOOL_GATEWAY_TOKEN"] not in snapshot_text
        assert "FINANCE_TOOL_GATEWAY_TOKEN" in wrapper_text
        assert gateway.endpoint.startswith("http://127.0.0.1:")
