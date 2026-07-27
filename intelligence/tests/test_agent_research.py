from __future__ import annotations

import json
import time
from datetime import date

from intelligence.services import agent_research
from intelligence.services.agent_research import (
    AgentEvidence,
    run_agent_loop,
    should_run,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import InformationCutoff, ResearchDeadline
from intelligence.services.research_contract import RequiredOutput, ResearchTaskContract
from intelligence.services.research_state import ResearchState


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
                    "args": {
                        "sufficient": False,
                        "assessment": "周内行情证据不足，不能定性",
                        "gaps": ["缺指数日K行情"],
                    },
                },
            ]
        ),
    )

    assert [step.tool for step in result.steps] == ["web_search", "finish"]
    assert len(result.evidence) == 1
    assert result.sufficient is False
    assert result.assessment == "周内行情证据不足，不能定性"
    assert result.gaps == ("缺指数日K行情",)
    assert result.stop_reason == "agent finish"
    assert result.traces[0].provider == "agent:web_search"


def test_gap_finish_must_try_relevant_available_capability_once() -> None:
    """Agent 不能在相关白名单工具尚未尝试时直接把可补缺口交给用户。"""

    contract = ResearchTaskContract(
        task_id="gap-before-attempt",
        question="本周市场下跌的外部触发是什么",
        subject="A股市场",
        subject_kind="market_pattern",
        question_type="market_cause",
        required_outputs=(
            RequiredOutput(
                "external_cause_evidence",
                "时间对齐的外部触发",
                ("web_search", "news_search"),
                True,
            ),
        ),
        allowed_capabilities=("web_search", "news_search"),
        research_tier="quick",
    )
    calls: list[str] = []

    def web_tool(query: str):
        calls.append(query)
        return _tool("web_search")(query)

    result = run_agent_loop(
        contract.question,
        tools={"web_search": web_tool, "news_search": _tool("news_search", hits=0)},
        steps_budget=2,
        research_state=ResearchState.from_contract(contract),
        complete_fn=_scripted_complete(
            [
                {
                    "tool": "finish",
                    "args": {
                        "sufficient": False,
                        "assessment": "外部触发仍待核验",
                        "gaps": ["缺外部证据"],
                    },
                },
                {
                    "tool": "web_search",
                    "args": {"query": "本周 A 股下跌 外部触发"},
                },
                {
                    "tool": "finish",
                    "args": {
                        "sufficient": True,
                        "assessment": "已取得时间窗口内的外部线索",
                        "gaps": [],
                    },
                },
            ]
        ),
    )

    assert calls == ["本周 A 股下跌 外部触发"]
    assert [step.tool for step in result.steps] == ["finish", "web_search", "finish"]
    assert "白名单能力尚未尝试" in result.steps[0].observation
    assert result.sufficient is True


def test_gap_finish_is_accepted_after_relevant_tool_returned_empty() -> None:
    """空结果也算已尝试；stop gate 不做隐藏重试管线。"""

    contract = ResearchTaskContract(
        task_id="gap-after-empty",
        question="未知事件",
        subject=None,
        subject_kind=None,
        question_type="general_finance_qa",
        required_outputs=(
            RequiredOutput("supporting_evidence", "可回查来源", ("web_search",), True),
        ),
        allowed_capabilities=("web_search",),
        research_tier="quick",
    )
    result = run_agent_loop(
        contract.question,
        tools={"web_search": _tool("web_search", hits=0)},
        steps_budget=2,
        research_state=ResearchState.from_contract(contract),
        complete_fn=_scripted_complete(
            [
                {"tool": "web_search", "args": {"query": "未知事件"}},
                {
                    "tool": "finish",
                    "args": {"sufficient": False, "assessment": "", "gaps": ["无结果"]},
                },
            ]
        ),
    )

    assert [step.tool for step in result.steps] == ["web_search", "finish"]
    assert result.sufficient is False
    assert result.stop_reason == "agent finish"


def test_structured_evidence_gets_stable_content_hash() -> None:
    evidence, _ = agent_research.block_lines_to_evidence(
        "market_data",
        "2026-07-20：上证指数 -1.2%",
        "本地 DuckDB",
    )
    assert evidence[0].content_hash
    assert evidence[0].content_hash == agent_research.evidence_content_hash(evidence[0])


def test_structured_evidence_can_inherit_block_snapshot_date() -> None:
    evidence, _ = agent_research.block_lines_to_evidence(
        "market_data",
        "当前成交额21949亿元\n2026-07-20：指数上涨0.85%",
        "本地 DuckDB",
        source_date="2026-07-23",
    )

    assert [item.source_date for item in evidence] == [
        "2026-07-23",
        "2026-07-23",
    ]


