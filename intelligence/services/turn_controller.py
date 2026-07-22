from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace
from typing import Literal, TypeAlias, cast

from intelligence.services import ask_clarify, llm_refine
from intelligence.services.query_resolution import QueryResolution, QueryResolver
from intelligence.services.query_understanding import (
    QueryEnvelope,
    envelope_from_task_frame,
    is_dated_market_review,
    is_market_watch_query,
    project_task_frame,
)
from intelligence.services.evidence_capabilities import is_current_market_query
from intelligence.services.route_table import (
    ROUTE_TABLE,
    RouteRow,
    render_route_table_prompt,
    route_by_id,
)
from intelligence.services.research_contract import (
    TurnIntent,
    answer_owner_for_question_type,
    build_turn_intent,
    contextualize_intent_query,
    is_contextual_follow_up,
)
from intelligence.services.task_frame import (
    TaskFrame,
    align_task_frame,
    build_task_frame,
    rebase_task_frame,
    resolve_task_frame_clarification,
    task_frame_requires_retrieval,
)

TurnLane: TypeAlias = Literal[
    "chat",
    "meta",
    "knowledge",
    "research",
    "workflow",
    "clarify",
]
LLMComplete: TypeAlias = Callable[
    [list[dict[str, str]]], tuple[str | None, object | None, str]
]

_CAPABILITIES = frozenset(
    {
        "memory",
        "market_quote",
        "market_news",
        "web_search",
        "web_fetch",
        "graph",
        "filings",
        "financials",
    }
)
_GREETING_PATTERN = re.compile(
    r"^[\s，。！？,.!?]*(你好|您好|嗨|hello|hi|早上好|下午好|晚上好)"
    r"[\s，。！？,.!?]*$",
    re.IGNORECASE,
)
_META_PATTERN = re.compile(
    r"(你是谁|你是什么模型|什么模型|你的模型|系统提示|能做什么|model)",
    re.IGNORECASE,
)
_FINANCE_PATTERN = re.compile(
    r"(股票|公司|个股|题材|板块|估值|财报|研报|公告|市场|指数|行情|"
    r"涨跌|收盘|复盘|成交|涨停|跌停|资金|持仓|目标价|产业链|"
    r"上涨空间|后续空间|还能涨|收入|利润|毛利率|净利率|双红|回撤榜)"
)
_WORKFLOW_PATTERN = re.compile(
    r"(今日复盘|每日复盘|生成报告|生成日报|执行工作流|运行工作流|"
    r"导出报告|按模板输出|跑一遍|"
    r"美股\s*AI\s*回撤|美股回撤榜|AI\s*阵营回撤|"
    r"最大回撤排序)",
    re.IGNORECASE,
)
_DAILY_RESEARCH_WORKFLOW_PATTERN = re.compile(
    r"^\s*(?:(?:第[一二三四五六七八九十0-9]+轮)\s*)?"
    r"(?:(?:请|帮我|给我|麻烦)?\s*"
    r"(?:看|看看|看一下|请看|打开|运行|执行)?\s*)?"
    r"(?:研究雷达|研究队列|今天研究什么|daily[-_ ]?agent)"
    r"(?P<suffix>[\s\S]*)$",
    re.IGNORECASE,
)
_DAILY_RESEARCH_OUTPUT_REQUEST_PATTERN = re.compile(
    r"^(?:请|按|列|输出|给(?:我|出)?|展示|生成|整理|汇总|包括|包含|"
    r"并|同时|重点|需要|要求|覆盖|先|再|从|把|用|以|分|附|说明|标注)",
    re.IGNORECASE,
)
_DAILY_RESEARCH_EXPLANATION_PATTERN = re.compile(
    r"(?:和|与).{0,24}(?:区别|差异|不同)|有什么区别|是什么意思|"
    r"是(?:什么|否)|为什么|为何|怎么定义|如何定义",
    re.IGNORECASE,
)
_FRESHNESS_PATTERN = re.compile(
    r"(今天|今日|昨天|昨日|隔夜|最近|近期|最新|刚刚|本周|本月|"
    r"消息|新闻|进展|动态|现状)"
)
_MEMORY_PATTERN = re.compile(
    r"(我的知识库|根据我(?:之前|过去)|我们之前|上次|前面提到|历史判断|"
    r"已有框架|长期记忆)"
)
_BROAD_MARKET_PATTERN = re.compile(
    r"^(?:请|帮我)?(?:看一下|看看|分析一下)?"
    r"(?:今天|今日|现在|最近)?(?:的)?市场(?:怎么样|如何|什么情况|表现如何)[？?。！!\s]*$"
)
_VERIFIED_SUBJECT_MATCHES = frozenset(
    {"ticker", "entity", "candidate", "alias", "quoted"}
)
_KNOWLEDGE_QUESTION_PATTERN = re.compile(
    r"(是什么|什么是|为什么|原理|如何工作|怎么理解|什么意思|区别|"
    r"介绍一下|解释一下)"
)


