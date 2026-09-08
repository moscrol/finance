"""Build one bounded continuous-agent run context from a canonical TaskFrame.

This is a composition seam, not another router. It never reinterprets the
question and never imports private helpers from the legacy orchestrator.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
import re

from intelligence.adapters.knowledge import KnowledgeAdapter
from intelligence.services.evidence_capabilities import (
    EvidencePlan,
    EvidenceRequirement,
    resolve_evidence_plan,
    runtime_capabilities_for_frame,
)
from intelligence.services.mandatory_satisfiability import (
    apply_static_chain_mapping_precheck,
)
from intelligence.services.honesty_gates import requested_information_cutoff
from intelligence.services.research_contract import (
    FORWARD_HYPOTHESIS_OUTPUT_IDS,
    InformationCutoff,
    RequiredOutput,
    ResearchDeadline,
    ResearchPolicy,
    ResearchRunContext,
    ResearchTaskContract,
    root_budget_for_policy,
)
from intelligence.services.research_tool_registry import (
    DEFAULT_RESEARCH_CAPABILITIES,
)
from intelligence.services.task_frame import TaskFrame, task_frame_requires_retrieval


# 盘面类槽位的描述带「写出具体数值」的硬要求。这是 #289（composer 看得见
# 评分表）的引擎 A 版：08-12 A 组冒烟里证据已绑定（3~15 条）仍 0/7，12 条失败
# 全在 fact 层——模型做了定性概括，把证据里的成交额环比、涨停家数、强度状态词
# 全部省掉了（draft 有 1000 字上限，省数字是模型的理性选择）。判卷按数字判，
# 生成侧却没人告诉模型数字必须落在正文——「上层知道的，下层不知道，要显式
# 搬运」。描述经 build_episode_input 进模型输入，不碰指纹锁定的指令文本。
_OUTPUT_DESCRIPTIONS: dict[str, str] = {
    "direct_assessment": "直接回答用户问题并说明判断强度",
    "direct_answer": "直接回答用户问题",
    "direct_definition": "解释用户所问概念",
    "current_baseline": "说明最新可用市场基线与数据日期，关键指标写出具体数值",
    "duration_assessment": "判断反弹可能持续的时间窗口",
    "continuation_conditions": "列出判断继续成立的可核验条件",
    "invalidation_conditions": "列出判断失效或降级的条件",
    "evidence_boundary": "说明证据覆盖范围、数据日期与缺口",
    "technical_levels": "给出结构化行情支持的技术区间或关键位",
    "data_date": "标明行情数据截止日期",
    "valuation_assessment": ("基于当前市场锚点说明估值方法、关键假设与当前估值判断"),
    "financial_business_anchor": "给出至少一项逐季财务或业务兑现硬数据锚点",
    "scenario_range": "给出明确方法与假设边界的估值情景区间",
    "causal_chain": "解释时间对齐的原因、传导链和盘面印证",
    "counterpoint": "提供主要反证或竞争性解释",
    "supporting_evidence": (
        "列出与结论直接相关的支持证据；证据中的关键数值与状态词须原样写进"
        "正文（如成交额及环比、涨停/跌停家数、涨幅、家数、状态标签），"
        "不得只作定性概括"
    ),
    "risk_signals": "列出风险信号与观察条件",
    "market_summary": (
        "概括目标市场窗口的结构化表现，写出成交额及环比、涨停/跌停家数、"
        "指数涨幅等证据中的具体数值"
    ),
    "mainline_structure": (
        "判断当前市场主线及其强弱结构，写出主线题材的涨停家数等证据中的"
        "具体数值"
    ),
    "scenario_paths": "给出条件化情景路径",
    "prior_recall": "复述用户此前对该主体的判断或纠偏原则，并说明与当前的差异",
    "prime_quote": (
        "给出本次问答所依据的最新可用行情要点与数据日期；取不到则在证据边界中写明缺口"
    ),
    "prime_news": "给出与问题相关的最新财经消息要点；未检索到则写明未取得",
    "prime_memory": "复述用户此前对该主体的判断或纠偏原则；台账为空则跳过，不编造",
    "chain_mapping": "产业链层级、角色与关键环节",
    "financial_assessment": "公司财务表现的直接判断",
    "metric_evidence": "支撑财务判断的指标证据",
    "comparison_dimensions": "列出比较维度与各自的观察口径",
    "key_differences": "说明候选之间的关键差异",
    "transmission_chain": "说明情景向结果的传导链",
    "direct_explanation": "解释所问方法或概念的要点",
    "tradeoffs": "列出方法取舍与适用边界",
    "event_facts": "列出事件的可核验事实与时间",
    "impact_transmission": "说明事件向盘面或基本面的传导",
    "fact_value": "给出所问事实的取值",
    "as_of_date": "标明事实对应的数据日期",
    "comparison_conclusion": "给出比较后的主线判断",
    "verification_conditions": "列出可核验的验证条件",
    "method": "给出可执行的判断方法",
    "evidence_hierarchy": "说明证据层级与采用顺序",
    "failure_modes": "列出方法的失败模式",
    "verification_path": "给出后续验证路径",
    "change_summary": "概括相对前次的变化",
    "tracking_signals": "列出后续跟踪信号",
    "claim_summary": "概括被评述观点的主张",
    "evidence_assessment": "评估主张的证据支撑",
    "biases_and_gaps": "指出偏见与证据缺口",
    "analog_similarities": "说明类比对象的相似点",
    "limits_of_analogy": "说明类比的适用边界",
    "conditional_thesis": "给出条件化投资命题",
    "cause_attribution": "给出时间对齐的下跌或上涨归因",
    "scenario_tree": (
        "给出条件化情景树：路径分支 + 同一现象的互斥因果假说"
        "（裁决须带证据编号，裁不了写并立）"
    ),
    "historical_analogs": "列出可对照的历史相似阶段",
    "falsification_conditions": "列出可核验的证伪条件",
    "money_flow": "说明资金流向与结构变化",
    "comparison": "比较候选并给出差异",
    "relation_map": "说明主体之间的关系与传导",
    "company_mapping": (
        "列出观察名单：股票名称 + 六位代码 + 角色（机会 / 出清或风险），"
        "不得只写行业形容词"
    ),
    "market_change": "说明市场相对前一阶段的变化",
    "customer_validation": "给出客户或订单侧的可核验证据",
    "valuation_range": "给出估值区间与方法边界",
    "definition": "解释用户所问概念",
    "rebound_case": "给出反弹或修复情景及成立条件",
    "decline_case": "给出走弱或回落情景及成立条件",
    "invalidation": "列出使当前判断失效的条件",
    "dual_red_snapshot": "给出严格双红快照：日期、个数或名单，取不到则写明缺口",
    "aggregate_count": "给出问句所要的精确计数，并标明口径与日期",
    "detail_rows": "列出问句所要的明细行，标明日期与口径",
    "cross_table_intersection": "给出跨表精确交集，对不上则写明缺口",
    "catalog_preflight": "说明目标表是否存在、站立日是否有行",
    "contradiction_audit": "列出同日跨表冲突；没有冲突则写明无冲突",
    "substitute_observation": (
        "主线题材当日无严格双红匹配时，给出带「出清/分歧观察」标签的替补池"
        "（板块+个股，非机会）；开口预取已带则引用其 E 号，无缺口则写明主线已被双红覆盖"
    ),
    "verification_timepoints": (
        "给出验证时点：核心判断在什么时间窗、看哪个可观察指标即可回验"
        "（如「9 月中报看订单兑现」）；写不出可核验的指标×时点就不绑，不要硬凑"
    ),
    "volume_qualification": (
        "给出大盘量能资格盘：站立日全市场成交额、20 日均额（含当日窗口）与"
        "总量/均额比；开口预取已带则引用其 E 号；资格判语按画像规则解读，"
        "取不到数据则写明缺口"
    ),
    "volume_step_trajectory": (
        "给出题目相关板块的近 5 日量能台阶（逐日涨跌幅/成交额/边际量/双红戳）；"
        "开口预取已带则引用其 E 号；subject 未锚定到板块口径时如实声明，"
        "不得臆配板块"
    ),
}


def _require_output_description(output_id: str) -> str:
    """Fail loud when a required slot has no human description.

    静默 ``.get(output_id, output_id)`` 会把 ``chain_mapping`` 写成裸 id，
    模型看见同义反复、gap 标签也变成英文蛇形。缺键必须在构造契约时失败。
    """

    try:
        return _OUTPUT_DESCRIPTIONS[output_id]
    except KeyError as exc:
        raise ValueError(
            f"missing _OUTPUT_DESCRIPTIONS[{output_id!r}]"
        ) from exc


# 用户在问题里引用了自己过去的看法。这类问题要回答的不是「现在怎么样」，而是
# 「跟我上次说的比，变了什么」——后者需要先取回那份先验。
#
# 为什么要这条判据：`memory_lookup` 授权、注册、召回全部打通后，两次真实 run
# （`221010` 泛问、`221845` 明确点名「先查我自己的历史判断」）里模型**一次都没调它**。
# 原因不是提示词不够明确，而是当时全部 required output 都是 `grounding=evidence`，
# 而该工具的产出按设计标着「不是市场事实、不能当作证据引用」——调回来的东西
# 一格也填不进去。在 4 次工具预算下，不调它才是理性选择。
#
# 所以补的是**槽位**不是措辞：给这份先验一个 `user_premise` 的落点，
# 让「调它」这个动作对完成契约有贡献。
_PRIOR_REFERENCE_RE = re.compile(
    r"(?:我(?:之前|此前|过去|原来|先前|上次|当初)"
    r"|之前(?:我|的)(?:判断|看法|观点|结论)"
    r"|我(?:的)?(?:判断|看法|观点|逻辑)(?:还|是否|对不对|成立)"
    r"|跟我(?:上次|之前)"
    r"|(?:还|是否)(?:成立|站得住|有效))"
)

# 只在这三类问题上注入 prior_recall。判据是「用户点名了自己过去的看法」——
# 与公司深挖 / 题材分析 / 题材跟踪三条策略上的 memory_lookup 授权配对。
# residual 的 general_finance_evidence 现在也授权 memory_lookup，但用的是
# 另一格 prime_memory，不走这条题型闸门。
_PRIOR_RECALL_QUESTION_TYPES = frozenset(
    {"stock_deep_dive", "theme_analysis", "theme_track", "trade_advice"}
)

_VALUATION_REQUIRED_OUTPUTS = (
    "valuation_assessment",
    "financial_business_anchor",
    "scenario_range",
    "evidence_boundary",
    "invalidation_conditions",
)

_PRESENTATION_PROFILES: dict[str, str] = {
    "market_forecast": "market_scenarios",
    "market_cause": "market_causal",
    "market_technical": "market_technical",
    "market_watch": "market_watch",
    "valuation_estimate": "company_valuation",
    "stock_deep_dive": "stock_research",
    "comparison": "comparison",
    "comparison_analog": "comparison",
}

_MODEL_OWNED_READ_CAPABILITIES = ("finance_query", "evidence_search")
_MAX_SYNTHESIS_BUDGET_FRACTION = 2.0 / 3.0
_MARKET_CAUSE_REASONING_OUTPUTS = frozenset(
    {"causal_chain", "cause_attribution"}
)
_OUTLOOK_JUDGMENT_OUTPUTS = frozenset({"direct_answer", "direct_assessment"})
_OUTLOOK_JUDGMENT_RE = re.compile(
    # 「后续走势 / 后市」：theme_analysis「分析下 X 板块后续的走势」此前不入闸，
    # 推翻条件/验证时点整组缺席（2026-08-25 生产契约冻结实测，SPT 有色题）。
    r"(?:你认为|你觉得|怎么看|机会在哪|会怎么走|后续的?走势|后市)"
)
# 只圈前瞻类题型：market_technical 的失效位应来自行情数据（支撑/均线是可查的），
# 继续按 evidence 签约，不进本名单。
_FORWARD_HYPOTHESIS_QUESTION_TYPES = frozenset({"market_forecast", "event_forecast"})


def _authorized_capabilities(
    frame: TaskFrame,
    capabilities: tuple[str, ...] | None,
) -> tuple[str, ...]:
    projected = (
        runtime_capabilities_for_frame(frame)
        if capabilities is None
        else tuple(
            dict.fromkeys(
                str(item).strip() for item in capabilities if str(item).strip()
            )
        )
    )
    projected = tuple(
        dict.fromkeys((*projected, *_MODEL_OWNED_READ_CAPABILITIES))
    )
    allowed_names = set(DEFAULT_RESEARCH_CAPABILITIES)
    unknown = tuple(item for item in projected if item not in allowed_names)
    if unknown:
        raise ValueError("unknown runtime capability: " + ",".join(sorted(unknown)))
    return projected


def _episode_evidence_plan(frame: TaskFrame) -> EvidencePlan:
    plan = resolve_evidence_plan(
        frame.raw_question,
        question_type=frame.question_type,
        freshness="current",
    )
    if frame.question_type == "market_cause":
        kb_extras = tuple(
            item
            for item in plan.requirements
            if item.capability in {"kb_search", "evidence_search"}
        )
        return EvidencePlan(
            profile="time_aligned_market_causal",
            requirements=(
                EvidenceRequirement(
                    "MARKET_CAUSE_WINDOW",
                    "market_data",
                    True,
                    "current",
                    "指定市场窗口的结构化表现",
                ),
                EvidenceRequirement(
                    "MARKET_CAUSE_NEWS",
                    "news_search",
                    True,
                    "current",
                    "与市场窗口时间对齐的原因证据",
                ),
                EvidenceRequirement(
                    "MARKET_CAUSE_WEB",
                    "web_search",
                    False,
                    "current",
                    "明确标注为外部观点的竞争性解释",
                ),
                *kb_extras,
            ),
            freshness="current",
        )
    if frame.question_type != "valuation_estimate":
        return plan
    requirements = tuple(
        item for item in plan.requirements if item.capability != "market_data"
    )
    return EvidencePlan(
        profile="valuation_current_anchor",
        requirements=(
            EvidenceRequirement(
                "VALUATION_MARKET",
                "market_data",
                True,
                "current",
                "当前价格、交易日与可比估值锚点",
            ),
            EvidenceRequirement(
                "VALUATION_FINANCIAL",
                "financial_data",
                True,
                "current",
                "逐季营收、利润或盈利质量硬数据锚点",
            ),
            *requirements,
        ),
        freshness="current",
    )


def _references_prior_judgement(frame: TaskFrame) -> bool:
    """Return whether the user's own wording reaches back to a past judgement."""

    if frame.question_type not in _PRIOR_RECALL_QUESTION_TYPES:
        return False
    if _PRIOR_REFERENCE_RE.search(frame.raw_question):
        return True
    from intelligence.services.stance_pack import detect_stance_kinds

    return bool(detect_stance_kinds(frame.raw_question))


