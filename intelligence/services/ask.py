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

import glob
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date as date_cls, timedelta
from pathlib import Path
from typing import Any

from intelligence import userspace
from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.paths import default_paths
from intelligence.services import ask_clarify, ask_planner, checkpoint_recall, entity_anchor, experience_cards, forecast_preflight, kb_rag, l3_evidence, llm_refine, market_financials, market_analogs, market_midterm, market_news, market_timeseries, market_moneyflow, research_brief, scenario_tree, user_memory
from intelligence.services.answer_quality import build_quality_context
from intelligence.services.answer_orchestrator import (
    QUESTION_MARKET_FORECAST,
    QUESTION_MARKET_REVIEW,
    QUESTION_NEWS_IMPACT,
    QUESTION_STOCK_DEEP_DIVE,
    QUESTION_THEME_ANALYSIS,
    QUESTION_VALUATION,
    QuestionPlan,
    plan_answer_question,
)
from intelligence.services import event_transmission, evidence_gap_radar, market_structure, output_review, theme_lifecycle, valuation_estimate, valuation_gap
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

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPORTS_DIR = REPO_ROOT / "market_feature_store" / "exports"

# few-shot 锚：高分样板目录。文件名前缀按问题类型路由（deep-dive-* / forecast-*），
# 最多注入 EXEMPLAR_MAX_FILES 篇、总长度上限 EXEMPLAR_MAX_CHARS（超量会稀释证据注意力）。
EXEMPLAR_DIR = REPO_ROOT / "skills" / "stock-deep-dive" / "exemplars"
EXEMPLAR_MAX_FILES = 3
EXEMPLAR_MAX_CHARS = 6000
_EXEMPLAR_PREFIX_BY_TYPE = {
    QUESTION_STOCK_DEEP_DIVE: "deep-dive-",
    QUESTION_MARKET_FORECAST: "forecast-",
    QUESTION_VALUATION: "valuation-",
}


def _exemplar_guidance_for(question_type: str, exemplar_dir: Path = EXEMPLAR_DIR) -> str:
    prefix = _EXEMPLAR_PREFIX_BY_TYPE.get(question_type)
    if prefix is None or not exemplar_dir.is_dir():
        return ""
    parts: list[str] = []
    budget = EXEMPLAR_MAX_CHARS
    for path in sorted(exemplar_dir.glob(f"{prefix}*.md"))[:EXEMPLAR_MAX_FILES]:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if not text:
            continue
        snippet = text[:budget]
        parts.append(f"### 样板：{path.stem}\n{snippet}")
        budget -= len(snippet)
        if budget <= 0:
            break
    return "\n\n".join(parts)

# Trade-date freshness threshold (calendar days) above which graph evidence is
# flagged as potentially stale. Stand-in for a real Temporal Facts layer.
DEFAULT_STALE_DAYS = 45

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


@dataclass(frozen=True)
class AskOptions:
    query: str
    date: str | None = None
    exports_dir: str | Path | None = None
    kb_wiki: str | Path | None = None
    top_companies: int = 12
    top_concepts: int = 6
    max_evidence: int = 8
    stale_days: int = DEFAULT_STALE_DAYS
    use_modules: bool = True
    modules: tuple[str, ...] | None = None
    module_timeout: int = 180
    # P2.5 实时盘面：本地 market_feature_store DuckDB 路径。仅 agent 用、默认 None；
    # 提供且可打开时才启用 opt-in 工具 search_market_live，否则行为逐字节不变。
    market_db_path: str | Path | None = None
    # W source: knowledge-base hybrid 向量检索 (semantic wiki page recall)
    use_wiki_rag: bool = True
    wiki_rag_k: int = 6
    wiki_rag_mode: str = "hybrid"
    wiki_rag_timeout: int = 90
    wiki_rag_excerpt: int = 200
    # 全文版：W 源索引目录覆盖（指向 .rag_index_full）。None=默认 .rag_index，行为逐字节不变。
    wiki_rag_index_dir: str | Path | None = None
    use_llm: bool = False
    # compose: 让 LLM 把多源证据有机融合成一段连贯回答（自由形态，带内联引用）；
    # 默认关，关时行为与旧版逐字节一致。开时若无 key/调用失败则降级回六段模板。
    compose: bool = False
    llm_model: str | None = None
    llm_timeout: int = field(default_factory=lambda: int(os.environ.get("LLM_TIMEOUT", "60")))
    detail: bool = False
    user: str | None = None
    experience_cards_window: int = 12
    compose_self_review: bool = True
    include_market_value_block: bool = True
    include_customer_hardness_block: bool = True
    include_second_derivative_block: bool = True
    include_mainline_context_block: bool = True
    # D5 估值数据块：仅 valuation 问题类型 + compose 时生成（东财快照取数，可用 FINANCE_VALUATION_FETCH=0 关闭）。
    include_valuation_block: bool = True
    # D0 盘面时序直查数据块：仅当问题命中「白名单指标 × 过去 N 日逐日」时序取数意图时生成。
    include_timeseries_block: bool = True
    # D6 多日/中期趋势数据块：仅当问题命中「中期/赔率/配置/未来 N 个月」时间尺度意图时生成，
    # 给出题材近 N 日双红天数/成交额趋势/拥挤度分位，纠正 brief/D4 的当日快照偏置。
    include_midterm_block: bool = True
    # D8 历史类比检索块：仅当问题命中「类似/历史上/上一次/先例」意图时生成，从题材自身历史
    # 找与当前 N 日形态最相似的窗口及其后续 5/10/20 日实际走法，只列历史事实不给概率。
    include_analog_block: bool = True
    # D7 逐季财报数据块：仅当问题命中「财报/业绩/营收/净利/毛利率」意图且能解析到目标股时生成，
    # 走东财免费 F10 取逐季营收/归母净利/毛利率/净利率（+同比），补业绩兑现节奏缺口。
    include_financials_block: bool = True
    # W7 web 事件检索块：仅当问题命中「事件/消息/催化/涨价/对标」意图且能解析到关键词（实体/题材）时生成，
    # 走东财免费资讯搜索取近 N 天新闻（日期/来源/标题/链接），只列不编，补消息面缺口。
    include_news_block: bool = True
    # D9 L2 大单资金流数据块：仅当问题命中「资金流/大单/主买/量化单」意图时生成，直查
    # l2-moneyflow 盘后特征表；榜单只扫涨停股+成交额 top100，缺行≠无资金流入，块内强制声明口径。
    include_moneyflow_block: bool = True
    # 固定日报工作流需把 L2 作为显式模块，即使用户问题没有重复写“资金流”也要取数。
    force_moneyflow_block: bool = False
    # 情景树/推演表达层：推演类问题命中时向 synthesis prompt 注入「变量表→情景分支→监控信号」
    # 表达契约（禁数值概率，likelihood 只准高/中/低并注依据）；非推演问题不注入，行为不变。
    include_scenario_guidance: bool = True
    # M 用户记忆检索块：按相关性召回 judgments/corrections/回检胜率注入证据链；
    # 台账缺失或无相关记录时不追加块，无记忆用户行为逐字节不变。
    include_memory_block: bool = True
    # V 回检块：检索系统对该题材/个股登记过的可证伪判断（checkpoints）及其最新裁决
    # （hit/miss/partial/unverifiable），附数据新鲜度自检（台账/盘面截至日，过期显式声明）；
    # 台账缺失或无相关记录时不追加块，行为逐字节不变。
    include_recall_block: bool = True
    # 澄清追问前置门（clarify-then-act）：问题明确模糊（空问题/纯空泛词面）时不硬答，
    # 返回结构化澄清问题（对象/口径/日期），跳过整次检索；带实质内容的问题行为逐字节不变。
    clarify: bool = True
    # 子任务并行：把命中的独立取数块（D0/D6/D9/D8/D7/W7/M/V/D1/D4/D2/D5）扔进线程池并行取，
    # 仍按固定顺序汇总，evidence_text/引用编号与串行逐字节一致；关掉退回串行（调试用）。
    parallel_blocks: bool = True
    # 实体锚定：图谱语义检索前先做确定性实体解析（股票名/代码→entity_exposures 精确匹配），
    # 命中后用实体自身概念暴露定锚；未命中行为逐字节不变。
    use_entity_anchor: bool = True
    # L3 runtime evidence tools: official announcements / exchange interaction.
    use_l3_lookup: bool = False
    l3_lookup_timeout: int = 480
    l3_lookup_limit: int = 5
    # 质检 WARN 回灌修订（修订版在前契约）：compose 回答经 output_review 闸门后若有 WARN，
    # 把意见送回同一段对话做一轮定向修订，用户拿到修订版全文，审查意见退居「输出质检」附录。
    # 仅影响 compose 路径；模板路径与无 WARN 时行为逐字节不变。
    compose_revise_on_warn: bool = True
    conversation_context: str = ""
    supplemental_evidence: str = ""
    stream_text_delta: Callable[[str], None] | None = field(
        default=None, repr=False, compare=False
    )
    stream_cancel_check: Callable[[], bool] | None = field(
        default=None, repr=False, compare=False
    )


@dataclass
class Citation:
    tag: str  # e.g. "S1", "G2", "R3"
    source: str
    detail: str = ""
    chunk_id: str = ""
    content_hash: str = ""
    index_source_revision: str = ""
    index_freshness: str = ""


