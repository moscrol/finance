from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace
from typing import Literal, TypeAlias, cast

from intelligence.services import ask_clarify, llm_refine
from intelligence.services.query_understanding import QueryEnvelope, understand_query

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

_LANES = frozenset({"chat", "meta", "knowledge", "research", "workflow", "clarify"})
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
    r"导出报告|按模板输出|跑一遍|研究雷达|研究队列|今天研究什么|"
    r"daily[_ ]?agent|美股\s*AI\s*回撤|美股回撤榜|AI\s*阵营回撤|"
    r"最大回撤排序)",
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

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


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


def _deterministic_decision(
    query: str,
    *,
    skill_mode: str,
    selected_skill_ids: Sequence[str],
) -> TurnDecision | None:
    cleaned = query.strip()
    envelope = understand_query(cleaned)
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
        return _decision(
            "clarify",
            confidence=0.95,
            reason="市场范围不明确",
            clarification_questions=(
                "你想看 A 股、美股，还是全球市场？",
                "要看收盘表现、盘中行情，还是市场结构与主线？",
            ),
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
    if envelope.question_type == "external_market":
        return _decision(
            "research",
            envelope=envelope,
            confidence=envelope.confidence,
            reason="明确海外市场行情请求",
            capabilities=("market_quote", "market_news", "web_search"),
        )
    if envelope.question_type == "concept_definition":
        return _decision(
            "knowledge",
            envelope=envelope,
            needs_retrieval=False,
            needs_memory=bool(_MEMORY_PATTERN.search(cleaned)),
            confidence=envelope.confidence,
            reason="稳定概念解释不需要默认进入金融研究",
            capabilities=("memory",) if _MEMORY_PATTERN.search(cleaned) else (),
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
            capabilities=("memory", "market_quote", "graph", "financials"),
        )
    return None


def _controller_messages(query: str, context: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是对话 Turn Controller，只分类，不回答用户问题，也不调用工具。"
                "判断 lane：chat=普通对话；meta=系统/模型元问题；"
                "knowledge=概念或一般知识；research=需要金融数据、来源或时效核验；"
                "workflow=明确执行固定工作流；clarify=信息不足需追问。"
                "Router 只能在 research/workflow 后运行。不要因为工作台是金融产品，"
                "就把普通问题默认判为 research。低置信度应选择 clarify。"
                "严格输出一个 JSON 对象，键必须且只能是："
                "lane,needs_retrieval,needs_memory,needs_template,question_type,"
                "subject,timeframe,confidence,reason,capabilities。"
                "capabilities 只能从 memory,market_quote,market_news,web_search,"
                "web_fetch,graph,filings,financials 中选择。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "query": query,
                    "minimal_conversation_context": context,
                },
                ensure_ascii=False,
            ),
        },
    ]


def _parse_llm_decision(content: str) -> TurnDecision | None:
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
    expected = {
        "lane",
        "needs_retrieval",
        "needs_memory",
        "needs_template",
        "question_type",
        "subject",
        "timeframe",
        "confidence",
        "reason",
        "capabilities",
    }
    if not isinstance(value, dict) or set(value) != expected:
        return None
    lane = value["lane"]
    capabilities = value["capabilities"]
    if lane not in _LANES or not isinstance(capabilities, list):
        return None
    if any(
        not isinstance(item, str) or item not in _CAPABILITIES for item in capabilities
    ):
        return None
    if not all(
        isinstance(value[key], bool)
        for key in ("needs_retrieval", "needs_memory", "needs_template")
    ):
        return None
    if isinstance(value["confidence"], bool) or not isinstance(
        value["confidence"], (int, float)
    ):
        return None
    if not isinstance(value["reason"], str) or not value["reason"].strip():
        return None
    for key in ("question_type", "subject", "timeframe"):
        if value[key] is not None and not isinstance(value[key], str):
            return None
    decision = TurnDecision(
        lane=cast(TurnLane, lane),
        needs_retrieval=value["needs_retrieval"],
        needs_memory=value["needs_memory"],
        needs_template=value["needs_template"],
        question_type=value["question_type"],
        subject=value["subject"],
        timeframe=value["timeframe"],
        confidence=max(0.0, min(1.0, float(value["confidence"]))),
        reason=value["reason"].strip(),
        capabilities=tuple(dict.fromkeys(capabilities)),
    )
    return _apply_policy(decision)


def _apply_policy(decision: TurnDecision) -> TurnDecision:
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


def _safe_fallback(query: str) -> TurnDecision:
    envelope = understand_query(query)
    if _KNOWLEDGE_QUESTION_PATTERN.search(query):
        return _decision(
            "knowledge",
            envelope=envelope,
            needs_retrieval=False,
            confidence=0.55,
            reason="Controller 不可用；按一般知识问题安全降级",
        )
    return _decision(
        "chat",
        envelope=envelope,
        needs_retrieval=False,
        confidence=0.45,
        reason="Controller 不可用；安全降级为不检索的普通对话",
    )


def decide_turn(
    query: str,
    *,
    context: str = "",
    skill_mode: str = "auto",
    selected_skill_ids: Sequence[str] = (),
    llm_complete: LLMComplete | None = None,
) -> TurnDecision:
    deterministic = _deterministic_decision(
        query,
        skill_mode=skill_mode,
        selected_skill_ids=selected_skill_ids,
    )
    if deterministic is not None:
        return deterministic
    complete = llm_refine.complete if llm_complete is None else llm_complete
    try:
        content, _provider, _reason = complete(_controller_messages(query, context))
    except Exception:
        content = None
    if content is None:
        return _safe_fallback(query)
    parsed = _parse_llm_decision(content)
    return parsed if parsed is not None else _safe_fallback(query)
