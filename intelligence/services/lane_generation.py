from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass

from intelligence.services import ask_clarify, llm_refine
from intelligence.services.longtail_baseline import lane_suffix
from intelligence.services.ask import AskResult
from intelligence.services.honesty_gates import (
    bound_caliber_disclosure,
    calendar_disclosure,
    empty_caliber_disclosure,
    retired_table_disclosure,
)
from intelligence.services.trading_calendar import (
    question_has_retrievable_trading_day_range,
)
from intelligence.services.turn_controller import TurnDecision

LLMComplete = Callable[[list[dict[str, str]]], tuple[str | None, object | None, str]]
_THANKS_PATTERN = re.compile(
    r"^[\s，。！？,.!?]*(谢谢|感谢|多谢|thanks?)[\s，。！？,.!?]*$",
    re.IGNORECASE,
)
_GOODBYE_PATTERN = re.compile(
    r"^[\s，。！？,.!?]*(再见|拜拜|回头见|bye)[\s，。！？,.!?]*$",
    re.IGNORECASE,
)
_STATUS_PATTERN = re.compile(
    r"^[\s，。！？,.!?]*(你好吗|你怎么样|在吗|还在吗)[\s，。！？,.!?]*$"
)


@dataclass(frozen=True)
class LaneAnswer:
    answer: str
    provider: str | None = None
    model: str | None = None
    fallback_reason: str = ""


def deterministic_lane_answer(query: str, decision: TurnDecision) -> str | None:
    retired = retired_table_disclosure(query)
    if retired is not None:
        return retired
    empty = empty_caliber_disclosure(query)
    if empty is not None:
        return empty
    frame = decision.task_frame
    if frame is not None:
        # 休市是日历事实，不限 quick_fact。C2 已走这条；C1「2026-07-25 市场
        # 怎么样」是 general_finance_qa/research，旧守卫放它进检索后答证据不足。
        # 区间题（R4）：终点休市仍注入假设，但不能整题 canned，否则周内
        # 峰值被吞。休市句由 with_calendar_disclosure 在检索后前置。
        disclosure = calendar_disclosure(frame)
        if disclosure and not question_has_retrievable_trading_day_range(query):
            return disclosure if disclosure.endswith("。") else f"{disclosure}。"
    bound = bound_caliber_disclosure(query)
    if bound is not None:
        return bound
    if decision.lane == "chat" and decision.reason == "明确寒暄":
        return "你好，我是 Foresight。你可以直接聊天，也可以让我做需要证据的金融研究。"
    if decision.lane == "chat" and _THANKS_PATTERN.fullmatch(query):
        return "不客气。你可以继续聊，也可以直接告诉我想了解或核验什么。"
    if decision.lane == "chat" and _GOODBYE_PATTERN.fullmatch(query):
        return "再见，需要时随时继续。"
    if decision.lane == "chat" and _STATUS_PATTERN.fullmatch(query):
        return "我在，可以继续聊。"
    if decision.lane == "meta":
        return (
            "我是 Foresight 本地金融研究工作台的对话入口，"
            "由工作台当前配置的大模型提供生成能力。"
            "具体底层模型以运行配置为准；这类元问题不会触发金融检索。"
        )
    if decision.lane == "clarify":
        questions = list(decision.clarification_questions)
        if not questions:
            questions = ask_clarify.clarify_for_query(query).questions
        if not questions:
            questions = ["你希望我解释概念、检索最新信息，还是做金融研究？"]
        return "我还缺少一点信息：\n" + "\n".join(
            f"{index}. {question}" for index, question in enumerate(questions, 1)
        )
    return None


