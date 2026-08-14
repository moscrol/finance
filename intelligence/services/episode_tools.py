"""Composition root for the continuous episode's existing finance tools.

No provider is reimplemented here. The factory wraps the same KB RAG, graph,
evidence-index, DuckDB blocks, and deterministic technical calculator already
used by the Workbench, then exposes them through ``ResearchToolRegistry``.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from datetime import date, timedelta
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
    market_news,
    market_technical,
    user_memory,
    valuation_estimate,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    InformationCutoff,
    ResearchRunContext,
)
from intelligence.services.research_tool_registry import (
    PreparedToolArguments,
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


def _agent_finance_parameters() -> dict[str, object]:
    """把 Agent 侧的真实行数上限**写进 schema**，而不是只写在契约散文里。

    保真性缺口（2026-08-12 实测修复）：``FINANCE_QUERY_PARAMETERS`` 的
    ``limit.maximum`` 是 1000（那是查询引擎的通用上限），但 Agent 路径在
    ``finance_query_runner`` 里 ``min(normalized.limit, 25)``。于是模型按 schema
    以为能取 1000 行，实际永远只有 25 行，且**只在拿到结果之后**才由 observation
    补一句「已截断」——下单时它不知道。

    这不是理论风险。历史 run 里模型写出的 limit 分布：20(72) 10(43) 30(18)
    100(16) 15(16) 200(13) **1000(8)** 5(3) —— **189 次调用里 55 次（约 29%）
    要的行数超过工具能给的上限**，其中 8 次逐字写了 schema 广告的 1000。
    ai-agent-book ch4 那条底线说的就是这个：模型感知到的世界与工具操作的世界
    之间不能存在系统性偏差。

    **上限从 ``_AGENT_FINANCE_QUERY_MAX_ROWS`` 生成，不手抄**（BUILD 模式 6）：
    手抄的数会和真正执行的那个常数分叉，而分叉时没有任何门禁会发红。
    ``test_agent_finance_schema_limit_matches_enforced_cap`` 钉住这条等式。
    """

    parameters = copy.deepcopy(finance_query.FINANCE_QUERY_PARAMETERS)
    properties = parameters["properties"]
    assert isinstance(properties, dict)
    properties["limit"] = {
        **properties["limit"],
        "maximum": _AGENT_FINANCE_QUERY_MAX_ROWS,
        # 限定语排在被限定内容之前（BUILD 模式 4）：先说上限是硬的，再说怎么办。
        "description": (
            f"返回行数上限 {_AGENT_FINANCE_QUERY_MAX_ROWS}，这是硬上限，"
            "写更大的值不会拿到更多行。需要更完整的切片就加筛选、分组或排序后再查一次，"
            "不要靠调大 limit。"
        ),
    }
    return parameters


# A dedicated tier, deliberately absent from ``answer_model._HARD_EVIDENCE_TIERS``:
# user memory is the user's own prior judgement, never an objective market fact.
# Reusing an existing tier (e.g. ``agent_retrieval``) would make it
# indistinguishable downstream from objective retrieval.
_USER_MEMORY_EVIDENCE_TIER = "user_memory"
_AGENT_MEMORY_LOOKUP_MAX_RECORDS = 5
# ``select_relevant`` scores a tag hit (4) above a body-text overlap (2), but it
# can only do that when the caller names the subject.  Passing the raw tool query
# alone leaves the ledger's ``themes``/``stocks`` tags dependent on the model
# happening to repeat the subject verbatim, so a follow-up like "那还能追吗"
# recalls nothing.  The upstream contract already resolved subject and
# subject_kind; route them in rather than re-deriving intent here.
#
# One parameter, not two.  ``user_memory._query_terms`` flattens ``theme`` and
# ``entity`` into a single scored term list, and which tags get scanned is fixed
# per record type by ``relevant_memory_records`` (judgments: themes+stocks,
# corrections: themes) regardless of which parameter the caller used.  The two
# are therefore byte-for-byte equivalent today; ``theme`` is the one we pass
# because production ledgers tag company names under ``themes`` (there is no
# ``stocks`` field in corrections at all).  Do not reintroduce a split here
# unless ``select_relevant`` first learns to weight the two differently.
#
# Kinds with no ledger tag counterpart (market_pattern / index /
# external_market / unknown) route nothing: "A股市场" would only add a noise
# term.  That bounds *which* subjects get routed, NOT how general the routed
# term is — a short subject such as "AI" still substring-matches many tags,
# because ``_norm`` compares against one joined tag string.  That is a
# select_relevant scoring property this hop cannot fix, so any recall eval has
# to record the routed subject to attribute its own false positives.
#
# ``SubjectKind`` (query_understanding.py) is a ``typing.Literal``, so it is not
# enforced at runtime and ``TaskFrame.subject_kind`` is a plain ``str``; match
# defensively rather than exhaustively.  "concept" is kept for that reason, not
# because a production caller was observed emitting it.
_MEMORY_SUBJECT_KINDS_WITH_LEDGER_TAGS = frozenset({"company", "concept", "theme"})
# ``_query_terms`` drops query tokens shorter than 2 chars but applies no floor
# to a routed subject.  Hold routed subjects to the same bar: a single-char
# subject is never a real A-share company or theme, and substring matching makes
# it sweep the whole ledger.
_MIN_ROUTED_SUBJECT_CHARS = 2


def _memory_recall_intent(contract_subject: str | None, subject_kind: str | None) -> dict[str, str]:
    """Route the contract's resolved subject into the ledger recall parameter."""

    subject = str(contract_subject or "").strip()
    if len(subject) < _MIN_ROUTED_SUBJECT_CHARS:
        return {}
    kind = str(subject_kind or "").strip().lower()
    if kind in _MEMORY_SUBJECT_KINDS_WITH_LEDGER_TAGS:
        return {"theme": subject}
    return {}