def test_default_news_tool_passes_the_episode_information_cutoff(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_news(query: str, **kwargs):
        captured["query"] = query
        captured["as_of"] = kwargs.get("as_of")
        return agent_research.market_news.NewsFetchResult(
            (),
            ProviderTrace(
                provider="东财",
                capability="directional_news",
                status="empty",
            ),
        )

    monkeypatch.setattr(
        agent_research.market_news,
        "fetch_eastmoney_news_result",
        fake_news,
    )
    tools = agent_research.build_default_tools(lambda *_args, **_kwargs: object())
    context = agent_research.AgentToolContext(
        ResearchDeadline.from_timeout(5.0),
        lambda: False,
        InformationCutoff(date(2026, 7, 24), "requested"),
    )

    tools["news_search"]("A股下跌原因", context)

    assert captured == {
        "query": "A股下跌原因",
        "as_of": date(2026, 7, 24),
    }


def test_default_news_tool_tightens_cutoff_to_explicit_query_window(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_news(query: str, **kwargs):
        captured["query"] = query
        captured["as_of"] = kwargs.get("as_of")
        return agent_research.market_news.NewsFetchResult(
            (),
            ProviderTrace(
                provider="东财",
                capability="directional_news",
                status="empty",
            ),
        )

    monkeypatch.setattr(
        agent_research.market_news,
        "fetch_eastmoney_news_result",
        fake_news,
    )
    tools = agent_research.build_default_tools(lambda *_args, **_kwargs: object())
    context = agent_research.AgentToolContext(
        ResearchDeadline.from_timeout(5.0),
        lambda: False,
        InformationCutoff(date(2026, 7, 27), "runtime_default"),
    )

    tools["news_search"](
        "2026年7月24日 A股大跌原因 上证指数 7月20日至24日",
        context,
    )

    assert captured == {
        "query": "2026年7月24日 A股大跌原因 上证指数 7月20日至24日",
        "as_of": date(2026, 7, 24),
    }


def test_tool_action_binds_evidence_to_known_hypothesis() -> None:
    contract = ResearchTaskContract(
        task_id="hypothesis-binding",
        question="明天是反弹还是继续下跌",
        subject="A股市场",
        subject_kind="market_pattern",
        question_type="market_forecast",
        required_outputs=(
            RequiredOutput("rebound_case", "反弹情景", ("web_search",), True),
        ),
        allowed_capabilities=("web_search",),
        research_tier="quick",
    )
    state = ResearchState.from_contract(contract)
    # RequiredOutput 也作为状态假设的来源，模拟通用 contract 的真实路径。
    state.add_hypothesis("rebound_case", "反弹情景")
    result = run_agent_loop(
        contract.question,
        tools={"web_search": _tool("web_search")},
        steps_budget=1,
        research_state=state,
        complete_fn=_scripted_complete(
            [
                {
                    "tool": "web_search",
                    "args": {
                        "query": "明天反弹触发条件",
                        "hypothesis_ids": ["rebound_case", "unknown"],
                        "stance": "support",
                    },
                }
            ]
        ),
    )
    assert result.evidence[0].supports == ("rebound_case",)
    assert result.steps[0].hypothesis_ids == ("rebound_case",)


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


def test_two_empty_tool_results_record_no_information_gain_gap() -> None:
    state = ResearchState(
        question="问题",
        subject=None,
        question_type="general_finance_qa",
    )
    result = run_agent_loop(
        "问题",
        tools={"kb_search": _tool("kb_search", hits=0)},
        steps_budget=3,
        research_state=state,
        complete_fn=_scripted_complete(
            [
                {"tool": "kb_search", "args": {"query": "第一次查询"}},
                {"tool": "kb_search", "args": {"query": "第二次查询"}},
            ]
        ),
    )

    expected_gap = "连续两次检索未获得新增信息，无法继续补全证据。"
    assert result.stop_reason == "no_information_gain"
    assert result.gaps == (expected_gap,)
    assert [gap.description for gap in state.gaps] == [expected_gap]
    assert len(result.steps) == len(result.traces) == 2


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


def test_agent_loop_preserves_synthesis_reserve_for_root_deadline() -> None:
    observed: dict[str, float] = {}
    deadline = ResearchDeadline(
        time.monotonic() + 1.0,
        synthesis_reserve=0.8,
    )

    def complete(messages, timeout=0, temperature=0.0):
        del messages, temperature
        observed["llm_timeout"] = timeout
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
    assert 0 < observed["llm_timeout"] <= 0.25


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


def test_configured_step_budget_supports_deep_hard_ceiling(monkeypatch) -> None:
    monkeypatch.delenv(agent_research.ENV_MAX_STEPS, raising=False)
    assert agent_research.max_steps() == agent_research.DEFAULT_MAX_STEPS == 4

    monkeypatch.setenv(agent_research.ENV_MAX_STEPS, "24")
    assert agent_research.max_steps() == 24
    monkeypatch.setenv(agent_research.ENV_MAX_STEPS, "25")
    assert agent_research.max_steps() == 24
    monkeypatch.setenv(agent_research.ENV_MAX_STEPS, "0")
    assert agent_research.max_steps() == 1
    monkeypatch.setenv(agent_research.ENV_MAX_STEPS, "invalid")
    assert agent_research.max_steps() == agent_research.DEFAULT_MAX_STEPS