def _required_output_ids(frame: TaskFrame) -> tuple[str, ...]:
    outputs = frame.required_outputs
    if frame.question_type == "valuation_estimate":
        outputs = tuple(dict.fromkeys((*outputs, *_VALUATION_REQUIRED_OUTPUTS)))
    from intelligence.services.research_contract import compile_research_program

    program = compile_research_program(
        frame.raw_question,
        question_class=frame.question_type,
    )
    extras = tuple(slot.slot_id for slot in program.required_fact_slots)
    return tuple(dict.fromkeys((*outputs, *extras)))


def _with_prior_recall(
    output_ids: tuple[str, ...],
    frame: TaskFrame,
    capabilities: tuple[str, ...],
) -> tuple[str, ...]:
    """Add the prior_recall slot only when the tool that fills it is authorized.

    这个判据里的 `memory_lookup in capabilities` 不是防御性冗余。`prior_recall`
    的注入条件只看题型与措辞，而 `memory_lookup` 的授权来自另一条路
    （`evidence_capabilities.py` 的 evidence policy），两者可以不同步：

    - 调用方显式传 `capabilities` 且其中没有 `memory_lookup`；
    - 或 `_is_evidence_free_task` 把 `authorized` 整个清空（反事实题的
      `user_goal` 判据与 `theme_analysis` 题型可以同时成立）。

    这两种情况下若仍注入，`_required_output_evidence_types` 会把这一格的
    evidence_types 算成**空 tuple**：契约里挂着一个谁都填不上的槽位。那正是
    本轮根因的同一种形态——槽位与工具各自为政、错开时不报错，只是静静地
    产出一个填不满的契约。所以把「有工具」变成注入的前置条件。
    """

    if not _references_prior_judgement(frame):
        return output_ids
    if "memory_lookup" not in capabilities:
        return output_ids
    return tuple(dict.fromkeys((*output_ids, "prior_recall")))


