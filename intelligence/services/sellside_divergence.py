"""卖方观点发散（P1）：判断卖方信息是否还有 alpha，而不是按推荐强度排序.

对应 docs/learning/finance-agent-skill-expansion-brainstorm.md P1-6：
晚间卖方材料多（研报/晨汇/深度覆盖），但"卖方推得猛"不等于"值得发散"。
本模块按四个可判定维度给每条卖方观点分类：

- 覆盖密度：低覆盖（首次/少数覆盖）→ 信息差还在；高覆盖 → 大概率已定价
- 证据硬度：观点里是否带 L3 硬事实（公告/订单/量产/认证），还是纯空间测算
- 盘面位置：由市场结构状态机给出（低位/启动 vs 主升 vs 高位分歧/兑现）
- 兑现风险：事件日临近、高位放量、拥挤度

三类输出（与手册一致）：

- 优先发散：低覆盖 + 高证据硬度 + 盘面刚启动/低位
- 只作确认：高覆盖 + 盘面已主升（观点只能佐证既有持仓逻辑，不能作为新买点依据）
- 反向谨慎：高覆盖 + 高拥挤 + 证据弱或兑现临近

纯规则、确定性；不输出买卖指令，只输出研究优先级与理由。
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
from intelligence.services.research_brief import classify_evidence_line
from intelligence.services.answer_quality import LAYER_L3

BUCKET_EXPLORE = "优先发散"
BUCKET_CONFIRM_ONLY = "只作确认"
BUCKET_CONTRARIAN_CAUTION = "反向谨慎"

_HIGH_COVERAGE_TERMS = ("一致预期", "多家覆盖", "集体上调", "重申", "维持买入", "全市场", "热门", "拥挤")
_LOW_COVERAGE_TERMS = ("首次覆盖", "独家", "少数覆盖", "冷门", "低覆盖", "尚未覆盖")
_REALIZATION_TERMS = ("发布会", "业绩预告", "解禁", "兑现", "落地在即", "催化临近", "事件日")

_LOW_BASE_PHASES = {PHASE_HIGH_LOW_SWITCH, PHASE_SHRINK_ROTATION, PHASE_ICE_REPAIR}
_HIGH_RISK_PHASES = {PHASE_TREND_DIVERGENCE, PHASE_HIGH_REALIZATION}


@dataclass
class SellsideView:
    text: str
    bucket: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "bucket": self.bucket, "reasons": list(self.reasons)}


@dataclass
class SellsideDivergenceReport:
    market_phase: str
    views: list[SellsideView] = field(default_factory=list)

    def bucket(self, name: str) -> list[SellsideView]:
        return [v for v in self.views if v.bucket == name]

    def to_dict(self) -> dict[str, Any]:
        return {"market_phase": self.market_phase, "views": [v.to_dict() for v in self.views]}

    def to_prompt_block(self) -> str:
        lines = ["## 卖方观点发散（判断卖方信息还有没有 alpha，不按推荐强度排序）"]
        for name in (BUCKET_EXPLORE, BUCKET_CONFIRM_ONLY, BUCKET_CONTRARIAN_CAUTION):
            views = self.bucket(name)
            lines.append(f"- {name}（{len(views)} 条）：")
            for v in views[:3]:
                lines.append(f"  - {v.text[:80]} ｜ {'；'.join(v.reasons)}")
        return "\n".join(lines)


def classify_sellside_view(text: str, market_state: MarketStructureState) -> SellsideView:
    line = str(text or "").strip()
    reasons: list[str] = []
    high_cov = any(t in line for t in _HIGH_COVERAGE_TERMS)
    low_cov = any(t in line for t in _LOW_COVERAGE_TERMS)
    hard = classify_evidence_line(line, "R") == LAYER_L3
    realization_near = any(t in line for t in _REALIZATION_TERMS)
    phase = market_state.phase

    if high_cov and (realization_near or not hard or phase in _HIGH_RISK_PHASES):
        bucket = BUCKET_CONTRARIAN_CAUTION
        reasons.append("高覆盖=大概率已定价")
        if realization_near:
            reasons.append("兑现事件临近，利好落地即分歧")
        if not hard:
            reasons.append("证据偏 L1 测算，缺 L3 硬事实")
        if phase in _HIGH_RISK_PHASES:
            reasons.append(f"盘面处于{phase}，追高性价比差")
    elif high_cov or (phase == PHASE_MAIN_RISE and not low_cov and not hard):
        bucket = BUCKET_CONFIRM_ONLY
        reasons.append("覆盖已密/盘面已主升：观点只能佐证既有逻辑，不构成新信息差")
    elif (low_cov or not high_cov) and hard and phase not in _HIGH_RISK_PHASES:
        bucket = BUCKET_EXPLORE
        reasons.append("覆盖低 + 带 L3 硬证据：信息差仍在")
        if phase in _LOW_BASE_PHASES:
            reasons.append(f"盘面处于{phase}，低位切换正是奖励预期差的阶段")
    elif low_cov:
        bucket = BUCKET_EXPLORE
        reasons.append("低覆盖但证据偏软：可发散，但只能作为跟踪假设，先补 L3 再升级")
    else:
        bucket = BUCKET_CONFIRM_ONLY
        reasons.append("覆盖/证据/盘面信号均不突出：默认只作确认，不主动发散")
    return SellsideView(text=line, bucket=bucket, reasons=reasons)


def diverge_sellside_views(
    view_lines: list[str],
    market_state: MarketStructureState,
) -> SellsideDivergenceReport:
    report = SellsideDivergenceReport(market_phase=market_state.phase)
    for raw in view_lines or []:
        line = str(raw or "").strip()
        if not line:
            continue
        report.views.append(classify_sellside_view(line, market_state))
    return report
