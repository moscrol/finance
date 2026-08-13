"""题材生命周期诊断（P1）：判断"市场现在把这个题材交易到哪一段".

对应 docs/learning/finance-agent-skill-expansion-brainstorm.md P1-5：
题材不是静态概念，而是有生命周期。很多 Agent 只会讲产业逻辑，不会判断
交易阶段。本模块把「证据侧发酵信号 + 盘面侧市场信号 + 市场结构状态机」
规则合成为八阶段判定：

新出现 → 旧逻辑唤醒 → 升温验证 → 加速定价 → 高位分歧 → 二阶段回流
→ 衰退观察 → 证伪退出

输出不是机械字段表，而是"阶段 + 市场奖励谁/抛弃谁 + 相对昨天变化了什么"。
纯规则、确定性、可测试；与个股深挖共享 market_structure 的阶段判定。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from intelligence.services.market_structure import (
    MarketStructureState,
    PHASE_HIGH_LOW_SWITCH,
    PHASE_HIGH_REALIZATION,
    PHASE_ICE_REPAIR,
    PHASE_MAIN_RISE,
    PHASE_SHRINK_ROTATION,
    PHASE_TREND_DIVERGENCE,
)

STAGE_NEW = "新出现"
STAGE_REAWAKEN = "旧逻辑唤醒"
STAGE_WARMING = "升温验证"
STAGE_ACCELERATION = "加速定价"
STAGE_HIGH_DIVERGENCE = "高位分歧"
STAGE_SECOND_WAVE = "二阶段回流"
STAGE_DECAY_WATCH = "衰退观察"
STAGE_FALSIFIED_EXIT = "证伪退出"
STAGE_UNKNOWN = "无法判定"

LIFECYCLE_STAGES = [
    STAGE_NEW,
    STAGE_REAWAKEN,
    STAGE_WARMING,
    STAGE_ACCELERATION,
    STAGE_HIGH_DIVERGENCE,
    STAGE_SECOND_WAVE,
    STAGE_DECAY_WATCH,
    STAGE_FALSIFIED_EXIT,
]

_STAGE_GUIDANCE = {
    STAGE_NEW: "市场刚给出定义权：奖励第一批定义标的，谁都没被证实，仓位逻辑是试错而非重仓",
    STAGE_REAWAKEN: "旧逻辑被新催化唤醒：先分清是新增量还是旧共识复读，奖励上轮核心低位股",
    STAGE_WARMING: "升温验证期：奖励有 L3 硬证据跟进的标的，纯标签股开始被抛弃",
    STAGE_ACCELERATION: "加速定价期：奖励主线核心与高弹性，追入者要接受回撤半衰期恶化的风险",
    STAGE_HIGH_DIVERGENCE: "高位分歧期：市场犹豫核心、抛弃外围；此时新逻辑（远期故事）最容易兑现",
    STAGE_SECOND_WAVE: "二阶段回流：奖励一阶段被错杀/未启动的二阶导表达，核心难创新高",
    STAGE_DECAY_WATCH: "衰退观察期：市场抛弃全题材，只有 L3 再验证能重启，反弹按修复对待",
    STAGE_FALSIFIED_EXIT: "证伪退出：关键事实被否定，任何反弹都是出局机会而非回补机会",
    STAGE_UNKNOWN: "证据与盘面都不足：先补题材双红/涨停/新高与产业证据，再谈阶段",
}

_NEW_TERMS = ("新词", "首次出现", "新题材", "新概念", "别名未登记", "未登记")
_REAWAKEN_TERMS = ("唤醒", "再度", "重启", "旧逻辑", "历史发酵", "上一轮")
_HARD_FOLLOW_TERMS = ("公告", "订单", "中标", "认证", "量产", "互动易")
_FALSIFY_TERMS = ("否认", "证伪", "澄清", "不属实", "终止", "取消订单")
# 注意用"跌停潮"而非"跌停"：市场环境行的全市场跌停计数不代表本题材衰退
_DECAY_TERMS = ("退潮", "衰退", "跌停潮", "补跌", "资金撤离", "连续缩量")


@dataclass
class ThemeLifecycleDiagnosis:
    theme: str
    stage: str = STAGE_UNKNOWN
    guidance: str = _STAGE_GUIDANCE[STAGE_UNKNOWN]
    market_phase: str = ""
    signals: list[str] = field(default_factory=list)
    delta_notes: list[str] = field(default_factory=list)  # 相对昨天/近期变化
    gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "theme": self.theme,
            "stage": self.stage,
            "guidance": self.guidance,
            "market_phase": self.market_phase,
            "signals": list(self.signals),
            "delta_notes": list(self.delta_notes),
            "gaps": list(self.gaps),
        }

    def to_prompt_block(self) -> str:
        lines = [
            "## 题材生命周期诊断（回答要说清市场交易到哪一段、奖励谁抛弃谁）",
            f"- 题材：{self.theme}",
            f"- 生命周期阶段：{self.stage}",
            f"- 阶段含义：{self.guidance}",
        ]
        if self.market_phase:
            lines.append(f"- 市场结构阶段：{self.market_phase}")
        if self.signals:
            lines.append("- 判定依据：" + "；".join(self.signals[:5]))
        for note in self.delta_notes:
            lines.append(f"- 边际变化：{note}")
        for gap in self.gaps:
            lines.append(f"- ⚠️缺口：{gap}")
        return "\n".join(lines)


def diagnose_theme_lifecycle(
    theme: str,
    evidence_lines: list[str] | None,
    gap_lines: list[str] | None,
    market_state: MarketStructureState,
    *,
    candidate_tier: str | None = None,
) -> ThemeLifecycleDiagnosis:
    diag = ThemeLifecycleDiagnosis(theme=theme, market_phase=market_state.phase)
    evidence_text = "\n".join(str(x or "") for x in (evidence_lines or []))
    gap_text = "\n".join(str(x or "") for x in (gap_lines or []))
    text = f"{evidence_text}\n{gap_text}"

    # 证伪/衰退只认证据正文：gap_lines 里的方法论提醒（如"待证伪区"）不算证伪事实
    falsified = [t for t in _FALSIFY_TERMS if t in evidence_text]
    decay = [t for t in _DECAY_TERMS if t in evidence_text]
    is_new = any(t in text for t in _NEW_TERMS)
    reawaken = [t for t in _REAWAKEN_TERMS if t in text]
    hard_follow = [t for t in _HARD_FOLLOW_TERMS if t in evidence_text]
    phase = market_state.phase

    if falsified:
        diag.stage, diag.signals = STAGE_FALSIFIED_EXIT, falsified
    elif decay or phase == PHASE_HIGH_REALIZATION:
        diag.stage = STAGE_DECAY_WATCH
        diag.signals = decay or [f"市场结构处于{phase}"]
    elif phase == PHASE_TREND_DIVERGENCE:
        diag.stage, diag.signals = STAGE_HIGH_DIVERGENCE, market_state.signals
    elif phase in {PHASE_HIGH_LOW_SWITCH, PHASE_ICE_REPAIR} or (
        reawaken and phase == PHASE_SHRINK_ROTATION
    ):
        # 主线退潮后被重新点火：有过一轮发酵史 → 二阶段回流；否则按旧逻辑唤醒
        if reawaken:
            diag.stage, diag.signals = STAGE_SECOND_WAVE, reawaken + market_state.signals
        else:
            diag.stage, diag.signals = STAGE_REAWAKEN, market_state.signals
    elif is_new:
        diag.stage = STAGE_NEW
        diag.signals = ["图谱/知识库未登记，属市场新词"]
    elif phase == PHASE_MAIN_RISE:
        # 主升里再分：有 L3 硬证据跟进 → 加速定价；只有热度 → 升温验证
        if hard_follow:
            diag.stage, diag.signals = STAGE_ACCELERATION, hard_follow + market_state.signals
        else:
            diag.stage, diag.signals = STAGE_WARMING, market_state.signals
    elif hard_follow:
        diag.stage, diag.signals = STAGE_WARMING, hard_follow
    elif reawaken:
        diag.stage, diag.signals = STAGE_REAWAKEN, reawaken
    else:
        diag.gaps.append("证据与盘面均未命中生命周期特征：需要发酵链路回溯（首板日/双红日/扩散日）补数据")

    diag.guidance = _STAGE_GUIDANCE[diag.stage]
    if candidate_tier:
        diag.delta_notes.append(f"当日盘面候选分层：{candidate_tier}")
    if diag.stage in {STAGE_WARMING, STAGE_ACCELERATION} and not hard_follow:
        diag.gaps.append("升温/加速阶段但无 L3 硬证据跟进：题材高度受限，防拔估值后证伪")
    if market_state.missing:
        diag.gaps.extend(market_state.missing)
    return diag
