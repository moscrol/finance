"""Deterministic finance-answer structure review.

The keyword rubric finds missing sections; it does not measure prediction
quality or reasoning correctness. It is deterministic by design: no LLM, no
I/O, no network. Until a historical blind test shows that its scores separate
hit from miss, all outputs remain advisory and decision-ineligible.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

QUESTION_MARKET_FORECAST = "market_forecast"

# 真实证据标记：股票代码 / 日期 / 引用编号 / 带单位数字。
# 词表命中可以靠堆砌行话刷出来，这些不行——只有答案真的引了数据才会出现。
_EVIDENCE_MARKER_PATTERNS: tuple[tuple[str, str], ...] = (
    ("stock_code", r"\b\d{6}\b"),
    ("iso_date", r"\b\d{4}-\d{2}-\d{2}\b"),
    ("cn_date", r"\d{1,2}\s*月\s*\d{1,2}\s*日"),
    ("citation", r"\[[SGRW]\d+\]"),
    ("percent", r"\d+(?:\.\d+)?\s*%"),
    ("amount", r"\d+(?:\.\d+)?\s*(?:亿元|万元|亿|万)"),
)

# 拿满证据分所需的去重标记数。实测基准：一份真实题材答案 46 个标记，
# 一段只念词表、零事实的空壳 0 个。
EVIDENCE_FULL_CREDIT = 8

# 这几维都断言「答案有据可依」，所以它们的得分上限由真实证据标记密度决定。
# 不加这道闸门时，191 字的纯行话空壳能拿 91/100(A)，而 8720 字、13 个股票代码、
# 28 条引用编号的真实答案只有 60/100(D)——指标与它要测的东西反相关。
# 注：``local_data_priority`` 也在闸门内——自动评分路径（cli.py 调
# ``auto_eval.evaluate_answer``）从不传 ``local_sources``，该维度实际只在测
# 答案有没有说「本地/知识库/repo」这几个词，等于奖励「声称」而非「做到」。
EVIDENCE_GATED_KEYS: frozenset[str] = frozenset(
    {
        "local_data_priority",
        "evidence_layering",
        "market_stage",
        "industry_reasoning",
        "actionability",
    }
)

# 题型 → 该题型结构上就不产出、因而不该参与评分的维度。
# 默认 7 维全部适用；只登记确有把握的，避免拿范畴外的维度扣分——
# 对一个结构上不可能存在的东西要证据，是范畴错误，不是质量缺陷。
DIMENSION_NOT_APPLICABLE: dict[str, frozenset[str]] = {
    "concept_definition": frozenset({"market_stage", "actionability"}),
    "methodology_discussion": frozenset({"local_data_priority", "market_stage"}),
    # 取值查询的必需输出是 (fact_value, as_of_date, evidence_boundary)——见
    # task_frame。一个收盘价写不出盘面阶段、产业传导、反方审稿或交易方法论；
    # evidence_layering 测的是 L1-L4 多源分层，对单值查询同样是范畴错误。
    #
    # 于是只剩 local_data_priority（满分 15）。这是个诚实但很弱的信号：本 rubric
    # 目前没有任何一维对应 quick_fact 的真实契约（值 / 口径日期 / 证据边界）。
    # 补一个专用维度需要先定「好的取值回答长什么样」，是独立的产品判断，
    # 不在本次路由修复范围内——宁可少测，也不要拿不适用的维度扣分。
    "quick_fact": frozenset(
        {
            "evidence_layering",
            "market_stage",
            "industry_reasoning",
            "critic_review",
            "actionability",
            "personal_methodology",
        }
    ),
}


@dataclass(frozen=True)
class RubricDimension:
    key: str
    label: str
    score: int
    max_score: int
    reason: str
    hits: list[str] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        return self.score / self.max_score if self.max_score else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "score": self.score,
            "max_score": self.max_score,
            "ratio": round(self.ratio, 4),
            "reason": self.reason,
            "hits": list(self.hits),
            "misses": list(self.misses),
        }


@dataclass(frozen=True)
class FinanceAnswerScore:
    question: str
    total_score: int
    max_score: int
    grade: str
    dimensions: list[RubricDimension]
    failures: list[str] = field(default_factory=list)
    question_type: str | None = None
    role: str = "advisory_review"
    calibration_status: str = "unvalidated"
    decision_eligible: bool = False

    @property
    def percent(self) -> float:
        return self.total_score / self.max_score * 100 if self.max_score else 0.0

    def dimension(self, key: str) -> RubricDimension:
        for item in self.dimensions:
            if item.key == key:
                return item
        raise KeyError(key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "question_type": self.question_type,
            "total_score": self.total_score,
            "max_score": self.max_score,
            "percent": round(self.percent, 2),
            "grade": self.grade,
            "failures": list(self.failures),
            "dimensions": [d.to_dict() for d in self.dimensions],
            "role": self.role,
            "calibration_status": self.calibration_status,
            "decision_eligible": self.decision_eligible,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def score_answer(
    question: str,
    answer: str,
    *,
    local_sources: list[str] | None = None,
    question_type: str | None = None,
) -> FinanceAnswerScore:
    """Score one financial answer with the vertical rubric.

    ``question_type`` 与 answer_orchestrator 的题型对齐；传入
    ``market_forecast`` 时，在通用 7 维之上追加复盘/前瞻研判专用维度组，
    逐项核对编排器视角清单里「必须写到」的硬要求；登记在
    ``DIMENSION_NOT_APPLICABLE`` 里的维度则整维剔除，不计入满分。

    断言「有据可依」的维度还会过一道证据密度闸门（``EVIDENCE_GATED_KEYS``），
    上限随真实证据标记数收紧，避免只堆行话就拿高分。
    """
    text = _norm(answer)
    dims = [
        _score_local_data_priority(text, local_sources or []),
        _score_evidence_layering(text),
        _score_market_stage(text),
        _score_industry_reasoning(text),
        _score_critic_review(text),
        _score_actionability(text),
        _score_personal_methodology(text),
    ]
    if question_type == QUESTION_MARKET_FORECAST:
        dims.extend(_score_market_forecast_group(answer, text))
    skipped = DIMENSION_NOT_APPLICABLE.get(question_type or "", frozenset())
    dims = [d for d in dims if d.key not in skipped]
    marker_count = evidence_marker_count(answer)
    dims = [_apply_evidence_gate(d, marker_count) for d in dims]
    total = sum(d.score for d in dims)
    max_score = sum(d.max_score for d in dims)
    failures = [
        f"{d.label}不足：{'; '.join(d.misses) or d.reason}"
        for d in dims
        if d.ratio < 0.55
    ]
    return FinanceAnswerScore(
        question=question,
        total_score=total,
        max_score=max_score,
        grade=_grade(total, max_score),
        dimensions=dims,
        failures=failures,
        question_type=question_type,
    )


def format_score(score: FinanceAnswerScore) -> str:
    """Render advisory review hints; the score is not a decision gate."""
    lines = [
        f"# 金融回答候选审稿意见：{score.total_score}/{score.max_score}（{score.grade}）",
        "",
        "> 仅用于发现结构缺口；未经历史盲测校准，不代表预测质量，不得自动阻断或自动回灌。",
        "",
        "| 维度 | 得分 | 评语 |",
        "|---|---:|---|",
    ]
    for d in score.dimensions:
        lines.append(f"| {d.label} | {d.score}/{d.max_score} | {d.reason} |")
    if score.failures:
        lines.append("")
        lines.append("## 主要缺口")
        lines.extend(f"- {item}" for item in score.failures)
    return "\n".join(lines) + "\n"


def _score_local_data_priority(text: str, local_sources: list[str]) -> RubricDimension:
    local_marks = ("本地", "知识库", "金融 repo", "金融repo", "market_feature_store", "金融库", "repo")
    web_marks = ("web", "网页", "搜索", "外部")
    hits = _hits(text, local_marks)
    misses: list[str] = []
    if not hits:
        misses.append("未体现本地知识库/金融 repo 优先")
    if local_sources and not hits:
        score = 4
    elif hits and _web_as_primary(text):
        score = 10
    elif hits:
        score = 15
    else:
        score = 8
    reason = "体现本地知识库/金融 repo 优先" if hits else "未体现本地数据优先，容易退化成泛搜索回答"
    if _hits(text, web_marks) and not hits:
        misses.append("可能把外部搜索当主数据源")
        score = min(score, 5)
    return RubricDimension(
        "local_data_priority", "本地数据优先", score, 15, reason, hits, misses
    )


def _web_as_primary(text: str) -> bool:
    if "不把 web 当主来源" in text or "web 只" in text or "web只是" in text:
        return False
    return (
        ("web" in text or "网页" in text or "搜索" in text)
        and ("主来源" in text or "主要来源" in text or "主要依据" in text)
    )


def _score_evidence_layering(text: str) -> RubricDimension:
    layer_hits = _hits(text, ("l1", "l2", "l3", "l4"))
    # 后三个是本仓自己的规范分层词汇（见答案表格的「直接性 / 分层 / 证据状态」列
    # 与「证据边界」段）。原词表只认 L1-L4 那一套，识别不了系统实际输出的措辞，
    # 导致真实分层答案被判「缺少分层」。证据密度闸门保证补词不会变成新的刷分口。
    concept_hits = _hits(
        text,
        (
            "证据分层",
            "产业叙事",
            "基本面",
            "硬事实",
            "盘面情绪",
            "公司硬事实",
            "证据边界",
            "证据状态",
            "直接性",
        ),
    )
    score = min(15, len(set(layer_hits)) * 3 + len(concept_hits) * 2)
    if "l1-l4" in text or "l1～l4" in text or "l1/l2/l3/l4" in text:
        score = 15
    misses = []
    if score < 8:
        misses.append("缺少 L1-L4 或事实/情绪/基本面分层")
    reason = (
        "能用 L1-L4 区分产业叙事、基本面、公司硬事实和盘面情绪"
        if score >= 12
        else "证据分层较弱，容易把研报观点、公司事实和盘面情绪混在一起"
    )
    return RubricDimension(
        "evidence_layering", "证据分层", score, 15, reason, layer_hits + concept_hits, misses
    )


def _score_market_stage(text: str) -> RubricDimension:
    stage_hits = _hits(
        text,
        (
            "预期交易",
            "兑现分歧",
            "事实验证",
            "能力验证",
            "退潮",
            "利好兑现",
            "分歧",
            "情绪",
        ),
    )
    market_hits = _hits(text, ("双红", "放量", "缩量", "成交", "强势异动", "扩散", "承接", "流动性"))
    score = min(20, len(stage_hits) * 3 + len(market_hits) * 2)
    if stage_hits and len(market_hits) >= 2:
        score = max(score, 16)
    misses = []
    if not stage_hits:
        misses.append("缺少盘面阶段判断")
    if not market_hits:
        misses.append("缺少量价/双红/扩散/流动性等盘面语言")
    reason = (
        "能判断预期交易、事实验证或兑现分歧，并结合量价/扩散信号"
        if score >= 16
        else "盘面阶段判断不足，容易把利好等同于上涨"
    )
    return RubricDimension(
        "market_stage", "盘面阶段", score, 20, reason, stage_hits + market_hits, misses
    )


def _score_industry_reasoning(text: str) -> RubricDimension:
    chain_hits = _hits(text, ("一阶", "二阶", "产业链", "传导", "扩散"))
    business_hits = _hits(text, ("订单", "客户", "收入", "产能", "毛利率", "利润", "报表", "利用率"))
    score = min(15, len(chain_hits) * 3 + len(business_hits) * 2)
    if chain_hits and len(business_hits) >= 3:
        score = max(score, 13)
    misses = []
    if not chain_hits:
        misses.append("缺少一阶/二阶或产业链传导")
    if len(business_hits) < 2:
        misses.append("缺少订单/客户/收入/毛利率等财务映射")
    reason = (
        "能把题材传导到订单、客户、收入、产能和毛利率"
        if score >= 12
        else "产业推导偏弱，停留在概念罗列"
    )
    return RubricDimension(
        "industry_reasoning", "产业推导", score, 15, reason, chain_hits + business_hits, misses
    )


def _score_critic_review(text: str) -> RubricDimension:
    hits = _hits(
        text,
        (
            "反方",
            "审稿",
            "老预期",
            "被交易",
            "证伪",
            "否认",
            "风险",
            "不足",
            "替代",
            "高置信",
        ),
    )
    score = min(15, len(hits) * 2)
    if ("反方" in text or "审稿" in text) and len(hits) >= 4:
        score = 15
    misses = []
    if score < 8:
        misses.append("缺少反方审稿")
    if "证伪" not in text and "否认" not in text:
        misses.append("缺少证伪/反证检查")
    reason = (
        "主动做反方审稿，检查旧预期、证伪点和置信度"
        if score >= 12
        else "反方审稿不足，回答容易顺着题材讲"
    )
    return RubricDimension("critic_review", "反方审稿", score, 15, reason, hits, misses)


def _score_actionability(text: str) -> RubricDimension:
    hits = _hits(text, ("结论", "观察", "后续", "看", "如果", "需要", "非投资建议", "高置信", "不足"))
    metric_hits = _hits(text, ("订单", "客户", "收入", "毛利率", "利用率", "成交", "扩散"))
    score = min(10, len(hits) + len(metric_hits))
    if "结论" in text and metric_hits:
        score = max(score, 8)
    misses = []
    if score < 6:
        misses.append("结论不可操作，缺少后续观察指标")
    reason = (
        "给出分层结论和后续观察指标"
        if score >= 8
        else "结论偏口号，缺少可跟踪指标"
    )
    return RubricDimension("actionability", "结论可用性", score, 10, reason, hits + metric_hits, misses)


def _score_personal_methodology(text: str) -> RubricDimension:
    hits = _hits(
        text,
        (
            "双红",
            "流动性",
            "题材",
            "生命周期",
            "预期差",
            "兑现",
            "强弱",
            "扩散",
            "切换",
            "资金推动价格",
            "量能决定周期",
            "20日量能回归",
            "情绪",
            "结构",
            "行业聚散度",
            "成交占比环比",
            "板块周期",
            "市场周期",
            "底部横盘",
            "顶部横盘",
            "主升",
            "龙头",
            "新高",
            "量价结构",
        ),
    )
    score = min(10, len(hits) * 2)
    misses = []
    if score < 5:
        misses.append("缺少双红/流动性/资金量能周期/题材生命周期等用户方法论")
    reason = (
        "体现双红、扩散、资金量能周期或全量盘面体系等用户交易方法论"
        if score >= 8
        else "个性化交易方法论体现不足"
    )
    return RubricDimension(
        "personal_methodology", "个人方法论贴合", score, 10, reason, hits, misses
    )


def _grade(total: int, max_score: int = 100) -> str:
    pct = total / max_score * 100 if max_score else 0.0
    if pct >= 85:
        return "A"
    if pct >= 75:
        return "B"
    if pct >= 65:
        return "C"
    if pct >= 50:
        return "D"
    return "F"


_FORECAST_SOURCE_MARKS: dict[str, tuple[str, ...]] = {
    "全量盘面": ("全量盘面", "盘面复盘", "复盘数据", "双红", "涨停热度", "新高集群", "边际量"),
    "晚间卖方": ("晚间卖方", "卖方", "机构胜率", "覆盖密度"),
    "外盘/隔夜美股": ("隔夜美股", "外盘", "纳指", "费半", "美股", "soxx", "qqq"),
    "晨汇": ("晨汇", "早间材料", "盘前材料"),
}

_HYPOTHESIS_MARK = re.compile(r"(?:^|\n)[^\n]{0,12}?假设\s*(?:[0-9１-６一二三四五六]\s*[:：．.]?|[:：])")
_NUMERIC_THRESHOLD = re.compile(r"\d+(?:\.\d+)?\s*[%％亿万家只个点元倍日]")
_TIMING_MARKS = ("盘后", "次日", "明日", "收盘", "盘中", "验证时点", "下一交易日", "t+1")
_ATTRIBUTION_MARKS = ("支持", "反证", "缺数据")


def _hypothesis_blocks(answer: str) -> list[str]:
    matches = list(_HYPOTHESIS_MARK.finditer(answer))
    blocks: list[str] = []
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(answer)
        block = answer[match.end():end].strip()
        if block:
            blocks.append(block)
    return blocks


def _score_market_forecast_group(answer: str, text: str) -> list[RubricDimension]:
    return [
        _score_forecast_source_consensus(text),
        _score_forecast_stage_call(text),
        _score_forecast_strategy_mapping(text),
        _score_forecast_hypotheses(answer),
        _score_forecast_hypothesis_attribution(answer, text),
    ]


def _score_forecast_source_consensus(text: str) -> RubricDimension:
    hits: list[str] = []
    misses: list[str] = []
    for source, marks in _FORECAST_SOURCE_MARKS.items():
        if _hits(text, marks):
            hits.append(source)
        else:
            misses.append(f"未引用{source}")
    score = len(hits) * 3
    reason = (
        "四源合议齐备：全量盘面、晚间卖方、外盘、晨汇均被引用"
        if len(hits) == 4
        else "四源合议不齐，缺失来源会让前瞻判断失去交叉验证"
    )
    return RubricDimension(
        "forecast_source_consensus", "四源合议", score, 12, reason, hits, misses
    )


def _score_forecast_stage_call(text: str) -> RubricDimension:
    stage_hits = _hits(text, ("大盘阶段", "情绪阶段", "市场阶段", "阶段"))
    style_hits = _hits(
        text,
        ("普涨", "结构性", "分歧", "退潮", "主升", "扩散", "防御", "轮动", "高位", "低位切换", "抱团", "承接"),
    )
    score = min(8, (2 if stage_hits else 0) + len(style_hits) * 2)
    misses = []
    if not stage_hits:
        misses.append("缺少明确的阶段判断词")
    if not style_hits:
        misses.append("缺少普涨/结构性/分歧/轮动等风格判断")
    reason = (
        "给出了明确的大盘/情绪阶段与风格判断"
        if score >= 6
        else "阶段与风格判断不明确，研判容易停留在指数涨跌描述"
    )
    return RubricDimension(
        "forecast_stage_call", "阶段与风格判断", score, 8, reason, stage_hits + style_hits, misses
    )


def _score_forecast_strategy_mapping(text: str) -> RubricDimension:
    strategy_hits = _hits(
        text,
        ("策略一", "策略二", "策略三", "策略四", "策略1", "策略2", "策略3", "策略4"),
    )
    selection_hits = _hits(text, ("优先", "优选", "备选", "选择理由", "理由"))
    score = min(6, len(set(strategy_hits)) * 2) + (4 if strategy_hits and selection_hits else 0)
    misses = []
    if not strategy_hits:
        misses.append("未映射策略一二三四")
    if not selection_hits:
        misses.append("缺少明确的策略选择结论与理由")
    reason = (
        "把行情阶段映射到策略一二三四，并给出明确选择结论"
        if score >= 8
        else "策略状态映射不足，行情判断没有落到具体策略选择"
    )
    return RubricDimension(
        "forecast_strategy_mapping", "策略状态映射", score, 10, reason, strategy_hits + selection_hits, misses
    )


def _score_forecast_hypotheses(answer: str) -> RubricDimension:
    blocks = _hypothesis_blocks(answer)
    n = len(blocks)
    misses: list[str] = []
    hits: list[str] = [f"假设条数={n}"]
    if n == 0:
        return RubricDimension(
            "forecast_hypotheses", "可验证假设", 0, 12,
            "没有输出编号假设，盘后无法逐条验证", [], ["缺少 3-6 条可盘后验证的假设"],
        )
    score = 6 if 3 <= n <= 6 else 3
    if not 3 <= n <= 6:
        misses.append(f"假设条数 {n} 不在 3-6 条要求内")
    with_threshold = sum(1 for b in blocks if _NUMERIC_THRESHOLD.search(b))
    with_timing = sum(1 for b in blocks if any(mark in b.lower() for mark in _TIMING_MARKS))
    if with_threshold == n:
        score += 3
        hits.append("每条假设含数值阈值")
    elif with_threshold * 2 >= n:
        score += 1
        misses.append("部分假设缺数值阈值")
    else:
        misses.append("假设普遍缺数值阈值")
    if with_timing == n:
        score += 3
        hits.append("每条假设含验证时点")
    elif with_timing * 2 >= n:
        score += 1
        misses.append("部分假设缺验证时点")
    else:
        misses.append("假设普遍缺验证时点")
    reason = (
        "假设条数、数值阈值和验证时点齐备，盘后可逐条验证"
        if score >= 10
        else "假设可验证性不足，盘后回填会缺少核对口径"
    )
    return RubricDimension("forecast_hypotheses", "可验证假设", score, 12, reason, hits, misses)


def _score_forecast_hypothesis_attribution(answer: str, text: str) -> RubricDimension:
    blocks = _hypothesis_blocks(answer)
    if not blocks:
        return RubricDimension(
            "forecast_hypothesis_attribution", "假设来源标注", 0, 8,
            "没有假设可标注来源", [], ["每条假设须标支持/反证来源"],
        )
    source_marks = tuple(mark for marks in _FORECAST_SOURCE_MARKS.values() for mark in marks)
    attributed = sum(
        1
        for b in blocks
        if any(mark in b for mark in _ATTRIBUTION_MARKS)
        and (any(mark in b.lower() for mark in source_marks) or "缺数据" in b)
    )
    score = round(8 * attributed / len(blocks))
    misses = []
    if attributed < len(blocks):
        misses.append(f"{len(blocks) - attributed} 条假设未标支持/反证来源")
    reason = (
        "每条假设都标注了支持/反证来源"
        if attributed == len(blocks)
        else "部分假设缺来源标注，验证时无法定位证据"
    )
    hits = [f"已标注 {attributed}/{len(blocks)} 条"]
    return RubricDimension(
        "forecast_hypothesis_attribution", "假设来源标注", score, 8, reason, hits, misses
    )


def evidence_marker_count(answer: str) -> int:
    """答案里去重后的真实证据标记数（股票代码/日期/引用编号/带单位数字）。"""
    raw = str(answer or "")
    total = 0
    for _name, pattern in _EVIDENCE_MARKER_PATTERNS:
        total += len(set(re.findall(pattern, raw)))
    return total


def _evidence_ceiling_ratio(marker_count: int) -> float:
    if EVIDENCE_FULL_CREDIT <= 0:
        return 1.0
    return min(1.0, marker_count / EVIDENCE_FULL_CREDIT)


def _apply_evidence_gate(dim: RubricDimension, marker_count: int) -> RubricDimension:
    """把断言「有据可依」的维度压到证据密度允许的上限内。"""
    if dim.key not in EVIDENCE_GATED_KEYS:
        return dim
    ceiling = int(dim.max_score * _evidence_ceiling_ratio(marker_count))
    if dim.score <= ceiling:
        return dim
    misses = list(dim.misses)
    misses.append(
        f"证据标记不足（{marker_count}/{EVIDENCE_FULL_CREDIT}）：只有关键词、"
        "缺股票代码/日期/引用编号/带单位数字，得分已按证据密度封顶"
    )
    return RubricDimension(
        dim.key, dim.label, ceiling, dim.max_score, dim.reason, list(dim.hits), misses
    )


def _norm(text: str) -> str:
    return str(text or "").lower()


def _hits(text: str, marks: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for mark in marks:
        if mark.lower() in text:
            out.append(mark)
    return out
