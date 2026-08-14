"""市场结构状态机（P1 最小版）：把盘面信号规则化成六个交易阶段.

对应 docs/learning/finance-agent-skill-expansion-brainstorm.md P1-8：
同一条公司/产业逻辑，在不同市场阶段的交易价值完全不同。个股深挖（第 4 步
市场价值 / 第 6 步生命周期）和题材生命周期诊断共享这一份阶段判定，避免
各技能各自造一套市场判断。

六阶段（互斥，按优先级判定）：

- 主升扩散：量能扩张 + 新高/涨停成簇 + 双红齐升 —— 市场奖励主线核心和高弹性
- 顺势分歧：高位放量但滞涨/分歧 —— 硬证据不足的远期故事容易兑现
- 高位兑现：主线高位缩量/资金流出 —— 兑现风险大于扩散机会
- 高低切：主线退潮 + 低位方向被点火 —— 市场奖励低位切换和预期差
- 缩量轮动：整体缩量、热点轮动无主线 —— 只奖励预期差，不奖励追高
- 冰点修复：情绪冰点后的修复反弹 —— 弱逻辑也可能短期反弹，但不可外推

纯规则判定（关键词 + 触发信号），确定性、可测试；后续可换成 DuckDB 指标
阈值版而不改调用方接口。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PHASE_MAIN_RISE = "主升扩散"
PHASE_TREND_DIVERGENCE = "顺势分歧"
PHASE_HIGH_REALIZATION = "高位兑现"
PHASE_HIGH_LOW_SWITCH = "高低切"
PHASE_SHRINK_ROTATION = "缩量轮动"
PHASE_ICE_REPAIR = "冰点修复"
PHASE_UNKNOWN = "未识别"

MARKET_PHASES = [
    PHASE_MAIN_RISE,
    PHASE_TREND_DIVERGENCE,
    PHASE_HIGH_REALIZATION,
    PHASE_HIGH_LOW_SWITCH,
    PHASE_SHRINK_ROTATION,
    PHASE_ICE_REPAIR,
]

# 阶段 → 该阶段下市场奖励谁 / 回答该怎么用这条逻辑
PHASE_PLAYBOOK = {
    PHASE_MAIN_RISE: "市场奖励主线核心与高弹性表达；此时追硬证据不足的支线要防被主线虹吸",
    PHASE_TREND_DIVERGENCE: "放量分歧期：远期故事容易借势兑现，回答必须区分增量扩散与存量博弈",
    PHASE_HIGH_REALIZATION: "高位兑现期：利好落地即分歧点，硬证据也要先回答'是否已定价'",
    PHASE_HIGH_LOW_SWITCH: "高低切期：市场奖励低位预期差，追高位主线的性价比最差",
    PHASE_SHRINK_ROTATION: "缩量轮动期：无主线，只奖励低位切换与预期差，逻辑再硬也难有持续溢价",
    PHASE_ICE_REPAIR: "冰点修复期：弱逻辑也能反弹，但反弹不证明逻辑成立，不可外推空间",
    PHASE_UNKNOWN: "盘面信号不足：先补市场结构数据，再谈交易价值",
}

_EXPANSION_TERMS = ("放量", "边际量放大", "增量", "量能扩张", "成交额新高", "双红")
_CLUSTER_TERMS = ("新高成簇", "涨停热度集中", "连板", "涨停潮", "limit_heat", "new_high_cluster", "limit_advance_cluster", "double_red")
_DIVERGENCE_TERMS = ("分歧", "滞涨", "高开低走", "炸板", "巨量换手", "放量不涨")
_HIGH_REALIZE_TERMS = ("高位缩量", "兑现", "资金流出", "获利了结", "抱团松动", "高位放量下跌")
_SWITCH_TERMS = ("高低切", "低位切换", "低位补涨", "主线退潮", "切换")
_SHRINK_TERMS = ("缩量", "轮动", "无主线", "存量", "地量")
_ICE_TERMS = ("冰点", "情绪冰点", "修复", "超跌反弹", "跌停潮后")


@dataclass
class MarketStructureState:
    phase: str = PHASE_UNKNOWN
    playbook: str = PHASE_PLAYBOOK[PHASE_UNKNOWN]
    signals: list[str] = field(default_factory=list)  # 命中的原始依据
    missing: list[str] = field(default_factory=list)  # 判定缺什么输入

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "playbook": self.playbook,
            "signals": list(self.signals),
            "missing": list(self.missing),
        }

    def to_prompt_block(self) -> str:
        lines = [
            "## 市场结构状态机（公司逻辑必须放进当前阶段里谈交易价值）",
            f"- 阶段判定：{self.phase}",
            f"- 阶段含义：{self.playbook}",
        ]
        if self.signals:
            lines.append("- 判定依据：" + "；".join(self.signals[:4]))
        if self.missing:
            lines.append("- 判定缺口：" + "；".join(self.missing))
        return "\n".join(lines)


def _hits(text: str, terms: tuple[str, ...]) -> list[str]:
    return [t for t in terms if t in text]


def classify_market_structure(
    market_lines: list[str] | None,
    trigger_types: list[str] | None = None,
) -> MarketStructureState:
    """从盘面文本行 + 候选触发信号规则判定市场阶段。

    优先级：冰点修复 > 高低切 > 高位兑现 > 顺势分歧 > 主升扩散 > 缩量轮动。
    （越特殊的状态越先判，主升/缩量是兜底的常态分支。）
    """
    state = MarketStructureState()
    text = "\n".join(str(line or "") for line in (market_lines or []))
    text = f"{text}\n{' '.join(trigger_types or [])}"
    if not text.strip():
        state.missing.append("无盘面数据行：接入 D1/D4 数据块或 theme-candidates 触发信号后才能判定")
        return state

    expansion = _hits(text, _EXPANSION_TERMS)
    cluster = _hits(text, _CLUSTER_TERMS)
    divergence = _hits(text, _DIVERGENCE_TERMS)
    realize = _hits(text, _HIGH_REALIZE_TERMS)
    switch = _hits(text, _SWITCH_TERMS)
    shrink = _hits(text, _SHRINK_TERMS)
    ice = _hits(text, _ICE_TERMS)

    if ice:
        state.phase, state.signals = PHASE_ICE_REPAIR, ice
    elif switch:
        state.phase, state.signals = PHASE_HIGH_LOW_SWITCH, switch
    elif realize:
        state.phase, state.signals = PHASE_HIGH_REALIZATION, realize
    elif divergence and (expansion or cluster):
        state.phase, state.signals = PHASE_TREND_DIVERGENCE, divergence + expansion + cluster
    elif expansion and cluster:
        state.phase, state.signals = PHASE_MAIN_RISE, expansion + cluster
    elif shrink:
        state.phase, state.signals = PHASE_SHRINK_ROTATION, shrink
    elif cluster or expansion:
        # 只有单边信号：偏主升但置信不足，显式写缺口而不是硬判
        state.phase, state.signals = PHASE_MAIN_RISE, cluster + expansion
        state.missing.append("仅命中单边量/热度信号，缺另一边（量能扩张 或 新高/涨停成簇）佐证，主升判定置信偏低")
    else:
        state.missing.append("盘面行未命中任何阶段特征词：需要涨家数/量能/涨停/新高等结构化信号")
        return state

    state.playbook = PHASE_PLAYBOOK[state.phase]
    return state
