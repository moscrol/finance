"""Composition root for the continuous episode's existing finance tools.

No provider is reimplemented here. The factory wraps the same KB RAG, graph,
evidence-index, DuckDB blocks, and deterministic technical calculator already
used by the Workbench, then exposes them through ``ResearchToolRegistry``.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import time

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.paths import default_paths
from intelligence.services import (
    agent_research,
    ask_blocks,
    entity_anchor,
    evidence_search,
    finance_query,
    kb_rag,
    l3_evidence,
    market_technical,
    valuation_estimate,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
    ToolSpec,
    ToolRunResult,
    default_registry,
)
from intelligence.services.task_frame import TaskFrame


_FAST_PATH_TYPES = frozenset(
    {"market_technical", "external_market", "quick_fact", "dated_market_review"}
)
_NON_EVIDENCE_PREFIXES = (
    "使用边界：",
    "因果使用要求：",
    "使用要求：",
    "⚠",
)
_OFFICIAL_L3_RUNNER = object()
_DEFAULT_EVIDENCE_SEARCH_JUDGE = object()
_AGENT_FINANCE_QUERY_MAX_ROWS = 25


def is_deterministic_fast_path(frame: TaskFrame) -> bool:
    return frame.question_type in _FAST_PATH_TYPES


def _roots(
    finance_root: str | Path | None,
    knowledge_wiki: str | Path | None,
) -> tuple[Path, Path]:
    paths = default_paths()
    return (
        Path(finance_root).expanduser() if finance_root else paths.finance_root,
        Path(knowledge_wiki).expanduser() if knowledge_wiki else paths.knowledge_wiki,
    )


def latest_market_date(finance_root: str | Path | None = None) -> str | None:
    finance, _wiki = _roots(finance_root, None)
    return ask_blocks._market_data_asof(  # noqa: SLF001 - public factory seam
        finance / "db" / "market_feature_store.duckdb"
    )


def _market_block(
    frame: TaskFrame,
    context: ResearchRunContext,
    market_db_path: Path,
) -> tuple[str, str, str]:
    if frame.question_type == "market_forecast":
        block = "\n".join(
            part
            for part in (
                ask_blocks._daily_market_overview_block_for_llm(market_db_path),
                ask_blocks._market_cause_window_block_for_llm(market_db_path),
            )
            if part
        )
        return block, "本地 DuckDB · 预测盘面窗口", "market_forecast_window"
    if frame.question_type == "market_cause":
        return (
            ask_blocks._market_cause_window_block_for_llm(market_db_path),
            "本地 DuckDB · 周内市场归因窗口",
            "market_cause_window",
        )
    if frame.question_type == "valuation_estimate":
        timeout = context.deadline.stage_timeout(6.0)
        if timeout <= 0.001:
            raise TimeoutError("valuation market-data deadline expired")

        def fetch_snapshot(code: str, name: str = ""):
            return valuation_estimate.fetch_eastmoney_snapshot(
                code,
                name,
                timeout=min(timeout, context.deadline.stage_timeout(timeout)),
            )

        return (
            ask_blocks._valuation_block_for_llm(
                frame.raw_question,
                frame.subject,
                market_db_path,
                fetcher=fetch_snapshot,
            ),
            "东财快照 + 本地 DuckDB 可比集",
            "company_valuation_snapshot",
        )
    return (
        ask_blocks._daily_market_overview_block_for_llm(market_db_path),
        "本地 DuckDB · MARKET_DAILY 市场总览",
        "market_overview",
    )


def build_episode_registry(
    frame: TaskFrame,
    context: ResearchRunContext,
    *,
    finance_root: str | Path | None = None,
    knowledge_wiki: str | Path | None = None,
    l3_runner: agent_research.ToolRunner | None | object = _OFFICIAL_L3_RUNNER,
    evidence_search_judge: evidence_search.SemanticJudge | None | object = (
        _DEFAULT_EVIDENCE_SEARCH_JUDGE
    ),
) -> ResearchToolRegistry:
    """Build a read-only registry from the repository's current tool runners."""

    finance, wiki = _roots(finance_root, knowledge_wiki)
    market_db_path = finance / "db" / "market_feature_store.duckdb"
    structured_source_date = None
    if frame.question_type != "valuation_estimate":
        structured_source_date = (
            context.latest_data_date
            or ask_blocks._market_data_asof(  # noqa: SLF001
                market_db_path
            )
        )
    knowledge = KnowledgeAdapter(wiki_root=wiki)

    def retrieve_kb(query: str, timeout: float):
        return kb_rag.retrieve(
            query,
            wiki,
            k=6,
            mode="hybrid",
            timeout=min(timeout, 30.0),
            excerpt_chars=240,
            budget_query=frame.raw_question,
            require_fresh=True,
            cache_scope=context.contract.task_id,
        )

    tools = {
        **agent_research.build_default_tools(retrieve_kb),
        **agent_research.build_graph_tools(knowledge),
    }

    def market_data_runner(
        _query: str,
        tool_context: agent_research.AgentToolContext,
    ):
        tool_context.check_cancelled()
        if tool_context.deadline.expired:
            raise TimeoutError("market-data deadline expired")
        block, source, detail = _market_block(frame, context, market_db_path)
        tool_context.check_cancelled()
        evidence, observation = agent_research.block_lines_to_evidence(
            "market_data",
            block,
            source,
            limit=18,
            detail_chars=1000,
            source_date=structured_source_date,
        )
        evidence = [
            item
            for item in evidence
            if not item.detail.startswith(_NON_EVIDENCE_PREFIXES)
        ]
        return (
            evidence,
            observation or "结构化行情无可用结果",
            ProviderTrace(
                provider="agent:market_data",
                capability="market_data",
                status="success" if evidence else "empty",
                detail=detail,
                result_count=len(evidence),
            ),
        )

    def financial_data_runner(
        _query: str,
        tool_context: agent_research.AgentToolContext,
    ):
        tool_context.check_cancelled()
        timeout = tool_context.deadline.stage_timeout(8.0)
        if timeout <= 0.001:
            raise TimeoutError("financial-data deadline expired")
        block = ask_blocks._financials_block_for_llm(
            f"{frame.subject} {frame.raw_question}",
            market_db_path,
            timeout=timeout,
        )
        tool_context.check_cancelled()
        evidence, observation = agent_research.block_lines_to_evidence(
            "financial_data",
            block,
            "东财 F10 / AKShare · D7 逐季财报",
            limit=12,
            detail_chars=1000,
        )
        evidence = [
            item
            for item in evidence
            if not item.detail.startswith(_NON_EVIDENCE_PREFIXES)
        ]
        return (
            evidence,
            observation or "逐季财务指标无可用结果",
            ProviderTrace(
                provider="agent:financial_data",
                capability="financial_data",
                status="success" if evidence else "empty",
                detail="quarterly_financials_snapshot",
                result_count=len(evidence),
            ),
        )

    def mainline_runner(
        _query: str,
        tool_context: agent_research.AgentToolContext,
    ):
        tool_context.check_cancelled()
        if tool_context.deadline.expired:
            raise TimeoutError("mainline-context deadline expired")
        block = ask_blocks._market_review_mainline_context_block_for_llm(
            frame.raw_question,
            frame.subject,
            market_db_path,
        )
        tool_context.check_cancelled()
        if not block or "当前交易日的题材级主线未知" in block:
            evidence = []
            observation = block or "同日主线结构无可用数据"
        else:
            evidence, observation = agent_research.block_lines_to_evidence(
                "mainline_context",
                block,
                "本地 DuckDB · D4 同日主线结构",
                limit=12,
                detail_chars=1000,
                source_date=structured_source_date,
            )
            evidence = [
                item
                for item in evidence
                if not item.detail.startswith(_NON_EVIDENCE_PREFIXES)
            ]
        return (
            evidence,
            observation,
            ProviderTrace(
                provider="agent:mainline_context",
                capability="mainline_context",
                status="success" if evidence else "empty",
                detail="current_mainline_context",
                result_count=len(evidence),
            ),
        )

    def official_l3_runner(
        query: str,
        tool_context: agent_research.AgentToolContext,
    ):
        tool_context.check_cancelled()
        timeout = tool_context.deadline.stage_timeout(30.0)
        if timeout <= 0.001:
            raise TimeoutError("l3 lookup deadline expired")
        bundle = l3_evidence.lookup_l3_company(
            query,
            config=l3_evidence.L3LookupConfig.from_env(
                enabled=True,
                timeout=max(1, int(timeout)),
                limit=5,
            ),
        )
        tool_context.check_cancelled()
        evidence = [
            agent_research.AgentEvidence(
                tool="l3_lookup",
                title=item.title,
                detail=item.summary,
                source=item.citation or item.source_type,
                evidence_tier="L3",
                freshness="current",
            )
            for item in bundle.items
        ]
        providers = tuple(dict.fromkeys(item.source_type for item in bundle.items))
        return (
            evidence,
            bundle.to_prompt_block(),
            ProviderTrace(
                provider="+".join(providers) or "l3_lookup",
                capability="l3_lookup",
                status="success" if evidence else "empty",
                detail="；".join(bundle.warnings) or "official disclosure lookup",
                result_count=len(evidence),
            ),
        )

    if "market_data" in context.contract.allowed_capabilities:
        tools["market_data"] = market_data_runner
    if "financial_data" in context.contract.allowed_capabilities:
        tools["financial_data"] = financial_data_runner
    if "mainline_context" in context.contract.allowed_capabilities:
        tools["mainline_context"] = mainline_runner
    selected_l3_runner = (
        official_l3_runner if l3_runner is _OFFICIAL_L3_RUNNER else l3_runner
    )
    if "l3_lookup" in context.contract.allowed_capabilities and callable(
        selected_l3_runner
    ):
        tools["l3_lookup"] = selected_l3_runner
    base_registry = default_registry(tools)
    specs = list(base_registry.authorized_specs())

    if "finance_query" in context.contract.allowed_capabilities:
        # The semantic query engine also serves non-agent callers that may
        # legitimately export wider tables.  The Episode seam is different:
        # every returned atom is replayed into later model turns and verifier
        # input, so a 100-row result can multiply into a six-figure prompt.
        # Keep the general engine flexible while bounding this model-facing
        # observation surface.  The model can refine filters/order and query
        # again when it genuinely needs another slice.
        query_engine = finance_query.FinanceQuery(market_db_path)

        def parse_finance_arguments(arguments):
            spec = finance_query.FinanceQuerySpec.from_arguments(arguments)
            selected = ",".join((*spec.dimensions, *spec.metrics))
            return spec, f"{spec.dataset}:{selected}"

        def finance_query_runner(
            value: object,
            tool_context: agent_research.AgentToolContext,
        ):
            if not isinstance(value, finance_query.FinanceQuerySpec):
                raise finance_query.FinanceQueryValidationError(
                    "finance query input was not parsed"
                )
            bounded_value = replace(
                value,
                limit=min(value.limit, _AGENT_FINANCE_QUERY_MAX_ROWS),
            )
            try:
                result = query_engine.run(
                    bounded_value,
                    information_cutoff=context.information_cutoff,
                    deadline=tool_context.deadline,
                    is_cancelled=tool_context.is_cancelled,
                )
            except finance_query.FinanceQueryError as exc:
                return _finance_query_failure_result(value, exc)
            gaps = (
                ()
                if result.evidence
                else (f"{value.dataset} 在指定条件与时点内没有结构化结果",)
            )
            observation = result.observation
            if (
                value.limit > result.audit.applied_limit
                and result.audit.row_count >= result.audit.applied_limit
            ):
                observation = (
                    f"{observation}；查询结果已按 Agent 上下文预算截断至 "
                    f"{result.audit.applied_limit} 条；如需更多，请增加筛选、"
                    "分组或排序后继续查询"
                )
            return ToolRunResult(
                evidence=tuple(result.evidence),
                observation=observation,
                trace=ProviderTrace(
                    provider="duckdb_semantic_query",
                    capability="finance_query",
                    status="success" if result.evidence else "empty",
                    detail=(
                        f"dataset={value.dataset}; rows={len(result.evidence)}; "
                        f"fingerprint={result.audit.sql_fingerprint}"
                    ),
                    source_trade_date=result.served_date,
                    result_count=len(result.evidence),
                ),
                gaps=gaps,
            )

        specs.append(
            ToolSpec(
                name="finance_query",
                capability="finance_query",
                description=(
                    "查询本地结构化金融数据。dataset 可选 market_daily、"
                    "stock_daily、sector_daily、sector_stock_daily、"
                    "mainline_theme_daily、mainline_sector_daily；由你选择"
                    "指标、维度、筛选、分组、排序和时间范围。字段必须按"
                    "dataset 对应关系选择，不要混用不同 dataset 的字段。"
                    f"可用字段：{finance_query.dataset_field_hint()}"
                ),
                cost="local",
                freshness="current",
                runner=finance_query_runner,
                parameters=finance_query.FINANCE_QUERY_PARAMETERS,
                parse_arguments=parse_finance_arguments,
            )
        )

    if "evidence_search" in context.contract.allowed_capabilities:
        selected_judge = (
            evidence_search.default_semantic_judge
            if evidence_search_judge is _DEFAULT_EVIDENCE_SEARCH_JUDGE
            else evidence_search_judge
        )

        def evidence_search_runner(
            query: str,
            tool_context: agent_research.AgentToolContext,
        ):
            def retrieve_for_search(candidate: str):
                return retrieve_kb(candidate, tool_context.timeout(30.0))

            search = evidence_search.EvidenceSearch(
                retrieve_for_search,
                semantic_judge=(selected_judge if callable(selected_judge) else None),
            )
            result = search.search(
                query=query,
                anchor=entity_anchor.resolve_entity_anchor(query, knowledge),
                information_cutoff=context.information_cutoff,
                deadline=tool_context.deadline,
            )
            return ToolRunResult(
                evidence=tuple(result.evidence),
                observation=result.observation,
                trace=result.trace,
                gaps=result.gaps,
            )

        specs.append(
            ToolSpec(
                name="evidence_search",
                capability="evidence_search",
                description=(
                    "对本地知识证据执行 narrow→broad→counter 闭环检索，"
                    "适合验证公司、题材、产业链关系、反证和替代解释。"
                ),
                cost="local",
                freshness="current",
                runner=evidence_search_runner,
            )
        )

    return ResearchToolRegistry(tuple(specs))


