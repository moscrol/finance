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
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date as date_cls, timedelta
from pathlib import Path
from typing import Any

from intelligence import userspace
from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.paths import default_paths
from intelligence.services import (
    answer_model,
    ask_clarify,
    ask_planner,
    checkpoint_recall,
    closed_loop_retrieval,
    entity_anchor,
    experience_cards,
    external_market,
    forecast_preflight,
    kb_rag,
    l3_evidence,
    llm_refine,
    market_analogs,
    market_financials,
    market_midterm,
    market_moneyflow,
    market_news,
    market_timeseries,
    perspective_lab,
    research_brief,
    scenario_tree,
    user_memory,
    web_research,
)
from intelligence.services.answer_quality import (
    AnswerQualityContext,
    build_quality_context,
)
from intelligence.services.answer_orchestrator import (
    QUESTION_CONCEPT_DEFINITION,
    QUESTION_EXTERNAL_MARKET,
    QUESTION_FINANCIAL_ANALYSIS,
    QUESTION_GENERAL,
    QUESTION_MARKET_FORECAST,
    QUESTION_MARKET_REVIEW,
    QUESTION_NEWS_IMPACT,
    QUESTION_STOCK_DEEP_DIVE,
    QUESTION_THEME_ANALYSIS,
    QUESTION_VALUATION,
    QuestionPlan,
    plan_answer_question,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services import event_transmission, evidence_gap_radar, market_structure, output_review, theme_lifecycle, valuation_estimate, valuation_gap
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

REPO_ROOT = Path(__file__).resolve().parents[2]


def _data_repo_root() -> Path:
    """盘面/exports/DuckDB 等数据根目录。

    双根架构：PYTHONPATH 指向 runtime 代码快照，真实数据在
    WORKBENCH_REPO_ROOT / FINANCE_WS（private 仓）。未设置环境变量时回退代码根。
    """
    for name in ("WORKBENCH_REPO_ROOT", "FINANCE_WS", "FINANCE_ROOT"):
        value = os.environ.get(name)
        if value:
            return Path(value).expanduser().resolve()
    return REPO_ROOT


DATA_REPO_ROOT = _data_repo_root()
DEFAULT_EXPORTS_DIR = DATA_REPO_ROOT / "market_feature_store" / "exports"

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
    wiki_rag_cache_scope: str | None = None
    # 全文版：W 源索引目录覆盖（指向 .rag_index_full）。None=默认 .rag_index，行为逐字节不变。
    wiki_rag_index_dir: str | Path | None = None
    use_llm: bool = False
    # compose: 让 LLM 把多源证据有机融合成一段连贯回答（自由形态，带内联引用）；
    # 默认关，关时行为与旧版逐字节一致。开时若无 key/调用失败则降级回六段模板。
    compose: bool = False
    # 影子实验：生产 Presenter 保持不变，旁路生成 DecisionBrief + Grounded Composer，
    # 结果只写运行产物，不进入用户可见答案。默认关闭。
    shadow_grounded_composer: bool = field(
        default_factory=lambda: os.environ.get(
            "WORKBENCH_SHADOW_GROUNDED_COMPOSER",
            "0",
        )
        == "1"
    )
    shadow_grounded_timeout: int = field(
        default_factory=lambda: int(
            os.environ.get("WORKBENCH_SHADOW_GROUNDED_TIMEOUT", "90")
        )
    )
    # Daily Agent 正式 Presenter：daily_agent_grounded 契约走 Grounded Composer，
    # 通过确定性门禁 + 语义蕴含审后保留 LLM 最终措辞；
    # 门禁未通过或 LLM 不可用时降级回结构化 claim 合成路径。
    daily_agent_grounded_presenter: bool = field(
        default_factory=lambda: os.environ.get(
            "WORKBENCH_DAILY_AGENT_GROUNDED_PRESENTER",
            "1",
        )
        == "1"
    )
    # 允许只运行 compose 取数和 AnswerSpec 裁决，不额外调用 LLM 生成自由文本。
    synthesize: bool = True
    llm_model: str | None = None
    llm_timeout: int = field(
        default_factory=lambda: int(
            os.environ.get(
                "LLM_SYNTHESIS_TIMEOUT",
                os.environ.get("LLM_TIMEOUT", "60"),
            )
        )
    )
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
    # Workbench 专项 Skill answer-owner 可固定问题类型，避免再次依赖脆弱词面分类。
    question_type_override: str | None = None
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
    perspective_mode: str = perspective_lab.PERSPECTIVE_MODE_NEUTRAL
    perspective_ids: tuple[str, ...] = ()
    stream_text_delta: Callable[[str], None] | None = field(
        default=None, repr=False, compare=False
    )
    stream_cancel_check: Callable[[], bool] | None = field(
        default=None, repr=False, compare=False
    )
    deadline: ResearchDeadline | None = field(
        default=None,
        repr=False,
        compare=False,
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
    next_trade_date: str | None = None
    market_data_source: str = "unknown"
    snapshot_date: str | None = None
    data_notice: str | None = None
    market_summary: str | None = None
    sections: dict[str, list[str]] = field(default_factory=dict)
    citations: list[Citation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provider_traces: list[ProviderTrace] = field(default_factory=list)
    found_market: bool = False
    found_graph: bool = False
    found_wiki: bool = False
    # W 源检索遥测（用了哪种索引/检索方式/命中质量）；None=未启用 W 源。
    wiki_rag_telemetry: kb_rag.RetrievalTelemetry | None = None
    closed_loop_retrieval: (
        closed_loop_retrieval.ClosedLoopRetrievalResult | None
    ) = None
    routed_modules: list[str] = field(default_factory=list)
    llm_refined: bool = False
    llm_provider: str | None = None
    # 有机合成（--compose）的自由形态回答正文；None 表示未启用/已降级为模板
    synthesis: str | None = None
    # 首轮合成的完整对话 messages（system+user+assistant）；供多轮追问复用证据+历史。
    # None 表示未启用/已降级（无法进入多轮对话）。
    synthesis_messages: list[dict] | None = None
    prepared_synthesis_messages: list[dict] | None = field(
        default=None,
        repr=False,
    )
    prepared_synthesis_is_market_review: bool = field(
        default=False,
        repr=False,
    )
    llm_fallback_reason: str | None = None
    llm_stream_telemetry: dict[str, object] = field(default_factory=dict)
    grounded_composer_shadow: (
        answer_model.GroundedComposerShadow | None
    ) = None
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
    # 裁决层唯一输出：表达层和 LLM 只能消费该结构，不能直接拼接检索字符串。
    answer_spec: answer_model.AnswerSpec | None = None
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


@dataclass(frozen=True)
class PreparedAnswer:
    options: AskOptions
    result: AskResult


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


def _company_exposure_tier(row: dict[str, Any]) -> str:
    strength = str(row.get("strength") or "").lower()
    confidence = str(row.get("confidence") or "").lower()
    evidence_layer = str(row.get("evidence_layer") or "").lower()
    direct_company_evidence = (
        evidence_layer in {"l3", "l2_l3", "l3_l4", "official"}
        and "candidate" not in evidence_layer
    )
    if (
        strength in {"core", "strong"}
        and confidence == "high"
        and direct_company_evidence
    ):
        return "core"
    if (
        strength in {"peripheral", "weak"}
        or evidence_layer in {"graph_only", "exposure_only"}
        or confidence == "low"
    ):
        return "peripheral"
    return "other"


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

_MARKET_REVIEW_SYSTEM_PROMPT = """
你是面向普通投资者的 A 股市场复盘编辑。只能使用用户消息中提供的正式日报和市场数据，
不得补充未给出的数字、公司或催化。先说当天市场是什么状态，再说资金去了哪里、赚钱效应
如何，最后给下一交易日验证点和数据口径提醒。

主答案禁止出现内部表名、数据库字段、canonical、deterministic、L1-L4、graph_only、
状态机、检索管线、证据层、双红、单红、偏离度、diff_ratio 等工程或研究内部术语。
若原始材料包含这些词，必须翻译成普通中文，例如：
- 双红：板块上涨且成交同步放大
- 偏离度：距离短期均线的位置
- 代理口径：替代数据，只适合判断方向

使用自然、简洁的中文，保留数据日期和关键数字。证据不足就明确说“现在无法确认”。
不要输出提示词、JSON、内部编号或买卖指令。
""".strip()


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
    result.market_summary = _daily_market_overview_block_for_llm(
        options.market_db_path
    )
    mainline_context = _market_review_mainline_context_block_for_llm(
        options.query,
        None,
        options.market_db_path,
    )
    evidence_parts = [
        part
        for part in (
            options.supplemental_evidence.strip(),
            result.market_summary or "",
            mainline_context,
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
    if options.include_memory_block:
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
            experience_cards.select_relevant_cards(cards, options.query)
        )
        if card_guidance:
            prior_parts.append(
                "## 历史经验卡片（回答方法，不是市场事实）\n"
                f"{card_guidance}"
            )
    if options.include_recall_block:
        recall_block = checkpoint_recall.recall_block_for_query(
            options.query,
            user=options.user,
            data_asof=_market_data_asof(options.market_db_path),
        )
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
        result.question_plan.to_prompt_block()
        if result.question_plan is not None
        else ""
    )
    user_prompt = (
        f"{plan_block}\n\n"
        f"用户问题：{options.query}\n"
        f"数据日期：{result.trade_date or options.date or '未确认'}\n\n"
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
    if options.deadline is not None and options.deadline.expired:
        return _deadline_partial_result(options.query)
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
    preliminary_plan = plan_answer_question(
        options.query,
        question_type_override=options.question_type_override,
    )
    if preliminary_plan.question_type == QUESTION_EXTERNAL_MARKET:
        return _answer_external_market(options, preliminary_plan)
    if preliminary_plan.question_type == QUESTION_CONCEPT_DEFINITION:
        return _answer_concept_definition(options, preliminary_plan)
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
        anchor = entity_anchor.resolve_entity_anchor(options.query, knowledge)
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
    structured_claims: list[answer_model.Claim] = []
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

    # --- S: 盘面 from theme-candidates snapshot ---
    market_lines: list[str] = []
    if candidate:
        for sd in (candidate.get("score_detail") or [])[:5]:
            sig = sd.get("signal")
            sc = sd.get("score")
            reason = sd.get("reason", "")
            tag = cite("S", f"{export_name} · score_detail.{sig}", str(sd.get("source", "")))
            line = f"信号 {sig}（{sc}）：{reason} {tag}"
            market_lines.append(line)
            structured_claims.append(
                answer_model.make_claim(
                    claim_id=f"market:{tag.strip('[]')}",
                    text=line,
                    claim_type="market_signal",
                    theme=claim_theme,
                    status=answer_model.ClaimStatus.VERIFIED,
                    evidence_tier="L4",
                )
            )
        ctx = doc.get("market_context") or {}
        if ctx:
            caps = "、".join(
                f"{s.get('name')}（占比 {s.get('ratio')}%）"
                for s in (ctx.get("capacity_sectors") or [])[:3]
            )
            tag = cite("S", f"{export_name} · market_context")
            line = (
                f"市场环境：{ctx.get('market_stage')}，成交 {ctx.get('total_amount')} 亿，"
                f"涨停 {ctx.get('limit_up')} / 跌停 {ctx.get('limit_down')}，容量前三 {caps} {tag}"
            )
            market_lines.append(line)
            structured_claims.append(
                answer_model.make_claim(
                    claim_id=f"market:{tag.strip('[]')}",
                    text=line,
                    claim_type="market_context",
                    theme=claim_theme,
                    status=answer_model.ClaimStatus.VERIFIED,
                    evidence_tier="L4",
                )
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
        line = f"命中概念：{names} {tag}"
        graph_concept_lines.append(line)
        structured_claims.append(
            answer_model.make_claim(
                claim_id=f"concept:{tag.strip('[]')}",
                text=line,
                claim_type="theme_mapping",
                theme=claim_theme,
                status=answer_model.ClaimStatus.CANDIDATE,
                evidence_tier="concept_graph",
            )
        )

    company_lines: list[str] = []
    focus_entities = (
        question_plan.research_spec.focus_entities
        if question_plan.research_spec is not None
        else ()
    )
    exposure_limit = max(options.top_companies, len(focus_entities) * 4)
    exposures = knowledge.get_exposure_matches(graph_query, limit=exposure_limit)
    if exposures.get("found") and focus_entities:
        focus_order = {
            company: index for index, company in enumerate(focus_entities)
        }
        exposure_items = list(exposures["items"])
        exposure_items.sort(
            key=lambda row: (
                0 if str(row.get("company") or "") in focus_order else 1,
                focus_order.get(str(row.get("company") or ""), len(focus_order)),
            )
        )
        exposures["items"] = exposure_items[: options.top_companies]
    tiers: dict[str, list[str]] = {"core": [], "peripheral": [], "other": []}
    company_evidence_concepts: dict[str, str] = {}
    if exposures.get("found"):
        result.found_graph = True
        for row in exposures["items"]:
            conf = str(row.get("confidence") or "").lower()
            layer = str(row.get("evidence_layer") or "")
            company = str(row.get("company") or "").strip()
            concept = str(row.get("concept") or "").strip()
            if company and concept:
                company_evidence_concepts[company] = concept
            exposure_tier = _company_exposure_tier(row)
            label = f"{company}({row.get('ticker')}|{row.get('role') or '—'}|{conf or '?'}/{layer or '?'})"
            tiers[exposure_tier].append(label)
            requested_tier = {
                "core": answer_model.CompanyTier.CORE,
                "peripheral": answer_model.CompanyTier.PERIPHERAL,
            }.get(exposure_tier, answer_model.CompanyTier.CANDIDATE)
            company_candidates.append(
                answer_model.CompanyCandidate(
                    company=company,
                    ticker=str(row.get("ticker") or ""),
                    chain_stage=str(row.get("chain_stage") or row.get("role") or "待确认"),
                    directness=str(row.get("strength") or "待确认"),
                    requested_tier=requested_tier,
                    evidence_layer=layer,
                )
            )
        tag = cite("G", "knowledge-base · wiki/relations/entity_exposures.json")
        for candidate_company in company_candidates:
            is_direct = candidate_company.requested_tier == answer_model.CompanyTier.CORE
            structured_claims.append(
                answer_model.make_claim(
                    claim_id=f"company:{candidate_company.company}:{tag.strip('[]')}",
                    text=(
                        f"{candidate_company.company}与"
                        f"{company_evidence_concepts.get(candidate_company.company, '该题材')}"
                        "存在公司级映射。"
                    ),
                    claim_type="company_mapping",
                    theme=claim_theme,
                    status=(
                        answer_model.ClaimStatus.VERIFIED
                        if is_direct
                        else answer_model.ClaimStatus.CANDIDATE
                    ),
                    evidence_tier=candidate_company.evidence_layer,
                    company=candidate_company.company,
                    evidence_ids=(tag.strip("[]"),),
                )
            )
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
    targets.extend(company_evidence_concepts)
    for target in dict.fromkeys(t for t in targets if t):
        ev = knowledge.get_evidence(
            target,
            concept=company_evidence_concepts.get(target),
            limit=options.max_evidence,
        )
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
            layer_name = research_brief.classify_evidence_line(line, "R")
            target_name = str(item.get("target") or "").strip()
            structured_claims.append(
                answer_model.make_claim(
                    claim_id=f"evidence:{tag.strip('[]')}",
                    text=line,
                    claim_type="company_evidence" if target_name in company_evidence_concepts else "theme_evidence",
                    theme=claim_theme,
                    status=(
                        answer_model.ClaimStatus.VERIFIED
                        if layer_name == "L3" and not stale
                        else answer_model.ClaimStatus.CANDIDATE
                    ),
                    evidence_tier=layer_name,
                    company=target_name if target_name in company_evidence_concepts else None,
                    confidence=_confidence_score(item.get("confidence")),
                    freshness="stale" if stale else "current",
                )
            )
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
        line = (
            f"{ke.get('target')}：{src}（质量 {ke.get('quality') or '?'}，盘面候选携带） {tag}"
        )
        evidence_lines.append(line)
        target_name = str(ke.get("target") or "").strip()
        structured_claims.append(
            answer_model.make_claim(
                claim_id=f"candidate-evidence:{tag.strip('[]')}",
                text=line,
                claim_type="company_evidence" if target_name in company_evidence_concepts else "theme_evidence",
                theme=claim_theme,
                status=answer_model.ClaimStatus.CANDIDATE,
                evidence_tier="candidate_snapshot",
                company=target_name if target_name in company_evidence_concepts else None,
            )
        )

    # --- W: 知识库 hybrid 向量召回（语义选页 → 读候选页正文作证据，打通复盘↔知识库闭环）---
    wiki_lines: list[str] = []
    wiki_counter_lines: list[str] = []
    wiki_llm_line_pairs: list[tuple[str, str]] = []
    wiki_stats: dict[str, Any] = {
        "attempted": bool(options.use_wiki_rag),
        "mode": options.wiki_rag_mode,
        "index": "full" if options.wiki_rag_index_dir else "structured",
    }
    if options.use_wiki_rag:
        loop = closed_loop_retrieval.retrieve_closed_loop(
            graph_query,
            anchor=anchor,
            retrieve=lambda retrieval_query: kb_rag.retrieve(
                retrieval_query,
                resolved_kb_wiki,
                k=options.wiki_rag_k,
                mode=options.wiki_rag_mode,
                timeout=_stage_timeout(options, options.wiki_rag_timeout),
                excerpt_chars=options.wiki_rag_excerpt,
                budget_query=graph_query,
                index_dir=options.wiki_rag_index_dir,
                require_fresh=True,
                cache_scope=options.wiki_rag_cache_scope,
            ),
        )
        _, wiki_evidence_total_chars = kb_rag.evidence_budget_for_query(
            options.query,
            mode=options.wiki_rag_mode,
            index_kind=loop.telemetry.index_kind if loop.telemetry else "",
        )
        conclusion_hits = [item.hit for item in loop.conclusion]
        counter_hits = [item.hit for item in loop.counter_clues]
        if counter_hits:
            conclusion_budget = int(wiki_evidence_total_chars * 0.75)
            kb_rag.apply_total_llm_budget(conclusion_hits, conclusion_budget)
            kb_rag.apply_total_llm_budget(
                counter_hits,
                wiki_evidence_total_chars - conclusion_budget,
            )
        else:
            kb_rag.apply_total_llm_budget(
                conclusion_hits,
                wiki_evidence_total_chars,
            )
        result.closed_loop_retrieval = loop
        wiki_stats.update(
            {
                "ok": bool(loop.conclusion),
                "hits": len(loop.conclusion),
                "clues": len(loop.clues),
                "discarded": len(loop.discarded),
                "counter_clues": len(loop.counter_clues),
                "scores": [item.hit.score for item in loop.conclusion],
                "neighbor_hits": sum(
                    1 for item in loop.conclusion if item.hit.via_neighbor
                ),
                "pages": [item.hit.file_path for item in loop.conclusion],
                "warning": "；".join(loop.warnings),
                "attempts": loop.inspector_dict()["attempts"],
            }
        )
        result.wiki_rag_telemetry = loop.telemetry
        if loop.conclusion:
            result.found_wiki = True
            result.found_graph = True
            for bucketed in loop.conclusion:
                h = bucketed.hit
                nb = "·邻居扩展" if h.via_neighbor else ""
                section_ref = f"｜section={h.section}" if h.section else ""
                tag = cite(
                    "W",
                    f"knowledge-base · {h.file_path}",
                    (
                        f"closed-loop:{bucketed.aperture}｜{h.title}"
                        f"｜chunk={h.best_chunk_id}{section_ref}"
                        f"｜evidence_chunks={','.join(h.evidence_chunk_ids or (h.best_chunk_id,))}"
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
                line = (
                    f"{baseline}{h.title}（相关度 {round(h.score, 4)}{nb}）：{h.excerpt} {tag}"
                )
                llm_body = h.llm_evidence or h.excerpt
                llm_line = (
                    f"{baseline}{h.title}（相关度 {round(h.score, 4)}{nb}）：{llm_body} {tag}"
                )
                wiki_lines.append(line)
                wiki_llm_line_pairs.append((line, llm_line))
                matched_company = next(
                    (
                        company
                        for company in company_evidence_concepts
                        if company in line
                    ),
                    None,
                )
                structured_claims.append(
                    answer_model.make_claim(
                        claim_id=f"wiki:{tag.strip('[]')}",
                        text=line,
                        claim_type="company_evidence" if matched_company else "theme_evidence",
                        theme=claim_theme,
                        status=answer_model.ClaimStatus.CANDIDATE,
                        evidence_tier="wiki_candidate",
                        company=matched_company,
                        confidence=h.score,
                        freshness=h.index_freshness,
                    )
                )
        if loop.counter_clues:
            result.found_wiki = True
            for bucketed in loop.counter_clues:
                h = bucketed.hit
                section_ref = f"｜section={h.section}" if h.section else ""
                tag = cite(
                    "W",
                    f"knowledge-base · {h.file_path}",
                    (
                        f"closed-loop:counter｜{h.title}"
                        f"｜chunk={h.best_chunk_id}{section_ref}"
                        f"｜evidence_chunks={','.join(h.evidence_chunk_ids or (h.best_chunk_id,))}"
                        f"｜hash={h.content_hash[:12]}｜index={h.index_source_revision[:12]}"
                        f"｜freshness={h.index_freshness}"
                    ),
                    chunk_id=h.best_chunk_id,
                    content_hash=h.content_hash,
                    index_source_revision=h.index_source_revision,
                    index_freshness=h.index_freshness,
                )
                line = f"反方线索（待进一步核验）：{h.title}：{h.excerpt} {tag}"
                llm_line = (
                    f"反方线索（待进一步核验）：{h.title}：{h.llm_evidence or h.excerpt} {tag}"
                )
                wiki_counter_lines.append(line)
                wiki_llm_line_pairs.append((line, llm_line))
        result.warnings.extend(f"wiki-rag：{warning}" for warning in loop.warnings)

    # --- E: 外部 Web 检索（仅 general lane，且本地盘面/图谱/证据/wiki 全空时触发）---
    web_fallback_lines: list[str] = []
    web_fallback_attempted = False
    if (
        question_plan.question_type == QUESTION_GENERAL
        and not market_lines
        and not graph_concept_lines
        and not company_lines
        and not evidence_lines
        and not wiki_lines
        and not wiki_counter_lines
    ):
        web_fallback_attempted = True
        web_result = web_research.fetch_web_search(options.query)
        result.provider_traces.append(web_result.trace)
        for item in web_result.items[:4]:
            tag = cite("E", item.title, item.url)
            web_fallback_lines.append(
                f"{item.title}：{item.snippet or '搜索结果未提供摘要'}（外部快照，仅作背景线索） {tag}"
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
            mr = run_module(
                name,
                graph_query,
                resolved_kb_wiki,
                _stage_timeout(options, options.module_timeout),
            )
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
    if tiers["other"]:
        gap_lines.append(
            f"{len(tiers['other'])} 家公司仅有间接或候选证据，未达到公司级硬证据门槛，不得升级为核心受益。"
        )
    gap_lines.extend(framing.get("gaps", []))
    gap_lines.extend(stale_notes)
    gap_lines.extend(wiki_counter_lines)
    if web_fallback_attempted and not web_fallback_lines:
        gap_lines.append(
            "本地盘面/图谱/知识库均未命中，外部 Web Search 也未返回可用来源；"
            "未用无关资料替代。"
        )
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
    theme = (
        question_plan.research_spec.theme
        if question_plan.research_spec is not None
        else _quoted_topic(options.query)
        or question_plan.query_envelope.subject
        or result.matched_theme
        or options.query
    )
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
        "结论与交易含义由结构化规则生成；证据不足处已标为待验证。",
        _conclusion_ttl_line(result.trade_date),
    ]
    conclusion = [*framing.get("conclusion", []), *conclusion]

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
    follow_ups = [*framing.get("follow_ups", []), *follow_ups]
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
        + (
            [f"{SUBHEAD}外部 Web 兜底(低层级背景线索)"] + web_fallback_lines
            if web_fallback_lines
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
    if options.use_l3_lookup:
        local_evidence_text = _evidence_text_for_llm(
            _evidence_chain_with_llm_wiki(evidence_chain, wiki_llm_line_pairs),
            gap_lines,
        )
        l3_bundle = l3_evidence.lookup_l3_evidence(
            options.query,
            question_plan,
            local_evidence_text,
            config=l3_evidence.L3LookupConfig.from_env(
                enabled=True,
                timeout=_stage_timeout(options, options.l3_lookup_timeout),
                limit=options.l3_lookup_limit,
            ),
        )
        result.l3_evidence = l3_bundle
        result.warnings.extend(f"l3-evidence：{w}" for w in l3_bundle.warnings)
        l3_lines = l3_bundle.to_prompt_block().splitlines()
        evidence_chain.extend([f"{SUBHEAD}L3 官方证据工具补查", *l3_lines])
        for index, item in enumerate(l3_bundle.items, start=1):
            company = next(
                (
                    name
                    for name in company_evidence_concepts
                    if name in f"{item.title} {item.summary}"
                ),
                anchor.entity if anchor is not None else None,
            )
            if company is None and question_plan.question_type == QUESTION_STOCK_DEEP_DIVE:
                company = _company_name_from_official_title(item.title)
            if company and not any(
                candidate.company == company for candidate in company_candidates
            ):
                company_candidates.append(
                    answer_model.CompanyCandidate(
                        company=company,
                        directness="研究对象",
                        requested_tier=answer_model.CompanyTier.CANDIDATE,
                    )
                )
            structured_claims.append(
                answer_model.make_claim(
                    claim_id=f"official:L{index}",
                    text=f"{item.title}：{item.summary}",
                    claim_type="company_evidence" if company else "theme_evidence",
                    theme=claim_theme,
                    status=answer_model.ClaimStatus.VERIFIED,
                    evidence_tier="L3",
                    company=company,
                    evidence_ids=(f"L{index}",),
                )
            )

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
        evidence_text = _evidence_text_for_llm(
            _evidence_chain_with_llm_wiki(evidence_chain, wiki_llm_line_pairs),
            gap_lines,
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
        if options.include_financials_block and (
            market_financials.parse_financials_intent(options.query)
            or (
                question_plan.base_finance_mode is not None
                and question_plan.base_finance_mode.require_financials
            )
        ):
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

            block_tasks.append(ask_planner.BlockTask("D7", "逐季财报", _build_d7))
        if options.include_news_block and (
            market_news.parse_news_intent(options.query)
            or (
                question_plan.base_finance_mode is not None
                and question_plan.base_finance_mode.require_news
            )
        ):
            def _build_w7():
                news_keyword = market_news.resolve_news_keyword(options.query, theme, anchored_name)
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
                block = (
                    _market_review_mainline_context_block_for_llm(
                        options.query,
                        theme,
                        options.market_db_path,
                    )
                    if is_market_review
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

        outcomes = ask_planner.run_block_tasks(
            block_tasks,
            parallel=options.parallel_blocks,
            deadline=options.deadline,
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
        if options.include_second_derivative_block and not is_market_review:
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
    result.warnings.extend(
        f"AnswerSpec 质检：{issue.message}"
        for issue in result.answer_spec.quality.issues
    )

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
            timeout=_stage_timeout(options, options.llm_timeout),
            deadline=_llm_deadline(options),
            temperature=0.2,
        )
        if revised is not None:
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
            else:
                presented_revision = answer_model.present_llm_answer(
                    proposed_revision,
                    result.answer_spec,
                )
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
        "数据源状态": [
            (
                f"{trace.provider}｜{trace.capability}｜{trace.status}"
                f"｜source_trade_date={trace.source_trade_date or '未记录'}"
                f"｜result_count={trace.result_count}"
                + (f"｜{trace.detail}" if trace.detail else "")
            )
            for trace in result.provider_traces
        ],
        "引用来源": [f"[{c.tag}] {c.source}" + (f" — {c.detail}" if c.detail else "") for c in citations],
    }
    result.citations = citations
    return result


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


def _stage_timeout(options: AskOptions, configured_limit: float) -> float:
    if options.deadline is None:
        return max(0.001, float(configured_limit))
    return max(0.001, options.deadline.stage_timeout(configured_limit))


def _llm_deadline(options: AskOptions) -> llm_refine.Deadline:
    if options.deadline is not None:
        return llm_refine.Deadline(options.deadline.expires_at)
    return llm_refine.Deadline.from_timeout(options.llm_timeout)


def _claims_from_data_block(
    block: str,
    tag: str,
    label: str,
    theme: str,
) -> list[answer_model.Claim]:
    claims: list[answer_model.Claim] = []
    for index, raw in enumerate(block.splitlines(), start=1):
        line = raw.strip().lstrip("-").strip()
        if not line or line.startswith("口径"):
            continue
        if line.startswith("#"):
            status = answer_model.ClaimStatus.INFERRED
        elif any(
            term in line
            for term in (
                "缺失",
                "未取得",
                "未取到",
                "不可用",
                "无匹配",
                "未识别",
            )
        ):
            status = answer_model.ClaimStatus.MISSING
        elif tag in {"D2", "D3"} or any(
            term in line
            for term in ("必须", "需要补", "使用要求", "回答时", "继续查")
        ):
            status = answer_model.ClaimStatus.INFERRED
        else:
            status = answer_model.ClaimStatus.VERIFIED
        claims.append(
            answer_model.make_claim(
                claim_id=f"data:{tag}:{index}",
                text=f"{label}：{line}",
                claim_type="market_data",
                theme=theme,
                status=status,
                evidence_tier="market_data",
                evidence_ids=(tag,),
            )
        )
    return claims


def _company_name_from_official_title(title: str) -> str | None:
    candidate = re.split(
        r"(?:公告|问询函|回复|互动易|投资者关系|调研纪要)",
        str(title or "").strip(),
        maxsplit=1,
    )[0].strip(" ：:（）()")
    if re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9]{2,20}", candidate):
        return candidate
    return None


def _build_answer_spec_for_result(
    *,
    result: AskResult,
    research_spec: answer_model.ThemeResearchSpec,
    conclusion_lines: list[str],
    structured_claims: list[answer_model.Claim],
    company_candidates: list[answer_model.CompanyCandidate],
    counter_lines: list[str],
    gap_lines: list[str],
    trigger_lines: list[str],
    follow_ups: list[str],
    citations: list[Citation],
) -> answer_model.AnswerSpec:
    claims = _dedupe_structured_claims(structured_claims)
    company_table = answer_model.build_company_assessments(
        company_candidates,
        claims,
    )
    market_claims = [
        claim
        for claim in claims
        if claim.claim_type in {"market_signal", "market_context"}
        and claim.status == answer_model.ClaimStatus.VERIFIED
    ]
    signal_labels: list[str] = []
    for claim in market_claims:
        rendered = answer_model.humanize(claim.text)
        if claim.claim_type != "market_signal":
            continue
        label = rendered.split("：", 1)[0].strip()
        if label and label not in signal_labels:
            signal_labels.append(label)
    question_type = (
        result.question_plan.question_type
        if result.question_plan is not None
        else ""
    )
    is_theme_research = question_type in {
        QUESTION_THEME_ANALYSIS,
        QUESTION_NEWS_IMPACT,
        QUESTION_STOCK_DEEP_DIVE,
    }
    if is_theme_research:
        summary: list[answer_model.Claim] = [
            answer_model.make_claim(
                claim_id="summary:definition",
                text=(
                    f"{research_spec.theme}的研究范围是："
                    f"{research_spec.definition.rstrip('。')}。"
                ),
                claim_type="summary",
                theme=research_spec.theme,
                status=answer_model.ClaimStatus.INFERRED,
                evidence_tier="research_ontology",
                evidence_ids=("ONTOLOGY",),
            )
        ]
    elif question_type == QUESTION_VALUATION:
        subject = (
            result.question_plan.query_envelope.subject
            if result.question_plan is not None
            else None
        )
        summary = [
            answer_model.make_claim(
                claim_id="summary:valuation-gap",
                text=(
                    f"{subject or result.query}本轮尚未取得足够的当前估值、财务和"
                    "可比公司数据，不能可靠判断估值高低。"
                ),
                claim_type="summary",
                theme=subject or research_spec.theme,
                status=answer_model.ClaimStatus.MISSING,
            )
        ]
    else:
        summary = [
            answer_model.make_claim(
                claim_id=f"summary:base:{index}",
                text=line,
                claim_type="summary",
                theme=research_spec.theme,
                status=answer_model.ClaimStatus.INFERRED,
                evidence_tier="base_finance",
            )
            for index, line in enumerate(dict.fromkeys(conclusion_lines[:3]), start=1)
            if line
        ]
    if is_theme_research and signal_labels:
        market_evidence_ids = tuple(
            dict.fromkeys(
                evidence_id
                for claim in market_claims
                for evidence_id in claim.evidence_ids
            )
        )
        summary.append(
            answer_model.make_claim(
                claim_id="summary:market",
                text=(
                    f"盘面上已经出现{'、'.join(signal_labels[:3])}，"
                    "说明市场关注度有所升温；但这些信号只能反映资金行为，"
                    "不能替代公司公告、客户、订单或收入证据。"
                ),
                claim_type="summary",
                theme=research_spec.theme,
                status=answer_model.ClaimStatus.CANDIDATE,
                evidence_tier="market_data",
                evidence_ids=market_evidence_ids,
            )
        )
    elif is_theme_research:
        summary.append(
            answer_model.make_claim(
                claim_id="summary:market-gap",
                text=(
                    "盘面数据本轮不足，暂时无法判断资金是否已经形成持续共识。"
                ),
                claim_type="summary",
                theme=research_spec.theme,
                status=answer_model.ClaimStatus.MISSING,
            )
        )
    verified_company_claims = [
        claim
        for claim in claims
        if claim.company and claim.status == answer_model.ClaimStatus.VERIFIED
    ]
    if is_theme_research and verified_company_claims:
        verified_companies = list(
            dict.fromkeys(
                claim.company for claim in verified_company_claims if claim.company
            )
        )
        summary.append(
            answer_model.make_claim(
                claim_id="summary:company",
                text=(
                    f"公司层面已找到可回查的公开材料，覆盖"
                    f"{'、'.join(verified_companies[:3])}；是否属于核心受益者，"
                    "仍需结合业务直接性和收入贡献判断。"
                ),
                claim_type="summary",
                theme=research_spec.theme,
                status=answer_model.ClaimStatus.VERIFIED,
                evidence_tier="company_evidence",
                evidence_ids=tuple(
                    dict.fromkeys(
                        evidence_id
                        for claim in verified_company_claims
                        for evidence_id in claim.evidence_ids
                    )
                ),
            )
        )
    elif is_theme_research:
        summary.append(
            answer_model.make_claim(
                claim_id="summary:company-gap",
                text=(
                    "公司层面尚未形成可回查的公告、年报、官网产品或客户订单证据，"
                    "因此不能把任何公司列为核心受益者。"
                ),
                claim_type="summary",
                theme=research_spec.theme,
                status=answer_model.ClaimStatus.MISSING,
            )
        )
    user_gaps = [
        line
        for line in gap_lines
        if line
        and not line.startswith(
            (
                "阶段判断",
                "市场结构推演路径",
                "反方审稿",
                "市场结构状态机",
                "证据分层审计",
            )
        )
        and "Temporal Facts" not in line
    ]
    gaps = tuple(
        answer_model.make_claim(
            claim_id=f"gap:{index}",
            text=line,
            claim_type="evidence_gap",
            theme=research_spec.theme,
            status=answer_model.ClaimStatus.MISSING,
        )
        for index, line in enumerate(dict.fromkeys(user_gaps), start=1)
    )
    counter_evidence = tuple(
        answer_model.make_claim(
            claim_id=f"counter:{index}",
            text=line,
            claim_type="counter_evidence",
            theme=research_spec.theme,
            status=answer_model.ClaimStatus.CONFLICT,
        )
        for index, line in enumerate(dict.fromkeys(counter_lines), start=1)
    )
    triggers: list[answer_model.Claim] = []
    for index, line in enumerate(dict.fromkeys(trigger_lines), start=1):
        matching_claim = next(
            (claim for claim in claims if answer_model.humanize(claim.text) == answer_model.humanize(line)),
            None,
        )
        triggers.append(
            answer_model.make_claim(
                claim_id=f"trigger:{index}",
                text=line,
                claim_type="trigger",
                theme=research_spec.theme,
                status=(
                    matching_claim.status
                    if matching_claim is not None
                    else answer_model.ClaimStatus.INFERRED
                ),
                evidence_tier=(
                    matching_claim.evidence_tier
                    if matching_claim is not None
                    else "research_ontology"
                ),
                evidence_ids=(
                    matching_claim.evidence_ids
                    if matching_claim is not None
                    else ("ONTOLOGY",)
                ),
            )
        )
    evidence_tiers: dict[str, str] = {}
    for claim in claims:
        for evidence_id in claim.evidence_ids:
            current = evidence_tiers.get(evidence_id, "")
            if not current or answer_model.is_hard_evidence_tier(
                claim.evidence_tier,
                (evidence_id,),
            ):
                evidence_tiers[evidence_id] = claim.evidence_tier
    sources = [
        answer_model.EvidenceRef(
            evidence_id=citation.tag,
            source=citation.source,
            detail=citation.detail,
            tier=evidence_tiers.get(citation.tag, ""),
        )
        for citation in citations
    ]
    if is_theme_research:
        sources.append(
            answer_model.EvidenceRef(
                evidence_id="ONTOLOGY",
                source=f"题材研究配置 · {research_spec.theme}",
                detail="仅用于定义、产业链和核验协议，不作为公司级事实。",
                tier="research_ontology",
            )
        )
    for index, item in enumerate(result.l3_evidence.items, start=1):
        sources.append(
            answer_model.EvidenceRef(
                evidence_id=f"L{index}",
                source=item.citation or item.source_type,
                detail=item.title,
                tier="L3",
            )
        )
    notices: list[str] = []
    if result.data_notice:
        notices.append(result.data_notice)
    if re.search(r"T\+1|下一交易日|明天", result.query, re.IGNORECASE):
        notices.append(
            f"下一交易日为 {result.next_trade_date}（按交易日历确认，不按自然日顺延）。"
            if result.next_trade_date
            else "下一交易日（日期待交易日历确认），不得按自然日猜测。"
        )
    requires_company_evidence = (
        result.question_plan is not None
        and result.question_plan.question_type
        in {
            QUESTION_THEME_ANALYSIS,
            QUESTION_NEWS_IMPACT,
            QUESTION_STOCK_DEEP_DIVE,
            QUESTION_FINANCIAL_ANALYSIS,
            QUESTION_VALUATION,
        }
    )
    has_verified_company_claim = any(
        claim.company and claim.status == answer_model.ClaimStatus.VERIFIED
        for claim in claims
    )
    if requires_company_evidence and not has_verified_company_claim:
        notices.append("本轮未形成可验证的公司级来源；公司判断均按待验证展示。")
    if any(
        term in warning.lower()
        for warning in result.warnings
        for term in ("失败", "不可用", "timeout", "degraded")
    ):
        notices.append("部分资料源本轮不可用，未用于结论。")
    actions = list(research_spec.verification_actions) if is_theme_research else []
    actions.extend(
        line for line in conclusion_lines if line.startswith("观点有效期")
    )
    actions.extend(
        line
        for line in follow_ups
        if line
        and "市场结构推演路径" not in line
        and not re.match(r"^\[[^\]]+\]", line)
    )
    spec = answer_model.AnswerSpec(
        research_spec=research_spec,
        summary=tuple(summary),
        verified_facts=tuple(
            claim for claim in claims if claim.status == answer_model.ClaimStatus.VERIFIED
        ),
        company_table=company_table,
        counter_evidence=counter_evidence,
        gaps=gaps,
        triggers=tuple(triggers),
        next_actions=tuple(dict.fromkeys(actions)),
        sources=tuple(dict.fromkeys(sources)),
        system_notices=tuple(dict.fromkeys(notices)),
        prompt_constraints=tuple(
            item
            for item in (
                result.question_plan.to_prompt_block()
                if result.question_plan is not None
                else "",
                (
                    "## 交易日历约束\n"
                    f"- 数据交易日：{result.trade_date or '未确认'}\n"
                    f"- 下一交易日：{result.next_trade_date or '日期待交易日历确认'}"
                ),
                (
                    forecast_preflight.render_preflight_prompt(
                        result.forecast_preflight
                    )
                    if result.forecast_preflight is not None
                    else ""
                ),
                (
                    result.l3_evidence.to_prompt_block()
                    if result.l3_evidence is not None
                    and (
                        result.l3_evidence.items
                        or result.l3_evidence.gaps
                        or result.l3_evidence.warnings
                    )
                    else ""
                ),
            )
            if item
        ),
        presentation_kind=(
            "theme_research"
            if result.question_plan is not None
            and result.question_plan.question_type
            in {
                QUESTION_THEME_ANALYSIS,
                QUESTION_NEWS_IMPACT,
                QUESTION_STOCK_DEEP_DIVE,
            }
            else "base_finance"
        ),
        presentation_title=(
            {
                QUESTION_MARKET_FORECAST: "市场判断",
                QUESTION_VALUATION: "估值判断",
            }.get(
                result.question_plan.question_type,
                "金融问题裁决",
            )
            if result.question_plan is not None
            else "金融问题裁决"
        ),
    )
    return answer_model.finalize_answer_spec(spec)


def _presentable_lines(*blocks: str) -> list[str]:
    lines: list[str] = []
    for block in blocks:
        for raw in str(block or "").splitlines():
            line = raw.strip().lstrip("-").strip()
            if (
                not line
                or line.startswith("#")
                or line.startswith("|")
                or set(line) <= {"-", "|", ":", " "}
            ):
                continue
            lines.append(line)
    return list(dict.fromkeys(lines))


def _build_base_answer_spec_from_sections(
    result: AskResult,
    *,
    theme: str,
    evidence_blocks: tuple[str, ...] = (),
    direct_lines: tuple[str, ...] = (),
    risk_lines: tuple[str, ...] = (),
    action_lines: tuple[str, ...] = (),
) -> answer_model.AnswerSpec:
    citations = [
        citation for citation in result.citations if citation.tag not in {"M", "V"}
    ]
    sources = [
        answer_model.EvidenceRef(
            evidence_id=citation.tag,
            source=citation.source,
            detail=citation.detail,
        )
        for citation in citations
    ]
    evidence_ids = tuple(dict.fromkeys(citation.tag for citation in citations))
    if evidence_blocks:
        sources.append(
            answer_model.EvidenceRef(
                evidence_id="BASE",
                source="本轮可核验资料",
                detail="用于统一答案裁决与展示。",
            )
        )
        evidence_ids = (*evidence_ids, "BASE")

    conclusions = list(direct_lines) or _presentable_lines(
        "\n".join(result.sections.get("结论", []))
    )
    if not conclusions:
        conclusions = ["当前证据不足，暂时不能形成可靠定性。"]
    summary_status = (
        answer_model.ClaimStatus.INFERRED
        if evidence_ids
        else answer_model.ClaimStatus.MISSING
    )
    summary = tuple(
        answer_model.make_claim(
            claim_id=f"base:summary:{index}",
            text=line,
            claim_type="summary",
            theme=theme,
            status=summary_status,
            evidence_tier="base_finance",
            evidence_ids=evidence_ids,
        )
        for index, line in enumerate(conclusions[:3], start=1)
    )

    evidence_lines = _presentable_lines(
        "\n".join(result.sections.get("证据链", [])),
        *evidence_blocks,
    )
    verified_facts = tuple(
        answer_model.make_claim(
            claim_id=f"base:fact:{index}",
            text=line,
            claim_type="supporting_fact",
            theme=theme,
            status=answer_model.ClaimStatus.VERIFIED,
            evidence_tier="base_finance",
            evidence_ids=evidence_ids,
        )
        for index, line in enumerate(evidence_lines[:8], start=1)
        if evidence_ids
    )

    risks = list(risk_lines) or _presentable_lines(
        "\n".join(result.sections.get("分歧反证", []))
    )
    if not risks:
        risks = ["缺少足以独立复核结论的反方资料。"]
    gaps = tuple(
        answer_model.make_claim(
            claim_id=f"base:gap:{index}",
            text=line,
            claim_type="evidence_gap",
            theme=theme,
            status=answer_model.ClaimStatus.MISSING,
        )
        for index, line in enumerate(risks[:6], start=1)
    )

    implications = _presentable_lines(
        "\n".join(result.sections.get("交易含义", []))
    )
    boundary_lines = implications or [
        "若关键证据或市场条件出现反向变化，当前判断应立即降级。"
    ]
    triggers = tuple(
        answer_model.make_claim(
            claim_id=f"base:trigger:{index}",
            text=line,
            claim_type="condition_boundary",
            theme=theme,
            status=answer_model.ClaimStatus.INFERRED,
            evidence_tier="base_finance",
            evidence_ids=evidence_ids,
        )
        for index, line in enumerate(boundary_lines[:3], start=1)
    )

    actions = list(action_lines) or _presentable_lines(
        "\n".join(result.sections.get("后续验证点", []))
    )
    if not actions:
        actions = ["补齐核心数据后重新裁决。"]
    spec = answer_model.AnswerSpec(
        research_spec=answer_model.ThemeResearchSpec(
            theme=theme,
            pack_id="base_finance_mode",
            definition="常驻金融问答基座",
            chain_stages=(),
            company_scope="",
            as_of=result.trade_date,
            evidence_requirements=(),
            counter_evidence_requirements=(),
            trigger_conditions=(),
            verification_actions=tuple(actions),
            focus_entities=(),
            requested_sections=(
                "direct_assessment",
                "strongest_evidence",
                "main_risk",
                "condition_boundary",
                "next_verification",
            ),
        ),
        summary=summary,
        verified_facts=verified_facts,
        company_table=(),
        counter_evidence=(),
        gaps=gaps,
        triggers=triggers,
        next_actions=tuple(actions),
        sources=tuple(dict.fromkeys(sources)),
        system_notices=tuple(
            item for item in (result.data_notice,) if item
        ),
        prompt_constraints=tuple(
            item
            for item in (
                (
                    result.question_plan.to_prompt_block()
                    if result.question_plan is not None
                    else ""
                ),
                *evidence_blocks,
            )
            if item
        ),
        presentation_kind="base_finance",
        presentation_title=theme,
    )
    return answer_model.finalize_answer_spec(spec)


def _dedupe_structured_claims(
    claims: list[answer_model.Claim],
) -> list[answer_model.Claim]:
    seen: set[tuple[str, str | None, answer_model.ClaimStatus]] = set()
    result: list[answer_model.Claim] = []
    for claim in claims:
        key = (answer_model.humanize(claim.text), claim.company, claim.status)
        if key in seen:
            continue
        seen.add(key)
        result.append(claim)
    return result


def _prepare_answer_spec_synthesis(
    *,
    options: AskOptions,
    result: AskResult,
    question_plan: QuestionPlan,
    theme: str,
    citations: list[Citation],
    quality_context: AnswerQualityContext,
    is_market_review: bool,
) -> list[dict]:
    if result.answer_spec is None:
        return []
    citation_legend = "\n".join(
        f"[{citation.tag}] {citation.source}"
        + (f" — {citation.detail}" if citation.detail else "")
        for citation in citations
    )
    us = userspace.user_space(options.user)
    perspective_context = perspective_lab.build_runtime_context(
        us,
        mode=options.perspective_mode,
        perspective_ids=options.perspective_ids,
        query=options.query,
    )
    experience_guidance = ""
    if options.include_memory_block:
        cards, card_warn = experience_cards.load_cards(
            us.experience_cards_path,
            window=options.experience_cards_window,
        )
        if card_warn:
            result.warnings.append(card_warn)
        selected_cards = experience_cards.select_relevant_cards(
            cards,
            options.query,
        )
        experience_guidance = experience_cards.render_for_prompt(
            selected_cards
        )
    exemplar_guidance = _exemplar_guidance_for(question_plan.question_type)
    if options.include_scenario_guidance:
        scenario_guidance = scenario_tree.scenario_guidance_for_query(
            options.query,
            question_plan.question_type,
        )
        if scenario_guidance:
            experience_guidance = (
                f"{experience_guidance}\n\n{scenario_guidance}"
                if experience_guidance
                else scenario_guidance
            )
    messages = llm_refine.build_synthesis_messages(
        options.query,
        theme,
        result.answer_spec.to_prompt_block(),
        citation_legend=citation_legend,
        quality_context=None if is_market_review else quality_context,
        experience_guidance=experience_guidance,
        exemplar_guidance=exemplar_guidance,
    )
    messages[0]["content"] = (
        f"{messages[0]['content']}\n\n## 本轮视角约束\n"
        f"{perspective_context.prompt}"
    )
    if options.conversation_context:
        messages.insert(
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
    return messages


def synthesize_prepared_answer(prepared: PreparedAnswer) -> AskResult:
    options = prepared.options
    result = prepared.result
    messages = result.prepared_synthesis_messages
    if result.answer_spec is None or not messages:
        return result
    if promote_daily_agent_grounded_answer(options, result):
        return result
    started = time.monotonic()
    deadline = _llm_deadline(options)
    chunks: list[str] = []
    provider_connect_ms: int | None = None
    first_token_ms: int | None = None
    last_token_ms: int | None = None
    stream_elapsed_ms: int | None = None
    quality_gate_ms: int | None = None
    provider_finish_reason: str | None = None
    provider = llm_refine.detect_provider(options.llm_model)

    def capture_connected() -> None:
        nonlocal provider_connect_ms
        if provider_connect_ms is None:
            provider_connect_ms = max(
                0,
                round((time.monotonic() - started) * 1000),
            )

    def capture(delta: str) -> None:
        nonlocal first_token_ms, last_token_ms
        if options.stream_cancel_check is not None and options.stream_cancel_check():
            raise llm_refine.LLMStreamCancelled()
        elapsed_ms = max(0, round((time.monotonic() - started) * 1000))
        if first_token_ms is None:
            first_token_ms = elapsed_ms
        last_token_ms = elapsed_ms
        chunks.append(delta)

    def capture_finish_reason(finish_reason: str | None) -> None:
        nonlocal provider_finish_reason
        if finish_reason in {
            "stop",
            "length",
            "content_filter",
            "tool_calls",
            "function_call",
        }:
            provider_finish_reason = finish_reason

    def telemetry(
        *,
        composed: llm_refine.SynthesisResult | None,
        fallback_reason: str | None,
    ) -> dict[str, object]:
        elapsed_ms = max(0, round((time.monotonic() - started) * 1000))
        remaining_ms = max(0, round(deadline.remaining() * 1000))
        text = composed.answer if composed is not None else "".join(chunks)
        safe_finish_reason = (
            composed.finish_reason
            if composed is not None
            and composed.finish_reason
            in {"stop", "length", "content_filter", "tool_calls", "function_call"}
            else provider_finish_reason
        )
        return {
            "provider": (
                composed.provider
                if composed is not None
                else provider.name if provider is not None else None
            ),
            "model": (
                composed.model
                if composed is not None
                else provider.model if provider is not None else options.llm_model
            ),
            "deadline_ms": round(
                (
                    options.deadline.remaining()
                    if options.deadline is not None
                    else options.llm_timeout
                )
                * 1000
            ),
            "remaining_budget_ms": remaining_ms,
            "provider_connect_ms": provider_connect_ms,
            "first_token_ms": first_token_ms,
            "last_token_ms": last_token_ms,
            "stream_elapsed_ms": stream_elapsed_ms,
            "quality_gate_ms": quality_gate_ms,
            "total_synthesis_ms": elapsed_ms,
            "elapsed_ms": elapsed_ms,
            "chunk_count": len(chunks),
            "output_chars": len(text),
            "finish_reason": safe_finish_reason,
            "thinking_disabled": llm_refine.synthesis_thinking_disabled(),
            "fallback_reason": fallback_reason,
        }

    if result.prepared_synthesis_is_market_review:
        composed, reason = llm_refine.synthesize_messages(
            messages,
            model_override=options.llm_model,
            timeout=_stage_timeout(options, options.llm_timeout),
            deadline=deadline,
        )
    elif options.compose_self_review:
        composed, reason = llm_refine.synthesize_messages_with_review(
            messages,
            model_override=options.llm_model,
            timeout=_stage_timeout(options, options.llm_timeout),
            deadline=deadline,
        )
    else:
        composed, reason = llm_refine.synthesize_messages_stream(
            messages,
            on_delta=capture,
            on_connected=capture_connected,
            on_finish_reason=capture_finish_reason,
            is_cancelled=options.stream_cancel_check,
            model_override=options.llm_model,
            timeout=_stage_timeout(options, options.llm_timeout),
            deadline=deadline,
        )
    stream_elapsed_ms = max(0, round((time.monotonic() - started) * 1000))
    if composed is None:
        result.warnings.append(reason)
        result.llm_fallback_reason = _stable_llm_fallback_reason(reason)
        result.llm_stream_telemetry = telemetry(
            composed=None,
            fallback_reason=result.llm_fallback_reason,
        )
        return result
    if composed.finish_reason is not None and composed.finish_reason != "stop":
        reason = (
            "LLM 合成响应被截断，已降级为模板"
            if composed.finish_reason == "length"
            else "LLM 合成未正常停止，已降级为模板"
        )
        result.warnings.append(reason)
        result.llm_fallback_reason = _stable_llm_fallback_reason(reason)
        result.llm_stream_telemetry = telemetry(
            composed=composed,
            fallback_reason=result.llm_fallback_reason,
        )
        return result
    result.llm_fallback_reason = composed.fallback_reason
    result.llm_stream_telemetry = telemetry(
        composed=composed,
        fallback_reason=result.llm_fallback_reason,
    )
    proposed_synthesis = composed.answer
    accepted_composition = composed
    quality_gate_started = time.monotonic()
    blocking_issues = [
        issue
        for issue in answer_model.validate_llm_answer(
            proposed_synthesis,
            result.answer_spec,
        )
        if issue.severity == "error"
    ]
    if blocking_issues and deadline.remaining() > 0:
        correction_started = time.monotonic()
        correction, correction_reason = llm_refine.synthesize_messages(
            [
                *messages,
                {
                    "role": "user",
                    "content": llm_refine.claim_binding_revision_user_content(
                        [issue.message for issue in blocking_issues],
                        answer_model.structured_claim_registry_block(
                            result.answer_spec
                        ),
                    ),
                },
            ],
            model_override=options.llm_model,
            timeout=_stage_timeout(options, options.llm_timeout),
            deadline=deadline,
            temperature=0.0,
        )
        result.llm_stream_telemetry["claim_binding_revision_ms"] = round(
            (time.monotonic() - correction_started) * 1000
        )
        result.llm_stream_telemetry["claim_binding_revision_reason"] = (
            correction_reason or None
        )
        if correction is not None:
            corrected_synthesis = correction.answer
            corrected_issues = answer_model.validate_llm_answer(
                corrected_synthesis,
                result.answer_spec,
            )
            corrected_blocking = [
                issue
                for issue in corrected_issues
                if issue.severity == "error"
            ]
            if not corrected_blocking:
                proposed_synthesis = corrected_synthesis
                accepted_composition = correction
                blocking_issues = []
            else:
                blocking_issues = corrected_blocking
    structured_claims, unbound_claim_lines = (
        answer_model.parse_structured_claims(proposed_synthesis)
    )
    quality_gate_ms = max(
        0,
        round((time.monotonic() - quality_gate_started) * 1000),
    )
    result.llm_stream_telemetry["quality_gate_ms"] = quality_gate_ms
    result.llm_stream_telemetry["total_synthesis_ms"] = max(
        0,
        round((time.monotonic() - started) * 1000),
    )
    result.llm_stream_telemetry["elapsed_ms"] = result.llm_stream_telemetry[
        "total_synthesis_ms"
    ]
    result.llm_stream_telemetry["structured_claim_count"] = len(
        structured_claims
    )
    result.llm_stream_telemetry["unbound_claim_line_count"] = len(
        unbound_claim_lines
    )
    if blocking_issues:
        result.warnings.extend(
            f"LLM 输出被 AnswerSpec 门禁拒绝：{issue.message}"
            for issue in blocking_issues
        )
        result.llm_fallback_reason = "quality_gate_rejected"
        result.llm_stream_telemetry["fallback_reason"] = result.llm_fallback_reason
        return result
    presented_synthesis = answer_model.present_llm_answer(
        proposed_synthesis,
        result.answer_spec,
    )
    result.synthesis = (
        f"{result.data_notice}\n\n{presented_synthesis}"
        if result.data_notice and not result.prepared_synthesis_is_market_review
        else presented_synthesis
    )
    result.llm_provider = accepted_composition.provider
    result.synthesis_messages = [
        *messages,
        {"role": "assistant", "content": result.synthesis},
    ]
    if options.stream_text_delta is not None:
        options.stream_text_delta(result.synthesis)
    if reason:
        result.warnings.append(reason)
    return result


def _strip_empty_grounded_sections(text: str) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    for index, line in enumerate(lines):
        if line.lstrip().startswith("#"):
            has_body = False
            for later in lines[index + 1 :]:
                if later.lstrip().startswith("#"):
                    break
                if later.strip():
                    has_body = True
                    break
            if not has_body:
                continue
        kept.append(line)
    collapsed: list[str] = []
    for line in kept:
        if not line.strip() and collapsed and not collapsed[-1].strip():
            continue
        collapsed.append(line)
    return "\n".join(collapsed).strip()


def _grounded_body_line_count(text: str) -> int:
    return sum(
        1
        for line in text.splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
        and "非投资建议" not in line
    )


def promote_daily_agent_grounded_answer(
    options: AskOptions,
    result: AskResult,
) -> bool:
    spec = result.answer_spec
    if (
        spec is None
        or spec.presentation_kind
        != answer_model.DAILY_AGENT_PRESENTATION_KIND
        or not options.daily_agent_grounded_presenter
    ):
        return False
    synthesize_shadow_grounded_answer(
        PreparedAnswer(
            options=replace(
                options,
                shadow_grounded_composer=True,
                shadow_grounded_timeout=max(
                    options.shadow_grounded_timeout, 240
                ),
            ),
            result=result,
        ),
        repair_drop_invalid=True,
        token_budget_scale=3,
    )
    shadow = result.grounded_composer_shadow
    presented = (
        _strip_empty_grounded_sections(shadow.presented_answer)
        if shadow is not None and shadow.presented_answer
        else ""
    )
    if (
        shadow is None
        or shadow.status not in {"accepted", "repaired"}
        or _grounded_body_line_count(presented) < 2
    ):
        if shadow is not None:
            reason = shadow.failure_reason or (
                "insufficient_grounded_body"
                if shadow.status in {"accepted", "repaired"}
                else shadow.status
            )
            result.warnings.append(
                "研究雷达自然语言合成未通过门禁或不可用"
                f"（{reason}），已降级回结构化合成。"
            )
        return False
    result.synthesis = (
        f"{result.data_notice}\n\n{presented}"
        if result.data_notice
        else presented
    )
    result.llm_provider = shadow.provider
    result.synthesis_messages = [
        *(result.prepared_synthesis_messages or []),
        {"role": "assistant", "content": result.synthesis},
    ]
    if options.stream_text_delta is not None:
        options.stream_text_delta(result.synthesis)
    return True


def _shadow_support_claims(
    answer_spec: answer_model.AnswerSpec,
) -> tuple[answer_model.Claim, ...]:
    return tuple(
        claim
        for claim in (*answer_spec.summary, *answer_spec.verified_facts)
        if claim.claim_id
        and claim.evidence_ids
        and claim.status is not answer_model.ClaimStatus.MISSING
    )


def synthesize_shadow_grounded_answer(
    prepared: PreparedAnswer,
    *,
    repair_drop_invalid: bool = False,
    token_budget_scale: int = 1,
) -> AskResult:
    options = prepared.options
    result = prepared.result
    if (
        not options.shadow_grounded_composer
        or result.answer_spec is None
    ):
        return result
    started = time.monotonic()
    if not _shadow_support_claims(result.answer_spec):
        result.grounded_composer_shadow = (
            answer_model.GroundedComposerShadow(
                status="ineligible_evidence",
                failure_reason="no_valid_support_claims",
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
        )
        return result
    deadline = llm_refine.Deadline.from_timeout(
        options.shadow_grounded_timeout
    )
    registry_block = answer_model.grounded_claim_registry_block(
        result.answer_spec
    )
    brief_result, brief_reason = llm_refine.synthesize_messages(
        llm_refine.build_decision_brief_messages(
            options.query,
            registry_block,
        ),
        model_override=options.llm_model,
        timeout=options.shadow_grounded_timeout,
        deadline=deadline,
        temperature=0.0,
        max_tokens=1200 * token_budget_scale,
        max_chars=8000 * token_budget_scale,
    )
    if brief_result is None:
        result.grounded_composer_shadow = (
            answer_model.GroundedComposerShadow(
                status="brief_unavailable",
                failure_reason=brief_reason,
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
        )
        return result
    decision_brief, brief_issues = answer_model.parse_decision_brief(
        brief_result.answer,
        result.answer_spec,
    )
    if decision_brief is None:
        result.grounded_composer_shadow = (
            answer_model.GroundedComposerShadow(
                status="brief_rejected",
                deterministic_issues=brief_issues,
                provider=brief_result.provider,
                model=brief_result.model,
                failure_reason="decision_brief_quality_gate_rejected",
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
        )
        return result
    composed, compose_reason = llm_refine.synthesize_messages(
        llm_refine.build_grounded_composer_messages(
            options.query,
            decision_brief.to_prompt_block(),
            registry_block,
        ),
        model_override=options.llm_model,
        timeout=max(1, int(deadline.remaining())),
        deadline=deadline,
        temperature=0.2,
        max_tokens=2400 * token_budget_scale,
        max_chars=16000 * token_budget_scale,
    )
    if composed is None:
        result.grounded_composer_shadow = (
            answer_model.GroundedComposerShadow(
                status="composer_unavailable",
                decision_brief=decision_brief,
                provider=brief_result.provider,
                model=brief_result.model,
                failure_reason=compose_reason,
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
        )
        return result
    raw_answer = composed.answer
    deterministic_issues = (
        answer_model.validate_grounded_composer_answer(
            raw_answer,
            result.answer_spec,
        )
    )
    candidate_answer = raw_answer
    repaired = False
    if any(
        issue.severity == "error" for issue in deterministic_issues
    ):
        deterministic_repair = (
            answer_model.repair_grounded_composer_answer(
                raw_answer,
                result.answer_spec,
                drop_invalid=repair_drop_invalid,
            )
        )
        if deterministic_repair is None:
            result.grounded_composer_shadow = (
                answer_model.GroundedComposerShadow(
                    status="deterministic_gate_rejected",
                    decision_brief=decision_brief,
                    raw_answer=raw_answer,
                    deterministic_issues=deterministic_issues,
                    provider=composed.provider,
                    model=composed.model,
                    failure_reason="deterministic_repair_failed",
                    elapsed_ms=round(
                        (time.monotonic() - started) * 1000
                    ),
                )
            )
            return result
        candidate_answer = deterministic_repair
        repaired = True
    sentences, _unbound = answer_model.parse_grounded_sentences(
        candidate_answer
    )
    judged, judge_reason = llm_refine.synthesize_messages(
        llm_refine.build_grounding_judge_messages(
            options.query,
            candidate_answer,
            registry_block,
        ),
        model_override=options.llm_model,
        timeout=max(1, int(deadline.remaining())),
        deadline=deadline,
        temperature=0.0,
        max_tokens=1200 * token_budget_scale,
        max_chars=8000 * token_budget_scale,
    )
    if judged is None:
        result.grounded_composer_shadow = (
            answer_model.GroundedComposerShadow(
                status="judge_unavailable",
                decision_brief=decision_brief,
                raw_answer=raw_answer,
                repaired_answer=(
                    candidate_answer if repaired else None
                ),
                deterministic_issues=deterministic_issues,
                provider=composed.provider,
                model=composed.model,
                failure_reason=judge_reason,
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
        )
        return result
    judge_report = answer_model.parse_grounding_judge_report(
        judged.answer,
        sentence_count=len(sentences),
    )
    if judge_report is None:
        result.grounded_composer_shadow = (
            answer_model.GroundedComposerShadow(
                status="judge_rejected",
                decision_brief=decision_brief,
                raw_answer=raw_answer,
                repaired_answer=(
                    candidate_answer if repaired else None
                ),
                deterministic_issues=deterministic_issues,
                judge_raw=judged.answer,
                provider=composed.provider,
                model=composed.model,
                failure_reason="judge_output_invalid",
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
        )
        return result
    if not judge_report.passed:
        semantic_repair = answer_model.repair_grounded_composer_answer(
            candidate_answer,
            result.answer_spec,
            rejected_sentence_indexes=(
                judge_report.rejected_sentence_indexes
            ),
            drop_invalid=repair_drop_invalid,
        )
        if semantic_repair is None:
            result.grounded_composer_shadow = (
                answer_model.GroundedComposerShadow(
                    status="semantic_gate_rejected",
                    decision_brief=decision_brief,
                    raw_answer=raw_answer,
                    repaired_answer=(
                        candidate_answer if repaired else None
                    ),
                    deterministic_issues=deterministic_issues,
                    judge_report=judge_report,
                    provider=composed.provider,
                    model=composed.model,
                    failure_reason="semantic_repair_failed",
                    elapsed_ms=round(
                        (time.monotonic() - started) * 1000
                    ),
                )
            )
            return result
        candidate_answer = semantic_repair
        repaired = True
    result.grounded_composer_shadow = (
        answer_model.GroundedComposerShadow(
            status="repaired" if repaired else "accepted",
            decision_brief=decision_brief,
            raw_answer=raw_answer,
            repaired_answer=candidate_answer if repaired else None,
            presented_answer=(
                answer_model.present_grounded_composer_answer(
                    candidate_answer
                )
            ),
            deterministic_issues=deterministic_issues,
            judge_report=judge_report,
            provider=composed.provider,
            model=composed.model,
            elapsed_ms=round((time.monotonic() - started) * 1000),
        )
    )
    return result


def _stable_llm_fallback_reason(reason: str) -> str:
    normalized = str(reason or "").casefold()
    if "未配置" in normalized:
        return "provider_unavailable"
    if "截止时间" in normalized or "超时" in normalized:
        return "timeout"
    if "输出超长" in normalized or "too long" in normalized:
        return "output_too_long"
    if "截断" in normalized or "length" in normalized:
        return "truncated_response"
    if "未正常停止" in normalized or "stalled" in normalized:
        return "provider_stalled"
    if "http" in normalized:
        return "provider_http_error"
    if "空内容" in normalized:
        return "empty_response"
    return "provider_unavailable"


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


def _evidence_chain_with_llm_wiki(
    evidence_chain: list[str],
    wiki_llm_line_pairs: list[tuple[str, str]],
) -> list[str]:
    if not wiki_llm_line_pairs:
        return evidence_chain
    replacements = dict(wiki_llm_line_pairs)
    return [replacements.get(item, item) for item in evidence_chain]


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


def _market_review_mainline_context_block_for_llm(
    query: str,
    theme: str | None,
    market_db_path: str | Path | None,
) -> str:
    market_date = _market_data_asof(market_db_path)
    db_path = Path(market_db_path).expanduser() if market_db_path else REPO_ROOT / "db" / "market_feature_store.duckdb"
    if not market_date or not db_path.exists():
        return ""
    try:
        import duckdb  # type: ignore

        con = duckdb.connect(str(db_path), read_only=True)
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
            theme_date = None
            themes: list[tuple[str, int]] = []
            if "fact_mainline_theme_daily" in table_names:
                row = con.execute(
                    "select max(trade_date) from fact_mainline_theme_daily"
                ).fetchone()
                theme_date = str(row[0]) if row and row[0] else None
                if theme_date == market_date:
                    themes = [
                        (str(name), int(sector_count or 0))
                        for name, sector_count in con.execute(
                            """
                            select theme_name, sector_count
                            from fact_mainline_theme_daily
                            where trade_date = ?
                            order by min_sort nulls last, theme_name
                            limit 10
                            """,
                            [theme_date],
                        ).fetchall()
                        if name
                    ]
            sector_date = None
            if "fact_mainline_sector_daily" in table_names:
                row = con.execute(
                    "select max(trade_date) from fact_mainline_sector_daily"
                ).fetchone()
                sector_date = str(row[0]) if row and row[0] else None
        finally:
            con.close()
    except Exception:
        return ""
    if sector_date == market_date:
        return _mainline_context_block_for_llm(query, theme, market_db_path)
    lines = ["## 市场复盘主线数据边界"]
    if theme_date == market_date and themes:
        theme_text = "、".join(name for name, _ in themes)
        lines.append(
            f"- 当日市场总览和题材级主线汇总均截至 {market_date}；"
            f"当前主线题材为 {theme_text}。"
        )
    elif theme_date:
        lines.append(
            f"- 当日市场总览截至 {market_date}；主线题材汇总仅截至 {theme_date}。"
        )
        lines.append(
            "- 当前交易日的题材级主线未知，禁止把旧题材名称写成当日事实。"
        )
    else:
        lines.append(
            f"- 当日市场总览截至 {market_date}；没有可用的同日主线题材汇总。"
        )
        lines.append("- 当前交易日的题材级主线未知。")
    if sector_date:
        lines.append(
            f"- 核心板块明细仅截至 {sector_date}；当前核心板块、周期状态和标的未知。"
        )
    else:
        lines.append("- 没有可用的核心板块明细；当前核心板块、周期状态和标的未知。")
    lines.append(
        "- 禁止把旧板块名称、涨幅、生命周期或标的写成当日事实。"
    )
    return "\n".join(lines)


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

        theme_date = None
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
                if theme_text and str(theme_date) == trade_date:
                    lines.append(f"- 主线题材（截至 {theme_date}）：{theme_text}。")
                elif theme_text:
                    lines.append(
                        f"- 主线题材汇总仅截至 {theme_date}，早于整体盘面日期 {trade_date}；"
                        "当前题材级主线未知，不展示旧题材名称。"
                    )

        if "fact_mainline_sector_daily" in table_names:
            sector_date_row = con.execute(
                "select max(trade_date) from fact_mainline_sector_daily"
            ).fetchone()
            sector_date = sector_date_row[0] if sector_date_row else None
            if sector_date and str(sector_date) != trade_date:
                if theme_date and str(theme_date) == trade_date:
                    lines.append(
                        f"- 局部数据提示：题材级主线汇总已更新到 {trade_date}，"
                        f"但核心板块明细仅更新到 {sector_date}；当前核心板块、周期状态和标的未知。"
                    )
                else:
                    lines.append(
                        f"- 局部数据提示：核心板块明细仅更新到 {sector_date}，"
                        f"早于整体盘面日期 {trade_date}；只能作历史参考。"
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


def _is_market_index_comparison_query(query: str) -> bool:
    names = ("上证指数", "深证成指", "创业板指")
    return sum(name in query for name in names) >= 2


def _quoted_topic(query: str) -> str | None:
    match = re.search(r"[“《\"]([^”》\"]{2,40})[”》\"]", query)
    return match.group(1).strip() if match else None


def _theme_research_framing(
    research_spec: answer_model.ThemeResearchSpec | None,
    matched_theme: str | None,
) -> dict[str, list[str]]:
    if research_spec is None:
        return {}
    stage_labels = ("上游", "中游", "下游")
    chain_lines = [
        f"产业链{stage_labels[index] if index < len(stage_labels) else index + 1}"
        f"（研究口径，待公司级证据验证）：{stage}。"
        for index, stage in enumerate(research_spec.chain_stages)
    ]
    framing = {
        "conclusion": [
            f"题材定义（研究口径，非公司级事实）：{research_spec.definition}"
        ],
        "evidence": [
            *chain_lines,
            f"公司映射边界：{research_spec.company_scope}",
        ],
        "gaps": [
            "事实、推测与待验证边界：题材定义和产业链属于研究口径；"
            f"公司结论必须满足：{'、'.join(research_spec.evidence_requirements)}。"
        ],
        "follow_ups": [
            f"核验动作：{action}" for action in research_spec.verification_actions
        ],
    }
    if matched_theme and matched_theme not in research_spec.theme:
        framing["conclusion"].append(
            f"盘面数据仅以“{matched_theme}”作为近似映射，不能替代"
            f"“{research_spec.theme}”本身的公司级证据。"
        )
    return framing


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _confidence_score(value: Any) -> float | None:
    normalized = str(value or "").strip().lower()
    mapped = {
        "high": 0.9,
        "medium": 0.65,
        "mid": 0.65,
        "low": 0.35,
    }.get(normalized)
    return mapped if mapped is not None else _finite_float(value)


def _populate_market_index_comparison(
    result: AskResult,
    query: str,
    market_db_path: str | Path | None,
) -> None:
    requested = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", query)
    trade_date = requested.group(1) if requested else result.trade_date
    result.trade_date = trade_date
    result.next_trade_date = next_trading_day(
        trade_date,
        db_path=market_db_path,
    )
    db_path = (
        Path(market_db_path).expanduser()
        if market_db_path
        else REPO_ROOT / "db" / "market_feature_store.duckdb"
    )
    row: tuple[Any, ...] | None = None
    if trade_date and db_path.exists():
        try:
            import duckdb  # type: ignore

            con = duckdb.connect(str(db_path), read_only=True)
            try:
                row = con.execute(
                    """
                    select sh_index_close, sh_index_pct_chg, sh_index_amount,
                           sh_index_volume, sh_index_source
                    from fact_market_daily
                    where trade_date = ?
                    """,
                    [trade_date],
                ).fetchone()
            finally:
                con.close()
        except Exception:
            row = None

    evidence: list[str] = []
    gaps: list[str] = []
    citations: list[Citation] = []
    if row:
        close = _finite_float(row[0])
        pct_chg = _finite_float(row[1])
        amount = _finite_float(row[2])
        volume = _finite_float(row[3])
        raw_source = str(row[4] or "")
        source = (
            "AkShare 上证指数日线"
            if raw_source.startswith("akshare:")
            else "本地市场数据"
        )
        metric = "成交额缺失；成交量等可用强弱指标也缺失"
        if amount is not None:
            metric = f"成交额 {amount / 100_000_000:.2f} 亿元"
        elif volume is not None:
            metric = (
                f"成交额缺失；可用强弱指标为成交量 "
                f"{volume / 100_000_000:.2f} 亿"
            )
        close_text = f"{close:.3f}" if close is not None else "缺失"
        pct_text = f"{pct_chg:+.2f}%" if pct_chg is not None else "缺失"
        evidence.append(
            f"上证指数：收盘 {close_text}，当日涨跌 {pct_text}，{metric}；"
            f"来源：{source}；数据截止日：{trade_date}。[S1]"
        )
        citations.append(
            Citation(
                "S1",
                source,
                f"上证指数日线，截至 {trade_date}",
            )
        )
        result.found_market = True
    else:
        evidence.append(
            f"上证指数：当日涨跌、成交或强弱指标均缺失；"
            f"当前本地数据源未找到 {trade_date or '目标日期'} 记录，不猜测。"
        )
        gaps.append("上证指数目标交易日记录缺失。")

    for name in ("深证成指", "创业板指"):
        evidence.append(
            f"{name}：当日涨跌、成交或强弱指标均缺失；"
            "当前本地市场库未覆盖该指数日线，不使用其他指数或自然语言描述代替。"
        )
        gaps.append(f"{name}日线未接入，无法完成三指数强弱排序。")

    next_trade_line = (
        f"下一交易日为 {result.next_trade_date}（按交易日历确认）。"
        if result.next_trade_date
        else "下一交易日待交易日历确认，不按自然日猜测。"
    )
    conclusion = [
        f"{trade_date or '目标日期'} 的三指数对比只能部分完成："
        "上证指数有可验证日线，深证成指和创业板指明确缺失。",
        next_trade_line,
    ]
    result.sections = {
        "结论": conclusion,
        "证据链": evidence,
        "分歧反证": gaps
        or ["三项指数均有完整同口径日线，可直接比较。"],
        "后续验证点": [
            "补同步深证成指与创业板指同一交易日的收盘、涨跌幅和成交指标。",
            "三项指数必须使用同一来源、同一截止日后再做强弱排序。",
            f"在 {result.next_trade_date or '下一交易日'} 开盘前复核数据是否完成更新。",
        ],
        "检索可观测": [],
        "输出质检": [],
        "交易含义": [
            "当前只能确认上证指数当日表现，不能据此推断深证成指或创业板指相对强弱。"
        ],
        "引用来源": [
            f"[{citation.tag}] {citation.source} — {citation.detail}"
            for citation in citations
        ],
    }
    result.citations = citations


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
    timeout: float = 8.0,
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
    return market_financials.financials_block_for_target(
        target_code,
        target_name,
        fetcher=fetcher,
        timeout=timeout,
    )


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
NO_EVIDENCE_NOTICE = "本轮没有形成可用于结论的可验证来源；以下内容仅作待验证线索。"


def render_answer(result: AskResult) -> str:
    use_research_answer_spec = result.answer_spec is not None
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
    if not result.citations and not use_research_answer_spec:
        lines.append(f"> {NO_EVIDENCE_NOTICE}")
    if result.synthesis:
        lines.append("")
        lines.append("## 【对话式回答】"
                     + (f"（LLM·{result.llm_provider} 有机合成）" if result.llm_provider else ""))
        lines.append("")
        lines.append(result.synthesis.rstrip())
        lines.append("")
        lines.append("---")
        lines.append("*以下为确定性检索的结构化证据，供核对引用编号：*")
    elif use_research_answer_spec:
        assert result.answer_spec is not None
        lines.append("")
        lines.append(answer_model.render_answer_spec(result.answer_spec).rstrip())
        if result.detail_reports:
            lines.append("")
            lines.append("## 【模块完整报告（--detail 钻取）】")
            for label, body in result.detail_reports:
                lines.extend(
                    [
                        "",
                        f"<details><summary>完整报告 · {label}</summary>",
                        "",
                        body.rstrip(),
                        "",
                        "</details>",
                    ]
                )
        return "\n".join(lines) + "\n"
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
    evidence_notice = f"{NO_EVIDENCE_NOTICE}\n\n" if not result.citations else ""
    if result.synthesis:
        return result.synthesis
    if result.answer_spec is not None:
        return answer_model.render_answer_spec(result.answer_spec)

    lines: list[str] = []
    if evidence_notice:
        lines.append(NO_EVIDENCE_NOTICE)
    if result.data_notice:
        if lines:
            lines.append("")
        lines.append(result.data_notice)
    if re.search(r"T\+1|下一交易日|明天", result.query, re.IGNORECASE):
        if lines:
            lines.append("")
        if result.next_trade_date:
            lines.append(
                f"下一交易日为 {result.next_trade_date}（按交易日历确认，不按自然日顺延）。"
            )
        else:
            lines.append("下一交易日（日期待交易日历确认），不得按自然日猜测。")
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

    visible_sections = (
        ("结论", 8),
        ("证据链", 40),
        ("分歧反证", 12),
        ("后续验证点", 12),
        ("交易含义", 6),
        ("引用来源", 12),
    )
    rendered_sections = False
    for title, limit in visible_sections:
        if result.market_summary and title == "证据链":
            continue
        items = result.sections.get(title, [])
        if not items:
            continue
        if lines:
            lines.append("")
        lines.append(f"## {title}")
        for item in items[:limit]:
            if item.startswith(SUBHEAD):
                lines.append(f"### {item[len(SUBHEAD):]}")
            else:
                lines.append(f"- {item}")
        rendered_sections = True

    if rendered_sections or result.market_summary:
        if lines:
            lines.append("")
        lines.append(
            "自然语言综合暂时不可用；以上为确定性检索结果，"
            "缺失项未作猜测。完整来源和结构化产物保留在“运行详情”中。"
        )
    else:
        if lines:
            lines.append("")
        lines.append(
            "本轮检索已完成，但没有形成可展示的确定性结果。"
            "自然语言综合暂时不可用，请在“运行详情”中核对数据缺口后重试。"
        )
    return "\n".join(lines).rstrip() + "\n"
