from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from intelligence.services import ask_clarify, llm_refine
from intelligence.services.ask import AskResult
from intelligence.services.turn_controller import TurnDecision

LLMComplete = Callable[[list[dict[str, str]]], tuple[str | None, object | None, str]]


@dataclass(frozen=True)
class LaneAnswer:
    answer: str
    provider: str | None = None
    model: str | None = None
    fallback_reason: str = ""


def deterministic_lane_answer(query: str, decision: TurnDecision) -> str | None:
    if decision.lane == "chat" and decision.reason == "明确寒暄":
        return "你好，我是 Foresight。你可以直接聊天，也可以让我做需要证据的金融研究。"
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


def _system_prompt(lane: str, grounded: bool) -> str:
    if lane == "knowledge":
        grounding = (
            "涉及当前事实时只能使用用户消息中的已检索材料；材料不足就明确说明。"
            if grounded
            else "回答稳定的一般知识；若问题依赖最新事实，应说明需要检索核验。"
        )
        return (
            "你是中性的知识助手。先直接回答概念或原理，再补充必要背景。"
            "不要自动映射到 A 股、公司名单、投资建议或金融研究模板。"
            "不要虚构来源、数据或时效性事实。"
            f"{grounding}"
        )
    return (
        "你是自然、简洁的对话助手。直接回应用户，不要套金融研究模板，"
        "不要主动检索、不要提公司级证据、不要追加非投资建议，"
        "除非用户明确提出金融研究请求。"
    )


def generate_lane_answer(
    query: str,
    decision: TurnDecision,
    *,
    context: str = "",
    evidence: str = "",
    model_override: str | None = None,
    timeout: int = 45,
    llm_complete: LLMComplete | None = None,
) -> LaneAnswer:
    deterministic = deterministic_lane_answer(query, decision)
    if deterministic is not None:
        return LaneAnswer(deterministic)
    messages = [
        {
            "role": "system",
            "content": _system_prompt(decision.lane, bool(evidence)),
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
        content, provider, reason = llm_refine.complete(
            messages,
            model_override=model_override,
            timeout=timeout,
            temperature=0.2,
        )
    else:
        content, provider, reason = llm_complete(messages)
    answer = (content or "").strip()
    if answer:
        return LaneAnswer(
            answer=answer,
            provider=getattr(provider, "name", None),
            model=getattr(provider, "model", None),
        )
    fallback = (
        "当前自然语言生成暂时不可用，无法在不检索的情况下可靠回答这个问题。"
        if decision.lane == "knowledge"
        else "当前自然语言生成暂时不可用，请稍后重试或把问题说得更具体一些。"
    )
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
    lines: list[str] = []
    for key in ("结论", "证据链", "分歧反证"):
        for item in result.sections.get(key, []):
            text = str(item).strip()
            if text and text not in lines:
                lines.append(text)
    if lines:
        return "\n\n".join(lines)
    return "当前没有取得足够可靠的资料来回答这个问题。"