@dataclass(frozen=True)
class TurnDecision:
    lane: TurnLane
    needs_retrieval: bool
    needs_memory: bool
    needs_template: bool
    question_type: str | None = None
    subject: str | None = None
    timeframe: str | None = None
    confidence: float = 1.0
    reason: str = ""
    capabilities: tuple[str, ...] = ()
    clarification_questions: tuple[str, ...] = ()
    turn_intent: TurnIntent | None = None
    task_frame: TaskFrame | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        if self.task_frame is not None:
            payload["task_frame"] = self.task_frame.to_dict()
            payload["task_frame_hash"] = self.task_frame.task_frame_hash
        return payload


def _decision(
    lane: TurnLane,
    *,
    envelope: QueryEnvelope | None = None,
    needs_retrieval: bool | None = None,
    needs_memory: bool = False,
    needs_template: bool | None = None,
    confidence: float = 1.0,
    reason: str,
    capabilities: Sequence[str] = (),
    clarification_questions: Sequence[str] = (),
) -> TurnDecision:
    retrieval = (
        lane in {"research", "workflow"} if needs_retrieval is None else needs_retrieval
    )
    template = (
        lane in {"research", "workflow"} if needs_template is None else needs_template
    )
    return TurnDecision(
        lane=lane,
        needs_retrieval=retrieval,
        needs_memory=needs_memory,
        needs_template=template,
        question_type=envelope.question_type if envelope is not None else None,
        subject=envelope.subject if envelope is not None else None,
        timeframe=envelope.timeframe if envelope is not None else None,
        confidence=max(0.0, min(1.0, confidence)),
        reason=reason,
        capabilities=tuple(
            capability
            for capability in dict.fromkeys(capabilities)
            if capability in _CAPABILITIES
        ),
        clarification_questions=tuple(clarification_questions),
    )


def _route_capabilities(
    question_type: str | None,
    fallback: Sequence[str],
) -> tuple[str, ...]:
    """能力集单一事实源（P0 修复）：确定性分支按 question_type 反查路由表行。

    此前规则分支手工复制能力清单，与 route_table 漂移——同一意图因"规则命中
    还是 LLM 命中"获得不同工具权限（如 news_impact 表内要求 market_news+
    web_search，规则分支却统一给 market_quote+financials）。"""
    if question_type:
        for row in ROUTE_TABLE:
            if row.question_type == question_type:
                return row.capabilities
    return tuple(fallback)


def _is_daily_research_workflow_query(query: str) -> bool:
    """识别显式 Daily 命令，同时排除仅提及命令名称的解释/比较问题。

    Daily 是产品工作流入口，允许用户在命令后追加“按优先级列……”等输出
    参数；但“今天研究什么和普通研究有什么区别”只是知识问题，不应夺走
    GenericResearchOwner。命令锚点与后缀语义分开判断，比宽泛 substring 或
    过窄 fullmatch 都更稳定。
    """

    match = _DAILY_RESEARCH_WORKFLOW_PATTERN.fullmatch(query)
    if match is None:
        return False
    suffix = (match.group("suffix") or "").strip()
    if not suffix:
        return True
    if _DAILY_RESEARCH_EXPLANATION_PATTERN.search(suffix):
        return False
    tail = suffix.lstrip("\t \r\n，,：:；;。.!！?？、").strip()
    if not tail:
        return True
    return bool(_DAILY_RESEARCH_OUTPUT_REQUEST_PATTERN.match(tail))


