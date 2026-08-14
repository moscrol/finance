"""事件冲击传导（P2-9）：新闻/政策/公告 → 产业链传导 → 验证路径的研究骨架.

对应 docs/learning/finance-agent-skill-expansion-brainstorm.md P2-9：
事实抽取 → 产业链传导 → 财务科目 → 公司弹性 → 市场误分类 → 验证路径。
输出是研究假设，不是交易指令。

与 StockResearchBrief 同一设计：编排层强制六步视角、缺视角写显式缺口，
输出层交给 compose 自然成文。纯规则、确定性、可测试。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from intelligence.services.answer_quality import LAYER_L3
from intelligence.services.research_brief import classify_evidence_line

EVENT_STEP_ORDER = ["事实抽取", "产业链传导", "财务科目", "公司弹性", "市场误分类", "验证路径"]

_FACT_TERMS = ("公告", "发布", "政策", "文件", "订单", "中标", "禁令", "关税", "补贴", "招标")
_CHAIN_TERMS = ("产业链", "上游", "下游", "供应", "传导", "环节", "核心层", "暴露")
_FINANCE_TERMS = ("收入", "利润", "毛利", "成本", "价格", "产能", "出货", "占比")
_ELASTICITY_TERMS = ("弹性", "受益", "受损", "占比", "业绩", "兑现")
_MISCLASS_TERMS = ("误分类", "错杀", "预期差", "标签", "被贴", "混淆", "一阶", "二阶")


@dataclass
class EventStep:
    name: str
    points: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "points": list(self.points), "gaps": list(self.gaps)}


@dataclass
class EventTransmissionBrief:
    event: str
    steps: list[EventStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "steps": [s.to_dict() for s in self.steps],
            "warnings": list(self.warnings),
        }

    def to_prompt_block(self) -> str:
        lines = ["## 事件冲击传导骨架（输出研究假设，不输出交易指令）", f"- 事件：{self.event}"]
        for step in self.steps:
            lines.append(f"### {step.name}")
            for p in step.points:
                lines.append(f"- {p}")
            for g in step.gaps:
                lines.append(f"- ⚠️缺口：{g}")
        for w in self.warnings:
            lines.append(f"- ⚠️{w}")
        return "\n".join(lines)


def _collect(lines: list[str], terms: tuple[str, ...]) -> list[str]:
    return [ln for ln in lines if any(t in ln for t in terms)]


def build_event_transmission_brief(
    event: str,
    evidence_lines: list[str] | None,
) -> EventTransmissionBrief:
    brief = EventTransmissionBrief(event=event)
    lines = [str(x or "").strip() for x in (evidence_lines or []) if str(x or "").strip()]

    facts = _collect(lines, _FACT_TERMS)
    hard_facts = [ln for ln in facts if classify_evidence_line(ln, "R") == LAYER_L3]
    step = EventStep("事实抽取", points=facts[:4])
    if not facts:
        step.gaps.append("未抽取到事件事实：先确认事件原文（公告/政策全文），不能从转述开始推")
    elif not hard_facts:
        step.gaps.append("事实均非 L3 硬证据：传导推演只能按'预期'档处理")
    brief.steps.append(step)

    chain = _collect(lines, _CHAIN_TERMS)
    step = EventStep("产业链传导", points=chain[:4])
    if not chain:
        step.gaps.append("缺产业链传导路径：需回答冲击先打到哪个环节、再传到哪个环节")
    brief.steps.append(step)

    fin = _collect(lines, _FINANCE_TERMS)
    step = EventStep("财务科目", points=fin[:4])
    if not fin:
        step.gaps.append("缺财务科目映射：冲击最终落在量、价、成本还是费用，决定弹性方向")
    brief.steps.append(step)

    ela = _collect(lines, _ELASTICITY_TERMS)
    step = EventStep("公司弹性", points=ela[:4])
    if not ela:
        step.gaps.append("缺公司弹性：同环节公司的收入占比/产能弹性差异未量化，谁受益最大不明")
    brief.steps.append(step)

    mis = _collect(lines, _MISCLASS_TERMS)
    step = EventStep("市场误分类", points=mis[:4])
    if not mis:
        step.gaps.append("缺市场误分类检查：一阶/二阶受益是否被混淆、有无错杀或强行贴标签")
    brief.steps.append(step)

    verify = EventStep(
        "验证路径",
        points=[
            "T+1 盘面确认：受益环节是否放量/新高，受损环节是否补跌",
            "T+3 证据确认：公司公告/互动易是否跟进确认暴露",
            "T+5 传导确认：二阶环节是否开始被定价，或事件被证伪回吐",
        ],
    )
    brief.steps.append(verify)

    if not hard_facts:
        brief.warnings.append("事件事实未达 L3：整条传导链按可验证假设对待，禁止写成确定性结论")
    return brief
