"""Composition root for the continuous episode's existing finance tools.

No provider is reimplemented here. The factory wraps the same KB RAG, graph,
evidence-index, DuckDB blocks, and deterministic technical calculator already
used by the Workbench, then exposes them through ``ResearchToolRegistry``.
"""

from __future__ import annotations

from pathlib import Path
import time

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.paths import default_paths
from intelligence.services import (
    agent_research,
    ask_blocks,
    kb_rag,
    l3_evidence,
    market_technical,
    valuation_estimate,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
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
        if tool_context.deadline.expired:
            raise TimeoutError("market-data deadline expired")
        block, source, detail = _market_block(frame, context, market_db_path)
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

    def mainline_runner(
        _query: str,
        tool_context: agent_research.AgentToolContext,
    ):
        if tool_context.deadline.expired:
            raise TimeoutError("mainline-context deadline expired")
        block = ask_blocks._market_review_mainline_context_block_for_llm(
            frame.raw_question,
            frame.subject,
            market_db_path,
        )
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
    if "mainline_context" in context.contract.allowed_capabilities:
        tools["mainline_context"] = mainline_runner
    selected_l3_runner = (
        official_l3_runner if l3_runner is _OFFICIAL_L3_RUNNER else l3_runner
    )
    if "l3_lookup" in context.contract.allowed_capabilities and callable(
        selected_l3_runner
    ):
        tools["l3_lookup"] = selected_l3_runner
    return default_registry(tools)


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
            else f"{level.zone_low:.2f}~{level.zone_high:.2f}"
        )
        distance = (
            f"{low_pct:.1f}%"
            if abs(level.zone_high - level.zone_low) < 1e-9
            else f"{low_pct:.1f}%~{high_pct:.1f}%"
        )
        resistance_parts.append(f"{zone}（距收盘约 {distance}）")
    support_parts = [
        (
            f"{level.zone_low:.2f}"
            if abs(level.zone_high - level.zone_low) < 1e-9
            else f"{level.zone_low:.2f}~{level.zone_high:.2f}"
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
