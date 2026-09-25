"""Evidence capability planning for ownerless research.

Question type remains a coarse controller output. This module resolves the
evidence products a contract must obtain without adding another route table.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass

from intelligence.services.route_table import LANE_COMPOSITION_RULES
from intelligence.services.task_frame import (
    TaskFrame,
    has_explicit_date,
    task_frame_requires_retrieval,
)


@dataclass(frozen=True)
class EvidenceRequirement:
    provider_name: str
    capability: str
    mandatory: bool
    freshness: str = "current"
    reason: str = ""


@dataclass(frozen=True)
class EvidencePlan:
    profile: str = "general"
    requirements: tuple[EvidenceRequirement, ...] = ()
    freshness: str = "current"

    @property
    def mandatory_provider_names(self) -> tuple[str, ...]:
        return tuple(item.provider_name for item in self.requirements if item.mandatory)

    @property
    def optional_provider_names(self) -> tuple[str, ...]:
        return tuple(item.provider_name for item in self.requirements if not item.mandatory)

    @property
    def mandatory_capabilities(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.capability for item in self.requirements if item.mandatory))

    def to_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "freshness": self.freshness,
            "requirements": [asdict(item) for item in self.requirements],
        }


# 时间信号与主体信号必须分开。初版把「主线/盘面/市场结构/成交/涨停」同时放进
# _CURRENT_MARKERS 和下方的主体词表，于是 `has_time and has_subject` 这个 AND 对
# 这五个词退化成单词命中——「如何判断主线候选和噪音」因此被判成要当日盘面事实。
# 实测基线（tmp/probe_routing_baseline.py，18 条自然问法）里它是唯一的过度触发。
_CURRENT_TIME_MARKERS = (
    "当前", "目前", "现在", "今天", "今日", "最新", "近期", "最近",
    "这两天", "这几天", "当下", "此刻", "本周", "截至",
)
# 主体词：问的是整个市场/板块层面的状态，命中后 mainline_context 才有意义。
_MARKET_SUBJECT_MARKERS = (
    "市场", "大盘", "行情", "板块", "主线", "盘面", "a股", "指数",
)
# 盘面度量词：本身就蕴含「要看数据」，可以在没有时间词时独立成立
#（「涨停家数多少」「茅台多少钱」都没有时间词，但都必须查行情）。
_MARKET_STATE_MARKERS = (
    "市场结构", "成交", "涨停", "涨跌", "家数", "情绪", "换手", "北向",
    "多少钱", "股价", "价格", "收盘",
)
# 现状判断词：不带时间词、也不带度量词，但问的就是「此刻强不强/在什么位置」。
# 「A股强不强」在纯时间词方案下一个都命中不了。这里刻意不收「怎么样/如何」这类
# 泛问句词——它们会把「市盈率怎么计算」这类知识题也拖进来；只收对**状态**本身
# 发问的说法，且必须与主体词同时出现才成立。
_PRESENT_CONDITION_MARKERS = (
    "强不强", "强弱", "强势", "弱势", "什么位置", "什么状态",
    "什么阶段", "处于", "健康", "有没有机会",
)
# 前瞻时间词：判断「未来一个月哪个会成为主线」同样要以当日盘面为基线，
# 缺了它 test_comparative_mainline_decision_overrides_single_theme_defaults 会掉。
# 那条测试原先是靠 bug 通过的——旧词表里「主线」同时是时间词和主体词，AND 退化成
# 单词命中，恰好放它过去。信号其实是时间锚指向未来，不是「主线」这个词。
_FORWARD_TIME_MARKERS = (
    "未来", "明天", "明日", "后天", "下周", "下个月", "下半年",
    "接下来", "后续", "还能", "能不能持续",
)
_HISTORICAL_MARKERS = ("2025", "2024", "历史上", "过去几年", "去年")
# 「如何判断/怎么设计 X」问的是方法，不是当日盘面；这类问题即使带市场词也
# 不该拿到行情数据（既有注释里「避免金融数据泄漏进知识题」的同一条纪律）。
_DECISION_METHOD_RE = re.compile(
    r"(?:应该|应当|该|如何|怎么|怎样).{0,20}(?:判断|区分|识别|设计|实现|构造)"
)
_RUNTIME_CAPABILITY_FLOOR: dict[str, tuple[str, ...]] = {
    "current_a_share_market": ("market_data", "mainline_context"),
    "dated_a_share_market": ("market_data", "mainline_context"),
    "current_market_scenarios": (
        "market_data",
        "mainline_context",
    ),
    "time_aligned_market_causal": (
        "market_data",
        "news_search",
        "web_search",
    ),
    "structured_market_technical": ("market_data",),
    "current_external_market": ("market_data", "news_search", "web_search"),
    # memory_lookup 默认只加在「用户很可能对该主体表达过看法」的策略上
    # （公司深挖、题材分析、题材跟踪、买卖题条件化 thesis），不是全部 20 条：
    # 它每次占一个工具槽，而实测一轮 research 在 4-6 次调用就会
    # budget_exhausted，广授权会挤掉盘面查询。取值查询和方法论讨论仍然不加。
    #
    # 例外是 general_finance_evidence（见下）：残差题没有子 skill 菜单，Knevo
    # 形下限要求记忆+行情+新闻同时在授权里。这里接受预算拥挤，不是漏把第四条
    # 策略误加进去。
    "company_multi_layer_evidence": (
        "market_data",
        "kb_search",
        "graph_lookup",
        "evidence_lookup",
        "web_search",
        "memory_lookup",
    ),
    "company_valuation_evidence": (
        "market_data",
        "financial_data",
        "kb_search",
        "evidence_lookup",
        "web_search",
    ),
    "theme_multi_layer_evidence": (
        "kb_search",
        "graph_lookup",
        "news_search",
        "web_search",
        "memory_lookup",
    ),
    "event_and_official_evidence": (
        "graph_lookup",
        "evidence_lookup",
        "news_search",
        "web_search",
        "l3_lookup",
    ),
    "company_financial_evidence": (
        "market_data",
        "financial_data",
        "kb_search",
        "evidence_lookup",
        "l3_lookup",
        "web_search",
    ),
    "current_fact_evidence": (
        "market_data",
        "kb_search",
        "evidence_lookup",
        "web_search",
    ),
    "theme_tracking_evidence": (
        "market_data",
        "mainline_context",
        "kb_search",
        "graph_lookup",
        "news_search",
        "web_search",
        "memory_lookup",
    ),
    "source_critique_evidence": (
        "kb_search",
        "evidence_lookup",
        "news_search",
        "web_search",
    ),
    "comparable_multi_source_evidence": (
        "kb_search",
        "graph_lookup",
        "evidence_lookup",
        "web_search",
    ),
    "event_scenario_evidence": ("graph_lookup", "news_search", "web_search"),
    "claim_verification_evidence": (
        "kb_search",
        "evidence_lookup",
        "news_search",
        "web_search",
        "l3_lookup",
    ),
    "conditional_thesis_evidence": (
        "market_data",
        "kb_search",
        "graph_lookup",
        "evidence_lookup",
        "news_search",
        "web_search",
        "memory_lookup",
    ),
    "current_public_knowledge": ("news_search", "web_search"),
    # 残差政策：Knevo 形三件套 + 原 kb/web。预算拥挤是有意取舍，见上方
    # memory_lookup 注释。
    "general_finance_evidence": (
        "market_data",
        "news_search",
        "memory_lookup",
        "kb_search",
        "web_search",
    ),
}

_PLAN_CAPABILITY_TO_RUNTIME: dict[str, str] = {
    "market_data": "market_data",
    "mainline_context": "mainline_context",
    "market_timeseries": "market_data",
    "market_midterm": "market_data",
    "kb_search": "kb_search",
    "graph_lookup": "graph_lookup",
    "evidence_lookup": "evidence_lookup",
    "news_search": "news_search",
    "web_search": "web_search",
    "l3_lookup": "l3_lookup",
}

# 工具身份 → 计划能力。finance_query 是结构化行情/板块事实的语义入口，
# 不是「名字里有 daily 就算行情」的字符串启发。
_TOOL_RECEIPT_PLAN_CAPABILITIES: dict[str, frozenset[str]] = {
    "finance_query": frozenset({"finance_query", "market_data", "mainline_context"}),
    "market_data": frozenset({"market_data"}),
    "mainline_context": frozenset({"mainline_context"}),
    "financial_data": frozenset({"financial_data"}),
}

# dataset id 是注册表键，精确查找。空 dataset 不加能力，只靠工具身份。
_DATASET_PLAN_CAPABILITIES: dict[str, frozenset[str]] = {
    "sector_daily": frozenset({"market_data", "mainline_context"}),
    "market_daily": frozenset({"market_data"}),
    "stock_daily": frozenset({"market_data"}),
    "sector_stock_daily": frozenset({"market_data", "mainline_context"}),
    "mainline_theme_daily": frozenset({"market_data", "mainline_context"}),
    "mainline_sector_daily": frozenset({"market_data", "mainline_context"}),
    "theme_limit_heat_daily": frozenset({"market_data", "mainline_context"}),
}

# overlay 追加行的 (provider, mandatory, freshness)。mandatory 必须与 overnight
# 既有行为一致：news_search / web_search 都是 required=False。
_OVERLAY_REQUIREMENT_TEMPLATE: dict[str, tuple[str, bool, str]] = {
    "news_search": ("W7", False, "current"),
    "web_search": ("WEB", False, "current"),
}

_OVERLAY_REASONS: dict[tuple[str, str], str] = {
    ("overnight_external_premise", "news_search"): "核验隔夜/外盘前提",
    ("overnight_external_premise", "web_search"): "外盘结构与海外来源",
    (
        "external_macro_event_local_inference",
        "news_search",
    ): "核验外部宏观事件前提",
    (
        "external_macro_event_local_inference",
        "web_search",
    ): "外部决议与海外来源",
}

# episode_tools 仍从本模块读这个私有名；与组合表第一条共用同一谓词对象。
_has_overnight_external_premise = next(
    rule.predicate
    for rule in LANE_COMPOSITION_RULES
    if rule.rule_name == "overnight_external_premise"
)

# V1b：题形 → optional KB 通道。全部 mandatory=False；预算仍走
# kb_rag.select_mode_for_remaining（<15s→BM25），本模块不另建降档。
_KB_GUIDED_QUESTION_TYPES = frozenset(
    {
        "theme_analysis",
        "theme_track",
        "stock_deep_dive",
        "market_cause",
        "valuation_estimate",
    }
)
_KB_OVERLAY_QUESTION_TYPES = frozenset({"dated_market_review", "market_review"})
# 词表与 query_understanding._CAUSE_LAYER_TOKEN_RE / _CAUSE_VERB_RE 对齐。
# 不收题材别名、不收单独「板块」——「今天板块表现如何」不得开火。
_SECTOR_THEME_LAYER_RE = re.compile(r"板块|题材|行业")
_ATTRIBUTION_INTENT_RE = re.compile(r"为什么|原因|驱动|归因")


def has_sector_theme_attribution_intent(query: str) -> bool:
    """复盘题形段级 overlay：层名词 ∧ 归因动词。

    ``dated_market_review`` 与别名 ``market_review`` 共用本函数，不得各写一份。
    可修订：扩动词（如「催化」）或改用题材别名，见 V1b 验证文档。
    """

    normalized = re.sub(r"\s+", "", str(query or "")).casefold()
    if not normalized:
        return False
    return bool(
        _SECTOR_THEME_LAYER_RE.search(normalized)
        and _ATTRIBUTION_INTENT_RE.search(normalized)
    )


def should_guide_kb_channel(query: str, question_type: str) -> bool:
    if question_type in _KB_GUIDED_QUESTION_TYPES:
        return True
    if question_type in _KB_OVERLAY_QUESTION_TYPES:
        return has_sector_theme_attribution_intent(query)
    return False


def _optional_kb_requirement() -> EvidenceRequirement:
    return EvidenceRequirement(
        "KB",
        "kb_search",
        False,
        "current",
        "知识库通道引导（图谱/研报/L1-L3；预算走 remaining-budget 既有分档）",
    )


def _with_kb_channel_guidance(
    query: str,
    question_type: str,
    requirements: tuple[EvidenceRequirement, ...],
) -> tuple[EvidenceRequirement, ...]:
    if not should_guide_kb_channel(query, question_type):
        return requirements
    present = {item.capability for item in requirements}
    if "kb_search" in present or "evidence_search" in present:
        return requirements
    return (*requirements, _optional_kb_requirement())


def is_current_market_query(query: str) -> bool:
    """识别需要同日市场事实的问题，不改变粗粒度 question_type。

    三条入口而不是一条 AND：时间词+主体词、显式日期+主体词、盘面度量词独立
    成立。初版只有第一条，于是「今天板块表现如何」（时间词表缺「今天」）、
    「以 2026-08-07 收盘为准…」（无时间词，只有日期）、「涨停家数多少」
    （无时间词）全部漏判。方法类提问先行排除，避免把知识题拖进行情数据。
    """

    normalized = re.sub(r"\s+", "", str(query or "")).casefold()
    if not normalized:
        return False
    if _DECISION_METHOD_RE.search(normalized):
        return False
    has_subject = any(
        marker in normalized for marker in _MARKET_SUBJECT_MARKERS
    )
    has_time = any(marker in normalized for marker in _CURRENT_TIME_MARKERS)
    # 局部名不能叫 has_explicit_date：那会遮蔽上面 import 进来的同名函数。
    dated = has_explicit_date(normalized)
    has_state = any(marker in normalized for marker in _MARKET_STATE_MARKERS)
    has_condition = any(
        marker in normalized for marker in _PRESENT_CONDITION_MARKERS
    )
    has_forward = any(marker in normalized for marker in _FORWARD_TIME_MARKERS)
    # 历史词只在「没有任何当期时间信号」时才排除。初版是无条件 return False，
    # 于是「最近行情和2024年哪段像」这类**今昔对比**被整条否掉——而它恰恰同时
    # 需要当日盘面和历史区间。纯历史复盘（“复盘2025年A股市场主线”，无时间词）
    # 仍然被排除，既有测试守着这条。
    if any(marker in normalized for marker in _HISTORICAL_MARKERS) and not (
        has_time or dated
    ):
        return False
    if has_subject and (has_time or dated or has_condition or has_forward):
        return True
    return has_state


def _overlay_requirement(capability: str, rule_name: str) -> EvidenceRequirement:
    spec = _OVERLAY_REQUIREMENT_TEMPLATE.get(capability)
    if spec is None:
        raise ValueError(
            f"lane composition overlay has no requirement template for {capability!r}"
        )
    provider_name, mandatory, freshness = spec
    reason = _OVERLAY_REASONS.get((rule_name, capability), "")
    return EvidenceRequirement(
        provider_name,
        capability,
        mandatory,
        freshness,
        reason,
    )


def _apply_lane_composition(
    query: str,
    requirements: tuple[EvidenceRequirement, ...],
) -> tuple[EvidenceRequirement, ...]:
    """按组合表追加缺失 capabilities。只加不删；后规则撞上已有 cap 则跳过。"""
    present = {item.capability for item in requirements}
    extras: list[EvidenceRequirement] = []
    for rule in LANE_COMPOSITION_RULES:
        if not rule.predicate(query):
            continue
        for capability in rule.extra_capabilities:
            if capability in present:
                continue
            extras.append(_overlay_requirement(capability, rule.rule_name))
            present.add(capability)
    return (*requirements, *extras)


# 公司主体题形：问题的主体是单一公司，同日大盘总览/主线结构只是背景放大器，
# 不是答案本体。这些题形若因「涨跌幅/成交额/股价」等盘面度量词命中
# is_current_market_query，套上市场级 mainline_current 计划就会把 market_data
# （市场总览，非个股行情）与 mainline_context 设为 mandatory——个股走势本身走
# finance_query，这两条组合事实约束在公司题形下要么结构性缺失（每答必记
# missing_mandatory_capability，修复轮白白追逐），要么答非所问（修复轮被契约
# 压着调 market_data，市场级数字混进个股稿）。R-20260821-05 生产 n=3 复现。
# 处置：降级为 optional——能力经 runtime_capabilities_for_frame 的 planned 并集
# 保持可用（背景可取），只去掉义务与修复追逐。valuation_estimate 在
# episode_factory._episode_evidence_plan 已有同意图先例（剥掉 resolve 计划里的
# market_data 再换公司级锚点）。已知边界：quick_fact 不在此列——「茅台多少钱」
# 与「涨停家数多少」同题形不同主体，题形本身分不出主体，需另行立项。
_COMPANY_SUBJECT_QUESTION_TYPES = frozenset(
    {"stock_deep_dive", "valuation_estimate", "financial_analysis"}
)


def resolve_evidence_plan(
    query: str,
    *,
    question_type: str,
    freshness: str = "current",
) -> EvidencePlan:
    # “概念解释 + 当前事实”是复合任务，不能被单一 concept_definition
    # 标签吞掉后半句。这里增加证据需求而不增加 route-table 题型：定义和
    # 当日事实仍由同一个 Generic Owner/ResearchState 合成。
    if question_type == "concept_definition" and is_current_market_query(query):
        plan = EvidencePlan(
            "current_market_fact",
            (
                EvidenceRequirement(
                    "D4",
                    "mainline_context",
                    True,
                    "current",
                    "当前市场指标定义与同日板块事实",
                ),
            ),
            "current",
        )
        return EvidencePlan(
            plan.profile,
            _with_kb_channel_guidance(
                query,
                question_type,
                _apply_lane_composition(query, plan.requirements),
            ),
            plan.freshness,
        )
    # 纯方法论/纯概念解释里的“市场、主线、当前”等词是讨论对象，不是要求
    # 当前盘面事实；能力层排除避免金融数据泄漏进知识题。
    if question_type in {"methodology_discussion", "answer_review", "concept_definition"}:
        return EvidencePlan(
            "general",
            _with_kb_channel_guidance(query, question_type, ()),
            freshness,
        )
    if question_type == "market_forecast":
        requirements = (
            EvidenceRequirement("MARKET_DAILY", "market_data", True, "current", "最新市场总览"),
            EvidenceRequirement("D4", "mainline_context", False, "current", "主线结构补充"),
        )
        return EvidencePlan(
            "market_forecast",
            _with_kb_channel_guidance(
                query,
                question_type,
                _apply_lane_composition(query, requirements),
            ),
            "current",
        )
    if freshness == "current" and is_current_market_query(query):
        if question_type in _COMPANY_SUBJECT_QUESTION_TYPES:
            plan = EvidencePlan(
                "company_current_backdrop",
                (
                    EvidenceRequirement(
                        "MARKET_DAILY",
                        "market_data",
                        False,
                        "current",
                        "同日市场总览（公司主体题仅作背景放大器，非必填）",
                    ),
                    EvidenceRequirement(
                        "D4",
                        "mainline_context",
                        False,
                        "current",
                        "同日主线结构（公司主体题仅作背景放大器，非必填）",
                    ),
                    EvidenceRequirement("D0", "market_timeseries", False, "current", "盘面时序补充"),
                    EvidenceRequirement("D6", "market_midterm", False, "current", "中期持续性补充"),
                    EvidenceRequirement("W7", "news_search", False, "current", "消息面补充"),
                ),
                "current",
            )
        else:
            plan = EvidencePlan(
                "mainline_current",
                (
                    EvidenceRequirement("MARKET_DAILY", "market_data", True, "current", "同日市场总览"),
                    EvidenceRequirement("D4", "mainline_context", True, "current", "同日主线结构"),
                    EvidenceRequirement("D0", "market_timeseries", False, "current", "盘面时序补充"),
                    EvidenceRequirement("D6", "market_midterm", False, "current", "中期持续性补充"),
                    EvidenceRequirement("W7", "news_search", False, "current", "消息面补充"),
                ),
                "current",
            )
        return EvidencePlan(
            plan.profile,
            _with_kb_channel_guidance(
                query,
                question_type,
                _apply_lane_composition(query, plan.requirements),
            ),
            plan.freshness,
        )
    # 知识题（methodology / answer_review / 纯 concept_definition）已在上面
    # 空计划返回。研究题落到 general 时仍要吃组合表——「美联储决议后 A 股
    # XX 板块」真实路由经常是 theme_analysis，不是测试里写死的 market_forecast。
    # overlay 只追加 capabilities，不发明 required_outputs，也不改 question_type。
    return EvidencePlan(
        "general",
        _with_kb_channel_guidance(
            query,
            question_type,
            _apply_lane_composition(query, ()),
        ),
        freshness,
    )


# 全工具授权的部署开关。默认关：按 ``_RUNTIME_CAPABILITY_FLOOR`` 逐策略给工具子集。
# 设为 ``all`` 时，需要检索的题一律拿到注册表全部工具——那张策略表存在的理由是
# 「一轮 4-6 次调用就 budget_exhausted，广授权会挤掉盘面查询」（见表头注释），它是
# 预算约束的派生物；2026-09-06 用户决策「先找能力 max、再按超限加约束」，预算一放开，
# 这层裁剪就没有独立理由了。不需要检索的题（方法论 / 用户前提）仍是空授权：那条是
# 防金融数据泄漏进知识题的正确性规则，不是预算规则，不随本开关放开。
TOOL_AUTHORIZATION_ENV = "WORKBENCH_TOOL_AUTHORIZATION"


def all_tools_authorized() -> bool:
    return os.environ.get(TOOL_AUTHORIZATION_ENV, "").strip().lower() == "all"


def runtime_capabilities_for_frame(frame: TaskFrame) -> tuple[str, ...]:
    """Project task semantics into the continuous runtime's tool namespace."""

    plan = resolve_evidence_plan(
        frame.raw_question,
        question_type=frame.question_type,
        freshness="current",
    )
    frame_requires_retrieval = task_frame_requires_retrieval(frame)
    if not frame_requires_retrieval and not plan.requirements:
        return ()
    if all_tools_authorized():
        # 延迟 import：research_tool_registry 在运行期 import 本模块所在的一族
        # （agent_research → …），模块级反向 import 会成环。
        from intelligence.services.research_tool_registry import (
            DEFAULT_RESEARCH_CAPABILITIES,
        )

        return tuple(DEFAULT_RESEARCH_CAPABILITIES)
    floor = _RUNTIME_CAPABILITY_FLOOR.get(frame.evidence_policy)
    if floor is None:
        floor = ("kb_search", "web_search") if frame_requires_retrieval else ()
    planned = tuple(
        runtime_name
        for item in plan.requirements
        if (runtime_name := _PLAN_CAPABILITY_TO_RUNTIME.get(item.capability))
    )
    capabilities = tuple(dict.fromkeys((*floor, *planned)))
    # 取页是检索的延伸，不单独进策略表：授权了 web_search 就授权 web_fetch——
    # web_search 只回 160 字符 snippet，没有取页那条线索到不了可读证据（spec §3.6）。
    # 反向不成立：没有 web_search 的策略（本地盘面 / 技术面）也不该取页。
    if "web_search" in capabilities and "web_fetch" not in capabilities:
        capabilities = (*capabilities, "web_fetch")
    return capabilities


def plan_capabilities_from_receipt(*, tool: str, dataset: str = "") -> frozenset[str]:
    """把一条 typed tool receipt 投影成计划能力 id。

    只做精确查找：工具名、注册 dataset id。禁止对 dataset 做子串启发。
    """

    tool_key = str(tool or "").strip()
    dataset_key = str(dataset or "").strip()
    caps: set[str] = set()
    if tool_key:
        caps.add(tool_key)
        caps.update(_TOOL_RECEIPT_PLAN_CAPABILITIES.get(tool_key, ()))
    if dataset_key:
        caps.update(_DATASET_PLAN_CAPABILITIES.get(dataset_key, ()))
    return frozenset(caps)


def collect_satisfied_plan_capabilities(
    evidence,
    traces=(),
) -> frozenset[str]:
    """桌上有效收据（证据 + trace）并集投影到计划能力。"""

    caps: set[str] = set()
    for item in evidence:
        caps.update(plan_capabilities_from_receipt(tool=getattr(item, "tool", "")))
    for trace in traces:
        caps.update(
            plan_capabilities_from_receipt(
                tool=str(getattr(trace, "capability", "") or ""),
                dataset=str(getattr(trace, "dataset", "") or ""),
            )
        )
    return frozenset(caps)
