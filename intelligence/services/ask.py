"""Unified multi-source `ask` over the local knowledge graph + market 盘面 snapshot.

This is a deterministic *retrieval skeleton*: it routes a query to the matching
theme candidate (盘面/S source, read from the committed
``market_feature_store/exports/*-theme-candidates.json`` snapshot) and to the
knowledge graph (G/R sources, read live from the cross-repo knowledge base
``wiki/relations/*.json`` via :class:`KnowledgeAdapter`), optionally adds a
semantic recall path (W source — the knowledge-base hybrid 向量检索 selecting wiki
candidate pages via :mod:`intelligence.services.kb_rag`), then assembles a fixed
six-section answer with numbered citations.

No external LLM is required. The 结论 / 交易含义 sections are template-generated
placeholders meant to be refined by an LLM downstream; every factual line carries
a ``[S#]/[G#]/[R#]/[W#]`` citation back to its source.
"""

from __future__ import annotations

import copy
import glob
import json
import re
import statistics
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import date as date_cls, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from intelligence import userspace
from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.paths import default_paths
from intelligence.services import (
    agent_research,
    answer_model,
    evidence_providers,
    ask_clarify,
    ask_planner,
    evidence_registry,
    checkpoint_recall,
    closed_loop_retrieval,
    corrections,
    entity_anchor,
    experience_cards,
    external_market,
    forecast_preflight,
    kb_rag,
    l3_evidence,  # noqa: F401  (测试经 ask.l3_evidence 打桩)
    query_ledger,
    retrieval_cache,
    llm_refine,
    market_analogs,
    market_financials,
    market_regime_analogs,
    stock_analogs,
    task_fulfillment,
    market_midterm,
    market_moneyflow,
    market_capital,
    market_dragon,
    market_news,
    overnight_map,
    market_technical,
    market_timeseries,
    perspective_lab,
    research_brief,
    research_queue,
    retrieval_planner,
    generic_research_owner,
    research_task_planner,
    research_tool_registry,
    research_contract,
    user_memory,
    web_research,
)
from intelligence.services.answer_quality import (
    build_quality_context,
)
from intelligence.services.answer_orchestrator import (
    QUESTION_CONCEPT_DEFINITION,
    QUESTION_EXTERNAL_MARKET,
    QUESTION_FACT_CHECK,
    QUESTION_GENERAL,
    QUESTION_MARKET_FORECAST,
    QUESTION_MARKET_REVIEW,
    QUESTION_MARKET_TECHNICAL,
    QUESTION_NEWS_IMPACT,
    QUESTION_STOCK_DEEP_DIVE,
    QUESTION_THEME_ANALYSIS,
    QUESTION_VALUATION,
    QuestionPlan,
    plan_answer_question,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.query_understanding import market_review_requested_date
from intelligence.services.research_state import ResearchGap
from intelligence.services import event_transmission, evidence_gap_radar, market_structure, output_review, recall_audit, theme_lifecycle, valuation_gap
from intelligence.services.trading_calendar import (
    next_trading_day,
    trading_day_prompt_block,
)
from intelligence.services.theme_modules import (
    MODULE_BRIEF,
    MODULE_DEEP_DIVE,
    MODULE_FRONT_MAP,
    MODULE_MIGRATE,
    MODULE_REPLAY,
    MODULE_SCAN,
    route_modules,
    run_module,
)

from intelligence.services.ask_types import (  # noqa: F401  (re-export 兼容旧导入)
    DATA_REPO_ROOT,
    DEFAULT_EXPORTS_DIR,
    DEFAULT_STALE_DAYS,
    NO_EVIDENCE_NOTICE,
    REPO_ROOT,
    SECTION_ORDER,
    SUBHEAD,
    AskOptions,
    AskResult,
    Citation,
    PreparedAnswer,
    SynthesisDiagnostic,
    _contains,
    _data_repo_root,
    _llm_deadline,
    _normalize,
    _stage_timeout,
    _synthesis_timeout,
)
from intelligence.services.ask_blocks import (  # noqa: F401
    _append_block_outcome,
    _confidence_score,
    _customer_evidence_hardness_block_for_llm,
    _d_block_stat,
    _daily_market_overview_block_for_llm,
    _market_cause_window_block_for_llm,
    _evidence_chain_with_llm_wiki,
    _evidence_text_for_llm,
    _financials_block_for_llm,
    _is_market_index_comparison_query,
    _mainline_context_block_for_llm,
    _market_data_asof,
    _market_review_evidence_chain,
    _market_review_knowledge_anchor_block_for_llm,
    _market_review_mainline_context_block_for_llm,
    _market_value_block_for_llm,
    _populate_market_index_comparison,
    _quoted_topic,
    _second_derivative_queue_block_for_llm,
    _theme_research_framing,
    _valuation_block_for_llm,
)
from intelligence.services.evidence_window import (
    is_time_aligned_evidence,
    select_agent_evidence,
)
from intelligence.services.relation_guard import relation_edge_supported, relation_gap_text
from intelligence.services.ask_synthesis import (  # noqa: F401
    EXEMPLAR_DIR,
    _EXEMPLAR_PREFIX_BY_TYPE,
    _exemplar_guidance_for,
    _grounded_body_line_count,
    _stable_llm_fallback_reason,
    _strip_empty_grounded_sections,
    ensure_forecast_scenarios_visible as _ensure_forecast_scenarios_visible,
    ensure_track_contract_visible as _ensure_track_contract_visible,
    promote_daily_agent_grounded_answer,
    promote_grounded_answer,
    repair_unfulfilled_answer,
    synthesize_shadow_grounded_answer,
    _build_answer_spec_for_result,
    _build_base_answer_spec_from_sections,
    _claims_from_data_block,
    _prepare_answer_spec_synthesis,
    _presentable_lines,
    synthesize_prepared_answer,
)
from intelligence.services.ask_render import (  # noqa: F401
    render_answer,
    render_conversation_answer,
)


def _emit_progress(
    options: AskOptions,
    stage: str,
    status: str,
    detail: dict[str, object] | None = None,
) -> None:
    """Best-effort 控制面进度；可观测性故障不得改变研究结果。"""

    callback = options.progress_callback
    if callback is None:
        return
    try:
        callback(stage, status, dict(detail or {}))
    except Exception:  # noqa: BLE001 - telemetry sink 必须 fail-open
        return


def _perspective_active(options: "AskOptions") -> bool:
    """本轮是否带 KOL 视角（single/compare 且至少选了一个视角）。

    供 D6 门控放宽与检索 planner 的视角必选块共用同一判定，防两处各写一份漂移。
    """
    return (
        options.perspective_mode != perspective_lab.PERSPECTIVE_MODE_NEUTRAL
        and bool(options.perspective_ids)
    )


def _unique_citation_sources(citations: list[Citation]) -> list[str]:
    """Project public sources once; detailed tagged citations stay in ``citations``."""

    return list(
        dict.fromkeys(citation.source for citation in citations if citation.source)
    )


@contextmanager
def _progress_stage(
    options: AskOptions,
    stage: str,
    **initial_detail: object,
) -> Iterator[dict[str, object]]:
    """为同步 Ask 子阶段发 started/completed/failed 控制面事件。"""

    started = time.monotonic()
    detail = dict(initial_detail)
    _emit_progress(options, stage, "started", detail)
    try:
        yield detail
    except BaseException as exc:
        detail["elapsed_ms"] = max(
            0,
            round((time.monotonic() - started) * 1000),
        )
        detail["error_type"] = type(exc).__name__
        _emit_progress(options, stage, "failed", detail)
        raise
    else:
        detail["elapsed_ms"] = max(
            0,
            round((time.monotonic() - started) * 1000),
        )
        _emit_progress(options, stage, "completed", detail)


# Human-readable labels + 结论 summary prefixes for each routed recall backend.
MODULE_LABELS = {
    MODULE_BRIEF: "brief（产业维 · radar.py --mode brief 速览）",
    MODULE_FRONT_MAP: "front-map（产业维 · radar.py --mode front-map 前瞻信息地图）",
    MODULE_DEEP_DIVE: "deep-dive（产业维 · radar.py --mode deep-dive 题材深拆）",
    MODULE_REPLAY: "replay（时间维 · 模块7 发酵复盘）",
    MODULE_SCAN: "scan（横截面 · 模块4 全库横扫）",
    MODULE_MIGRATE: "migrate（横截面 · 模块8 横向迁移）",
}
MODULE_SUMMARY_PREFIX = {
    MODULE_BRIEF: "产业维定锚",
    MODULE_FRONT_MAP: "前瞻信息地图",
    MODULE_DEEP_DIVE: "深拆定锚",
    MODULE_REPLAY: "时间维发酵阶段",
    MODULE_SCAN: "全库横扫",
    MODULE_MIGRATE: "横向迁移标尺",
}




def _resolve_exports_dir(exports_dir: str | Path | None) -> Path:
    if exports_dir:
        return Path(exports_dir).expanduser()
    return DEFAULT_EXPORTS_DIR


def _snapshot_is_usable(path: Path) -> bool:
    """快照里有没有候选。文件名最新 ≠ 内容可用。

    盘面数据尚未同步时导出器仍会写出一个 found=False、candidate_count=0 的文件
    （warnings 全是 market daily row not found）。收盘到夜间管线跑完之间的每一天
    都会出现这种文件。"""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(doc, dict) or doc.get("found") is False:
        return False
    return bool(_all_candidates(doc))


def load_theme_candidates(exports_dir: str | Path | None, date: str | None) -> dict[str, Any]:
    """Load a theme-candidates export. Defaults to the latest *usable* date."""
    base = _resolve_exports_dir(exports_dir)
    skipped: list[str] = []
    if date:
        path = base / f"{date}-theme-candidates.json"
        if not path.exists():
            return {"found": False, "path": str(path), "warnings": [f"no export for {date}"], "doc": {}}
    else:
        matches = sorted(glob.glob(str(base / "*-theme-candidates.json")))
        if not matches:
            return {"found": False, "path": str(base), "warnings": ["no theme-candidates export found"], "doc": {}}
        # 从最新往回找第一个有候选的；空快照会被跳过并记名，让上层能说明"盘面快照是哪天"。
        path = Path(matches[-1])
        for candidate_path in reversed(matches):
            if _snapshot_is_usable(Path(candidate_path)):
                path = Path(candidate_path)
                break
            skipped.append(Path(candidate_path).name.replace("-theme-candidates.json", ""))
        else:
            # 全都是空的：退回最新，让下游照旧走"无候选"分支，但把原因说清楚。
            # json.loads 必须包起来：最新那个文件可能本身就是损坏的（_snapshot_is_usable
            # 已经吞掉过一次解析错误），裸调用会把 JSONDecodeError 抛出这个函数，
            # 而下面既有的读取路径一直是 try/except 返回 found=False 的。
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                return {"found": False, "path": str(path), "warnings": [str(exc)], "doc": {}}
            return {
                "found": True,
                "path": str(path),
                "warnings": [f"最近 {len(skipped)} 个盘面快照均无候选（{'、'.join(skipped[:5])}）"],
                "doc": doc,
            }
    # 盘面快照缓存：as_of=当日、revision=文件 mtime（导出重写即失效）。
    cache = retrieval_cache.shared_cache()
    try:
        revision = str(path.stat().st_mtime_ns)
    except OSError:
        revision = ""
    as_of = date_cls.today().isoformat()
    stale = (
        [f"盘面快照回退到 {path.name.replace('-theme-candidates.json', '')}（{'、'.join(skipped)} 尚无候选）"]
        if skipped
        else []
    )
    cached = cache.get("theme_candidates", str(path), as_of, revision)
    if cached is not None:
        # deepcopy：缓存值只读，防调用方原地改动污染后续 run。
        return {"found": True, "path": str(path), "warnings": stale, "doc": copy.deepcopy(cached)}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        return {"found": False, "path": str(path), "warnings": [str(exc)], "doc": {}}
    cache.put("theme_candidates", str(path), doc, as_of, revision)
    return {"found": True, "path": str(path), "warnings": stale, "doc": doc}


def _resolve_market_data_context(
    snapshot_date: str | None,
    market_db_path: str | Path | None,
    requested_date: str | None = None,
) -> tuple[str | None, str, str | None, list[str]]:
    if requested_date:
        from intelligence.services.market_watch_pack import exact_market_daily_exists

        exact = exact_market_daily_exists(market_db_path, requested_date)
        if exact is True:
            return requested_date, "requested_date", None, []
        if exact is False:
            return (
                None,
                "requested_date_missing",
                f"{requested_date} 无行情数据。",
                [],
            )
        return requested_date, "requested_date", None, []

    market_date = _market_data_asof(market_db_path)
    if market_date:
        warnings: list[str] = []
        if snapshot_date and snapshot_date != market_date:
            warnings.append(
                f"题材候选快照截至 {snapshot_date}，早于本地市场数据的 {market_date}；"
                "快照仅作辅助参考，不作为本轮整体数据日期。"
            )
        notice = (
            f"**数据截至 {market_date}。** 市场总览优先读取本地市场数据；"
            "日报导出和题材候选快照仅作补充，并按各自日期标注。"
        )
        return market_date, "duckdb", notice, warnings

    if snapshot_date:
        notice = (
            "**数据说明：本轮没有连接本地市场数据。** "
            f"以下使用截至 {snapshot_date} 的历史盘面快照，仅供辅助判断，"
            "不能视为最新交易日复盘。"
        )
        return snapshot_date, "snapshot_fallback", notice, [
            f"本轮没有连接本地市场数据，已使用截至 {snapshot_date} 的历史盘面快照。"
        ]

    notice = (
        "**数据说明：本轮没有连接本地市场数据，也没有可用的历史盘面快照。** "
        "本轮无法完成最新交易日复盘。"
    )
    return None, "unavailable", notice, [
        "本轮没有连接本地市场数据，也没有可用的历史盘面快照。"
    ]


def bind_market_watch_pack(
    options: AskOptions,
    *,
    frame: Any = None,
    query: str | None = None,
) -> AskOptions:
    """Run the market_watch pack before owner/model fork and lock AskOptions."""

    from intelligence.services.honesty_gates import calendar_disclosure
    from intelligence.services.market_watch_pack import run_market_watch_pack

    disclosure = calendar_disclosure(frame) if frame is not None else None
    # 替补观察探针仅在盘面题单点开启；weekly 五日包与一般题路径保持默认关
    # （spec 2026-08-25-substitute-observation-probe P1 另议）。
    pack = run_market_watch_pack(
        query or options.query,
        market_db_path=options.market_db_path,
        calendar_disclosure=disclosure,
        substitute_probes=True,
    )
    inject = pack.should_stop or not pack.market_daily_empty
    rendered = pack.render() if inject else ""
    supplemental = options.supplemental_evidence
    if rendered:
        supplemental = (
            f"{rendered}\n\n{options.supplemental_evidence}".strip()
            if options.supplemental_evidence
            else rendered
        )
    return replace(
        options,
        date=pack.standing_date if pack.standing_date is not None else options.date,
        compose=False if pack.should_stop else options.compose,
        synthesize=False if pack.should_stop else options.synthesize,
        supplemental_evidence=supplemental,
        market_watch_pack=pack,
    )


def bind_disclosure_scan_pack(
    options: AskOptions,
    *,
    frame: Any = None,
    query: str | None = None,
    as_of: str | None = None,
    cninfo_fetch: Any = None,
    clock: Any = None,
    sleep_fn: Any = None,
) -> AskOptions:
    """Run the disclosure scan pack and always lock compose/synthesize off."""

    from intelligence.services.disclosure_scan_pack import run_disclosure_scan_pack

    standing = as_of or options.date
    if standing is None and frame is not None:
        timeframe = str(getattr(frame, "timeframe", "") or "")
        if len(timeframe) == 10 and timeframe[4] == "-" and timeframe[7] == "-":
            standing = timeframe
    pack = run_disclosure_scan_pack(
        query or options.query,
        as_of=standing,
        market_db_path=options.market_db_path,
        cninfo_fetch=cninfo_fetch,
        clock=clock,
        sleep_fn=sleep_fn,
    )
    rendered = pack.render()
    supplemental = options.supplemental_evidence
    if rendered:
        supplemental = (
            f"{rendered}\n\n{options.supplemental_evidence}".strip()
            if options.supplemental_evidence
            else rendered
        )
    return replace(
        options,
        compose=False,
        synthesize=False,
        supplemental_evidence=supplemental,
        disclosure_scan_pack=pack,
    )


def v_block_for_ask(
    options: AskOptions,
    theme: str | None = None,
    entity: str | None = None,
) -> str:
    """[V] 投影：有 StancePack 只渲染袋，禁止再查台账。"""

    pack = getattr(options, "stance_pack", None)
    if pack is not None:
        from intelligence.services.stance_pack import render_prior_bag

        return render_prior_bag(
            pack.prior_bag,
            data_asof=_market_data_asof(options.market_db_path),
        )
    return checkpoint_recall.recall_block_for_query(
        options.query,
        theme,
        entity,
        user=options.user,
        data_asof=_market_data_asof(options.market_db_path),
    )


def bind_research_program(
    options: AskOptions,
    *,
    frame: Any = None,
    query: str | None = None,
) -> AskOptions:
    """Compile a ResearchProgram; market_watch still binds the four-bag pack first."""

    from intelligence.services.query_understanding import is_market_watch_query
    from intelligence.services.research_contract import compile_research_program

    text = query or options.query
    question_class = ""
    if frame is not None:
        question_class = str(getattr(frame, "question_type", "") or "")
    program = compile_research_program(text, question_class=question_class)
    _ = program.to_dict()
    if is_market_watch_query(text) or question_class == "market_watch":
        bound = bind_market_watch_pack(options, frame=frame, query=query)
        return replace(bound, research_program=program)
    from intelligence.services.market_watch_pack import (
        render_strict_signal_pack,
        run_strict_signal_pack,
    )

    hits = run_strict_signal_pack(
        program,
        query=text,
        market_db_path=options.market_db_path,
    )
    rendered = render_strict_signal_pack(hits)
    supplemental = options.supplemental_evidence
    if rendered:
        supplemental = (
            f"{rendered}\n\n{options.supplemental_evidence}".strip()
            if options.supplemental_evidence
            else rendered
        )
    return replace(
        options,
        research_program=program,
        supplemental_evidence=supplemental,
    )


def _forecast_preflight_for_options(
    options: AskOptions,
    market_doc: dict[str, Any],
    trade_date_override: str | None = None,
) -> dict[str, Any]:
    base = _resolve_exports_dir(options.exports_dir)
    trade_date = (
        options.date
        or trade_date_override
        or str(market_doc.get("trade_date") or "").strip()
    )
    path, payload = research_queue.load_research_queue(
        base,
        date=trade_date or None,
    )
    if path is None:
        source = str(base / f"{trade_date or '<latest>'}-research-queue.json")
        return forecast_preflight.build_forecast_preflight({}, source_artifact=source)
    if not payload:
        result = forecast_preflight.build_forecast_preflight({}, source_artifact=str(path))
        result["human_summary"] = "研究队列读取失败。"
        result["prompt_block"] = forecast_preflight.render_preflight_prompt(result)
        return result
    return forecast_preflight.build_forecast_preflight(payload, source_artifact=str(path))


def _all_candidates(doc: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(doc.get("candidates"), list):
        return [c for c in doc["candidates"] if isinstance(c, dict)]
    out: list[dict[str, Any]] = []
    for key in ("deep_candidates", "watch_candidates", "long_tail_candidates"):
        for c in doc.get(key, []) or []:
            if isinstance(c, dict):
                out.append(c)
    return out


def match_candidate(query: str, doc: dict[str, Any]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_score = 0
    for cand in _all_candidates(doc):
        score = 0
        for key in ("canonical_concept", "market_theme"):
            name = cand.get(key)
            if not name:
                continue
            if _normalize(name) == _normalize(query):
                score = max(score, 100)
            elif _contains(query, str(name)):
                score = max(score, 60)
        for mc in cand.get("matched_concepts", []) or []:
            name = mc.get("concept") if isinstance(mc, dict) else None
            concept_score = mc.get("score") if isinstance(mc, dict) else None
            if (
                name
                and isinstance(concept_score, (int, float))
                and concept_score >= 5
                and _contains(query, str(name))
            ):
                score = max(score, 30)
        if score > best_score:
            best_score, best = score, cand
    return best


def _evidence_is_stale(item: dict[str, Any], stale_days: int) -> bool:
    raw = str(item.get("source_date") or "")
    m = re.search(r"(\d{4})\D?(\d{2})\D?(\d{2})", raw)
    if not m:
        return False
    try:
        ev_date = date_cls(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return False
    return (date_cls.today() - ev_date).days > stale_days


# 生命周期回溯窗口：与 daily_agent 的 `lifecycle_dates` 取同一口径（最近 6 个有
# 候选快照的交易日），避免两条路径对同一题材算出不同阶段。
_LIFECYCLE_HISTORY_DAYS = 6


def _theme_lifecycle_stage(
    options: "AskOptions", candidate: dict[str, Any] | None
) -> str | None:
    """当前题材的逻辑生命周期阶段；拿不到就返回 None。

    **旧证据不等于失效。** 在 ``logic_lifecycle`` 的七阶段里，"旧"既可以通向
    「旧逻辑唤醒」（旧材料命中 + 盘面重新触发，是最高价值信号），也可以通向
    「衰退观察」/「证伪退出」——区分它们的是盘面时序（连续天数、优先级变化、
    强势股增减），不是日历天数。证据渲染此前只有 ``stale_days`` 一个天数阈值，
    把这三种相反的情况压成同一个「⚠️过期」，等于把机会标成风险。

    这里只取阶段名，判定逻辑仍归 ``logic_lifecycle`` 单点所有——daily_agent 与
    ask 必须共用同一套判据，否则又是两个各自自洽的词表。

    延迟导入：``logic_lifecycle`` 反向依赖 ``ask.load_theme_candidates``，
    模块级导入会成环。
    """
    if not candidate:
        return None
    try:
        from intelligence.services import logic_lifecycle
        from intelligence.services.logic_market_match import available_candidate_dates

        current_date = str(options.date or "")
        dates = [
            item
            for item in available_candidate_dates(options.exports_dir)
            if not current_date or item <= current_date
        ][-_LIFECYCLE_HISTORY_DAYS:]
        if not dates:
            return None
        history = logic_lifecycle.load_theme_history(
            options.exports_dir, dates, current_date or dates[-1]
        )
        theme = str(candidate.get("query") or candidate.get("theme") or "").strip()
        snapshot = logic_lifecycle.build_lifecycle_snapshot(
            candidate, history.get(theme) or []
        )
    except Exception:
        # 生命周期是增强信息，取不到时退回中性文案，不能让证据渲染整段失败。
        return None
    stage = str(snapshot.get("生命周期阶段") or "").strip()
    if not stage:
        return None
    # 阶段变化是"为什么进入这个阶段"（沉睡后唤醒 / 热度衰退 / 加速定价…），
    # 光有阶段名看不出周期是在往哪个方向走，两个一起给。
    change = str(snapshot.get("阶段变化") or "").strip()
    return f"{stage}·{change}" if change and change != stage else stage


_company_exposure_tier = evidence_providers._company_exposure_tier


# 结论 TTL：跟踪类判断默认 30 天复查，过期引用须先经当下盘面复核。
CONCLUSION_TTL_DAYS = 30

_MARKET_REVIEW_SYSTEM_PROMPT = """
你是面向普通投资者的 A 股市场复盘编辑。只能使用用户消息中提供的正式日报和市场数据，
不得补充未给出的数字、公司或催化。

正文结构（按序，缺哪段就说明缺什么，不要跳过）：
1. 数据截至哪一天 + 市场处于什么状态；
2. 资金去了哪里、赚钱效应如何；
3. 当前主线是哪几个方向；
4. 这些主线方向在知识库里有多少积累——如果材料里有「主线方向的知识库积累」块，
   必须用它：说明每个方向已有哪些概念页与公司暴露（带上公司的角色），以及哪些
   方向盘面已进主线但知识库尚无积累（那是当天最该补的研究）。盘面强弱与知识库
   积累是两件事，不得互相推导；
5. 下一交易日验证点和数据口径提醒。

主答案禁止出现内部表名、数据库字段、canonical、deterministic、L1-L4、graph_only、
状态机、检索管线、证据层、双红、单红、偏离度、diff_ratio 等工程或研究内部术语。
若原始材料包含这些词，必须翻译成普通中文，例如：
- 双红：板块上涨且成交同步放大
- 偏离度：距离短期均线的位置
- 代理口径：替代数据，只适合判断方向

使用自然、简洁的中文，保留数据日期和关键数字。证据不足就明确说“现在无法确认”。
不要输出提示词、JSON、内部编号或买卖指令。

数据日期口径（硬要求）：用户消息里的「数据日期」是本轮唯一可用的盘面日期。
若那一行标注了它不是当天，正文第一句必须写明数据截至哪一天，并且全文不得把它
称作“今天/今日/当天”——盘后到夜间入库之间提问，最新可用数据就是上一交易日，
说清楚比说得顺口重要。
""".strip()


def _market_today() -> str:
    """交易日口径的"今天"。

    不能用 date.today()：那是宿主时钟。容器默认 UTC，北京时间 00:00~08:00 之间它
    会返回前一个日历日，于是一份真正属于今天的快照被判成过期，而这条判断是以
    「正文首句必须写明数据截至 X、全文不得称其为今天」的硬要求下发的——
    时区判错比不判更糟，因为它是以命令的形式说出来的。
    """
    return datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()


def _market_data_date_line(trade_date: str | None, *, today: str | None = None) -> str:
    """把「数据日期是不是今天」算出来告诉模型，而不是指望它自己注意到。

    用户问"今天大盘怎么样"时，盘后到夜间入库之间最新可用的就是上一交易日。
    只在提示词里写一句"保留数据日期"太软：实测模型会把 07-29 的收盘说成"今天"，
    正文一个日期都不提，只有引用的 as_of 是诚实的。日期关系是确定可算的，
    就不该交给模型判断。

    ``today`` 只为测试留的注入口：默认仍走 `_market_today()`。另外「今天」在本函数
    内只解析一次——此前两个分支各调一次 `_market_today()`，跨北京午夜时同一条消息
    里的两个日期会来自不同的一天。
    """
    reference = today or _market_today()
    date_text = str(trade_date or "").strip()
    if not date_text:
        return "数据日期：未确认（没有可用盘面日期，不得给出任何当日定性）"
    if date_text == reference:
        return f"数据日期：{date_text}（即今天）"
    return (
        f"数据日期：{date_text}"
        f"（今天是 {reference}，因此这不是当日数据："
        f"正文首句必须写明「数据截至 {date_text}」，全文不得称其为今天/今日/当天）"
    )


def _conclusion_ttl_line(trade_date: str | None) -> str:
    until = ""
    m = re.search(r"(\d{4})\D?(\d{2})\D?(\d{2})", str(trade_date or ""))
    if m:
        try:
            until = (
                date_cls(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                + timedelta(days=CONCLUSION_TTL_DAYS)
            ).isoformat()
        except ValueError:
            until = ""
    suffix = f"（至 {until}）" if until else ""
    return f"观点有效期：建议 {CONCLUSION_TTL_DAYS} 天内复查{suffix}；过期引用本结论须先经当下盘面复核。"


def _answer_market_review(
    options: AskOptions,
    result: AskResult,
) -> AskResult:
    result.matched_theme = None
    result.candidate_tier = None
    result.priority_score = None
    pack = getattr(options, "market_watch_pack", None)
    if pack is not None:
        result.market_summary = pack.render()
        if pack.should_stop:
            result.trade_date = None if pack.market_daily_empty else pack.standing_date
            result.found_market = not pack.market_daily_empty
            result.answer_spec = _build_base_answer_spec_from_sections(
                result,
                theme="市场复盘",
                direct_lines=(pack.stop_text(),),
                evidence_blocks=(pack.render(),),
                risk_lines=(),
                action_lines=(),
            )
            return result
        mainline_context = ""
        knowledge_anchor = (
            _market_review_knowledge_anchor_block_for_llm(
                options.market_db_path,
                as_of=pack.standing_date or options.date or None,
                kb_wiki=options.kb_wiki or None,
                warnings=result.warnings,
            )
            if evidence_registry.provider_enabled(options, "MAINLINE_KB")
            else ""
        )
        if knowledge_anchor:
            result.citations.append(
                Citation(
                    "MAINLINE_KB",
                    "主线方向的知识库积累",
                    "按当日主线方向逐个取概念页/公司暴露/已入库证据；含知识库尚无积累的方向",
                )
            )
        evidence_parts = [
            part
            for part in (
                options.supplemental_evidence.strip(),
                result.market_summary or "",
                knowledge_anchor,
            )
            if part
        ]
        result.found_market = True
        if not options.compose:
            result.answer_spec = _build_base_answer_spec_from_sections(
                result,
                theme="市场复盘",
                evidence_blocks=tuple(evidence_parts),
                direct_lines=(
                    f"截至 {pack.standing_date}，"
                    "本轮只确认资料覆盖的市场变化，未覆盖部分保持未知。",
                ),
                risk_lines=(),
                action_lines=(
                    "下一交易日复核量能、涨跌结构和主线承接是否同时改善。",
                ),
            )
            return result
        result.answer_spec = _build_base_answer_spec_from_sections(
            result,
            theme="市场复盘",
            evidence_blocks=tuple(evidence_parts),
            direct_lines=(
                f"截至 {pack.standing_date}，"
                "本轮只确认资料覆盖的市场变化，未覆盖部分保持未知。",
            ),
            risk_lines=(),
            action_lines=(
                "下一交易日复核量能、涨跌结构和主线承接是否同时改善。",
            ),
        )
        return result
    result.market_summary = _daily_market_overview_block_for_llm(
        options.market_db_path
    )
    mainline_context = _market_review_mainline_context_block_for_llm(
        options.query,
        None,
        options.market_db_path,
    )
    # 第二条腿：盘面说哪个方向在走，知识库说我对这个方向研究到什么程度。
    # 缺了它，日常复盘就只有盘面数字，用户自己积累的概念页与公司暴露一条也进不来。
    knowledge_anchor = (
        _market_review_knowledge_anchor_block_for_llm(
            options.market_db_path,
            as_of=options.date or None,
            # kb_wiki 必须跟着走：同一个答案里其他知识库块都用 options.kb_wiki
            # 解析，这里漏传会让 eval/回测在钉住快照时读到实时 wiki。
            kb_wiki=options.kb_wiki or None,
            warnings=result.warnings,
        )
        if evidence_registry.provider_enabled(options, "MAINLINE_KB")
        else ""
    )
    if knowledge_anchor:
        result.citations.append(
            Citation(
                "MAINLINE_KB",
                "主线方向的知识库积累",
                "按当日主线方向逐个取概念页/公司暴露/已入库证据；含知识库尚无积累的方向",
            )
        )
    evidence_parts = [
        part
        for part in (
            options.supplemental_evidence.strip(),
            result.market_summary or "",
            mainline_context,
            knowledge_anchor,
        )
        if part
    ]
    result.found_market = bool(evidence_parts)
    if not evidence_parts:
        result.warnings.append("最新交易日的正式日报和市场数据均不可用")
        result.answer_spec = _build_base_answer_spec_from_sections(
            result,
            theme="市场复盘",
            direct_lines=("当前缺少最新交易日资料，无法形成可靠市场复盘。",),
            risk_lines=("缺最新市场总览与正式日报，任何当日判断都不可靠。",),
            action_lines=("补齐最新交易日市场总览和正式日报后重新复盘。",),
        )
        return result
    if not options.compose:
        result.answer_spec = _build_base_answer_spec_from_sections(
            result,
            theme="市场复盘",
            evidence_blocks=tuple(evidence_parts),
            direct_lines=(
                f"截至 {result.trade_date or options.date or '当前可用日期'}，"
                "本轮只确认资料覆盖的市场变化，未覆盖部分保持未知。",
            ),
            risk_lines=tuple(
                line
                for line in _presentable_lines(mainline_context)
                if any(token in line for token in ("缺", "未知", "滞后", "风险"))
            ),
            action_lines=(
                "下一交易日复核量能、涨跌结构和主线承接是否同时改善。",
            ),
        )
        return result

    prior_parts: list[str] = []
    if evidence_registry.provider_enabled(options, "M"):
        memory_block = user_memory.memory_block_for_query(
            options.query,
            user=options.user,
        )
        if memory_block:
            prior_parts.append(memory_block)
            result.citations.append(
                Citation(
                    "M",
                    "用户记忆检索块",
                    "历史判断与纠偏原则，仅作先验，不替代当前市场事实",
                )
            )
        user_space = userspace.user_space(options.user)
        cards, card_warning = experience_cards.load_cards(
            user_space.experience_cards_path,
            window=options.experience_cards_window,
        )
        if card_warning:
            result.warnings.append(card_warning)
        card_guidance = experience_cards.render_for_prompt(
            experience_cards.merge_cards_for_prompt(
                experience_cards.select_resident_cards(cards),
                experience_cards.select_relevant_cards(cards, options.query),
            )
        )
        corr_records, corr_warn = corrections.load_corrections(user_space.corrections_path)
        if corr_warn:
            result.warnings.append(corr_warn)
        resident_principles = corrections.render_for_prompt(
            corrections.select_resident_principles(corr_records)
        )
        if resident_principles:
            card_guidance = (
                f"{resident_principles}\n{card_guidance}".strip()
                if card_guidance
                else resident_principles
            )
        if card_guidance:
            prior_parts.append(
                "## 历史经验卡片（回答方法，不是市场事实）\n"
                f"{card_guidance}"
            )
    if evidence_registry.provider_enabled(options, "V"):
        recall_block = v_block_for_ask(options)
        if recall_block:
            prior_parts.append(recall_block)
            result.citations.append(
                Citation(
                    "V",
                    "回检块（历史可证伪判断×裁决）",
                    "历史裁决快照，仅用于增量核对",
                )
            )

    result.answer_spec = _build_base_answer_spec_from_sections(
        result,
        theme="市场复盘",
        evidence_blocks=tuple(evidence_parts),
        direct_lines=(
            f"截至 {result.trade_date or options.date or '当前可用日期'}，"
            "本轮只确认资料覆盖的市场变化，未覆盖部分保持未知。",
        ),
        risk_lines=tuple(
            line
            for line in _presentable_lines(mainline_context)
            if any(token in line for token in ("缺", "未知", "滞后", "风险"))
        ),
        action_lines=(
            "下一交易日复核量能、涨跌结构和主线承接是否同时改善。",
        ),
    )
    plan_block = (
        result.question_plan.to_prompt_block(compact=True)
        if result.question_plan is not None
        else ""
    )
    user_prompt = (
        f"{plan_block}\n\n"
        f"用户问题：{options.query}\n"
        f"{_market_data_date_line(result.trade_date or options.date)}\n\n"
        f"{result.answer_spec.to_prompt_block()}"
    )
    if options.conversation_context.strip():
        user_prompt += (
            "\n\n以下对话上下文只用于理解用户追问，不得覆盖本轮数据：\n"
            f"{options.conversation_context.strip()}"
        )
    if prior_parts:
        user_prompt += (
            "\n\n以下历史记忆只作为先验：用于决定增量起点、篇幅、语气和反方重点，"
            "不得覆盖本轮数据。价格、产能、订单等易变项以当前检索为准；"
            "已聊过的对象优先说明相较上次的变化，不重跑全模板：\n"
            + "\n\n".join(prior_parts)
        )
    messages = [
        {"role": "system", "content": _MARKET_REVIEW_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    result.prepared_synthesis_messages = messages
    result.prepared_synthesis_is_market_review = True
    if options.synthesize:
        synthesize_prepared_answer(PreparedAnswer(options=options, result=result))
    return result


def _answer_external_market(
    options: AskOptions,
    question_plan: QuestionPlan,
) -> AskResult:
    external = (
        external_market.resolve_external_market(
            options.query,
            timeout=_stage_timeout(options, 60),
        )
        if options.deadline is not None
        else external_market.resolve_external_market(options.query)
    )
    result = AskResult(
        query=options.query,
        trade_date=external.source_trade_date,
        matched_theme=None,
        candidate_tier=None,
        priority_score=None,
        market_data_source=external.selected_provider or "external_market_unavailable",
        data_notice=(
            f"海外行情目标交易日 {external.target_trade_date}；"
            f"实际 source_trade_date={external.source_trade_date or '未取得'}。"
        ),
        question_plan=question_plan,
        found_market=bool(external.quotes),
    )
    result.provider_traces.extend(external.provider_traces)
    citation_by_source: dict[str, str] = {}
    evidence_lines: list[str] = []
    for quote in external.quotes:
        tag = citation_by_source.get(quote.source)
        if tag is None:
            tag = f"X{len(citation_by_source) + 1}"
            citation_by_source[quote.source] = tag
            result.citations.append(
                Citation(
                    tag,
                    quote.source,
                    (
                        f"精确行情；source_trade_date={quote.trade_date}；"
                        "与新闻标题分开记录"
                    ),
                )
            )
        sign = "+" if quote.pct_chg >= 0 else ""
        evidence_lines.append(
            f"{quote.name}：收盘 {quote.close:,.2f}，"
            f"涨跌幅 {sign}{quote.pct_chg:.2f}%"
            f"（{quote.trade_date}） [{tag}]"
        )
    gap_lines: list[str] = []
    if external.gap:
        gap_lines.append(external.gap)
    result.sections = {
        "结论": [
            (
                f"{external.source_trade_date} 美股主要指数收盘数据如下。"
                if external.quotes
                else "本轮未取得可核验的美股收盘行情。"
            )
        ],
        "证据链": evidence_lines,
        "分歧反证": gap_lines,
        "后续验证点": [
            "需要盘中或当晚最新行情时，按完成交易时段重新拉取 finance quote。"
        ],
        "交易含义": [
            "本轮只回答海外指数本身，不用 A 股题材或本地 Wiki 代替外盘行情。"
        ],
        "数据源状态": [
            (
                f"{trace.provider}｜{trace.capability}｜{trace.status}"
                f"｜source_trade_date={trace.source_trade_date or '未记录'}"
                f"｜result_count={trace.result_count}"
                + (f"｜{trace.detail}" if trace.detail else "")
            )
            for trace in external.provider_traces
        ],
        "引用来源": [
            f"[{citation.tag}] {citation.source}：{citation.detail}"
            for citation in result.citations
        ],
    }
    result.warnings.extend(gap_lines)
    result.answer_spec = _build_base_answer_spec_from_sections(
        result,
        theme="海外市场",
        evidence_blocks=tuple(evidence_lines),
        direct_lines=tuple(result.sections["结论"]),
        risk_lines=tuple(
            gap_lines
            or ["行情仅反映已完成交易日收盘，不代表盘中或下一交易日走势。"]
        ),
        action_lines=tuple(result.sections["后续验证点"]),
    )
    return result


def _answer_market_technical(
    options: AskOptions,
    question_plan: QuestionPlan,
) -> AskResult:
    """指数/个股技术位：结构化 OHLCV 确定性计算，成功即停，失败 fail-closed。"""
    outcome = market_technical.resolve_market_technical(
        options.query,
        timeout=_stage_timeout(options, 15),
        as_of=options.date,
    )
    subject = outcome.subject
    result = AskResult(
        query=options.query,
        trade_date=None,
        matched_theme=None,
        candidate_tier=None,
        priority_score=None,
        market_data_source="tencent_kline",
        question_plan=question_plan,
    )
    if isinstance(outcome, market_technical.TechnicalGap):
        gap_text = market_technical.gap_answer_text(outcome)
        result.market_data_source = "market_technical_unavailable"
        result.data_notice = gap_text
        result.found_market = False
        result.warnings.append(f"market-technical：{outcome.reason}")
        result.provider_traces.append(
            ProviderTrace(
                provider="tencent_kline",
                capability="market_technical",
                status="failed",
                detail=outcome.reason,
            )
        )
        result.sections = {
            "结论": [gap_text],
            "证据链": [],
            "分歧反证": [],
            "后续验证点": ["数据源恢复后重新计算技术位。"],
            "数据源状态": [f"tencent_kline｜market_technical｜failed｜{outcome.reason}"],
        }
        result.answer_spec = _build_base_answer_spec_from_sections(
            result,
            theme=f"{subject}技术位",
            direct_lines=(gap_text,),
            risk_lines=("本轮未取得行情数据，任何点位判断都不可靠。",),
            presentation_kind="evidence_gap",
        )
        return result

    levels = outcome
    result.trade_date = levels.as_of
    result.found_market = True
    live_notice = ""
    if levels.live_quote is not None:
        live_notice = (
            f"当前盘中参考价 {levels.live_quote.price:.2f}"
            f"（{levels.live_quote.as_of}，未用于已确认技术位计算）。"
        )
    result.data_notice = (
        f"{levels.subject} 技术位计算基于截至 {levels.as_of} 的已完成日线，"
        f"来源腾讯行情 K 线接口（{levels.symbol}）；"
        f"{live_notice}支撑/压力为确定性计算结果。"
    )
    tag = "T1"
    fields = "OHLCV" if levels.volume_available else "OHLC"
    result.citations.append(
        Citation(
            tag,
            f"tencent_kline · {levels.symbol}",
            f"日线 {fields}；数据截止日={levels.as_of}；确定性技术位计算",
        )
    )
    result.provider_traces.append(
        ProviderTrace(
            provider="tencent_kline",
            capability="market_technical",
            status="success",
            source_trade_date=levels.as_of,
            result_count=len(levels.supports) + len(levels.resistances),
        )
    )
    close_line = f"{levels.subject} 已完成日线收盘 {levels.close:.2f}（{levels.as_of}） [{tag}]"
    if levels.live_quote is not None:
        close_line += f"；盘中参考价 {levels.live_quote.price:.2f}（未入计算）"
    evidence_lines = [close_line]
    ma_text = "、".join(
        f"{name}={value:.2f}" for name, value in levels.ma.items() if value is not None
    )
    if ma_text:
        evidence_lines.append(f"均线：{ma_text} [{tag}]")
    support_lines = []
    for index, level in enumerate(levels.supports, start=1):
        zone = (
            f"{level.zone_low:.2f}"
            if abs(level.zone_high - level.zone_low) < 1e-9
            else f"{level.zone_low:.2f}–{level.zone_high:.2f}"
        )
        support_lines.append(
            f"支撑{index}：{zone}（依据：{'；'.join(level.basis)}） [{tag}]"
        )
    resistance_lines = []
    for index, level in enumerate(levels.resistances, start=1):
        zone = (
            f"{level.zone_low:.2f}"
            if abs(level.zone_high - level.zone_low) < 1e-9
            else f"{level.zone_low:.2f}–{level.zone_high:.2f}"
        )
        resistance_lines.append(
            f"压力{index}：{zone}（依据：{'；'.join(level.basis)}） [{tag}]"
        )
    conclusion = (
        f"{levels.subject}（{levels.symbol}）截至 {levels.as_of} 收盘 "
        f"{levels.close:.2f}。下方支撑区（由近到远）："
        + ("；".join(
            f"{lv.zone_low:.2f}" + (
                f"–{lv.zone_high:.2f}" if abs(lv.zone_high - lv.zone_low) > 1e-9 else ""
            )
            for lv in levels.supports
        ) or "当前价下方无可靠支撑候选")
        + "。"
    )
    volume_line = levels.volume_confirmation or "成交量确认：最近完整日量能不足以形成独立判断。"
    result.sections = {
        "结论": [conclusion],
        "证据链": [*evidence_lines, *support_lines, *resistance_lines],
        "分歧反证": [levels.invalidation],
        "后续验证点": [
            f"回踩首个支撑区时复核量能；{volume_line}"
        ],
        "交易含义": [
            "技术位只回答位置问题，不构成买卖指令；结合量能与市场阶段使用。"
        ],
        "数据源状态": [
            f"tencent_kline｜market_technical｜success｜数据截止日={levels.as_of}"
        ],
        "引用来源": [
            f"[{citation.tag}] {citation.source}：{citation.detail}"
            for citation in result.citations
        ],
    }
    result.warnings.extend(levels.warnings)
    result.answer_spec = _build_base_answer_spec_from_sections(
        result,
        theme=f"{levels.subject}技术位",
        evidence_blocks=tuple(evidence_lines + support_lines + resistance_lines),
        direct_lines=(conclusion,),
        risk_lines=(levels.invalidation,),
        action_lines=tuple(result.sections["后续验证点"]),
        presentation_kind="market_technical",
    )
    return result


def _answer_concept_definition(
    options: AskOptions,
    question_plan: QuestionPlan,
) -> AskResult:
    resolved_kb_wiki = (
        Path(options.kb_wiki).expanduser()
        if options.kb_wiki
        else default_paths().knowledge_wiki
    )
    result = AskResult(
        query=options.query,
        trade_date=None,
        matched_theme=question_plan.query_envelope.subject,
        candidate_tier=None,
        priority_score=None,
        market_data_source="not_applicable",
        data_notice="本轮为概念定义与技术背景查询，不使用 A 股盘面材料补答。",
        question_plan=question_plan,
    )
    loop = closed_loop_retrieval.retrieve_closed_loop(
        options.query,
        anchor=None,
        total_seconds=_stage_timeout(
            options, closed_loop_retrieval.MAX_TOTAL_SECONDS
        ),
        retrieve=lambda retrieval_query: kb_rag.retrieve(
            retrieval_query,
            resolved_kb_wiki,
            k=options.wiki_rag_k,
            mode=options.wiki_rag_mode,
            timeout=_stage_timeout(options, options.wiki_rag_timeout),
            excerpt_chars=options.wiki_rag_excerpt,
            budget_query=options.query,
            index_dir=options.wiki_rag_index_dir,
            require_fresh=True,
            cache_scope=options.wiki_rag_cache_scope,
        ),
    )
    result.closed_loop_retrieval = loop
    result.wiki_rag_telemetry = loop.telemetry
    evidence_lines: list[str] = []
    needs_fresh_web = bool(
        re.search(
            r"(今天|今日|昨天|昨日|隔夜|最近|近期|最新|刚刚|本周|本月|"
            r"消息|新闻|进展|动态|现状)",
            options.query,
        )
    )
    if loop.conclusion:
        result.found_wiki = True
        result.found_graph = True
        result.provider_traces.append(
            ProviderTrace(
                provider="local_wiki",
                capability="concept_definition",
                status="success",
                detail="closed-loop relevance gate passed",
                result_count=len(loop.conclusion),
            )
        )
        for index, bucketed in enumerate(loop.conclusion[:4], start=1):
            hit = bucketed.hit
            tag = f"W{index}"
            result.citations.append(
                Citation(
                    tag,
                    f"knowledge-base · {hit.file_path}",
                    f"{hit.title}｜chunk={hit.best_chunk_id}",
                )
            )
            evidence_lines.append(f"{hit.title}：{hit.excerpt} [{tag}]")
    else:
        result.provider_traces.append(
            ProviderTrace(
                provider="local_wiki",
                capability="concept_definition",
                status="empty",
                detail="; ".join(loop.warnings) or "no relevant local evidence",
            )
        )
    if not loop.conclusion or needs_fresh_web:
        web_result = web_research.fetch_web_search(options.query)
        result.provider_traces.append(web_result.trace)
        for index, item in enumerate(web_result.items[:4], start=1):
            tag = f"E{index}"
            result.citations.append(
                Citation(tag, item.title, item.url)
            )
            evidence_lines.append(
                f"{item.title}：{item.snippet or '搜索结果未提供摘要'} [{tag}]"
            )
    else:
        result.provider_traces.append(
            ProviderTrace(
                provider=web_research.PROVIDER_BING_WEB,
                capability="general_web_search",
                status="not_attempted",
                detail="local knowledge satisfied relevance gate",
            )
        )
    gap_lines: list[str] = []
    if not evidence_lines:
        gap_lines.append(
            "本地知识库未命中，外部 Web Search 也未返回可用来源；"
            "未使用无关 A 股资料替代。"
        )
    result.sections = {
        "结论": [
            (
                f"已为“{question_plan.query_envelope.subject or options.query}”"
                "取得可核验的定义/背景来源。"
                if evidence_lines
                else "当前来源不足，暂不能给出可靠定义。"
            )
        ],
        "证据链": evidence_lines,
        "分歧反证": gap_lines,
        "后续验证点": [
            "如需投资映射，可在定义确认后另行查询产业链和 A 股暴露。"
        ],
        "交易含义": [
            "概念定义与市场交易判断分开处理，本轮不自动扩展公司名单。"
        ],
        "数据源状态": [
            (
                f"{trace.provider}｜{trace.capability}｜{trace.status}"
                f"｜source_trade_date={trace.source_trade_date or '未记录'}"
                f"｜result_count={trace.result_count}"
                + (f"｜{trace.detail}" if trace.detail else "")
            )
            for trace in result.provider_traces
        ],
        "引用来源": [
            f"[{citation.tag}] {citation.source}：{citation.detail}"
            for citation in result.citations
        ],
    }
    if not evidence_lines:
        result.warnings.extend(loop.warnings)
        result.warnings.extend(gap_lines)
    result.answer_spec = _build_base_answer_spec_from_sections(
        result,
        theme=question_plan.query_envelope.subject or "概念定义",
        evidence_blocks=tuple(evidence_lines),
        direct_lines=tuple(result.sections["结论"]),
        risk_lines=tuple(
            gap_lines
            or ["当前仅完成定义与背景核验，尚未验证产业链或投资映射。"]
        ),
        action_lines=tuple(result.sections["后续验证点"]),
    )
    return result


def answer_query(options: AskOptions) -> AskResult:
    # per-run DuckDB 只读连接复用：各 D 块/盘面查询借用同一连接的 cursor。
    # query_ledger：turn 内同 provider+query 检索只真实执行一次（orchestrator
    # 已开账本时嵌套复用；CLI 单跑时在本层兜底开启）。
    with _progress_stage(options, "ask_root"):
        with retrieval_cache.duckdb_run_pool(), query_ledger.query_ledger_scope():
            return _answer_query_impl(options)


def _market_cause_fallback_assessment(
    evidence: list[agent_research.AgentEvidence],
) -> str:
    """新闻/资金检索缺口时，用周内结构化数据给出可审计的机制判断。

    这是盘面机制，不把它升级成“某个事件导致下跌”；外部因果证据仍由
    completion report 保留为可选缺口。
    """
    details = [item.detail.strip() for item in evidence if item.detail.strip()]
    window = next((line for line in details if line.startswith("窗口：")), "该周窗口")
    window = window.split("；", 1)[0]
    index_line = next((line for line in details if line.startswith("上证指数：")), "指数周内走弱")
    pressure_line = next(
        (line for line in details if line.startswith("下跌交易日：")),
        "下跌交易日与亏钱效应数据有限",
    )
    index_line = index_line.rstrip("。；; ")
    pressure_line = pressure_line.rstrip("。；; ")
    return (
        f"从{window}的盘面证据看，本周下跌更符合风险偏好收缩、卖压集中释放的"
        f"市场机制，而不是已经核验出某一个单一外部事件。{index_line}；"
        f"{pressure_line}。这能解释指数走弱与亏钱效应扩散，但"
        "宏观、外盘或资金流向的具体触发因素仍缺少与该周逐日对齐的可回查证据。"
    )


def _mainline_current_fallback_assessment(
    evidence: list[agent_research.AgentEvidence],
) -> str:
    """在表达模型不可用时，从同日两项结构化事实生成最小直接回答。

    这不是替模型做开放式推理，而是把 D4 已明确给出的主线/边界和
    MARKET_DAILY 的盘面状态拼成可回查的判断，避免长尾问题退化成“已找到
    来源但不能判断”。任何无法确认的部分仍保持未知。
    """

    market_lines = [
        item.detail.strip()
        for item in evidence
        if item.tool == "market_data" and item.detail.strip()
    ]
    mainline_lines = [
        item.detail.strip()
        for item in evidence
        if item.tool == "mainline_context" and item.detail.strip()
    ]
    market_text = "；".join(market_lines[:2]) or "同日市场总览已取得"
    mainline_text = "；".join(mainline_lines[:3]) or "同日主线结构已取得"
    return (
        f"当前市场主线应以同日主线结构为准：{mainline_text}。"
        f"同日盘面总览显示：{market_text}。"
        "这能确认盘面正在交易的方向和强弱，但仅凭结构化盘面不能确认产业基本面或持续性；"
        "后续需用新的同日数据和公司/行业硬证据复核是否从短线异动演变为持续主线。"
    )


def _current_market_fact_fallback_assessment(
    evidence: list[agent_research.AgentEvidence],
) -> str:
    """Project one definition and its current measured fact without LLM prose."""

    details = [
        item.detail.strip()
        for item in evidence
        if item.tool == "mainline_context" and item.detail.strip()
    ]
    selected = [
        line
        for prefix in ("双红定义：", "双红数据截至：", "当前双红板块：")
        if (line := next((value for value in details if value.startswith(prefix)), ""))
    ]
    if selected:
        return "；".join(line.rstrip("。； ") for line in selected) + "。"
    return "；".join(details[:3]) or "当前市场指标数据未取得。"


def _market_forecast_fallback_assessment(
    evidence: list[agent_research.AgentEvidence],
) -> tuple[str, str, str, str]:
    """Use current structured breadth/volume facts to form bounded scenarios.

    The function makes a low-confidence *inference*, not a price prediction.  It
    exists so a provider timeout cannot turn a well-specified two-scenario task
    into an evasive “no view” template after the market truth was already read.
    """

    details = [
        agent_research.evidence_display_text(item)
        for item in evidence
        if item.tool == "market_data" and item.detail.strip()
    ]
    joined = "；".join(details)

    def number(pattern: str) -> float | None:
        match = re.search(pattern, joined)
        if match is None:
            return None
        try:
            return float(match.group(1))
        except (TypeError, ValueError):
            return None

    index_change = number(r"上证指数[^；。]*当日\s*([+-]?[\d.]+)%")
    amount_change = number(r"全市场成交额[^；。]*较前一日\s*([+-]?[\d.]+)%")
    limit_up = number(r"涨停\s*([\d.]+)\s*家")
    limit_down = number(r"跌停\s*([\d.]+)\s*家")
    down_stage = "下跌阶段" in joined

    if (
        down_stage
        and limit_down is not None
        and limit_up is not None
        and limit_down > max(30.0, limit_up * 1.5)
    ):
        base = (
            "基准判断（低置信度）：我更偏向弱势延续或冲高回落，而不是形成有广度的强反弹。"
            f"当前仍处下跌阶段，跌停 {limit_down:.0f} 家明显多于涨停 {limit_up:.0f} 家；"
            + (
                f"即使指数当日上涨 {index_change:.2f}%，也更像指数修复与个股卖压并存。"
                if index_change is not None and index_change > 0
                else "个股端卖压尚未显示已经充分收缩。"
            )
        )
    elif (
        index_change is not None
        and index_change > 0
        and amount_change is not None
        and amount_change > 0
    ):
        base = (
            "基准判断（低置信度）：我略偏向技术性反弹延续，但只按修复看待。"
            f"指数当日上涨 {index_change:.2f}%，成交较前一日增加 {amount_change:.2f}%，"
            "说明承接有所恢复；是否升级为趋势反转仍取决于市场广度。"
        )
    else:
        base = (
            "基准判断（低置信度）：更可能维持弱势震荡，暂不把单日波动解释成趋势反转。"
            "当前结构同时包含修复线索和未出清卖压。"
        )
    rebound = (
        "反弹情景：若下一交易日跌停家数明显收缩、上涨家数扩大，且成交没有在指数上行时萎缩，"
        "则技术性修复更可信；若只有权重拉指数、个股广度不改善，只算弱反抽。"
    )
    decline = (
        "继续下跌情景：若跌停继续扩散、上涨家数重新收缩，或放量但指数和主线同步走弱，"
        "说明卖压尚未出清，弱势延续的解释更占优。"
    )
    invalidation = (
        "失效条件：开盘后涨跌停结构、成交和指数方向与上述触发条件相反时，"
        "本轮基准判断失效，必须用下一交易日的新盘面重算。"
    )
    return "".join((base, rebound, decline, invalidation)), rebound, decline, invalidation


_FALLBACK_ASSESSMENT_LABELS = {
    "market_cause": "基于周内结构化数据的机制判断（外部触发因素仍待核验）：",
    "general_finance": "基于本轮已检索证据的初步判断（深度分析仍待补全）：",
}
_DEFAULT_ASSESSMENT_LABEL = "基于本轮已收集证据的判断："


def _assessment_label_for_fallback(kind: str | None) -> str:
    """按 fallback 种类选择降级标签。

    这里必须按种类分发，不能共用一句话：market_cause 的标签写死了「周内
    结构化数据」「外部触发因素」，那是原因题的语境。估值/公司分析题复用它
    会给出一个措辞完全错误的降级理由——比空白更糟，因为用户无法察觉。
    """

    if kind is None:
        return _DEFAULT_ASSESSMENT_LABEL
    return _FALLBACK_ASSESSMENT_LABELS.get(kind, _DEFAULT_ASSESSMENT_LABEL)


def _general_finance_fallback_assessment(
    evidence: list[agent_research.AgentEvidence],
    *,
    query: str,
) -> str:
    """当 agent loop 的 LLM 不可用时，从已检索证据拼出最小可审计判断。

    与 market_cause / mainline_current 等 fallback 同一思路：不替模型做
    开放式推理，只把已有的证据要点结构化地串成一句可回查的直接回答，
    让 completion gate 判 direct_assessment 为 fulfilled 而非 evidence_unbound。

    保守设计：只做证据摘要 + 明确标注「需进一步判断」，不编造数字或结论。
    """

    _MAX_ITEM_CHARS = 200
    details = [
        agent_research.evidence_display_text(item)[:_MAX_ITEM_CHARS]
        for item in evidence
        if item.detail.strip()
    ]
    if not details:
        return f"针对「{query}」，本轮已尝试检索但未取得可直接引用的证据材料。"
    # 取前 3 条证据摘要（每条至多 200 字），拼成可审计的 assessment
    top = details[:3]
    summary = "；".join(top)
    return (
        f"针对「{query}」，本轮检索到以下可回查材料：{summary}。"
        "以上证据为初步线索，模型的深度分析与条件化判断仍需后续补全。"
    )


def _filter_current_window_evidence(
    selected: list[agent_research.AgentEvidence],
    *,
    all_evidence: list[agent_research.AgentEvidence],
) -> list[agent_research.AgentEvidence]:
    """Keep structured truth and date-aligned external material for current claims."""

    market_dates: list[date_cls] = []
    for item in all_evidence:
        if item.tool != "market_data" or not item.source_date:
            continue
        try:
            market_dates.append(
                date_cls.fromisoformat(str(item.source_date)[:10].replace("/", "-"))
            )
        except ValueError:
            continue
    reference_date = max(market_dates, default=None)
    return [
        item
        for item in selected
        if item.tool in {"market_data", "mainline_context"}
        or is_time_aligned_evidence(item, reference_date=reference_date)
    ]


def _relation_gap_answer_spec(
    answer_spec: answer_model.AnswerSpec,
    gap_text: str,
) -> answer_model.AnswerSpec:
    """Fail closed when a relation question has no explicit graph edge."""
    theme = answer_spec.research_spec.theme
    gap = answer_model.make_claim(
        claim_id="relation:edge-gap",
        text=gap_text,
        claim_type="evidence_gap",
        theme=theme,
        status=answer_model.ClaimStatus.MISSING,
    )
    return answer_model.finalize_answer_spec(
        replace(
            answer_spec,
            summary=(gap,),
            verified_facts=(),
            company_table=(),
            counter_evidence=(),
            gaps=(gap,),
            triggers=(),
            candidate_facts=(),
            next_actions=("补齐图谱关系边或官方供应链证据后再判断上下游方向。",),
            presentation_kind="evidence_gap",
            presentation_title="关系证据缺口",
        )
    )


def _fact_check_counterparty(query: str, subject: str | None) -> str | None:
    """从“甲与乙是否合作”中抽取 subject 之外的合作方。"""

    text = re.sub(r"\s+", "", str(query or ""))
    match = re.search(
        r"([\u4e00-\u9fffA-Za-z0-9.]{2,24})(?:和|与|跟|及)"
        r"([\u4e00-\u9fffA-Za-z0-9.]{2,24}?)"
        r"(?:是否|有无|有没有|已经|已确认|确认|合作|供货|供应)",
        text,
    )
    if match is None:
        return None
    candidates = (match.group(1), match.group(2))
    normalized_subject = re.sub(r"\s+", "", str(subject or ""))
    return next(
        (
            item
            for item in candidates
            if item and item != normalized_subject
        ),
        None,
    )


def _official_relation_item_matches(
    item: l3_evidence.L3EvidenceItem,
    counterparty: str,
) -> bool:
    """L3 结果必须同时命中合作方和关系动词，避免无关公告充数。"""

    aliases = {counterparty.casefold()}
    if counterparty == "英伟达":
        aliases.update({"nvidia", "nvda"})
    text = f"{item.title} {item.summary} {item.raw}".casefold()
    relation_terms = ("合作", "供货", "供应", "客户", "订单", "合同", "认证", "定点")
    return any(alias in text for alias in aliases) and any(
        term in text for term in relation_terms
    )


def _answer_generic_owner(options: AskOptions) -> AskResult:
    """Ownerless 长尾入口：先运行 Agent 研究闭环，再构造候选证据 AnswerSpec。"""

    contract = options.research_task_contract
    assert contract is not None
    generic_question_plan = plan_answer_question(
        options.query,
        question_type_override=contract.question_type,
    )
    resolved_kb_wiki = (
        Path(options.kb_wiki).expanduser()
        if options.kb_wiki
        else default_paths().knowledge_wiki
    )
    knowledge = KnowledgeAdapter(wiki_root=resolved_kb_wiki)
    policy = research_contract.ResearchPolicy.for_tier(contract.research_tier)
    deadline = options.deadline or research_contract.ResearchDeadline.from_timeout(
        policy.total_seconds,
        synthesis_reserve=policy.synthesis_reserve,
    )
    context = research_contract.ResearchRunContext(
        contract=contract,
        deadline=deadline,
        policy=policy,
        trace_parent_id=contract.task_id,
        today=date_cls.today().isoformat(),
        latest_data_date=_market_data_asof(options.market_db_path),
    )
    # 只做一次极短的任务拆解。它影响 agent 的检索顺序说明，不改变契约的
    # 工具白名单、required outputs、档位或预算；调用时间也受同一 turn deadline
    # 钳制，避免 planner 变成隐藏的第二条研究循环。
    planner_timeout = max(
        1,
        min(
            research_task_planner.DEFAULT_TIMEOUT,
            int(context.deadline.stage_timeout(research_task_planner.DEFAULT_TIMEOUT)),
        ),
    )
    task_plan = research_task_planner.plan_task(
        contract.question,
        contract=contract,
        timeout=planner_timeout,
        # 无配置 provider 时直接走规则计划，不触碰测试/主循环注入的
        # completion callback；配置 provider 后才增加这一次受 deadline 钳制的
        # 短规划调用。
        enabled=llm_refine.detect_provider(options.llm_model) is not None,
    )

    def retrieve_kb(agent_query: str, timeout: float):
        return kb_rag.retrieve(
            agent_query,
            resolved_kb_wiki,
            k=options.wiki_rag_k,
            mode=options.wiki_rag_mode,
            timeout=min(timeout, options.wiki_rag_timeout),
            excerpt_chars=options.wiki_rag_excerpt,
            budget_query=options.query,
            index_dir=options.wiki_rag_index_dir,
            require_fresh=True,
            cache_scope=options.wiki_rag_cache_scope,
        )

    def _generic_market_data(
        agent_query: str,
        context: agent_research.AgentToolContext,
    ):
        """通用 Owner 的结构化行情工具。

        预测题固定预取“最新总览 + 多日窗口”，原因题仍使用归因窗口；两者
        都只输出可核验盘面事实，不把日报模板或方向判断伪装成证据。
        """
        if context.deadline.expired:
            raise TimeoutError("agent market data deadline expired")
        if contract.presentation_profile == "mainline_current":
            block = "\n".join(
                part
                for part in (
                    "## 当前市场总览结构化证据 [MARKET_DAILY]",
                    _daily_market_overview_block_for_llm(options.market_db_path),
                    "- 使用边界：这是同一最新交易日的盘面事实，不等于题材主线判断。",
                )
                if part
            )
            detail = "mainline_current_market_overview"
            source = "本地 DuckDB · MARKET_DAILY 同日市场总览"
        elif contract.question_type == QUESTION_MARKET_FORECAST:
            overview = _daily_market_overview_block_for_llm(options.market_db_path)
            window = _market_cause_window_block_for_llm(options.market_db_path)
            block = "\n".join(
                part
                for part in (
                    "## 预测所需结构化盘面证据 [MFORECAST]",
                    overview,
                    window,
                    "- 使用边界：以上仅为盘面事实；反弹/下跌情景必须另行绑定证据，不能由数据块自动推出。",
                )
                if part
            )
            detail = "market_forecast_overview_and_window"
            source = "本地 DuckDB · 预测盘面窗口"
        else:
            block = _market_cause_window_block_for_llm(options.market_db_path)
            detail = "weekly_market_cause_window"
            source = "本地 DuckDB · 周内市场归因窗口"
        evidence, observation = agent_research.block_lines_to_evidence(
            "market_data",
            block,
            source,
            limit=(18 if contract.question_type == QUESTION_MARKET_FORECAST else 12),
            detail_chars=700,
        )
        if contract.question_type == QUESTION_MARKET_FORECAST:
            # 预取行情必须直接进入同一个 ResearchState 的情景关系图。
            # 旧实现只存“context”，导致状态层认为反弹/下跌/失效三项全未
            # 覆盖，agent 被迫再搜与次日窗口无关的年度展望网页。
            tagged: list[agent_research.AgentEvidence] = []
            for item in evidence:
                text = item.detail
                supports: list[str] = []
                if any(term in text for term in ("上证指数", "全市场成交额", "强势股状态")):
                    supports.append("rebound_case")
                if any(term in text for term in ("下跌阶段", "涨跌结构", "跌停")):
                    supports.append("decline_case")
                if any(term in text for term in ("上证指数", "全市场成交额", "涨跌结构")):
                    supports.append("invalidation")
                tagged.append(
                    replace(item, supports=tuple(dict.fromkeys(supports)))
                )
            evidence = tagged
        trace = ProviderTrace(
            provider="agent:market_data",
            capability="agent_loop",
            status="success" if evidence else "empty",
            detail=detail,
            result_count=len(evidence),
        )
        return evidence, observation or "本地结构化市场数据无匹配", trace

    def _generic_mainline_context(
        agent_query: str,
        context: agent_research.AgentToolContext,
    ):
        """通用 Owner 的 D4 主线结构工具，保留同日/滞后边界。"""

        if context.deadline.expired:
            raise TimeoutError("agent mainline context deadline expired")
        block = _market_review_mainline_context_block_for_llm(
            options.query,
            contract.subject,
            options.market_db_path,
        )
        if "双红" in options.query:
            double_red_block = market_timeseries.latest_double_red_snapshot_block_for_llm(
                options.market_db_path
            )
            block = "\n".join(part for part in (double_red_block, block) if part)
        # A freshness/boundary block is useful for the gap explanation but is
        # not a mainline fact.  Returning it as ``mainline_context`` evidence
        # would make the fallback presenter promote “主线未知” to a completed
        # assessment merely because one source emitted a warning line.
        if not block or "当前交易日的题材级主线未知" in block:
            return (
                [],
                block or "同日主线结构无可用数据",
                ProviderTrace(
                    provider="agent:mainline_context",
                    capability="agent_loop",
                    status="empty",
                    detail="mainline_current_context_gap",
                    result_count=0,
                ),
            )
        evidence, observation = agent_research.block_lines_to_evidence(
            "mainline_context",
            block,
            "本地 DuckDB · D4 同日主线结构",
            limit=10,
            detail_chars=1000,
        )
        trace = ProviderTrace(
            provider="agent:mainline_context",
            capability="agent_loop",
            status="success" if evidence else "empty",
            detail="mainline_current_context",
            result_count=len(evidence),
        )
        return evidence, observation or "本地主线结构无匹配", trace

    tools = {
        **agent_research.build_default_tools(retrieve_kb),
        **agent_research.build_graph_tools(knowledge),
    }

    def _generic_l3_lookup(
        agent_query: str,
        context: agent_research.AgentToolContext,
    ):
        bundle = l3_evidence.lookup_l3_evidence(
            agent_query,
            generic_question_plan,
            "通用研究循环识别到客户/订单/量产等公司级硬证据缺口。",
            config=l3_evidence.L3LookupConfig.from_env(
                enabled=True,
                timeout=context.timeout(options.l3_lookup_timeout),
                limit=options.l3_lookup_limit,
            ),
            company_hint=contract.subject,
        )
        counterparty = _fact_check_counterparty(
            options.query,
            contract.subject,
        )
        evidence = [
            agent_research.AgentEvidence(
                tool="l3_lookup",
                title=item.title,
                detail=item.summary[:240],
                source=item.citation or item.source_type,
                source_date=(
                    match.group(0).replace("/", "-")
                    if (match := re.search(r"20\d{2}[-/]\d{1,2}[-/]\d{1,2}", f"{item.title} {item.summary}"))
                    else None
                ),
                evidence_tier="L3_official",
                independent_key=f"{item.source_type}:{item.title}",
            )
            for item in bundle.items[:6]
            if not counterparty
            or _official_relation_item_matches(item, counterparty)
        ]
        trace = ProviderTrace(
            provider="agent:l3_lookup",
            capability="agent_loop",
            status="success" if evidence else "empty",
            detail=agent_query[:120],
            result_count=len(evidence),
        )
        observation = (
            "；".join(f"{item.title}：{item.detail[:100]}" for item in evidence)
            or "官方证据无命中"
        )
        return evidence, observation, trace

    if "l3_lookup" in contract.allowed_capabilities:
        tools["l3_lookup"] = _generic_l3_lookup
    if contract.presentation_profile == "mainline_current" or contract.question_type == QUESTION_MARKET_FORECAST or (
        contract.question_type == "market_cause" and options.market_db_path is not None
    ):
        tools["market_data"] = _generic_market_data
    if contract.presentation_profile in {"mainline_current", "market_fact_current"}:
        tools["mainline_context"] = _generic_mainline_context
    registry = research_tool_registry.default_registry(tools)
    preloaded_items: list[agent_research.AgentEvidence] = []
    preloaded_trace_items: list[ProviderTrace] = []
    preloaded_gaps: list[ResearchGap] = []
    preloaded_observations: list[str] = []
    disabled_tool_names: list[str] = []
    if contract.presentation_profile == "mainline_current" and {
        "market_data",
        "mainline_context",
    }.issubset(registry.names()):
        # 当前主线是两个不同事实能力的组合：同日盘面总览（MARKET_DAILY）
        # 和题材/板块结构（D4）。两者都确定性预取，LLM 只负责综合与补
        # 反证；任何一个失败都留下 gap，不能被网页搜索替代。
        for tool_name, query, gap_id, description, source_capability in (
            (
                "market_data",
                "当前市场最新总览",
                "market_data_prefetch",
                "MARKET_DAILY 同日市场总览预取失败；当前盘面真值缺口不能由网页替代。",
                "market_data",
            ),
            (
                "mainline_context",
                "当前市场主线与板块结构",
                "mainline_context_prefetch",
                "D4 同日主线结构预取失败；当前主线不能由旧日报或网页替代。",
                "mainline_context",
            ),
        ):
            step_id = f"{contract.task_id}:owner:prefetch:{tool_name}"
            try:
                observation = registry.execute(
                    tool_name,
                    {},
                    context=context,
                    step_id=step_id,
                )
                preloaded_items.extend(observation.evidence)
                preloaded_trace_items.append(observation.trace)
                preloaded_observations.append(observation.observation)
                disabled_tool_names.append(tool_name)
                if not observation.evidence:
                    preloaded_gaps.append(
                        ResearchGap(
                            gap_id,
                            description,
                            blocks=tuple(item.output_id for item in contract.required_outputs),
                            suggested_capabilities=(source_capability,),
                        )
                    )
            except Exception as exc:
                detail = f"{type(exc).__name__}: {str(exc)[:160]}"
                preloaded_trace_items.append(
                    ProviderTrace(
                        provider=f"agent:{tool_name}",
                        capability="agent_loop",
                        status="request_error",
                        detail=detail,
                        result_count=0,
                        parent_id=contract.task_id,
                        step_id=step_id,
                    )
                )
                preloaded_observations.append(
                    f"{tool_name} 预取失败（{detail}）；不能用弱来源替代该必需能力。"
                )
                preloaded_gaps.append(
                    ResearchGap(
                        gap_id,
                        description,
                        blocks=tuple(item.output_id for item in contract.required_outputs),
                        suggested_capabilities=(source_capability,),
                    )
                )
                disabled_tool_names.append(tool_name)
    elif (
        contract.presentation_profile == "market_fact_current"
        and "mainline_context" in registry.names()
    ):
        step_id = f"{contract.task_id}:owner:prefetch:mainline_context"
        try:
            observation = registry.execute(
                "mainline_context",
                {},
                context=context,
                step_id=step_id,
            )
            preloaded_items.extend(observation.evidence)
            preloaded_trace_items.append(observation.trace)
            preloaded_observations.append(observation.observation)
            disabled_tool_names.append("mainline_context")
            if not observation.evidence:
                preloaded_gaps.append(
                    ResearchGap(
                        "current_market_fact_prefetch",
                        "当前市场指标数据未取得；不能用模型常识补写当前名单。",
                        blocks=tuple(item.output_id for item in contract.required_outputs),
                        suggested_capabilities=("mainline_context",),
                    )
                )
        except Exception as exc:
            detail = f"{type(exc).__name__}: {str(exc)[:160]}"
            preloaded_trace_items.append(
                ProviderTrace(
                    provider="agent:mainline_context",
                    capability="agent_loop",
                    status="request_error",
                    detail=detail,
                    result_count=0,
                    parent_id=contract.task_id,
                    step_id=step_id,
                )
            )
            preloaded_observations.append(
                f"当前市场指标预取失败（{detail}）；不能用模型常识替代。"
            )
            preloaded_gaps.append(
                ResearchGap(
                    "current_market_fact_prefetch",
                    "当前市场指标数据预取失败。",
                    blocks=tuple(item.output_id for item in contract.required_outputs),
                    suggested_capabilities=("mainline_context",),
                )
            )
            disabled_tool_names.append("mainline_context")
    elif contract.question_type in {"market_cause", QUESTION_MARKET_FORECAST} and "market_data" in registry.names():
        # 盘面是真值底座，不能由 agent 的工具选择顺序决定是否取得；预取后
        # 从可选工具中移除，避免固定管线与 agent loop 重复查盘。
        try:
            observation = registry.execute(
                "market_data",
                {},
                context=context,
                step_id=f"{contract.task_id}:owner:prefetch",
            )
            preloaded_items.extend(observation.evidence)
            preloaded_trace_items.append(observation.trace)
            preloaded_observations.append(observation.observation)
            # 已预取的工具不再交给 agent 二次选择，避免同一 turn 重复查盘。
            disabled_tool_names.append("market_data")
        except Exception as exc:
            # 真值底座失败与“正常无结果”不同：必须留下控制面 trace、给 agent
            # 可见的 observation 和 completion gap；同时仍禁用工具，避免 agent
            # loop 在同一 turn 对同一真值源重复调用。
            step_id = f"{contract.task_id}:owner:prefetch"
            detail = f"{type(exc).__name__}: {str(exc)[:160]}"
            preloaded_trace_items.append(
                ProviderTrace(
                    provider="agent:market_data",
                    capability="agent_loop",
                    status="request_error",
                    detail=detail,
                    result_count=0,
                    parent_id=contract.task_id,
                    step_id=step_id,
                )
            )
            preloaded_observations.append(
                f"结构化行情预取失败（{detail}）；本轮不能把网页或新闻替代为市场真值。"
            )
            preloaded_gaps.append(
                ResearchGap(
                    "market_data_prefetch",
                    "结构化行情预取失败；当前结论只能基于其他白名单来源，不能补足市场真值。",
                    blocks=tuple(item.output_id for item in contract.required_outputs),
                    suggested_capabilities=("market_data",),
                )
            )
            disabled_tool_names.append("market_data")
    if contract.presentation_profile == "relation" and "graph_lookup" in registry.names():
        # 关系题的第一步是确定性查显式图谱边。它不把公司/概念共现升级成
        # 关系结论；同时从 agent 可选工具中移除，避免固定预取与循环重复查询。
        try:
            relation_query = "；".join(
                item
                for item in (contract.subject or "", contract.question)
                if item
            )
            observation = registry.execute(
                "graph_lookup",
                relation_query,
                context=context,
                step_id=f"{contract.task_id}:owner:prefetch:relation",
            )
            preloaded_items.extend(observation.evidence)
            preloaded_trace_items.append(observation.trace)
            preloaded_observations.append(observation.observation)
            disabled_tool_names.append("graph_lookup")
        except Exception:
            # 图谱不可用时仍允许 evidence/web/news 补查，完成门禁会保留缺边。
            pass
    mandatory_l3 = any(
        output.required and output.evidence_types == ("l3_lookup",)
        for output in contract.required_outputs
    )
    if mandatory_l3 and "l3_lookup" in registry.names():
        # “是否已确认合作”属于 hard-fact 核验。官方证据工具是契约要求，
        # 不能把是否调用完全交给 soft planner，否则模型可能直接 finish。
        try:
            observation = registry.execute(
                "l3_lookup",
                contract.question,
                context=context,
                step_id=f"{contract.task_id}:owner:prefetch:l3",
            )
            preloaded_items.extend(observation.evidence)
            preloaded_trace_items.append(observation.trace)
            preloaded_observations.append(observation.observation)
            disabled_tool_names.append("l3_lookup")
        except Exception as exc:
            # 工具故障也由完成门禁表现为“尚不能确认”，不允许改用弱来源补硬结论。
            # 失败 trace 必须留在控制面，否则用户只看到 gap，运维侧却无法区分
            # “官方源无结果”和“官方源不可用”。
            preloaded_trace_items.append(
                ProviderTrace(
                    provider="agent:l3_lookup",
                    capability="agent_loop",
                    status="error",
                    detail=f"{type(exc).__name__}: {str(exc)[:160]}",
                    result_count=0,
                    parent_id=contract.task_id,
                    step_id=f"{contract.task_id}:owner:prefetch:l3",
                )
            )
    preloaded_evidence = tuple(preloaded_items)
    preloaded_traces = tuple(preloaded_trace_items)
    preloaded_observation = "\n".join(
        item for item in preloaded_observations if item
    )
    disabled_tools = tuple(dict.fromkeys(disabled_tool_names))
    if mandatory_l3 and not any(
        item.tool == "l3_lookup" for item in preloaded_evidence
    ):
        # “是否已确认合作”是 hard-fact 核验。唯一能满足契约的官方证据工具
        # 已经返回空或报错后，继续检索自媒体/普通网页只会增加延迟和污染候选池，
        # 不可能把 required L3 从 missing 变成 fulfilled，因此在此确定性停止。
        loop = agent_research.AgentLoopResult(
            evidence=list(preloaded_evidence),
            traces=list(preloaded_traces),
            sufficient=False,
            gaps=("官方合作关系硬证据未命中",),
            stop_reason="mandatory_l3_gap",
        )
        owner_result = generic_research_owner.GenericResearchResult(
            run_id=contract.task_id,
            contract=contract,
            loop=loop,
            completion=generic_research_owner.evaluate_completion(
                contract,
                loop,
            ),
            evidence=preloaded_evidence,
            task_plan=task_plan,
        )
    else:
        owner_result = generic_research_owner.run_generic_research(
            contract,
            context=context,
            registry=registry,
            run_id=contract.task_id,
            existing_evidence_summary=(
                f"任务档位={policy.tier}；可用工具={','.join(registry.names())}"
            ),
            preloaded_evidence=preloaded_evidence,
            preloaded_traces=preloaded_traces,
            preloaded_gaps=tuple(preloaded_gaps),
            preloaded_observation=preloaded_observation,
            disabled_tools=disabled_tools,
            task_plan=task_plan,
        )
    is_customer_fact_check = bool(
        contract.question_type == QUESTION_FACT_CHECK
        and any(
            item.output_id == "customer_validation"
            for item in contract.required_outputs
        )
    )
    counterparty = _fact_check_counterparty(options.query, contract.subject)
    has_relevant_l3 = any(
        item.tool == "l3_lookup" for item in owner_result.evidence
    )
    l3_attempted = any(
        trace.provider == "agent:l3_lookup" for trace in owner_result.traces
    )
    fallback_assessment_kind: str | None = None
    visible_evidence = select_agent_evidence(
        options.query,
        owner_result.evidence,
        max_chars=(10000 if contract.presentation_profile in {"mainline_current", "market_fact_current", "forecast"} else 6000),
        max_items=(18 if contract.presentation_profile in {"mainline_current", "market_fact_current", "forecast"} else 12),
    )
    if contract.question_type in {"market_cause", QUESTION_MARKET_FORECAST}:
        # 原因题只把结构化周内盘面和时间对齐的外部证据送入正文。
        # 预测题同理：旧年度展望可以留在 trace 供调试，但不能进入“明日”
        # 的 EvidenceAtom、引用抽屉或 Grounded Presenter。
        visible_evidence = _filter_current_window_evidence(
            list(visible_evidence),
            all_evidence=list(owner_result.evidence),
        )
    if (
        contract.question_type == "market_cause"
        and visible_evidence
        and not owner_result.loop.assessment.strip()
    ):
        owner_result.loop.assessment = _market_cause_fallback_assessment(
            visible_evidence
        )
        owner_result.loop.sufficient = True
        if owner_result.loop.research_state is not None:
            owner_result.loop.research_state.set_assessment(
                owner_result.loop.assessment
            )
            if not any(
                item.tool in {"web_search", "news_search"}
                and is_time_aligned_evidence(item)
                for item in owner_result.evidence
            ):
                owner_result.loop.research_state.add_gap(
                    "external_trigger",
                    "宏观、外盘或资金事件仍未取得与该周窗口对齐的证据",
                    blocks=("cause_attribution",),
                    suggested_capabilities=("web_search", "news_search"),
                )
        fallback_assessment_kind = "market_cause"
        owner_result = replace(
            owner_result,
            completion=generic_research_owner.evaluate_completion(
                contract, owner_result.loop
            ),
        )

    if (
        contract.question_type == QUESTION_GENERAL
        and not owner_result.loop.assessment.strip()
        and owner_result.evidence
    ):
        # 通用金融问题（估值、公司分析等）在 agent loop LLM 不可用时，
        # 如果已有证据，用证据摘要拼出最小可审计判断。不替模型做开放式
        # 推理，只让 completion gate 能判 direct_assessment 为 fulfilled，
        # 避免"有证据但不出回答"的空白降级。
        owner_result.loop.assessment = _general_finance_fallback_assessment(
            list(owner_result.evidence),
            query=options.query,
        )
        owner_result.loop.sufficient = True
        if owner_result.loop.research_state is not None:
            owner_result.loop.research_state.set_assessment(
                owner_result.loop.assessment
            )
        fallback_assessment_kind = "general_finance"
        owner_result = replace(
            owner_result,
            completion=generic_research_owner.evaluate_completion(
                contract, owner_result.loop
            ),
        )

    if (
        contract.presentation_profile == "mainline_current"
        and not owner_result.loop.assessment.strip()
        and any(item.tool == "market_data" for item in owner_result.evidence)
        and any(item.tool == "mainline_context" for item in owner_result.evidence)
    ):
        # 两项必需结构化能力均已成功时，LLM 只负责措辞；模型不可用不应
        # 把“有真值但没自然语言”误报成没有答案。
        owner_result.loop.assessment = _mainline_current_fallback_assessment(
            list(owner_result.evidence)
        )
        owner_result.loop.sufficient = True
        if owner_result.loop.research_state is not None:
            owner_result.loop.research_state.set_assessment(
                owner_result.loop.assessment
            )
        owner_result = replace(
            owner_result,
            completion=generic_research_owner.evaluate_completion(
                contract, owner_result.loop
            ),
        )

    if (
        contract.presentation_profile == "market_fact_current"
        and not owner_result.loop.assessment.strip()
        and any(item.tool == "mainline_context" for item in owner_result.evidence)
    ):
        owner_result.loop.assessment = _current_market_fact_fallback_assessment(
            list(owner_result.evidence)
        )
        owner_result.loop.sufficient = True
        if owner_result.loop.research_state is not None:
            owner_result.loop.research_state.set_assessment(owner_result.loop.assessment)
        owner_result = replace(
            owner_result,
            completion=generic_research_owner.evaluate_completion(
                contract, owner_result.loop
            ),
        )

    if (
        contract.question_type == QUESTION_MARKET_FORECAST
        and any(item.tool == "market_data" for item in owner_result.evidence)
        and (
            not owner_result.loop.assessment.strip()
            or owner_result.loop.sufficient is not True
        )
    ):
        # “无法给出概率”不等于“无法完成任务”。有当前盘面真值时，给出低
        # 置信度基准判断 + 双情景 + 失效条件，仍让最终 claim verifier 审核。
        assessment, _rebound, _decline, _invalidation = (
            _market_forecast_fallback_assessment(list(owner_result.evidence))
        )
        owner_result.loop.assessment = assessment
        owner_result.loop.sufficient = True
        if owner_result.loop.research_state is not None:
            owner_result.loop.research_state.set_assessment(assessment)

    if (
        contract.question_type == QUESTION_MARKET_FORECAST
        and owner_result.loop.research_state is not None
        and any(item.tool == "market_data" for item in owner_result.evidence)
    ):
        # These are conditional monitoring scenarios, not directional facts:
        # bind each one to the current breadth/volume observations so the
        # completion gate sees all required branches as grounded.
        #
        # 这段原本嵌在上面的兜底分支里，只有 agent loop **没能**给出判断时才执行。
        # 于是行为是反的：loop 失败 → 绑定 → coverage fulfilled → business_status
        # complete → 允许 LLM 合成；loop 成功 → 不绑定 → 三个情景假设一直是
        # uncovered → coverage partial → business_status gap → prepare_existing_answer
        # 直接把 synthesize 关掉，用户拿到的是确定性模板。研究做得越好，表达越差。
        #
        # 实测 run_20260731_031601_415738：六个必需输出全部 fulfilled，汇总却是
        # gap，全程没有调用过 LLM。绑定的是同一批 market_data 证据——预测情景本来
        # 就以当前盘面为依据，最终门禁 _evidence_supports_claim 对这三个 output 用
        # 的也正是这条规则。没有 market_data 时不绑定，仍然 fail closed。
        market_state_ids = tuple(
            evidence_id
            for evidence_id, observation in owner_result.loop.research_state.evidence.items()
            if observation.tool == "market_data"
        )
        for hypothesis_id in ("rebound_case", "decline_case", "invalidation"):
            owner_result.loop.research_state.bind_hypothesis_evidence(
                hypothesis_id,
                market_state_ids,
            )
        owner_result = replace(
            owner_result,
            completion=generic_research_owner.evaluate_completion(
                contract, owner_result.loop
            ),
        )

    result = AskResult(
        query=options.query,
        trade_date=max(
            (
                item.source_date
                for item in visible_evidence
                if item.source_date
            ),
            default=None,
        ),
        matched_theme=contract.subject,
        candidate_tier=None,
        priority_score=None,
        market_data_source="generic_research_owner",
    )
    result.question_plan = generic_question_plan
    has_structured_truth = any(
        item.tool in {"market_data", "mainline_context"}
        for item in visible_evidence
    )
    result.data_notice = (
        "本轮已执行官方公告/互动证据补查，但未取得能确认该合作关系的硬证据。"
        if is_customer_fact_check and not has_relevant_l3 and l3_attempted
        else "本轮官方证据补查未成功完成，不能确认该合作关系。"
        if is_customer_fact_check and not has_relevant_l3
        else
        ""
        if (
            has_structured_truth
            and (
                owner_result.completion.business_status == "complete"
                or contract.question_type == "market_cause"
            )
        )
        else "本轮已找到相关来源，但证据强度仍不足以独立确认结论。"
        if owner_result.evidence
        else "本轮没有收集到可回查来源，暂不形成可靠定性。"
    )
    # 完成报告属于控制面：编排层据此决定是否允许进入 grounded synthesis，
    # 但不把内部的 missing/gap 诊断直接暴露给用户正文。
    result.completion_report = owner_result.completion.to_dict()
    result.business_status = owner_result.completion.business_status
    result.provider_traces.extend(owner_result.traces)
    result.provider_traces.append(
        ProviderTrace(
            provider="generic_research_owner",
            capability="generic_research",
            status="success" if owner_result.evidence else "empty",
            detail=json.dumps(owner_result.to_dict(), ensure_ascii=False)[:1000],
            result_count=len(owner_result.evidence),
            parent_id=owner_result.run_id,
            step_id=f"{owner_result.run_id}:owner",
        )
    )

    evidence_ids: list[str] = []
    candidate_claims: list[answer_model.Claim] = []
    verified_claims: list[answer_model.Claim] = []
    evidence_lines: list[str] = []
    evidence_by_tag: dict[str, agent_research.AgentEvidence] = {}
    for index, item in enumerate(visible_evidence[:12], start=1):
        tag = f"G{index}"
        evidence_by_tag[tag] = item
        evidence_ids.append(tag)
        result.citations.append(
            Citation(
                tag,
                item.source,
                item.detail,
                content_hash=item.content_hash,
            )
        )
        evidence_text = agent_research.evidence_display_text(item)
        evidence_lines.append(f"{evidence_text} [{tag}]")
        is_structured_truth = item.tool in {"market_data", "mainline_context"}
        claim = answer_model.make_claim(
            claim_id=(
                f"generic:verified:{index}"
                if is_structured_truth
                else f"generic:candidate:{index}"
            ),
            text=evidence_text,
            claim_type="supporting_fact",
            theme=contract.subject or options.query,
            status=(
                answer_model.ClaimStatus.VERIFIED
                if is_structured_truth
                else answer_model.ClaimStatus.CANDIDATE
            ),
            evidence_tier=(
                item.evidence_tier or "L4_structured"
                if is_structured_truth
                else item.evidence_tier or "agent_candidate"
            ),
            evidence_ids=(tag,),
        )
        (verified_claims if is_structured_truth else candidate_claims).append(
            claim
        )

    forecast_fallback_text = ""
    assessment_text = ""
    if contract.presentation_profile == "forecast" and has_structured_truth:
        # 预测题不能因外部新闻为空而退化成“什么都不能判断”。结构化盘面
        # 足以支持条件化情景（不支持概率/确定性方向）；把每个情景绑定到
        # 同一批 market_data claim，仍由 grounded verifier 审核证据编号。
        market_pairs = [
            (tag, agent_research.evidence_display_text(item))
            for tag, item in evidence_by_tag.items()
            if item.tool == "market_data"
        ]
        market_ids = tuple(tag for tag, _text in market_pairs)
        (
            forecast_fallback_text,
            rebound,
            decline,
            invalidation,
        ) = _market_forecast_fallback_assessment(
            [item for item in evidence_by_tag.values() if item.tool == "market_data"]
        )
        for claim_id, text in (
            ("generic:rebound_case", rebound),
            ("generic:decline_case", decline),
            ("generic:invalidation", invalidation),
        ):
            candidate_claims.append(
                answer_model.make_claim(
                    claim_id=claim_id,
                    text=text,
                    claim_type="expectation",
                    theme=contract.subject or options.query,
                    status=answer_model.ClaimStatus.INFERRED,
                    evidence_tier="L4_structured",
                    evidence_ids=market_ids,
                )
            )

    if owner_result.loop.assessment.strip() and evidence_ids:
        assessment_label = _assessment_label_for_fallback(fallback_assessment_kind)
        assessment_text = (
            assessment_label
            + f"{owner_result.loop.assessment.strip()} "
            f"[{', '.join(evidence_ids)}]"
        )
        candidate_claims.append(
            answer_model.make_claim(
                claim_id="generic:assessment",
                text=assessment_text,
                claim_type=(
                    "cause_attribution"
                    if contract.question_type == "market_cause"
                    else "summary"
                ),
                theme=contract.subject or options.query,
                status=(
                    answer_model.ClaimStatus.INFERRED
                    if has_structured_truth
                    else answer_model.ClaimStatus.CANDIDATE
                ),
                evidence_tier="agent_assessment",
                evidence_ids=tuple(evidence_ids),
            )
        )
    elif forecast_fallback_text and evidence_ids:
        assessment_text = f"{forecast_fallback_text} [{', '.join(evidence_ids)}]"

    relationship_label = (
        f"{contract.subject}与{counterparty}"
        if contract.subject and counterparty
        else contract.subject or "双方"
    )
    fact_check_gap_summary = (
        f"尚不能确认{relationship_label}已建立可核验的直接合作关系。"
    )
    summary_text = (
        fact_check_gap_summary
        if is_customer_fact_check and not has_relevant_l3
        else
        assessment_text
        if owner_result.loop.assessment.strip() and evidence_ids
        else forecast_fallback_text
        if forecast_fallback_text and evidence_ids
        else "已找到相关来源，但目前只能作为线索，不能据此下确定结论。"
        if owner_result.evidence
        else "本轮没有收集到可回查来源，不能形成可靠定性。"
    )
    summary = answer_model.make_claim(
        claim_id="generic:summary",
        text=summary_text,
        claim_type="summary",
        theme=contract.subject or options.query,
        # A source list is not a direct assessment.  Do not attach the market
        # evidence IDs to the generic “已找到相关来源” sentence, otherwise the
        # final task gate can mistake a gap notice for a completed conclusion.
        status=(
            answer_model.ClaimStatus.MISSING
            if (
                is_customer_fact_check
                and not has_relevant_l3
            )
            or not (assessment_text or forecast_fallback_text)
            else answer_model.ClaimStatus.INFERRED
        ),
        evidence_ids=(
            ()
            if (
                is_customer_fact_check
                and not has_relevant_l3
            )
            or not (assessment_text or forecast_fallback_text)
            else tuple(evidence_ids)
        ),
    )
    # CompletionReport 是控制面对象；展示层只投影其业务含义。逐项 required
    # output 的标签能让“尚未完成”变成用户可理解的未知项，也避免把同一条
    # loop gap 为每个 output 重复渲染。情景/反证类 output 同时就是
    # ResearchState 的 hypothesis coverage，因此在这里统一呈现为待验证判断。
    hypothesis_output_ids = {
        item.hypothesis_id
        for item in (
            owner_result.loop.research_state.hypotheses
            if owner_result.loop.research_state is not None
            else ()
        )
    }
    incomplete_outputs = tuple(
        (required, output)
        for required, output in zip(
            contract.required_outputs,
            owner_result.completion.outputs,
        )
        if output.status != "fulfilled"
    )
    # Agent 的 finish.gaps 属于不可信输入：它可能把 contract/
    # completion/trace 等控制面术语原样放进用户正文。展示面只接受
    # 业务化的“缺什么证据”；命中内部诊断词时丢弃 detail，保留
    # RequiredOutput.description 这个由程序定义的稳定业务标签。
    control_plane_gap = re.compile(
        r"(?ix)(?:"
        r"required_outputs?|task_coverage|factual_grounding|causal_adequacy|"
        r"completion_report|research_?state|provider_?trace|"
        r"parent_?id|step_?id|run_?id|tool_?budget|trace|token_?budget|"
        r"allowed_capabilities|research_tier|presentation_profile"
        r")"
    )

    def business_gap_detail(raw: object) -> str:
        detail = " ".join(str(raw or "").split()).strip()
        if not detail or control_plane_gap.search(detail):
            return ""
        return detail[:180]

    typed_gap_texts = []
    for required, output in incomplete_outputs:
        prefix = (
            f"待验证情景“{required.description}”尚缺少可回查依据"
            if required.output_id in hypothesis_output_ids
            else f"“{required.description}”尚缺少可回查依据"
        )
        detail = business_gap_detail(output.gap)
        typed_gap_texts.append(f"{prefix}：{detail}" if detail else f"{prefix}。")
    raw_business_gaps = [
        detail
        for detail in (business_gap_detail(item) for item in owner_result.gaps)
        if detail
    ]
    gap_texts = typed_gap_texts or raw_business_gaps
    if is_customer_fact_check and not has_relevant_l3:
        gap_texts = [
            (
                "本轮已补查官方公告/互动证据，但未发现同时指向双方且明确表述"
                "合作、供货、订单或认证的可回查材料；缺少证据不等于合作不存在。"
            )
        ]
    elif contract.presentation_profile == "forecast" and forecast_fallback_text and evidence_ids:
        # 预测题的条件化情景已经由结构化盘面 presenter 生成并绑定 G*；
        # agent loop 可能仍因没有“直接预测证据”而返回 required-output gap。
        # 不能把这个控制面缺口原样抛到展示面，否则正文一边给出两种情景，
        # 一边又声称两种情景都缺失。保留真实边界，但改写成非阻断说明：
        # 没有独立方向预测，故不报概率，只给触发/失效条件。
        gap_texts = [
            "未取得可直接预测下一交易日方向的独立证据；以上仅为条件化情景，不给出概率。"
        ]
    if not gap_texts and owner_result.completion.status != "completed":
        gap_texts.append("当前判断尚缺少可核验证据。")
    gaps = tuple(
        answer_model.make_claim(
            claim_id=f"generic:gap:{index}",
            text=text,
            claim_type="evidence_gap",
            theme=contract.subject or options.query,
            status=answer_model.ClaimStatus.MISSING,
        )
        for index, text in enumerate(dict.fromkeys(gap_texts), start=1)
    )
    sources = tuple(
        answer_model.EvidenceRef(
            evidence_id=citation.tag,
            source=citation.source,
            detail=citation.detail,
            tier=(
                "L4_structured"
                if evidence_by_tag[citation.tag].tool in {"market_data", "mainline_context"}
                else "agent_candidate"
            ),
            source_date=evidence_by_tag[citation.tag].source_date,
        )
        for citation in result.citations
    )
    next_action = (
        "后续仅在公司公告、合同/订单、客户认证或双方官方披露出现时升级判断。"
        if is_customer_fact_check and not has_relevant_l3
        else (
            "下一验证窗口：关注下一次与"
            + "、".join(
                f"“{required.description}”"
                for required, _output in incomplete_outputs[:3]
            )
            + "直接相关的官方披露、定期报告或结构化数据更新；新材料出现后重新核验当前判断。"
        )
        if incomplete_outputs
        else "下一步验证：补充与问题直接相关的官方披露或数据，并检查是否改变当前判断。"
    )
    result.sections = {
        "结论": [summary_text],
        "证据链": evidence_lines,
        "分歧反证": gap_texts,
        "后续验证点": [next_action],
        "数据源状态": [],
        "引用来源": _unique_citation_sources(result.citations),
    }
    result.answer_spec = answer_model.finalize_answer_spec(
        answer_model.AnswerSpec(
            research_spec=answer_model.resolve_answer_profile(
                options.query,
                contract.subject,
                contract.presentation_profile,
            ),
            summary=(summary,),
            verified_facts=tuple(verified_claims),
            company_table=(),
            counter_evidence=(),
            gaps=gaps,
            triggers=(),
            candidate_facts=tuple(candidate_claims),
            next_actions=(next_action,),
            sources=sources,
            system_notices=((result.data_notice,) if result.data_notice else ()),
            presentation_kind=(
                "evidence_gap"
                if is_customer_fact_check and not has_relevant_l3
                else "generic_research"
            ),
            presentation_title=(
                "合作关系核验"
                if is_customer_fact_check
                else contract.subject or "通用研究"
            ),
            presentation_profile=contract.presentation_profile,
            # 把本轮的必需输出交给表达层，让 composer 能看到自己被按什么标准验收。
            # 在此之前，brief/compose 的 prompt 里只有「用户问题 + claim registry」，
            # required_outputs 一个字都没进去，而 task_fulfillment 又逐条按它判、
            # 判不过就把整份答案换成「请补充数据源」——模型是在一张它看不见的评分表
            # 上被打分。专项 owner 早就填了这个字段（research_owner 的 output_contract），
            # 只有 GenericResearchOwner 这条路一直是空的。
            #
            # render_prompt_constraint 在描述后追加该槽位「验收接受的措辞标记」：
            # 光给描述不够——门禁按 _MARKERS 的子串判 marker_absent，模型写出
            # 语义正确但不含标记词的正文照样判缺（08-01 C5：24 条证据全绑定仍被
            # 换成缺口模板）。词表真源在 task_fulfillment，这里不复制。
            prompt_constraints=tuple(
                task_fulfillment.render_prompt_constraint(required)
                for required in contract.required_outputs
                if required.required
            ),
        )
    )
    return result


def _exposure_coverage_summary(exposures: dict[str, Any]) -> dict[str, Any] | None:
    """送出去的那几家 vs 候选池整体的证据覆盖度分布。**只读**。

    为什么加这一项：待办 I（换了问题意图，选择器挑的名单会不会真的不同）原本
    只能靠人翻 trace 比名单，没有量纲。有了这两组中位数就有判据——shown 明显
    高于 pool 说明取舍确实在用信息量维度；两者贴近说明模型只是复述了标注顺序，
    选择器的价值没兑现。

    刻意不参与排序、不进正文：现在还没有「选得对不对」的判据，先把判据造出来，
    再谈要不要改行为（十原则 9.5：优化目标是可治理，不是更多）。
    """
    coverage = exposures.get("evidence_coverage") or {}
    by_company = coverage.get("by_company") or {}
    if not by_company:
        return None
    shown = [
        int(by_company.get(str(row.get("company") or ""), 0))
        for row in (exposures.get("items") or [])
    ]
    pool = [int(value) for value in by_company.values()]
    return {
        "indexed": bool(coverage.get("indexed")),
        "shown_median": statistics.median(shown) if shown else 0,
        "shown_zero": sum(1 for value in shown if value == 0),
        "shown_max": max(shown, default=0),
        "pool_size": len(pool),
        "pool_median": statistics.median(pool) if pool else 0,
        "pool_max": max(pool, default=0),
    }


def _revise_synthesis_on_warn(result: AskResult, options: AskOptions) -> None:
    """WARN 意见回灌同一段对话做一轮定向修订（修订版在前契约）。

    用户拿到可直接引用的修订版全文，审查意见退居「输出质检」附录；修订失败、被
    门禁拒绝、或修订版经展示层剔除后为空时，一律**保留初稿**并记录原因。
    """

    if not (
        options.compose_revise_on_warn
        and options.stream_text_delta is None
        and result.synthesis is not None
        and result.synthesis_messages is not None
        and result.review_gate is not None
        and result.review_gate.warn_count > 0
    ):
        return
    warn_notes = [
        f"{c.name}：{c.note}"
        for c in result.review_gate.checks
        if c.status == output_review.WARN and not c.advisory_only
    ]
    revision_user = {"role": "user", "content": llm_refine.gate_revision_user_content(warn_notes)}
    revised, rev_reason = llm_refine.synthesize_messages(
        result.synthesis_messages + [revision_user],
        model_override=options.llm_model,
        timeout=_synthesis_timeout(options, options.llm_timeout),
        deadline=_llm_deadline(options),
        temperature=0.2,
    )
    if revised is None:
        if rev_reason:
            result.warnings.append(f"质检 WARN 回灌修订失败，保留初稿：{rev_reason}")
        return
    proposed_revision = revised.answer
    revision_issues = answer_model.validate_llm_answer(
        proposed_revision,
        result.answer_spec,
    )
    if any(issue.severity == "error" for issue in revision_issues):
        result.warnings.extend(
            f"LLM 修订被 AnswerSpec 门禁拒绝：{issue.message}"
            for issue in revision_issues
            if issue.severity == "error"
        )
        return
    presented_revision = answer_model.present_llm_answer(
        proposed_revision,
        result.answer_spec,
    )
    # 绑定/术语闸是 warning，拦不住展示层把修订版抠成空串（无效 claim ID 行、含
    # 内部术语的行都会被丢掉）。这里覆盖的是**已经成型的初稿**，抠空就覆盖等于
    # 用空白顶掉一篇好答卷——空则保留初稿。
    if not presented_revision.strip():
        result.warnings.append(
            "质检 WARN 回灌修订版经展示层剔除后为空，保留初稿。"
        )
        return
    result.synthesis = (
        f"{result.data_notice}\n\n{presented_revision}"
        if result.data_notice
        else presented_revision
    )
    result.synthesis_messages = result.synthesis_messages + [
        revision_user,
        {"role": "assistant", "content": result.synthesis},
    ]
    result.warnings.append(
        f"输出质检 {len(warn_notes)} 条 WARN 已回灌定向修订（正文为修订版，审查意见见「输出质检」附录）"
    )


def _answer_query_impl(options: AskOptions) -> AskResult:
    if options.deadline is not None and options.deadline.expired:
        return _deadline_partial_result(options.query)
    if options.research_task_contract is not None:
        with _progress_stage(options, "generic_research_owner"):
            return _answer_generic_owner(options)
    if options.clarify:
        clarify_decision = ask_clarify.clarify_for_query(options.query)
        if clarify_decision.needs_clarification:
            result = AskResult(
                query=options.query,
                trade_date=None,
                matched_theme=None,
                candidate_tier=None,
                priority_score=None,
            )
            result.clarify = clarify_decision
            result.warnings.append(f"澄清追问：{clarify_decision.reason}，本次未检索")
            return result
    with _progress_stage(options, "planning") as stage:
        preliminary_plan = plan_answer_question(
            options.query,
            question_type_override=options.question_type_override,
        )
        stage["question_type"] = preliminary_plan.question_type
    if preliminary_plan.question_type == QUESTION_EXTERNAL_MARKET:
        with _progress_stage(options, "external_market"):
            return _answer_external_market(options, preliminary_plan)
    if preliminary_plan.question_type == QUESTION_MARKET_TECHNICAL:
        with _progress_stage(options, "market_technical"):
            return _answer_market_technical(options, preliminary_plan)
    if preliminary_plan.question_type == QUESTION_CONCEPT_DEFINITION:
        with _progress_stage(options, "concept_definition"):
            return _answer_concept_definition(options, preliminary_plan)
    with _progress_stage(options, "market_context") as stage:
        resolved_kb_wiki = (
            Path(options.kb_wiki).expanduser()
            if options.kb_wiki
            else default_paths().knowledge_wiki
        )
        knowledge = KnowledgeAdapter(wiki_root=resolved_kb_wiki)
        loaded = load_theme_candidates(options.exports_dir, options.date)
        doc = loaded["doc"] if loaded["found"] else {}
        candidate = match_candidate(options.query, doc) if doc else None
        snapshot_date = str(doc.get("trade_date") or "").strip() or None
        trade_date, market_data_source, data_notice, data_warnings = (
            _resolve_market_data_context(
                snapshot_date,
                options.market_db_path,
                requested_date=options.date,
            )
        )
        stage["snapshot_found"] = bool(loaded["found"])
        stage["candidate_found"] = candidate is not None
        stage["trade_date_available"] = trade_date is not None

    result = AskResult(
        query=options.query,
        trade_date=trade_date,
        matched_theme=(candidate or {}).get("canonical_concept") or (candidate or {}).get("market_theme"),
        candidate_tier=(candidate or {}).get("candidate_tier"),
        priority_score=(candidate or {}).get("priority_score"),
        next_trade_date=next_trading_day(trade_date, db_path=options.market_db_path),
        market_data_source=market_data_source,
        snapshot_date=snapshot_date,
        data_notice=data_notice,
    )
    result.warnings.extend(loaded.get("warnings", []))
    result.warnings.extend(data_warnings)
    result.found_market = candidate is not None
    question_plan = plan_answer_question(
        options.query,
        result.matched_theme,
        question_type_override=options.question_type_override,
    )
    result.question_plan = question_plan
    result.warnings.extend(f"answer-orchestrator：{w}" for w in question_plan.warnings)
    if question_plan.question_type == QUESTION_MARKET_REVIEW:
        with _progress_stage(options, "market_review"):
            return _answer_market_review(options, result)
    if _is_market_index_comparison_query(options.query):
        _populate_market_index_comparison(
            result,
            options.query,
            options.market_db_path,
        )
        result.answer_spec = _build_base_answer_spec_from_sections(
            result,
            theme="三指数对比",
        )
        return result
    if question_plan.question_type == QUESTION_MARKET_FORECAST:
        result.forecast_preflight = _forecast_preflight_for_options(
            options,
            doc,
            trade_date_override=result.trade_date,
        )
        if not result.forecast_preflight.get("can_generate_formal"):
            result.warnings.append(f"forecast-preflight：{result.forecast_preflight.get('human_summary')}")

    anchor: entity_anchor.EntityAnchor | None = None
    if options.use_entity_anchor:
        with _progress_stage(options, "entity_anchor") as stage:
            anchor = entity_anchor.resolve_entity_anchor(options.query, knowledge)
            stage["matched"] = anchor is not None
    result.anchored_entity = anchor
    if anchor is not None:
        result.warnings.extend(f"entity-anchor：{w}" for w in anchor.warnings)
        question_plan = plan_answer_question(
            options.query,
            result.matched_theme,
            question_type_override=options.question_type_override,
            anchor=anchor,
        )
        result.question_plan = question_plan
        if question_plan.base_finance_mode is not None:
            question_plan = replace(
                question_plan,
                base_finance_mode=replace(
                    question_plan.base_finance_mode,
                    require_market=True,
                    require_memory=True,
                ),
            )
            result.question_plan = question_plan
    claim_theme = (
        question_plan.research_spec.theme
        if question_plan.research_spec is not None
        else question_plan.query_envelope.subject
        or result.matched_theme
        or options.query
    )
    # 命中实体后，图谱/向量检索用「实体名+概念暴露」定锚，替代问题原文；未命中保持原文。
    graph_query = (
        anchor.graph_query
        if anchor is not None
        else question_plan.query_envelope.subject or options.query
    )

    citations: list[Citation] = []
    citations.extend(
        item
        for item in options.supplemental_citations
        if isinstance(item, Citation)
    )
    structured_claims: list[answer_model.Claim] = list(options.supplemental_claims)
    company_candidates: list[answer_model.CompanyCandidate] = []

    def cite(
        prefix: str,
        source: str,
        detail: str = "",
        *,
        chunk_id: str = "",
        content_hash: str = "",
        index_source_revision: str = "",
        index_freshness: str = "",
    ) -> str:
        n = sum(1 for c in citations if c.tag.startswith(prefix)) + 1
        tag = f"{prefix}{n}"
        citations.append(
            Citation(
                tag=tag,
                source=source,
                detail=detail,
                chunk_id=chunk_id,
                content_hash=content_hash,
                index_source_revision=index_source_revision,
                index_freshness=index_freshness,
            )
        )
        return f"[{tag}]"

    export_name = Path(loaded.get("path", "")).name

    # 全市场后市推演先消费 S/D 系列当前盘面与 D8 历史类比；无明确主题时，
    # 通用 wiki 语义召回既慢又容易把“市场”锚到无关公司。本车道确定性关闭 W，
    # 不影响题材/个股研究的 Hybrid RAG。
    evidence_options = (
        replace(options, use_wiki_rag=False)
        if question_plan.question_type == QUESTION_MARKET_FORECAST
        else options
    )
    evidence_ctx = evidence_providers.EvidenceContext(
        options=evidence_options,
        result=result,
        knowledge=knowledge,
        question_plan=question_plan,
        anchor=anchor,
        candidate=candidate,
        doc=doc,
        export_name=export_name,
        claim_theme=claim_theme,
        graph_query=graph_query,
        cite=cite,
        structured_claims=structured_claims,
        company_candidates=company_candidates,
        is_stale=lambda item: _evidence_is_stale(item, options.stale_days),
        confidence_score=_confidence_score,
        stage_timeout=lambda limit: _stage_timeout(options, limit),
        # 整轮只算一次：生命周期是题材级的，不随单条证据变化
        lifecycle_stage=_theme_lifecycle_stage(options, candidate),
    )

    # --- S / G / R: 盘面快照 / 图谱分层 / 证据索引（evidence_providers 插件层）---
    with _progress_stage(options, "market_snapshot") as stage:
        market_lines = evidence_providers.collect_market_snapshot(evidence_ctx)
        stage["result_count"] = len(market_lines)
    with _progress_stage(options, "graph") as stage:
        graph_bundle = evidence_providers.collect_graph(evidence_ctx)
        stage["concept_count"] = len(graph_bundle.concept_lines)
        stage["company_count"] = len(graph_bundle.company_lines)
    graph_concept_lines = graph_bundle.concept_lines
    concepts = graph_bundle.concepts_result
    exposures = graph_bundle.exposures_result
    company_lines = graph_bundle.company_lines
    relation_query = bool(
        {"relation", "company_mapping"}.intersection(
            question_plan.query_envelope.operators
        )
    )
    directional_relation_query = bool(
        relation_query
        and re.search(
            r"(?:上游|下游|产业链位置|处于.{0,8}环节)",
            options.query,
        )
    )
    relation_edge_gap = (
        relation_gap_text(options.query)
        if directional_relation_query
        and not relation_edge_supported(options.query, (exposures.get("items") or []))
        else ""
    )
    if directional_relation_query:
        result.provider_traces.append(
            ProviderTrace(
                provider="relation_graph_guard",
                capability="graph_relation",
                status="empty" if relation_edge_gap else "success",
                detail=(
                    relation_edge_gap
                    or "explicit graph role/chain-stage edge matched"
                ),
                result_count=(0 if relation_edge_gap else 1),
            )
        )
    if relation_edge_gap:
        # 缺显式关系边时答案已经确定为 gap。继续跑 Wiki、Web 和 LLM 既不能
        # 把“共现”升级为关系，反而会浪费预算并制造大量无意义降级。
        # 同理，未参与结论的题材候选快照日期差不应被记为本轮 degrade；
        # 完整数据日期仍留在市场上下文 trace，不污染关系题的终态。
        result.warnings = [
            warning
            for warning in result.warnings
            if not warning.startswith("题材候选快照截至")
        ]
        result.data_notice = relation_edge_gap
        result.sections = {
            "结论": [relation_edge_gap],
            "证据链": [],
            "分歧反证": ["概念或公司在同一材料中出现，不等于存在上下游关系。"],
            "后续验证点": ["补齐图谱关系边或官方供应链证据后再判断方向。"],
            "数据源状态": ["relation_graph_guard｜graph_relation｜empty"],
            "引用来源": [],
        }
        result.answer_spec = _build_base_answer_spec_from_sections(
            result,
            theme=claim_theme,
            direct_lines=(relation_edge_gap,),
            risk_lines=("共现只能作为待核线索，不能证明上下游方向。",),
            action_lines=("补齐图谱关系边或官方供应链证据后再判断方向。",),
            presentation_kind="evidence_gap",
        )
        return result
    company_evidence_concepts = graph_bundle.company_evidence_concepts
    tiers = graph_bundle.tiers
    with _progress_stage(options, "evidence_index") as stage:
        evidence_index_bundle = evidence_providers.collect_evidence_index(
            evidence_ctx, company_evidence_concepts
        )
        stage["result_count"] = len(evidence_index_bundle.lines)
    evidence_lines = evidence_index_bundle.lines
    stale_notes = evidence_index_bundle.stale_notes

    # --- W: 知识库 hybrid 向量召回（evidence_providers 插件层）---
    with _progress_stage(options, "wiki_rag") as stage:
        wiki_bundle = evidence_providers.collect_wiki_rag(
            evidence_ctx, company_evidence_concepts
        )
        stage["result_count"] = len(wiki_bundle.lines)
    wiki_lines = wiki_bundle.lines
    wiki_counter_lines = wiki_bundle.counter_lines
    wiki_llm_line_pairs = wiki_bundle.llm_line_pairs
    wiki_stats = wiki_bundle.stats

    # --- E: 外部 Web 检索（仅 general lane，且本地盘面/图谱/证据/wiki 全空时触发）---
    with _progress_stage(options, "web_fallback") as stage:
        web_fallback_lines, web_fallback_attempted = (
            evidence_providers.collect_web_fallback(
                evidence_ctx,
                local_lines_empty=(
                    not market_lines
                    and not graph_concept_lines
                    and not company_lines
                    and not evidence_lines
                    and not wiki_lines
                    and not wiki_counter_lines
                ),
            )
        )
        stage["attempted"] = web_fallback_attempted
        stage["result_count"] = len(web_fallback_lines)

    # --- A: agent 检索循环（L3）：LLM 自主决定补检索（ASK_AGENT_LOOP 灰度）---
    agent_loop_lines: list[str] = []
    agent_loop_result: agent_research.AgentLoopResult | None = None
    if agent_research.should_run(options.controller_capabilities):
        # 跨管线查询账本（QueryLedger 种子版）：把固定管线已执行过的检索
        # （closed-loop 各光圈查询、Web 兜底）交给 agent 去重并写进观察摘要，
        # 避免 agent 重发主链刚试过的查询浪费步数预算。
        pipeline_attempted: list[tuple[str, str]] = []
        if result.closed_loop_retrieval is not None:
            pipeline_attempted.extend(
                ("kb_search", attempt.query)
                for attempt in result.closed_loop_retrieval.attempts
            )
        if web_fallback_attempted:
            pipeline_attempted.append(("web_search", options.query))
        attempted_summary = (
            "；".join(
                f"{tool}(\"{attempted}\")"
                for tool, attempted in pipeline_attempted[:12]
            )
            or "（无）"
        )
        existing_summary = "\n".join(
            [
                f"盘面 {len(market_lines)} 条／图谱概念 {len(graph_concept_lines)} 条／"
                f"公司暴露 {len(company_lines)} 条／证据索引 {len(evidence_lines)} 条／"
                f"知识库召回 {len(wiki_lines)} 条",
                *wiki_lines[:3],
                f"主链已执行过的检索（重复会被拦截，请改写或换角度）：{attempted_summary}",
            ]
        )

        def _agent_l3_lookup(
            agent_query: str,
            context: agent_research.AgentToolContext,
        ):
            # 官方证据补查：与主链 L 源同一底层（公告/互动易），agent 可对
            # 自己发现的新实体主动补 L3 硬证据。
            bundle = l3_evidence.lookup_l3_evidence(
                agent_query,
                question_plan,
                existing_summary,
                config=l3_evidence.L3LookupConfig.from_env(
                    enabled=True,
                    timeout=min(
                        _stage_timeout(options, options.l3_lookup_timeout),
                        context.timeout(options.l3_lookup_timeout),
                    ),
                    limit=options.l3_lookup_limit,
                ),
            )
            l3_items = [
                agent_research.AgentEvidence(
                    tool="l3_lookup",
                    title=item.title,
                    detail=item.summary[:200],
                    source=item.citation or item.source_type,
                )
                for item in bundle.items[:6]
            ]
            observation = (
                "；".join(f"{item.title}：{item.detail[:80]}" for item in l3_items)
                or "官方证据无命中"
                + (
                    f"（缺口：{'、'.join(gap.reason for gap in bundle.gaps[:3])}）"
                    if bundle.gaps
                    else ""
                )
            )
            trace = ProviderTrace(
                provider="agent:l3_lookup",
                capability="agent_loop",
                status="success" if l3_items else "empty",
                detail=agent_query[:120],
                result_count=len(l3_items),
            )
            return l3_items, observation, trace

        def _agent_market_data(
            agent_query: str,
            context: agent_research.AgentToolContext,
        ):
            if context.deadline.expired:
                raise TimeoutError("agent tool deadline expired")
            # 本地盘面确定性取数：按意图路由 D0 时序 → D6 中期趋势 → 市场总览。
            block = ""
            source_label = ""
            ts_intent = market_timeseries.parse_timeseries_intent(agent_query)
            if ts_intent is not None:
                block = market_timeseries.timeseries_block_for_llm(
                    ts_intent, options.market_db_path
                )
                source_label = "本地 DuckDB · 盘面时序直查"
            if not block:
                mid_intent = market_midterm.parse_midterm_intent(agent_query)
                if mid_intent is not None:
                    block = market_midterm.midterm_trend_block_for_llm(
                        agent_query,
                        result.matched_theme or agent_query,
                        options.market_db_path,
                        mid_intent.window,
                    )
                    source_label = "本地 DuckDB · 多日中期趋势"
            if not block:
                block = _daily_market_overview_block_for_llm(
                    options.market_db_path
                )
                source_label = "本地 DuckDB · 市场总览"
            market_evidence, observation = agent_research.block_lines_to_evidence(
                "market_data", block, source_label
            )
            trace = ProviderTrace(
                provider="agent:market_data",
                capability="agent_loop",
                status="success" if market_evidence else "empty",
                detail=agent_query[:120],
                result_count=len(market_evidence),
            )
            return market_evidence, observation or "本地盘面数据无匹配", trace

        agent_tools: dict[str, agent_research.ToolRunner] = {
            **agent_research.build_default_tools(
                lambda agent_query, timeout: kb_rag.retrieve(
                    agent_query,
                    resolved_kb_wiki,
                    k=options.wiki_rag_k,
                    mode=options.wiki_rag_mode,
                    timeout=min(
                        _stage_timeout(options, options.wiki_rag_timeout),
                        timeout,
                    ),
                    excerpt_chars=options.wiki_rag_excerpt,
                    budget_query=options.query,
                    index_dir=options.wiki_rag_index_dir,
                    require_fresh=True,
                    cache_scope=options.wiki_rag_cache_scope,
                ),
            ),
            # P1-B 工具面扩展：agent 可查知识图谱与证据索引（纯本地），
            # 发现新实体后能自主定位公司映射、核对已登记证据。
            **agent_research.build_graph_tools(knowledge),
        }
        if evidence_providers.should_request_l3_lookup(
            options=options,
            question_plan=question_plan,
            local_evidence_text=existing_summary,
        ):
            agent_tools["l3_lookup"] = _agent_l3_lookup
        if options.market_db_path is not None:
            agent_tools["market_data"] = _agent_market_data
        with _progress_stage(
            options,
            "agent_loop",
            tool_count=len(agent_tools),
        ) as stage:
            agent_loop_result = agent_research.run_agent_loop(
                options.query,
                tools=agent_tools,
                existing_evidence_summary=existing_summary,
                total_seconds=_stage_timeout(options, 60),
                deadline=options.deadline,
                attempted_queries=tuple(pipeline_attempted),
            )
            stage["step_count"] = len(agent_loop_result.steps)
            stage["evidence_count"] = len(agent_loop_result.evidence)
            stage["gap_count"] = len(agent_loop_result.gaps)
        result.provider_traces.extend(agent_loop_result.traces)
        result.provider_traces.append(
            ProviderTrace(
                provider="agent_loop",
                capability="agent_research",
                status="success" if agent_loop_result.evidence else "empty",
                detail=json.dumps(
                    agent_loop_result.to_dict(), ensure_ascii=False
                )[:800],
                result_count=len(agent_loop_result.evidence),
            )
        )
        for item in agent_loop_result.evidence[:8]:
            tag = cite(
                "A",
                f"agent 补检索 · {item.tool}",
                item.source,
                content_hash=item.content_hash,
            )
            line = f"{item.title}：{item.detail} {tag}"
            agent_loop_lines.append(line)
            # P0 修复：agent 补检索证据同步铸 CANDIDATE claim。此前只进
            # evidence_chain 展示层、不进 registry——合成层在 AnswerSpec 白名单
            # 契约下无法合法引用，长尾 agent 花了预算却产出"死证据"。
            structured_claims.append(
                answer_model.make_claim(
                    claim_id=f"agent:{tag.strip('[]')}",
                    text=line,
                    claim_type="theme_evidence",
                    theme=claim_theme,
                    status=answer_model.ClaimStatus.CANDIDATE,
                    evidence_tier="agent_retrieval",
                )
            )

    # --- 模块 fan-out: route query to theme-radar 模式 as recall backends ---
    module_block: list[str] = []
    module_follow_ups: list[tuple[str, str]] = []
    module_summ: list[str] = []
    if options.use_modules:
        routed = route_modules(
            options.query,
            list(options.modules) if options.modules else None,
            question_type=question_plan.question_type,
            subject_kind=question_plan.query_envelope.subject_kind,
        )
        result.routed_modules = list(routed)
        for name in routed:
            with _progress_stage(options, "module", module=name) as stage:
                mr = run_module(
                    name,
                    graph_query,
                    resolved_kb_wiki,
                    _stage_timeout(options, options.module_timeout),
                )
                stage["ok"] = mr.ok
                stage["highlight_count"] = len(mr.highlights)
            module_block.append(f"{SUBHEAD}模块·{MODULE_LABELS.get(name, name)}")
            if mr.ok and mr.highlights:
                result.found_graph = True
                tag = cite("G", mr.citation_source, f"{mr.command}" + (f" | {mr.citation_detail}" if mr.citation_detail else ""))
                for hl in mr.highlights:
                    module_block.append(f"{hl} {tag}")
                    # 模块召回同样进 candidate 通道，合成层可按待验证口吻引用。
                    structured_claims.append(
                        answer_model.make_claim(
                            claim_id=f"module:{name}:{len(structured_claims)}",
                            text=f"{hl} {tag}",
                            claim_type="theme_evidence",
                            theme=claim_theme,
                            status=answer_model.ClaimStatus.CANDIDATE,
                            evidence_tier="module_recall",
                        )
                    )
                module_follow_ups.extend((name, f) for f in mr.follow_ups)
                if options.detail and mr.full_report:
                    result.detail_reports.append((MODULE_LABELS.get(name, name), mr.full_report))
                if mr.title:
                    t = mr.title[:28] + ("…" if len(mr.title) > 28 else "")
                    module_summ.append(f"{MODULE_SUMMARY_PREFIX.get(name, name)}「{t}」")
            else:
                reason = mr.warning or "无产出"
                module_block.append(f"（{name} 模块未接入产出：{reason}）")
                result.warnings.append(f"模块 {name}：{reason}")

    framing = _theme_research_framing(
        question_plan.research_spec,
        result.matched_theme,
    )
    if question_plan.research_spec is not None:
        structured_claims.append(
            answer_model.make_claim(
                claim_id="ontology:definition",
                text=question_plan.research_spec.definition,
                claim_type="theme_definition",
                theme=claim_theme,
                status=answer_model.ClaimStatus.INFERRED,
                evidence_tier="research_ontology",
                evidence_ids=("ONTOLOGY",),
            )
        )
        structured_claims.extend(
            answer_model.make_claim(
                claim_id=f"ontology:chain:{index}",
                text=stage,
                claim_type="industry_chain",
                theme=claim_theme,
                status=answer_model.ClaimStatus.INFERRED,
                evidence_tier="research_ontology",
                evidence_ids=("ONTOLOGY",),
            )
            for index, stage in enumerate(question_plan.research_spec.chain_stages, start=1)
        )

    # --- gaps / contradictions ---
    gap_lines: list[str] = []
    is_market_forecast = (
        question_plan.question_type == QUESTION_MARKET_FORECAST
    )
    ks = (candidate or {}).get("knowledge_status") or {}
    gaps = ks.get("backfill_gaps") or []
    if gaps and not is_market_forecast:
        gap_lines.append(f"盘面候选标记缺口：{'、'.join(map(str, gaps))}（图谱覆盖不足，证据待补）")
    if not result.found_graph and not is_market_forecast:
        gap_lines.append("知识图谱未命中该词：可能是新词/别名未登记，建议先 concept-ingest 或 disclosure-archive 补证")
    if relation_edge_gap and not is_market_forecast:
        gap_lines.append(relation_edge_gap)
    # 先交代总量再交代分层。否则下面两条「N 家…」会被读成全集：实测「固态电池」
    # 图谱匹配 86 家、正文只写 12 家，而正文对此一字未提。
    exposure_shown = len(exposures.get("items") or [])
    exposure_total = int(exposures.get("total_matched") or exposure_shown)
    result.graph_exposure_telemetry = {
        "matched": exposure_total,
        "shown": exposure_shown,
        "truncated": bool(exposures.get("truncated")),
        # 这 12 家是模型按问题意图挑的还是确定性排序切的、以及回退时是为什么。
        # 没有这一项就只知道「截断了」，不知道「按什么截的」。
        "selector": exposures.get("selector") or None,
        "evidence_coverage": _exposure_coverage_summary(exposures),
    }
    if (
        exposures.get("truncated")
        and exposure_total > exposure_shown
        and not is_market_forecast
    ):
        # 取舍口径必须跟这一轮**实际走的路径**一致。选择器跑通了却说「按暴露强度
        # 取前 N 家、同档按名称排序」，就是留证在说假话——比不留证更糟。
        selector = exposures.get("selector") or {}
        if selector.get("mode") == "llm":
            backfilled = int(selector.get("backfilled") or 0)
            how = (
                f"本轮由模型从 {selector.get('candidate_count') or exposure_total} 家候选中"
                f"按问题意图挑出 {int(selector.get('llm_selected') or 0)} 家"
                + (f"、另按暴露强度补齐 {backfilled} 家" if backfilled else "")
            )
            tail = "要完整名单请指定公司或收窄题材"
        else:
            how = f"本轮按暴露强度取前 {exposure_shown} 家"
            tail = (
                "同强度同置信的公司之间按名称排序取舍，要完整名单请指定公司或收窄题材"
            )
        gap_lines.append(
            f"图谱共匹配 {exposure_total} 家公司，{how}写入正文；"
            f"其余 {exposure_total - exposure_shown} 家未展示，不代表不存在——{tail}"
        )
    if tiers["peripheral"] and not is_market_forecast:
        gap_lines.append(
            f"{len(tiers['peripheral'])} 家公司为 graph_only/低置信暴露，属预期差待证伪区，不宜直接作为基本面依据"
        )
    if tiers["other"] and not is_market_forecast:
        gap_lines.append(
            f"{len(tiers['other'])} 家公司仅有间接或候选证据，未达到公司级硬证据门槛，不得升级为核心受益。"
        )
    gap_lines.extend(framing.get("gaps", []))
    gap_lines.extend(stale_notes)
    gap_lines.extend(wiki_counter_lines)
    if evidence_index_bundle.counter_disclosure and not wiki_counter_lines:
        gap_lines.append(evidence_index_bundle.counter_disclosure)
    # KC-07：装配完成后跑召回自评四问，只披露不补搜。只看检索窗
    # （R/W/G/外部/agent），不扫 framing/缺口/D 块，避免本体页里的「产业链」
    # 冒充关系命中。
    recall_as_of = recall_audit.parse_as_of(
        result.trade_date, options.date, _market_today()
    ) or date_cls.today()
    gap_lines.extend(
        recall_audit.audit_recall(
            [
                *evidence_lines,
                *wiki_lines,
                *wiki_counter_lines,
                *graph_concept_lines,
                *company_lines,
                *web_fallback_lines,
                *agent_loop_lines,
            ],
            as_of=recall_as_of,
        ).disclosure_lines()
    )
    if agent_loop_result is not None:
        gap_lines.extend(
            f"agent 检索后仍缺：{gap}" for gap in agent_loop_result.gaps
        )
        if agent_loop_result.sufficient is False and not agent_loop_result.gaps:
            gap_lines.append("agent 检索判定证据不足，未能补齐关键数据")
    if web_fallback_attempted and not web_fallback_lines:
        gap_lines.append(
            "本地盘面/图谱/知识库均未命中，外部 Web Search 也未返回可用来源；"
            "未用无关资料替代。"
        )
    if (
        is_market_forecast
        and result.forecast_preflight is not None
        and not result.forecast_preflight.get("can_generate_formal")
    ):
        gap_lines.append(
            "后市推演前置查漏："
            + str(
                result.forecast_preflight.get("human_summary")
                or "研究缺口尚未补齐。"
            )
        )
    gap_lines.append(
        "Temporal Facts 层尚未接入：以上证据仅按 source_date 标注新鲜度；"
        "正式版应把会过期/被证伪的事实建成带 status(active/superseded/invalidated) 的时序边"
    )
    quality_context = build_quality_context(
        evidence_lines=evidence_lines + graph_concept_lines + company_lines + wiki_lines + module_block,
        market_lines=market_lines,
        gap_lines=gap_lines,
    ).compact_for(
        question_plan.question_type,
        "deep"
        if any(term in options.query for term in ("深挖", "深入", "系统研究"))
        else "standard",
    )
    gap_lines.insert(0, f"阶段判断：{quality_context.stage}（证据层：{', '.join(quality_context.layers) or '未识别'}）")
    gap_lines.extend(f"市场结构推演路径：{item}" for item in quality_context.methodology_checks)
    gap_lines.extend(f"反方审稿：{item}" for item in quality_context.critic_questions)

    # ---------- assemble fixed six sections ----------
    theme = (
        "A股市场"
        if is_market_forecast
        else (
            question_plan.research_spec.theme
            if question_plan.research_spec is not None
            else _quoted_topic(options.query)
            or question_plan.query_envelope.subject
            or result.matched_theme
            or options.query
        )
    )
    triggers = (
        "以本地市场总览与主线结构为准"
        if is_market_forecast
        else "、".join((candidate or {}).get("trigger_types", []) or [])
        or "无盘面触发"
    )
    concept_count = ks.get("concept_count", len(concepts.get("items", [])))
    exposure_count = ks.get("exposure_count", len(exposures.get("items", [])))

    stance_bits = []
    trig = set((candidate or {}).get("trigger_types", []) or [])
    if {"double_red"} & trig:
        stance_bits.append("板块双红（涨幅+边际量齐升）")
    if {"new_high_cluster", "new_high_direction"} & trig:
        stance_bits.append("新高成簇，方向被确认")
    if {"limit_advance_cluster", "limit_heat"} & trig:
        stance_bits.append("涨停热度集中")
    if (gaps or not result.found_graph) and not is_market_forecast:
        stance_bits.append("但基本面证据不足，偏盘面驱动")
    stance = (
        "只做条件化情景推演，不把单一路径写成确定结论"
        if is_market_forecast
        else "；".join(stance_bits)
        if stance_bits
        else "盘面信号有限"
    )

    route_line = (
        "研究路径：本地市场总览 → 主线结构 → 情景分支 → 盘后验证"
        if is_market_forecast
        else (
            "模块路由："
            + (
                "、".join(result.routed_modules)
                if result.routed_modules
                else "未启用"
            )
            + ("｜" + "；".join(module_summ) if module_summ else "")
        )
    )
    if is_market_forecast:
        preflight_summary = str(
            (result.forecast_preflight or {}).get("human_summary")
            or "复盘前置查漏状态未记录。"
        )
        conclusion = [
            f"{theme}后续判断：不预设唯一走势，只做条件化情景推演"
            f"（数据截至 {result.trade_date or '未记录'}）。",
            "基准情景：若主线成交与赚钱效应企稳，观察结构性修复；"
            "若量价继续走弱，则维持防守并等待新一轮确认。",
            "上行情景：主线放量后能缩量承接、强势方向扩散，修复持续性提高。",
            "下行情景：放量下跌延续、主线继续收缩，弱势阶段延长。",
            f"前置查漏：{preflight_summary}",
            route_line,
            _conclusion_ttl_line(result.trade_date),
        ]
    else:
        conclusion = [
            f"主题「{theme}」"
            + (
                f"（{result.candidate_tier or '候选'}，盘面评分 {result.priority_score}，所属 {(candidate or {}).get('sw_l1', '?')}）"
                if candidate
                else "（当日盘面候选未命中，以下仅基于知识图谱）"
            )
            + f"：{stance}。",
            f"图谱命中 {concept_count} 概念 / {exposure_count} 公司暴露，证据 {len(evidence_lines)} 条；盘面触发：{triggers}。",
            route_line,
            "结论与交易含义由结构化规则生成；证据不足处已标为待验证。",
            _conclusion_ttl_line(result.trade_date),
        ]
    conclusion = [*framing.get("conclusion", []), *conclusion]

    follow_ups: list[str] = (
        [
            "验证主线成交能否止跌并出现缩量承接，而不是仅看单日反弹。",
            "验证涨停家数、晋级率与上涨家数能否同步修复。",
            "若前置查漏仍未通过，只保留草稿级情景，不升级为正式方向判断。",
        ]
        if is_market_forecast
        else []
    )
    if "double_red" in trig and not is_market_forecast:
        follow_ups.append("跟踪边际量能否连续 ≥2 日维持（双红是否衰减）")
    if {"new_high_cluster", "new_high_direction"} & trig and not is_market_forecast:
        follow_ups.append("观察高位股能否带动补涨扩散，还是仅龙头孤军")
    if {"limit_heat", "limit_advance_cluster"} & trig and not is_market_forecast:
        follow_ups.append("看连板高度与晋级率，确认资金接力意愿")
    if (gaps or tiers["peripheral"]) and not is_market_forecast:
        follow_ups.append("对 graph_only / 缺口公司补研报与官方披露（disclosure-archive → apply）")
    follow_ups.extend(f"市场结构推演路径跟踪：{item}" for item in quality_context.methodology_checks if "缺口" in item)
    for mod_name, item in module_follow_ups:
        follow_ups.append(f"[{mod_name}] {item}")
    follow_ups = [*framing.get("follow_ups", []), *follow_ups]
    if not follow_ups:
        follow_ups.append("补充盘面与基本面证据后再评估")

    tier = (result.candidate_tier or "").lower()
    if is_market_forecast:
        implication = (
            "执行上只响应验证信号：承接与扩散确认后再提高风险暴露；"
            "量价继续恶化则保持防守。"
        )
    elif "deep" in tier:
        implication = "盘面属核心候选：若起涨龙头已高位，重点在低位补涨与上游；缺口公司仅作观察。"
    elif "watch" in tier:
        implication = "盘面属观察候选：等量价进一步确认或证据补齐再参与。"
    elif candidate:
        implication = "盘面属长尾候选：信号弱，暂列观察，不主动参与。"
    else:
        implication = "当日盘面未触发：以图谱认知储备为主，等待盘面信号出现。"
    implication += "（非投资建议，检索骨架输出。）"

    # W 源子块：先放一行检索可观测（用了哪种索引/检索方式/命中质量），再放召回条目。
    wiki_section: list[str] = []
    if result.wiki_rag_telemetry is not None and result.wiki_rag_telemetry.status != "pending":
        wiki_section.append(f"检索可观测：{result.wiki_rag_telemetry.summary_line()}")
    # 无命中时不塞占位行：上面那行检索可观测已经写明命中数与状态，比
    #「（未启用/未接入/无命中）」更具体。两者都没有时整节由 _section 丢弃。
    wiki_section.extend(wiki_lines)

    # 空节不出：占位行（「（图谱未命中概念）」等）既进 LLM 上下文又进渲染，
    # 但缺口信息已由 gap_lines 承担且更具体（会指出"可能是新词/别名未登记，
    # 建议先 concept-ingest 补证"）。保留占位符只是把同一件事说两遍，还把
    # 真正有内容的证据挤到下面。与 web 兜底/Agent 补检索两节的写法保持一致。
    def _section(head: str, lines: list[str]) -> list[str]:
        return [f"{SUBHEAD}{head}"] + lines if lines else []

    evidence_chain = (
        _section("盘面", market_lines)
        + _section("图谱·概念", graph_concept_lines)
        + _section("图谱·公司分层", company_lines)
        + _section("证据", evidence_lines)
        + _section("图谱·语义召回(wiki 向量)", wiki_section)
        + (
            [f"{SUBHEAD}外部 Web 兜底(低层级背景线索)"] + web_fallback_lines
            if web_fallback_lines
            else []
        )
        + (
            [f"{SUBHEAD}Agent 补检索(LLM 自主检索，来源可回查)"] + agent_loop_lines
            if agent_loop_lines
            else []
        )
        + module_block
    )
    if framing:
        evidence_chain = [
            f"{SUBHEAD}题材定义与产业链口径",
            *framing["evidence"],
            *evidence_chain,
        ]
    if question_plan.question_type in {
        QUESTION_MARKET_REVIEW,
        QUESTION_MARKET_FORECAST,
    }:
        daily_market_block = _daily_market_overview_block_for_llm(
            options.market_db_path
        )
        if daily_market_block:
            result.market_summary = daily_market_block
            evidence_chain.extend(
                [f"{SUBHEAD}最新市场总览（本地 DuckDB）", daily_market_block]
            )
            citations.append(
                Citation(
                    "M1",
                    "本地 DuckDB 市场总览",
                    f"fact_market_daily / fact_mainline_theme_daily，截至 {result.trade_date}",
                )
            )
            result.found_market = True

    # --- L: runtime L3 official evidence lookup (announcements / interactions) ---
    if anchor is not None and not any(
        candidate.company == anchor.entity for candidate in company_candidates
    ):
        company_candidates.append(
            answer_model.CompanyCandidate(
                company=anchor.entity,
                ticker=anchor.ticker,
                directness="研究对象",
                requested_tier=answer_model.CompanyTier.CANDIDATE,
            )
        )
    local_evidence_for_l3 = _evidence_text_for_llm(
        _evidence_chain_with_llm_wiki(evidence_chain, wiki_llm_line_pairs),
        gap_lines,
        query=options.query,
    )
    if evidence_providers.should_request_l3_lookup(
        options=options,
        question_plan=question_plan,
        local_evidence_text=local_evidence_for_l3,
    ):
        l3_lines = evidence_providers.collect_l3_official(
            evidence_ctx,
            company_evidence_concepts=company_evidence_concepts,
            local_evidence_text=local_evidence_for_l3,
        )
        if l3_lines:
            evidence_chain.extend([f"{SUBHEAD}L3 官方证据工具补查", *l3_lines])

    # --- P0 技能链：证据分层审计 → 检索遥测 → 反证计划 →（深挖时）研究简报 ---
    audit = research_brief.audit_evidence_chain(evidence_chain, gap_lines)
    telemetry = research_brief.build_retrieval_telemetry(
        audit=audit,
        citation_tags=[c.tag for c in citations],
        wiki_stats=wiki_stats,
        l3_lookup_items=len(result.l3_evidence.items),
    )
    counter_plan = (
        research_brief.CounterEvidencePlan(
            rebuttals=[
                "量价修复可能失败：若放量下跌延续，单日反弹不能视为阶段企稳。",
                "主线扩散可能不足：若强势方向仍是少数高位股独撑，"
                "结构性修复难以升级为全市场改善。",
                "前置查漏尚未通过：缺口未补齐前只保留草稿级情景。",
            ],
            downgrade_triggers=[
                "主线成交继续收缩且涨停家数、晋级率不同步修复 → 下调修复情景。",
                "放量后无法缩量承接、后排持续走弱 → 维持防守情景。",
            ],
            verification_schedule={
                "T+1": ["核对主线成交、涨跌家数、涨停家数与晋级率是否同步改善。"],
                "T+3": ["核对强势方向是否从龙头扩散到中位与低位，而非单点反抽。"],
                "T+5": ["重跑 forecast-preflight；缺口未关闭则不升级正式判断。"],
            },
        )
        if is_market_forecast
        else research_brief.build_counterevidence_plan(
            audit,
            stage=quality_context.stage,
        )
    )
    # --- P1 技能链：市场结构状态机（公共依赖）→（题材问题时）生命周期诊断 ---
    market_state = market_structure.classify_market_structure(
        market_lines, list((candidate or {}).get("trigger_types", []) or [])
    )
    result.market_state = market_state
    gap_lines.append(f"市场结构状态机：阶段={market_state.phase}；{market_state.playbook}")
    if question_plan.question_type == QUESTION_THEME_ANALYSIS:
        diag = theme_lifecycle.diagnose_theme_lifecycle(
            result.matched_theme or options.query,
            evidence_chain,
            gap_lines,
            market_state,
            candidate_tier=result.candidate_tier,
        )
        result.theme_lifecycle = diag
        gap_lines.append(f"题材生命周期：{diag.stage}——{diag.guidance}")
        gap_lines.extend(f"题材生命周期缺口：{g}" for g in diag.gaps)
    result.evidence_audit = audit
    result.retrieval_telemetry = telemetry
    result.counterevidence = counter_plan
    gap_lines.extend(f"证据分层审计：{w}" for w in audit.warnings)
    follow_ups.extend(counter_plan.follow_up_lines())
    if question_plan.question_type == QUESTION_NEWS_IMPACT:
        result.event_brief = event_transmission.build_event_transmission_brief(options.query, evidence_chain)
        gap_lines.extend(
            f"事件传导缺口（{s.name}）：{g}" for s in result.event_brief.steps for g in s.gaps
        )
    if question_plan.question_type == QUESTION_VALUATION:
        result.valuation_note = valuation_gap.check_valuation_gaps(evidence_chain)
        gap_lines.extend(f"估值四问：{g}" for g in result.valuation_note.gaps)
    if question_plan.question_type == QUESTION_STOCK_DEEP_DIVE:
        result.gap_radar = evidence_gap_radar.scan_evidence_gaps(options.query, evidence_chain)
        result.valuation_note = valuation_gap.check_valuation_gaps(evidence_chain)
        gap_lines.extend(f"证据缺口雷达：{n}" for n in result.gap_radar.gap_notes)
        gap_lines.extend(f"估值四问：{g}" for g in result.valuation_note.gaps)
        follow_ups.extend(f"候选研究任务（人工 review）：{t}" for t in result.gap_radar.candidate_tasks[:3])
        result.stock_brief = research_brief.build_stock_research_brief(
            options.query,
            question_plan.question_type,
            quality_context.stage,
            audit,
            telemetry,
            counter_plan,
        )

    # --- ② optional LLM refinement of 结论 / 交易含义 (graceful degrade w/o key) ---
    if options.use_llm:
        evidence_text = _evidence_text_for_llm(
            _evidence_chain_with_llm_wiki(evidence_chain, wiki_llm_line_pairs),
            gap_lines,
            query=options.query,
        )
        refined, reason = llm_refine.refine_or_reason(
            options.query, theme, evidence_text,
            model_override=options.llm_model,
            timeout=_stage_timeout(options, options.llm_timeout),
        )
        if refined is not None:
            result.llm_refined = True
            result.llm_provider = refined.provider
            conclusion = list(refined.conclusion) + [
                route_line,
                f"（结论/交易含义由 LLM·{refined.provider}/{refined.model} 基于上述编号证据精修；证据链/分歧/模块召回为确定性检索结果。）",
            ]
            implication_lines = list(refined.implication)
        else:
            result.warnings.append(reason)
            implication_lines = [implication]
    else:
        implication_lines = [implication]

    # --- ③ optional 有机合成 (compose): 把多源证据融成一段自由形态、带内联引用的回答 ---
    if not options.compose:
        result.d_block_stats = [
            research_brief.DBlockStat("D0", "盘面时序直查", note="仅 --compose + 时序取数意图生成"),
            research_brief.DBlockStat("D1", "市场价值与替代队列", note="仅 --compose 路径生成"),
            research_brief.DBlockStat("D2", "客户证据硬度", note="仅 --compose 路径生成"),
            research_brief.DBlockStat("D3", "二阶导研究队列", note="仅 --compose 路径生成"),
            research_brief.DBlockStat("D4", "主线题材结构", note="仅 --compose 路径生成"),
            research_brief.DBlockStat("D5", "估值数据块", note="仅 --compose + 估值问题类型生成"),
        ]
    if options.compose:
        is_market_review = question_plan.question_type == QUESTION_MARKET_REVIEW
        is_market_overview = question_plan.question_type in {
            QUESTION_MARKET_REVIEW,
            QUESTION_MARKET_FORECAST,
        }
        prompt_source_chain = _evidence_chain_with_llm_wiki(
            evidence_chain,
            wiki_llm_line_pairs,
        )
        compose_evidence_chain = (
            _market_review_evidence_chain(prompt_source_chain)
            if is_market_review
            else prompt_source_chain
        )
        evidence_text = _evidence_text_for_llm(
            compose_evidence_chain,
            [] if is_market_review else gap_lines,
            query=options.query,
        )
        if result.data_notice:
            evidence_text = (
                f"## 本轮数据说明\n{result.data_notice}\n\n{evidence_text}"
            )
        if result.question_plan is not None:
            evidence_text = f"{result.question_plan.to_prompt_block(compact=True)}\n\n{evidence_text}"
        if not is_market_review:
            evidence_text = (
                f"{evidence_text}\n\n{audit.to_prompt_block()}"
                f"\n\n{telemetry.to_prompt_block()}\n\n{counter_plan.to_prompt_block()}"
            )
        if result.stock_brief is not None and not is_market_review:
            evidence_text = f"{evidence_text}\n\n{result.stock_brief.to_prompt_block()}"
        if result.market_state is not None and not is_market_review:
            evidence_text = f"{evidence_text}\n\n{result.market_state.to_prompt_block()}"
        if result.theme_lifecycle is not None and not is_market_review:
            evidence_text = f"{evidence_text}\n\n{result.theme_lifecycle.to_prompt_block()}"
        if result.event_brief is not None and not is_market_review:
            evidence_text = f"{evidence_text}\n\n{result.event_brief.to_prompt_block()}"
        if result.gap_radar is not None and not is_market_review:
            evidence_text = f"{evidence_text}\n\n{result.gap_radar.to_prompt_block()}"
        if result.valuation_note is not None and not is_market_review:
            evidence_text = f"{evidence_text}\n\n{result.valuation_note.to_prompt_block()}"
        if result.forecast_preflight is not None and not is_market_review:
            evidence_text = f"{evidence_text}\n\n{forecast_preflight.render_preflight_prompt(result.forecast_preflight)}"
        # --- planner-worker 并行取数：数据块统一为 DataBlockProvider（applies=规则门控、
        # collect=取数），run_providers 对命中的块并行取数、按注册顺序汇总——evidence_text/
        # 引用编号与串行版逐字节一致，并行只是快。D3 依赖前面块的 evidence_text，单独串行收尾。---
        # LLM 检索 planner 灰度（ASK_PLANNER_MODE=rules|shadow|llm）：shadow 只记 trace，
        # llm 把鞈制后的计划写进 enabled_providers；失败/未配置完全回退规则门控。
        planner_plan: retrieval_planner.RetrievalPlan | None = None
        _planner_mode = retrieval_planner.planner_mode()
        if (
            _planner_mode != retrieval_planner.MODE_RULES
            and options.enabled_providers is None
        ):
            planner_plan = retrieval_planner.plan_retrieval(
                options.query,
                question_plan.question_type,
                perspective_active=_perspective_active(options),
            )
            plan_applied = (
                _planner_mode == retrieval_planner.MODE_LLM
                and planner_plan.source == retrieval_planner.MODE_LLM
            )
            result.provider_traces.append(
                ProviderTrace(
                    provider="retrieval_planner",
                    capability=f"mode={_planner_mode} applied={plan_applied}",
                    status=(
                        "success"
                        if planner_plan.source == retrieval_planner.MODE_LLM
                        else "fallback_failed"
                    ),
                    detail=json.dumps(planner_plan.to_dict(), ensure_ascii=False),
                    result_count=len(planner_plan.providers),
                )
            )
            if plan_applied:
                options = replace(
                    options, enabled_providers=planner_plan.providers,
                )
            else:
                planner_plan = None  # shadow 或回退：计划不生效
        anchored_name = result.anchored_entity.entity if result.anchored_entity is not None else None
        providers: list[ask_planner.DataBlockProvider] = []

        d0_intents: list[market_timeseries.TimeseriesIntent] = []
        d0_on_date: list[str] = []

        def _d0_applies() -> bool:
            if not evidence_registry.provider_enabled(options, "D0"):
                return False
            intent = market_timeseries.parse_timeseries_intent(options.query)
            if intent is None:
                # 「2026-02-17 涨停家数多少」这类单日精确取值不带时序措辞，
                # parse_timeseries_intent 取不到，此前就没有任何 provider 供数，
                # 于是路由再对也拿不到那个数。锚定到该日走同一条白名单直查。
                spec = market_timeseries.parse_single_metric_intent(options.query)
                requested = market_review_requested_date(options.query)
                if spec is None or requested is None:
                    return False
                intent = market_timeseries.TimeseriesIntent(
                    window=market_timeseries.MIN_WINDOW, metric_keys=(spec.key,)
                )
                d0_on_date.append(str(requested))
            d0_intents.append(intent)
            return True

        def _build_d0():
            intent = d0_intents[0]
            on_date = d0_on_date[0] if d0_on_date else None
            block = market_timeseries.timeseries_block_for_llm(
                intent, options.market_db_path, on_date=on_date
            )
            metric_labels = "/".join(spec.label for spec in intent.metrics)
            scope = f"{on_date} 单日" if on_date else f"过去 {intent.window} 个交易日"
            return block, Citation(
                "D0",
                "本地 DuckDB 盘面时序直查数据块",
                f"白名单指标逐日直查（{metric_labels}，{scope}）",
            )

        providers.append(ask_planner.DataBlockProvider("D0", "盘面时序直查", _d0_applies, _build_d0))

        d6_intents: list[market_midterm.MidtermIntent] = []

        def _d6_applies() -> bool:
            if not evidence_registry.provider_enabled(options, "D6"):
                return False
            # 视角模式下放宽词面门控（回退逻辑与理由见 midterm_intent_for）。
            intent = market_midterm.midterm_intent_for(
                options.query, perspective_active=_perspective_active(options)
            )
            if intent is None:
                return False
            d6_intents.append(intent)
            return True

        def _build_d6():
            intent = d6_intents[0]
            block = market_midterm.midterm_trend_block_for_llm(
                options.query, theme, options.market_db_path, intent.window,
            )
            return block, Citation(
                "D6",
                "本地 DuckDB 多日/中期趋势数据块",
                f"题材近 {intent.window} 日双红天数/成交额趋势/拥挤度分位（中期赔率视角）",
            )

        providers.append(ask_planner.DataBlockProvider("D6", "多日中期趋势", _d6_applies, _build_d6))

        def _d9_applies() -> bool:
            return evidence_registry.provider_enabled(options, "D9") and bool(
                options.force_moneyflow_block
                or market_moneyflow.parse_moneyflow_intent(options.query)
            )

        def _build_d9():
            block = market_moneyflow.moneyflow_block_for_llm(
                options.query,
                anchored_name,
                options.market_db_path,
                as_of_date=options.date,
            )
            return block, Citation(
                "D9",
                "本地 DuckDB L2 大单资金流数据块",
                "个股近日主买/总买净额+量化单特征 + 最新扫描日大单净流入榜（自有大单口径，非全市场）",
            )

        providers.append(ask_planner.DataBlockProvider("D9", "L2 大单资金流", _d9_applies, _build_d9))

        def _d12_applies() -> bool:
            return evidence_registry.provider_enabled(options, "D12") and bool(
                market_capital.parse_capital_intent(options.query)
            )

        def _build_d12():
            block = market_capital.capital_block_for_llm(
                options.query,
                options.market_db_path,
                as_of=options.date,
                timeout=_stage_timeout(options, 8),
            )
            return block, Citation(
                "D12",
                "东财资金面三件套数据块",
                "个股两融/大宗/未来90天解禁时间表（只列事实，解禁是待验证时点）",
            )

        providers.append(ask_planner.DataBlockProvider("D12", "资金面三件套", _d12_applies, _build_d12))

        def _d13_applies() -> bool:
            return evidence_registry.provider_enabled(options, "D13") and bool(
                market_dragon.parse_dragon_intent(options.query)
            )

        def _build_d13():
            block = market_dragon.dragon_block_for_llm(
                options.query,
                options.market_db_path,
            )
            return block, Citation(
                "D13",
                "本地 DuckDB 龙虎榜席位数据块",
                "个股近 N 个上榜日买卖前五席位类型分布（营业部/游资/机构，只列事实不跟单）",
            )

        providers.append(ask_planner.DataBlockProvider("D13", "龙虎榜席位", _d13_applies, _build_d13))

        def _d8_applies() -> bool:
            return evidence_registry.provider_enabled(options, "D8") and bool(
                market_analogs.parse_analog_intent(options.query)
            )

        def _build_d8():
            block = market_analogs.analog_block_for_llm(options.query, theme, options.market_db_path)
            return block, Citation(
                "D8",
                "本地 DuckDB 历史类比检索数据块",
                f"题材自身历史上与当前 {market_analogs.DEFAULT_WINDOW} 日形态最相似窗口及后续 5/10/20 日实际走法（小样本历史事实，非概率预测）",
            )

        providers.append(ask_planner.DataBlockProvider("D8", "历史类比检索", _d8_applies, _build_d8))

        def _d10_applies() -> bool:
            return evidence_registry.provider_enabled(options, "D10") and bool(
                market_regime_analogs.parse_regime_intent(options.query)
            )

        def _build_d10():
            block = market_regime_analogs.regime_block_for_llm(options.market_db_path)
            return block, Citation(
                "D10",
                "本地 DuckDB 市场情绪环境类比数据块",
                f"市场级情绪向量与当前 {market_regime_analogs.DEFAULT_WINDOW} 日环境最相似的历史窗口及后续 5/10/20 日实际走法（小样本历史事实，非概率预测）",
            )

        providers.append(ask_planner.DataBlockProvider("D10", "市场情绪环境类比", _d10_applies, _build_d10))

        def _d11_applies() -> bool:
            return evidence_registry.provider_enabled(options, "D11") and bool(
                stock_analogs.parse_stock_analog_intent(options.query)
            )

        def _build_d11():
            block = stock_analogs.stock_analog_block_for_llm(options.query, options.market_db_path)
            return block, Citation(
                "D11",
                "本地 DuckDB 个股走势类比数据块",
                f"个股自身历史上与当前 {stock_analogs.DEFAULT_WINDOW} 日量价结构最相似窗口及后续 5/10/20 日实际走法（含区间最高/达峰/峰后回撤；小样本历史事实，非概率预测）",
            )

        providers.append(ask_planner.DataBlockProvider("D11", "个股走势类比", _d11_applies, _build_d11))

        def _d7_applies() -> bool:
            return evidence_registry.provider_enabled(options, "D7") and bool(
                market_financials.parse_financials_intent(options.query)
                or (
                    question_plan.base_finance_mode is not None
                    and question_plan.base_finance_mode.require_financials
                )
            )

        def _build_d7():
            block = _financials_block_for_llm(
                options.query,
                options.market_db_path,
                timeout=_stage_timeout(options, 8),
            )
            return block, Citation(
                "D7",
                "东财 F10 逐季财报数据块",
                "目标近 N 期累计营收/归母净利/毛利率/净利率（+同比），业绩兑现节奏视角",
            )

        providers.append(ask_planner.DataBlockProvider("D7", "逐季财报", _d7_applies, _build_d7))

        def _w7_applies() -> bool:
            if not evidence_registry.provider_enabled(options, "W7"):
                return False
            if market_news.parse_news_intent(options.query) or (
                question_plan.base_finance_mode is not None
                and question_plan.base_finance_mode.require_news
            ):
                return True
            return bool(
                {"web_search", "market_news"}.intersection(
                    options.controller_capabilities
                )
                and market_news.resolve_news_keyword(
                    options.query, theme, anchored_name
                )
            )

        def _build_w7():
            news_keyword = (
                planner_plan.queries["W7"]
                if planner_plan is not None and planner_plan.queries.get("W7")
                else market_news.resolve_news_keyword(options.query, theme, anchored_name)
            )
            news_result = market_news.news_block_result_for_keyword(
                news_keyword,
                timeout=_stage_timeout(options, 20),
            )
            result.provider_traces.extend(news_result.traces)
            return news_result.block, Citation(
                "W7",
                "web 事件检索数据块（东财资讯 + web-access 全网检索）",
                f"「{news_keyword}」近 {market_news.DEFAULT_WITHIN_DAYS} 天资讯日期/来源/标题/链接（只列不编，消息面存在性证据）",
            )

        providers.append(ask_planner.DataBlockProvider("W7", "web 事件检索", _w7_applies, _build_w7))

        def _d17_applies() -> bool:
            return evidence_registry.provider_enabled(options, "D17") and bool(
                overnight_map.parse_overnight_intent(options.query)
            )

        def _build_d17():
            block = overnight_map.overnight_block_for_llm(
                finance_db_path=options.market_db_path,
            )
            return block, Citation(
                "D17",
                "fph2026 隔夜美股→A 股映射数据块",
                "美股主题热度/涨跌 → 对照表 A 股板块 → 当日 A 股温度计与涨跌（只列映射事实，不表示必然跟涨）",
            )

        providers.append(
            ask_planner.DataBlockProvider("D17", "隔夜美股映射", _d17_applies, _build_d17)
        )

        def _build_m():
            block = user_memory.memory_block_for_query(
                options.query, theme, anchored_name, user=options.user,
            )
            return block, Citation(
                "M",
                "用户记忆检索块",
                "相关性召回的用户既有核心判断/纠偏原则/回检胜率（非市场事实，承接往前推）",
            )

        providers.append(
            ask_planner.DataBlockProvider(
                "M", "用户记忆检索", lambda: evidence_registry.provider_enabled(options, "M"), _build_m,
            )
        )

        def _build_v():
            block = v_block_for_ask(options, theme, anchored_name)
            return block, Citation(
                "V",
                "回检块（历史可证伪判断×裁决）",
                "系统对该题材/个股登记过的可证伪判断及最新裁决 hit/miss/partial/unverifiable，"
                "附数据新鲜度自检（裁决快照非新预测，未终态不作数）",
            )

        providers.append(
            ask_planner.DataBlockProvider(
                "V", "回检块", lambda: evidence_registry.provider_enabled(options, "V"), _build_v,
            )
        )

        def _build_d1():
            block = _market_value_block_for_llm(options.query, theme, options.market_db_path)
            return block, Citation(
                "D1",
                "本地 DuckDB 市场价值数据块",
                "CAR/峰后回撤/半衰期代理/同题材强势替代队列",
            )

        providers.append(
            ask_planner.DataBlockProvider(
                "D1",
                "市场价值与替代队列",
                lambda: evidence_registry.provider_enabled(options, "D1")
                and not is_market_overview,
                _build_d1,
            )
        )

        def _build_d4():
            block = (
                _market_review_mainline_context_block_for_llm(
                    options.query,
                    theme,
                    options.market_db_path,
                )
                if is_market_overview
                else _mainline_context_block_for_llm(
                    options.query,
                    theme,
                    options.market_db_path,
                )
            )
            return block, Citation(
                "D4",
                "本地 DuckDB 主线题材结构数据块",
                "同日主线结构；若快照滞后则仅提供数据边界",
            )

        providers.append(
            ask_planner.DataBlockProvider(
                "D4", "主线题材结构", lambda: evidence_registry.provider_enabled(options, "D4"), _build_d4,
            )
        )

        def _build_d2():
            block = _customer_evidence_hardness_block_for_llm(evidence_chain, gap_lines)
            return block, Citation(
                "D2",
                "本地证据链客户硬度数据块",
                "客户/订单/量产/送样/验证证据按硬度分层",
            )

        providers.append(
            ask_planner.DataBlockProvider(
                "D2",
                "客户证据硬度",
                lambda: evidence_registry.provider_enabled(options, "D2")
                and not is_market_overview,
                _build_d2,
            )
        )

        def _build_d5():
            block = _valuation_block_for_llm(options.query, result.matched_theme, options.market_db_path)
            return block, Citation(
                "D5",
                "东财快照估值数据块",
                "目标 PE/PB/市值 + 同题材可比估值带与横截面分位",
            )

        providers.append(
            ask_planner.DataBlockProvider(
                "D5",
                "估值数据块",
                lambda: evidence_registry.provider_enabled(options, "D5")
                and question_plan.question_type == QUESTION_VALUATION,
                _build_d5,
            )
        )

        with _progress_stage(
            options,
            "data_blocks",
            provider_count=len(providers),
            parallel=options.parallel_blocks,
        ) as stage:
            outcomes = ask_planner.run_providers(
                providers,
                parallel=options.parallel_blocks,
                deadline=options.deadline,
            )
            stage["outcome_count"] = len(outcomes)
            stage["nonempty_count"] = sum(
                bool(outcome.block) for outcome in outcomes
            )
        for outcome in outcomes:
            structured_claims.extend(
                _claims_from_data_block(
                    outcome.block,
                    outcome.tag,
                    outcome.label,
                    claim_theme,
                )
            )
        d5_outcome: ask_planner.BlockOutcome | None = None
        for outcome in outcomes:
            if outcome.tag == "D5":
                d5_outcome = outcome  # D5 按原有顺序在 D3 之后汇总
                continue
            evidence_text = _append_block_outcome(result, outcome, evidence_text, citations)
        # D3 依赖此前累积的 evidence_text（文本兜底路径），必须在其他块汇总后串行生成。
        if (
            evidence_registry.provider_enabled(options, "D3")
            and not is_market_overview
        ):
            second_derivative_block = _second_derivative_queue_block_for_llm(
                options.query,
                theme,
                options.market_db_path,
                evidence_text,
            )
            result.d_block_stats.append(_d_block_stat("D3", "二阶导研究队列", second_derivative_block))
            if second_derivative_block:
                structured_claims.extend(
                    _claims_from_data_block(
                        second_derivative_block,
                        "D3",
                        "二阶导研究队列",
                        claim_theme,
                    )
                )
                evidence_text = f"{evidence_text}\n\n{second_derivative_block}"
                citations.append(
                    Citation(
                        "D3",
                        "本地 DuckDB + 证据链二阶导研究队列数据块",
                        "强势替代表达/目标股再升级/产业瓶颈补盲",
                    )
                )
        if d5_outcome is not None:
            evidence_text = _append_block_outcome(result, d5_outcome, evidence_text, citations)
        if options.supplemental_evidence:
            evidence_text = (
                f"{evidence_text}\n\n## 本轮产品 Skill 结构化结果\n"
                f"{options.supplemental_evidence}"
            )
        evidence_text = (
            f"{evidence_text}\n\n"
            f"{trading_day_prompt_block(result.trade_date, db_path=options.market_db_path)}"
        )
        result.answer_spec = _build_answer_spec_for_result(
            result=result,
            research_spec=(
                question_plan.research_spec
                or answer_model.resolve_theme_research_spec(
                    options.query,
                    question_plan.query_envelope.subject or result.matched_theme,
                )
            ),
            conclusion_lines=conclusion,
            structured_claims=structured_claims,
            company_candidates=company_candidates,
            counter_lines=counter_plan.rebuttals,
            gap_lines=gap_lines,
            trigger_lines=[
                *market_lines,
                *(
                    question_plan.research_spec.trigger_conditions
                    if question_plan.research_spec is not None
                    else ()
                ),
            ],
            follow_ups=follow_ups,
            citations=citations,
        )
        if relation_edge_gap:
            result.answer_spec = _relation_gap_answer_spec(
                result.answer_spec,
                relation_edge_gap,
            )
        result.prepared_synthesis_messages = _prepare_answer_spec_synthesis(
            options=options,
            result=result,
            question_plan=question_plan,
            theme=theme,
            citations=citations,
            quality_context=quality_context,
            is_market_review=is_market_review,
        )
        result.prepared_synthesis_is_market_review = is_market_review
        if options.synthesize:
            with _progress_stage(options, "synthesis"):
                synthesize_prepared_answer(
                    PreparedAnswer(
                        options=options,
                        result=result,
                    )
                )

    if result.answer_spec is None:
        result.answer_spec = _build_answer_spec_for_result(
            result=result,
            research_spec=(
                question_plan.research_spec
                or answer_model.resolve_theme_research_spec(
                    options.query,
                    question_plan.query_envelope.subject or result.matched_theme,
                )
            ),
            conclusion_lines=conclusion,
            structured_claims=structured_claims,
            company_candidates=company_candidates,
            counter_lines=counter_plan.rebuttals,
            gap_lines=gap_lines,
            trigger_lines=[
                *market_lines,
                *(
                    question_plan.research_spec.trigger_conditions
                    if question_plan.research_spec is not None
                    else ()
                ),
            ],
            follow_ups=follow_ups,
            citations=citations,
        )
        if relation_edge_gap:
            result.answer_spec = _relation_gap_answer_spec(
                result.answer_spec,
                relation_edge_gap,
            )
    result.warnings.extend(
        f"AnswerSpec 质检：{issue.message}"
        for issue in result.answer_spec.quality.issues
    )
    _ensure_forecast_scenarios_visible(result)
    _ensure_track_contract_visible(result, enabled=options.include_track_guidance)

    with _progress_stage(options, "output_review") as stage:
        result.review_gate = output_review.review_output(
            trade_date=result.trade_date,
            audit=audit,
            counter_plan=counter_plan,
            gap_lines=gap_lines,
            follow_ups=follow_ups,
            conclusion_lines=conclusion,
            final_answer=result.synthesis,
        )
        stage["warn_count"] = result.review_gate.warn_count
    result.warnings.extend(
        f"输出质检：{c.name}——{c.note}"
        for c in result.review_gate.checks
        if c.status == output_review.WARN and not c.advisory_only
    )
    _revise_synthesis_on_warn(result, options)
    result.sections = {
        "结论": conclusion,
        "证据链": evidence_chain,
        "分歧反证": gap_lines,
        "后续验证点": follow_ups,
        "检索可观测": telemetry.summary_lines() + research_brief.summarize_d_blocks(result.d_block_stats),
        "输出质检": result.review_gate.summary_lines(),
        "交易含义": implication_lines,
        "数据源状态": [
            (
                f"{trace.provider}｜{trace.capability}｜{trace.status}"
                f"｜source_trade_date={trace.source_trade_date or '未记录'}"
                f"｜result_count={trace.result_count}"
                + (f"｜{trace.detail}" if trace.detail else "")
            )
            for trace in result.provider_traces
        ],
        "引用来源": _unique_citation_sources(citations),
    }
    result.citations = citations
    _propose_foresight_judgments(options, result)
    _register_track_next_watch(options, result)
    return result


def _should_propose_foresight_judgments(options: AskOptions) -> bool:
    """测试用户和 default 不写台账；生产身份才提案。"""
    import os

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    user = options.user or os.environ.get("FORESIGHT_USER") or ""
    return bool(user) and user not in {"golden-test", "tester", "default"}


def _propose_foresight_judgments(options: AskOptions, result: AskResult) -> None:
    if not _should_propose_foresight_judgments(options):
        return
    try:
        from intelligence.services import judgment_extract

        written = judgment_extract.propose_from_answer(
            judgments_path=userspace.user_space(options.user).judgments_path,
            query=options.query,
            answer=render_answer(result),
            as_of=result.trade_date or options.date,
            theme=result.matched_theme,
            citations=result.citations,
        )
        if written:
            result.warnings.append(
                f"前瞻判断已提案 {len(written)} 条（pending，checkpoint accept 后入账）"
            )
    except Exception as exc:
        result.warnings.append(f"前瞻判断抽取未入账：{exc}")


def _register_track_next_watch(options: AskOptions, result: AskResult) -> None:
    """跟踪题下期关注 → checkpoint。测试/default 用户不写台账。"""
    if not options.include_track_guidance or not _should_propose_foresight_judgments(options):
        return
    try:
        from intelligence.services.track_contract import ingest_next_watch

        question_type = (
            result.question_plan.question_type if result.question_plan is not None else None
        )
        written = ingest_next_watch(
            userspace.user_space(options.user).checkpoints_path,
            result.synthesis or "",
            query=options.query,
            question_type=question_type,
            as_of=result.trade_date or options.date,
            theme=result.matched_theme,
        )
        if written:
            result.warnings.append(
                f"下期关注已登记 {len(written)} 条 checkpoint，次日 foresight 强制对照"
            )
    except Exception as exc:
        result.warnings.append(f"下期关注未入账：{exc}")


def _deadline_partial_result(query: str) -> AskResult:
    warning = "统一研究截止时间已到，未启动新的检索阶段"
    return AskResult(
        query=query,
        trade_date=None,
        matched_theme=None,
        candidate_tier=None,
        priority_score=None,
        warnings=[warning],
        sections={
            "结论": ["本轮研究时间预算已耗尽，仅保留截止前完成的结构化产物。"],
            "证据链": [],
            "分歧反证": ["未完成阶段不得推断为不存在证据。"],
            "后续验证点": ["增加研究预算后，从未完成阶段继续。"],
            "交易含义": ["证据不足，不给出新增交易判断。"],
            "数据源状态": [warning],
            "引用来源": [],
        },
    )


def prepare_answer(options: AskOptions) -> PreparedAnswer:
    prepared_options = replace(
        options,
        synthesize=False,
        compose_revise_on_warn=False,
    )
    return PreparedAnswer(
        options=prepared_options,
        result=answer_query(prepared_options),
    )


def prepare_existing_answer(
    options: AskOptions,
    result: AskResult,
) -> PreparedAnswer:
    # GenericResearchOwner 必须先通过契约完成门禁，再允许 LLM 做表达层合成。
    # 未完成时保留结构化候选/缺口，由专用 renderer 输出，不再生成可被误读成
    # 已完成研究的 synthesis prompt。
    if (
        result.completion_report is not None
        and result.completion_report.get("business_status", "partial") != "complete"
    ):
        # partial/gap 只允许 deterministic AnswerSpec/gap renderer 出站。
        # factual_grounding fulfilled 不能绕过任务完成度；否则会出现
        # “有候选来源但没有直接判断”仍启动 synthesis 的伪完成路径。
        return PreparedAnswer(
            options=replace(options, synthesize=False),
            result=result,
        )
    # 技术位是结构化行情的确定性计算，AnswerSpec 已经是最终展示数据。
    # 再让 LLM 改写不仅增加 30s 级延迟，还可能改动点位、符号或失效条件。
    if (
        result.answer_spec is not None
        and result.answer_spec.presentation_kind
        in {"market_technical", "evidence_gap"}
    ):
        result.prepared_synthesis_messages = []
        return PreparedAnswer(
            options=replace(options, synthesize=False),
            result=result,
        )
    if result.answer_spec is not None and result.prepared_synthesis_messages is None:
        citation_legend = "\n".join(
            f"[{citation.tag}] {citation.source}"
            + (f" — {citation.detail}" if citation.detail else "")
            for citation in result.citations
        )
        theme = result.matched_theme or result.answer_spec.presentation_title or options.query
        result.prepared_synthesis_messages = llm_refine.build_synthesis_messages(
            options.query,
            theme,
            result.answer_spec.to_prompt_block(),
            citation_legend=citation_legend,
        )
    return PreparedAnswer(
        options=replace(options, synthesize=False),
        result=result,
    )