_RESIDUAL_PRIME_SLOTS: tuple[tuple[str, str], ...] = (
    ("market_data", "prime_quote"),
    ("news_search", "prime_news"),
    ("memory_lookup", "prime_memory"),
)

# 契约里存在但缺了不判失败的槽位：装配层加的检索引导（prime_*）与用户先验
# 召回（prior_recall）。它们的作用是让「调对应工具」对完成契约有贡献，
# 不是用户点名要的产出，所以缺口降级为 gap 行，不进 missing_outputs。
_ADVISORY_OUTPUT_IDS = frozenset(
    {
        "prior_recall",
        "prime_memory",
        "prime_quote",
        "prime_news",
        "dual_red_snapshot",
        "aggregate_count",
        "detail_rows",
        "cross_table_intersection",
        "catalog_preflight",
        "contradiction_audit",
        "substitute_observation",
        "volume_qualification",
        "volume_step_trajectory",
    }
)


def _with_residual_prime(
    output_ids: tuple[str, ...],
    frame: TaskFrame,
    capabilities: tuple[str, ...],
) -> tuple[str, ...]:
    """Add Knevo-shaped retrieval slots only when the matching tool is authorized.

    残差题没有子 skill 菜单。只扩大 allowed_capabilities、不给契约槽，模型从
    契约里读不出「哪一格只能由行情/新闻/先验填」——`prior_recall` 已经证伪过
    「全量 evidence_types + 提示词要求优先调用」。各槽独立注入：授权里没有
    对应工具就不挂那一格，避免有格子没工具。

    禁止把这些 id 写进 task_frame 默认产出：超出
    {direct_answer, evidence_boundary} 会被当成研究信号，把笑话拖进检索。
    """

    if frame.question_type != "general_finance_qa":
        return output_ids
    if not task_frame_requires_retrieval(frame):
        return output_ids
    extras = tuple(
        slot_id
        for capability, slot_id in _RESIDUAL_PRIME_SLOTS
        if capability in capabilities
    )
    if not extras:
        return output_ids
    return tuple(dict.fromkeys((*output_ids, *extras)))