def _finance_query_failure_result(
    spec: finance_query.FinanceQuerySpec,
    error: finance_query.FinanceQueryError,
) -> ToolRunResult:
    if isinstance(error, finance_query.FinanceQueryValidationError):
        failure_code = "invalid_query"
        status = "parse_error"
        observation = (
            f"结构化查询参数无效：{str(error)[:160]}；重试提示："
            f"{finance_query.validation_retry_hint(spec, error)}"
        )
        gap = "结构化查询条件无效；请改写 dataset、字段、筛选或日期范围后重试"
    elif isinstance(error, finance_query.FinanceQueryTimedOut):
        failure_code = "timeout"
        status = "request_error"
        observation = "结构化查询超时，未返回可发布的数据"
        gap = "结构化查询超时；请缩小时间范围、字段或结果数量后重试"
    elif isinstance(error, finance_query.FinanceQueryCancelled):
        failure_code = "cancelled"
        status = "request_error"
        observation = "结构化查询已取消，未返回可发布的数据"
        gap = "结构化查询被取消；如任务仍需该数据，请重新发起更窄的查询"
    elif isinstance(error, finance_query.FinanceQueryLimitExceeded):
        failure_code = "limit_exceeded"
        status = "request_error"
        observation = "结构化查询结果超过资源上限，未返回截断数据"
        gap = "结构化查询结果超过资源上限；请缩小时间范围、字段或结果数量后重试"
    else:
        failure_code = "request_error"
        status = "request_error"
        observation = "结构化数据源暂不可用，未返回可发布的数据"
        gap = "结构化数据源暂不可用；当前答案仍缺少该查询对应的数据"
    return ToolRunResult(
        evidence=(),
        observation=observation,
        trace=ProviderTrace(
            provider="duckdb_semantic_query",
            capability="finance_query",
            status=status,
            detail=f"dataset={spec.dataset}; failure={failure_code}",
            result_count=0,
        ),
        gaps=(gap,),
    )


