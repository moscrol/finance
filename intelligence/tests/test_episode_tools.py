from __future__ import annotations

from intelligence.services.research_tool_registry import QUERY_TOOL_PARAMETERS

from dataclasses import asdict, replace
from datetime import date
import json
from pathlib import Path

import duckdb
import pytest

from intelligence.services import (
    episode_tools,
    finance_query,
    l3_evidence,
    user_memory,
)
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_tools import build_episode_registry
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.kb_rag import RetrievalTelemetry, WikiHit, WikiRagResult
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


def _market_cause_frame() -> TaskFrame:
    return TaskFrame(
        raw_question="这一周行情下跌的主要原因是什么",
        user_goal="解释指定时间窗口内市场涨跌的主要原因并形成可回查因果链",
        question_type="market_cause",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="这一周",
        required_outputs=("direct_assessment", "causal_chain", "counterpoint"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="time_aligned_market_causal",
        confidence=0.96,
    )


def _historical_market_cause_frame() -> TaskFrame:
    return TaskFrame(
        raw_question="2026年7月1日至5日A股下跌的主要原因是什么",
        user_goal="解释指定历史窗口内市场涨跌的主要原因并形成可回查因果链",
        question_type="market_cause",
        subject="A股市场",
        subject_kind="market_pattern",
        market_scope="A股",
        timeframe="2026-07-01",
        required_outputs=("direct_assessment", "causal_chain", "counterpoint"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="time_aligned_market_causal",
        confidence=0.96,
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


def test_sealed_fixture_registry_is_local_only(tmp_path, monkeypatch) -> None:
    def unexpected_call(*_args, **_kwargs):
        raise AssertionError("sealed fixture attempted an external provider")

    monkeypatch.setattr(
        episode_tools.agent_research.web_research,
        "fetch_web_search",
        unexpected_call,
    )
    monkeypatch.setattr(
        episode_tools.market_news,
        "fetch_eastmoney_news_result",
        unexpected_call,
    )
    monkeypatch.setattr(
        episode_tools.valuation_estimate,
        "fetch_eastmoney_snapshot",
        unexpected_call,
    )
    monkeypatch.setattr(
        episode_tools.ask_blocks.market_financials,
        "fetch_quarterly_financials",
        unexpected_call,
    )
    monkeypatch.setattr(
        episode_tools.ask_blocks.market_financials,
        "fetch_quarterly_financials_akshare",
        unexpected_call,
    )
    frame = replace(
        _valuation_frame(),
        raw_question="688323 瑞华泰的合理估值",
    )
    context = build_episode_context(
        frame,
        task_id="sealed-fixture-local-only",
        capabilities=(
            "kb_search",
            "web_search",
            "news_search",
            "l3_lookup",
            "market_data",
            "financial_data",
        ),
        timeout=30.0,
    )

    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        fixture_policy=episode_tools.SealedFixturePolicy(),
    )

    assert registry.names() == (
        "kb_search",
        "graph_lookup",
        "evidence_lookup",
        "market_data",
        "financial_data",
        "finance_query",
        "evidence_search",
    )
    registry.execute(
        "market_data",
        {},
        context=context,
        step_id="sealed-fixture-local-only:market",
    )
    registry.execute(
        "financial_data",
        {},
        context=context,
        step_id="sealed-fixture-local-only:financials",
    )


def test_sealed_fixture_registry_uses_explicit_physical_paths(
    tmp_path,
    monkeypatch,
) -> None:
    frame = _market_cause_frame()
    context = build_episode_context(
        frame,
        task_id="sealed-fixture-physical-paths",
        capabilities=("kb_search", "market_data"),
        timeout=30.0,
        today="2026-07-24",
        latest_data_date="2026-07-24",
    )
    finance_root = tmp_path / "unused-finance-root"
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    market_db = tmp_path / "finance.duckdb"
    market_db.write_bytes(b"fixture")
    index = tmp_path / "hybrid-index"
    index.mkdir()
    code = tmp_path / "kb-code"
    (code / "scripts").mkdir(parents=True)
    python = tmp_path / "rag-python"
    python.write_text("", encoding="utf-8")
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        episode_tools.ask_blocks,
        "_market_data_asof",
        lambda path, **_kwargs: captured.setdefault("market_db", path)
        and "2026-07-24",
    )

    def fake_retrieve(_query, _wiki, **kwargs):
        captured.update(kwargs)
        return episode_tools.kb_rag.WikiRagResult()

    monkeypatch.setattr(episode_tools.kb_rag, "retrieve", fake_retrieve)

    registry = build_episode_registry(
        frame,
        context,
        finance_root=finance_root,
        knowledge_wiki=wiki,
        fixture_policy=episode_tools.SealedFixturePolicy(
            market_db_path=market_db,
            knowledge_index_dir=index,
            knowledge_code_root=code,
            knowledge_python=python,
        ),
    )
    registry.execute(
        "kb_search",
        "A股下跌",
        context=context,
        step_id="sealed-fixture-physical-paths:kb",
    )

    assert captured["market_db"] == market_db
    assert captured["index_dir"] == index
    assert captured["code_root"] == code
    assert captured["python_executable"] == python
    assert captured["worker_enabled"] is False


def test_valuation_registry_uses_valuation_provider_snapshot_date(
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
            "东财实时快照：瑞华泰最新价42.00元\n"
            "- 估值快照日期：2026-07-22（来源返回时间；不等同本地盘面日期）。",
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

    assert observation.evidence[0].source_date == "2026-07-22"
    assert observation.trace.served_date == "2026-07-22"


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


def test_valuation_tools_reuse_shared_entity_anchor_for_subject_resolution(
    tmp_path: Path,
    monkeypatch,
) -> None:
    wiki = tmp_path / "wiki"
    relations = wiki / "relations"
    relations.mkdir(parents=True)
    (relations / "entity_exposures.json").write_text(
        '{"entities":{"瑞华泰":{"codes":["688323"],"concepts":{"PI薄膜":{}}}}}',
        encoding="utf-8",
    )
    captured: dict[str, str] = {}

    def fake_valuation(query, *_args, **_kwargs):
        captured["valuation"] = str(query)
        return "目标估值快照：瑞华泰（688323）市值50亿元，PB 2.0。"

    def fake_financials(query, *_args, **_kwargs):
        captured["financials"] = str(query)
        return "逐季财务数据：2026Q1 营收4亿元，归母净利0.5亿元。"

    monkeypatch.setattr(
        episode_tools.ask_blocks,
        "_valuation_block_for_llm",
        fake_valuation,
    )
    monkeypatch.setattr(
        episode_tools.ask_blocks,
        "_financials_block_for_llm",
        fake_financials,
    )
    frame = _valuation_frame()
    context = build_episode_context(
        frame,
        task_id="valuation-entity-anchor",
        capabilities=("market_data", "financial_data"),
        timeout=30.0,
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=wiki,
        l3_runner=None,
    )

    market = registry.execute(
        "market_data",
        {},
        context=context,
        step_id="valuation-entity-anchor:market",
    )
    financials = registry.execute(
        "financial_data",
        {},
        context=context,
        step_id="valuation-entity-anchor:financials",
    )

    assert market.evidence
    assert financials.evidence
    assert "瑞华泰" in captured["valuation"]
    assert "688323" in captured["valuation"]
    assert "瑞华泰" in captured["financials"]
    assert "688323" in captured["financials"]


def test_time_aligned_market_news_uses_market_window_end_without_query_date(
    tmp_path,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_news(query: str, **kwargs):
        captured["query"] = query
        captured["as_of"] = kwargs.get("as_of")
        return episode_tools.agent_research.market_news.NewsFetchResult(
            (),
            ProviderTrace("东财", "directional_news", "empty"),
        )

    monkeypatch.setattr(
        episode_tools.agent_research.market_news,
        "fetch_eastmoney_news_result",
        fake_news,
    )
    frame = _market_cause_frame()
    context = build_episode_context(
        frame,
        task_id="market-cause-news-window",
        capabilities=("news_search",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-27",
        latest_data_date="2026-07-24",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )

    registry.execute(
        "news_search",
        {"query": "A股下跌原因"},
        context=context,
        step_id="market-cause-news-window:1",
    )

    assert captured == {
        "query": "A股下跌原因",
        "as_of": date(2026, 7, 24),
    }


def test_time_aligned_market_news_uses_explicit_historical_window_end(
    tmp_path,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_news(query: str, **kwargs):
        captured["query"] = query
        captured["as_of"] = kwargs.get("as_of")
        return episode_tools.agent_research.market_news.NewsFetchResult(
            (),
            ProviderTrace("东财", "directional_news", "empty"),
        )

    monkeypatch.setattr(
        episode_tools.agent_research.market_news,
        "fetch_eastmoney_news_result",
        fake_news,
    )
    frame = _historical_market_cause_frame()
    context = build_episode_context(
        frame,
        task_id="historical-market-cause-news-window",
        capabilities=("news_search",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-27",
        latest_data_date="2026-07-24",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )

    registry.execute(
        "news_search",
        {"query": "A股下跌原因"},
        context=context,
        step_id="historical-market-cause-news-window:1",
    )

    assert captured == {"query": "A股下跌原因", "as_of": date(2026, 7, 5)}


def test_time_aligned_causal_evidence_rejects_off_window_topic_drift(
    tmp_path,
    monkeypatch,
) -> None:
    seen_queries: list[str] = []

    def retrieve(query: str, *_args, **_kwargs) -> WikiRagResult:
        seen_queries.append(query)
        hit = WikiHit(
            page_id="old-topic-drift",
            file_path="wiki/sources/晚间卖方研报20260709.md",
            title="半导体与光纤光缆复盘",
            score=0.9,
            excerpt="行情下跌后关注半导体、光纤光缆、牧原股份和猪周期",
            best_chunk_id="old-topic-drift::0",
            content_hash="old-topic-drift",
            source_date="2026-07-09",
            index_freshness="fresh",
        )
        return WikiRagResult(
            ok=True,
            hits=[hit],
            telemetry=RetrievalTelemetry(status="ok", hit_count=1),
            command=query,
        )

    monkeypatch.setattr(episode_tools.kb_rag, "retrieve", retrieve)
    frame = _market_cause_frame()
    context = build_episode_context(
        frame,
        task_id="market-cause-evidence-window",
        capabilities=("evidence_search",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-27",
        latest_data_date="2026-07-24",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
        evidence_search_judge=lambda *_args: None,
    )

    result = registry.execute(
        "evidence_search",
        frame.raw_question,
        context=context,
        step_id="market-cause-evidence-window:1",
    )

    assert result.trace.status == "empty"
    assert result.evidence == ()
    assert result.observation == ""
    assert any("2026-07-20" in gap for gap in result.gaps)
    forbidden = ("牧原股份", "猪周期", "半导体", "光纤光缆")
    assert all(
        token not in query
        for query in seen_queries[1:]
        for token in forbidden
    )


def _write_ruihuatai_anchor(wiki: Path) -> None:
    relations = wiki / "relations"
    relations.mkdir(parents=True)
    (relations / "entity_exposures.json").write_text(
        '{"entities":{"瑞华泰":{"codes":["688323.SH"],'
        '"concepts":{"PI薄膜":{}}},"方邦股份":{"codes":["688020.SH"],'
        '"concepts":{"功能薄膜":{}}}}}',
        encoding="utf-8",
    )


def _valuation_admission_retriever():
    calls = 0

    def retrieve(query: str, *_args, **_kwargs) -> WikiRagResult:
        nonlocal calls
        calls += 1
        if calls > 1:
            return WikiRagResult(
                ok=False,
                hits=[],
                telemetry=RetrievalTelemetry(status="empty", hit_count=0),
                command=query,
            )
        hits = [
            WikiHit(
                page_id="subject",
                file_path="wiki/entities/瑞华泰.md",
                title="瑞华泰（688323）",
                score=0.9,
                excerpt="证据条目：公司基础资料",
                best_chunk_id="subject::0",
                content_hash="subject",
                source_date="2026-07-24",
                index_freshness="fresh",
            ),
            WikiHit(
                page_id="bare",
                file_path="wiki/entities/天奈科技.md",
                title="天奈科技（688116）",
                score=0.8,
                excerpt="证据条目：[[汉威科技]] · [[福莱新材]] · [[瑞华泰]]",
                best_chunk_id="bare::0",
                content_hash="bare",
                source_date="2026-07-24",
                index_freshness="fresh",
            ),
            WikiHit(
                page_id="relation",
                file_path="wiki/entities/方邦股份.md",
                title="方邦股份（688020）",
                score=0.7,
                excerpt="证据条目：[[瑞华泰]] — PI薄膜企业，同属功能薄膜赛道",
                best_chunk_id="relation::0",
                content_hash="relation",
                source_date="2026-07-24",
                index_freshness="fresh",
            ),
        ]
        return WikiRagResult(
            ok=True,
            hits=hits,
            telemetry=RetrievalTelemetry(status="ok", hit_count=len(hits)),
            command=query,
        )

    return retrieve


@pytest.mark.parametrize("tool_query", ["合理估值证据", "方邦股份 PB"])
def test_valuation_registry_keeps_frame_anchor_for_every_evidence_query(
    tmp_path,
    monkeypatch,
    tool_query,
) -> None:
    wiki = tmp_path / "wiki"
    _write_ruihuatai_anchor(wiki)
    monkeypatch.setattr(
        episode_tools.kb_rag,
        "retrieve",
        _valuation_admission_retriever(),
    )
    frame = _valuation_frame()
    context = build_episode_context(
        frame,
        task_id="valuation-subject-local-admission",
        capabilities=("evidence_search",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-24",
        latest_data_date="2026-07-24",
    )

    result = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=wiki,
        l3_runner=None,
        evidence_search_judge=lambda *_args: None,
    ).execute(
        "evidence_search",
        tool_query,
        context=context,
        step_id="valuation-subject-local-admission:1",
    )

    assert [item.title for item in result.evidence] == ["瑞华泰（688323）"]
    assert result.trace.status == "success"


def test_non_valuation_registry_keeps_open_evidence_admission(
    tmp_path,
    monkeypatch,
) -> None:
    wiki = tmp_path / "wiki"
    _write_ruihuatai_anchor(wiki)
    monkeypatch.setattr(
        episode_tools.kb_rag,
        "retrieve",
        _valuation_admission_retriever(),
    )
    frame = _l3_frame()
    context = build_episode_context(
        frame,
        task_id="non-valuation-open-admission",
        capabilities=("evidence_search",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-24",
        latest_data_date="2026-07-24",
    )

    result = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=wiki,
        l3_runner=None,
        evidence_search_judge=lambda *_args: None,
    ).execute(
        "evidence_search",
        "合理估值证据",
        context=context,
        step_id="non-valuation-open-admission:1",
    )

    assert {item.title for item in result.evidence} == {
        "瑞华泰（688323）",
        "天奈科技（688116）",
        "方邦股份（688020）",
    }


def test_time_aligned_market_web_filters_results_after_market_window(
    tmp_path,
    monkeypatch,
) -> None:
    web_research = episode_tools.agent_research.web_research

    def fake_web(_query: str, **_kwargs):
        return web_research.WebSearchResult(
            (
                web_research.WebSearchItem(
                    "7月27日 A股盘后消息",
                    "https://example.test/future",
                    "7月27日盘后出现的新催化",
                ),
                web_research.WebSearchItem(
                    "7月24日 A股收评",
                    "https://example.test/aligned",
                    "7月24日市场回撤",
                ),
            ),
            ProviderTrace(
                "bing_web",
                "general_web_search",
                "success",
                result_count=2,
            ),
        )

    monkeypatch.setattr(web_research, "fetch_web_search", fake_web)
    frame = _market_cause_frame()
    context = build_episode_context(
        frame,
        task_id="market-cause-web-window",
        capabilities=("web_search",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-27",
        latest_data_date="2026-07-24",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )

    observation = registry.execute(
        "web_search",
        {"query": "A股下跌原因"},
        context=context,
        step_id="market-cause-web-window:1",
    )

    assert [item.source_date for item in observation.evidence] == ["2026-07-24"]
    assert [item.source for item in observation.evidence] == [
        "https://example.test/aligned"
    ]
    assert observation.trace.requested_date == "2026-07-24"
    assert "future_of_cutoff=1" in observation.trace.detail


def test_historical_market_web_uses_task_window_instead_of_latest_data_date(
    tmp_path,
    monkeypatch,
) -> None:
    web_research = episode_tools.agent_research.web_research

    def fake_web(_query: str, **_kwargs):
        return web_research.WebSearchResult(
            (
                web_research.WebSearchItem(
                    "7月6日 历史窗口后的复盘",
                    "https://example.test/after-window",
                    "7月6日新增解释",
                ),
                web_research.WebSearchItem(
                    "7月5日 历史窗口收评",
                    "https://example.test/window-end",
                    "7月5日市场表现",
                ),
            ),
            ProviderTrace(
                "bing_web",
                "general_web_search",
                "success",
                result_count=2,
            ),
        )

    monkeypatch.setattr(web_research, "fetch_web_search", fake_web)
    frame = _historical_market_cause_frame()
    context = build_episode_context(
        frame,
        task_id="historical-market-cause-web-window",
        capabilities=("web_search",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-27",
        latest_data_date="2026-07-24",
    )
    observation = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    ).execute(
        "web_search",
        {"query": "A股下跌原因"},
        context=context,
        step_id="historical-market-cause-web-window:1",
    )

    assert [item.source for item in observation.evidence] == [
        "https://example.test/window-end"
    ]
    assert observation.trace.requested_date == "2026-07-05"
    assert "future_of_cutoff=1" in observation.trace.detail


def test_market_registry_uses_structured_provider_date_for_every_atom(
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
        "_market_data_asof",
        lambda *_args, **_kwargs: "2026-07-23",
    )
    monkeypatch.setattr(
        episode_tools.ask_blocks,
        "_market_review_mainline_context_block_for_llm",
        lambda *_args, **_kwargs: (
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


def test_episode_registry_exposes_and_executes_model_owned_research_tools(
    tmp_path: Path,
    monkeypatch,
) -> None:
    finance_root = tmp_path / "finance"
    db_path = finance_root / "db" / "market_feature_store.duckdb"
    db_path.parent.mkdir(parents=True)
    connection = duckdb.connect(str(db_path))
    connection.execute(
        """
        create table fact_market_daily(
            trade_date date,
            market_stage varchar,
            total_amount double,
            sh_index_pct_chg double
        )
        """
    )
    connection.execute(
        "insert into fact_market_daily values ('2026-07-24', '反弹阶段', 22000, 1.2)"
    )
    connection.close()

    def retrieve(query: str, *_args, **_kwargs) -> WikiRagResult:
        hit = WikiHit(
            page_id="mainline",
            file_path="wiki/sources/mainline.md",
            title="A股市场主线证据",
            score=0.9,
            excerpt="A股市场主线需要成交、强度和持续性共同验证",
            best_chunk_id="mainline::0",
            content_hash="mainline-content",
            source_date="2026-07-24",
        )
        return WikiRagResult(
            ok=True,
            hits=[hit],
            telemetry=RetrievalTelemetry(status="ok", hit_count=1),
            command=query,
        )

    monkeypatch.setattr(episode_tools.kb_rag, "retrieve", retrieve)
    frame = _market_forecast_frame()
    context = build_episode_context(
        frame,
        task_id="model-owned-tools",
        capabilities=("market_data",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-24",
        latest_data_date="2026-07-24",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=finance_root,
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
        evidence_search_judge=lambda *_args: None,
    )

    tool_definitions = registry.tool_definitions()
    definitions = {
        item["function"]["name"]: item["function"]["parameters"]
        for item in tool_definitions
    }
    descriptions = {
        item["function"]["name"]: item["function"]["description"]
        for item in tool_definitions
    }
    assert set(definitions["finance_query"]["properties"]["dataset"]["enum"]) == {
        "market_daily",
        "stock_daily",
        "sector_daily",
        "sector_stock_daily",
        "stock_high_daily",
        "mainline_theme_daily",
        "mainline_sector_daily",
    }
    assert set(definitions["finance_query"]["required"]) == {
        "dataset",
        "metrics",
        "dimensions",
    }
    assert "sector_daily" in descriptions["finance_query"]
    assert "return_pct" in descriptions["finance_query"]
    assert "不要混用不同 dataset 的字段" in descriptions["finance_query"]
    # 比对真本源而非手抄字面量，见 BUILD 模式 6。
    assert definitions["evidence_search"] == QUERY_TOOL_PARAMETERS

    structured = registry.execute(
        "finance_query",
        {
            "dataset": "market_daily",
            "metrics": ["index_return_pct", "total_amount"],
            "dimensions": ["trade_date", "market_stage"],
            "filters": [],
            "time_range": {"start": "2026-07-24", "end": "2026-07-24"},
            "group_by": [],
            "order_by": [{"field": "trade_date", "direction": "asc"}],
            "limit": 5,
        },
        context=context,
        step_id="model-owned-tools:finance",
    )
    searched = registry.execute(
        "evidence_search",
        "A股市场主线",
        context=context,
        step_id="model-owned-tools:evidence",
    )

    assert structured.evidence[0].tool == "finance_query"
    assert structured.trace.served_date == "2026-07-24"
    assert searched.evidence[0].tool == "evidence_search"
    assert searched.trace.requested_date == "2026-07-24"


def test_current_finance_query_rejects_rows_older_than_snapshot_floor(
    tmp_path: Path,
) -> None:
    finance_root = tmp_path / "finance"
    db_path = finance_root / "db" / "market_feature_store.duckdb"
    db_path.parent.mkdir(parents=True)
    connection = duckdb.connect(str(db_path))
    connection.execute(
        """
        create table fact_market_daily(
            trade_date date,
            market_stage varchar,
            total_amount double,
            sh_index_pct_chg double
        )
        """
    )
    connection.execute(
        "insert into fact_market_daily values "
        "('2025-06-30', '主升阶段', 14866, 0.59)"
    )
    connection.close()
    frame = _market_forecast_frame()
    context = build_episode_context(
        frame,
        task_id="stale-current-market",
        capabilities=("market_data",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-27",
        latest_data_date="2026-07-27",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=finance_root,
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )

    result = registry.execute(
        "finance_query",
        {
            "dataset": "market_daily",
            "metrics": ["index_return_pct", "total_amount"],
            "dimensions": ["trade_date", "market_stage"],
            "filters": [],
            "group_by": [],
            "order_by": [{"field": "trade_date", "direction": "desc"}],
            "limit": 5,
        },
        context=context,
        step_id="stale-current-market:1",
    )

    assert result.evidence == ()
    assert result.trace.status == "stale"
    assert result.trace.requested_date == "2026-07-27"
    assert result.trace.served_date == "2025-06-30"
    assert result.gaps == (
        "结构化市场数据仅更新到 2025-06-30，早于当前所需 2026-07-27；"
        "旧数据未用于当前判断",
    )


def test_current_market_tool_rejects_stale_block_before_model_observation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    frame = _market_forecast_frame()
    context = build_episode_context(
        frame,
        task_id="stale-current-block",
        capabilities=("market_data",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-27",
        latest_data_date="2026-07-27",
    )
    monkeypatch.setattr(
        episode_tools.ask_blocks,
        "_market_data_asof",
        lambda *_args, **_kwargs: "2025-06-30",
    )
    monkeypatch.setattr(
        episode_tools,
        "_market_block",
        lambda *_args: (
            "交易日=2025-06-30；市场阶段=主升阶段",
            "本地 DuckDB · 预测盘面窗口",
            "market_forecast_window",
        ),
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )

    result = registry.execute(
        "market_data",
        {},
        context=context,
        step_id="stale-current-block:1",
    )

    assert result.evidence == ()
    assert result.trace.status == "stale"
    assert result.trace.requested_date == "2026-07-27"
    assert result.trace.served_date == "2025-06-30"


def test_model_selected_historical_window_is_rejected_for_current_task(
    tmp_path: Path,
) -> None:
    finance_root = tmp_path / "finance"
    db_path = finance_root / "db" / "market_feature_store.duckdb"
    db_path.parent.mkdir(parents=True)
    connection = duckdb.connect(str(db_path))
    connection.execute(
        "create table fact_market_daily("
        "trade_date date, market_stage varchar, total_amount double)"
    )
    connection.execute(
        "insert into fact_market_daily values "
        "('2025-06-30', '主升阶段', 14866)"
    )
    connection.close()
    frame = _market_forecast_frame()
    context = build_episode_context(
        frame,
        task_id="model-selected-historical-market",
        capabilities=("market_data",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-27",
        latest_data_date="2026-07-27",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=finance_root,
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )

    result = registry.execute(
        "finance_query",
        {
            "dataset": "market_daily",
            "metrics": ["total_amount"],
            "dimensions": ["trade_date", "market_stage"],
            "filters": [],
            "time_range": {"start": "2025-06-30", "end": "2025-06-30"},
            "group_by": [],
            "order_by": [{"field": "trade_date", "direction": "desc"}],
            "limit": 5,
        },
        context=context,
        step_id="model-selected-historical-market:1",
    )

    assert result.evidence == ()
    assert result.trace.status == "parse_error"
    assert "historical_window_not_authorized_by_task" in result.trace.detail
    assert result.trace.requested_date == "2026-07-27"


def test_user_dated_task_authorizes_historical_finance_query(
    tmp_path: Path,
) -> None:
    finance_root = tmp_path / "finance"
    db_path = finance_root / "db" / "market_feature_store.duckdb"
    db_path.parent.mkdir(parents=True)
    connection = duckdb.connect(str(db_path))
    connection.execute(
        "create table fact_market_daily("
        "trade_date date, market_stage varchar, total_amount double)"
    )
    connection.execute(
        "insert into fact_market_daily values "
        "('2026-07-01', '下跌阶段', 14866)"
    )
    connection.close()
    frame = _historical_market_cause_frame()
    context = build_episode_context(
        frame,
        task_id="user-authorized-historical-market",
        capabilities=("market_data",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-27",
        latest_data_date="2026-07-27",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=finance_root,
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )

    result = registry.execute(
        "finance_query",
        {
            "dataset": "market_daily",
            "metrics": ["total_amount"],
            "dimensions": ["trade_date", "market_stage"],
            "filters": [],
            "time_range": {"start": "2026-07-01", "end": "2026-07-01"},
            "group_by": [],
            "order_by": [{"field": "trade_date", "direction": "desc"}],
            "limit": 5,
        },
        context=context,
        step_id="user-authorized-historical-market:1",
    )

    assert len(result.evidence) == 1
    assert result.trace.status == "success"
    assert result.trace.served_date == "2026-07-01"


def test_frozen_cutoff_caps_newer_snapshot_freshness_floor(
    tmp_path: Path,
) -> None:
    finance_root = tmp_path / "finance"
    db_path = finance_root / "db" / "market_feature_store.duckdb"
    db_path.parent.mkdir(parents=True)
    connection = duckdb.connect(str(db_path))
    connection.execute(
        "create table fact_market_daily("
        "trade_date date, market_stage varchar, total_amount double)"
    )
    connection.execute(
        "insert into fact_market_daily values "
        "('2026-07-24', '下跌阶段', 24000)"
    )
    connection.close()
    frame = _market_forecast_frame()
    context = build_episode_context(
        frame,
        task_id="frozen-market-cutoff",
        capabilities=("market_data",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-24",
        latest_data_date="2026-07-27",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=finance_root,
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )

    result = registry.execute(
        "finance_query",
        {
            "dataset": "market_daily",
            "metrics": ["total_amount"],
            "dimensions": ["trade_date", "market_stage"],
            "filters": [],
            "group_by": [],
            "order_by": [{"field": "trade_date", "direction": "desc"}],
            "limit": 5,
        },
        context=context,
        step_id="frozen-market-cutoff:1",
    )

    assert len(result.evidence) == 1
    assert result.trace.status == "success"
    assert result.trace.served_date == "2026-07-24"


def test_frozen_market_tool_selects_provider_rows_at_cutoff(
    tmp_path: Path,
) -> None:
    finance_root = tmp_path / "finance"
    db_path = finance_root / "db" / "market_feature_store.duckdb"
    db_path.parent.mkdir(parents=True)
    connection = duckdb.connect(str(db_path))
    connection.execute(
        """
        create table fact_market_daily(
          trade_date date, market_stage varchar, stage_day integer,
          total_amount double, advancers integer, limit_up integer,
          limit_down integer, sh_index_close double, sh_index_pct_chg double,
          industry_1 varchar, industry_1_ratio double,
          industry_2 varchar, industry_2_ratio double,
          industry_3 varchar, industry_3_ratio double
        )
        """
    )
    connection.execute(
        """
        insert into fact_market_daily values
        ('2026-07-24', '反弹阶段', 1, 25000, 3600, 90, 5, 3850, 1.3,
         '电子', 25, '通信', 10, '计算机', 8),
        ('2026-07-27', '主升阶段', 2, 29000, 4200, 120, 2, 3920, 1.8,
         '机器人', 28, '军工', 11, '医药', 9)
        """
    )
    connection.close()
    frame = _market_forecast_frame()
    context = build_episode_context(
        frame,
        task_id="frozen-market-provider-selection",
        capabilities=("market_data",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-24",
        latest_data_date="2026-07-27",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=finance_root,
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )

    result = registry.execute(
        "market_data",
        {},
        context=context,
        step_id="frozen-market-provider-selection:1",
    )

    assert result.evidence
    assert {item.source_date for item in result.evidence} == {"2026-07-24"}
    assert result.trace.status == "success"
    assert result.trace.served_date == "2026-07-24"
    assert not result.trace.detail.startswith("future_of_cutoff")


def test_agent_finance_query_bounds_broad_result_before_model_observation(
    tmp_path: Path,
) -> None:
    """Broad typed queries must not flood every later model turn."""

    finance_root = tmp_path / "finance"
    db_path = finance_root / "db" / "market_feature_store.duckdb"
    db_path.parent.mkdir(parents=True)
    connection = duckdb.connect(str(db_path))
    connection.execute(
        """
        create table fact_sector_daily(
            trade_date date,
            sector_ts_code varchar,
            sector_name varchar,
            sw_l1 varchar,
            multi_period_resonance boolean,
            pct_chg double,
            amount double,
            diff_ratio double,
            strength double
        )
        """
    )
    connection.executemany(
        "insert into fact_sector_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "2026-07-24",
                f"88{index:04d}.TI",
                f"板块{index}",
                "电子",
                False,
                float(index),
                float(index * 10),
                float(index) / 10,
                float(index) / 20,
            )
            for index in range(60)
        ],
    )
    connection.close()

    frame = _market_forecast_frame()
    context = build_episode_context(
        frame,
        task_id="finance-query-observation-budget",
        capabilities=("market_data",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-24",
        latest_data_date="2026-07-24",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=finance_root,
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )

    observation = registry.execute(
        "finance_query",
        {
            "dataset": "sector_daily",
            "metrics": ["return_pct", "amount", "marginal_volume_pct"],
            "dimensions": ["trade_date", "sector_code", "sector_name"],
            "filters": [],
            "time_range": {"start": "2026-07-24", "end": "2026-07-24"},
            "group_by": [],
            "order_by": [{"field": "return_pct", "direction": "desc"}],
            "limit": 100,
        },
        context=context,
        step_id="finance-query-observation-budget:1",
    )

    assert len(observation.evidence) == 25
    assert observation.trace.result_count == 25
    assert "已按 Agent 上下文预算截断至 25 条" in observation.observation


def test_finance_query_invalid_semantic_field_returns_repairable_gap(
    tmp_path: Path,
) -> None:
    frame = _market_forecast_frame()
    context = build_episode_context(
        frame,
        task_id="finance-query-invalid-field",
        capabilities=("market_data",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-24",
        latest_data_date="2026-07-24",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )

    observation = registry.execute(
        "finance_query",
        {
            "dataset": "market_daily",
            "metrics": ["not_a_public_metric"],
            "dimensions": ["trade_date"],
            "filters": [],
            "group_by": [],
            "order_by": [],
            "limit": 5,
        },
        context=context,
        step_id="finance-query-invalid-field:1",
    )

    assert observation.evidence == ()
    assert observation.trace.status == "parse_error"
    assert "invalid_query" in observation.trace.detail
    assert "not_a_public_metric" in observation.observation
    assert "重试提示" in observation.observation
    assert "index_return_pct" in observation.observation
    assert observation.gaps == (
        "结构化查询条件无效；请改写 dataset、字段、筛选或日期范围后重试",
    )


def test_finance_query_wrong_dataset_points_to_the_field_owner(
    tmp_path: Path,
) -> None:
    frame = _market_forecast_frame()
    context = build_episode_context(
        frame,
        task_id="finance-query-cross-dataset-repair",
        capabilities=("market_data",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-24",
        latest_data_date="2026-07-24",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )

    observation = registry.execute(
        "finance_query",
        {
            "dataset": "market_daily",
            "metrics": ["net_inflow_1d", "max_limit_height"],
            "dimensions": ["trade_date"],
            "filters": [],
            "group_by": [],
            "order_by": [],
            "limit": 5,
        },
        context=context,
        step_id="finance-query-cross-dataset-repair:1",
    )

    assert observation.trace.status == "parse_error"
    assert "net_inflow_1d" in observation.observation
    assert "max_limit_height" in observation.observation
    assert "mainline_sector_daily" in observation.observation
    assert "metric" in observation.observation
    assert "拆成多个查询" in observation.observation


def test_finance_query_date_filter_is_compensated_not_rejected(
    tmp_path: Path,
) -> None:
    """日期写进 filters 时 Harness 代偿搬到 time_range，不再烧掉一个工具槽。

    这条曾断言 `parse_error`：写法错了就报错，靠重试提示让模型改。实测一轮
    research 里同一个错犯了两次，两个槽白烧后 `deadline_exhausted` 降级——提示
    在那儿，模型隔一轮又照原样写。所以判定改成代偿：语义等价时直接搬，把
    「写法不合规」从失败降级成一句附注。

    仍要断言附注存在：代偿必须让模型看见，否则下一轮还会照原样写。
    """

    finance_root = tmp_path / "finance"
    db_path = finance_root / "db" / "market_feature_store.duckdb"
    db_path.parent.mkdir(parents=True)
    connection = duckdb.connect(str(db_path))
    connection.execute(
        """
        create table fact_market_daily(
            trade_date date,
            sh_index_pct_chg double
        )
        """
    )
    connection.executemany(
        "insert into fact_market_daily values (?, ?)",
        [("2026-07-23", 0.4), ("2026-07-24", 1.25)],
    )
    connection.close()

    frame = _market_forecast_frame()
    context = build_episode_context(
        frame,
        task_id="finance-query-date-filter-repair",
        capabilities=("market_data",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-24",
        latest_data_date="2026-07-24",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=finance_root,
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )

    observation = registry.execute(
        "finance_query",
        {
            "dataset": "market_daily",
            "metrics": ["index_return_pct"],
            "dimensions": ["trade_date"],
            "filters": [
                {"field": "trade_date", "op": "eq", "value": "2026-07-24"}
            ],
            "group_by": [],
            "order_by": [],
            "limit": 5,
        },
        context=context,
        step_id="finance-query-date-filter-repair:1",
    )

    # 查询真的跑了：`eq 2026-07-24` 搬成闭区间单日，只命中那一行。
    assert observation.trace.status == "success"
    assert len(observation.evidence) == 1
    assert "1.25" in observation.observation
    # 且模型被告知写法被改过，以及下次该怎么写。
    assert "已自动把 filters 中的日期条件搬到 time_range" in observation.observation
    assert "trade_date eq 2026-07-24" in observation.observation


@pytest.mark.parametrize(
    ("failure", "failure_code", "expected_gap"),
    [
        (
            finance_query.FinanceQueryTimedOut("physical sql timeout"),
            "timeout",
            "结构化查询超时；请缩小时间范围、字段或结果数量后重试",
        ),
        (
            finance_query.FinanceQueryCancelled("cancelled"),
            "cancelled",
            "结构化查询被取消；如任务仍需该数据，请重新发起更窄的查询",
        ),
        (
            finance_query.FinanceQueryLimitExceeded("byte limit"),
            "limit_exceeded",
            "结构化查询结果超过资源上限；请缩小时间范围、字段或结果数量后重试",
        ),
        (
            finance_query.FinanceQueryExecutionError(
                "missing physical table fact_market_daily"
            ),
            "request_error",
            "结构化数据源暂不可用；当前答案仍缺少该查询对应的数据",
        ),
    ],
)
def test_finance_query_runtime_failure_returns_safe_repairable_gap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    failure_code: str,
    expected_gap: str,
) -> None:
    class FailingFinanceQuery:
        def __init__(self, _path: Path) -> None:
            pass

        def run(self, *_args, **_kwargs):
            raise failure

    monkeypatch.setattr(
        episode_tools.finance_query, "FinanceQuery", FailingFinanceQuery
    )
    frame = _market_forecast_frame()
    context = build_episode_context(
        frame,
        task_id=f"finance-query-{failure_code}",
        capabilities=("market_data",),
        timeout=10.0,
        synthesis_reserve=0.0,
        today="2026-07-24",
        latest_data_date="2026-07-24",
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
    )

    observation = registry.execute(
        "finance_query",
        {
            "dataset": "market_daily",
            "metrics": ["index_return_pct"],
            "dimensions": ["trade_date"],
            "filters": [],
            "group_by": [],
            "order_by": [],
            "limit": 5,
        },
        context=context,
        step_id=f"finance-query-{failure_code}:1",
    )

    assert observation.evidence == ()
    assert failure_code in observation.trace.detail
    assert observation.gaps == (expected_gap,)
    public_text = f"{observation.observation} {observation.trace.detail}"
    assert "fact_market_daily" not in public_text
    assert "physical sql" not in public_text


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


def _memory_frame() -> TaskFrame:
    return TaskFrame(
        raw_question="光刻胶，现在怎么看",
        user_goal="确认用户此前的判断与增量变化",
        question_type="stock_deep_dive",
        subject="光刻胶",
        subject_kind="concept",
        market_scope="A股",
        timeframe="当前",
        required_outputs=("direct_assessment",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="company_official_evidence",
        confidence=0.9,
    )


def _memory_fixture(tmp_path) -> Path:
    """Write a throwaway memory ledger.

    The real ledgers hold the user's private judgements, so every test points
    ``memory_users_root`` at a temp dir instead: nothing here reads or asserts
    on real content.
    """

    root = tmp_path / "users" / "fixture"
    root.mkdir(parents=True)
    (root / "judgments.jsonl").write_text(
        json.dumps(
            {
                "ts": "2026-07-01T10:00:00",
                "memo": "光刻胶国产替代要看客户验证进度，不看产能公告",
                "themes": ["光刻胶"],
                "stocks": [],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "corrections.jsonl").write_text(
        json.dumps(
            {
                "ts": "2026-07-02T10:00:00",
                "correction": "先看客户验证再谈弹性",
                "principle": "验证进度优先于产能规划",
                "themes": ["光刻胶"],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    # A record tagged only by ``stocks``: reachable through a company subject,
    # and deliberately scoring 0 against the theme-shaped queries above so the
    # existing recall counts stay unchanged.
    with (root / "judgments.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "ts": "2026-07-03T10:00:00",
                    "memo": "瑞华泰的PI膜产线要看良率爬坡",
                    "themes": [],
                    "stocks": ["瑞华泰"],
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    return root


def _memory_registry(
    tmp_path,
    *,
    users_root: Path | None,
    task_id: str,
    frame: TaskFrame | None = None,
):
    # task_id must be unique per test: root budgets are registered in a
    # process-wide live-episode table that rejects duplicate episode ids.
    frame = frame if frame is not None else _memory_frame()
    context = build_episode_context(
        frame,
        task_id=task_id,
        capabilities=("memory_lookup",),
        timeout=30.0,
    )
    return build_episode_registry(
        frame,
        context,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
        memory_users_root=users_root,
    ), context


def test_memory_lookup_recalls_user_judgements_as_prior_not_fact(tmp_path) -> None:
    """The agent can pull the user's own prior judgements as a tool call."""

    users_root = _memory_fixture(tmp_path)
    registry, context = _memory_registry(
        tmp_path,
        users_root=users_root,
        task_id="memory-lookup-recall",
    )

    assert "memory_lookup" in registry.names()
    result = registry.execute(
        "memory_lookup",
        "光刻胶，现在怎么看",
        context=context,
        step_id="memory-lookup-recall:1",
    )

    assert result.trace.status == "success"
    assert result.trace.result_count == 2
    assert result.gaps == ()
    details = [item.detail for item in result.evidence]
    assert any("客户验证进度" in detail for detail in details)
    assert any("验证进度优先于产能规划" in detail for detail in details)
    # Every atom must carry the dedicated tier, so downstream can tell this
    # apart from objective retrieval.
    assert {item.evidence_tier for item in result.evidence} == {"user_memory"}
    # The source label has to self-declare: it is the only semantics the model sees.
    assert all("非市场事实" in item.source for item in result.evidence)
    # Locators point at the fixture, never the real ledger.
    assert all(str(users_root) in item.internal_locator for item in result.evidence)


def test_memory_lookup_reports_empty_recall_instead_of_staying_silent(tmp_path) -> None:
    """No memory must be an explicit signal, not an empty success."""

    empty_root = tmp_path / "users" / "empty"
    empty_root.mkdir(parents=True)
    registry, context = _memory_registry(
        tmp_path,
        users_root=empty_root,
        task_id="memory-lookup-empty",
    )

    result = registry.execute(
        "memory_lookup",
        "光刻胶，现在怎么看",
        context=context,
        step_id="memory-lookup-empty:1",
    )

    assert result.evidence == ()
    assert result.trace.status == "empty"
    assert result.trace.result_count == 0
    assert "无相关命中" in result.observation
    assert result.gaps == ("用户记忆中没有与本题相关的历史判断",)


def test_memory_lookup_is_gated_by_allowed_capabilities(tmp_path) -> None:
    frame = _memory_frame()
    unauthorized = build_episode_context(
        frame,
        task_id="memory-unauthorized",
        capabilities=("market_data",),
        timeout=30.0,
    )
    registry = build_episode_registry(
        frame,
        unauthorized,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
        memory_users_root=_memory_fixture(tmp_path),
    )

    assert "memory_lookup" not in registry.names()


def test_memory_lookup_needs_identity_not_just_authorization(tmp_path) -> None:
    """授权到位但身份缺失时不注册——否则会读到别人的台账。

    这条锁的是隐私边界，不是「少一个能力」。`user_memory._ledger_paths` 在 ``user``
    与 ``users_root`` 都为 None 时回落 ``userspace.user_space(None)`` →
    ``resolve_user_id(None)`` → ``FORESIGHT_USER`` 或 ``"default"``。多用户服务端上
    那意味着**每个用户都去读 default 用户的私有判断**，而且读得「成功」：有召回、
    有证据、无报错，只是记录属于别人。

    所以它也顺带把「授权」和「身份穿透」焊成一件事：把 `_RUNTIME_CAPABILITY_FLOOR`
    里那三条 `memory_lookup` 加了、却没把 user_id 传到 `build_episode_registry`，
    工具依然不出现——不会出现「以为接好了、实际在串号」的中间态。

    变异验证：把 `memory_identity_resolved` 那个条件删掉，本条必红。
    """

    frame = _memory_frame()
    authorized = build_episode_context(
        frame,
        task_id="memory-authorized-without-identity",
        capabilities=("memory_lookup",),
        timeout=30.0,
    )

    registry = build_episode_registry(
        frame,
        authorized,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
        # 既不给 memory_user 也不给 memory_users_root：生产里忘了穿透身份的形状。
    )

    assert "memory_lookup" not in registry.names()


def test_memory_lookup_registers_once_identity_is_threaded(tmp_path) -> None:
    """给了 user_id（不给 users_root）就应注册：这是生产实际走的那条路。

    与上一条成对：上一条证明缺身份不注册，这条证明补上身份就通，两条一起才说明
    守卫拦的是「缺身份」而不是「把工具关掉了」。既有测试都走 ``memory_users_root``
    （临时 fixture 目录），没有一条覆盖生产用的 ``memory_user`` 分支。
    """

    frame = _memory_frame()
    authorized = build_episode_context(
        frame,
        task_id="memory-identity-threaded",
        capabilities=("memory_lookup",),
        timeout=30.0,
    )

    registry = build_episode_registry(
        frame,
        authorized,
        finance_root=tmp_path / "finance",
        knowledge_wiki=tmp_path / "wiki",
        l3_runner=None,
        memory_user="fixture-user",
    )

    assert "memory_lookup" in registry.names()


def test_memory_lookup_locator_never_reaches_the_outward_payload(tmp_path) -> None:
    """Ledger paths are control-plane only (mirrors test_agent_runtime.py:196)."""

    users_root = _memory_fixture(tmp_path)
    registry, context = _memory_registry(
        tmp_path,
        users_root=users_root,
        task_id="memory-lookup-locator",
    )

    result = registry.execute(
        "memory_lookup",
        "光刻胶，现在怎么看",
        context=context,
        step_id="memory-lookup-locator:1",
    )

    assert result.evidence
    for index, item in enumerate(result.evidence):
        payload = asdict(item.to_observation(f"M{index}"))
        assert "internal_locator" not in payload
        assert str(users_root) not in json.dumps(payload, ensure_ascii=False)


def test_memory_recall_intent_routes_tagged_kinds_through_one_parameter() -> None:
    """Kinds with ledger tags route; the rest pass nothing.

    ``theme`` is the only parameter used on purpose: ``_query_terms`` flattens
    ``theme`` and ``entity`` into one scored list, so a split would be a
    promise the recall code does not keep.
    """

    for kind in ("company", "concept", "theme"):
        assert episode_tools._memory_recall_intent("瑞华泰", kind) == {
            "theme": "瑞华泰"
        }
    # Kinds with no ledger tag counterpart must pass nothing: routing
    # "A股市场" as a theme would only add a noise term to every query.
    for kind in ("market_pattern", "index", "external_market", "unknown"):
        assert episode_tools._memory_recall_intent("A股市场", kind) == {}
    # Absent/blank subject and absent kind are both no-ops, never crashes.
    assert episode_tools._memory_recall_intent(None, "company") == {}
    assert episode_tools._memory_recall_intent("   ", "company") == {}
    assert episode_tools._memory_recall_intent("光刻胶", None) == {}


def test_memory_recall_intent_refuses_subjects_too_short_to_discriminate() -> None:
    """A 1-char subject substring-matches most tags, so it must not route.

    ``select_relevant`` compares against one joined tag string, so recall
    breadth is driven by how general the routed term is, not by its kind.
    ``_query_terms`` already drops sub-2-char query tokens; a routed subject
    gets held to the same floor.
    """

    assert episode_tools._memory_recall_intent("股", "theme") == {}
    assert episode_tools._memory_recall_intent("A", "company") == {}
    assert episode_tools._memory_recall_intent(" 股 ", "theme") == {}
    # Two chars is the floor, not an exclusion: "AI" is a real theme subject.
    # It stays broad against substring matching, which is why a recall eval has
    # to record the routed subject rather than trust the kind alone.
    assert episode_tools._memory_recall_intent("AI", "theme") == {"theme": "AI"}


def test_memory_lookup_recalls_through_contract_subject_when_query_omits_it(
    tmp_path,
) -> None:
    """A follow-up that never repeats the subject must still reach the ledger.

    This is the whole point of the structured-intent hop: the tool query is
    whatever the model typed, so on "那还能追吗" the ledger's ``themes`` tags
    are unreachable unless the resolved subject is passed in alongside it.
    """

    users_root = _memory_fixture(tmp_path)
    followup = "那还能追吗"

    # Control: the query alone carries no term overlapping the ledger.
    assert (
        user_memory.relevant_memory_records(followup, users_root=users_root).total == 0
    )

    registry, context = _memory_registry(
        tmp_path,
        users_root=users_root,
        task_id="memory-lookup-contract-subject",
    )
    result = registry.execute(
        "memory_lookup",
        followup,
        context=context,
        step_id="memory-lookup-contract-subject:1",
    )

    assert result.trace.status == "success"
    assert result.trace.result_count == 2
    details = [item.detail for item in result.evidence]
    assert any("客户验证进度" in detail for detail in details)
    assert any("验证进度优先于产能规划" in detail for detail in details)
    # The stock-tagged record belongs to another subject and must stay out.
    assert not any("良率爬坡" in detail for detail in details)


def test_memory_lookup_company_subject_recalls_only_its_own_records(
    tmp_path,
) -> None:
    """A company subject recalls its own records and nothing else.

    Deliberately not asserted here: *which* tag field matched.  ``theme`` and
    ``entity`` are flattened into one term list by ``_query_terms``, so a test
    claiming "reaches the stocks tags" would pass under either parameter and
    prove nothing.  What is worth pinning is the subject-level partition.
    """

    users_root = _memory_fixture(tmp_path)
    company_frame = replace(
        _memory_frame(),
        raw_question="现在还能追吗",
        subject="瑞华泰",
        subject_kind="company",
    )
    registry, context = _memory_registry(
        tmp_path,
        users_root=users_root,
        task_id="memory-lookup-company-subject",
        frame=company_frame,
    )

    result = registry.execute(
        "memory_lookup",
        "现在还能追吗",
        context=context,
        step_id="memory-lookup-company-subject:1",
    )

    assert result.trace.status == "success"
    details = [item.detail for item in result.evidence]
    assert any("良率爬坡" in detail for detail in details)
    # The unrelated theme-tagged records must not ride along.
    assert not any("客户验证进度" in detail for detail in details)


def test_memory_lookup_unmapped_subject_kind_adds_no_recall_terms(
    tmp_path,
) -> None:
    """market_pattern subjects must not widen recall (guards false positives)."""

    users_root = _memory_fixture(tmp_path)
    market_frame = replace(
        _memory_frame(),
        raw_question="大盘还能反弹多久",
        subject="A股市场",
        subject_kind="market_pattern",
    )
    registry, context = _memory_registry(
        tmp_path,
        users_root=users_root,
        task_id="memory-lookup-market-subject",
        frame=market_frame,
    )

    result = registry.execute(
        "memory_lookup",
        "大盘还能反弹多久",
        context=context,
        step_id="memory-lookup-market-subject:1",
    )

    assert result.evidence == ()
    assert result.trace.status == "empty"
    assert result.gaps == ("用户记忆中没有与本题相关的历史判断",)


def test_memory_recall_binds_into_prior_recall_through_the_real_episode_loop(
    tmp_path,
) -> None:
    """整条链跑一遍真实 episode 循环：注册 → 调用 → 召回 → 绑进 prior_recall。

    在这条之前，`memory_lookup` 的证据只被单独执行验证过（``registry.execute``），
    而 `prior_recall` 槽位只被单独验证过存在于契约里。两件事各自成立不等于链路通：
    中间还隔着 `validate_episode_finish` 的 basis 校验、evidence hash 白名单、以及
    registry 自动补 ``content_hash``（research_tool_registry.py:533）——工具 runner
    自己并不设 hash，如果那一步没补上，绑定会因「unknown evidence hash」被拒。

    这里唯一被替换掉的是模型的自由选择（``ScriptedModel`` 直接发起 memory_lookup
    调用）。工具执行、证据落账、hash 补齐、终止校验全部走生产代码，所以它能验证
    「模型一旦选择调用，后面每一步都接得住」，而不需要一个可用的 LLM 网关。

    仍然验不到的那一格：真实模型会不会**主动**选这个工具。那需要真实 provider。
    """

    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.services.agent_runtime import ModelToolCall, ModelTurn

    users_root = _memory_fixture(tmp_path)
    # 触发 prior_recall 注入需要两个条件同时成立：问题引用了自己过去的看法，
    # 且题型属于「用户可能对该主体表达过看法」的那三类。
    frame = replace(
        _memory_frame(),
        raw_question="光刻胶我之前的判断还成立吗",
        user_goal="确认用户此前的判断与增量变化",
    )
    registry, context = _memory_registry(
        tmp_path,
        users_root=users_root,
        task_id="memory-prior-recall-episode",
        frame=frame,
    )

    prior_recall = next(
        (
            item
            for item in context.contract.required_outputs
            if item.output_id == "prior_recall"
        ),
        None,
    )
    assert prior_recall is not None, "契约里没有 prior_recall，召回结果无处可绑"
    assert prior_recall.grounding_mode == "user_premise"

    # 先单独执行一次，拿到 registry 补出来的真实 content_hash。
    # ``evidence_content_hash`` 只取 (tool, title, detail, source)，与查询串无关，
    # 所以下面 episode 内再次执行同一工具会得到同一个 hash——不必把 hash 或证据
    # 字段硬编进测试，也就不会在 runner 措辞改动时假红。
    probe = registry.execute(
        "memory_lookup",
        "光刻胶 我之前怎么判断的",
        context=context,
        step_id="memory-prior-recall-episode:probe",
    )
    recalled_hashes = [item.content_hash for item in probe.evidence]
    assert recalled_hashes, "fixture 台账没被召回，后面的绑定断言会失去意义"

    model = ScriptedEpisodeModel(
        [
            ModelTurn(
                "",
                (
                    ModelToolCall(
                        "call-1",
                        "memory_lookup",
                        {"query": "光刻胶 我之前怎么判断的"},
                    ),
                ),
                "scripted",
                "",
            ),
            _prior_recall_finish_turn(recalled_hashes),
        ]
    )

    outcome = ContinuousAgentEpisode(model).run(
        task_frame=frame,
        context=context,
        registry=registry,
    )

    # 1. 工具真的被执行了，证据来自 memory_lookup
    memory_evidence = [
        item for item in outcome.evidence if item.tool == "memory_lookup"
    ]
    assert memory_evidence, "memory_lookup 没有产出证据"
    # registry 自动补的 hash——没有它，下面的绑定会被判 unknown evidence hash
    assert all(item.content_hash for item in memory_evidence)

    # 0 号 model 调用：model_turn 之前 episode 要把工具清单传给模型。
    # 「memory_lookup 出现在 tools 里」是模型能看见它的必要条件——
    # 这一格验的是「注册到 registry → 工具描述到达模型」的最后一段传输。
    assert model.calls, "ScriptedModel 从未被调用，测试没有跑起来"
    first_call_tool_names = {t.get("function", {}).get("name") for t in model.calls[0]["tools"]}
    assert "memory_lookup" in first_call_tool_names, (
        "memory_lookup 没有出现在发给模型的 tools 列表里——"
        "即使注册成功，模型也会像盲人一样看不见它"
    )

    # 2. 先验绑进了 prior_recall，且 basis 是 user_premise
    binding = next(
        (item for item in outcome.bindings if item.output_id == "prior_recall"),
        None,
    )
    assert binding is not None, "召回成功却没绑进 prior_recall——链路断在终止校验"
    assert binding.basis == "user_premise"
    assert binding.evidence_hashes, "prior_recall 绑了空证据，等于没接上"
    assert set(binding.evidence_hashes) <= {
        item.content_hash for item in memory_evidence
    }

    # 3. 先验不得外泄台账路径（控制面字段）
    assert all(str(users_root) not in outcome.draft for _ in (0,))


class ScriptedEpisodeModel:
    """Minimal model double: replays a fixed turn sequence.

    Mirrors ``test_agent_episode.ScriptedModel``; duplicated here instead of
    imported so this file keeps owning its own fixtures.
    """

    def __init__(self, turns) -> None:
        self._turns = iter(turns)
        self.calls: list[dict[str, object]] = []

    def complete(self, *, messages, tools, timeout):
        self.calls.append({"tools": [*tools], "timeout": timeout})
        return next(self._turns)


def _prior_recall_finish_turn(recalled_hashes):
    """Finish with the prior bound to ``prior_recall`` and the answer left open.

    ``status="partial"`` is deliberate.  ``direct_assessment`` is an evidence
    slot and this run only ever retrieved the user's own prior, which by
    contract is not market evidence.  Claiming ``completed`` here would need
    the memory records to prop up an evidence slot — exactly what the tool
    description forbids — so the honest shape is: prior bound, answer still
    owing market evidence.
    """

    from intelligence.services.agent_runtime import ModelTurn

    return ModelTurn(
        json.dumps(
            {
                "status": "partial",
                "draft": (
                    "你此前的判断是看客户验证进度而不是产能公告；"
                    "本轮尚未取得可核验的当前市场证据，先不改动结论。"
                ),
                "gaps": ["缺少当前市场证据"],
                "bindings": [
                    {
                        "output_id": "prior_recall",
                        "evidence_hashes": recalled_hashes,
                        "gap": "",
                        "basis": "user_premise",
                    },
                    {
                        "output_id": "direct_assessment",
                        "evidence_hashes": [],
                        "gap": "缺少当前市场证据",
                        "basis": "evidence",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        (),
        "scripted",
        "",
    )


class TestAgentFinanceSchemaTellsTheTruth:
    """schema 广告的行数上限必须等于真正执行的那个上限。

    2026-08-12 修的保真性缺口：``FINANCE_QUERY_PARAMETERS`` 的 limit.maximum 是
    1000（查询引擎的通用上限），而 Agent 路径 ``min(normalized.limit, 25)``。
    模型按 schema 以为能取 1000 行，实际永远 25 行，且只在**拿到结果之后**才由
    observation 补一句「已截断」。

    历史 run 实测：189 次 finance_query 调用里 55 次（约 29%）要的行数超过 25，
    其中 8 次逐字写了 schema 广告的 1000。ai-agent-book ch4「参数传递的保真性」：
    模型感知到的世界与工具操作的世界之间不能存在系统性偏差。

    与 ``test_tool_behavior_contract.py`` 里那些契约断言不同，**这一条是硬不变量**：
    契约那边刻意不做全覆盖门禁（会逼人编一句），而「schema 说的 = 执行的」两边
    都是机器可读的数，等式要么成立要么不成立，没有编造空间。
    """

    def test_agent_finance_schema_limit_matches_enforced_cap(self) -> None:
        parameters = episode_tools._agent_finance_parameters()

        advertised = parameters["properties"]["limit"]["maximum"]

        assert advertised == episode_tools._AGENT_FINANCE_QUERY_MAX_ROWS

    def test_agent_schema_does_not_mutate_the_shared_engine_schema(self) -> None:
        """引擎那份是通用的（别的调用方上限本就更高），不能被 Agent 侧就地改掉。"""
        before = finance_query.FINANCE_QUERY_PARAMETERS["properties"]["limit"]["maximum"]

        episode_tools._agent_finance_parameters()

        after = finance_query.FINANCE_QUERY_PARAMETERS["properties"]["limit"]["maximum"]
        assert before == after
        assert after > episode_tools._AGENT_FINANCE_QUERY_MAX_ROWS

    def test_limit_description_states_the_cap_is_hard(self) -> None:
        """光把 maximum 调小不够——模型会以为「写 25 就能拿 25」而不知道该改查法。

        ch4 §工具描述的艺术：清晰列出边界（做不到什么）比描述能力更重要。
        """
        description = episode_tools._agent_finance_parameters()["properties"]["limit"][
            "description"
        ]

        assert str(episode_tools._AGENT_FINANCE_QUERY_MAX_ROWS) in description
        assert "硬上限" in description
