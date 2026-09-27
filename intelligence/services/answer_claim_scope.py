"""口径越界 lint：识别答案说得比本轮证据宽的已知形状。

来源是 2026-09-21 K3 写手 / 无判官首跑留证的四条实测反例（见
`docs/verification/2026-09-22-k3-acceptance/`）：把库内最新日期说成"最近一个
已收盘交易日"、只比较 5 个板块却称跑赢"所有归属板块"、用成交额推断"资金集中
流入"、材料已写"亿元"仍称未注明单位。四条都不是算错，是**结论的适用范围超出
了这次实际取到的证据**。

与邻居的分工：`honesty_gates` 管数值本身脏不脏，`conclusion_five_element_lint`
管结论段结构缺不缺，本模块只管"这句话的适用范围有没有超过证据的适用范围"。

另覆盖历史窗口方向、终点收益误作途中路径、板块择优缺少筛选口径。
这些规则是有限的确定性提示，不是内容质量评分器，也不是判官替代品。
它只认关键词和取数上下文：换一种说法绕过它很容易（漏报），把不同指标的单位
缺口误判成同一个也可能（误报）。它能给的只有一件事——已覆盖的实测反例再犯时
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
    "claim_direction_mismatch",
    "historical_path_unverified",
    "selection_criteria_missing",
)

# 证据判定按**注册表事实**，不按对 payload 做子串匹配：后者任何一段文本
# （例如 kb_search 的检索词里写了「交易日历」）都能把证据判成"取过"，规则
# 随即静默。下面两组常量 2026-09-22 从 finance_query 注册表枚举，
# RegistryFactTests 会在注册表漂移时变红。
#
# finance_query 里承载资金**方向**的指标（成交额/量能不在其列）。
FUND_FLOW_METRICS = frozenset(
    {
        "fund_flow_today",  # core_stock_daily
        "net_amount",  # dragon_tiger_daily
        "net_inflow_1d",  # mainline_sector_daily
        "fund_flow_1d",  # sector_stock_daily / theme_limit_stock_daily
        "fund_flow_5d",  # sector_stock_daily
        "fund_today",  # stock_high_daily
    }
)

# finance_query **没有**交易日历 dataset：日历事实只在
# `market_feature_store/trading_days.py`，agent 的工具面够不着。所以
# calendar_evidence 不可能从 episode 自动推出，只能由调用方显式声明来源。
# 这个空集合是事实陈述，不是待填的 TODO。
CALENDAR_DATASETS: frozenset[str] = frozenset()

_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?；;])|\n")
_WHITESPACE = re.compile(r"\s+")
_QUOTE_LIMIT = 80

# R1：断言某日是"最近/最新交易日"。日历事实来自交易日历，不来自 fact 表的
# max(trade_date)——库里最后一行只能证明"我们存到这儿"，不能证明"市场停在这儿"。
_LATEST_TRADING_DAY = re.compile(
    r"(?:最近|最新|最后|上一个)(?:一个)?(?:已)?(?:收盘)?(?:的)?(?:交易日|收盘日)"
)
# 限定必须**紧挨断言**才算数。原先只要整句任意位置出现「数据截至」「快照」
# 就放行，于是 `数据截至 2026-09-18（最近一个已收盘交易日）`——越界断言一字
# 未改——直接静默（2026-09-22 审查探针实测）。更糟的是本模块给出的 remedy
# 正把写手往「（数据截至…）」引导，等于教人把红灯写成绿灯。改判为：断言短语
# 前 12 字内出现范围限定词，才算这次断言被限住。
_CLAIM_BINDING_WINDOW = 12
# 「可得」是拿 1347 个历史 run 压出来的：真实答案里大量写「本轮可得的最近一个
# 已收盘交易日」「当前可得的最新已收盘交易日」——限定得干净，只是词表没收。
_SCOPE_BINDING = re.compile(
    r"库内|本地库|数据库(?:内|中)|库中|已入库|落库|入库|可用|可得|"
    r"现有数据|样本内"
)
# 否定句（"不能视为最新交易日复盘"）说的正是本规则要的话，不能倒扪。
# 这条是拿仓内已归档答案做校准时实测出来的误报。
_LATEST_DAY_NEGATION = re.compile(
    r"不(?:能|可|应|得)?(?:视为|当作|等同|代表|等于)|并非|不是最新|非最新|"
    r"尚未(?:收盘|更新)|不属于最新"
)
# 「是否为最近一个已收盘交易日无法确认」正是本规则想要的写法，却被当成断言
# （2026-09-23 第二方审查探针）。免责必须**紧跟断言短语**（同一子句内 ≤8 字）
# 才算：若把「无法确认」收进句级词表，「X 为最近一个已收盘交易日，但成交额
# 无法确认」这种对别的对象免责的句子也会静默——又是一个 fail-open。
_LATEST_DAY_HEDGE_AFTER = re.compile(
    r"^[^，,。；;！!？?]{0,8}(?:无法|无从|不能|难以|尚未|未能)"
    r"(?:确认|核验|核实|确定|判断|验证|核对)"
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
    r"(?:净)?(?:流入|流出|撤离|回流|抢筹)|净(?:流入|流出)|"
    # 迁移类说法是 1347 run 召回探针抓出的漏报：「存量资金内部腾挪而非
    # 增量进场」「存量资金从权重撤出」——同样是拿量能推资金方向，只是换了
    # 动词。主语与动词间允许 6 字（「资金**内部**腾挪」）。不收「加仓/减仓」：
    # 回测里那 31 句全是给用户的仓位建议，不是对市场资金方向的断言。
    r"(?:资金|主力|北向|游资|机构|筹码)[^。；！？\n]{0,6}"
    r"(?:腾挪|搬家|进场|入场|撤出|转移|涌入|出逃)"
)
# 免责词表是拿 1347 个历史 run 压出来的（见
# docs/verification/2026-09-22-claim-scope-backtest）：原词表只认「未取/无资金流」，
# 而真实答案里自陈缺数据的写法还有「未查得…不做断言」「无法核验」「未支持：」
# 「需要补充…证据」——这些正是规则想要的行为，误报它们等于惩罚诚实。
_FUND_FLOW_DISCLAIMER = re.compile(
    r"未(?:取|查|拉|验证)(?:得)?(?:到)?(?:资金|流向|净额)|无资金流(?:向|数据|证据)|"
    r"缺(?:少)?资金流|不能据此(?:判断|推断)|非资金流|"
    r"未(?:查|取|获|返回|检索)得?|无法核验|未支持|无法区分|均不成立|"
    r"不(?:做|作|能)(?:断言|判断|归因)|"
    r"需要?补充.{0,12}证据|本轮缺失|尚无.{0,6}数据|"
    # 反驳句：句子在论证「这个资金结论立不住」，比如「日线先后不足以说资金
    # 转移」「『资金转移』不是唯一解释」——报它们等于反对说真话。
    r"不足以|不构成|不能.{0,4}证明|不是唯一|未建立|待核验|"
    r"不成立|撤回|不是典型|反证|竞争性?解释|也可解释为|方向相反"
)
# 引号里的是被**讨论**的口号，不是本句的断言：「『成交增加=新增资金入场』
# 不成立」、「『存量资金腾挪放大换手』——撤回」。堆词表追不完这些写法，
# 用结构判据：句中所有资金短语都落在引号内，就是提及而非断言。
_QUOTED_SPAN = re.compile(r"[「『“\"][^」』”\"]*[」』”\"]")
# 「大单净流入**扫描榜单**」「板块级资金净流入**字段**」是榜单/字段的**名字**，
# 不是方向断言。与本模块早先处理「单位成本」是指标名同一类问题；
# 2026-09-22 的日期类管辖差分测试把它当场抓住。
_DATASET_NOUN = re.compile(r"^(?:榜单|扫描|排行|排名|名单|明细|数据|字段|指标|口径|表)")
# 设问句不是断言：「成交增加能否证明新增资金入场？」是小标题，不是结论。
_INTERROGATIVE = re.compile(r"[？?]\s*$|(?:能否|是否|可否|吗)[^。！\n]{0,20}[？?]")

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
    historical_endpoint_returns: tuple[tuple[str, str, int, float], ...] = ()
    observed_sector_names: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_length": len(self.question),
            "evidence_dates": list(self.evidence_dates),
            "calendar_evidence": self.calendar_evidence,
            "compared_scope_count": self.compared_scope_count,
            "known_scope_total": self.known_scope_total,
            "fund_flow_evidence": self.fund_flow_evidence,
            "historical_endpoint_returns": [list(item) for item in self.historical_endpoint_returns],
            "observed_sector_names": list(self.observed_sector_names),
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
                "已知形状与已映射证据的有限检出器；干净不代表内容正确，"
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


# 管辖边界：本规则只管**无真值可比**时的越界断言。若块层带着真实扫描日、
# 答案把旧数据写成「当日」，那是 `output_review._check_stale_mislabel` 的事实核对，
# 不归这里。差分测试见 intelligence/tests/test_date_claim_jurisdiction.py。
def _latest_trading_day_issue(
    sentence: str, context: ClaimEvidenceContext
) -> ClaimIssue | None:
    matches = list(_LATEST_TRADING_DAY.finditer(sentence))
    if not matches:
        return None
    if context.calendar_evidence:
        return None
    if _LATEST_DAY_NEGATION.search(sentence):
        return None
    # 一句里可能出现多次断言；每一次都得被紧邻限定住、或紧跟着免责，才算限住。
    if all(
        _SCOPE_BINDING.search(
            sentence[max(0, match.start() - _CLAIM_BINDING_WINDOW) : match.start()]
        )
        or _LATEST_DAY_HEDGE_AFTER.search(sentence[match.end() :])
        for match in matches
    ):
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


def scope_comparison_needed(answer: str) -> bool:
    """Whether this answer contains an unbounded universal scope claim."""
    return any(
        _SCOPE_UNIVERSAL.search(sentence) and not _SCOPE_BOUNDED.search(sentence)
        for sentence in split_sentences(answer)
    )


def _scope_issue(sentence: str, context: ClaimEvidenceContext) -> ClaimIssue | None:
    if not scope_comparison_needed(sentence):
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
    if _FUND_FLOW_DISCLAIMER.search(sentence) or _INTERROGATIVE.search(sentence):
        return None
    claims = [
        match
        for match in _FUND_FLOW_CLAIM.finditer(sentence)
        if not _DATASET_NOUN.match(sentence[match.end() :])
    ]
    if not claims:
        return None
    quoted = [m.span() for m in _QUOTED_SPAN.finditer(sentence)]
    if claims and all(
        any(start <= claim.start() and claim.end() <= end for start, end in quoted)
        for claim in claims
    ):
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
    """检查已知口径越界；命中给出原句、理由与改写方向。

    同一 (规则, 原句) 只报一次；基础规则在前，研究规则在后，顺序稳定。
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
    from intelligence.services.research_claim_scope import research_claim_issues

    for issue in research_claim_issues(answer, resolved):
        key = (issue.rule, issue.quote)
        if key not in seen:
            seen.add(key)
            issues.append(issue)
    return ClaimScopeReport(
        issues=issues, context=resolved, sentences_scanned=len(sentences)
    )


def summarize_issues(issues: Iterable[ClaimIssue]) -> list[str]:
    """给人读的一行式摘要，供 CLI / 交接文档直接引用。"""

    return [f"{issue.label}：{issue.quote} —— {issue.reason}" for issue in issues]
