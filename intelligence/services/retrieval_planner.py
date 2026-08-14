"""轻量 LLM 检索 planner（方案 2）：规则门控升级为「LLM 出计划、代码钳制执行」。

现状的取块决策是纯关键词意图匹配——换个问法漏块、同类问题证据同质。本模块让
小模型基于 evidence_registry 的机读 provider 描述输出**计划**（选哪些块、W 检索式
改写、理由），执行仍是确定性代码，可审计性不丢：

- 最终集合 = ``(LLM 计划 ∩ 注册表白名单) ∪ 规则必选块``；
- LLM 未配置/超时/输出不合法 → 完全回退现行规则，行为等同今天；
- 计划（含 shadow 模式的未生效计划）写入 ``result.provider_traces``。

灰度开关 ``ASK_PLANNER_MODE``：
- ``rules``（默认）：不调 LLM，行为逐字节不变；
- ``shadow``：调 LLM 但计划只记 trace 不生效——先积累对比数据再决定切换；
- ``llm``：计划生效（钳制后写入 ``options.enabled_providers``）。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from intelligence.services import evidence_registry, llm_refine

ENV_MODE = "ASK_PLANNER_MODE"
MODE_RULES = "rules"
MODE_SHADOW = "shadow"
MODE_LLM = "llm"
_VALID_MODES = (MODE_RULES, MODE_SHADOW, MODE_LLM)

DEFAULT_TIMEOUT = 8

# 规则必选块：无论 LLM 计划怎么选，这些块按问题类型强制保留（安全网，防小模型漏块）。
MANDATORY_PROVIDERS: dict[str, tuple[str, ...]] = {
    "market_review": ("D4", "M", "V"),
    "valuation": ("D5", "M", "V"),
}
DEFAULT_MANDATORY: tuple[str, ...] = ("M", "V")
# 视角模式激活时的追加必选块：KOL 视角是解释盘面的镜头，事实底座至少要有
# 同日市场总览（MARKET_DAILY）、主线结构（D4）与题材量价趋势（D6），否则视角
# 会对着空产生"该方向无盘面信号"的假阴性判断（2026-08-13 实测）。
#
# 生效边界（勿高估）：本必选块只在 ``ASK_PLANNER_MODE=llm`` 的钳制路径生效
# （rules 默认模式不跑 plan_retrieval，也就不写 enabled_providers）；且
# enabled 只是"允许"，各 provider 的 ``applies()`` 意图门仍要过。默认模式下
# 视角的盘面证据放宽实际由 ``market_midterm.midterm_intent_for`` 的
# perspective 回退承担（D6），D4 默认开启，MARKET_DAILY 走 owner 侧预取。
PERSPECTIVE_MANDATORY: tuple[str, ...] = ("MARKET_DAILY", "D4", "D6")


def planner_mode() -> str:
    mode = str(os.environ.get(ENV_MODE) or MODE_RULES).strip().lower()
    return mode if mode in _VALID_MODES else MODE_RULES


@dataclass(frozen=True)
class RetrievalPlan:
    """一次检索计划：providers 已钳制（∩ 白名单 ∪ 必选块），queries 为检索式改写。"""

    providers: tuple[str, ...]
    queries: dict[str, str] = field(default_factory=dict)
    reason: str = ""
    source: str = MODE_RULES  # rules | llm | llm_fallback:<原因>

    def to_dict(self) -> dict[str, object]:
        return {
            "providers": list(self.providers),
            "queries": dict(self.queries),
            "reason": self.reason,
            "source": self.source,
        }


def _registry_prompt_block() -> str:
    lines = [
        f"- {spec.name}（{spec.label}）：{spec.description}"
        for spec in evidence_registry.REGISTRY
    ]
    return "\n".join(lines)


_SYSTEM_PROMPT = (
    "你是检索计划器。根据用户问题从下列证据块中选出应该取数的块，"
    "并可为 W7（web 事件检索）改写更好的检索式。\n"
    "只输出 JSON（无 markdown 代码栏）："
    '{"providers": ["D6", ...], "queries": {"W7": "改写后的检索式"}, "reason": "一句话理由"}\n'
    "可选块：\n{registry}\n"
    "原则：宁多勿漏；与问题无关的块不选；不确定时保留默认。"
)


def _parse_plan_json(content: str) -> dict[str, object] | None:
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.S)
        if brace:
            text = brace.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def mandatory_for(
    question_type: str,
    *,
    perspective_active: bool = False,
) -> tuple[str, ...]:
    base = MANDATORY_PROVIDERS.get(question_type, DEFAULT_MANDATORY)
    if not perspective_active:
        return base
    return tuple(dict.fromkeys((*base, *PERSPECTIVE_MANDATORY)))


def clamp_plan(
    raw_providers: object,
    question_type: str,
    *,
    perspective_active: bool = False,
) -> tuple[str, ...]:
    """钳制 LLM 计划：∩ 注册表白名单，∪ 规则必选块，按注册顺序输出（确定性）。"""
    requested = {
        str(name).strip().upper()
        for name in (raw_providers if isinstance(raw_providers, list) else [])
    }
    allowed = requested & set(evidence_registry.PROVIDER_NAMES)
    allowed |= set(mandatory_for(question_type, perspective_active=perspective_active))
    return tuple(
        name for name in evidence_registry.PROVIDER_NAMES if name in allowed
    )


def plan_retrieval(
    query: str,
    question_type: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    perspective_active: bool = False,
) -> RetrievalPlan:
    """调小模型出计划；任何失败都回退 rules（source 说明原因，供 trace 审计）。"""
    messages = [
        {
            "role": "system",
            "content": _SYSTEM_PROMPT.replace("{registry}", _registry_prompt_block()),
        },
        {
            "role": "user",
            "content": f"问题类型：{question_type}\n用户问题：{query}",
        },
    ]
    content, _provider, reason = llm_refine.complete(
        messages, timeout=timeout, temperature=0.0,
    )
    if content is None:
        return RetrievalPlan(
            providers=(), source=f"llm_fallback:{reason}",
        )
    data = _parse_plan_json(content)
    if data is None:
        return RetrievalPlan(
            providers=(), source="llm_fallback:非法 JSON 输出",
        )
    providers = clamp_plan(
        data.get("providers"), question_type, perspective_active=perspective_active,
    )
    raw_queries = data.get("queries")
    queries = {
        str(key).strip().upper(): str(value).strip()
        for key, value in (raw_queries or {}).items()
        if isinstance(raw_queries, dict) and str(value).strip()
    }
    return RetrievalPlan(
        providers=providers,
        queries=queries,
        reason=str(data.get("reason") or "").strip(),
        source=MODE_LLM,
    )