def _canonicalize_head_resolution(
    query: str,
    resolution: QueryResolution,
) -> QueryResolution:
    """让确定性头部意图在构造 TurnIntent 前成为完整控制契约。

    知识库主题解析是宽召回：用户要求里的“验证信号”也可能命中“信号系统”
    之类的题材别名。market-watch 已由可回归规则确定后，不能只锁 lane 而让
    软解析继续提供 subject / answer_owner，否则会同时启动 daily 与 theme
    两条工作流。
    """
    is_daily_research_workflow = _is_daily_research_workflow_query(query)
    if not is_market_watch_query(query) and not is_daily_research_workflow:
        return resolution
    row = route_by_id("market_watch")
    if row is None or row.question_type is None:
        return resolution
    envelope = replace(
        resolution.envelope,
        question_type=row.question_type,
        subject_kind="market_pattern",
        subject=None,
        decision_goal="总结当日盘面主线、观察清单与验证信号",
        matched_by=(
            "daily_workflow_anchor"
            if is_daily_research_workflow
            else "market_anchor"
        ),
        confidence=max(0.98, resolution.envelope.confidence),
        research_mode="general",
    )
    return replace(resolution, envelope=envelope)


def _deterministic_decision(
    query: str,
    *,
    envelope: QueryEnvelope,
    skill_mode: str,
    selected_skill_ids: Sequence[str],
) -> TurnDecision | None:
    cleaned = query.strip()
    clarification = ask_clarify.clarify_for_query(cleaned)
    if clarification.needs_clarification:
        return _decision(
            "clarify",
            confidence=1.0,
            reason=clarification.reason,
            clarification_questions=clarification.questions,
        )
    if selected_skill_ids or skill_mode == "manual":
        return _decision(
            "workflow",
            envelope=envelope,
            needs_memory=True,
            confidence=1.0,
            reason="用户显式选择了工作流能力",
            capabilities=("memory",),
        )
    if _GREETING_PATTERN.fullmatch(cleaned):
        return _decision("chat", confidence=1.0, reason="明确寒暄")
    if (
        len(cleaned) <= 64
        and _META_PATTERN.search(cleaned)
        and not _FINANCE_PATTERN.search(cleaned)
    ):
        return _decision("meta", confidence=0.99, reason="明确系统或模型元问题")
    if _BROAD_MARKET_PATTERN.fullmatch(cleaned):
        if is_market_watch_query(cleaned):
            return _decision(
                "workflow",
                envelope=envelope,
                needs_memory=True,
                confidence=0.95,
                reason="金融工作台默认将当日市场概览解释为 A 股盘面关注点",
                capabilities=("memory", "market_quote", "graph"),
            )
        return _decision(
            "clarify",
            confidence=0.95,
            reason="市场范围不明确",
            clarification_questions=(
                "你想看 A 股、美股，还是全球市场？",
                "要看收盘表现、盘中行情，还是市场结构与主线？",
            ),
        )
    if is_dated_market_review(cleaned, envelope):
        return _decision(
            "workflow",
            envelope=envelope,
            needs_memory=True,
            confidence=0.98,
            reason="明确请求指定日期的 A 股行情复盘",
            capabilities=("memory", "market_quote", "graph"),
        )
    if is_market_watch_query(cleaned):
        return _decision(
            "workflow",
            envelope=envelope,
            needs_memory=True,
            confidence=0.95,
            reason="明确请求当日盘面关注点",
            capabilities=("memory", "market_quote", "graph"),
        )
    if _is_daily_research_workflow_query(cleaned):
        return _decision(
            "workflow",
            envelope=envelope,
            needs_memory=True,
            confidence=0.98,
            reason="明确请求 Daily Agent 研究工作流",
            capabilities=("memory", "market_quote", "graph"),
        )
    if _WORKFLOW_PATTERN.search(cleaned):
        return _decision(
            "workflow",
            envelope=envelope,
            needs_memory=True,
            confidence=0.95,
            reason="明确请求固定研究工作流",
            capabilities=("memory", "market_quote", "graph"),
        )
    if envelope.question_type == "market_technical":
        return _decision(
            "research",
            envelope=envelope,
            needs_template=False,
            confidence=envelope.confidence,
            reason="确定性识别指数/个股技术位问题（支撑/压力/均线/突破位）",
            capabilities=_route_capabilities(
                "market_technical",
                ("market_quote",),
            ),
        )
    if envelope.question_type == "market_cause":
        return _decision(
            "research",
            envelope=envelope,
            needs_template=False,
            confidence=envelope.confidence,
            reason="确定性识别市场时间窗口与涨跌原因归因问题，交给通用研究 Owner 闭环",
            capabilities=_route_capabilities(
                "market_cause",
                ("market_quote", "market_news", "web_search"),
            ),
        )
    if envelope.question_type in {"market_forecast", "event_forecast", "comparison"}:
        # 这些是研究问题而不是知识解释；即使没有明确主体，也必须进入
        # GenericResearchOwner，不能因“未知对象”落到 chat/knowledge fallback。
        return _decision(
            "research",
            envelope=envelope,
            needs_retrieval=True,
            needs_memory=bool(_MEMORY_PATTERN.search(cleaned)),
            needs_template=True,
            confidence=envelope.confidence,
            reason="确定性识别到无专项 owner 的情景/比较研究问题，交给通用研究闭环",
            capabilities=_route_capabilities(
                envelope.question_type,
                ("memory", "market_quote", "market_news", "web_search", "graph"),
            ),
        )
    if envelope.question_type == "external_market":
        return _decision(
            "research",
            envelope=envelope,
            confidence=envelope.confidence,
            reason="明确海外市场行情请求",
            capabilities=_route_capabilities(
                "external_market",
                ("market_quote", "market_news", "web_search"),
            ),
        )
    if envelope.question_type == "concept_definition":
        if is_current_market_query(cleaned):
            return _decision(
                "research",
                envelope=envelope,
                needs_retrieval=True,
                needs_memory=bool(_MEMORY_PATTERN.search(cleaned)),
                needs_template=True,
                confidence=envelope.confidence,
                reason="概念解释同时包含当前市场事实，交给通用研究闭环合并定义与数据",
                capabilities=("market_quote", "graph", "web_search"),
            )
        return _decision(
            "knowledge",
            envelope=envelope,
            needs_retrieval=False,
            needs_memory=bool(_MEMORY_PATTERN.search(cleaned)),
            confidence=envelope.confidence,
            reason="稳定概念解释不需要默认进入金融研究",
            capabilities=("memory",) if _MEMORY_PATTERN.search(cleaned) else (),
        )
    if envelope.question_type == "methodology_discussion":
        return _decision(
            "knowledge",
            envelope=envelope,
            needs_retrieval=False,
            needs_memory=bool(_MEMORY_PATTERN.search(cleaned)),
            needs_template=False,
            confidence=envelope.confidence,
            reason="系统/Agent 方法论问题使用模型原生推理，不进入金融 RAG",
            capabilities=("memory",) if _MEMORY_PATTERN.search(cleaned) else (),
        )
    owner = answer_owner_for_question_type(envelope.question_type)
    if owner is not None and (
        envelope.matched_by in _VERIFIED_SUBJECT_MATCHES
        or (
            envelope.question_type == "news_impact"
            and envelope.subject_kind == "theme"
        )
    ):
        return _decision(
            "research",
            envelope=envelope,
            needs_memory=bool(_MEMORY_PATTERN.search(cleaned)),
            confidence=max(0.75, envelope.confidence),
            reason=f"确定性识别到研究 owner 问题类型（{owner}）",
            capabilities=_route_capabilities(
                envelope.question_type,
                ("memory", "market_quote", "graph", "financials"),
            ),
        )
    if _FRESHNESS_PATTERN.search(cleaned):
        lane: TurnLane = "research" if _FINANCE_PATTERN.search(cleaned) else "knowledge"
        return _decision(
            lane,
            envelope=envelope,
            needs_retrieval=True,
            needs_memory=bool(_MEMORY_PATTERN.search(cleaned)),
            needs_template=lane == "research",
            confidence=max(0.78, envelope.confidence),
            reason="问题包含时效性事实，需要检索核验",
            capabilities=("web_search", "web_fetch", "market_news"),
        )
    if (
        envelope.subject_kind != "unknown" and envelope.confidence >= 0.7
    ) or _FINANCE_PATTERN.search(cleaned):
        return _decision(
            "research",
            envelope=envelope,
            needs_memory=bool(_MEMORY_PATTERN.search(cleaned)),
            confidence=max(0.75, envelope.confidence),
            reason="明确金融研究对象或决策目标",
            capabilities=_route_capabilities(
                envelope.question_type,
                ("memory", "market_quote", "graph", "financials"),
            ),
        )
    return None