@dataclass(frozen=True)
class SealedFixturePolicy:
    """Local-only tool policy shared by fair headless/App Server controls."""

    external_search_enabled: bool = False
    external_valuation_enabled: bool = False
    external_financials_enabled: bool = False
    require_fresh_kb: bool = True
    market_db_path: Path | None = None
    knowledge_index_dir: Path | None = None
    knowledge_code_root: Path | None = None
    knowledge_python: Path | None = None


def _iso_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _structured_freshness_floor(
    context: ResearchRunContext,
) -> date | None:
    snapshot_date = _iso_date(context.latest_data_date)
    if snapshot_date is None:
        return None
    return min(snapshot_date, context.information_cutoff.as_of_date)


def _is_current_query_stale(
    spec: finance_query.FinanceQuerySpec,
    *,
    served_date: str | None,
    floor: date | None,
    historical_authorized: bool = False,
) -> bool:
    served = _iso_date(served_date)
    if floor is None or served is None:
        return False
    if (
        historical_authorized
        and spec.time_range is not None
        and spec.time_range.end is not None
        and spec.time_range.end < floor
    ):
        return False
    return served < floor


def _task_authorizes_historical_window(
    frame: TaskFrame,
    *,
    floor: date | None,
) -> bool:
    """Only user-owned task semantics may relax the current-data floor."""

    if frame.question_type == "dated_market_review":
        return True
    timeframe_date = _iso_date(frame.timeframe)
    if timeframe_date is not None and (floor is None or timeframe_date < floor):
        return True
    task_text = f"{frame.raw_question} {frame.timeframe or ''}"
    return any(
        cue in task_text
        for cue in ("历史", "去年", "前年", "上个月", "上月", "上季度", "当时")
    )


def _requests_earlier_window(
    spec: finance_query.FinanceQuerySpec,
    *,
    floor: date | None,
) -> bool:
    return bool(
        floor is not None
        and spec.time_range is not None
        and spec.time_range.end is not None
        and spec.time_range.end < floor
    )


def _structured_provider_is_stale(
    served_date: str | None,
    *,
    floor: date | None,
) -> bool:
    if floor is None:
        return False
    served = _iso_date(served_date)
    return served is None or served < floor


def _stale_structured_result(
    *,
    capability: str,
    provider: str,
    served_date: str | None,
    floor: date,
    detail: str,
) -> ToolRunResult:
    served = str(served_date or "未知日期")
    required = floor.isoformat()
    gap = (
        f"结构化市场数据仅更新到 {served}，早于当前所需 {required}；"
        "旧数据未用于当前判断"
    )
    return ToolRunResult(
        evidence=(),
        observation=gap,
        trace=ProviderTrace(
            provider=provider,
            capability=capability,
            status="stale",
            detail=detail,
            source_trade_date=served_date,
            requested_date=required,
            served_date=served_date,
            result_count=0,
        ),
        gaps=(gap,),
    )


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


