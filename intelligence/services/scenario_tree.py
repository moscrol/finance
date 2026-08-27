"""#9+12 情景树/决策者推演表达层：把已有证据组织成「变量表→情景分支→监控信号」。

背景（为什么要这个层）：
    事件预测轮判负——Knevo 有情景树 + 决策者行为模拟 + 概率区间的完整产品形态，
    工作台没有推演表达。但 Knevo 的概率（B 40%、扭亏 20%）全部无溯源拍脑袋，
    这正是它最典型的软肋。本层做**确定性版**：不需要任何新数据源，只是要求 LLM
    把既有 D/W/M 块证据组织成推演结构，且**禁止编数值概率**——likelihood 只准
    高/中/低定性并必须注依据，变量值必须带证据编号，缺证据写显式缺口。

设计：
    - **确定性意图路由**：问题类型为 market_forecast，或命中「推演/情景/沙盘/
      如果…会怎样/演绎」词面才注入，避免污染普通问答。
    - 这是**表达层模板**（注入 synthesis prompt 的格式契约），不是数据块：
      不新增证据、不改证据链，只约束输出组织方式，所以零外部依赖、零取数成本。
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

_SCENARIO_TERMS = (
    "推演",
    "情景",
    "沙盘",
    "演绎",
    "怎么走",
    "会怎样",
    "会怎么样",
    "概率",
    "可能性",
    "预测",
)

# 「能否/能不能」原来在 _SCENARIO_TERMS 里做裸子串匹配，但它同时是汉语最高频的
# 礼貌请求前缀：「能否帮我把复盘导出成 PDF」会被判成推演题，进而追加
# scenario_tree 这一格 required_output——而一道导出请求永远填不上它，最后由契约门
# 如实拒答。判别特征是句首无主语 + 后接请求动词：
#     「正极能否扭亏」    → 主语在前、后接谓词，是真可行性问题
#     「能否帮我导出…」   → 句首起头、后接请求动词，是祈使句
_REQUEST_VERB_TAIL = (
    r"(?:帮|替|给|告诉|说明|解释|讲|介绍|看看|看下|看一下|查|搜|找|"
    r"导出|输出|生成|列|写|做|整理|发|把|将|提供|补充)"
)
_FEASIBILITY_RE = re.compile(
    rf"[\u4e00-\u9fffA-Za-z0-9%.]{{2,}}(?:能否|能不能)(?!{_REQUEST_VERB_TAIL})"
)


@dataclass(frozen=True)
class ScenarioBranch:
    branch_id: str
    label: str
    likelihood: str
    triggers: tuple[str, ...]
    conclusion: str
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioTreeArtifact:
    theme: str
    horizon: str
    variables: tuple[dict[str, Any], ...]
    branches: tuple[ScenarioBranch, ...]
    degrade_reason: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.branches)

    def to_payload(self) -> dict[str, object]:
        return {
            "theme": self.theme,
            "horizon": self.horizon,
            "available": self.available,
            "variables": list(self.variables),
            "branches": [asdict(branch) for branch in self.branches],
            "degrade_reason": self.degrade_reason,
            "numeric_probabilities_allowed": False,
        }


def build_scenario_tree_artifact(
    *,
    theme: str,
    horizon: str,
    verified_facts: tuple[dict[str, Any], ...],
    triggers: tuple[dict[str, Any], ...],
    counterevidence: tuple[dict[str, Any], ...],
    gaps: tuple[dict[str, Any], ...],
) -> ScenarioTreeArtifact:
    variables = tuple(
        {
            "name": str(claim.get("text") or ""),
            "evidence_ids": list(claim.get("evidence_ids") or ()),
            "status": str(claim.get("status") or ""),
        }
        for claim in verified_facts[:4]
        if claim.get("text")
    )
    evidence_ids = tuple(
        dict.fromkeys(
            evidence_id
            for variable in variables
            for evidence_id in variable["evidence_ids"]
            if isinstance(evidence_id, str)
        )
    )
    upgrade_triggers = tuple(
        str(claim.get("text"))
        for claim in triggers[:3]
        if claim.get("text")
    )
    downgrade_triggers = tuple(
        str(claim.get("text"))
        for claim in (*counterevidence, *gaps)[:3]
        if claim.get("text")
    )
    branches = (
        ScenarioBranch(
            "upgrade",
            "升级情景",
            "待验证",
            upgrade_triggers
            or ("出现可回查的公司级公告、订单或经营兑现证据",),
            "只有触发条件被可追溯证据确认后，才上调题材判断。",
            evidence_ids,
        ),
        ScenarioBranch(
            "base",
            "基准情景",
            "待验证",
            ("现有证据层级与盘面趋势没有发生实质变化",),
            "维持当前分层，不把题材级线索升级为公司级事实。",
            evidence_ids,
        ),
        ScenarioBranch(
            "downgrade",
            "降级/证伪情景",
            "待验证",
            downgrade_triggers
            or ("关键事实长期缺席，或后续公开信息否定当前映射",),
            "触发任一可证伪条件时降级，不以叙事强度替代证据。",
            evidence_ids,
        ),
    )
    reason = None if variables else "情景树缺少已核验变量，分支仅保留证据门槛"
    return ScenarioTreeArtifact(
        theme=theme,
        horizon=horizon,
        variables=variables,
        branches=branches,
        degrade_reason=reason,
    )


def parse_scenario_intent(query: str, question_type: str | None = None) -> bool:
    """问题类型为 market_forecast，或命中推演/情景词面即触发。

    「能否/能不能」不在 `_SCENARIO_TERMS` 里，走 `_FEASIBILITY_RE`：它要求前面有
    主语、后面不是请求动词，把祈使句（「能否帮我导出…」）排除在推演题之外。
    """
    if question_type == "market_forecast":
        return True
    text = re.sub(r"\s+", "", str(query or ""))
    if not text:
        return False
    if any(term in text for term in _SCENARIO_TERMS):
        return True
    return _FEASIBILITY_RE.search(text) is not None


def build_scenario_guidance() -> str:
    """情景树表达契约（注入 synthesis prompt；确定性文本，无取数）。"""
    return "\n".join(
        [
            "## 情景树/推演表达契约（本题为推演类问题，回答必须按此结构组织）",
            "1. **关键变量表**：列出决定结局的 3-6 个变量；每个变量的当前取值必须带证据编号"
            "（如 [D6]/[D7]/[W7]/[L1-x]），没有证据的变量写「缺数：<需要什么数据>」，禁止填印象值。",
            "2. **情景分支**（A/B/…，2-4 支）：每支只写「触发条件（可观察、可证伪）→ 条件化结论」。"
            "likelihood 只允许 高/中/低 三档定性，且每档必须紧跟「依据：<证据编号或历史事实>」；"
            "**禁止给出任何数值概率或概率区间**（如 40%、15-20%）——无溯源概率是编造。",
            "3. **监控信号清单**：每支情景给 1-3 个带时间窗的领先信号（何时看什么数据，出现即倒向哪支），"
            "信号必须是可获取的公开数据/公告/盘面指标，不得是「市场情绪转暖」这类不可证伪表述。",
            "4. 若 [M] 块有用户既有判断，情景分支应显式承接或反驳它（注明承接/反驳哪条）。",
            "5. 决策者行为只能作为「条件」写进触发条件（如「若管理层在中报说明会确认扩产」），"
            "禁止代入决策者视角编心理活动或内部剧本。",
            "6. **互斥因果假说**（与第 2 条情景分支不是同一物）：先写本题要解释的同一现象，"
            "再给 ≥2 条互斥因果假说（解释为什么发生，不是量能/涨跌路径换皮）。"
            "裁决必须带已检索证据编号；裁不了必须写「证据不足，两假说并立」。"
            "禁止数值概率。最后写一句操作含义。"
            "若证据里已有外盘领跌相对强弱，必须用它裁决（例如龙头弱于链条 vs 链条弱于龙头），"
            "不得只写成交抱团/缩量避险三分支。",
        ]
    )


def build_scenario_guidance_for_episode() -> str:
    """episode 主路径版情景树契约——纪律同 :func:`build_scenario_guidance`，术语换血。

    legacy 版证据编号用 [D6]/[W7]/[M]，那是 ask_synthesis 检索块记号。
    episode 的证据纪律是 E1、E2…；原样注入会让模型对照不存在的块。
    """
    return (
        "【情景树表达契约】本题为推演/预测类问题，draft 必须按此结构组织：\n"
        "1. 关键变量的当前取值必须带证据序号 E1、E2…；没有证据的变量写缺口，"
        "禁止填印象值。\n"
        "2. 情景分支（2-4 支）只写「可观察触发条件 → 条件化结论」。"
        "likelihood 只允许 高/中/低，且必须紧跟依据（证据序号或已检索历史事实）。"
        "禁止任何数值概率或概率区间。\n"
        "3. 每支给 1-3 个带时间窗的领先信号；信号必须是可获取的公开数据/公告/盘面指标。\n"
        "4. 若 memory_lookup 或 conversation_context 有用户既有判断，"
        "情景分支应显式承接或反驳。\n"
        "5. 决策者行为只能作为可观察条件，禁止编心理活动。\n"
        "6. 互斥因果假说（与情景分支不是同一物）：先写同一现象，再给 ≥2 条"
        "互斥因果假说（解释为什么发生，不是量能/涨跌路径换皮）。"
        "裁决必须带证据序号 E1、E2…；裁不了必须写「证据不足，两假说并立」。"
        "禁止数值概率。最后写一句操作含义。"
        "若证据里已有外盘领跌相对强弱，必须用它裁决（例如龙头弱于链条 vs 链条弱于龙头），"
        "不得只写成交抱团/缩量避险三分支。"
    )


def scenario_guidance_for_query(query: str, question_type: str | None = None) -> str:
    """命中意图返回表达契约，否则空串（不注入，行为不变）。"""
    if not parse_scenario_intent(query, question_type):
        return ""
    return build_scenario_guidance()


def episode_scenario_rule(query: str, question_type: str | None = None) -> str:
    """episode 指令的条件注入口：命中推演意图返回 episode 版契约，否则空串。"""
    if not parse_scenario_intent(query, question_type):
        return ""
    return build_scenario_guidance_for_episode()
