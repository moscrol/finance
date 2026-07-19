from __future__ import annotations

import json
import time

from intelligence.services import agent_research
from intelligence.services.agent_research import (
    AgentEvidence,
    run_agent_loop,
    should_run,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchDeadline


def _tool(name: str, hits: int = 1):
    def runner(query: str):
        evidence = [
            AgentEvidence(
                tool=name,
                title=f"{query}-命中{index}",
                detail="摘要",
                source=f"wiki/{query}-{index}.md",
            )
            for index in range(hits)
        ]
        trace = ProviderTrace(
            provider=f"agent:{name}",
            capability="agent_loop",
            status="success" if evidence else "empty",
            result_count=len(evidence),
        )
        return evidence, "观察", trace

    return runner


def _scripted_complete(actions: list[dict]):
    remaining = list(actions)

    def complete(messages, timeout=0, temperature=0.0):
        if not remaining:
            return None, None, "script exhausted"
        return json.dumps(remaining.pop(0), ensure_ascii=False), None, ""

    return complete


def test_loop_executes_tools_then_finishes_with_gaps() -> None:
    result = run_agent_loop(
        "科创50的支撑点位在哪",
        tools={"kb_search": _tool("kb_search"), "web_search": _tool("web_search")},
        steps_budget=4,
        complete_fn=_scripted_complete(
            [
                {"tool": "web_search", "args": {"query": "科创50 当前点位"}},
                {
                    "tool": "finish",
                    "args": {"sufficient": False, "gaps": ["缺指数日K行情"]},
                },
            ]
        ),
    )

    assert [step.tool for step in result.steps] == ["web_search", "finish"]
    assert len(result.evidence) == 1
    assert result.sufficient is False
    assert result.gaps == ("缺指数日K行情",)
    assert result.stop_reason == "agent finish"
    assert result.traces[0].provider == "agent:web_search"


def test_duplicate_query_is_intercepted_without_execution() -> None:
    calls: list[str] = []

    def counting_tool(query: str):
        calls.append(query)
        return [], "空", ProviderTrace(
            provider="agent:kb_search", capability="agent_loop", status="empty"
        )

    result = run_agent_loop(
        "问题",
        tools={"kb_search": counting_tool},
        steps_budget=3,
        complete_fn=_scripted_complete(
            [
                {"tool": "kb_search", "args": {"query": "同一查询"}},
                {"tool": "kb_search", "args": {"query": "同一 查询"}},
                {"tool": "finish", "args": {"sufficient": False, "gaps": []}},
            ]
        ),
    )

    assert calls == ["同一查询"]
    assert "重复查询已拦截" in result.steps[1].observation


def test_llm_unavailable_returns_partial_result() -> None:
    result = run_agent_loop(
        "问题",
        tools={"kb_search": _tool("kb_search")},
        steps_budget=3,
        complete_fn=_scripted_complete(
            [{"tool": "kb_search", "args": {"query": "查一下"}}]
        ),
    )

    assert len(result.evidence) == 1
    assert result.stop_reason.startswith("LLM 不可用")


def test_illegal_tool_stops_loop() -> None:
    result = run_agent_loop(
        "问题",
        tools={"kb_search": _tool("kb_search")},
        steps_budget=3,
        complete_fn=_scripted_complete(
            [{"tool": "rm_rf", "args": {"query": "x"}}]
        ),
    )

    assert result.steps == []
    assert "非法工具" in result.stop_reason


def test_step_budget_is_hard_limit() -> None:
    result = run_agent_loop(
        "问题",
        tools={"kb_search": _tool("kb_search")},
        steps_budget=2,
        complete_fn=_scripted_complete(
            [
                {"tool": "kb_search", "args": {"query": "一"}},
                {"tool": "kb_search", "args": {"query": "二"}},
                {"tool": "kb_search", "args": {"query": "三"}},
            ]
        ),
    )

    assert len([step for step in result.steps if step.tool != "finish"]) == 2
    assert result.stop_reason == "预算耗尽：步数"


def test_zero_total_budget_has_no_llm_or_tool_side_effect() -> None:
    llm_calls: list[float] = []
    tool_calls: list[str] = []

    def complete(messages, timeout=0, temperature=0.0):
        del messages, temperature
        llm_calls.append(timeout)
        return (
            '{"tool":"kb_search","args":{"query":"不应执行"},"reason":"x"}',
            None,
            "",
        )

    def tool(query: str):
        tool_calls.append(query)
        return _tool("kb_search")(query)

    result = run_agent_loop(
        "问题",
        tools={"kb_search": tool},
        total_seconds=0,
        complete_fn=complete,
    )

    assert llm_calls == []
    assert tool_calls == []
    assert result.stop_reason == "预算耗尽：总时长"


def test_root_deadline_clamps_llm_timeout() -> None:
    observed: list[float] = []
    deadline = ResearchDeadline(time.monotonic() + 0.5)

    def complete(messages, timeout=0, temperature=0.0):
        del messages, temperature
        observed.append(timeout)
        return (
            '{"tool":"finish","args":{"sufficient":false,"gaps":[]},"reason":"x"}',
            None,
            "",
        )

    result = run_agent_loop(
        "问题",
        tools={"kb_search": _tool("kb_search")},
        total_seconds=60,
        llm_timeout=15,
        deadline=deadline,
        complete_fn=complete,
    )

    assert result.stop_reason == "agent finish"
    assert len(observed) == 1
    assert 0 < observed[0] <= 0.5


def test_tool_exception_degrades_to_failed_trace() -> None:
    def broken(query: str):
        raise RuntimeError("boom")

    result = run_agent_loop(
        "问题",
        tools={"web_search": broken},
        steps_budget=2,
        complete_fn=_scripted_complete(
            [
                {"tool": "web_search", "args": {"query": "查"}},
                {"tool": "finish", "args": {"sufficient": False, "gaps": []}},
            ]
        ),
    )

    assert result.traces[0].status == "request_error"
    assert "工具执行失败" in result.steps[0].observation


def test_should_run_modes(monkeypatch) -> None:
    monkeypatch.setenv(agent_research.ENV_MODE, "off")
    assert not should_run(("web_search",))
    monkeypatch.setenv(agent_research.ENV_MODE, "auto")
    assert should_run(("market_quote", "web_search"))
    assert not should_run(("market_quote",))
    monkeypatch.setenv(agent_research.ENV_MODE, "on")
    assert should_run(())
