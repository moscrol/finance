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
import re
import time

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.paths import default_paths
from intelligence.services import (
    agent_research,
    ask_blocks,
    entity_anchor,
    evidence_capabilities,
    evidence_search,
    external_market,
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
from intelligence.services.tool_payload import field_names_from_rows


# runner 真能出零 LLM 答案的题型。``run_deterministic_fast_path`` 用它判
# unsupported，adapter 的 ``CONTINUOUS_FAST_PATH_TYPES`` 直接引用它——同一
# 支持集只写这一处，不再「名单说可以、执行者说不认识」（R-20260828-08）。
FAST_PATH_RUNNER_SUPPORTED_TYPES = frozenset({"market_technical"})

# A/B 评测分臂名单：命中即评测走确定性臂、跳过 episode。它只能包含生产
# 不进 episode 的题型（adapter 拒接或 fast path），否则评测测的是生产
# 不存在的空壳路径——quick_fact 曾因此在 R-20260828-05 后仍被评测按
# 确定性臂跑「尚未接入」占位（F1 修了生产、评测臂没跟上的活漂移）。
# services 不 import runtime，与 DETERMINISTIC_OWNER_TYPES 的包含关系由
# tests/test_route_composition_gate.py 钉住（同 DO_NOT_LENGTHEN 手法）。
_FAST_PATH_TYPES = FAST_PATH_RUNNER_SUPPORTED_TYPES | frozenset(
    {"external_market", "dated_market_review"}
)
_SUPPORT_FOCUS_RE = re.compile(r"支撑")
_RESISTANCE_FOCUS_RE = re.compile(r"反弹|上涨空间|压力|阻力")


def _market_technical_focus(question: str) -> str:
    """快路径出文焦点：支撑题先报支撑，其余保持反弹/压力口径。"""
    text = re.sub(r"\s+", "", str(question or ""))
    if _SUPPORT_FOCUS_RE.search(text) and not _RESISTANCE_FOCUS_RE.search(text):
        return "support"
    return "resistance"


# 单一真本源在 ``agent_research``：同一张前缀表既用来把限定语挡在证据之外
# （这里），也用来把它提到 observation 最前面（``block_lines_to_evidence``）。
# 抄第二份必然分叉，且分叉时没有门禁会发红。
_NON_EVIDENCE_PREFIXES = agent_research.QUALIFIER_LINE_PREFIXES
_OFFICIAL_L3_RUNNER = object()


def _finance_payload_kwargs(
    spec: finance_query.FinanceQuerySpec,
    result: finance_query.FinanceQueryResult | None = None,
) -> dict[str, object]:
    """Attach dataset/caliber/field names for a finance_query return. Never row values."""

    requested = (*(spec.dimensions or ()), *(spec.metrics or ()))
    names = field_names_from_rows(
        None if result is None else result.rows,
        requested=requested,
    )
    table = finance_query.dataset_physical_table(spec.dataset)
    return {
        "dataset": spec.dataset,
        "caliber": table or spec.dataset,
        "payload_field_names": names,
    }
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


def _should_attach_overnight_leaders(
    frame: TaskFrame,
    fixture_policy: SealedFixturePolicy | None,
) -> bool:
    if frame.question_type != "market_forecast":
        return False
    if fixture_policy is not None and not fixture_policy.external_search_enabled:
        return False
    return evidence_capabilities._has_overnight_external_premise(frame.raw_question)


def _overnight_leader_evidence(
    frame: TaskFrame,
    *,
    timeout: float,
) -> tuple[list[agent_research.AgentEvidence], str | None]:
    result = external_market.resolve_overnight_leaders(
        frame.raw_question,
        timeout=timeout,
    )
    evidence: list[agent_research.AgentEvidence] = []
    for quote in result.quotes:
        line = external_market.format_quote_line(quote)
        item = agent_research.AgentEvidence(
            tool="market_data",
            title=line[:48],
            detail=line,
            source=quote.source,
            source_date=quote.trade_date,
            evidence_tier="L4_structured",
        )
        evidence.append(
            replace(item, content_hash=agent_research.evidence_content_hash(item))
        )
    return evidence, result.gap


_OVERNIGHT_NEWS_QUERY = "美股"


def _should_attach_overnight_news(
    frame: TaskFrame,
    fixture_policy: SealedFixturePolicy | None,
    allowed_capabilities,
) -> bool:
    if "news_search" not in allowed_capabilities:
        return False
    if frame.question_type != "market_forecast":
        return False
    if fixture_policy is not None and not fixture_policy.external_search_enabled:
        return False
    return evidence_capabilities._has_overnight_external_premise(frame.raw_question)


def _overnight_news_evidence(
    *,
    as_of,
    timeout,
) -> tuple[list[agent_research.AgentEvidence], str]:
    result = market_news.fetch_eastmoney_news_result(
        _OVERNIGHT_NEWS_QUERY,
        timeout=timeout,
        as_of=as_of,
    )
    if as_of is None:
        cutoff_text = None
    elif hasattr(as_of, "isoformat"):
        cutoff_text = as_of.isoformat()
    else:
        cutoff_text = str(as_of)[:10]
    after_cutoff = bool(not result.items and result.after_cutoff_items)
    source_items = result.items[:6] or result.after_cutoff_items[:6]
    evidence = [
        agent_research.AgentEvidence(
            tool="news_search",
            title=(
                f"晚于问句日 {cutoff_text}｜{item.title}"
                if after_cutoff and cutoff_text
                else item.title
            ),
            detail=f"{item.date} {item.source}",
            source=item.url,
            source_date=item.date[:10] or None,
            evidence_tier="news",
            independent_key=item.url,
        )
        for item in source_items
    ]
    evidence = [
        replace(item, content_hash=agent_research.evidence_content_hash(item))
        for item in evidence
    ]
    if after_cutoff and cutoff_text and evidence:
        listed = "；".join(f"{item.detail}《{item.title}》" for item in evidence)
        observation = (
            f"源返回 {len(evidence)} 条，全部晚于问句日 {cutoff_text}，"
            f"已标注后交付；不是源里没有。{listed}"
        )
    else:
        observation = "；".join(
            f"{item.detail}《{item.title}》" for item in evidence
        )
    return evidence, observation


def _structured_as_of(context: ResearchRunContext) -> str:
    """盘面查询上界：有快照用 min(快照, cutoff)，没有快照也必须夹在 cutoff 内。

    freshness_floor 在缺快照时返回 None，是为了不把「昨天的数」误判成 stale。
    查询上界不能跟着变成 None——否则 cutoff=07-21 仍会取出 08-13 的最新行（C7）。
    """

    floor = _structured_freshness_floor(context)
    if floor is not None:
        return floor.isoformat()
    return context.information_cutoff.as_of_date.isoformat()


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


def _window_anchored_on_episode_dates(
    spec: finance_query.FinanceQuerySpec,
    authorized_trade_dates: set[str] | frozenset[str],
) -> bool:
    """窗口起点已在本轮证据里 → 允许查那一天，不看题型。"""

    start = spec.time_range.start if spec.time_range is not None else None
    return bool(start is not None and start.isoformat() in authorized_trade_dates)


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


def _subject_exited_universe(
    *,
    served_date: str | None,
    dataset_max_date: str | None,
    floor: date,
) -> bool:
    """被筛子集停在更早，但数据集本身是新的 → 该主体退出了集合，不是管道陈旧。

    2026-08-17 用户口径：新鲜度按**数据类**分档，不是整体放宽。

    - DuckDB 硬事实（行情/成交/涨停）→ 照旧从严；
    - 知识库/图谱 → 关注逻辑的生命周期变化，本就不过这道门；
    - 本函数只处理第三种情形：**行业构成的变化本身就是要观察的对象**。

    实例：`fact_mainline_sector_daily` 整体有到 2026-08-14 的行，而「AI算力」最后
    一天是 08-07（08-10 起主线只剩有色金属/医药/消费零售）。「算力掉出主线」正是
    「发酵/共识/透支」要的那个信号，把它当过期数据整批丢弃等于丢掉答案。

    **红线不动**：判别变量是「数据集 max 与被筛子集 max 的关系」，不是放宽 floor。
    `dataset_max < floor` 说明整条管道确实落后，仍然照旧拒绝——那是这道门禁的
    原始设计意图。探针取不到值（None）时同样落回拒绝那一侧，fail-closed。
    """

    dataset_max = _iso_date(dataset_max_date)
    served = _iso_date(served_date)
    if dataset_max is None or served is None:
        return False
    # 数据集本身没跟上 → 真陈旧，不是退出。**这一条是唯一的判别闸**，
    # 抽掉它两种情形就合并了（有测试钉住）。
    if dataset_max < floor:
        return False
    # 子集不早于数据集 → 没退出这回事。
    #
    # ⚠️ 这一行在调用方的契约下**可证明冗余**，故变异它不会让测试转红——这是
    # 等价变异，不是门禁有洞。推导：调用方只在已判 stale（`served < floor`）时
    # 才调本函数，而上一条已保证 `dataset_max >= floor`，于是
    # `served < floor <= dataset_max` 恒成立。要构造反例需
    # `served >= dataset_max >= floor > served`，自相矛盾。
    # 保留它是防御——本函数若将来被别处直接调用（契约不再成立），它仍正确。
    return served < dataset_max


def _probe_filtered_universe_exit(
    query_engine: finance_query.FinanceQuery,
    spec: finance_query.FinanceQuerySpec,
    *,
    context: ResearchRunContext,
    tool_context: agent_research.AgentToolContext,
    dataset_label: str,
) -> ToolRunResult | None:
    """问句日无行时，探测「该筛选条件最后一次出现」是否构成要素退出。

    与 stale 路径的差别：历史授权的定点查询 served_date 为空，不会走进
    `_is_current_query_stale`。空结果若只说「无结果」，模型会把「航空发动机」
    放宽成「航空」（R5 live）。探针失败 fail-closed，仍走原来的空结果。
    """

    if not spec.filters or spec.time_range is None:
        return None
    requested = spec.time_range.end or spec.time_range.start
    if requested is None:
        return None
    time_field = next(
        (item for item in spec.dimensions if item in {"trade_date", "as_of"}),
        "trade_date",
    )
    last_spec = replace(
        spec,
        time_range=None,
        order_by=(finance_query.Order(field=time_field, direction="desc"),),
        limit=1,
    )
    try:
        last_result = query_engine.run(
            last_spec,
            information_cutoff=context.information_cutoff,
            deadline=tool_context.deadline,
            is_cancelled=tool_context.is_cancelled,
        )
        dataset_max = query_engine.dataset_max_date(
            spec,
            information_cutoff=context.information_cutoff,
            deadline=tool_context.deadline,
            is_cancelled=tool_context.is_cancelled,
        )
    except finance_query.FinanceQueryError:
        return None
    if not _subject_exited_universe(
        served_date=last_result.served_date,
        dataset_max_date=dataset_max,
        floor=requested,
    ):
        return None
    return _exited_universe_result(
        last_result,
        capability="finance_query",
        provider="duckdb_semantic_query",
        dataset_label=dataset_label,
        dataset_max_date=str(dataset_max),
        detail=f"dataset={spec.dataset}; subject_exited_universe",
        spec=spec,
    )


def _exited_universe_result(
    result: finance_query.FinanceQueryResult,
    *,
    capability: str,
    provider: str,
    dataset_label: str,
    dataset_max_date: str,
    detail: str,
    spec: finance_query.FinanceQuerySpec | None = None,
) -> ToolRunResult:
    """交付「退出集合」这一生命周期事实，连同退出前的行。

    与 `_stale_structured_result` 的关键差别：**证据照常交付**。那些行确实早于
    floor，但它们不是「冒充当前状态的旧数据」——它们是「该主体最后一次出现时
    长什么样」，配合退出事实一起读才完整。每条证据自带 `source_date`，日期在场，
    不会被误读成当前盘面。
    """

    served = str(result.served_date or "未知日期")
    fact = (
        f"{dataset_label} 中该筛选条件最后一次出现是 {served}；"
        f"数据集已更新到 {dataset_max_date}，其后未再出现"
        "（构成要素退出，非数据陈旧）。"
    )
    observation = f"{fact}{result.observation}" if result.observation else fact
    payload = _finance_payload_kwargs(spec, result) if spec is not None else {}
    return ToolRunResult(
        evidence=result.evidence,
        observation=observation,
        trace=ProviderTrace(
            provider=provider,
            capability=capability,
            status="ok",
            detail=detail,
            source_trade_date=result.served_date,
            served_date=result.served_date,
            result_count=len(result.evidence),
        ),
        gaps=(),
        **payload,
    )


def _stale_structured_result(
    *,
    capability: str,
    provider: str,
    served_date: str | None,
    floor: date,
    detail: str,
    spec: finance_query.FinanceQuerySpec | None = None,
) -> ToolRunResult:
    served = str(served_date or "未知日期")
    required = floor.isoformat()
    gap = (
        f"结构化市场数据仅更新到 {served}，早于当前所需 {required}；"
        "旧数据未用于当前判断"
    )
    payload = _finance_payload_kwargs(spec) if spec is not None else {}
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
        **payload,
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


def _is_fermentation_prefetch(frame: TaskFrame) -> bool:
    from intelligence.services.query_understanding import (
        SIGNAL_FERMENTATION,
        surface_research_signals,
    )
    from intelligence.services.research_contract import (
        OPERATOR_STRICT_DOUBLE_RED,
        compile_research_program,
    )

    program = compile_research_program(
        frame.raw_question,
        question_class=frame.question_type,
    )
    signals = surface_research_signals(
        frame.raw_question,
        question_class=frame.question_type,
    )
    return (
        OPERATOR_STRICT_DOUBLE_RED in program.operators
        and SIGNAL_FERMENTATION in signals
    )


def _asof_prefetch_text(
    frame: TaskFrame,
    context: ResearchRunContext,
    market_db_path: Path,
) -> str:
    from intelligence.services.asof_prefetch import collect_prefetch_items

    try:
        as_of = date.fromisoformat(_structured_as_of(context))
        items = collect_prefetch_items(
            question=frame.raw_question,
            question_type=frame.question_type,
            subject=frame.subject or "",
            as_of=as_of,
            market_db_path=market_db_path,
        )
    except Exception:
        return ""
    return "\n".join(item.detail for item in items if str(item.detail or "").strip())


def _opening_prefetch_evidence(
    frame: TaskFrame,
    context: ResearchRunContext,
    market_db_path: Path,
    *,
    user_space=None,
    perspective_ids: tuple[str, ...] = (),
    perspective_mode: str = "neutral",
) -> tuple[agent_research.AgentEvidence, ...]:
    from intelligence.services.asof_prefetch import (
        collect_prefetch_items,
        evidence_from_prefetch,
    )

    try:
        as_of = date.fromisoformat(_structured_as_of(context))
        items = collect_prefetch_items(
            question=frame.raw_question,
            question_type=frame.question_type,
            subject=frame.subject or "",
            as_of=as_of,
            market_db_path=market_db_path,
        )
    except Exception:
        return ()
    evidence = list(evidence_from_prefetch(items))
    if frame.question_type == "market_forecast":
        for item in _live_weekly_opening_evidence(
            items,
            user_space=user_space,
            perspective_ids=perspective_ids,
            perspective_mode=perspective_mode,
        ):
            digest = str(item.content_hash or "").strip() or agent_research.evidence_content_hash(item)
            evidence.append(replace(item, content_hash=digest))
    return tuple(evidence)


def _live_weekly_opening_evidence(
    items,
    *,
    user_space,
    perspective_ids: tuple[str, ...],
    perspective_mode: str,
) -> tuple[agent_research.AgentEvidence, ...]:
    from intelligence.services.perspective_live_weekly import (
        bind_live_weekly,
        live_weekly_evidence,
        retrieve_analog_snippets,
    )

    pid = next((str(item).strip() for item in perspective_ids if str(item).strip()), "")
    receipt = bind_live_weekly(
        user_space,
        pid,
        perspective_mode=perspective_mode,
    )
    analogs: list[dict[str, str]] = []
    if receipt.bound and receipt.date and user_space is not None and pid:
        tape = next(
            (str(item.detail) for item in items if getattr(item, "title", "") == "先验周量能序列"),
            "",
        )
        analogs = retrieve_analog_snippets(
            user_space,
            pid,
            tape or "量能 主线 双红",
            live_date=receipt.date,
        )
    return live_weekly_evidence(receipt, analogs)


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
    as_of_value = _structured_as_of(context)
    prefetch_text = _asof_prefetch_text(frame, context, market_db_path)
    if _is_fermentation_prefetch(frame) and prefetch_text:
        return prefetch_text, "本地 DuckDB · 问句日预取", "fermentation_timeline"
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
        if prefetch_text:
            block = "\n".join(part for part in (block, prefetch_text) if part)
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
    perspective_ids: tuple[str, ...] = (),
    perspective_mode: str = "neutral",
    user_space=None,
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
            as_of=_structured_as_of(context),
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
        if _should_attach_overnight_leaders(frame, fixture_policy):
            leader_timeout = tool_context.deadline.stage_timeout(15.0)
            if leader_timeout > 0.001:
                leader_evidence, leader_gap = _overnight_leader_evidence(
                    frame,
                    timeout=leader_timeout,
                )
                evidence.extend(leader_evidence)
                extras = [item.detail for item in leader_evidence]
                if leader_gap:
                    extras.append(leader_gap)
                if extras:
                    observation = "；".join(
                        part for part in (observation, *extras) if part
                    )
        if _should_attach_overnight_news(
            frame,
            fixture_policy,
            context.contract.allowed_capabilities,
        ) and not any(item.tool == "news_search" for item in evidence):
            news_timeout = tool_context.deadline.stage_timeout(8.0)
            if news_timeout > 0.001:
                news_evidence, news_obs = _overnight_news_evidence(
                    as_of=market_news.query_date_cutoff(
                        _OVERNIGHT_NEWS_QUERY,
                        upper_bound=context.information_cutoff.as_of_date,
                    ),
                    timeout=news_timeout,
                )
                if news_evidence:
                    evidence.extend(news_evidence)
                    if news_obs:
                        observation = "；".join(
                            part for part in (observation, news_obs) if part
                        )
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
            "东财 F10 / 新浪利润表 / AKShare · D7 逐季财报",
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
            as_of=_structured_as_of(context),
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
            ) or _window_anchored_on_episode_dates(
                bounded_value,
                context.authorized_trade_dates,
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
                    **_finance_payload_kwargs(bounded_value),
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
                # 判 stale 之前先分一次因：被筛子集停在更早，可能是「该主体退出了
                # 集合」而不是「管道陈旧」。两者在 served_date 上同码，只有再读一次
                # 不加 filter 的 max 才分得开。探针只在这条（本就要拒的）路径上发。
                dataset_max = None
                if bounded_value.filters:
                    dataset_max = query_engine.dataset_max_date(
                        bounded_value,
                        information_cutoff=context.information_cutoff,
                        deadline=tool_context.deadline,
                        is_cancelled=tool_context.is_cancelled,
                    )
                if _subject_exited_universe(
                    served_date=result.served_date,
                    dataset_max_date=dataset_max,
                    floor=freshness_floor,
                ):
                    return _exited_universe_result(
                        result,
                        capability="finance_query",
                        provider="duckdb_semantic_query",
                        dataset_label=value.dataset,
                        dataset_max_date=str(dataset_max),
                        detail=f"dataset={value.dataset}; subject_exited_universe",
                        spec=bounded_value,
                    )
                return _stale_structured_result(
                    capability="finance_query",
                    provider="duckdb_semantic_query",
                    served_date=result.served_date,
                    floor=freshness_floor,
                    detail=f"dataset={value.dataset}; stale_current_data",
                    spec=bounded_value,
                )
            if not result.evidence and bounded_value.filters:
                exit_result = _probe_filtered_universe_exit(
                    query_engine,
                    bounded_value,
                    context=context,
                    tool_context=tool_context,
                    dataset_label=value.dataset,
                )
                if exit_result is not None:
                    return exit_result
            gaps = (
                ()
                if result.evidence
                else (f"{value.dataset} 在指定条件与时点内没有结构化结果",)
            )
            # 三条限定语**排在数据行之前**（BUILD 模式 4）。它们此前追加在
            # observation 末尾，而 ``tool_result_budget`` 从头数满 900 字符就切，
            # 于是限定语先于它约束的数据被砍掉。2026-08-30 实测 400 份
            # continuous-episode.json：「查询结果已按…截断至 N 条」出现 123 次，
            # 位置均值在全文 84% 处，**67 次被字符预算吃掉**——关于行数截断的通知，
            # 自己被字符截断砍了；「实际覆盖 X..Y」同样 123 次里丢 67 次，
            # 而时点与完整性正是 ``tool_result_budget`` 开头声明永不截断的红线。
            # 数据行在 ``evidence[]`` 里逐条另有副本（实测被砍片段 92% 有副本），
            # 这三条没有——所以先给限定语，砍到的只会是有副本的那部分。
            notices: list[str] = []
            notice = finance_query.truncation_notice(
                result.audit,
                covered_range=finance_query.covered_date_range(
                    tuple(item.source_date for item in result.evidence)
                ),
            )
            if notice:
                notices.append(notice)
            # 代偿必须让模型看见：查询成功但写法被改过，不说它下一轮还会照原样写。
            if normalization_notes:
                notices.extend(normalization_notes)
            # 覆盖面提示同理，但它拦的是**校验器够不着的那一半**：在子集表上排名次，
            # 查询完全合法、数值也对，错的是分母。A5 实测（2026-08-18）就是在只有
            # 十余行的 mainline_sector_daily 上按 limit_up_count 取 top15，
            # 去回答「全市涨停集中在哪些题材」。空串表示无话可说。
            advisory = finance_query.coverage_advisory(bounded_value)
            if advisory:
                notices.append(advisory)
            observation = "；".join(
                part for part in (*notices, result.observation) if part
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
                    requested_time_range=result.audit.requested_time_range,
                ),
                gaps=gaps,
                **_finance_payload_kwargs(bounded_value, result),
            )

        specs.append(
            ToolSpec(
                name="finance_query",
                capability="finance_query",
                description=(
                    "查询本地结构化金融数据。dataset 必须选自当前注册表"
                    f"（{ '、'.join(finance_query._PUBLIC_DATASETS) }）；"
                    "周历/周末大事用 event_daily。"
                    "由你选择指标、维度、筛选、分组、排序和时间范围。"
                    "字段必须按 dataset 对应关系选择，不要混用不同 dataset 的字段。"
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
            peer_lines = user_memory.judgment_peer_hits(
                list(recall.judgments),
                user=memory_user,
                users_root=memory_users_root,
            )
            for record, peer in zip(recall.judgments, peer_lines, strict=False):
                memo = str(record.get("memo") or "").strip()
                if not memo:
                    continue
                if peer:
                    memo = f"{memo}\n{peer}"
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

    live_us = user_space
    if live_us is None and str(memory_user or "").strip():
        from intelligence import userspace

        try:
            live_us = userspace.user_space(memory_user)
        except ValueError:
            # Audit probe / illegal id: skip live weekly, keep assembling tools.
            live_us = None
    return ResearchToolRegistry(
        tuple(specs),
        opening_prefetch=_opening_prefetch_evidence(
            frame,
            context,
            market_db_path,
            user_space=live_us,
            perspective_ids=tuple(perspective_ids),
            perspective_mode=perspective_mode,
        ),
    )


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
        from intelligence.services.tool_hunger import record_finance_query_rejected

        record_finance_query_rejected(spec, failure_code)
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
        **_finance_payload_kwargs(spec),
    )


def run_deterministic_fast_path(
    frame: TaskFrame,
    *,
    timeout: float,
    as_of: str | None = None,
) -> dict[str, object]:
    """Execute a preserved deterministic lane without entering AgentEpisode."""

    started = time.monotonic()
    if frame.question_type not in FAST_PATH_RUNNER_SUPPORTED_TYPES:
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
        as_of=as_of,
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
    resistance_text = "；".join(resistance_parts) or "当前没有高于收盘的可靠压力候选"
    support_text = "；".join(support_parts) or "暂无可靠支撑候选"
    header = (
        f"截至 {outcome.as_of}，{outcome.subject}收盘 {outcome.close:.2f}。"
        "按近期日线结构，"
    )
    if _market_technical_focus(frame.raw_question) == "support":
        answer = (
            f"{header}下方支撑为：{support_text}。"
            f"上方压力区：{resistance_text}。"
            f"{outcome.invalidation}"
        )
    else:
        answer = (
            f"{header}反弹空间先看上方压力区：{resistance_text}。"
            f"下方支撑为：{support_text}。"
            f"{outcome.invalidation}"
        )
    return {
        "execution_kind": "deterministic_fast_path",
        "status": "completed",
        "answer": answer,
        "as_of": outcome.as_of,
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
    "FAST_PATH_RUNNER_SUPPORTED_TYPES",
    "build_episode_registry",
    "is_deterministic_fast_path",
    "latest_market_date",
    "run_deterministic_fast_path",
]