def _system_prompt(decision: TurnDecision, grounded: bool) -> str:
    if decision.lane == "knowledge":
        if decision.question_type == "methodology_discussion":
            prompt = (
                "你是资深 Agent 系统架构师。这是方法论或工程机制问题，可以基于"
                "通用原理做因果分析，不需要为了显得有依据而检索金融 Wiki。"
                "先直接回答核心机制，再说明边界、替代方案与验证方法。"
                "按问题复杂度控制篇幅；对单一‘为什么’问题给紧凑答案，"
                "避免穷举所有可能架构。"
                "不要套金融研究模板，不要虚构当前代码实现；若用户问到本地实现而"
                "上下文没有代码证据，要把通用原理与待核验的实现事实分开。"
            )
        else:
            grounding = (
                "涉及当前事实时只能使用用户消息中的已检索材料；材料不足就明确说明。"
                if grounded
                else "回答稳定的一般知识；若问题依赖最新事实，应说明需要检索核验。"
            )
            prompt = (
                "你是中性的知识助手。先直接回答概念或原理，再补充必要背景。"
                "不要自动映射到 A 股、公司名单、投资建议或金融研究模板。"
                "不要虚构来源、数据或时效性事实。"
                "输出纪律：区分事实、推断与未知；引用检索材料时标注来源；"
                "材料之间有矛盾时并列呈现而不是只挑一面；"
                "关键缺口（缺哪类数据、缺哪个时间段）要显式披露。"
                f"{grounding}"
            )
    else:
        prompt = (
            "你是自然、简洁的对话助手。直接回应用户，不要套金融研究模板，"
            "不要主动检索、不要提公司级证据、不要追加非投资建议，"
            "除非用户明确提出金融研究请求。"
        )
    suffix = lane_suffix(decision)
    if suffix:
        return f"{prompt}\n\n{suffix}"
    return prompt


def generate_lane_answer(
    query: str,
    decision: TurnDecision,
    *,
    context: str = "",
    evidence: str = "",
    model_override: str | None = None,
    timeout: int = llm_refine.DEFAULT_LLM_TIMEOUT,
    llm_complete: LLMComplete | None = None,
) -> LaneAnswer:
    deterministic = deterministic_lane_answer(query, decision)
    if deterministic is not None:
        return LaneAnswer(deterministic)
    messages = [
        {
            "role": "system",
            "content": _system_prompt(decision, bool(evidence)),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": query,
                    "minimal_conversation_context": context,
                    "retrieved_material": evidence or None,
                },
                ensure_ascii=False,
            ),
        },
    ]
    if llm_complete is None:
        attempt_timeout = (
            min(90, timeout)
            if decision.question_type == "methodology_discussion"
            and timeout >= 120
            else timeout
        )
        content, provider, reason = llm_refine.complete(
            messages,
            model_override=model_override,
            timeout=attempt_timeout,
            temperature=0.2,
        )
        if (
            not (content or "").strip()
            and decision.question_type == "methodology_discussion"
            and timeout >= 120
            and re.search(r"timeout|超时", str(reason or ""), re.IGNORECASE)
        ):
            # Provider 偶发卡住时，把原本 180s 的单次赌注拆成 90s + 90s。
            # 总 wall-time 预算不增加；方法论题仍不回退金融 RAG。
            content, provider, retry_reason = llm_refine.complete(
                messages,
                model_override=model_override,
                timeout=max(1, timeout - attempt_timeout),
                temperature=0.2,
            )
            reason = retry_reason or reason
    else:
        content, provider, reason = llm_complete(messages)
    answer = (content or "").strip()
    if answer:
        return LaneAnswer(
            answer=answer,
            provider=getattr(provider, "name", None),
            model=getattr(provider, "model", None),
        )
    if decision.question_type == "methodology_discussion":
        fallback = "当前自然语言生成暂时不可用，无法可靠生成方法论分析；请稍后重试。"
    elif decision.lane == "knowledge":
        fallback = "当前自然语言生成暂时不可用；我会尝试从可核验资料中提取一个中性回答。"
    else:
        fallback = "当前自然语言生成暂时不可用，暂时不能可靠生成这段对话；请稍后重试。"
    return LaneAnswer(fallback, fallback_reason=reason)


def knowledge_evidence(result: AskResult) -> str:
    return json.dumps(
        {
            "sections": result.sections,
            "sources": [
                {
                    "source": citation.source,
                    "detail": citation.detail,
                }
                for citation in result.citations
            ],
            "data_notice": result.data_notice,
            "warnings": result.warnings,
        },
        ensure_ascii=False,
    )


def render_knowledge_fallback(result: AskResult) -> str:
    evidence: list[str] = []
    for item in result.sections.get("证据链", []):
        text = str(item).strip()
        if text and text not in evidence:
            evidence.append(text)
    if evidence:
        return (
            "自然语言生成暂时不可用，先提供本轮取得的可核验资料摘要：\n\n"
            + "\n\n".join(evidence)
        )
    lines: list[str] = []
    for key in ("结论", "分歧反证"):
        for item in result.sections.get(key, []):
            text = str(item).strip()
            if text and text not in lines:
                lines.append(text)
    if lines:
        return "\n\n".join(lines)
    return "当前没有取得足够可靠的资料来回答这个问题。"
