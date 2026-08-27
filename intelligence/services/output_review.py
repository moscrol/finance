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

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

from intelligence.services.conclusion_five_element_lint import (
    ELEMENT_LABELS,
    lint_conclusion_five_elements,
)
from intelligence.services.research_brief import CounterEvidencePlan, EvidenceAudit

# 数据块「时点限定（先读）」行的机器可读形状（当前只有 D9 采用；
# 任何块照这个措辞发限定行，就自动进入时点错标检查的覆盖面）。
STALE_HINT_RE = re.compile(r"最新扫描日 (\d{4}-\d{2}-\d{2}) 早于盘面日期 (\d{4}-\d{2}-\d{2})")
# 答案里这些词附近若出现盘面日期/「当日/今日」而全篇不带扫描日，判疑似错标
_STALE_TOPIC_TERMS = ("榜单", "扫描", "大单净流入", "主买净额")
_STALE_WINDOW = 40

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
    advisory_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "note": self.note,
            "advisory_only": self.advisory_only,
        }


@dataclass
class OutputReviewGate:
    checks: list[ReviewCheck] = field(default_factory=list)
    decision_role: str = "advisory_review"
    blocking: bool = False

    @property
    def status(self) -> str:
        return WARN if self.warn_count else PASS

    @property
    def warn_count(self) -> int:
        return sum(
            1
            for c in self.checks
            if c.status == WARN and not c.advisory_only
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "decision_role": self.decision_role,
            "blocking": self.blocking,
            "checks": [c.to_dict() for c in self.checks],
        }

    def summary_lines(self) -> list[str]:
        actionable = [check for check in self.checks if not check.advisory_only]
        passed = sum(1 for check in actionable if check.status == PASS)
        lines = [
            f"输出质检助手：{self.status}（{passed}/{len(actionable)} 项通过；"
            "结论五元素只提示，不阻断、不进修订轮）"
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
_BOUNDED_CERTAINTY_TERMS = (
    "无法确定",
    "尚未确定",
    "不能确定",
    "难以确定",
    "不确定",
    "未确定",
    "待确定",
    "确定性",
)


def _check_overclaim(audit: EvidenceAudit | None, conclusion_lines: list[str] | None) -> ReviewCheck:
    name = CHECK_ORDER[5]
    text = "\n".join(str(x or "") for x in (conclusion_lines or []))
    claim_text = text
    for term in _BOUNDED_CERTAINTY_TERMS:
        claim_text = claim_text.replace(term, "")
    hard_words = [t for t in _HARD_CLAIM_TERMS if t in claim_text]
    no_l3 = audit is not None and not audit.has_l3
    if no_l3 and hard_words:
        return ReviewCheck(name, WARN, f"无 L3 硬证据却出现确定性措辞：{'、'.join(hard_words)}")
    if no_l3 and audit is not None and audit.verdict in ("预期交易", "情绪脉冲"):
        return ReviewCheck(name, PASS, f"无 L3：结论已限定在'{audit.verdict}'档，未越级")
    return ReviewCheck(name, PASS, "未发现弱证据硬写")


def extract_stale_block_hints(
    blocks: Iterable[tuple[str, str]],
) -> tuple[tuple[str, str, str], ...]:
    """从数据块文本抽「时点限定」：(tag, 扫描日, 盘面日期)。无限定行的块不产出。"""

    hints: list[tuple[str, str, str]] = []
    for tag, text in blocks:
        match = STALE_HINT_RE.search(text or "")
        if match:
            hints.append((str(tag), match.group(1), match.group(2)))
    return tuple(hints)


def _check_stale_mislabel(
    final_answer: str | None,
    hints: tuple[tuple[str, str, str], ...],
) -> list[ReviewCheck]:
    """时点错标嗅探（只提示不阻断）。

    2026-08-26 blk-d9 实测形状：块层带「最新扫描日 2026-08-07」，LLM 合成层
    丢掉限定语、把 19 天前的榜单写成「2026-08-26 当日的大单净流入扫描榜单」。
    判定：答案在榜单/扫描类词 ±40 字内出现盘面日期或「当日/今日」，且全篇
    不含真实扫描日 → 疑似错标。列名「当日名次」豁免。观察一段在场率后再议
    是否升格进修订轮（同 KC-13 五元素 lint 的推进方式）。
    """

    checks: list[ReviewCheck] = []
    text = str(final_answer or "")
    for tag, scan_date, as_of in hints:
        name = f"时点错标·{tag}"
        if not text:
            continue
        if scan_date in text:
            checks.append(
                ReviewCheck(name, PASS, f"已带扫描日 {scan_date}", advisory_only=True)
            )
            continue
        suspicious = False
        for term in _STALE_TOPIC_TERMS:
            for match in re.finditer(re.escape(term), text):
                lo = max(0, match.start() - _STALE_WINDOW)
                window = text[lo : match.end() + _STALE_WINDOW]
                if "当日名次" in window:
                    continue
                if as_of in window or "当日" in window or "今日" in window:
                    suspicious = True
                    break
            if suspicious:
                break
        if suspicious:
            checks.append(
                ReviewCheck(
                    name,
                    WARN,
                    f"疑似把 {scan_date} 的 {tag} 数据表述为当日（盘面日期 {as_of}），"
                    f"且正文未出现扫描日（只提示，不进修订轮）",
                    advisory_only=True,
                )
            )
        else:
            checks.append(
                ReviewCheck(
                    name,
                    WARN,
                    f"正文未写明 {tag} 扫描日 {scan_date}（未见当日化表述；只提示）",
                    advisory_only=True,
                )
            )
    return checks


def review_output(
    *,
    trade_date: str | None,
    audit: EvidenceAudit | None,
    counter_plan: CounterEvidencePlan | None,
    gap_lines: list[str] | None,
    follow_ups: list[str] | None,
    conclusion_lines: list[str] | None,
    final_answer: str | None = None,
    today: date | None = None,
    stale_block_hints: tuple[tuple[str, str, str], ...] = (),
) -> OutputReviewGate:
    gate = OutputReviewGate()
    gate.checks.append(_check_freshness(trade_date, today))
    gate.checks.append(_check_layering(audit))
    gate.checks.append(_check_counterevidence(counter_plan))
    gate.checks.append(_check_gaps(gap_lines))
    gate.checks.append(_check_verifiable(follow_ups))
    visible_lines = [final_answer] if final_answer else conclusion_lines
    gate.checks.append(_check_overclaim(audit, visible_lines))
    gate.checks.extend(_five_element_checks(visible_lines))
    gate.checks.extend(_check_stale_mislabel(final_answer, stale_block_hints))
    return gate


def _five_element_checks(visible_lines: list[str] | None) -> list[ReviewCheck]:
    text = "\n".join(str(item or "") for item in (visible_lines or []))
    lint = lint_conclusion_five_elements(text)
    checks: list[ReviewCheck] = []
    present = set(lint.present_ids)
    for element_id, label in ELEMENT_LABELS.items():
        name = f"结论五元素·{label}"
        if element_id in present:
            checks.append(ReviewCheck(name, PASS, f"在场：{label}", advisory_only=True))
        else:
            checks.append(
                ReviewCheck(name, WARN, f"缺{label}（只提示，不进修订轮）", advisory_only=True)
            )
    return checks