def _required_output_evidence_types(
    output_id: str,
    capabilities: tuple[str, ...],
) -> tuple[str, ...]:
    if output_id in {"prior_recall", "prime_memory"}:
        # 这一格只有 memory_lookup 的产出能填：它装的是用户自己的历史判断，
        # 市场侧工具（kb_search / graph_lookup / news_search ...）返回的都是
        # 当前世界事实，格式与 grounding_mode=user_premise 不兼容。
        #
        # 为什么收窄而不是加强提示词：上一轮决证（run_20260808_102708）里
        # prior_recall 槽位、memory_lookup 授权、"必须优先调用"的提示词三样
        # 都在，模型仍在第一轮把 7 次工具预算全投给市场侧检索。原因是这格的
        # evidence_types 是全量能力列表——模型从契约里读不出"哪个工具能填它"，
        # 而其余三格都是 evidence，市场侧工具对它们的贡献是确定的。
        #
        # 收窄后契约自身就携带了工具→槽位的映射，模型靠自主推理即可选中
        # memory_lookup，不需要任何强制调用顺序。这保住了 agentic RAG：
        # 其余槽位的 evidence_types 不变，市场侧工具照常参与竞争。
        return tuple(
            capability for capability in ("memory_lookup",)
            if capability in capabilities
        )
    if output_id == "prime_quote":
        return tuple(
            capability for capability in ("market_data",)
            if capability in capabilities
        )
    if output_id == "prime_news":
        return tuple(
            capability for capability in ("news_search",)
            if capability in capabilities
        )
    if output_id == "financial_business_anchor":
        return tuple(
            capability
            for capability in (
                "financial_data",
                "l3_lookup",
                "evidence_lookup",
                "kb_search",
            )
            if capability in capabilities
        )
    if output_id in {
        "dual_red_snapshot",
        "aggregate_count",
        "detail_rows",
        "cross_table_intersection",
        "catalog_preflight",
        "contradiction_audit",
        "substitute_observation",
        "volume_qualification",
        "volume_step_trajectory",
    }:
        return tuple(
            capability
            for capability in ("market_data", "finance_query")
            if capability in capabilities
        )
    return capabilities


