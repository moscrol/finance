"""Finance-domain answer rubric for vertical agent quality scoring.

This module scores the *thinking quality* of a financial answer, complementing
``agent_eval`` which mostly guards grounding mechanics such as citations and
tool budgets. The scorer is deterministic by design: no LLM, no I/O, no network.
That makes it suitable as a cheap regression baseline before adding an optional
LLM-as-judge layer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


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

    def dimension(self, key: str) -> RubricDimension:
        for item in self.dimensions:
            if item.key == key:
                return item
        raise KeyError(key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "total_score": self.total_score,
            "max_score": self.max_score,
            "grade": self.grade,
            "failures": list(self.failures),
            "dimensions": [d.to_dict() for d in self.dimensions],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def score_answer(
    question: str,
    answer: str,
    *,
    local_sources: list[str] | None = None,
) -> FinanceAnswerScore:
    """Score one financial answer with a 100-point vertical rubric."""
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
    total = sum(d.score for d in dims)
    failures = [
        f"{d.label}不足：{'; '.join(d.misses) or d.reason}"
        for d in dims
        if d.ratio < 0.55
    ]
    return FinanceAnswerScore(
        question=question,
        total_score=total,
        max_score=sum(d.max_score for d in dims),
        grade=_grade(total),
        dimensions=dims,
        failures=failures,
    )


def format_score(score: FinanceAnswerScore) -> str:
    """Render a human-readable markdown scorecard."""
    lines = [
        f"# 金融回答质量评分：{score.total_score}/{score.max_score}（{score.grade}）",
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
    concept_hits = _hits(text, ("证据分层", "产业叙事", "基本面", "硬事实", "盘面情绪", "公司硬事实"))
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


def _grade(total: int) -> str:
    if total >= 85:
        return "A"
    if total >= 75:
        return "B"
    if total >= 65:
        return "C"
    if total >= 50:
        return "D"
    return "F"


def _norm(text: str) -> str:
    return str(text or "").lower()


def _hits(text: str, marks: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for mark in marks:
        if mark.lower() in text:
            out.append(mark)
    return out
