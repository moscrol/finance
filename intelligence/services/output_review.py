"""Review 层候选审稿助手（手册§三第4层）：回答前六项确定性检查.

对应 docs/learning/finance-agent-skill-expansion-brainstorm.md §三 Review Layer：
回答前检查——

1. 是否用了本地最新数据
2. 是否区分事实/推演/盘面/经验
3. 是否有反证
4. 是否有缺口
5. 是否有可验证假设
6. 是否把弱证据写成硬事实

与 answer_quality 的区别：answer_quality 是"提示词引导"（把质检清单塞给
LLM 让它自查，柔性）；本模块是确定性闸门（对最终 AskResult 的结构化产物
逐项判 PASS/WARN，可测试、可统计）。两层互补——面试可讲：LLM 应用
的质量保障要"prompt 引导 + 程序化 gate"双层，只靠 prompt 无法保证稳定性。

只读检查、不修改回答内容；WARN 不阻断输出。该规则集尚未通过历史盲测证明
能区分预测 hit/miss，只能提供候选审稿意见，不能充当评分裁判或自动硬闸门。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from intelligence.services.research_brief import CounterEvidencePlan, EvidenceAudit

PASS = "PASS"
WARN = "WARN"

CHECK_ORDER = [
    "本地数据新鲜度",
    "证据分层",
    "反证",
    "缺口显式化",
    "可验证假设",
    "弱证据硬写",
]

# 交易日超过该天数视为陈旧（复盘数据通常 T+0/T+1 落库）
FRESH_DAYS = 7


@dataclass
class ReviewCheck:
    name: str
    status: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "note": self.note}


@dataclass
class OutputReviewGate:
    checks: list[ReviewCheck] = field(default_factory=list)
    decision_role: str = "advisory_review"
    blocking: bool = False

    @property
    def status(self) -> str:
        return WARN if any(c.status == WARN for c in self.checks) else PASS

    @property
    def warn_count(self) -> int:
        return sum(1 for c in self.checks if c.status == WARN)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "decision_role": self.decision_role,
            "blocking": self.blocking,
            "checks": [c.to_dict() for c in self.checks],
        }

    def summary_lines(self) -> list[str]:
        lines = [
            f"输出质检助手：{self.status}（{len(self.checks) - self.warn_count}/{len(self.checks)} 项通过；仅提示，不阻断）"
        ]
        for c in self.checks:
            mark = "✓" if c.status == PASS else "⚠️"
            lines.append(f"{mark} {c.name}：{c.note}" if c.note else f"{mark} {c.name}")
        return lines


def _check_freshness(trade_date: str | None, today: date | None) -> ReviewCheck:
    name = CHECK_ORDER[0]
    if not trade_date:
        return ReviewCheck(name, WARN, "未拿到本地交易日：回答未挂到任何盘面数据日期")
    try:
        td = datetime.strptime(trade_date[:10], "%Y-%m-%d").date()
    except ValueError:
        return ReviewCheck(name, WARN, f"交易日格式异常：{trade_date}")
    ref = today or date.today()
    age = (ref - td).days
    if age > FRESH_DAYS:
        return ReviewCheck(name, WARN, f"盘面数据停在 {trade_date}（{age} 天前），需先同步再下结论")
    return ReviewCheck(name, PASS, f"盘面数据 {trade_date}")


def _check_layering(audit: EvidenceAudit | None) -> ReviewCheck:
    name = CHECK_ORDER[1]
    if audit is None or not audit.items:
        return ReviewCheck(name, WARN, "证据链为空或未经分层审计")
    layers = sorted(k for k, v in audit.layer_counts.items() if v)
    return ReviewCheck(name, PASS, f"已分层：{'/'.join(layers)}，裁定={audit.verdict}")


def _check_counterevidence(plan: CounterEvidencePlan | None) -> ReviewCheck:
    name = CHECK_ORDER[2]
    if plan is None or not plan.rebuttals:
        return ReviewCheck(name, WARN, "未生成最强反证：回答仍是单边观点")
    return ReviewCheck(name, PASS, f"反证 {len(plan.rebuttals)} 条 + 降级触发 {len(plan.downgrade_triggers)} 条")


def _check_gaps(gap_lines: list[str] | None) -> ReviewCheck:
    name = CHECK_ORDER[3]
    if not gap_lines:
        return ReviewCheck(name, WARN, "无显式缺口：要么证据真的齐备，要么缺口没被暴露——先怀疑后者")
    return ReviewCheck(name, PASS, f"显式缺口 {len(gap_lines)} 条")


def _check_verifiable(follow_ups: list[str] | None) -> ReviewCheck:
    name = CHECK_ORDER[4]
    items = [x for x in (follow_ups or []) if any(t in str(x) for t in ("T+", "验证", "确认"))]
    if not items:
        return ReviewCheck(name, WARN, "无可验证假设：结论无法在 T+1/T+3/T+5 被检验")
    return ReviewCheck(name, PASS, f"可验证点 {len(items)} 条")


_HARD_CLAIM_TERMS = ("确定", "必然", "已证实", "板上钉钉", "毫无疑问")


def _check_overclaim(audit: EvidenceAudit | None, conclusion_lines: list[str] | None) -> ReviewCheck:
    name = CHECK_ORDER[5]
    text = "\n".join(str(x or "") for x in (conclusion_lines or []))
    hard_words = [t for t in _HARD_CLAIM_TERMS if t in text]
    no_l3 = audit is not None and not audit.has_l3
    if no_l3 and hard_words:
        return ReviewCheck(name, WARN, f"无 L3 硬证据却出现确定性措辞：{'、'.join(hard_words)}")
    if no_l3 and audit is not None and audit.verdict in ("预期交易", "情绪脉冲"):
        return ReviewCheck(name, PASS, f"无 L3：结论已限定在'{audit.verdict}'档，未越级")
    return ReviewCheck(name, PASS, "未发现弱证据硬写")


def review_output(
    *,
    trade_date: str | None,
    audit: EvidenceAudit | None,
    counter_plan: CounterEvidencePlan | None,
    gap_lines: list[str] | None,
    follow_ups: list[str] | None,
    conclusion_lines: list[str] | None,
    today: date | None = None,
) -> OutputReviewGate:
    gate = OutputReviewGate()
    gate.checks.append(_check_freshness(trade_date, today))
    gate.checks.append(_check_layering(audit))
    gate.checks.append(_check_counterevidence(counter_plan))
    gate.checks.append(_check_gaps(gap_lines))
    gate.checks.append(_check_verifiable(follow_ups))
    gate.checks.append(_check_overclaim(audit, conclusion_lines))
    return gate