def _grounding_mode(frame: TaskFrame, output_id: str) -> str:
    """Project question semantics into the output grounding contract."""

    if output_id in {"prior_recall", "prime_memory"}:
        # 这一格装的是用户自己的历史判断，按定义不是当前世界事实，所以既不能
        # 要求它有市场证据支撑，也不能让它被当成证据去支撑别的结论。语义裁判
        # 已有对应契约：user_premise 题「用户明确给出的前提视为真的假设，不能
        # 要求先证明前提」——正是这份先验需要的待遇。
        return "user_premise"
    if frame.question_type == "methodology_discussion" or "method" in frame.required_outputs:
        return "model_reasoning"
    if frame.user_goal.startswith("判断反事实条件"):
        return "user_premise"
    if (
        frame.question_type == "market_cause"
        and output_id in _MARKET_CAUSE_REASONING_OUTPUTS
    ):
        return "model_reasoning"
    if (
        output_id in _OUTLOOK_JUDGMENT_OUTPUTS
        and _OUTLOOK_JUDGMENT_RE.search(frame.raw_question)
    ):
        # 观点/前瞻题的判断正文不是盘面原文。押进 evidence 硬边界后，semantic
        # 修复会按句删光「你认为/机会在哪」这类条件化判断，公开答案只剩边界句
        # 却仍 completed（2026-08-16 两轮生产 run）。只改判断槽：边界槽继续
        # evidence，整题也不标 evidence-free，检索与硬事实闸门保持。
        # 不能用 user_goal==「形成条件化判断」当键——那是默认 decision_goal。
        return "model_reasoning"
    if (
        output_id in FORWARD_HYPOTHESIS_OUTPUT_IDS
        and frame.question_type in _FORWARD_HYPOTHESIS_QUESTION_TYPES
    ):
        # 前瞻题的条件槽是向前的假设。押进 evidence 硬边界后，数值门禁把
        # 「若指数跌破3870点则失效」这类可操作阈值整句砍掉，模型学会只输出
        # 「相对变化描述，具体阈值以盘面为准」自保（2026-08-19 生产 run +
        # 分层审查实锤）。只改条件槽：direct_assessment / evidence_boundary
        # 等事实、边界槽继续 evidence，检索与硬事实闸门不动。
        return "model_reasoning"
    return "evidence"


