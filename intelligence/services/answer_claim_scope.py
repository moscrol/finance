"""口径越界 lint：答案说得比证据宽的四种确定性形状。

来源是 2026-09-21 K3 写手 / 无判官首跑留证的四条实测反例（见
`docs/verification/2026-09-22-k3-acceptance/`）：把库内最新日期说成"最近一个
已收盘交易日"、只比较 5 个板块却称跑赢"所有归属板块"、用成交额推断"资金集中
流入"、材料已写"亿元"仍称未注明单位。四条都不是算错，是**结论的适用范围超出
了这次实际取到的证据**。

与邻居的分工：`honesty_gates` 管数值本身脏不脏，`conclusion_five_element_lint`
管结论段结构缺不缺，本模块只管"这句话的适用范围有没有超过证据的适用范围"。

**这是四个已知形状的检出器，不是内容质量评分器，也不是判官替代品。**
它只认关键词和取数上下文：换一种说法绕过它很容易（漏报），把不同指标的单位
缺口误判成同一个也可能（误报）。它能给的只有一件事——这四条实测反例再犯时
必被机器抓住，不必等人逐句读。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

RULE_LATEST_TRADING_DAY = "latest_trading_day_unverified"
RULE_SCOPE_OVERREACH = "scope_claim_exceeds_comparison"
RULE_FUND_FLOW = "fund_flow_claim_without_flow_evidence"
RULE_UNIT_GAP = "unit_gap_claim_contradicts_input"

RULE_LABELS = {
    RULE_LATEST_TRADING_DAY: "库内日期冒充最近交易日",
    RULE_SCOPE_OVERREACH: "范围结论超出实际比较",
    RULE_FUND_FLOW: "无资金流证据推断资金方向",
    RULE_UNIT_GAP: "称缺单位但输入已给单位",
}
RULE_ORDER = (
    RULE_LATEST_TRADING_DAY,
    RULE_SCOPE_OVERREACH,
    RULE_FUND_FLOW,
    RULE_UNIT_GAP,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?；;])|\n")
_WHITESPACE = re.compile(r"\s+")
_QUOTE_LIMIT = 80

# R1：断言某日是"最近/最新交易日"。日历事实来自交易日历，不来自 fact 表的
# max(trade_date)——库里最后一行只能证明"我们存到这儿"，不能证明"市场停在这儿"。
_LATEST_TRADING_DAY = re.compile(
    r"(?:最近|最新|最后|上一个)(?:一个)?(?:已)?(?:收盘)?(?:的)?(?:交易日|收盘日)"
)
_DATA_SCOPE_QUALIFIER = re.compile(
    r"库内|本地库|数据库(?:内|中)|库中|已入库|落库|入库(?:的)?最新|"
    r"可用(?:的)?(?:最新)?数据|数据截至|截至库|现有数据|"
    # 截至具体日期、或明写快照口径的，都已把适用范围限住
    r"截至\s*20\d{2}|(?:历史|盘面)?快照|快照日"
)
# 否定句（"不能视为最新交易日复盘"）说的正是本规则要的话，不能倒扪。
# 这条是拿仓内已归档答案做校准时实测出来的误报。
_LATEST_DAY_NEGATION = re.compile(
    r"不(?:能|可|应|得)?(?:视为|当作|等同|代表|等于)|并非|不是最新|非最新|"
    r"尚未(?:收盘|更新)|不属于最新"
)

# R2：全称范围词 + 范围名词。"跑赢所有归属板块"要求分母是全部归属，
# 而这次只取了其中几个。
_SCOPE_UNIVERSAL = re.compile(
    r"(?:所有|全部|各个|每(?:一)?个|所属(?:的)?全部)(?:归属|所属|相关)?(?:的)?"
    r"(?:板块|行业|指数|同行|可比公司|成分股)"
)
_SCOPE_BOUNDED = re.compile(
    r"已(?:比较|对比|查询|取数|核对|覆盖)|所(?:查|取|比)|抽样|纳入(?:比较|对比)|"
    r"本次(?:比较|对比|取数)|样本内"
)

# R3：资金方向是净额口径（买入额-卖出额），成交额和量能放大推不出方向。
_FUND_FLOW_CLAIM = re.compile(
    r"(?:资金|主力|北向|游资|机构)"
    r"(?:[，、]?(?:大幅|明显|持续|集中|单日|当日|显著|加速|小幅)){0,3}"
    r"(?:净)?(?:流入|流出|撤离|回流|抢筹)|净(?:流入|流出)"
)
_FUND_FLOW_DISCLAIMER = re.compile(
    r"未(?:取|查|拉|验证)(?:得)?(?:到)?(?:资金|流向|净额)|无资金流(?:向|数据|证据)|"
    r"缺(?:少)?资金流|不能据此(?:判断|推断)|非资金流"
)

# R4：声称输入缺单位。币种（人民币/美元）与数量单位（亿元/万元）是两件事，
# 只有当声明里带"单位"且输入确实给了单位时才算矛盾。
# 缺口清单常是长句（"未注明公告日期、……及币种单位"），所以窗口放到 30 字；
# 同时要求"单位"后不再接汉字，否则"单位成本""单位投资额"这类指标名
# 会被当成单位缺口（两者都在真实首跑里出现过）。
_UNIT_GAP_CLAIM = re.compile(
    r"(?:未|没有|无|缺(?:少|失)?)(?:明确)?(?:注明|标注|标明|说明|给出|提供|交代)"
    r"[^。；！？\n]{0,30}?单位(?=[的，。；：、！？\s)）\]]|$)"
    r"|单位(?:未|不|没)(?:明确|注明|说明|详|知)"
)
_UNIT_TOKEN = re.compile(r"亿元|万元|亿股|万股|元/股|百万元|千元|人民币元|(?<!\w)元(?!/)")


@dataclass(frozen=True)
class ClaimEvidenceContext:
    """这次作答实际够得着的证据边界，全部由调用方从留证里解析。

    字段都允许 None/False：拿不到就当"没有这类证据"，宁可提示也不默认放行。
    """

    question: str = ""
    evidence_dates: tuple[str, ...] = ()
    calendar_evidence: bool = False
    compared_scope_count: int | None = None
    known_scope_total: int | None = None
    fund_flow_evidence: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_length": len(self.question),
            "evidence_dates": list(self.evidence_dates),
            "calendar_evidence": self.calendar_evidence,
            "compared_scope_count": self.compared_scope_count,
            "known_scope_total": self.known_scope_total,
            "fund_flow_evidence": self.fund_flow_evidence,
        }


@dataclass(frozen=True)
class ClaimIssue:
    rule: str
    label: str
    quote: str
    reason: str
    remedy: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "label": self.label,
            "quote": self.quote,
            "reason": self.reason,
            "remedy": self.remedy,
        }


@dataclass
class ClaimScopeReport:
    issues: list[ClaimIssue] = field(default_factory=list)
    context: ClaimEvidenceContext = field(default_factory=ClaimEvidenceContext)
    sentences_scanned: int = 0

    @property
    def clean(self) -> bool:
        return not self.issues

    def rules_hit(self) -> list[str]:
        seen = {issue.rule for issue in self.issues}
        return [rule for rule in RULE_ORDER if rule in seen]

    def to_dict(self) -> dict[str, Any]:
        return {
            "clean": self.clean,
            "issue_count": len(self.issues),
            "rules_hit": self.rules_hit(),
            "sentences_scanned": self.sentences_scanned,
            "context": self.context.to_dict(),
            "issues": [issue.to_dict() for issue in self.issues],
            "boundary": (
                "四个已知形状的关键词检出器；干净不代表内容正确，"
                "命中也需人读原句确认"
            ),
        }


def split_sentences(text: str) -> list[str]:
    """按中文句末标点与换行切句；保留原字符，只丢空句。"""

    parts = (segment.strip() for segment in _SENTENCE_SPLIT.split(text or ""))
    return [segment for segment in parts if segment]


def _quote(sentence: str) -> str:
    collapsed = _WHITESPACE.sub(" ", sentence).strip()
    if len(collapsed) <= _QUOTE_LIMIT:
        return collapsed
    return collapsed[:_QUOTE_LIMIT] + "…"


def _latest_trading_day_issue(
    sentence: str, context: ClaimEvidenceContext
) -> ClaimIssue | None:
    if not _LATEST_TRADING_DAY.search(sentence):
        return None
    if context.calendar_evidence or _DATA_SCOPE_QUALIFIER.search(sentence):
        return None
    if _LATEST_DAY_NEGATION.search(sentence):
        return None
    dates = "、".join(context.evidence_dates[:3]) or "无"
    return ClaimIssue(
        rule=RULE_LATEST_TRADING_DAY,
        label=RULE_LABELS[RULE_LATEST_TRADING_DAY],
        quote=_quote(sentence),
        reason=(
            f"本次未取交易日历证据（证据日期：{dates}）。"
            "库内最大交易日只能证明数据存到哪天，不能证明市场最近收盘在哪天"
        ),
        remedy="改写成「库内最新可用交易日 X（数据截至…）」，或取交易日历后再断言",
    )


def _scope_issue(sentence: str, context: ClaimEvidenceContext) -> ClaimIssue | None:
    if not _SCOPE_UNIVERSAL.search(sentence):
        return None
    if _SCOPE_BOUNDED.search(sentence):
        return None
    compared = context.compared_scope_count
    total = context.known_scope_total
    if compared is None:
        return None
    if total is not None and compared >= total:
        return None
    known = f"，已知归属 {total} 个" if total is not None else "，归属全集本次未取"
    return ClaimIssue(
        rule=RULE_SCOPE_OVERREACH,
        label=RULE_LABELS[RULE_SCOPE_OVERREACH],
        quote=_quote(sentence),
        reason=f"本次只比较了 {compared} 个{known}；全称结论的分母没取到",
        remedy=f"限定为「已比较的 {compared} 个中全部…」，或补齐全集再下全称结论",
    )


def _fund_flow_issue(sentence: str, context: ClaimEvidenceContext) -> ClaimIssue | None:
    if context.fund_flow_evidence:
        return None
    if not _FUND_FLOW_CLAIM.search(sentence):
        return None
    if _FUND_FLOW_DISCLAIMER.search(sentence):
        return None
    return ClaimIssue(
        rule=RULE_FUND_FLOW,
        label=RULE_LABELS[RULE_FUND_FLOW],
        quote=_quote(sentence),
        reason="本次没有资金流向取数；成交额/量能放大是活跃度，推不出净买卖方向",
        remedy="改写成成交活跃度描述，或取资金流数据后再谈流入流出",
    )


def _unit_gap_issue(sentence: str, context: ClaimEvidenceContext) -> ClaimIssue | None:
    if not _UNIT_GAP_CLAIM.search(sentence):
        return None
    found = _UNIT_TOKEN.search(context.question or "")
    if not found:
        return None
    return ClaimIssue(
        rule=RULE_UNIT_GAP,
        label=RULE_LABELS[RULE_UNIT_GAP],
        quote=_quote(sentence),
        reason=f"题面/材料已给数量单位「{found.group(0)}」，该缺口声明与输入矛盾",
        remedy="币种未知就只说币种未知，不要扩大成单位未知",
    )


_RULE_CHECKS = (
    _latest_trading_day_issue,
    _scope_issue,
    _fund_flow_issue,
    _unit_gap_issue,
)


def review_answer_claims(
    answer: str, context: ClaimEvidenceContext | None = None
) -> ClaimScopeReport:
    """逐句检四类口径越界；命中给出原句、理由与改写方向。

    同一 (规则, 原句) 只报一次；输出顺序固定为原文出现顺序，便于回归对比。
    """

    resolved = context or ClaimEvidenceContext()
    sentences = split_sentences(answer)
    issues: list[ClaimIssue] = []
    seen: set[tuple[str, str]] = set()
    for sentence in sentences:
        for check in _RULE_CHECKS:
            issue = check(sentence, resolved)
            if issue is None:
                continue
            key = (issue.rule, issue.quote)
            if key in seen:
                continue
            seen.add(key)
            issues.append(issue)
    return ClaimScopeReport(
        issues=issues, context=resolved, sentences_scanned=len(sentences)
    )


def summarize_issues(issues: Iterable[ClaimIssue]) -> list[str]:
    """给人读的一行式摘要，供 CLI / 交接文档直接引用。"""

    return [f"{issue.label}：{issue.quote} —— {issue.reason}" for issue in issues]