@dataclass
class AskResult:
    query: str
    trade_date: str | None
    matched_theme: str | None
    candidate_tier: str | None
    priority_score: float | None
    market_data_source: str = "unknown"
    snapshot_date: str | None = None
    data_notice: str | None = None
    market_summary: str | None = None
    sections: dict[str, list[str]] = field(default_factory=dict)
    citations: list[Citation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    found_market: bool = False
    found_graph: bool = False
    found_wiki: bool = False
    # W 源检索遥测（用了哪种索引/检索方式/命中质量）；None=未启用 W 源。
    wiki_rag_telemetry: kb_rag.RetrievalTelemetry | None = None
    routed_modules: list[str] = field(default_factory=list)
    llm_refined: bool = False
    llm_provider: str | None = None
    # 有机合成（--compose）的自由形态回答正文；None 表示未启用/已降级为模板
    synthesis: str | None = None
    # 首轮合成的完整对话 messages（system+user+assistant）；供多轮追问复用证据+历史。
    # None 表示未启用/已降级（无法进入多轮对话）。
    synthesis_messages: list[dict] | None = None
    # 问答编排层：先解析问题类型/深度/视角/证据计划，再进入 compose。
    question_plan: QuestionPlan | None = None
    # 澄清追问：问题明确模糊时的结构化追问；非 None 表示本次未检索、等用户补充。
    clarify: ask_clarify.ClarifyDecision | None = None
    # 实体锚定结果：确定性实体解析命中的实体与锚定概念；None=未命中/未启用。
    anchored_entity: entity_anchor.EntityAnchor | None = None
    # 行情前瞻前置查漏门：从 daily-agent research_queue 判断是否应先补 DeepDive / L3 证据。
    forecast_preflight: dict[str, Any] | None = None
    # 运行时 L3 官方证据补查。默认空；只有 use_l3_lookup 时才尝试调用外接 CLI。
    l3_evidence: l3_evidence.L3EvidenceBundle = field(
        default_factory=lambda: l3_evidence.L3EvidenceBundle(query="")
    )
    # P0 投研技能层（确定性，无 LLM）：证据分层审计 / 检索可观测 / 反证计划 / 个股研究简报。
    evidence_audit: research_brief.EvidenceAudit | None = None
    retrieval_telemetry: research_brief.RetrievalTelemetry | None = None
    counterevidence: research_brief.CounterEvidencePlan | None = None
    stock_brief: research_brief.StockResearchBrief | None = None
    # P1 技能层：市场结构状态机（个股/题材共享）与题材生命周期诊断。
    market_state: market_structure.MarketStructureState | None = None
    theme_lifecycle: theme_lifecycle.ThemeLifecycleDiagnosis | None = None
    # P2 技能层：事件冲击传导（news_impact）/ 证据缺口雷达 + 估值四问（个股深挖）。
    event_brief: event_transmission.EventTransmissionBrief | None = None
    gap_radar: evidence_gap_radar.GapRadarReport | None = None
    valuation_note: valuation_gap.ValuationGapNote | None = None
    # Review 层：输出前六项确定性检查闸门（只读、WARN 不阻断）。
    review_gate: output_review.OutputReviewGate | None = None
    # D1-D4 DuckDB 数据块的 per-block 可观测字段。
    d_block_stats: list[research_brief.DBlockStat] = field(default_factory=list)
    # (label, 完整报告全文) per routed module, only when --detail is set
    detail_reports: list[tuple[str, str]] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.found_market and self.found_graph:
            return "PASS"
        if self.found_market or self.found_graph:
            return "WARN"
        return "FAIL"


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


def _contains(a: str, b: str) -> bool:
    na, nb = _normalize(a), _normalize(b)
    return bool(na and nb and (na in nb or nb in na))


def _resolve_exports_dir(exports_dir: str | Path | None) -> Path:
    if exports_dir:
        return Path(exports_dir).expanduser()
    return DEFAULT_EXPORTS_DIR


def load_theme_candidates(exports_dir: str | Path | None, date: str | None) -> dict[str, Any]:
    """Load a theme-candidates export. Defaults to the latest available date."""
    base = _resolve_exports_dir(exports_dir)
    if date:
        path = base / f"{date}-theme-candidates.json"
        if not path.exists():
            return {"found": False, "path": str(path), "warnings": [f"no export for {date}"], "doc": {}}
    else:
        matches = sorted(glob.glob(str(base / "*-theme-candidates.json")))
        if not matches:
            return {"found": False, "path": str(base), "warnings": ["no theme-candidates export found"], "doc": {}}
        path = Path(matches[-1])
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        return {"found": False, "path": str(path), "warnings": [str(exc)], "doc": {}}
    return {"found": True, "path": str(path), "warnings": [], "doc": doc}


def _resolve_market_data_context(
    snapshot_date: str | None,
    market_db_path: str | Path | None,
    requested_date: str | None = None,
) -> tuple[str | None, str, str | None, list[str]]:
    if requested_date:
        return requested_date, "requested_date", None, []

    market_date = _market_data_asof(market_db_path)
    if market_date:
        warnings: list[str] = []
        if snapshot_date and snapshot_date != market_date:
            warnings.append(
                f"题材候选快照截至 {snapshot_date}，早于本地 DuckDB 的 {market_date}；"
                "快照仅作辅助参考，不作为本轮整体数据日期。"
            )
        notice = (
            f"**数据截至 {market_date}。** 市场总览优先读取本地 DuckDB；"
            "日报导出和题材候选快照仅作补充，并按各自日期标注。"
        )
        return market_date, "duckdb", notice, warnings

    if snapshot_date:
        notice = (
            "**数据降级：当前未连接本地 DuckDB。** "
            f"以下仅使用截至 {snapshot_date} 的 snapshot/export，不能视为最新交易日复盘。"
        )
        return snapshot_date, "snapshot_fallback", notice, [
            f"未连接本地 DuckDB；本轮回退到截至 {snapshot_date} 的 snapshot/export。"
        ]

    notice = (
        "**数据降级：当前未连接本地 DuckDB，且没有可用的 snapshot/export。** "
        "本轮无法完成最新交易日复盘。"
    )
    return None, "unavailable", notice, [
        "未连接本地 DuckDB，且没有可用 snapshot/export。"
    ]


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
    path: Path | None = None
    if trade_date:
        candidate = base / f"{trade_date}-daily-agent.json"
        if candidate.exists():
            path = candidate
    else:
        matches = sorted(glob.glob(str(base / "*-daily-agent.json")))
        if matches:
            path = Path(matches[-1])
    if path is None:
        source = str(base / f"{trade_date or '<latest>'}-daily-agent.json")
        return forecast_preflight.build_forecast_preflight({}, source_artifact=source)
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        result = forecast_preflight.build_forecast_preflight({}, source_artifact=str(path))
        result["human_summary"] = f"daily-agent 读取失败：{exc}"
        result["prompt_block"] = forecast_preflight.render_preflight_prompt(result)
        return result
    return forecast_preflight.build_forecast_preflight(report, source_artifact=str(path))


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
            if name and _contains(query, str(name)):
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


# 旧结论核验门：这些 wiki 目录里的页面本质是“某个时点的判断”而非可直接引用的事实，
# W 召回命中时打〔历史基线〕标签，合成层按先验处理（当下盘面核验 + 四态对照）。
_PRIOR_CONCLUSION_DIRS = ("synthesis/", "briefings/")


def _is_prior_conclusion_page(file_path: str) -> bool:
    p = str(file_path).replace("\\", "/").lstrip("/")
    if p.startswith("wiki/"):
        p = p[len("wiki/"):]
    return p.startswith(_PRIOR_CONCLUSION_DIRS)


# 结论 TTL：跟踪类判断默认 30 天复查，过期引用须先经当下盘面复核。
CONCLUSION_TTL_DAYS = 30


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


def answer_query(options: AskOptions) -> AskResult:
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
    resolved_kb_wiki = Path(options.kb_wiki).expanduser() if options.kb_wiki else default_paths().knowledge_wiki
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

    result = AskResult(
        query=options.query,
        trade_date=trade_date,
        matched_theme=(candidate or {}).get("canonical_concept") or (candidate or {}).get("market_theme"),
        candidate_tier=(candidate or {}).get("candidate_tier"),
        priority_score=(candidate or {}).get("priority_score"),
        market_data_source=market_data_source,
        snapshot_date=snapshot_date,
        data_notice=data_notice,
    )
    result.warnings.extend(loaded.get("warnings", []))
    result.warnings.extend(data_warnings)
    result.found_market = candidate is not None
    question_plan = plan_answer_question(options.query)
    result.question_plan = question_plan
    result.warnings.extend(f"answer-orchestrator：{w}" for w in question_plan.warnings)
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
        anchor = entity_anchor.resolve_entity_anchor(options.query, knowledge)
    result.anchored_entity = anchor
    if anchor is not None:
        result.warnings.extend(f"entity-anchor：{w}" for w in anchor.warnings)
    # 命中实体后，图谱/向量检索用「实体名+概念暴露」定锚，替代问题原文；未命中保持原文。
    graph_query = anchor.graph_query if anchor is not None else options.query

    citations: list[Citation] = []

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

    # --- S: 盘面 from theme-candidates snapshot ---
    market_lines: list[str] = []
    if candidate:
        for sd in (candidate.get("score_detail") or [])[:5]:
            sig = sd.get("signal")
            sc = sd.get("score")
            reason = sd.get("reason", "")
            tag = cite("S", f"{export_name} · score_detail.{sig}", str(sd.get("source", "")))
            market_lines.append(f"信号 {sig}（{sc}）：{reason} {tag}")
        ctx = doc.get("market_context") or {}
        if ctx:
            caps = "、".join(
                f"{s.get('name')}({s.get('ratio')}%,{s.get('capacity_type')})"
                for s in (ctx.get("capacity_sectors") or [])[:3]
            )
            tag = cite("S", f"{export_name} · market_context")
            market_lines.append(
                f"市场环境：{ctx.get('market_stage')}，成交 {ctx.get('total_amount')}，"
                f"涨停 {ctx.get('limit_up')} / 跌停 {ctx.get('limit_down')}，容量前三 {caps} {tag}"
            )

    # --- G: graph (concepts + company tiers) from KB relations ---
    graph_concept_lines: list[str] = []
    if anchor is not None:
        result.found_graph = True
        tag = cite("G", "knowledge-base · wiki/relations/entity_exposures.json", f"实体解析 matched_by={anchor.matched_by}")
        graph_concept_lines.append(f"{anchor.summary()} {tag}")
    concepts = knowledge.get_concept_matches(graph_query, limit=options.top_concepts)
    if concepts.get("found"):
        result.found_graph = True
        names = "、".join(f"{i['concept']}({i['score']})" for i in concepts["items"])
        tag = cite("G", "knowledge-base · wiki/relations/concept_graph.json")
        graph_concept_lines.append(f"命中概念：{names} {tag}")

    company_lines: list[str] = []
    exposures = knowledge.get_exposure_matches(graph_query, limit=options.top_companies)
    tiers: dict[str, list[str]] = {"core": [], "peripheral": [], "other": []}
    if exposures.get("found"):
        result.found_graph = True
        for row in exposures["items"]:
            strength = str(row.get("strength") or "").lower()
            conf = str(row.get("confidence") or "")
            layer = str(row.get("evidence_layer") or "")
            label = f"{row.get('company')}({row.get('ticker')}|{row.get('role') or '—'}|{conf or '?'}/{layer or '?'})"
            if strength in {"core", "strong"} or conf in {"high"}:
                tiers["core"].append(label)
            elif strength in {"peripheral", "weak"} or layer in {"graph_only"}:
                tiers["peripheral"].append(label)
            else:
                tiers["other"].append(label)
        tag = cite("G", "knowledge-base · wiki/relations/entity_exposures.json")
        if tiers["core"]:
            company_lines.append(f"核心层：{'、'.join(tiers['core'])} {tag}")
        if tiers["other"]:
            company_lines.append(f"中间层：{'、'.join(tiers['other'])} {tag}")
        if tiers["peripheral"]:
            company_lines.append(f"外围/弱关联层：{'、'.join(tiers['peripheral'])} {tag}")

    # --- R: evidence from KB evidence_index (+ candidate snapshot) + staleness ---
    evidence_lines: list[str] = []
    stale_notes: list[str] = []
    seen_evidence: set[str] = set()
    targets: list[str] = []
    if anchor is not None:
        targets.append(anchor.entity)
    if result.matched_theme:
        targets.append(result.matched_theme)
    targets.append(options.query)
    for label in tiers["core"][:3]:
        targets.append(label.split("(")[0])
    for target in dict.fromkeys(t for t in targets if t):
        ev = knowledge.get_evidence(target, limit=options.max_evidence)
        if not ev.get("found"):
            continue
        for item in ev["items"]:
            key = f"{item.get('target')}|{item.get('source')}|{item.get('evidence')}"
            if key in seen_evidence:
                continue
            seen_evidence.add(key)
            result.found_graph = True
            stale = _evidence_is_stale(item, options.stale_days)
            tag = cite(
                "R",
                "knowledge-base · wiki/relations/evidence_index.json",
                f"target={item.get('target')} source={item.get('source')}",
            )
            mark = " ⚠️过期" if stale else ""
            line = (
                f"{item.get('target')}：{str(item.get('evidence'))[:80]}"
                f"（{item.get('source')}, {item.get('source_date') or '无日期'}, "
                f"质量 {item.get('confidence') or '?'}{mark}） {tag}"
            )
            evidence_lines.append(line)
            if stale:
                stale_notes.append(
                    f"{item.get('target')} 证据 {item.get('source_date')} 已超 {options.stale_days} 天，需复核是否被新数据证伪 {tag}"
                )
            if len(evidence_lines) >= options.max_evidence:
                break
        if len(evidence_lines) >= options.max_evidence:
            break

    # candidate-embedded knowledge_evidence as cross-check
    for ke in (candidate or {}).get("knowledge_evidence", []) or []:
        src = ke.get("source")
        key = f"{ke.get('target')}|{src}"
        if not src or key in seen_evidence:
            continue
        seen_evidence.add(key)
        tag = cite("R", f"{export_name} · knowledge_evidence")
        evidence_lines.append(
            f"{ke.get('target')}：{src}（质量 {ke.get('quality') or '?'}，盘面候选携带） {tag}"
        )

    # --- W: 知识库 hybrid 向量召回（语义选页 → 读候选页正文作证据，打通复盘↔知识库闭环）---
    wiki_lines: list[str] = []
    wiki_stats: dict[str, Any] = {
        "attempted": bool(options.use_wiki_rag),
        "mode": options.wiki_rag_mode,
        "index": "full" if options.wiki_rag_index_dir else "structured",
    }
    if options.use_wiki_rag:
        wr = kb_rag.retrieve(
            graph_query,
            resolved_kb_wiki,
            k=options.wiki_rag_k,
            mode=options.wiki_rag_mode,
            timeout=options.wiki_rag_timeout,
            excerpt_chars=options.wiki_rag_excerpt,
            index_dir=options.wiki_rag_index_dir,
        )
        wiki_stats.update(
            {
                "ok": wr.ok,
                "hits": len(wr.hits),
                "scores": [h.score for h in wr.hits],
                "neighbor_hits": sum(1 for h in wr.hits if h.via_neighbor),
                "pages": [h.file_path for h in wr.hits],
                "warning": wr.warning,
            }
        )
        result.wiki_rag_telemetry = wr.telemetry
        if wr.ok and wr.hits:
            result.found_wiki = True
            result.found_graph = True
            for h in wr.hits:
                nb = "·邻居扩展" if h.via_neighbor else ""
                section_ref = f"｜section={h.section}" if h.section else ""
                tag = cite(
                    "W",
                    f"knowledge-base · {h.file_path}",
                    (
                        f"{wr.command}｜{h.title}｜chunk={h.best_chunk_id}{section_ref}"
                        f"｜hash={h.content_hash[:12]}｜index={h.index_source_revision[:12]}"
                        f"｜freshness={h.index_freshness}"
                    ),
                    chunk_id=h.best_chunk_id,
                    content_hash=h.content_hash,
                    index_source_revision=h.index_source_revision,
                    index_freshness=h.index_freshness,
                )
                # 旧结论核验门：synthesis/briefings 页是历史判断而非当前事实，打〔历史基线〕
                # 标签供合成层按 prior 处理（引用前须用当下盘面核验，给四态对照）。
                baseline = (
                    "〔历史基线·仅作先验，须以当下盘面核验〕"
                    if _is_prior_conclusion_page(h.file_path)
                    else ""
                )
                wiki_lines.append(
                    f"{baseline}{h.title}（相关度 {round(h.score, 4)}{nb}）：{h.excerpt} {tag}"
                )
            if wr.warning:  # 全文版索引缺失回退默认索引时，仍把提示记进 warnings
                result.warnings.append(f"wiki-rag：{wr.warning}")
        elif wr.warning:
            result.warnings.append(f"wiki-rag：{wr.warning}")

    # --- 模块 fan-out: route query to theme-radar 模式 as recall backends ---
    module_block: list[str] = []
    module_follow_ups: list[tuple[str, str]] = []
    module_summ: list[str] = []
    if options.use_modules:
        routed = route_modules(options.query, list(options.modules) if options.modules else None)
        result.routed_modules = list(routed)
        for name in routed:
            mr = run_module(name, graph_query, resolved_kb_wiki, options.module_timeout)
            module_block.append(f"{SUBHEAD}模块·{MODULE_LABELS.get(name, name)}")
            if mr.ok and mr.highlights:
                result.found_graph = True
                tag = cite("G", mr.citation_source, f"{mr.command}" + (f" | {mr.citation_detail}" if mr.citation_detail else ""))
                for hl in mr.highlights:
                    module_block.append(f"{hl} {tag}")
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

    # --- gaps / contradictions ---
    gap_lines: list[str] = []
    ks = (candidate or {}).get("knowledge_status") or {}
    gaps = ks.get("backfill_gaps") or []
    if gaps:
        gap_lines.append(f"盘面候选标记缺口：{'、'.join(map(str, gaps))}（图谱覆盖不足，证据待补）")
    if not result.found_graph:
        gap_lines.append("知识图谱未命中该词：可能是新词/别名未登记，建议先 concept-ingest 或 disclosure-archive 补证")
    if tiers["peripheral"]:
        gap_lines.append(
            f"{len(tiers['peripheral'])} 家公司为 graph_only/低置信暴露，属预期差待证伪区，不宜直接作为基本面依据"
        )
    gap_lines.extend(stale_notes)
    gap_lines.append(
        "Temporal Facts 层尚未接入：以上证据仅按 source_date 标注新鲜度；"
        "正式版应把会过期/被证伪的事实建成带 status(active/superseded/invalidated) 的时序边"
    )
    quality_context = build_quality_context(
        evidence_lines=evidence_lines + graph_concept_lines + company_lines + wiki_lines + module_block,
        market_lines=market_lines,
        gap_lines=gap_lines,
    )
    gap_lines.insert(0, f"阶段判断：{quality_context.stage}（证据层：{', '.join(quality_context.layers) or '未识别'}）")
    gap_lines.extend(f"市场结构推演路径：{item}" for item in quality_context.methodology_checks)
    gap_lines.extend(f"反方审稿：{item}" for item in quality_context.critic_questions)

    # ---------- assemble fixed six sections ----------
    theme = result.matched_theme or options.query
    triggers = "、".join((candidate or {}).get("trigger_types", []) or []) or "无盘面触发"
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
    if gaps or not result.found_graph:
        stance_bits.append("但基本面证据不足，偏盘面驱动")
    stance = "；".join(stance_bits) if stance_bits else "盘面信号有限"

    route_line = (
        "模块路由："
        + ("、".join(result.routed_modules) if result.routed_modules else "未启用")
        + ("｜" + "；".join(module_summ) if module_summ else "")
    )
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
        "（注：结论与交易含义为模板化骨架，待接 LLM 精修；证据链/分歧/模块召回为真实检索结果。）",
        _conclusion_ttl_line(result.trade_date),
    ]

    follow_ups: list[str] = []
    if "double_red" in trig:
        follow_ups.append("跟踪边际量能否连续 ≥2 日维持（双红是否衰减）")
    if {"new_high_cluster", "new_high_direction"} & trig:
        follow_ups.append("观察高位股能否带动补涨扩散，还是仅龙头孤军")
    if {"limit_heat", "limit_advance_cluster"} & trig:
        follow_ups.append("看连板高度与晋级率，确认资金接力意愿")
    if gaps or tiers["peripheral"]:
        follow_ups.append("对 graph_only / 缺口公司补研报与官方披露（disclosure-archive → apply）")
    follow_ups.extend(f"市场结构推演路径跟踪：{item}" for item in quality_context.methodology_checks if "缺口" in item)
    for mod_name, item in module_follow_ups:
        follow_ups.append(f"[{mod_name}] {item}")
    if not follow_ups:
        follow_ups.append("补充盘面与基本面证据后再评估")

    tier = (result.candidate_tier or "").lower()
    if "deep" in tier:
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
    wiki_section.extend(wiki_lines or ["（wiki 向量检索未启用/未接入/无命中）"])

    evidence_chain = (
        [f"{SUBHEAD}盘面"] + (market_lines or ["（当日无盘面候选命中）"])
        + [f"{SUBHEAD}图谱·概念"] + (graph_concept_lines or ["（图谱未命中概念）"])
        + [f"{SUBHEAD}图谱·公司分层"] + (company_lines or ["（图谱未命中公司暴露）"])
        + [f"{SUBHEAD}证据"] + (evidence_lines or ["（evidence_index 未命中）"])
        + [f"{SUBHEAD}图谱·语义召回(wiki 向量)"] + wiki_section
        + module_block
    )
    if question_plan.question_type in {QUESTION_MARKET_REVIEW, QUESTION_MARKET_FORECAST}:
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
    if options.use_l3_lookup:
        local_evidence_text = _evidence_text_for_llm(evidence_chain, gap_lines)
        l3_bundle = l3_evidence.lookup_l3_evidence(
            options.query,
            question_plan,
            local_evidence_text,
            config=l3_evidence.L3LookupConfig.from_env(
                enabled=True,
                timeout=options.l3_lookup_timeout,
                limit=options.l3_lookup_limit,
            ),
        )
        result.l3_evidence = l3_bundle
        result.warnings.extend(f"l3-evidence：{w}" for w in l3_bundle.warnings)
        l3_lines = l3_bundle.to_prompt_block().splitlines()
        evidence_chain.extend([f"{SUBHEAD}L3 官方证据工具补查", *l3_lines])

    # --- P0 技能链：证据分层审计 → 检索遥测 → 反证计划 →（深挖时）研究简报 ---
    audit = research_brief.audit_evidence_chain(evidence_chain, gap_lines)
    telemetry = research_brief.build_retrieval_telemetry(
        audit=audit,
        citation_tags=[c.tag for c in citations],
        wiki_stats=wiki_stats,
        l3_lookup_items=len(result.l3_evidence.items),
    )
    counter_plan = research_brief.build_counterevidence_plan(audit, stage=quality_context.stage)
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
        evidence_text = _evidence_text_for_llm(evidence_chain, gap_lines)
        refined, reason = llm_refine.refine_or_reason(
            options.query, theme, evidence_text,
            model_override=options.llm_model, timeout=options.llm_timeout,
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
        compose_evidence_chain = (
            _market_review_evidence_chain(evidence_chain)
            if is_market_review
            else evidence_chain
        )
        evidence_text = _evidence_text_for_llm(
            compose_evidence_chain,
            [] if is_market_review else gap_lines,
        )
        if result.data_notice:
            evidence_text = (
                f"## 本轮数据说明\n{result.data_notice}\n\n{evidence_text}"
            )
        if result.question_plan is not None:
            evidence_text = f"{result.question_plan.to_prompt_block()}\n\n{evidence_text}"
        if not is_market_review:
            evidence_text = (
                f"{evidence_text}\n\n{audit.to_prompt_block()}"
                f"\n\n{telemetry.to_prompt_block()}\n\n{counter_plan.to_prompt_block()}"
            )
        if result.stock_brief is not None:
            evidence_text = f"{evidence_text}\n\n{result.stock_brief.to_prompt_block()}"
        if result.market_state is not None:
            evidence_text = f"{evidence_text}\n\n{result.market_state.to_prompt_block()}"
        if result.theme_lifecycle is not None:
            evidence_text = f"{evidence_text}\n\n{result.theme_lifecycle.to_prompt_block()}"
        if result.event_brief is not None:
            evidence_text = f"{evidence_text}\n\n{result.event_brief.to_prompt_block()}"
        if result.gap_radar is not None:
            evidence_text = f"{evidence_text}\n\n{result.gap_radar.to_prompt_block()}"
        if result.valuation_note is not None:
            evidence_text = f"{evidence_text}\n\n{result.valuation_note.to_prompt_block()}"
        if result.forecast_preflight is not None:
            evidence_text = f"{evidence_text}\n\n{forecast_preflight.render_preflight_prompt(result.forecast_preflight)}"
        # --- planner-worker 并行取数：规则门控先定「要哪些块」，命中的块作为互相独立的
        # 子任务并行取数（ask_planner），取回后仍按固定顺序汇总——evidence_text/引用编号
        # 与串行版逐字节一致，并行只是快。D3 依赖前面块的 evidence_text，单独串行收尾。---
        anchored_name = result.anchored_entity.entity if result.anchored_entity is not None else None
        block_tasks: list[ask_planner.BlockTask] = []

        if options.include_timeseries_block:
            ts_intent = market_timeseries.parse_timeseries_intent(options.query)
            if ts_intent is not None:
                def _build_d0(intent=ts_intent):
                    block = market_timeseries.timeseries_block_for_llm(intent, options.market_db_path)
                    metric_labels = "/".join(spec.label for spec in intent.metrics)
                    return block, Citation(
                        "D0",
                        "本地 DuckDB 盘面时序直查数据块",
                        f"白名单指标逐日直查（{metric_labels}，过去 {intent.window} 个交易日）",
                    )

                block_tasks.append(ask_planner.BlockTask("D0", "盘面时序直查", _build_d0))
        if options.include_midterm_block:
            midterm_intent = market_midterm.parse_midterm_intent(options.query)
            if midterm_intent is not None:
                def _build_d6(intent=midterm_intent):
                    block = market_midterm.midterm_trend_block_for_llm(
                        options.query, theme, options.market_db_path, intent.window,
                    )
                    return block, Citation(
                        "D6",
                        "本地 DuckDB 多日/中期趋势数据块",
                        f"题材近 {intent.window} 日双红天数/成交额趋势/拥挤度分位（中期赔率视角）",
                    )

                block_tasks.append(ask_planner.BlockTask("D6", "多日中期趋势", _build_d6))
        if options.include_moneyflow_block and (
            options.force_moneyflow_block
            or market_moneyflow.parse_moneyflow_intent(options.query)
        ):
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

            block_tasks.append(ask_planner.BlockTask("D9", "L2 大单资金流", _build_d9))
        if options.include_analog_block and market_analogs.parse_analog_intent(options.query):
            def _build_d8():
                block = market_analogs.analog_block_for_llm(options.query, theme, options.market_db_path)
                return block, Citation(
                    "D8",
                    "本地 DuckDB 历史类比检索数据块",
                    f"题材自身历史上与当前 {market_analogs.DEFAULT_WINDOW} 日形态最相似窗口及后续 5/10/20 日实际走法（小样本历史事实，非概率预测）",
                )

            block_tasks.append(ask_planner.BlockTask("D8", "历史类比检索", _build_d8))
        if options.include_financials_block and market_financials.parse_financials_intent(options.query):
            def _build_d7():
                block = _financials_block_for_llm(options.query, options.market_db_path)
                return block, Citation(
                    "D7",
                    "东财 F10 逐季财报数据块",
                    "目标近 N 期累计营收/归母净利/毛利率/净利率（+同比），业绩兑现节奏视角",
                )

            block_tasks.append(ask_planner.BlockTask("D7", "逐季财报", _build_d7))
        if options.include_news_block and market_news.parse_news_intent(options.query):
            def _build_w7():
                news_keyword = market_news.resolve_news_keyword(options.query, theme, anchored_name)
                block = market_news.news_block_for_keyword(news_keyword)
                return block, Citation(
                    "W7",
                    "web 事件检索数据块（东财资讯 + web-access 全网检索）",
                    f"「{news_keyword}」近 {market_news.DEFAULT_WITHIN_DAYS} 天资讯日期/来源/标题/链接（只列不编，消息面存在性证据）",
                )

            block_tasks.append(ask_planner.BlockTask("W7", "web 事件检索", _build_w7))
        if options.include_memory_block:
            def _build_m():
                block = user_memory.memory_block_for_query(
                    options.query, theme, anchored_name, user=options.user,
                )
                return block, Citation(
                    "M",
                    "用户记忆检索块",
                    "相关性召回的用户既有核心判断/纠偏原则/回检胜率（非市场事实，承接往前推）",
                )

            block_tasks.append(ask_planner.BlockTask("M", "用户记忆检索", _build_m))
        if options.include_recall_block:
            def _build_v():
                block = checkpoint_recall.recall_block_for_query(
                    options.query, theme, anchored_name,
                    user=options.user,
                    data_asof=_market_data_asof(options.market_db_path),
                )
                return block, Citation(
                    "V",
                    "回检块（历史可证伪判断×裁决）",
                    "系统对该题材/个股登记过的可证伪判断及最新裁决 hit/miss/partial/unverifiable，"
                    "附数据新鲜度自检（裁决快照非新预测，未终态不作数）",
                )

            block_tasks.append(ask_planner.BlockTask("V", "回检块", _build_v))
        if options.include_market_value_block and not is_market_review:
            def _build_d1():
                block = _market_value_block_for_llm(options.query, theme, options.market_db_path)
                return block, Citation(
                    "D1",
                    "本地 DuckDB 市场价值数据块",
                    "CAR/峰后回撤/半衰期代理/同题材强势替代队列",
                )

            block_tasks.append(ask_planner.BlockTask("D1", "市场价值与替代队列", _build_d1))
        if options.include_mainline_context_block:
            def _build_d4():
                block = _mainline_context_block_for_llm(options.query, theme, options.market_db_path)
                return block, Citation(
                    "D4",
                    "本地 DuckDB 主线题材结构数据块",
                    "每日主线题材/核心板块/cycle_status/缩放量解释",
                )

            block_tasks.append(ask_planner.BlockTask("D4", "主线题材结构", _build_d4))
        if options.include_customer_hardness_block and not is_market_review:
            def _build_d2():
                block = _customer_evidence_hardness_block_for_llm(evidence_chain, gap_lines)
                return block, Citation(
                    "D2",
                    "本地证据链客户硬度数据块",
                    "客户/订单/量产/送样/验证证据按硬度分层",
                )

            block_tasks.append(ask_planner.BlockTask("D2", "客户证据硬度", _build_d2))
        if options.include_valuation_block and question_plan.question_type == QUESTION_VALUATION:
            def _build_d5():
                block = _valuation_block_for_llm(options.query, result.matched_theme, options.market_db_path)
                return block, Citation(
                    "D5",
                    "东财快照估值数据块",
                    "目标 PE/PB/市值 + 同题材可比估值带与横截面分位",
                )

            block_tasks.append(ask_planner.BlockTask("D5", "估值数据块", _build_d5))

        outcomes = ask_planner.run_block_tasks(block_tasks, parallel=options.parallel_blocks)
        d5_outcome: ask_planner.BlockOutcome | None = None
        for outcome in outcomes:
            if outcome.tag == "D5":
                d5_outcome = outcome  # D5 按原有顺序在 D3 之后汇总
                continue
            evidence_text = _append_block_outcome(result, outcome, evidence_text, citations)
        # D3 依赖此前累积的 evidence_text（文本兜底路径），必须在其他块汇总后串行生成。
        if options.include_second_derivative_block and not is_market_review:
            second_derivative_block = _second_derivative_queue_block_for_llm(
                options.query,
                theme,
                options.market_db_path,
                evidence_text,
            )
            result.d_block_stats.append(_d_block_stat("D3", "二阶导研究队列", second_derivative_block))
            if second_derivative_block:
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
        citation_legend = "\n".join(
            f"[{c.tag}] {c.source}" + (f" — {c.detail}" if c.detail else "") for c in citations
        )
        us = userspace.user_space(options.user)
        cards, card_warn = experience_cards.load_cards(
            us.experience_cards_path,
            window=options.experience_cards_window,
        )
        if card_warn:
            result.warnings.append(card_warn)
        selected_cards = experience_cards.select_relevant_cards(cards, options.query)
        experience_guidance = experience_cards.render_for_prompt(selected_cards)
        exemplar_guidance = _exemplar_guidance_for(question_plan.question_type)
        if options.include_scenario_guidance:
            scenario_guidance = scenario_tree.scenario_guidance_for_query(
                options.query, question_plan.question_type
            )
            if scenario_guidance:
                experience_guidance = (
                    f"{experience_guidance}\n\n{scenario_guidance}" if experience_guidance else scenario_guidance
                )
        msgs = llm_refine.build_synthesis_messages(
            options.query,
            theme,
            evidence_text,
            citation_legend=citation_legend,
            quality_context=quality_context,
            experience_guidance=experience_guidance,
            exemplar_guidance=exemplar_guidance,
        )
        if options.conversation_context:
            msgs.insert(
                1,
                {
                    "role": "system",
                    "content": (
                        "以下会话上下文仅用于理解指代和用户意图，不是本轮检索证据；"
                        "事实判断仍须引用当前轮证据：\n"
                        f"{options.conversation_context}"
                    ),
                },
            )
        if options.stream_text_delta is not None:
            notice_emitted = False

            def _emit_human_delta(delta: str) -> None:
                nonlocal notice_emitted
                if result.data_notice and not notice_emitted:
                    options.stream_text_delta(f"{result.data_notice}\n\n")
                    notice_emitted = True
                options.stream_text_delta(delta)

            composed, reason = llm_refine.synthesize_messages_stream(
                msgs,
                on_delta=_emit_human_delta,
                is_cancelled=options.stream_cancel_check,
                model_override=options.llm_model,
                timeout=options.llm_timeout,
            )
        elif options.compose_self_review:
            composed, reason = llm_refine.synthesize_messages_with_review(
                msgs, model_override=options.llm_model, timeout=options.llm_timeout,
            )
        else:
            composed, reason = llm_refine.synthesize_messages(
                msgs, model_override=options.llm_model, timeout=options.llm_timeout,
            )
        if composed is not None:
            result.synthesis = (
                f"{result.data_notice}\n\n{composed.answer}"
                if result.data_notice
                else composed.answer
            )
            result.llm_provider = composed.provider
            result.synthesis_messages = msgs + [
                {"role": "assistant", "content": result.synthesis}
            ]
            if reason:
                result.warnings.append(reason)
        else:
            result.warnings.append(reason)

    result.review_gate = output_review.review_output(
        trade_date=result.trade_date,
        audit=audit,
        counter_plan=counter_plan,
        gap_lines=gap_lines,
        follow_ups=follow_ups,
        conclusion_lines=conclusion,
        final_answer=result.synthesis,
    )
    result.warnings.extend(
        f"输出质检：{c.name}——{c.note}" for c in result.review_gate.checks if c.status == output_review.WARN
    )
    # 修订版在前契约：WARN 意见回灌同一段对话做一轮定向修订，用户拿到可直接引用的
    # 修订版全文，审查意见退居「输出质检」附录；修订失败时保留初稿并记录原因。
    if (
        options.compose_revise_on_warn
        and options.stream_text_delta is None
        and result.synthesis is not None
        and result.synthesis_messages is not None
        and result.review_gate.warn_count > 0
    ):
        warn_notes = [
            f"{c.name}：{c.note}" for c in result.review_gate.checks if c.status == output_review.WARN
        ]
        revision_user = {"role": "user", "content": llm_refine.gate_revision_user_content(warn_notes)}
        revised, rev_reason = llm_refine.synthesize_messages(
            result.synthesis_messages + [revision_user],
            model_override=options.llm_model,
            timeout=options.llm_timeout,
            temperature=0.2,
        )
        if revised is not None:
            result.synthesis = (
                f"{result.data_notice}\n\n{revised.answer}"
                if result.data_notice
                else revised.answer
            )
            result.synthesis_messages = result.synthesis_messages + [
                revision_user,
                {"role": "assistant", "content": result.synthesis},
            ]
            result.warnings.append(
                f"输出质检 {len(warn_notes)} 条 WARN 已回灌定向修订（正文为修订版，审查意见见「输出质检」附录）"
            )
        elif rev_reason:
            result.warnings.append(f"质检 WARN 回灌修订失败，保留初稿：{rev_reason}")
    result.sections = {
        "结论": conclusion,
        "证据链": evidence_chain,
        "分歧反证": gap_lines,
        "后续验证点": follow_ups,
        "检索可观测": telemetry.summary_lines() + research_brief.summarize_d_blocks(result.d_block_stats),
        "输出质检": result.review_gate.summary_lines(),
        "交易含义": implication_lines,
        "引用来源": [f"[{c.tag}] {c.source}" + (f" — {c.detail}" if c.detail else "") for c in citations],
    }
    result.citations = citations
    return result


def _evidence_text_for_llm(evidence_chain: list[str], gap_lines: list[str]) -> str:
    """Flatten the retrieved 证据链 + 分歧反证 into plain text for the LLM prompt."""
    out: list[str] = ["## 证据链"]
    for item in evidence_chain:
        if item.startswith(SUBHEAD):
            out.append(f"### {item[len(SUBHEAD):]}")
        else:
            out.append(f"- {item}")
    out.append("## 分歧反证")
    out.extend(f"- {g}" for g in gap_lines)
    return "\n".join(out)


def _market_review_evidence_chain(evidence_chain: list[str]) -> list[str]:
    """Keep broad market-review synthesis focused on market-level evidence."""
    allowed_sections = {
        "盘面",
        "最新市场总览（本地 DuckDB）",
    }
    filtered: list[str] = []
    include_section = False
    for item in evidence_chain:
        if item.startswith(SUBHEAD):
            section = item[len(SUBHEAD):]
            include_section = section in allowed_sections
            if include_section:
                filtered.append(item)
            continue
        if include_section:
            filtered.append(item)
    return filtered


def _customer_evidence_hardness_block_for_llm(evidence_chain: list[str], gap_lines: list[str]) -> str:
    """Classify customer/order evidence into hardness buckets for compose answers."""
    hard: list[str] = []
    candidate: list[str] = []
    weak: list[str] = []
    rebuttal: list[str] = []
    for raw in [*evidence_chain, *gap_lines]:
        if raw.startswith(SUBHEAD):
            continue
        line = re.sub(r"\s+", " ", str(raw or "")).strip()
        if not line or line.startswith("（"):
            continue
        bucket = _classify_customer_evidence_line(line)
        if bucket == "hard":
            _append_unique_limited(hard, _shorten_evidence_line(line))
        elif bucket == "candidate":
            _append_unique_limited(candidate, _shorten_evidence_line(line))
        elif bucket == "weak":
            _append_unique_limited(weak, _shorten_evidence_line(line))
        elif bucket == "rebuttal":
            _append_unique_limited(rebuttal, _shorten_evidence_line(line))

    lines = ["## 客户证据硬度数据块 [D2]"]
    lines.append("- 硬证据：" + ("；".join(hard[:4]) if hard else "未从本轮证据链识别到公告/互动易/年报等官方口径的订单、量产、批量供货、收入或客户验证硬证据。"))
    lines.append("- 候选证据：" + ("；".join(candidate[:4]) if candidate else "未识别到带客户/导入/送样/审厂/收入目标的研报或调研候选证据。"))
    lines.append("- 弱证据/研报推断：" + ("；".join(weak[:4]) if weak else "未识别到仅有空间测算、预期、市场传闻或无客户落点的弱证据。"))
    lines.append("- 反证/缺口：" + ("；".join(rebuttal[:4]) if rebuttal else "本轮证据未给出明确反证；仍需检查是否存在公司口径保守、未并表、低占比或尚未进入财务的约束。"))
    lines.append("- 使用要求：回答时必须先说客户证据属于硬证据、候选证据还是弱证据；硬证据可支撑当期逻辑，候选证据只能支撑跟踪假设，弱证据不能直接当作基本面兑现。")
    return "\n".join(lines)


def _classify_customer_evidence_line(line: str) -> str | None:
    text = line.lower()
    customer_terms = r"客户|终端|订单|合同|中标|量产|批量|供货|出货|导入|认证|审厂|验证|收入|定点|供应商|配套|a客户|b客户"
    rebuttal_terms = r"否认|未确认|尚未|暂无|缺失|低占比|保守|未进入财务|不并表|亏损|证据不足|待证|待验证|不确定|缺口"
    hard_source_terms = r"公告|互动|年报|季报|半年报|招股书|定期报告|问询函|交易所|公司|官网|监管|合同|中标"
    hard_action_terms = r"量产|批量|订单|合同|中标|收入|出货|供货|定点|认证|客户验证|通过验证"
    candidate_source_terms = r"研报|调研|纪要|卖方|券商|ima|晨汇|产业链"
    weak_terms = r"预计|有望|推断|猜测|传闻|市场|空间|目标|测算|可能|预期|或将|弹性"
    has_customer = re.search(customer_terms, text) is not None
    if re.search(rebuttal_terms, text):
        return "rebuttal"
    if not has_customer and not re.search(hard_action_terms, text):
        return None
    if re.search(hard_source_terms, text) and re.search(hard_action_terms, text):
        return "hard"
    if re.search(candidate_source_terms, text) and (has_customer or re.search(hard_action_terms, text)):
        return "candidate"
    if re.search(weak_terms, text):
        return "weak"
    return "candidate" if has_customer else None


def _append_unique_limited(items: list[str], value: str, limit: int = 8) -> None:
    if value and value not in items and len(items) < limit:
        items.append(value)


def _shorten_evidence_line(line: str, max_chars: int = 120) -> str:
    line = line.replace(SUBHEAD, "")
    return line if len(line) <= max_chars else line[: max_chars - 1] + "…"


def _mainline_context_block_for_llm(
    query: str,
    theme: str | None,
    market_db_path: str | Path | None,
    lookback_days: int = 20,
) -> str:
    """Build the D4 mainline-theme structure block from local DuckDB.

    Grain: trade_date × mainline theme × core sector. This is L4 market signal,
    not entity baseline or hard company evidence.
    """
    db_path = Path(market_db_path).expanduser() if market_db_path else REPO_ROOT / "db" / "market_feature_store.duckdb"
    if not db_path.exists():
        return ""
    try:
        import duckdb  # type: ignore
    except Exception:
        return ""
    try:
        con = duckdb.connect(str(db_path), read_only=True)
    except Exception:
        return ""
    try:
        exists = con.execute(
            "select count(*) from information_schema.tables where table_name='fact_mainline_sector_daily'"
        ).fetchone()[0]
        if not exists:
            return ""
        latest = con.execute("select max(trade_date) from fact_mainline_sector_daily").fetchone()[0]
        if not latest:
            return ""
        target_theme = _resolve_mainline_theme(con, query, theme, latest)
        params: list[Any] = [latest]
        theme_filter = ""
        if target_theme:
            theme_filter = "and m.theme_name = ?"
            params.append(target_theme)
        rows = con.execute(
            f"""
            select
              m.trade_date, m.theme_name, m.sector_name, m.sort_no,
              m.cycle_status, m.cycle_level, m.today_pct, m.limit_up_count,
              m.startup_date_small, m.high_status_label, m.near_breakout_label,
              coalesce(s.pct_chg, m.today_pct) as sector_pct,
              s.diff_ratio, coalesce(s.amount, m.amount / 10000.0) as sector_amount,
              s.sw_l1
            from fact_mainline_sector_daily m
            left join fact_sector_daily s
              on m.trade_date = s.trade_date and m.sector_ts_code = s.sector_ts_code
            where m.trade_date = ? {theme_filter}
            order by m.theme_name, m.sort_no nulls last, m.sector_name
            limit 30
            """,
            params,
        ).fetchall()
        if not rows:
            return ""
        cutoff = latest - timedelta(days=int(lookback_days)) if hasattr(latest, "__sub__") else latest
        history_params: list[Any] = [latest, cutoff]
        history_filter = ""
        if target_theme:
            history_filter = "and theme_name = ?"
            history_params.append(target_theme)
        history = con.execute(
            f"""
            select theme_name, count(distinct trade_date) as day_count,
                   min(trade_date) as first_date, max(trade_date) as last_date,
                   count(*) as sector_rows
            from fact_mainline_sector_daily
            where trade_date <= ?
              and trade_date >= ?
              {history_filter}
            group by theme_name
            order by day_count desc, sector_rows desc, theme_name
            limit 8
            """,
            history_params,
        ).fetchall()
        lines = ["## 主线题材结构数据块 [D4]"]
        matched = target_theme or "最新全市场主线"
        lines.append(f"- 最新主线日期：{latest}；匹配口径：{matched}；该块是 L4_market_signal，只能说明市场主线归因，不等同公司基本面兑现。")
        if history:
            hist_text = "；".join(
                f"{name}近{lookback_days}日出现{days}天（{first}~{last}，板块行{sector_rows}）"
                for name, days, first, last, sector_rows in history[:5]
            )
            lines.append(f"- 主线持续性：{hist_text}")
        grouped: dict[str, list[tuple[Any, ...]]] = {}
        for row in rows:
            grouped.setdefault(str(row[1]), []).append(row)
        for theme_name, items in grouped.items():
            sector_bits = []
            for row in items[:8]:
                (
                    _td,
                    _theme_name,
                    sector_name,
                    _sort_no,
                    cycle_status,
                    cycle_level,
                    _today_pct,
                    limit_up_count,
                    startup_date_small,
                    high_status_label,
                    near_breakout_label,
                    sector_pct,
                    diff_ratio,
                    sector_amount,
                    sw_l1,
                ) = row
                volume_state = _classify_mainline_volume_state(sector_pct, diff_ratio, sector_amount)
                breakout = high_status_label or near_breakout_label or ""
                breakout_text = f"，{breakout}" if breakout else ""
                startup_text = f"，启动日{startup_date_small}" if startup_date_small else ""
                sector_bits.append(
                    f"{sector_name}({sw_l1 or '-'}，{cycle_status or '未标注'}/{cycle_level or '-'}，"
                    f"涨{_fmt_optional(sector_pct)}%，边际量{_fmt_optional(diff_ratio)}%，"
                    f"成交{_fmt_optional(sector_amount)}亿，涨停{limit_up_count or 0}，{volume_state}{breakout_text}{startup_text})"
                )
            lines.append(f"- {theme_name}核心板块：" + "；".join(sector_bits))
        lines.append("- 使用要求：回答时要区分连续主线与新启动主线；cycle_status=分歧/消亡不能写成无条件主升；涨幅为正但 diff_ratio 为负时，优先解释为缩量强修复/存量抱团，而不是低位放量启动。")
        return "\n".join(lines)
    except Exception:
        return ""
    finally:
        try:
            con.close()
        except Exception:
            pass


def _resolve_mainline_theme(con: Any, query: str, theme: str | None, latest_date: Any) -> str | None:
    rows = con.execute(
        """
        select distinct theme_name
        from fact_mainline_sector_daily
        where trade_date=?
        order by theme_name
        """,
        [latest_date],
    ).fetchall()
    names = [str(r[0]) for r in rows if r and r[0]]
    text = f"{query or ''} {theme or ''}"
    normalized_text = _normalize(text)
    for name in names:
        n = _normalize(name)
        if n and (n in normalized_text or normalized_text in n):
            return name
    return None


def _classify_mainline_volume_state(pct_chg: Any, diff_ratio: Any, amount: Any) -> str:
    pct = _safe_float(pct_chg)
    diff = _safe_float(diff_ratio)
    amt = _safe_float(amount)
    if pct is not None and pct > 0 and diff is not None and diff > 10 and (amt is None or amt > 500):
        return "真正双红/增量启动"
    if pct is not None and pct > 0 and diff is not None and diff < 0:
        return "缩量强修复/存量抱团"
    if pct is not None and pct > 0 and diff is not None and diff >= 0:
        return "弱放量修复"
    if pct is not None and pct < 0 and diff is not None and diff > 0:
        return "放量分歧/承接检验"
    return "量价状态待确认"


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_optional(value: Any, digits: int = 2) -> str:
    num = _safe_float(value)
    if num is None:
        return "-"
    return f"{num:.{digits}f}"


def _second_derivative_queue_block_for_llm(
    query: str,
    theme: str | None,
    market_db_path: str | Path | None,
    evidence_text: str,
) -> str:
    """Build a structured P0/P1/P2 second-derivative research queue."""
    db_path = Path(market_db_path).expanduser() if market_db_path else REPO_ROOT / "db" / "market_feature_store.duckdb"
    if not db_path.exists():
        return _second_derivative_queue_from_text_only(theme, evidence_text)
    try:
        import duckdb  # type: ignore
    except Exception:
        return _second_derivative_queue_from_text_only(theme, evidence_text)

    try:
        con = duckdb.connect(str(db_path), read_only=True)
    except Exception:
        return _second_derivative_queue_from_text_only(theme, evidence_text)

    try:
        stock = _resolve_stock_for_market_block(con, query)
        if not stock:
            return _second_derivative_queue_from_text_only(theme, evidence_text)
        stock_code, stock_name = stock
        latest = con.execute(
            """
            select trade_date, close, pct_chg, amount
            from fact_stock_daily
            where stock_ts_code=? and close is not null
            order by trade_date desc
            limit 1
            """,
            [stock_code],
        ).fetchone()
        if not latest:
            return _second_derivative_queue_from_text_only(theme, evidence_text)
        latest_date, latest_close, latest_pct, latest_amount = latest
        sector_rows = con.execute(
            """
            select sector_name, sw_l1, pct_chg, amount
            from fact_sector_stock_daily
            where trade_date=? and stock_ts_code=?
            order by amount desc
            limit 8
            """,
            [latest_date, stock_code],
        ).fetchall()
        sector_names = _prioritize_sector_names([str(r[0]) for r in sector_rows if r and r[0]], theme)
        sector_lines = _format_sector_state_lines(con, latest_date, sector_names[:5])
        rank_lines = _format_stock_rank_lines(con, latest_date, stock_code, sector_names)
        alternative_lines = _format_alternative_queue_lines(con, latest_date, stock_code, sector_names[:4])
        bottlenecks = _extract_bottleneck_terms(evidence_text)

        lines = ["## 二阶导研究队列数据块 [D3]"]
        lines.append(
            f"- 标的状态：{stock_name}（{stock_code}）最新有效交易日 {latest_date}，涨跌幅 {latest_pct}%，成交额 {latest_amount} 亿；"
            + ("相对强度=" + "；".join(rank_lines[:4]) if rank_lines else "相对强度排名未取到")
        )
        lines.append(
            "- P0 盘面已选择的强势替代表达："
            + ("；".join(alternative_lines[:6]) if alternative_lines else "未从同题材中取到明确强势替代队列，需观察是否只是目标股孤立行情。")
        )
        lines.append(
            "- P1 目标股再升级条件："
            + f"观察 {stock_name} 是否重新进入所属题材涨幅/成交前排、是否收复近 90 日高点或形成新高，并且关联题材从非双红转为连续双红；"
            + ("当前关联题材状态=" + "；".join(sector_lines[:5]) if sector_lines else "当前关联题材双红状态未取到")
        )
        lines.append(
            "- P2 产业瓶颈补盲："
            + ("围绕 " + "、".join(bottlenecks[:8]) + " 查找客户验证、产能、良率、涨价、国产替代和上游材料/设备约束。" if bottlenecks else "本轮证据文本未抽到明确瓶颈词；需要用年报、互动易、公告或研报全文补公司产品结构、客户链和上游约束。")
        )
        lines.append(
            "- 反向观察：若板块继续有双红/新高集群但目标股相对强度掉队，优先把它降为后排跟随或旧逻辑分歧承接；若替代队列持续扩散而目标股不修复，说明市场可能已经选择了更优表达。"
        )
        return "\n".join(lines)
    except Exception:
        return _second_derivative_queue_from_text_only(theme, evidence_text)
    finally:
        try:
            con.close()
        except Exception:
            pass


def _second_derivative_queue_from_text_only(theme: str | None, evidence_text: str) -> str:
    bottlenecks = _extract_bottleneck_terms(evidence_text)
    lines = ["## 二阶导研究队列数据块 [D3]"]
    lines.append("- P0 盘面已选择的强势替代表达：本轮未取到 DuckDB 同题材强势替代队列，回答时必须把这一项作为数据缺口说明。")
    lines.append("- P1 目标股再升级条件：需要补最新相对强度、成交额边际、所属题材双红/新高/涨停扩散，确认它是核心、同步、补涨还是后排。")
    lines.append(
        "- P2 产业瓶颈补盲："
        + ("围绕 " + "、".join(bottlenecks[:8]) + " 继续查客户验证、订单、产能和上游约束。" if bottlenecks else f"围绕 {theme or '命中主题'} 补上游材料/设备、关键客户、价格传导和替代公司。")
    )
    lines.append("- 反向观察：若缺少 P0/P1 数据，不能直接给出强趋势结论，只能提出待验证假设。")
    return "\n".join(lines)


def _extract_bottleneck_terms(text: str) -> list[str]:
    terms = [
        "HBM",
        "DDR5",
        "CXL",
        "TLVR",
        "AI电感",
        "钽电容",
        "MLCC",
        "LTCC",
        "银浆",
        "磁性材料",
        "陶瓷粉体",
        "玻璃基板",
        "CoWoS",
        "先进封装",
        "存储",
        "光模块",
        "CPO",
        "交换芯片",
        "电源模块",
        "功率模块",
        "良率",
        "产能",
        "涨价",
        "国产替代",
        "客户验证",
        "量产",
    ]
    out: list[str] = []
    lower = text.lower()
    for term in terms:
        if term.lower() in lower and term not in out:
            out.append(term)
    return out


def _append_block_outcome(
    result: AskResult,
    outcome: ask_planner.BlockOutcome,
    evidence_text: str,
    citations: list[Citation],
) -> str:
    """把并行子任务的取数结果按原有串行语义汇总：登记可观测、拼 evidence、记引用。"""
    if outcome.error:
        result.warnings.append(f"{outcome.tag} {outcome.label}块生成失败（已降级为缺失）：{outcome.error}")
    result.d_block_stats.append(_d_block_stat(outcome.tag, outcome.label, outcome.block))
    if outcome.block:
        evidence_text = f"{evidence_text}\n\n{outcome.block}"
        if outcome.citation is not None:
            citations.append(outcome.citation)
    return evidence_text


def _d_block_stat(tag: str, source: str, block: str | None) -> research_brief.DBlockStat:
    text = (block or "").strip()
    return research_brief.DBlockStat(
        tag,
        source,
        attempted=True,
        generated=bool(text),
        line_count=len(text.splitlines()) if text else 0,
        note="" if text else "无匹配数据或未提供 market_db_path",
    )


def _daily_market_overview_block_for_llm(
    market_db_path: str | Path | None,
) -> str:
    db_path = (
        Path(market_db_path).expanduser()
        if market_db_path
        else REPO_ROOT / "db" / "market_feature_store.duckdb"
    )
    if not db_path.exists():
        return ""
    try:
        import duckdb

        con = duckdb.connect(str(db_path), read_only=True)
    except Exception:
        return ""

    try:
        table_names = {
            str(row[0])
            for row in con.execute(
                """
                select table_name
                from information_schema.tables
                where table_schema = 'main'
                """
            ).fetchall()
        }
        if "fact_market_daily" not in table_names:
            return ""

        available_columns = {
            str(row[1])
            for row in con.execute("pragma table_info('fact_market_daily')").fetchall()
        }
        wanted_columns = (
            "trade_date",
            "market_stage",
            "stage_day",
            "total_amount",
            "amount_vs_yesterday_pct",
            "volume_ratio",
            "volume_state",
            "advancers",
            "limit_up",
            "limit_down",
            "sh_index_close",
            "sh_index_pct_chg",
            "concentration_state",
            "industry_1",
            "industry_1_ratio",
            "industry_2",
            "industry_2_ratio",
            "industry_3",
            "industry_3_ratio",
            "strength_avg_pct",
            "strength_marginal_pct",
            "strength_status",
        )
        select_columns = [
            column if column in available_columns else f"null as {column}"
            for column in wanted_columns
        ]
        row = con.execute(
            f"""
            select {", ".join(select_columns)}
            from fact_market_daily
            order by trade_date desc
            limit 1
            """
        ).fetchone()
        if not row or not row[0]:
            return ""

        values = dict(zip(wanted_columns, row, strict=True))
        trade_date = str(values["trade_date"])
        stage = str(values["market_stage"] or "未标注")
        stage_day = values["stage_day"]
        stage_text = f"{stage}（第 {stage_day} 天）" if stage_day is not None else stage
        lines = [
            "## 本地 DuckDB 最新市场总览",
            f"- 市场数据截至：{trade_date}。该日期是本轮整体盘面日期。",
            f"- 市场阶段：{stage_text}；量能状态：{values['volume_state'] or '未标注'}。",
            (
                f"- 全市场成交额：{_fmt_optional(values['total_amount'])} 亿元；"
                f"较前一日 {_fmt_optional(values['amount_vs_yesterday_pct'])}%；"
                f"量比 {_fmt_optional(values['volume_ratio'])}%。"
            ),
            (
                f"- 涨跌结构：上涨 {values['advancers'] if values['advancers'] is not None else '-'} 家；"
                f"涨停 {values['limit_up'] if values['limit_up'] is not None else '-'} 家；"
                f"跌停 {values['limit_down'] if values['limit_down'] is not None else '-'} 家。"
            ),
            (
                f"- 上证指数：{_fmt_optional(values['sh_index_close'], 3)} 点，"
                f"当日 {_fmt_optional(values['sh_index_pct_chg'])}%。"
            ),
            (
                f"- 强势股状态：{values['strength_status'] or '未标注'}；"
                f"平均涨幅 {_fmt_optional(values['strength_avg_pct'])}%；"
                f"边际变化 {_fmt_optional(values['strength_marginal_pct'])}%。"
            ),
        ]

        industries = [
            (values["industry_1"], values["industry_1_ratio"]),
            (values["industry_2"], values["industry_2_ratio"]),
            (values["industry_3"], values["industry_3_ratio"]),
        ]
        industry_text = "、".join(
            f"{name}（{_fmt_optional(ratio)}%）"
            for name, ratio in industries
            if name
        )
        if industry_text:
            lines.append(
                f"- 行业集中度：{values['concentration_state'] or '未标注'}；"
                f"领先行业为 {industry_text}。"
            )

        if "fact_mainline_theme_daily" in table_names:
            theme_date_row = con.execute(
                "select max(trade_date) from fact_mainline_theme_daily"
            ).fetchone()
            theme_date = theme_date_row[0] if theme_date_row else None
            if theme_date:
                themes = con.execute(
                    """
                    select theme_name, sector_count
                    from fact_mainline_theme_daily
                    where trade_date = ?
                    order by min_sort nulls last, theme_name
                    limit 10
                    """,
                    [theme_date],
                ).fetchall()
                theme_text = "、".join(
                    f"{name}（{sector_count or 0} 个核心板块）"
                    for name, sector_count in themes
                    if name
                )
                if theme_text:
                    lines.append(f"- 主线题材（截至 {theme_date}）：{theme_text}。")

        if "fact_mainline_sector_daily" in table_names:
            sector_date_row = con.execute(
                "select max(trade_date) from fact_mainline_sector_daily"
            ).fetchone()
            sector_date = sector_date_row[0] if sector_date_row else None
            if sector_date and str(sector_date) != trade_date:
                lines.append(
                    f"- 局部数据提示：主线板块明细表仅更新到 {sector_date}，"
                    f"早于整体盘面日期 {trade_date}；只能作历史参考，不能覆盖整体日期。"
                )
        return "\n".join(lines)
    except Exception:
        return ""
    finally:
        con.close()


def _market_data_asof(market_db_path: str | Path | None) -> str | None:
    """盘面库 fact_market_daily 最新交易日（回检块新鲜度自检用）；库/duckdb 不可用返回 None。"""
    db_path = Path(market_db_path).expanduser() if market_db_path else REPO_ROOT / "db" / "market_feature_store.duckdb"
    if not db_path.exists():
        return None
    try:
        import duckdb  # type: ignore

        con = duckdb.connect(str(db_path), read_only=True)
        try:
            row = con.execute("SELECT MAX(trade_date) FROM fact_market_daily").fetchone()
        finally:
            con.close()
        return str(row[0]) if row and row[0] else None
    except Exception:
        return None


def _market_value_block_for_llm(
    query: str,
    theme: str | None,
    market_db_path: str | Path | None,
) -> str:
    """Build a deterministic market-value and alternative-queue block.

    This is intentionally lightweight and best-effort. It enriches compose
    answers with measurable L4 context without turning the LLM into a calculator.
    """
    db_path = Path(market_db_path).expanduser() if market_db_path else REPO_ROOT / "db" / "market_feature_store.duckdb"
    if not db_path.exists():
        return ""
    try:
        import duckdb  # type: ignore
    except Exception:
        return ""

    try:
        con = duckdb.connect(str(db_path), read_only=True)
    except Exception:
        return ""
    try:
        stock = _resolve_stock_for_market_block(con, query)
        if not stock:
            return ""
        stock_code, stock_name = stock
        latest = con.execute(
            """
            select trade_date, close, pct_chg, amount
            from fact_stock_daily
            where stock_ts_code=? and close is not null
            order by trade_date desc
            limit 1
            """,
            [stock_code],
        ).fetchone()
        if not latest:
            return ""
        latest_date, latest_close, latest_pct, latest_amount = latest
        rows = con.execute(
            """
            select trade_date, close
            from fact_stock_daily
            where stock_ts_code=? and close is not null
              and trade_date >= cast(? as date) - interval 90 day
              and trade_date <= cast(? as date)
            order by trade_date
            """,
            [stock_code, latest_date, latest_date],
        ).fetchall()
        value_lines = _format_market_value_rows(rows, latest_close)

        sector_rows = con.execute(
            """
            select sector_name, sw_l1, pct_chg, amount
            from fact_sector_stock_daily
            where trade_date=? and stock_ts_code=?
            order by amount desc
            limit 8
            """,
            [latest_date, stock_code],
        ).fetchall()
        sector_names = _prioritize_sector_names([str(r[0]) for r in sector_rows if r and r[0]], theme)
        rank_lines = _format_stock_rank_lines(con, latest_date, stock_code, sector_names)
        sector_lines = _format_sector_state_lines(con, latest_date, sector_names[:5])
        alternative_lines = _format_alternative_queue_lines(con, latest_date, stock_code, sector_names[:4])

        lines = [
            "## 市场价值与替代队列数据块 [D1]",
            f"- 标的识别：{stock_name}（{stock_code}），最新有效交易日 {latest_date}，收盘 {latest_close}，当日涨跌幅 {latest_pct}%，成交额 {latest_amount} 亿。",
        ]
        lines.extend(value_lines)
        if sector_lines:
            lines.append("- 关联题材/行业状态：" + "；".join(sector_lines))
        if rank_lines:
            lines.append("- 个股相对强度排名：" + "；".join(rank_lines))
        if alternative_lines:
            lines.append("- 同题材强势替代队列：" + "；".join(alternative_lines))
        lines.append("- 使用要求：把该块用于回答 CAR/峰后回撤/半衰期代理、相对强度和二阶导，不要机械照抄；若指标口径不足，要说明这是本地 DuckDB 的代理口径。")
        return "\n".join(lines)
    except Exception:
        return ""
    finally:
        try:
            con.close()
        except Exception:
            pass


def _resolve_stock_for_market_block(con: Any, query: str) -> tuple[str, str] | None:
    code_match = re.search(r"\b(\d{6})(?:\.(SH|SZ|BJ))?\b", str(query or ""), re.I)
    if code_match:
        raw = code_match.group(1)
        suffix = code_match.group(2)
        if suffix:
            rows = con.execute(
                "select stock_ts_code, stock_name from fact_stock_daily where stock_ts_code=? limit 1",
                [f"{raw}.{suffix.upper()}"],
            ).fetchall()
        else:
            rows = con.execute(
                "select stock_ts_code, stock_name from fact_stock_daily where stock_ts_code like ? limit 1",
                [f"{raw}.%"],
            ).fetchall()
        if rows:
            return str(rows[0][0]), str(rows[0][1] or rows[0][0])
    rows = con.execute(
        """
        select stock_ts_code, stock_name
        from fact_stock_daily
        where stock_name is not null and stock_name <> ''
        group by stock_ts_code, stock_name
        """
    ).fetchall()
    q = str(query or "")
    matches = [(str(code), str(name)) for code, name in rows if str(name) and str(name) in q]
    if matches:
        matches.sort(key=lambda item: len(item[1]), reverse=True)
        return matches[0]
    return None


def _prioritize_sector_names(sector_names: list[str], theme: str | None) -> list[str]:
    """Prefer the matched theme when a stock is mapped to many sectors."""
    names = [s for s in dict.fromkeys(sector_names) if s]
    if not theme:
        return names
    normalized_theme = _normalize(theme)
    matched = [s for s in names if normalized_theme and (_normalize(s) in normalized_theme or normalized_theme in _normalize(s))]
    if not matched:
        return names
    preferred = matched[0]
    return [preferred] + [s for s in names if s != preferred]


def _format_market_value_rows(rows: list[tuple[Any, Any]], latest_close: float | None) -> list[str]:
    clean = [(r[0], float(r[1])) for r in rows if r and r[1] is not None]
    if len(clean) < 2 or latest_close is None:
        return ["- 市场价值成绩单：近 90 日有效行情不足，CAR/峰后回撤/半衰期代理未取到。"]
    base_date, base_close = clean[0]
    peak_date, peak_close = max(clean, key=lambda x: x[1])
    latest = float(latest_close)
    interval_gain = _pct(latest / base_close - 1)
    peak_gain = _pct(peak_close / base_close - 1)
    drawdown = _pct(latest / peak_close - 1)
    retention = None
    if peak_gain and peak_gain > 0:
        retention = latest / base_close - 1
        retention = round(retention / (peak_gain / 100) * 100, 2)
    half_life = "未跌破峰值收益一半" if retention is not None and retention >= 50 else "已跌破峰值收益一半" if retention is not None else "未计算"
    return [
        f"- 市场价值成绩单：从 {base_date} 到 {clean[-1][0]} 区间涨幅 {interval_gain}%，峰值日 {peak_date} 峰值涨幅 {peak_gain}%，峰后回撤 {drawdown}%，峰值收益保留率 {retention if retention is not None else '—'}%，半衰期代理={half_life}。",
    ]


def _format_stock_rank_lines(con: Any, latest_date: Any, stock_code: str, sector_names: list[str]) -> list[str]:
    if not sector_names:
        return []
    out: list[str] = []
    for sector in sector_names[:5]:
        row = con.execute(
            """
            with base as (
              select sector_name, stock_ts_code, stock_name, pct_chg, amount,
                     rank() over(partition by sector_name order by amount desc nulls last) as amount_rank,
                     rank() over(partition by sector_name order by pct_chg desc nulls last) as pct_rank,
                     count(*) over(partition by sector_name) as n
              from fact_sector_stock_daily
              where trade_date=? and sector_name=?
            )
            select amount_rank, pct_rank, n, pct_chg, amount
            from base where stock_ts_code=?
            """,
            [latest_date, sector, stock_code],
        ).fetchone()
        if row:
            out.append(f"{sector}成交排名{row[0]}/{row[2]}、涨幅排名{row[1]}/{row[2]}、涨跌幅{row[3]}%、成交{row[4]}亿")
    return out


def _format_sector_state_lines(con: Any, latest_date: Any, sector_names: list[str]) -> list[str]:
    if not sector_names:
        return []
    out: list[str] = []
    for sector in sector_names:
        row = con.execute(
            """
            select pct_chg, amount, diff_ratio
            from fact_sector_daily
            where trade_date=? and sector_name=?
            limit 1
            """,
            [latest_date, sector],
        ).fetchone()
        if row:
            proxy = "双红代理" if (row[0] or 0) > 0 and (row[2] or 0) > 0 else "非双红代理"
            out.append(f"{sector}{row[0]}%、成交{row[1]}亿、边际量{row[2]}%，{proxy}")
    return out


def _valuation_block_for_llm(
    query: str,
    theme: str | None,
    market_db_path: str | Path | None,
    fetcher: Any = None,
) -> str:
    """Build the D5 valuation block: target snapshot + same-theme peer band.

    目标/可比标的从本地 DuckDB 解析（可比取同板块成交额前排），估值快照走东财
    免费接口（valuation_estimate）；网络或库不可用时返回带显式缺口的块或空串。
    """
    fetch = fetcher or valuation_estimate.fetch_eastmoney_snapshot
    if not valuation_estimate.fetch_enabled():
        return valuation_estimate.build_valuation_block(None, [], fetch_disabled=True)
    db_path = Path(market_db_path).expanduser() if market_db_path else REPO_ROOT / "db" / "market_feature_store.duckdb"
    target_code: str | None = None
    target_name = ""
    peer_codes: list[tuple[str, str]] = []
    if db_path.exists():
        try:
            import duckdb  # type: ignore

            con = duckdb.connect(str(db_path), read_only=True)
            try:
                stock = _resolve_stock_for_market_block(con, query)
                if stock:
                    target_code, target_name = stock
                    latest = con.execute(
                        "select max(trade_date) from fact_sector_stock_daily where stock_ts_code=?",
                        [target_code],
                    ).fetchone()
                    latest_date = latest[0] if latest else None
                    if latest_date is not None:
                        sector_rows = con.execute(
                            """
                            select sector_name from fact_sector_stock_daily
                            where trade_date=? and stock_ts_code=?
                            order by amount desc limit 4
                            """,
                            [latest_date, target_code],
                        ).fetchall()
                        sectors = _prioritize_sector_names([str(r[0]) for r in sector_rows if r and r[0]], theme)
                        if sectors:
                            rows = con.execute(
                                """
                                select stock_ts_code, stock_name from fact_sector_stock_daily
                                where trade_date=? and sector_name=? and stock_ts_code<>?
                                order by amount desc nulls last limit 4
                                """,
                                [latest_date, sectors[0], target_code],
                            ).fetchall()
                            peer_codes = [(str(c), str(n or c)) for c, n in rows]
            finally:
                con.close()
        except Exception:
            pass
    if target_code is None:
        code_match = re.search(r"\b(\d{6})(?:\.(SH|SZ|BJ))?\b", str(query or ""), re.I)
        if not code_match:
            return ""
        target_code = code_match.group(1)
    target = fetch(target_code, target_name)
    peers = valuation_estimate.snapshots_for(peer_codes, fetcher=fetch)
    return valuation_estimate.build_valuation_block(target, peers)


def _financials_block_for_llm(
    query: str,
    market_db_path: str | Path | None,
    fetcher: Any = None,
) -> str:
    """Build the D7 quarterly-financials block for a single target stock.

    目标股从本地 DuckDB 解析（代码/名称），逐季财务走东财免费 F10（market_financials）；
    解析不到目标股时返回空串（不追加块），网络/库不可用时返回带显式缺口的块。
    """
    if not market_financials.fetch_enabled():
        return market_financials.build_financials_block("", "", [], fetch_disabled=True)
    db_path = Path(market_db_path).expanduser() if market_db_path else REPO_ROOT / "db" / "market_feature_store.duckdb"
    target_code: str | None = None
    target_name = ""
    if db_path.exists():
        try:
            import duckdb  # type: ignore

            con = duckdb.connect(str(db_path), read_only=True)
            try:
                stock = _resolve_stock_for_market_block(con, query)
                if stock:
                    target_code, target_name = stock
            finally:
                con.close()
        except Exception:
            pass
    if target_code is None:
        code_match = re.search(r"\b(\d{6})(?:\.(SH|SZ|BJ))?\b", str(query or ""), re.I)
        if not code_match:
            return ""
        target_code = code_match.group(0)
    return market_financials.financials_block_for_target(target_code, target_name, fetcher=fetcher)


def _format_alternative_queue_lines(con: Any, latest_date: Any, stock_code: str, sector_names: list[str]) -> list[str]:
    if not sector_names:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for sector in sector_names:
        rows = con.execute(
            """
            select sector_name, stock_name, pct_chg, amount, pct_chg_5d, pct_chg_10d, high_status_label, limit_times
            from fact_sector_stock_daily
            where trade_date=? and stock_ts_code<>? and sector_name=?
            order by pct_chg desc nulls last, amount desc nulls last
            limit 5
            """,
            [latest_date, stock_code, sector],
        ).fetchall()
        added_for_sector = 0
        for sector_name, name, pct, amount, pct5, pct10, high, limits in rows:
            if name in seen:
                continue
            seen.add(str(name))
            added_for_sector += 1
            tag = f"，{high}" if high else ""
            limit_tag = f"，涨停次数{limits}" if limits else ""
            out.append(f"{name}({sector_name}) {pct}%、成交{amount}亿、5日{pct5}%、10日{pct10}%{tag}{limit_tag}")
            if len(out) >= 6 or added_for_sector >= 3:
                break
        if len(out) >= 6:
            break
    return out


def _pct(value: float) -> float:
    return round(value * 100, 2)


SUBHEAD = "\x00SUB\x00"
SECTION_ORDER = ["结论", "证据链", "分歧反证", "后续验证点", "检索可观测", "输出质检", "交易含义", "引用来源"]


def render_answer(result: AskResult) -> str:
    lines: list[str] = []
    lines.append(f"# ask：{result.query}")
    if result.clarify is not None:
        lines.append("")
        lines.append("## 【澄清追问】")
        lines.extend(f"- {line}" for line in result.clarify.summary_lines())
        lines.append("")
        lines.append("（问题过于模糊，本次未检索；补充后重新提问，或用 --no-clarify 强制硬答。）")
        return "\n".join(lines) + "\n"
    meta = [
        f"盘面日期={result.trade_date or '—'}",
        f"命中主题={result.matched_theme or '—'}",
        f"模块路由={'/'.join(result.routed_modules) or '—'}",
        f"召回状态={result.status}",
    ]
    if result.wiki_rag_telemetry is not None and result.wiki_rag_telemetry.status != "pending":
        t = result.wiki_rag_telemetry
        meta.append(f"W检索={t.mode}/{t.index_kind or '?'}·命中{t.hit_count}·{t.status}")
    lines.append("> " + " | ".join(meta))
    if result.warnings:
        lines.append("> 警告：" + "；".join(result.warnings))
    if result.synthesis:
        lines.append("")
        lines.append("## 【对话式回答】"
                     + (f"（LLM·{result.llm_provider} 有机合成）" if result.llm_provider else ""))
        lines.append("")
        lines.append(result.synthesis.rstrip())
        lines.append("")
        lines.append("---")
        lines.append("*以下为确定性检索的结构化证据，供核对引用编号：*")
    for name in SECTION_ORDER:
        lines.append("")
        lines.append(f"## 【{name}】")
        for item in result.sections.get(name, []):
            if item.startswith(SUBHEAD):
                lines.append(f"\n*{item[len(SUBHEAD):]}*")
            else:
                lines.append(f"- {item}")
    if result.detail_reports:
        lines.append("")
        lines.append("## 【模块完整报告（--detail 钻取）】")
        for label, body in result.detail_reports:
            lines.append("")
            lines.append(f"<details><summary>完整报告 · {label}</summary>")
            lines.append("")
            lines.append(body.rstrip())
            lines.append("")
            lines.append("</details>")
    return "\n".join(lines) + "\n"


def render_conversation_answer(result: AskResult) -> str:
    if result.synthesis:
        return result.synthesis

    lines: list[str] = []
    if result.data_notice:
        lines.append(result.data_notice)
    if result.market_summary:
        if lines:
            lines.append("")
        lines.append(
            result.market_summary.replace(
                "## 本地 DuckDB 最新市场总览",
                "## 市场概览",
                1,
            )
        )
    if not result.market_summary:
        if lines:
            lines.append("")
        lines.append(
            "本轮检索已完成，但自然语言综合暂时不可用。"
            "数据来源、运行轨迹和结构化产物保留在“运行详情”中，请稍后重试。"
        )
    return "\n".join(lines).rstrip() + "\n"