_MARKET_FLOOR_PATTERN = re.compile(r"(大盘|A股|美股|港股|股市|盘面)")


def _needs_retrieval_floor(query: str, envelope: QueryEnvelope) -> bool:
    """检索硬触发下限：命中已验证标的、时效词或金融信号时，不得零检索作答。"""
    if (
        envelope.subject_kind != "unknown"
        and envelope.matched_by in _VERIFIED_SUBJECT_MATCHES
    ):
        return True
    return bool(
        _FRESHNESS_PATTERN.search(query)
        or _FINANCE_PATTERN.search(query)
        or _MARKET_FLOOR_PATTERN.search(query)
    )


def _controller_messages(
    query: str,
    context: str,
    task_frame: TaskFrame,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是对话 Turn Controller，只做意图识别，不回答用户问题，也不调用工具。"
                "下面是唯一合法的路由表，你必须从中选择最匹配的一行：\n"
                + render_route_table_prompt()
                + "\n规则：不要因为工作台是金融产品就把普通问题往研究类路由；"
                "拿不准时选 clarify；不得发明表外的 route_id。"
                "TaskFrame 已锁定主体、市场、时间和任务类型，lane 不得覆盖这些语义。"
                "严格输出一个 JSON 对象，键必须且只能是：route_id,confidence,reason,"
                "user_goal,required_outputs,assumptions,ambiguities。后四项只能补充"
                "TaskFrame，不得返回或修改主体、市场、时间、证据政策。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "query": query,
                    "minimal_conversation_context": context,
                    "task_frame": task_frame.to_dict(),
                },
                ensure_ascii=False,
            ),
        },
    ]


