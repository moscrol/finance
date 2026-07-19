"""ask 的公共类型与常量层：AskOptions/AskResult/Citation/PreparedAnswer（从 ask.py 拆出，行为不变）。"""

from __future__ import annotations


import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from intelligence.services import (
    answer_model,
    ask_clarify,
    entity_anchor,
    kb_rag,
    l3_evidence,
    llm_refine,
    perspective_lab,
    research_brief,
)
from intelligence.services.answer_orchestrator import (
    QuestionPlan,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchDeadline
from intelligence.services import event_transmission, evidence_gap_radar, market_structure, output_review, valuation_gap


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

SUBHEAD = "\x00SUB\x00"
SECTION_ORDER = ["结论", "证据链", "分歧反证", "后续验证点", "检索可观测", "输出质检", "交易含义", "引用来源"]
NO_EVIDENCE_NOTICE = "本轮没有形成可用于结论的可验证来源；以下内容仅作待验证线索。"




# Trade-date freshness threshold (calendar days) above which graph evidence is
# flagged as potentially stale. Stand-in for a real Temporal Facts layer.
DEFAULT_STALE_DAYS = 45

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
    # 通用 Grounded Presenter：非 market_review 的 compose 回答也走 Grounded Composer
    # 链路（DecisionBrief → 自然语言成文 → 确定性门禁 → 逐句语义审 → 逐句修复），
    # LLM 保留最终措辞；任一阶段不可用或门禁未过时降回结构化 claim 合成路径。
    grounded_presenter: bool = field(
        default_factory=lambda: os.environ.get(
            "WORKBENCH_GROUNDED_PRESENTER",
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
    # 数据块 provider 白名单（evidence_registry）：None（默认）走上面各 include_*_block
    # 旧开关，完全兼容；给定集合时只允许名单内的块参与门控（意图门控仍生效，
    # enabled 是“允许”不是“强制取数”）。
    enabled_providers: tuple[str, ...] | None = None
    # 澄清追问前置门（clarify-then-act）：问题明确模糊（空问题/纯空泛词面）时不硬答，
    # 返回结构化澄清问题（对象/口径/日期），跳过整次检索；带实质内容的问题行为逐字节不变。
    clarify: bool = True
    # Workbench 专项 Skill answer-owner 可固定问题类型，避免再次依赖脆弱词面分类。
    question_type_override: str | None = None
    # Turn Controller 判定的能力需求（web_search/market_news 等）：W7 web 事件检索块
    # 据此在词面意图未命中时仍然生成，承接未被任何 skill 路由命中的长尾问题；
    # 空元组时 W7 门控行为不变。
    controller_capabilities: tuple[str, ...] = ()
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

def _stage_timeout(options: AskOptions, configured_limit: float) -> float:
    if options.deadline is None:
        return max(0.001, float(configured_limit))
    return max(0.001, options.deadline.stage_timeout(configured_limit))


def _llm_deadline(options: AskOptions) -> llm_refine.Deadline:
    if options.deadline is not None:
        return llm_refine.Deadline(options.deadline.expires_at)
    return llm_refine.Deadline.from_timeout(options.llm_timeout)


