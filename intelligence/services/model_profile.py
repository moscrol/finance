"""模型档位（model capability profile）——harness 的「地板 / 天花板」分层开关。

同一套 harness 要同时服务两类模型：

* 实惠模型（economy）：需要地板——硬路由、固定步数、低置信度先澄清；
* 强模型（frontier）：需要天花板——更多研究步数、更长证据、路由降级为建议，
  由模型自己处理模糊问题，而不是被规则截停。

核查层（数字闸、证据边界、检索硬触发下限）对所有档位一律生效，不随档位放松。

选择方式：环境变量 ``FWP_MODEL_PROFILE``（standard | economy | frontier）。
未设置或取值不认识 → ``standard``，**其所有旋钮与引入本模块前的行为逐项一致**
（见 tests/test_model_profile.py 的等价断言）。单项环境变量（如
``ASK_AGENT_MAX_STEPS``）优先级高于档位。

economy 目前与 standard 数值相同：它是给后续「按难度分流 / 升档」预留的身份，
具体数值要等 2×2 实验数据校准后再定，不在这里拍脑袋。

本模块只依赖标准库，可被 services / runtime 任意层安全导入。
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass

ENV_MODEL_PROFILE = "FWP_MODEL_PROFILE"

PROFILE_STANDARD = "standard"
PROFILE_ECONOMY = "economy"
PROFILE_FRONTIER = "frontier"

ROUTE_BINDING = "binding"
ROUTE_ADVISORY = "advisory"


@dataclass(frozen=True)
class ModelProfile:
    name: str
    # agent_research 研究循环默认步数（ASK_AGENT_MAX_STEPS 显式设置时以其为准）。
    agent_loop_max_steps: int
    # kb_rag 证据送达字符预算倍率：per_hit 与 total（含 8000 封顶）同比缩放。
    evidence_char_scale: float
    # binding：controller 置信度 < 0.6 一律转澄清（地板）；
    # advisory：不强制澄清，带检索进入 knowledge 车道，由模型自行消歧（天花板）。
    route_authority: str
    # 预留：按难度分流时是否允许从本档升到强模型。当前不接线，只作身份标记。
    escalation_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


# standard 的每个数值必须与引入本模块前的硬编码一致：
#   agent_research.DEFAULT_MAX_STEPS = 4
#   kb_rag.evidence_budget_for_query 无缩放（8000 封顶）
#   turn_controller._apply_policy 低置信度 → clarify
PROFILES: dict[str, ModelProfile] = {
    PROFILE_STANDARD: ModelProfile(
        name=PROFILE_STANDARD,
        agent_loop_max_steps=4,
        evidence_char_scale=1.0,
        route_authority=ROUTE_BINDING,
    ),
    PROFILE_ECONOMY: ModelProfile(
        name=PROFILE_ECONOMY,
        agent_loop_max_steps=4,
        evidence_char_scale=1.0,
        route_authority=ROUTE_BINDING,
        escalation_eligible=True,
    ),
    PROFILE_FRONTIER: ModelProfile(
        name=PROFILE_FRONTIER,
        agent_loop_max_steps=8,
        evidence_char_scale=1.5,
        route_authority=ROUTE_ADVISORY,
    ),
}


def active_profile_name() -> str:
    raw = str(os.environ.get(ENV_MODEL_PROFILE) or "").strip().lower()
    return raw if raw in PROFILES else PROFILE_STANDARD


def active_profile() -> ModelProfile:
    """每次调用都重读环境变量——测试与 A/B 切档无需重启进程内缓存。"""
    return PROFILES[active_profile_name()]


def route_is_advisory() -> bool:
    return active_profile().route_authority == ROUTE_ADVISORY


def scale_chars(value: int, *, profile: ModelProfile | None = None) -> int:
    scale = (profile or active_profile()).evidence_char_scale
    if scale == 1.0:
        return int(value)
    return max(1, int(round(value * scale)))