def _parse_llm_decision(
    content: str,
    *,
    query: str,
    envelope: QueryEnvelope,
) -> TurnDecision | None:
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence is not None:
        text = fence.group(1)
    elif not text.startswith("{"):
        braces = re.search(r"\{.*\}", text, re.DOTALL)
        if braces is not None:
            text = braces.group(0)
    try:
        value = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    legacy_expected = {
        "route_id",
        "subject",
        "timeframe",
        "confidence",
        "reason",
    }
    aligned_expected = {
        "route_id",
        "confidence",
        "reason",
        "user_goal",
        "required_outputs",
        "assumptions",
        "ambiguities",
    }
    if not isinstance(value, dict):
        return None
    value_keys = frozenset(value)
    if value_keys not in {
        frozenset(legacy_expected),
        frozenset(aligned_expected),
    }:
        return None
    if not isinstance(value["route_id"], str):
        return None
    row = route_by_id(value["route_id"])
    if row is None:
        return None
    if isinstance(value["confidence"], bool) or not isinstance(
        value["confidence"], (int, float)
    ):
        return None
    if not isinstance(value["reason"], str) or not value["reason"].strip():
        return None
    if value_keys == frozenset(legacy_expected):
        for key in ("subject", "timeframe"):
            if value[key] is not None and not isinstance(value[key], str):
                return None
        subject = value["subject"]
        timeframe = value["timeframe"]
    else:
        for key in ("required_outputs", "assumptions", "ambiguities"):
            if not isinstance(value[key], list) or any(
                not isinstance(item, str) for item in value[key]
            ):
                return None
        if not isinstance(value["user_goal"], str):
            return None
        subject = envelope.subject
        timeframe = envelope.timeframe
    decision = _decision_from_route_row(
        row,
        query=query,
        subject=subject,
        timeframe=timeframe,
        confidence=max(0.0, min(1.0, float(value["confidence"]))),
        reason=value["reason"].strip(),
    )
    return _apply_policy(decision, query=query, envelope=envelope)


def _decision_from_route_row(
    row: RouteRow,
    *,
    query: str,
    subject: str | None,
    timeframe: str | None,
    confidence: float,
    reason: str,
) -> TurnDecision:
    return TurnDecision(
        lane=cast(TurnLane, row.lane),
        needs_retrieval=row.needs_retrieval,
        needs_memory=bool(_MEMORY_PATTERN.search(query)),
        needs_template=row.needs_template,
        question_type=row.question_type,
        subject=subject,
        timeframe=timeframe,
        confidence=confidence,
        reason=f"路由表命中 {row.route_id}：{reason}",
        capabilities=row.capabilities,
    )