def _is_evidence_free_task(frame: TaskFrame) -> bool:
    return (
        frame.question_type == "methodology_discussion"
        or "method" in frame.required_outputs
        or frame.user_goal.startswith("判断反事实条件")
    )


def _with_forward_hypothesis_slots(
    output_ids: tuple[str, ...],
    frame: TaskFrame,
) -> tuple[tuple[str, ...], frozenset[str]]:
    """前瞻信号题挂**可选**前瞻槽。返回（追加后的 ids, 本次追加的 id 集合）。

    「你怎么看明天」「后市会怎么走」经常落在 general_finance_qa / market_watch /
    stock_deep_dive——这些题的槽表里没有任何前瞻槽，于是模型写出的条件阈值
    （「若指数跌破3870点则转弱」）没有槽可绑，数值门按「证据里没有的数量」整句
    砍掉，模型转而输出「具体阈值以盘面为准」自保（2026-08-19 生产 run 实锤）。
    2026-08-19 那轮的修法是题型闸门 `_FORWARD_HYPOTHESIS_QUESTION_TYPES`，只覆盖
    market_forecast / event_forecast；本函数补的是**其余题型带前瞻信号**那一片。

    三条判据，缺一不挂：

    1. 问句命中 `_OUTLOOK_JUDGMENT_RE`——复用 #72 已生产验证的信号，不造第二张
       必漂的前瞻词表。**注意与 `_grounding_mode` 里 #72 那处的作用面差异**：那里
       是 `output_id in _OUTLOOK_JUDGMENT_OUTPUTS and 正则`，本函数只看正则，所以
       契约里没有判断槽的题也会被挂。这是有意的——「有没有 direct_answer 槽」与
       「这题是不是问前瞻」没有因果关系，用它当门是借来的判据。若 live 显示误触
       发噪声集中在无判断槽的题上，收窄时第一个该加的就是这个门。
    2. 契约里还没有任何前瞻槽（交集为空）。必须对**定稿后**的 output_ids 判断，
       否则看不见 valuation_estimate 在 `_required_output_ids` 里追加的
       invalidation_conditions，会对估值题重复挂槽。
    3. 不是 evidence-free 题。方法论 / 反事实题全契约非 evidence，数值门的整体
       豁免已经覆盖，挂槽纯属污染契约。

    挂上的槽是 `required=False`：**不写情景分析不算失败**，写了阈值有合法身份。
    可选性由返回的集合携带，不进 `_ADVISORY_OUTPUT_IDS`——那是全局降级，会把
    market_forecast 的**必选**前瞻槽也一起降掉。
    """

    if not _OUTLOOK_JUDGMENT_RE.search(frame.raw_question):
        return output_ids, frozenset()
    if _is_evidence_free_task(frame):
        return output_ids, frozenset()
    if set(output_ids) & FORWARD_HYPOTHESIS_OUTPUT_IDS:
        return output_ids, frozenset()
    # sorted() 而不是直接迭代 frozenset：字符串哈希默认随机化，直接迭代会让契约
    # 里的槽序逐进程漂动，同一问句两次跑出的契约不可比。排序是就地求得的确定序，
    # 不是第二张词表——槽 id 的真本源仍是 FORWARD_HYPOTHESIS_OUTPUT_IDS。
    mounted = tuple(sorted(FORWARD_HYPOTHESIS_OUTPUT_IDS))
    return tuple(dict.fromkeys((*output_ids, *mounted))), frozenset(mounted)


