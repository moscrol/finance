"""通用研究 Owner 的短任务规划器。

规划器只负责把自然语言问题拆成少量可执行的子问题和待验证假设。
它不能改变研究契约中的工具白名单、required outputs、研究档位或预算；
因此即使 LLM 输出了额外字段，调用方也不会把这些字段执行成能力扩张。

这是一个有意很薄的边界层：LLM 负责补充任务视角，确定性代码负责 schema
校验和规则回退，Research Agent 仍是唯一的检索决策者。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable

from intelligence.services import llm_refine

MAX_SUBQUESTIONS = 5
MAX_HYPOTHESES = 4
MAX_ITEM_CHARS = 180
DEFAULT_TIMEOUT = 5


@dataclass(frozen=True)
class TaskPlan:
    """经过 schema 和长度钳制的任务计划。"""

    subquestions: tuple[str, ...] = ()
    hypotheses: tuple[str, ...] = ()
    source: str = "rules"
    reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "subquestions": list(self.subquestions),
            "hypotheses": list(self.hypotheses),
            "source": self.source,
            "reason": self.reason,
        }

    def to_prompt_block(self) -> str:
        """给 agent 的任务说明，不暴露内部实现词。"""

        lines = ["任务拆解（仅用于选择检索顺序，不改变工具和预算）："]
        if self.subquestions:
            lines.append("子问题：")
            lines.extend(f"- {item}" for item in self.subquestions)
        if self.hypotheses:
            lines.append("待验证假设：")
            lines.extend(f"- {item}" for item in self.hypotheses)
        return "\n".join(lines)


def _parse_json(content: str) -> dict[str, object] | None:
    text = str(content or "").strip()
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
    if fenced:
        text = fenced.group(1)
    else:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            text = match.group(0)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _clean_items(value: object, *, limit: int) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    result: list[str] = []
    seen: set[str] = set()
    for raw in value:
        # 规划输出只接受纯文本条目。对象/嵌套数组一律丢弃，避免模型把
        # ``tools``、``tier`` 等控制字段藏进计划后被误执行。
        if not isinstance(raw, str):
            continue
        item = re.sub(r"\s+", " ", raw).strip()
        if not item or len(item) > MAX_ITEM_CHARS or item in seen:
            continue
        seen.add(item)
        result.append(item)
        if len(result) >= limit:
            break
    return tuple(result)


# 决策面：关键变量由某个主体拍板的那几类问题。每项是（题面标签，决定权主体）。
# 词表刻意窄——只收「有人拍板」的动作词，不收「政策利好」这类叙事词，
# 否则每道题材题都会被判成参与者约束题。
_DECISION_SURFACES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "审批/政策决定",
        "主管部门",
        ("批复", "核准", "审批", "备案", "立项", "发牌", "牌照", "配额", "出台",
         "新规", "禁令", "限产", "国补", "补贴目录", "纳入目录", "集采政策"),
    ),
    (
        "招标/采购决定",
        "招标方或采购方",
        ("招标", "中标", "投标", "定标", "流标", "废标", "集采", "框架协议",
         "询价", "采购订单", "供应商入围"),
    ),
    (
        "扩产/投资决定",
        "公司董事会与出资方",
        ("扩产", "新建产能", "扩建", "技改", "资本开支", "产能规划", "投产计划",
         "定增投向", "对外投资"),
    ),
)


def detect_decision_surface(question: str) -> tuple[str, str] | None:
    """问句里是否有「等某个主体拍板」的决策面。命中返回（题面标签，决定权主体）。"""
    text = re.sub(r"\s+", "", str(question or ""))
    if not text:
        return None
    for label, actor, terms in _DECISION_SURFACES:
        if any(term in text for term in terms):
            return label, actor
    return None


def _rule_plan(question: str, contract: object | None = None, *, reason: str = "") -> TaskPlan:
    """无 LLM/非法 JSON 时的保守规则计划。"""

    q = re.sub(r"\s+", "", str(question or ""))
    question_type = str(getattr(contract, "question_type", "") or "")
    subject = str(getattr(contract, "subject", "") or "")
    prefix = f"围绕{subject}，" if subject else ""
    if question_type == "market_forecast":
        return TaskPlan(
            subquestions=(
                f"{prefix}当前事实和时间窗口是什么？",
                "支持反弹/正向情景的证据和触发条件是什么？",
                "支持继续走弱/负向情景的证据和触发条件是什么？",
                "哪些反证会使当前判断失效？",
            ),
            hypotheses=(
                "反弹情景：当前证据是否支持短期修复？",
                "继续走弱情景：当前证据是否支持风险延续？",
                "失效条件：哪些新信息会推翻基准判断？",
            ),
            source="rules",
            reason=reason or "forecast_rule_fallback",
        )
    if question_type == "event_forecast":
        return TaskPlan(
            subquestions=(
                f"{prefix}事件已经确认的事实、待发生条件和时间窗口是什么？",
                "事件会通过哪些环节传导，哪些行业、公司或资产可能受益或受损？",
                "哪些新增事实、指标或披露会在什么窗口验证当前传导判断？",
                "哪些反向事实会在什么窗口证伪当前传导或方向判断？",
            ),
            hypotheses=(
                "事件事实：事件发生条件与时间窗口是否得到可回查证据支持？",
                "传导方向：受益/受损判断是否存在清晰传导链和边界？",
                "验证与证伪：后续窗口内哪些事实会确认或推翻当前推演？",
            ),
            source="rules",
            reason=reason or "event_forecast_rule_fallback",
        )
    if str(getattr(contract, "presentation_profile", "") or "") == "relation":
        return TaskPlan(
            subquestions=(
                f"{prefix}问题中的主体、关系方向和关系层级是什么？",
                "先查本地图谱是否存在与问题方向一致的显式关系边。",
                "再用证据索引或公开来源核对候选关系，区分已核验、候选和缺边。",
            ),
            hypotheses=(
                "关系地图：当前证据是否支持问题所问的关系边？",
                "缺边反证：命中的公司资料是否只是共现，不能推出关系？",
            ),
            source="rules",
            reason=reason or "relation_rule_fallback",
        )
    if question_type == "comparison" or re.search(r"比较|对比|相比", q):
        return TaskPlan(
            subquestions=(
                f"{prefix}比较对象和口径是什么？",
                "两者最重要的共同点和差异是什么？",
                "哪些证据支持比较结论，边界在哪里？",
            ),
            hypotheses=("关键差异能够解释结果差距。",),
            source="rules",
            reason=reason or "comparison_rule_fallback",
        )
    surface = detect_decision_surface(q)
    if surface is not None:
        # 参与者约束试验（Knevo q17 Q6 回灌，复核笔记候选三，**小范围试用**）：
        # 政策/招标/扩产/采购类问题的关键变量由某个主体决定，而不是由行业趋势决定。
        # 先问「谁有决定权、他的公开约束是什么、有哪几种可行动作、哪份材料能区分」，
        # 再谈传导，检索顺序才不会一上来就去抓行情。
        #
        # 刻意排在 forecast/relation/comparison 之后：那三类已有自己的规划，这一支
        # 只接管它们没接走的问句。试用出效果再考虑并进 event_forecast 那一支。
        label, actor = surface
        return TaskPlan(
            subquestions=(
                f"{prefix}这件{label}由谁决定？决策主体、层级和公开的决策程序是什么"
                f"（只用公开依据；查不到就写成假设，不补内部动机）？",
                f"{actor}受什么公开约束（法规、预算、合同条款、产能与现金约束）？",
                "在这些约束下他有哪几种可行动作？每种对应什么可观察的公开信号？",
                "哪份公告、条款或后续行为能区分这几种可能？出现在什么时间窗？",
                "这些动作分别怎么传导到收入/成本/利润，下一步先验证哪一条？",
            ),
            hypotheses=(
                f"决策权限：关键变量确实由{actor}决定，而不是另一层级或另一主体。",
                "公开约束：现有法规/合同/经营约束足以排除其中某些动作。",
                "区分证据：某份公开材料能在给定窗口内区分剩余可能。",
            ),
            source="rules",
            reason=reason or "participant_constraint_rule",
        )
    return TaskPlan(
        subquestions=(
            f"{prefix}问题涉及的对象、时间和口径是什么？",
            "哪些事实能直接回答问题？",
            "当前证据缺什么，下一步应核验什么？",
        ),
        hypotheses=("现有证据足以支持一个有边界的直接判断。",),
        source="rules",
        reason=reason or "generic_rule_fallback",
    )


def plan_task(
    question: str,
    *,
    contract: object | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    complete_fn: Callable[..., tuple[str | None, object, str]] | None = None,
    enabled: bool = True,
) -> TaskPlan:
    """用一次短 LLM 调用生成任务拆解，失败则回到确定性规则。

    ``complete_fn`` 仅供测试/上层注入；它的输出不会直接成为工具调用。
    """

    fallback = _rule_plan(question, contract=contract)
    if not enabled:
        return fallback
    complete = complete_fn or llm_refine.complete
    question_type = str(getattr(contract, "question_type", "") or "general_finance_qa")
    subject = str(getattr(contract, "subject", "") or "未指定")
    messages = [
        {
            "role": "system",
            "content": (
                "你是金融研究任务拆解器。只把问题拆成检索顺序参考，不能新增工具、"
                "不能改变预算/研究档位/硬性输出。只输出 JSON（无 markdown）："
                '{"subquestions":["..."],"hypotheses":["..."]}。'
                f"子问题最多 {MAX_SUBQUESTIONS} 条，假设最多 {MAX_HYPOTHESES} 条；"
                f"每条不超过 {MAX_ITEM_CHARS} 字。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"问题类型：{question_type}\n对象：{subject}\n用户问题：{question}"
            ),
        },
    ]
    try:
        content, _provider, reason = complete(
            messages,
            timeout=max(1, min(int(timeout), DEFAULT_TIMEOUT)),
            temperature=0.0,
        )
    except Exception as exc:  # pragma: no cover - provider-specific failure
        return _rule_plan(question, contract=contract, reason=f"planner_exception:{type(exc).__name__}")
    if content is None:
        return _rule_plan(
            question,
            contract=contract,
            reason=f"planner_unavailable:{str(reason or 'unknown')[:120]}",
        )
    data = _parse_json(content)
    if data is None:
        return _rule_plan(question, contract=contract, reason="planner_invalid_json")
    subquestions = _clean_items(data.get("subquestions"), limit=MAX_SUBQUESTIONS)
    hypotheses = _clean_items(data.get("hypotheses"), limit=MAX_HYPOTHESES)
    # 空计划不是“成功”：它会让 agent 丢失问题结构，按规则计划处理。
    if not subquestions and not hypotheses:
        return _rule_plan(question, contract=contract, reason="planner_empty_plan")
    return TaskPlan(
        subquestions=subquestions,
        hypotheses=hypotheses,
        source="llm",
        reason="planner_ok",
    )


__all__ = [
    "DEFAULT_TIMEOUT",
    "MAX_HYPOTHESES",
    "MAX_ITEM_CHARS",
    "MAX_SUBQUESTIONS",
    "TaskPlan",
    "plan_task",
]