def _apply_policy(
    decision: TurnDecision,
    *,
    query: str,
    envelope: QueryEnvelope,
) -> TurnDecision:
    if decision.confidence < 0.6:
        return TurnDecision(
            lane="clarify",
            needs_retrieval=False,
            needs_memory=False,
            needs_template=False,
            question_type=decision.question_type,
            subject=decision.subject,
            timeframe=decision.timeframe,
            confidence=decision.confidence,
            reason="Controller 置信度不足，先澄清",
            clarification_questions=(
                "你希望我解释概念、检索最新信息，还是做金融研究？",
            ),
        )
    if decision.lane == "chat" and _needs_retrieval_floor(query, envelope):
        return replace(
            decision,
            lane="knowledge",
            needs_retrieval=True,
            needs_template=False,
            reason="检索硬触发下限：命中标的/时效信号，不得零检索作答",
        )
    if decision.lane in {"chat", "meta", "clarify"}:
        return replace(
            decision,
            needs_retrieval=False,
            needs_memory=False,
            needs_template=False,
            capabilities=(),
        )
    if decision.lane == "knowledge":
        return replace(decision, needs_template=False)
    return replace(decision, needs_retrieval=True, needs_template=True)


def _safe_fallback(query: str, envelope: QueryEnvelope) -> TurnDecision:
    if _KNOWLEDGE_QUESTION_PATTERN.search(query):
        return _decision(
            "knowledge",
            envelope=envelope,
            needs_retrieval=_needs_retrieval_floor(query, envelope),
            confidence=0.55,
            reason="Controller 不可用；按一般知识问题安全降级",
        )
    if _needs_retrieval_floor(query, envelope):
        return _decision(
            "knowledge",
            envelope=envelope,
            needs_retrieval=True,
            confidence=0.55,
            reason="Controller 不可用；命中标的/时效信号，降级为带检索的知识回答",
        )
    return _decision(
        "chat",
        envelope=envelope,
        needs_retrieval=False,
        confidence=0.45,
        reason="Controller 不可用；安全降级为不检索的普通对话",
    )


def _enforce_task_frame_route(
    decision: TurnDecision,
    task_frame: TaskFrame,
) -> TurnDecision:
    """Prevent a soft route from removing evidence required by the frame."""

    if not task_frame_requires_retrieval(task_frame):
        return decision
    capability_floor: dict[str, tuple[str, ...]] = {
        "general_finance_evidence": ("memory", "web_search"),
        "current_public_knowledge": ("web_search",),
        "current_a_share_market": ("market_quote", "market_news"),
        "dated_a_share_market": ("market_quote", "market_news"),
        "current_market_scenarios": (
            "market_quote",
            "market_news",
            "web_search",
        ),
        "time_aligned_market_causal": (
            "market_quote",
            "market_news",
            "web_search",
        ),
        "structured_market_technical": ("market_quote",),
        "current_external_market": ("market_quote", "web_search"),
        "company_multi_layer_evidence": ("memory", "graph", "web_search"),
        "company_valuation_evidence": ("financials", "market_quote"),
        "theme_multi_layer_evidence": ("memory", "graph", "market_news"),
        "event_and_official_evidence": ("market_news", "filings", "web_search"),
        "company_financial_evidence": ("financials", "filings"),
        "comparable_multi_source_evidence": ("memory", "graph", "web_search"),
        "event_scenario_evidence": ("market_news", "web_search"),
        "claim_verification_evidence": ("filings", "web_search"),
    }
    lane = decision.lane
    if lane in {"chat", "meta", "clarify"} or not decision.needs_retrieval:
        lane = (
            "knowledge"
            if task_frame.evidence_policy == "current_public_knowledge"
            else "research"
        )
    return replace(
        decision,
        lane=lane,
        needs_retrieval=True,
        needs_memory=decision.needs_memory or "memory" in capability_floor.get(
            task_frame.evidence_policy,
            (),
        ),
        needs_template=(
            decision.needs_template or lane in {"research", "workflow"}
        ),
        capabilities=tuple(
            dict.fromkeys(
                (
                    *decision.capabilities,
                    *capability_floor.get(task_frame.evidence_policy, ()),
                )
            )
        ),
        reason=(
            f"{decision.reason}；TaskFrame 证据政策禁止零检索执行"
        ),
    )