def latest_market_date(
    finance_root: str | Path | None = None,
    *,
    market_db_path: str | Path | None = None,
) -> str | None:
    finance, _wiki = _roots(finance_root, None)
    return ask_blocks._market_data_asof(  # noqa: SLF001 - public factory seam
        (
            Path(market_db_path).expanduser()
            if market_db_path is not None
            else finance / "db" / "market_feature_store.duckdb"
        )
    )


def _market_block(
    frame: TaskFrame,
    context: ResearchRunContext,
    market_db_path: Path,
    subject_query: str | None = None,
    valuation_fetcher: object | None = None,
) -> tuple[str, str, str]:
    as_of = _structured_freshness_floor(context)
    as_of_value = as_of.isoformat() if as_of is not None else None
    if frame.question_type == "market_forecast":
        block = "\n".join(
            part
            for part in (
                ask_blocks._daily_market_overview_block_for_llm(
                    market_db_path,
                    as_of=as_of_value,
                ),
                ask_blocks._market_cause_window_block_for_llm(
                    market_db_path,
                    as_of=as_of_value,
                ),
            )
            if part
        )
        return block, "本地 DuckDB · 预测盘面窗口", "market_forecast_window"
    if frame.question_type == "market_cause":
        return (
            ask_blocks._market_cause_window_block_for_llm(
                market_db_path,
                as_of=as_of_value,
            ),
            "本地 DuckDB · 周内市场归因窗口",
            "market_cause_window",
        )
    if frame.question_type == "valuation_estimate":
        timeout = context.deadline.stage_timeout(6.0)
        if timeout <= 0.001:
            raise TimeoutError("valuation market-data deadline expired")

        if callable(valuation_fetcher):
            fetch_snapshot = valuation_fetcher
        else:

            def fetch_snapshot(code: str, name: str = ""):
                return valuation_estimate.fetch_eastmoney_snapshot(
                    code,
                    name,
                    timeout=min(timeout, context.deadline.stage_timeout(timeout)),
                )

        return (
            ask_blocks._valuation_block_for_llm(
                subject_query or frame.raw_question,
                frame.subject,
                market_db_path,
                fetcher=fetch_snapshot,
                as_of=as_of_value,
                snapshot_date_hint=context.latest_data_date,
            ),
            "东财快照 + 本地 DuckDB 可比集",
            "company_valuation_snapshot",
        )
    return (
        ask_blocks._daily_market_overview_block_for_llm(
            market_db_path,
            as_of=as_of_value,
        ),
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
    fixture_policy: SealedFixturePolicy | None = None,
    memory_user: str | None = None,
    memory_users_root: str | Path | None = None,
) -> ResearchToolRegistry:
    """Build a read-only registry from the repository's current tool runners."""

    finance, wiki = _roots(finance_root, knowledge_wiki)
    market_db_path = (
        Path(fixture_policy.market_db_path).expanduser()
        if fixture_policy is not None and fixture_policy.market_db_path is not None
        else finance / "db" / "market_feature_store.duckdb"
    )
    freshness_floor = _structured_freshness_floor(context)
    structured_source_date = None
    if frame.question_type != "valuation_estimate":
        structured_source_date = ask_blocks._market_data_asof(  # noqa: SLF001
            market_db_path,
            as_of=(
                freshness_floor.isoformat()
                if freshness_floor is not None
                else None
            ),
        )
    market_reference_date = context.latest_data_date or structured_source_date
    evidence_profile = context.contract.evidence_plan.profile
    market_window_start = None
    market_window_end = None
    if evidence_profile == "time_aligned_market_causal":
        market_window_end = market_news.latest_explicit_query_date(
            f"{frame.raw_question} {frame.timeframe or ''}",
            reference_date=context.information_cutoff.as_of_date,
        )
        if market_window_end is None and market_reference_date:
            try:
                market_window_end = date.fromisoformat(
                    str(market_reference_date)[:10]
                )
            except ValueError:
                market_window_end = None
        if market_window_end is None:
            market_window_end = context.information_cutoff.as_of_date
        market_window_start = market_news.latest_explicit_query_date(
            frame.timeframe or "",
            reference_date=context.information_cutoff.as_of_date,
        )
        if market_window_start is None:
            market_window_start = market_window_end - timedelta(
                days=market_window_end.weekday()
            )
    evidence_search_policy = evidence_search.EvidenceSearchPolicy()
    if market_window_start is not None and market_window_end is not None:
        evidence_search_policy = evidence_search.EvidenceSearchPolicy(
            expansion_policy="query_only",
            required_source_start=market_window_start,
            required_source_end=market_window_end,
            require_counter_evidence=True,
        )
    elif evidence_profile == "valuation_current_anchor":
        evidence_search_policy = evidence_search.EvidenceSearchPolicy(
            anchor_admission="subject_local",
        )
    knowledge = KnowledgeAdapter(wiki_root=wiki)
    subject_anchor = entity_anchor.resolve_entity_anchor(
        f"{frame.subject or ''} {frame.raw_question}",
        knowledge,
    )
    subject_query = (
        f"{subject_anchor.entity} {subject_anchor.ticker} {frame.raw_question}"
        if subject_anchor is not None and subject_anchor.ticker
        else f"{frame.subject or ''} {frame.raw_question}".strip()
    )

    def retrieve_kb(query: str, timeout: float):
        return kb_rag.retrieve(
            query,
            wiki,
            k=6,
            mode="hybrid",
            timeout=min(timeout, 30.0),
            excerpt_chars=240,
            budget_query=frame.raw_question,
            require_fresh=(
                fixture_policy.require_fresh_kb
                if fixture_policy is not None
                else True
            ),
            cache_scope=context.contract.task_id,
            index_dir=(
                fixture_policy.knowledge_index_dir
                if fixture_policy is not None
                else None
            ),
            code_root=(
                fixture_policy.knowledge_code_root
                if fixture_policy is not None
                else None
            ),
            python_executable=(
                fixture_policy.knowledge_python
                if fixture_policy is not None
                else None
            ),
            worker_enabled=(False if fixture_policy is not None else None),
        )

    default_tools = agent_research.build_default_tools(retrieve_kb)
    if fixture_policy is not None and not fixture_policy.external_search_enabled:
        default_tools.pop("web_search", None)
        default_tools.pop("news_search", None)
    tools = {
        **default_tools,
        **agent_research.build_graph_tools(knowledge),
    }

    def market_data_runner(
        _query: str,
        tool_context: agent_research.AgentToolContext,
    ):
        tool_context.check_cancelled()
        if tool_context.deadline.expired:
            raise TimeoutError("market-data deadline expired")
        if frame.question_type != "valuation_estimate" and _structured_provider_is_stale(
            structured_source_date,
            floor=freshness_floor,
        ):
            assert freshness_floor is not None
            return _stale_structured_result(
                capability="market_data",
                provider="agent:market_data",
                served_date=structured_source_date,
                floor=freshness_floor,
                detail="market_snapshot_newer_than_structured_market",
            )
        block, source, detail = _market_block(
            frame,
            context,
            market_db_path,
            subject_query,
            (
                (lambda _code, _name="": None)
                if fixture_policy is not None
                and not fixture_policy.external_valuation_enabled
                else None
            ),
        )
        served_date = (
            valuation_estimate.block_source_date(block)
            if frame.question_type == "valuation_estimate"
            else structured_source_date
        )
        if _structured_provider_is_stale(served_date, floor=freshness_floor):
            assert freshness_floor is not None
            return _stale_structured_result(
                capability="market_data",
                provider="agent:market_data",
                served_date=served_date,
                floor=freshness_floor,
                detail=(
                    "valuation_snapshot_missing_or_stale"
                    if frame.question_type == "valuation_estimate"
                    else detail
                ),
            )
        tool_context.check_cancelled()
        evidence, observation = agent_research.block_lines_to_evidence(
            "market_data",
            block,
            source,
            limit=18,
            detail_chars=1000,
            source_date=served_date,
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
                source_trade_date=served_date,
                requested_date=(
                    freshness_floor.isoformat() if freshness_floor else None
                ),
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
        if (
            fixture_policy is not None
            and not fixture_policy.external_financials_enabled
        ):
            block = ask_blocks.market_financials.build_financials_block(
                frame.subject or frame.raw_question,
                "",
                [],
                fetch_disabled=True,
            )
        else:
            block = ask_blocks._financials_block_for_llm(
                subject_query,
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
        if _structured_provider_is_stale(
            structured_source_date,
            floor=freshness_floor,
        ):
            assert freshness_floor is not None
            return _stale_structured_result(
                capability="mainline_context",
                provider="agent:mainline_context",
                served_date=structured_source_date,
                floor=freshness_floor,
                detail="market_snapshot_newer_than_structured_mainline",
            )
        block = ask_blocks._market_review_mainline_context_block_for_llm(
            frame.raw_question,
            frame.subject,
            market_db_path,
            as_of=(
                freshness_floor.isoformat()
                if freshness_floor is not None
                else None
            ),
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
    if (
        "l3_lookup" in context.contract.allowed_capabilities
        and callable(selected_l3_runner)
        and not (
            fixture_policy is not None
            and not fixture_policy.external_search_enabled
        )
    ):
        tools["l3_lookup"] = selected_l3_runner
    base_registry = default_registry(tools)
    specs = list(base_registry.authorized_specs())
    if market_window_end is not None:

        def causal_tool_cutoff(
            prepared: PreparedToolArguments,
            run_context: ResearchRunContext,
        ) -> InformationCutoff:
            task_cutoff = min(
                run_context.information_cutoff.as_of_date,
                market_window_end,
            )
            return InformationCutoff(
                market_news.query_date_cutoff(
                    prepared.display_query,
                    upper_bound=task_cutoff,
                ),
                "requested",
            )

        specs = [
            replace(spec, cutoff_resolver=causal_tool_cutoff)
            if spec.name in {"news_search", "web_search"}
            else spec
            for spec in specs
        ]

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
            # 归一化要在所有判定之前，否则新鲜度判定读 spec.time_range 会读到 None。
            # normalize_spec 是幂等的，run() 内部还会再调一次，代价极小。
            normalized, normalization_notes = finance_query.normalize_spec(value)
            bounded_value = replace(
                normalized,
                limit=min(normalized.limit, _AGENT_FINANCE_QUERY_MAX_ROWS),
            )
            freshness_floor = _structured_freshness_floor(context)
            historical_authorized = _task_authorizes_historical_window(
                frame,
                floor=freshness_floor,
            )
            if _requests_earlier_window(
                bounded_value,
                floor=freshness_floor,
            ) and not historical_authorized:
                assert freshness_floor is not None
                return ToolRunResult(
                    evidence=(),
                    observation=(
                        "当前用户任务未授权历史窗口；请把 time_range 调整到 "
                        f"{freshness_floor.isoformat()} 附近，或省略 time_range "
                        "让系统按当前截止日选择数据"
                    ),
                    trace=ProviderTrace(
                        provider="duckdb_semantic_query",
                        capability="finance_query",
                        status="parse_error",
                        detail=(
                            f"dataset={value.dataset}; "
                            "historical_window_not_authorized_by_task"
                        ),
                        requested_date=freshness_floor.isoformat(),
                        result_count=0,
                    ),
                    gaps=(
                        "当前问题需要截止日附近的结构化数据；模型选择的旧历史窗口未执行",
                    ),
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
            # 用 bounded_value 而不是 value：这条判定读 spec.time_range，读未归一化
            # 的那份就会把「日期写进了 filters」误判成「没给时间窗口」，
            # historical_authorized 的授权也就跟着失效——正是归一化要修的那个失真。
            if _is_current_query_stale(
                bounded_value,
                served_date=result.served_date,
                floor=freshness_floor,
                historical_authorized=historical_authorized,
            ):
                assert freshness_floor is not None
                return _stale_structured_result(
                    capability="finance_query",
                    provider="duckdb_semantic_query",
                    served_date=result.served_date,
                    floor=freshness_floor,
                    detail=f"dataset={value.dataset}; stale_current_data",
                )
            gaps = (
                ()
                if result.evidence
                else (f"{value.dataset} 在指定条件与时点内没有结构化结果",)
            )
            observation = result.observation
            if (
                normalized.limit > result.audit.applied_limit
                and result.audit.row_count >= result.audit.applied_limit
            ):
                observation = (
                    f"{observation}；查询结果已按 Agent 上下文预算截断至 "
                    f"{result.audit.applied_limit} 条；如需更多，请增加筛选、"
                    "分组或排序后继续查询"
                )
            # 代偿必须让模型看见：查询成功但写法被改过，不说它下一轮还会照原样写。
            # 放在结论之后、和截断提示同层——都是「结果可用，但有一条关于写法的话」。
            if normalization_notes:
                observation = "；".join((observation, *normalization_notes))
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
                parameters=_agent_finance_parameters(),
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
                policy=evidence_search_policy,
            )
            query_anchor = (
                subject_anchor
                if evidence_profile == "valuation_current_anchor"
                else entity_anchor.resolve_entity_anchor(query, knowledge)
            )
            result = search.search(
                query=query,
                anchor=query_anchor,
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

    # 授权之外还要求身份已解析。`user_memory._ledger_paths` 在 ``user`` 与
    # ``users_root`` 都为 None 时回落到 ``userspace.user_space(None)`` →
    # ``resolve_user_id(None)`` → ``FORESIGHT_USER`` 或 ``"default"``：多用户服务端
    # 上那不是「少一份召回」，而是**每个人都去读 default 用户的私有判断台账**。
    #
    # 所以缺身份时不注册这个工具。宁可少一个能力（模型看不到它，照常用其他工具
    # 完成任务），也不要静默串号——这也让「授权」与「身份穿透」两件事无法只做一半：
    # 单独加授权不会生效，必须同时把 user_id 传到这里。
    memory_identity_resolved = (
        str(memory_user or "").strip() != "" or memory_users_root is not None
    )
    if (
        "memory_lookup" in context.contract.allowed_capabilities
        and memory_identity_resolved
    ):

        def memory_lookup_runner(
            query: str,
            tool_context: agent_research.AgentToolContext,
        ):
            tool_context.check_cancelled()
            recall = user_memory.relevant_memory_records(
                query,
                user=memory_user,
                users_root=memory_users_root,
                **_memory_recall_intent(
                    context.contract.subject,
                    context.contract.subject_kind,
                ),
            )
            tool_context.check_cancelled()
            evidence: list[agent_research.AgentEvidence] = []
            for record in recall.judgments:
                memo = str(record.get("memo") or "").strip()
                if not memo:
                    continue
                tags = [
                    str(tag).strip()
                    for key in ("themes", "stocks")
                    for tag in (record.get(key) or [])
                    if str(tag).strip()
                ]
                evidence.append(
                    agent_research.AgentEvidence(
                        tool="memory_lookup",
                        title="用户历史判断",
                        detail=memo,
                        # Self-labelling source: the model only ever sees this
                        # string, so it has to say what the record is on its own.
                        source="用户自己的历史判断（先验，非市场事实）",
                        internal_locator=str(recall.judgments_path),
                        source_date=str(record.get("ts") or "")[:10] or None,
                        evidence_tier=_USER_MEMORY_EVIDENCE_TIER,
                        freshness="historical",
                        independent_key="｜".join(tags) if tags else "",
                    )
                )
            for record in recall.corrections:
                correction = str(record.get("correction") or "").strip()
                principle = str(record.get("principle") or "").strip()
                body = principle or correction
                if not body:
                    continue
                evidence.append(
                    agent_research.AgentEvidence(
                        tool="memory_lookup",
                        title="用户纠偏原则",
                        detail=body,
                        source="用户自己纠正过的方法论（先验，非市场事实）",
                        internal_locator=str(recall.corrections_path),
                        source_date=str(record.get("ts") or "")[:10] or None,
                        evidence_tier=_USER_MEMORY_EVIDENCE_TIER,
                        freshness="historical",
                    )
                )
            observation = (
                "；".join(f"{item.title}：{item.detail}" for item in evidence)
                or "用户记忆无相关命中（该题材/标的此前没有留下判断或纠偏）"
            )
            trace = ProviderTrace(
                provider="episode:memory_lookup",
                capability="memory_lookup",
                status="success" if evidence else "empty",
                detail=query[:120],
                result_count=len(evidence),
            )
            return ToolRunResult(
                evidence=tuple(evidence),
                observation=observation,
                trace=trace,
                gaps=() if evidence else ("用户记忆中没有与本题相关的历史判断",),
            )

        specs.append(
            ToolSpec(
                name="memory_lookup",
                capability="memory_lookup",
                description=(
                    "检索用户自己过去的判断与纠偏原则（本地私有台账）。"
                    "返回的是这位用户的历史先验，不是市场事实、不能当作证据引用；"
                    "用于确认用户此前怎么看、遵守其纠偏原则、聚焦增量变化。"
                ),
                cost="local",
                freshness="stable",
                runner=memory_lookup_runner,
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
