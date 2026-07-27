from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pytest

from intelligence.services import episode_tools, finance_query, l3_evidence
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
    assert definitions["evidence_search"] == {
        "type": "object",
        "properties": {"query": {"type": "string", "minLength": 1}},
        "required": ["query"],
        "additionalProperties": False,
    }

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


def test_finance_query_date_filter_points_to_time_range(tmp_path: Path) -> None:
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

    assert observation.trace.status == "parse_error"
    assert "time_range.start/time_range.end" in observation.observation
    assert "日期不要放入 filters" in observation.observation


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
