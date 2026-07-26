from __future__ import annotations

from intelligence.services import l3_evidence
from intelligence.services import episode_tools
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_tools import build_episode_registry
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.task_frame import TaskFrame


def _l3_frame() -> TaskFrame:
    return TaskFrame(
        raw_question="瑞华泰是否已有量产订单",
        user_goal="核验公司端兑现",
        question_type="stock_deep_dive",
        subject="瑞华泰",
        subject_kind="company",
        market_scope="A股",
        timeframe="最近30日",
        required_outputs=("direct_assessment", "evidence_boundary"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_official_evidence",
        confidence=0.95,
    )


def _market_technical_frame() -> TaskFrame:
    return TaskFrame(
        raw_question="科创50你认为反弹空间有多少",
        user_goal="判断指数反弹空间",
        question_type="market_technical",
        subject="科创50",
        subject_kind="index",
        market_scope="A股",
        timeframe="当前",
        required_outputs=("technical_levels",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="structured_market_data",
        confidence=1.0,
    )


def _market_forecast_frame() -> TaskFrame:
    return TaskFrame(
        raw_question="昨天的反弹能持续多久",
        user_goal="判断市场反弹持续时间",
        question_type="market_forecast",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="最近交易日",
        required_outputs=("current_baseline", "duration_assessment"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.95,
    )


def _valuation_frame() -> TaskFrame:
    return TaskFrame(
        raw_question="瑞华泰的合理估值",
        user_goal="估算瑞华泰合理估值区间",
        question_type="valuation_estimate",
        subject="瑞华泰",
        subject_kind="company",
        market_scope="A股",
        timeframe="当前",
        required_outputs=("valuation_range",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="valuation_with_current_anchor",
        confidence=0.95,
    )


def test_valuation_registry_does_not_borrow_market_database_snapshot_date(
    tmp_path,
    monkeypatch,
) -> None:
    frame = _valuation_frame()
    context = build_episode_context(
        frame,
        task_id="valuation-asof",
        capabilities=("market_data",),
        timeout=30.0,
        latest_data_date="2026-07-22",
    )
    monkeypatch.setattr(
        episode_tools,
        "_market_block",
        lambda *_args: (
            "东财实时快照：瑞华泰最新价42.00元",
            "东财快照 + 本地 DuckDB 可比集",
            "company_valuation_snapshot",
        ),
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )

    observation = registry.execute(
        "market_data",
        {},
        context=context,
        step_id="valuation-asof:1",
    )

    assert observation.evidence[0].source_date is None


def test_valuation_registry_exposes_structured_financial_anchor(
    tmp_path,
    monkeypatch,
) -> None:
    frame = _valuation_frame()
    context = build_episode_context(
        frame,
        task_id="valuation-financial-anchor",
        capabilities=("market_data",),
        timeout=30.0,
    )
    monkeypatch.setattr(
        episode_tools.ask_blocks,
        "_financials_block_for_llm",
        lambda *_args, **_kwargs: (
            "## 逐季财报数据块 [D7]\n"
            "- 2026-06-30：营收4.20亿元，归母净利0.52亿元，毛利率38.5%"
        ),
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )

    observation = registry.execute(
        "financial_data",
        {},
        context=context,
        step_id="valuation-financial-anchor:1",
    )

    assert observation.evidence
    assert {item.tool for item in observation.evidence} == {"financial_data"}
    assert {item.source_date for item in observation.evidence} == {"2026-06-30"}
    assert observation.trace.capability == "financial_data"
    assert observation.trace.status == "success"


def test_market_registry_propagates_context_snapshot_date_to_every_atom(
    tmp_path,
    monkeypatch,
) -> None:
    frame = _market_forecast_frame()
    context = build_episode_context(
        frame,
        task_id="market-asof",
        capabilities=("market_data", "mainline_context"),
        timeout=30.0,
        latest_data_date="2026-07-23",
    )
    monkeypatch.setattr(
        episode_tools,
        "_market_block",
        lambda *_args: (
            "当前成交额21949亿元\n2026-07-20：指数上涨0.85%",
            "本地 DuckDB · 预测盘面窗口",
            "market_forecast_window",
        ),
    )
    monkeypatch.setattr(
        episode_tools.ask_blocks,
        "_market_review_mainline_context_block_for_llm",
        lambda *_args: (
            "最新主线为电子\n2026-07-20启动的电力仍在观察"
        ),
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )

    observation = registry.execute(
        "market_data",
        {},
        context=context,
        step_id="market-asof:1",
    )

    assert [item.source_date for item in observation.evidence] == [
        "2026-07-23",
        "2026-07-23",
    ]
    mainline = registry.execute(
        "mainline_context",
        {},
        context=context,
        step_id="market-asof:2",
    )
    assert [item.source_date for item in mainline.evidence] == [
        "2026-07-23",
        "2026-07-23",
    ]


def test_deterministic_fast_path_preserves_subsecond_timeout(monkeypatch) -> None:
    received: list[float] = []

    def fake_resolve(_question: str, *, timeout: float):
        received.append(timeout)
        return episode_tools.market_technical.TechnicalGap(
            subject="科创50",
            symbol=None,
            reason="test gap",
        )

    monkeypatch.setattr(
        episode_tools.market_technical,
        "resolve_market_technical",
        fake_resolve,
    )

    result = episode_tools.run_deterministic_fast_path(
        _market_technical_frame(),
        timeout=0.05,
    )

    assert received == [0.05]
    assert result["tool_calls"] == 1


def test_deterministic_fast_path_does_not_call_tool_after_deadline(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        episode_tools.market_technical,
        "resolve_market_technical",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("expired fast path must not call market provider")
        ),
    )

    result = episode_tools.run_deterministic_fast_path(
        _market_technical_frame(),
        timeout=0.0,
    )

    assert result["status"] == "failed"
    assert result["llm_calls"] == 0
    assert result["tool_calls"] == 0


def test_explicit_l3_capability_is_registered_and_returns_official_evidence(
    tmp_path,
    monkeypatch,
) -> None:
    frame = _l3_frame()
    context = build_episode_context(
        frame,
        task_id="l3-episode-test",
        capabilities=("l3_lookup",),
        timeout=30.0,
    )
    monkeypatch.setattr(
        l3_evidence,
        "lookup_l3_company",
        lambda *_args, **_kwargs: l3_evidence.L3EvidenceBundle(
            query="瑞华泰",
            items=[
                l3_evidence.L3EvidenceItem(
                    source_type="cninfo",
                    title="瑞华泰关于项目进展的公告",
                    summary="公告确认嘉兴项目进入试生产阶段。",
                    citation="https://example.invalid/announcement",
                )
            ],
        ),
    )

    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
    )
    observation = registry.execute(
        "l3_lookup",
        "瑞华泰",
        context=context,
        step_id="l3-episode-test:1",
    )

    assert "l3_lookup" in registry.names()
    assert {item["function"]["name"] for item in registry.tool_definitions()} >= {
        "l3_lookup"
    }
    assert len(observation.evidence) == 1
    assert observation.evidence[0].evidence_tier == "L3"
    assert observation.evidence[0].source.endswith("announcement")
    assert observation.trace.capability == "l3_lookup"
    assert observation.trace.status == "success"


def test_authorized_injected_l3_runner_is_defined_and_executable(tmp_path) -> None:
    frame = _l3_frame()
    context = build_episode_context(
        frame,
        task_id="l3-injected",
        capabilities=("l3_lookup",),
        timeout=30.0,
    )
    calls: list[str] = []

    def injected_runner(query, _tool_context):
        calls.append(query)
        return (
            [
                AgentEvidence(
                    tool="l3_lookup",
                    title="瑞华泰公告",
                    detail="项目进入试生产阶段",
                    source="https://example.invalid/l3",
                    source_date="2026-07-22",
                    evidence_tier="L3",
                )
            ],
            "官方公告命中",
            ProviderTrace(
                provider="injected-official",
                capability="l3_lookup",
                status="success",
                result_count=1,
            ),
        )

    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=injected_runner,
    )

    assert {item["function"]["name"] for item in registry.tool_definitions()} >= {
        "l3_lookup"
    }
    observation = registry.execute(
        "l3_lookup",
        "瑞华泰",
        context=context,
        step_id="l3-injected:1",
    )
    assert calls == ["瑞华泰"]
    assert observation.evidence[0].title == "瑞华泰公告"


def test_l3_is_not_exposed_without_runner_or_authorization(tmp_path) -> None:
    frame = _l3_frame()
    authorized = build_episode_context(
        frame,
        task_id="l3-disabled",
        capabilities=("l3_lookup",),
        timeout=30.0,
    )
    disabled = build_episode_registry(
        frame,
        authorized,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )
    assert "l3_lookup" not in disabled.names()

    unauthorized = build_episode_context(
        frame,
        task_id="l3-unauthorized",
        capabilities=("market_data",),
        timeout=30.0,
    )
    injected_but_unauthorized = build_episode_registry(
        frame,
        unauthorized,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=lambda *_args: None,
    )
    assert "l3_lookup" not in injected_but_unauthorized.names()