def decide_turn(
    query: str,
    *,
    context: str = "",
    skill_mode: str = "auto",
    selected_skill_ids: Sequence[str] = (),
    llm_complete: LLMComplete | None = None,
    previous_intent: TurnIntent | None = None,
    previous_turn_id: str | None = None,
    resolver: QueryResolver | None = None,
) -> TurnDecision:
    pending_frame = (
        TaskFrame.from_dict(previous_intent.pending_task_frame)
        if previous_intent is not None
        else None
    )
    if (
        pending_frame is not None
        and previous_intent is not None
        and previous_intent.clarification_rounds >= 1
    ):
        task_frame = resolve_task_frame_clarification(pending_frame, query)
        envelope = envelope_from_task_frame(
            task_frame,
            operators=previous_intent.operators,
            time_horizon=previous_intent.time_horizon,  # type: ignore[arg-type]
        )
        intent = replace(
            previous_intent,
            primary_subject=task_frame.subject,
            question_type=task_frame.question_type,
            answer_owner=answer_owner_for_question_type(task_frame.question_type),
            inherited_from_turn=previous_turn_id,
            timeframe=task_frame.timeframe,
            required_outputs=task_frame.required_outputs,
            task_frame_hash=task_frame.task_frame_hash,
            pending_task_frame=None,
        )
        deterministic = _deterministic_decision(
            task_frame.raw_question,
            envelope=envelope,
            skill_mode=skill_mode,
            selected_skill_ids=selected_skill_ids,
        )
        decision = deterministic or _safe_fallback(task_frame.raw_question, envelope)
        return _attach_turn_intent(decision, intent, task_frame=task_frame)

    resolution = _canonicalize_head_resolution(
        query,
        (resolver or QueryResolver()).resolve(query),
    )
    inherit_subject = bool(
        previous_intent is not None
        and is_contextual_follow_up(
            query,
            resolution.envelope,
            previous_intent,
            resolution=resolution,
        )
    )
    task_frame = build_task_frame(
        query,
        resolution.envelope,
        inherited_subject=(
            previous_intent.primary_subject
            if inherit_subject and previous_intent is not None
            else None
        ),
    )
    envelope = project_task_frame(task_frame, resolution.envelope)
    resolution = replace(resolution, envelope=envelope)
    if task_frame.clarification_question is not None:
        intent = replace(
            build_turn_intent(
                query,
                envelope,
                previous_intent=previous_intent,
                previous_turn_id=previous_turn_id,
                resolution=resolution,
                task_frame=task_frame,
            ),
            pending_task_frame=task_frame.to_dict(),
            clarification_rounds=1,
        )
        return _attach_turn_intent(
            _decision(
                "clarify",
                envelope=envelope,
                confidence=task_frame.confidence,
                reason="TaskFrame 存在会改变主体、工具或结论的歧义，追问一次",
                clarification_questions=(task_frame.clarification_question,),
            ),
            intent,
            task_frame=task_frame,
        )
    if resolution.context_dependent and previous_intent is None:
        return replace(
            _decision(
                "clarify",
                envelope=envelope,
                confidence=1.0,
                reason="追问包含指代或省略，但当前对话没有可继承的研究主体",
                clarification_questions=(
                    "你指的是哪家公司、题材或上一条研究逻辑？",
                ),
            ),
            task_frame=task_frame,
        )
    intent = build_turn_intent(
        query,
        envelope,
        previous_intent=previous_intent,
        previous_turn_id=previous_turn_id,
        resolution=resolution,
        task_frame=task_frame,
    )
    if intent.inherited_from_turn is not None:
        inherited_kind = (
            "company"
            if intent.answer_owner in {
                "stock-deep-dive",
                "financial-analysis",
                "news-impact",
            }
            else "theme"
            if intent.answer_owner == "theme-research"
            else "market_pattern"
            if intent.question_type
            in {
                "market_watch",
                "dated_market_review",
                "market_forecast",
                "market_cause",
            }
            else envelope.subject_kind
        )
        task_frame = rebase_task_frame(
            task_frame,
            question_type=intent.question_type,
            subject=intent.primary_subject,
            subject_kind=inherited_kind,
            timeframe=intent.timeframe,
            required_outputs=intent.required_outputs,
        )
        envelope = project_task_frame(task_frame, envelope)
        resolution = replace(resolution, envelope=envelope)
        intent = replace(intent, task_frame_hash=task_frame.task_frame_hash)
    effective_query = contextualize_intent_query(query, intent)
    deterministic = _deterministic_decision(
        effective_query,
        envelope=envelope,
        skill_mode=skill_mode,
        selected_skill_ids=selected_skill_ids,
    )
    if deterministic is not None:
        return _attach_turn_intent(deterministic, intent, task_frame=task_frame)
    complete = llm_refine.complete if llm_complete is None else llm_complete
    try:
        content, _provider, _reason = complete(
            _controller_messages(effective_query, context, task_frame)
        )
    except Exception:
        content = None
    if content is None:
        return _attach_turn_intent(
            _enforce_task_frame_route(
                _safe_fallback(effective_query, envelope),
                task_frame,
            ),
            intent,
            task_frame=task_frame,
        )
    task_frame = align_task_frame(task_frame, content)
    envelope = project_task_frame(task_frame, envelope)
    intent = replace(
        intent,
        timeframe=task_frame.timeframe,
        required_outputs=task_frame.required_outputs,
        task_frame_hash=task_frame.task_frame_hash,
    )
    if task_frame.clarification_question is not None:
        intent = replace(
            intent,
            pending_task_frame=task_frame.to_dict(),
            clarification_rounds=max(1, intent.clarification_rounds),
        )
        return _attach_turn_intent(
            _decision(
                "clarify",
                envelope=envelope,
                confidence=task_frame.confidence,
                reason="TaskFrame 存在会改变主体、工具或结论的歧义，追问一次",
                clarification_questions=(task_frame.clarification_question,),
            ),
            intent,
            task_frame=task_frame,
        )
    parsed = _parse_llm_decision(
        content,
        query=effective_query,
        envelope=envelope,
    )
    decision = (
        parsed
        if parsed is not None
        else _safe_fallback(effective_query, envelope)
    )
    decision = _enforce_task_frame_route(decision, task_frame)
    return _attach_turn_intent(decision, intent, task_frame=task_frame)