def build_episode_context(
    frame: TaskFrame,
    *,
    task_id: str,
    capabilities: tuple[str, ...] | None = None,
    tier: str = "standard",
    timeout: float | None = None,
    synthesis_reserve: float | None = None,
    trace_parent_id: str | None = None,
    today: str | None = None,
    latest_data_date: str | None = None,
    conversation_context: str = "",
    information_cutoff: InformationCutoff | None = None,
    perspective_context: str = "",
    knowledge: KnowledgeAdapter | None = None,
    stance_pack: object | None = None,
    retrieval_stages: tuple[str, ...] = (),
) -> ResearchRunContext:
    """Freeze control output into one immutable research run contract."""

    output_ids = _required_output_ids(frame)
    grounding_modes = tuple(
        _grounding_mode(frame, output_id) for output_id in output_ids
    )
    evidence_plan = _episode_evidence_plan(frame)
    authorized = list(_authorized_capabilities(frame, capabilities))
    if _is_evidence_free_task(frame):
        # These contracts ask the model to reason over a method or an explicit
        # user-supplied premise.  Retrieving current-world evidence adds cost
        # and can contaminate the hypothetical without strengthening it.
        evidence_plan = EvidencePlan(
            profile=grounding_modes[0],
            requirements=(),
            freshness="stable",
        )
        authorized = []
    known = set(DEFAULT_RESEARCH_CAPABILITIES)
    for capability in evidence_plan.mandatory_capabilities:
        if capability not in known:
            raise ValueError(f"unknown runtime capability: {capability}")
        if capability not in authorized:
            authorized.append(capability)
    capability_tuple = tuple(authorized)

    # 必须在 capability_tuple 定稿之后：`_with_prior_recall` 的前置条件是
    # 「memory_lookup 真的在这次的授权里」，而授权到这一行才算最终确定
    # （evidence_plan 的 mandatory_capabilities 会往里追加，
    # `_is_evidence_free_task` 会把它整个清空）。放在前面判断就会读到中间态。
    output_ids = _with_prior_recall(output_ids, frame, capability_tuple)
    output_ids = _with_residual_prime(output_ids, frame, capability_tuple)
    # 挂在最后：交集判据要看**定稿后**的 output_ids（含 valuation_estimate 在
    # `_required_output_ids` 里追加的 invalidation_conditions），否则会重复挂槽。
    output_ids, forward_slots = _with_forward_hypothesis_slots(output_ids, frame)

    base_policy = ResearchPolicy.for_tier(tier)
    effective_timeout = base_policy.total_seconds
    if timeout is not None:
        effective_timeout = min(
            base_policy.total_seconds,
            max(0.0, float(timeout)),
        )
    requested_reserve = (
        base_policy.synthesis_reserve
        if synthesis_reserve is None
        else max(0.0, float(synthesis_reserve))
    )
    reserve = min(
        requested_reserve,
        effective_timeout * _MAX_SYNTHESIS_BUDGET_FRACTION,
    )
    policy = ResearchPolicy(
        base_policy.tier,
        base_policy.max_steps,
        base_policy.total_seconds,
        reserve,
    )

    contract = ResearchTaskContract(
        task_id=task_id,
        question=frame.raw_question,
        subject=frame.subject,
        subject_kind=frame.subject_kind,
        question_type=frame.question_type,
        required_outputs=tuple(
            RequiredOutput(
                output_id=output_id,
                description=_require_output_description(output_id),
                # 前瞻信号挂上的槽 evidence_types 必须是**空**：这几格由推理
                # 填、没有任何工具能填。`_required_output_evidence_types` 对不
                # 认识的 output_id 会回全量能力列表，那正是 prior_recall 踩过
                # 的坑（run_20260808_102708：模型读不出哪个工具对应这一格，
                # 干脆把工具预算全投给别处）。model_reasoning 槽挂一串工具名
                # 比挂空更糟——它在暗示这格该去检索。
                evidence_types=(
                    ()
                    if output_id in forward_slots
                    else _required_output_evidence_types(
                        output_id,
                        capability_tuple,
                    )
                ),
                # prior_recall 是**可选**槽位，这一点是设计核心而不是保守：
                # 生产 users 根下 24 个用户的 judgments/corrections 全为空，
                # 台账为空时 memory_lookup 正确地返回零命中，这一格绑不上。
                # 若设 required=True，`completed` 检查（episode_protocol:318）
                # 会因为它缺 binding 而把每一道题材问答都压成 partial——
                # 那是给所有老用户引入回归，只为了接一个新工具。
                #
                # required=False 下它仍然完整存在于契约与提示词里，模型看得见、
                # 可以绑、绑了会被校验（basis 必须是 user_premise）；只是没有
                # 先验可取时不判失败。
                #
                # prime_quote / prime_news 同理改为可选（2026-08-19）：这两格
                # 是装配层替 controller 加的检索引导，不是用户点名的产出。
                # 描述文本本来就写着「取不到则写明缺口」——设计意图是 caveat
                # 而非硬门。required=True 的实际后果是 run_20260819_130854：
                # 混绑一条 finance_query 就整篇换成「现有证据不足」。可选后
                # 槽位仍在契约里引导模型调 market_data / news_search，缺了
                # 只降为 gap，不再单独打死整篇。
                #
                # 前瞻信号挂上的三槽（`forward_slots`）同样可选，但走的是**本次
                # 挂槽**这个事实，不是 `_ADVISORY_OUTPUT_IDS`：那个集合是全局的，
                # 把三个 id 加进去会连 market_forecast 的必选前瞻槽一起降级。
                required=(
                    output_id not in _ADVISORY_OUTPUT_IDS
                    and output_id not in forward_slots
                ),
                # 同理直接给 model_reasoning，不进 `_grounding_mode`——那个函数
                # 按题型/问句判签法，让它再去感知「这个槽是不是本次挂上来的」
                # 会把两件事揉进一个判据。
                grounding_mode=(
                    "model_reasoning"
                    if output_id in forward_slots
                    else _grounding_mode(frame, output_id)
                ),
            )
            for output_id in output_ids
        ),
        allowed_capabilities=capability_tuple,
        research_tier=policy.tier,
        presentation_profile=_PRESENTATION_PROFILES.get(
            frame.question_type,
            "general",
        ),
        freshness="current",
        timeframe=frame.timeframe,
        evidence_plan=evidence_plan,
        task_frame_hash=frame.task_frame_hash,
    )
    if frame.history_intent is not None and "finance_query" in capability_tuple:
        # Capability authorizes execution; evidence_types admits the actual
        # producer names. Keep historical provenance and narrow output contracts
        # (for example memory/news/financial anchors) intact.
        contract = replace(
            contract,
            required_outputs=tuple(
                replace(
                    output,
                    evidence_types=tuple(
                        dict.fromkeys(
                            (*output.evidence_types, "history_query", "read_history_result")
                        )
                    ),
                )
                if "finance_query" in output.evidence_types
                else output
                for output in contract.required_outputs
            ),
        )
    contract = apply_static_chain_mapping_precheck(contract, knowledge=knowledge)
    cutoff = (
        information_cutoff
        or requested_information_cutoff(frame.raw_question, today=today)
        or _default_information_cutoff(
            today=today,
            latest_data_date=latest_data_date,
        )
    )
    if frame.history_intent is not None and frame.history_intent.strict_window and frame.history_intent.requested_end:
        cutoff = InformationCutoff(
            min(cutoff.as_of_date, date.fromisoformat(frame.history_intent.requested_end)),
            "requested",
        )
    return ResearchRunContext(
        contract=contract,
        deadline=ResearchDeadline.from_timeout(
            effective_timeout,
            synthesis_reserve=reserve,
        ),
        policy=policy,
        trace_parent_id=trace_parent_id or task_id,
        today=today,
        latest_data_date=latest_data_date,
        conversation_context=str(conversation_context or "").strip(),
        information_cutoff=cutoff,
        root_budget=root_budget_for_policy(policy, episode_id=task_id),
        perspective_context=str(perspective_context or "").strip(),
        stance_pack=stance_pack,
        retrieval_stages=tuple(retrieval_stages or ()),
        history_intent=frame.history_intent,
    )


def _default_information_cutoff(
    *,
    today: str | None,
    latest_data_date: str | None,
) -> InformationCutoff:
    # Market snapshot freshness is provider metadata, not the upper bound on
    # news or other information available to the user.
    del latest_data_date
    try:
        runtime_date = date.fromisoformat(str(today or "")[:10])
    except ValueError:
        return InformationCutoff.runtime_default()
    return InformationCutoff(runtime_date, "runtime_default")


__all__ = ["build_episode_context"]
