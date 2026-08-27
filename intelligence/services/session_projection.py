"""Synchronous public-answer projection (dsh ``ctx.sessionProjections.view``).

同一份冻结终局事实只许有一条出口。成因是输入参数，不是开关，也不是第三条
拼串路径。本函数无 IO、无模型调用、无订阅；LLM 润色不得进入。

成因至少五类：

- ``transient_verifier_outage``：复核服务瞬时故障。决策保留（露出候选稿），
  措辞必须说「没人复核」，不得把基础设施故障写成内容质量问题。
- ``judge_unavailable_held``：复核挂了但**没有**放稿。开口说复核不可用，
  不得说证据不足或未绑定，也不得把未分类故障说成超时。
- ``evidence_gap``：证据不足。``_gap_answer`` 中间档与 ``_generic_gap_answer``
  走开口句。部分 marker_loss（W1）不再走本成因：残块保留走 ``verified`` +
  降级标注；空残块交空串，不挂道歉横幅。
- ``model_unavailable``：模型没服务成。判例已在 ``degraded_fallback.gap_opening``。
- ``verification_incomplete``：修复轮未吐合法终稿，但证据非空。开口不得写成
  「现有证据不足」。已兑现槽正文进 ``public``；未兑现槽由 ``unknown_slots``
  渲成用户语言，禁止 ``【结构缺口】`` / ``【质检``。

``verified`` 不是降级成因：核验通过后的正文也必须经本出口，避免再出现旁路。
"""

from __future__ import annotations

from dataclasses import dataclass

CAUSE_TRANSIENT_VERIFIER_OUTAGE = "transient_verifier_outage"
CAUSE_JUDGE_UNAVAILABLE_HELD = "judge_unavailable_held"
CAUSE_EVIDENCE_GAP = "evidence_gap"
CAUSE_MODEL_UNAVAILABLE = "model_unavailable"
CAUSE_VERIFICATION_INCOMPLETE = "verification_incomplete"
CAUSE_VERIFIED = "verified"

DEGRADED_CAUSES = (
    CAUSE_TRANSIENT_VERIFIER_OUTAGE,
    CAUSE_JUDGE_UNAVAILABLE_HELD,
    CAUSE_EVIDENCE_GAP,
    CAUSE_MODEL_UNAVAILABLE,
    CAUSE_VERIFICATION_INCOMPLETE,
)

_OPENING_TRANSIENT = (
    "本次未完成独立复核（复核服务超时）；内容与证据绑定已通过校验："
)
_OPENING_JUDGE_HELD = "本次未完成独立复核（复核服务不可用）。"


@dataclass(frozen=True)
class TerminalFacts:
    """冻结的终局事实。``view`` 的唯一输入。"""

    cause: str
    question: str = ""
    public: str = ""
    gap_body: str = ""
    unknown_slots: tuple[str, ...] = ()


def opening_for(cause: str, question: str = "") -> str:
    """降级成因的首句。成因行不跟 ``ASK_DEGRADED_FALLBACK``。"""

    subject = (question or "").strip() or "当前问题"
    if cause == CAUSE_TRANSIENT_VERIFIER_OUTAGE:
        return _OPENING_TRANSIENT
    if cause == CAUSE_JUDGE_UNAVAILABLE_HELD:
        return _OPENING_JUDGE_HELD
    if cause == CAUSE_EVIDENCE_GAP:
        return f"关于“{subject}”，现有证据不足，暂不能可靠回答。"
    if cause == CAUSE_MODEL_UNAVAILABLE:
        return f"关于“{subject}”，模型服务不可用，暂不能可靠回答。"
    if cause == CAUSE_VERIFICATION_INCOMPLETE:
        return f"关于“{subject}”，本轮核验未完成，已取得的观察不能当作完整结论。"
    if cause == CAUSE_VERIFIED:
        return ""
    raise ValueError(f"unknown projection cause: {cause}")


def render_unknown_slots(slots: tuple[str, ...]) -> str:
    """未兑现槽的用户语言。禁止质检标题。"""

    lines = []
    for raw in slots:
        label = str(raw or "").strip()
        if not label:
            continue
        lines.append(f"这次还核验不了：{label}。")
    return "\n".join(lines)


def view(facts: TerminalFacts) -> str:
    """把冻结终局事实折成整段公开文本。同步纯函数。"""

    if facts.cause == CAUSE_VERIFIED:
        return facts.public
    if facts.cause == CAUSE_TRANSIENT_VERIFIER_OUTAGE:
        opening = opening_for(facts.cause, facts.question)
        if facts.public:
            return f"{opening}\n\n{facts.public}"
        return opening
    if facts.cause == CAUSE_JUDGE_UNAVAILABLE_HELD:
        return opening_for(facts.cause, facts.question) + facts.gap_body
    if facts.cause == CAUSE_EVIDENCE_GAP:
        if facts.public and facts.gap_body:
            return f"{facts.public}\n{facts.gap_body}"
        return opening_for(facts.cause, facts.question) + facts.gap_body
    if facts.cause == CAUSE_MODEL_UNAVAILABLE:
        return opening_for(facts.cause, facts.question) + facts.gap_body
    if facts.cause == CAUSE_VERIFICATION_INCOMPLETE:
        chunks = [opening_for(facts.cause, facts.question)]
        if facts.public:
            chunks.append(facts.public)
        unknown = render_unknown_slots(facts.unknown_slots)
        if unknown:
            chunks.append(unknown)
        if facts.gap_body:
            chunks.append(facts.gap_body)
        return "\n".join(chunk for chunk in chunks if chunk)
    raise ValueError(f"unknown projection cause: {facts.cause}")