def _attach_turn_intent(
    decision: TurnDecision,
    intent: TurnIntent,
    *,
    task_frame: TaskFrame | None = None,
) -> TurnDecision:
    if task_frame is not None:
        intent = replace(
            intent,
            primary_subject=task_frame.subject,
            question_type=task_frame.question_type,
            answer_owner=answer_owner_for_question_type(task_frame.question_type),
            timeframe=task_frame.timeframe,
            required_outputs=task_frame.required_outputs,
            task_frame_hash=task_frame.task_frame_hash,
        )
    inherited_research_intent = (
        intent.answer_owner is not None
        or intent.question_type == "general_finance_qa"
        or any(
            row.question_type == intent.question_type and row.lane == "research"
            for row in ROUTE_TABLE
        )
    )
    if (
        intent.inherited_from_turn is not None
        and inherited_research_intent
        and (
            task_frame is None
            or task_frame.clarification_question is None
        )
        and decision.lane in {
            "chat",
            "clarify",
            "knowledge",
        }
    ):
        decision = replace(
            decision,
            lane="research",
            needs_retrieval=True,
            needs_memory=True,
            needs_template=True,
            reason="结构化追问继承既有研究任务",
            clarification_questions=(),
        )
    capabilities = decision.capabilities
    if {"relation", "company_mapping"}.intersection(intent.operators):
        capabilities = tuple(dict.fromkeys((*capabilities, "graph")))
    # 单一事实源（P0 修复）：controller 的裁决（确定性头部或路由表命中）
    # 优先于软解析 intent。此前这里无条件用 intent.question_type /
    # intent.primary_subject 覆盖 decision，导致 controller 选中的路由
    # （如 market_technical / market_forecast）被旧 understand_query 的
    # general_finance_qa 反向覆盖。现改为：decision 已给出 question_type
    # 时，把 intent 同步到 decision，保证下游 ResearchPlan / trace 一致。
    if (
        task_frame is None
        and decision.question_type is not None
        and intent.inherited_from_turn is None
    ):
        intent = replace(
            intent,
            question_type=decision.question_type,
            answer_owner=answer_owner_for_question_type(decision.question_type),
            primary_subject=decision.subject or intent.primary_subject,
        )
    return replace(
        decision,
        question_type=intent.question_type,
        subject=intent.primary_subject,
        timeframe=intent.timeframe,
        capabilities=capabilities,
        turn_intent=intent,
        task_frame=task_frame,
    )
