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
from intelligence.paths import data_repo_root, default_market_db_path
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import (
    ResearchDeadline,
    ResearchTaskContract,
)
from intelligence.services.research_policy import (
    GroundedBudgetProfile,
    grounded_deep,
)
from intelligence.services import event_transmission, evidence_gap_radar, market_structure, output_review, valuation_gap


REPO_ROOT = Path(__file__).resolve().parents[2]

# 数据根唯一来源是 intelligence.paths。这里曾经复制了一份
# WORKBENCH_REPO_ROOT → FINANCE_WS 查找，和 paths 分叉——生产 launcher
# 把 WORKBENCH_REPO_ROOT 指到代码快照，盘面层就静默消失。
_data_repo_root = data_repo_root
DATA_REPO_ROOT = data_repo_root()
DEFAULT_EXPORTS_DIR = DATA_REPO_ROOT / "market_feature_store" / "exports"
# 盘面 DuckDB 默认路径的唯一来源在 intelligence.paths（叶子模块，四个 market_*
# 模块也要用，从这里导入会成环）。此处重导出，保持既有调用方不变。
DEFAULT_MARKET_DB_PATH = default_market_db_path()

SUBHEAD = "\x00SUB\x00"
SECTION_ORDER = ["结论", "证据链", "分歧反证", "后续验证点", "检索可观测", "输出质检", "交易含义", "引用来源"]
# 控制面 section（P2 公共投影分离）：检索遥测/质检明细/provider 状态属于
# ResearchInspector 面——CLI render_answer 全量渲染（自查用），但不进入
# 用户报告模块与会话答案。数据本体仍在 provider_traces / retrieval_telemetry /
# review_gate 上，经 _record_retrieval trace 落盘，可观测性不丢。
CONTROL_PLANE_SECTIONS = frozenset({"数据源状态", "检索可观测", "输出质检"})
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
            os.environ.get(
                "WORKBENCH_SHADOW_GROUNDED_TIMEOUT",
                str(grounded_deep.child_seconds),
            )
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
    # 通用 Grounded Presenter：compose 回答（包括 market_review）走 Grounded Composer
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
    # 固定日报工作流需把 L2 作为显式模块，即使用户问题没有重复写“资金流”也要取数。
    force_moneyflow_block: bool = False
    # 情景树/推演表达层：推演类问题命中时向 synthesis prompt 注入「变量表→情景分支→监控信号」
    # 表达契约（禁数值概率，likelihood 只准高/中/低并注依据）；非推演问题不注入，行为不变。
    include_scenario_guidance: bool = True
    # 跟踪表达层（q8 契约回灌）：theme_track 类问题命中时注入「delta-only + 观点四态对照 +
    # 结论 TTL + 下期关注清单」表达契约；非跟踪问题不注入，行为不变。
    include_track_guidance: bool = True
    # 数据块允许名单（evidence_registry）：None（默认）= 全部允许，意图门控仍生效；
    # 给定集合时只允许名单内的块。关某一块用 without_providers / providers_allowing_memory。
    enabled_providers: tuple[str, ...] | None = None
    # 澄清追问前置门（clarify-then-act）：问题明确模糊（空问题/纯空泛词面）时不硬答，
    # 返回结构化澄清问题（对象/口径/日期），跳过整次检索；带实质内容的问题行为逐字节不变。
    clarify: bool = True
    # Workbench 专项 Skill answer-owner 可固定问题类型，避免再次依赖脆弱词面分类。
    question_type_override: str | None = None
    # GenericResearchOwner 长尾契约；非 None 时跳过通用固定 provider 前置链。
    research_task_contract: ResearchTaskContract | None = field(
        default=None,
        repr=False,
        compare=False,
    )
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
    # L3 runtime official evidence. True is an explicit override; False still
    # permits gap-driven lookup for deep valuation/company work and explicit
    # customer/order/production questions.
    use_l3_lookup: bool = False
    l3_lookup_timeout: int = 480
    l3_lookup_limit: int = 5
    # 质检 WARN 回灌修订（修订版在前契约）：compose 回答经 output_review 闸门后若有 WARN，
    # 把意见送回同一段对话做一轮定向修订，用户拿到修订版全文，审查意见退居「输出质检」附录。
    # 仅影响 compose 路径；模板路径与无 WARN 时行为逐字节不变。
    compose_revise_on_warn: bool = True
    conversation_context: str = ""
    supplemental_evidence: str = ""
    # 非 owner skill 的结构化事实不能只以 prompt 文本穿过合成层；由编排器
    # 铸成候选 claim + Citation 后，沿 AnswerSpec 同一证据通道传播。
    supplemental_claims: tuple[answer_model.Claim, ...] = ()
    supplemental_citations: tuple[Any, ...] = ()
    perspective_mode: str = perspective_lab.PERSPECTIVE_MODE_NEUTRAL
    perspective_ids: tuple[str, ...] = ()
    # Frozen text from the turn's single activate(). None = rebuild;
    # "" = already activated as empty (degraded / neutral).
    perspective_prompt_override: str | None = None
    stream_text_delta: Callable[[str], None] | None = field(
        default=None, repr=False, compare=False
    )
    stream_cancel_check: Callable[[], bool] | None = field(
        default=None, repr=False, compare=False
    )
    # 控制面阶段进度：供 Workbench trace/看门狗定位同步 Ask 卡点。
    # 只传阶段名、状态和计数/耗时，不得传证据正文或内部 locator。
    progress_callback: Callable[
        [str, str, dict[str, object]],
        None,
    ] | None = field(default=None, repr=False, compare=False)
    deadline: ResearchDeadline | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    # 合成尾段（composer+judge）的供给信封，刻意与 ``deadline`` 分开。
    #
    # ``deadline`` 是**检索窗口**：generic owner 按 tier 拿 30s/90s，用完就该收敛。
    # 但 composer/judge 是 turn 的合成尾段，由根 turn 的 synthesis_reserve 供给；
    # 此前两者共用 ``deadline``，导致 owner 的检索窗口反过来卡死合成——
    # standard tier 整个窗口 90s < 两段式准入地板 97s，于是 composer 恒被跳过，
    # 且不论研究跑得多快（run_20260805_204224_708450：入场剩 59.9s，判定 skip）。
    #
    # 为 None 时回退到 ``deadline``，保持既有调用方行为不变。
    synthesis_deadline: ResearchDeadline | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    # 本轮生效的 grounded 预算档位。为 None 时 ask_synthesis 回退到模块级
    # ``grounded_deep``——那是历史行为，但会让「门槛」和「发钱的那套」脱钩：
    # 门槛读全局常量，而窗口由 policy 决定，两边一错位就静默恒降级。
    grounded_budget_profile: GroundedBudgetProfile | None = field(
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


@dataclass(frozen=True)
class SynthesisPhase:
    """Grounded 链单段（brief/composer/judge）的可观测记录。

    只有纯数值和固定枚举，没有正文、没有 prompt——它要能安全地穿过公开 trace。

    存在的理由：这三段是串行 LLM 调用、共用一个 deadline，**降级几乎总是发生在
    其中一段**，但此前 trace 里连它们的名字都没有，只留下一句「未通过门禁或不可用」。
    结果是「哪一段吃掉了预算」只能靠读代码推，推错了就会去优化没坏的那一段。

    ``remaining_ms_at_entry`` 是这里最关键的一个数：它把「合成失败」和「合成压根
    没时间跑」区分开——前者要改 prompt/门禁，后者要改预算，处置完全相反。
    """

    name: str  # brief | composer | judge
    status: str  # ok | failed | skipped
    remaining_ms_at_entry: int = 0
    timeout_s: int = 0
    elapsed_ms: int = 0
    # 失败时的归一码（stable_llm_fallback_reason 的输出），成功时为空。
    reason_code: str = ""
    # provider=真实模型调用；deterministic=结构化投影/纯函数，不消耗模型预算。
    execution_mode: str = "provider"


@dataclass(frozen=True)
class SynthesisDiagnostic:
    """Safe control-plane reason for synthesis success or fallback."""

    state: str = "not_requested"
    reason_code: str = "not_requested"
    detail: str = "synthesis was not requested"
    prepared_message_count: int = 0
    candidate_claim_count: int = 0
    bound_claim_count: int = 0
    # 影子链的原始状态（accepted/repaired/judge_outage_released/*_unavailable…）。
    # ``state`` 是「用户拿到的是哪种答案」，``shadow_status`` 是「链条走到哪一步」，
    # 两者不可互相推导：同一个 rejected 可能来自 brief 失败也可能来自 judge 失败。
    shadow_status: str = ""
    phases: tuple[SynthesisPhase, ...] = ()

    def __post_init__(self) -> None:
        # Diagnostic detail is a control-plane summary, never a second channel for
        # prompts or evidence bodies.  Collapse whitespace before applying the hard
        # cap so a multiline provider error cannot inflate the public trace.
        detail = re.sub(r"\s+", " ", str(self.detail or "")).strip()
        object.__setattr__(
            self,
            "detail",
            (detail or "no additional detail")[:200],
        )


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
    # 图谱暴露的召回/送达比。found_graph 只说「命中了」，说不出「命中 86 家、
    # 只送了 12 家」——而后者才是答案质量的解释项。空 dict = 本轮没查图谱。
    graph_exposure_telemetry: dict[str, Any] = field(default_factory=dict)
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
    synthesis_diagnostic: SynthesisDiagnostic = field(
        default_factory=SynthesisDiagnostic
    )
    # Grounded 链逐段耗时/剩余预算。由 synthesize_shadow_grounded_answer 累积，
    # 再由 _set_synthesis_diagnostic 抄进 diagnostic 送上 trace。
    synthesis_phases: tuple[SynthesisPhase, ...] = ()
    grounded_composer_shadow: (
        answer_model.GroundedComposerShadow | None
    ) = None
    grounded_fallback_used: bool = False
    # 问答编排层：先解析问题类型/深度/视角/证据计划，再进入 compose。
    question_plan: QuestionPlan | None = None
    # 澄清追问：问题明确模糊时的结构化追问；非 None 表示本次未检索、等用户补充。
    clarify: ask_clarify.ClarifyDecision | None = None
    # 实体锚定结果：确定性实体解析命中的实体与锚定概念；None=未命中/未启用。
    anchored_entity: entity_anchor.EntityAnchor | None = None
    # 行情前瞻前置查漏门：从 research-queue（fallback daily-agent）判断是否应先补 DeepDive / L3 证据。
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
    # GenericResearchOwner 的确定性任务完成报告；仅控制面使用，不进入正文。
    completion_report: dict[str, object] | None = field(
        default=None,
        repr=False,
    )
    # Generic Owner 的业务完成度投影；与 run/HTTP transport status 分离。
    business_status: str = "unknown"
    # 最终用户可见正文的任务完成度；只在 Grounded Composer/repair 结束后
    # 计算，不复用检索阶段的 business_status。
    answer_status: str = "unknown"
    fulfillment_report: dict[str, object] | None = field(
        default=None,
        repr=False,
    )
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


def _synthesis_timeout(options: AskOptions, configured_limit: float) -> float:
    """合成阶段专用：可动用合成保留预算（见 ResearchDeadline.synthesis_reserve）。"""
    if options.deadline is None:
        return max(0.001, float(configured_limit))
    return max(0.001, options.deadline.synthesis_timeout(configured_limit))


def _llm_deadline(options: AskOptions) -> llm_refine.Deadline:
    if options.deadline is not None:
        return llm_refine.Deadline(options.deadline.expires_at)
    return llm_refine.Deadline.from_timeout(options.llm_timeout)