def run_deterministic_fast_path(
    frame: TaskFrame,
    *,
    timeout: float,
) -> dict[str, object]:
    """Execute a preserved deterministic lane without entering AgentEpisode."""

    started = time.monotonic()
    if frame.question_type != "market_technical":
        return {
            "execution_kind": "deterministic_fast_path",
            "status": "partial",
            "answer": "该确定性旁路尚未接入本次 A/B runner。",
            "gaps": [f"unsupported fast path: {frame.question_type}"],
            "traces": [],
            "latency": round(time.monotonic() - started, 4),
            "llm_calls": 0,
            "tool_calls": 0,
        }
    bounded_timeout = min(max(0.0, float(timeout)), 15.0)
    if bounded_timeout <= 0.0:
        return {
            "execution_kind": "deterministic_fast_path",
            "status": "failed",
            "answer": "",
            "gaps": ["deterministic fast path deadline exhausted"],
            "traces": [],
            "latency": round(time.monotonic() - started, 4),
            "llm_calls": 0,
            "tool_calls": 0,
        }
    outcome = market_technical.resolve_market_technical(
        frame.raw_question,
        timeout=bounded_timeout,
    )
    if isinstance(outcome, market_technical.TechnicalGap):
        return {
            "execution_kind": "deterministic_fast_path",
            "status": "partial",
            "answer": market_technical.gap_answer_text(outcome),
            "gaps": [outcome.reason],
            "traces": [
                ProviderTrace(
                    provider="tencent_kline",
                    capability="market_data",
                    status="empty",
                    detail=outcome.reason,
                ).to_dict()
            ],
            "latency": round(time.monotonic() - started, 4),
            "llm_calls": 0,
            "tool_calls": 1,
        }

    resistance_parts = []
    for level in outcome.resistances:
        low_pct = (level.zone_low / outcome.close - 1) * 100
        high_pct = (level.zone_high / outcome.close - 1) * 100
        zone = (
            f"{level.zone_low:.2f}"
            if abs(level.zone_high - level.zone_low) < 1e-9
            else f"{level.zone_low:.2f}–{level.zone_high:.2f}"
        )
        distance = (
            f"{low_pct:.1f}%"
            if abs(level.zone_high - level.zone_low) < 1e-9
            else f"{low_pct:.1f}%–{high_pct:.1f}%"
        )
        resistance_parts.append(f"{zone}（距收盘约 {distance}）")
    support_parts = [
        (
            f"{level.zone_low:.2f}"
            if abs(level.zone_high - level.zone_low) < 1e-9
            else f"{level.zone_low:.2f}–{level.zone_high:.2f}"
        )
        for level in outcome.supports
    ]
    answer = (
        f"截至 {outcome.as_of}，{outcome.subject}收盘 {outcome.close:.2f}。"
        f"按近期日线结构，反弹空间先看上方压力区："
        f"{'；'.join(resistance_parts) or '当前没有高于收盘的可靠压力候选'}。"
        f"下方支撑为：{'；'.join(support_parts) or '暂无可靠支撑候选'}。"
        f"{outcome.invalidation}"
    )
    return {
        "execution_kind": "deterministic_fast_path",
        "status": "completed",
        "answer": answer,
        "gaps": list(outcome.warnings),
        "traces": [
            ProviderTrace(
                provider="tencent_kline",
                capability="market_data",
                status="success",
                source_trade_date=outcome.as_of,
                result_count=len(outcome.supports) + len(outcome.resistances),
            ).to_dict()
        ],
        "latency": round(time.monotonic() - started, 4),
        "llm_calls": 0,
        "tool_calls": 1,
    }


__all__ = [
    "build_episode_registry",
    "is_deterministic_fast_path",
    "latest_market_date",
    "run_deterministic_fast_path",
]
