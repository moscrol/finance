"""公司证据缺口雷达（P1-7）：知道某公司重要，但不知道缺什么证据.

对应 docs/learning/finance-agent-skill-expansion-brainstorm.md P1-7：
对一家公司的现有证据链做六个维度的缺口扫描，输出「缺什么 + 对应候选
研究任务」，支持人工研究优先级排序，可与知识库 ingest 队列对接。

人工边界（红线）：只生成缺口和候选任务，不自动写实体正文、不自动入库。

六个维度：
- baseline：主营/收入结构/毛利等基础画像
- revenue_structure：收入结构与题材相关业务占比
- customer：客户验证/导入证据
- official：公告/互动易等 L3 官方证据
- chain_comparison：同链对比（更强核心/替代标的/上游瓶颈）
- market_value：盘面市场价值验证（CAR/相对强度/新高/承接）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DIM_BASELINE = "baseline"
DIM_REVENUE = "revenue_structure"
DIM_CUSTOMER = "customer"
DIM_OFFICIAL = "official"
DIM_CHAIN = "chain_comparison"
DIM_MARKET = "market_value"

GAP_DIMENSIONS = [DIM_BASELINE, DIM_REVENUE, DIM_CUSTOMER, DIM_OFFICIAL, DIM_CHAIN, DIM_MARKET]

# 维度 → (命中特征词, 缺口描述, 候选任务)
_DIMENSION_RULES: dict[str, tuple[tuple[str, ...], str, str]] = {
    DIM_BASELINE: (
        ("主营", "基础画像", "baseline", "行业分类", "产业链位置"),
        "缺公司 baseline（主营/产业链位置）",
        "补 multi-source baseline：年报/定期报告/iFinD/AKShare 的主营与行业分类（人工 review 后入库）",
    ),
    DIM_REVENUE: (
        ("收入结构", "营收占比", "收入占比", "毛利", "业务占比"),
        "缺收入结构与毛利弹性：无法判断题材业务是否构成利润弹性",
        "从年报分业务收入表提取题材相关业务占比与毛利率（生成候选，不自动写实体）",
    ),
    DIM_CUSTOMER: (
        ("客户", "导入", "送样", "验证", "供应关系"),
        "缺客户证据：受益逻辑停留在'有产品'，未确认'有客户'",
        "查互动易/公告/调研纪要里的客户导入与送样验证记录（disclosure-archive 补查）",
    ),
    DIM_OFFICIAL: (
        ("公告", "互动易", "中标", "订单", "认证", "量产"),
        "缺 L3 官方证据：公告/互动易/订单/认证均未命中，逻辑高度受限",
        "跑 L3 运行时补查（ask --l3-lookup）或 disclosure-archive，生成候选 source note 供人工复核",
    ),
    DIM_CHAIN: (
        ("同链", "同题材", "替代", "上游", "对比", "二阶导"),
        "缺同链对比：无法判断它是不是该题材最优表达",
        "用 theme-radar deep-dive 拉同题材核心层/替代标的/上游瓶颈做横向对比",
    ),
    DIM_MARKET: (
        ("相对强度", "新高", "涨停", "承接", "CAR", "回撤", "双红", "边际量"),
        "缺市场价值验证：没有盘面确认，产业逻辑再好也只是候选",
        "接 D1/D4 数据块看 CAR、相对强度、新高/涨停与成交承接",
    ),
}


@dataclass
class GapRadarReport:
    company: str
    covered: list[str] = field(default_factory=list)  # 已有证据的维度
    gaps: list[str] = field(default_factory=list)  # 缺口维度
    gap_notes: list[str] = field(default_factory=list)  # 缺口描述
    candidate_tasks: list[str] = field(default_factory=list)  # 人工任务队列候选

    @property
    def coverage_rate(self) -> float:
        return round(len(self.covered) / len(GAP_DIMENSIONS), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "company": self.company,
            "covered": list(self.covered),
            "gaps": list(self.gaps),
            "gap_notes": list(self.gap_notes),
            "candidate_tasks": list(self.candidate_tasks),
            "coverage_rate": self.coverage_rate,
        }

    def to_prompt_block(self) -> str:
        lines = [
            "## 公司证据缺口雷达（只生成缺口与候选任务，不自动写库）",
            f"- 公司：{self.company}｜维度覆盖率：{self.coverage_rate:.0%}（{len(self.covered)}/{len(GAP_DIMENSIONS)}）",
        ]
        for note in self.gap_notes:
            lines.append(f"- ⚠️{note}")
        for task in self.candidate_tasks:
            lines.append(f"- 候选任务：{task}")
        if not self.gap_notes:
            lines.append("- 六维证据齐备：优先复核证据新鲜度而非补量")
        return "\n".join(lines)


def scan_evidence_gaps(company: str, evidence_lines: list[str] | None) -> GapRadarReport:
    report = GapRadarReport(company=company)
    text = "\n".join(str(x or "") for x in (evidence_lines or []))
    for dim in GAP_DIMENSIONS:
        terms, gap_note, task = _DIMENSION_RULES[dim]
        if any(t in text for t in terms):
            report.covered.append(dim)
        else:
            report.gaps.append(dim)
            report.gap_notes.append(gap_note)
            report.candidate_tasks.append(task)
    return report
