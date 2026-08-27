"""V1b：题形 → evidence_plan 的 KB 通道引导（optional，不另建预算降档）。

缝：``resolve_evidence_plan``（及 ``has_sector_theme_attribution_intent``）。
``dated_market_review`` 与别名 ``market_review`` 共用同一谓词，非整题纳入。
"""

from __future__ import annotations

import inspect

import pytest

from intelligence.services import evidence_capabilities as evidence_capabilities_mod
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.evidence_capabilities import resolve_evidence_plan
from intelligence.runtime.turn_control_core import TurnControlCore

_KB_CAPS = frozenset({"kb_search", "evidence_search"})

# R-11 验证文档 §5 五案例（问句取 V1a 提案表同源台账题；题形按 live / 应落）。
_R11_PEROVSKITE = "钙钛矿电池产业链怎么拆"
_R11_CXO = "CXO概念这波怎么看"
_R11_HUANGSHI = (
    "皇氏集团最近两周（2026-08-06到2026-08-20）的走势复盘："
    "几个关键转折日各自的涨跌幅和成交额是多少？"
)
_R11_WEIGHT_LOSS = "减肥药这波从月初发酵到现在怎么看"

_REVIEW_HIT = "复盘7月16日半导体板块为什么走强"
_REVIEW_MISS = "复盘7月16日的A股市场"

_OUT_OF_SCOPE_TYPES = (
    "general_finance_qa",
    "comparison",
    "fact_check",
    "kol_review",
    "trade_advice",
    "comparison_analog",
    "financial_analysis",
    "news_impact",
    "market_forecast",
    "market_watch",
)


def _kb_items(plan) -> tuple:
    return tuple(item for item in plan.requirements if item.capability in _KB_CAPS)


def _has_kb(plan) -> bool:
    return bool(_kb_items(plan))


@pytest.mark.parametrize(
    ("query", "question_type"),
    [
        (_R11_PEROVSKITE, "theme_analysis"),
        ("光伏最近一个月有什么新变化", "theme_track"),
        (_R11_HUANGSHI, "stock_deep_dive"),
        ("这一周行情下跌的主要原因是什么", "market_cause"),
        ("宁德时代估值贵不贵", "valuation_estimate"),
    ],
)
def test_approved_types_guide_optional_kb(query: str, question_type: str) -> None:
    plan = resolve_evidence_plan(query, question_type=question_type)
    items = _kb_items(plan)
    assert items, f"{question_type} 应含 KB requirement"
    assert all(item.mandatory is False for item in items)
    assert "kb_search" not in plan.mandatory_capabilities


def test_dated_market_review_overlay_hits_only_with_attribution() -> None:
    hit = resolve_evidence_plan(_REVIEW_HIT, question_type="dated_market_review")
    miss = resolve_evidence_plan(_REVIEW_MISS, question_type="dated_market_review")
    assert _has_kb(hit)
    assert all(item.mandatory is False for item in _kb_items(hit))
    assert not _has_kb(miss)


def test_market_review_alias_shares_dated_overlay() -> None:
    """两个题形名共用同一谓词，不得各写一份。"""

    predicate = evidence_capabilities_mod.has_sector_theme_attribution_intent
    assert predicate(_REVIEW_HIT) is True
    assert predicate(_REVIEW_MISS) is False
    # 「今天板块表现如何」有层名词、无归因动词 → 不命中（保守）。
    assert predicate("今天板块表现如何") is False
    for question_type in ("dated_market_review", "market_review"):
        hit = resolve_evidence_plan(_REVIEW_HIT, question_type=question_type)
        miss = resolve_evidence_plan(_REVIEW_MISS, question_type=question_type)
        assert _has_kb(hit), question_type
        assert not _has_kb(miss), question_type


@pytest.mark.parametrize("question_type", _OUT_OF_SCOPE_TYPES)
def test_out_of_scope_types_do_not_gain_kb_requirement(question_type: str) -> None:
    plan = resolve_evidence_plan(
        "液冷和风冷的优势分别是什么",
        question_type=question_type,
    )
    assert not _has_kb(plan)


def test_r11_replay_perovskite_and_huangshi_plans_include_kb() -> None:
    perovskite = resolve_evidence_plan(
        _R11_PEROVSKITE, question_type="theme_analysis"
    )
    cxo = resolve_evidence_plan(_R11_CXO, question_type="theme_analysis")
    huangshi = resolve_evidence_plan(
        _R11_HUANGSHI, question_type="stock_deep_dive"
    )
    assert _has_kb(perovskite)
    assert _has_kb(cxo)
    assert _has_kb(huangshi)


def test_r11_weight_loss_live_fallback_type_stays_without_kb() -> None:
    """减肥药 live 落到 general_finance_qa；兜底不加 KB（路由债另立）。"""

    live = resolve_evidence_plan(
        _R11_WEIGHT_LOSS, question_type="general_finance_qa"
    )
    intended = resolve_evidence_plan(
        _R11_WEIGHT_LOSS, question_type="theme_analysis"
    )
    assert not _has_kb(live)
    assert _has_kb(intended)


def test_market_cause_factory_keeps_optional_kb_from_resolve() -> None:
    control = TurnControlCore().control(
        "这一周行情下跌的主要原因是什么",
        llm_complete=lambda *_args, **_kwargs: (None, None, "disabled"),
    )
    context = build_episode_context(
        control.task_frame,
        task_id="v1b-market-cause-kb",
        capabilities=control.capabilities,
    )
    plan = context.contract.evidence_plan
    assert plan.profile == "time_aligned_market_causal"
    items = _kb_items(plan)
    assert items
    assert all(item.mandatory is False for item in items)
    assert set(plan.mandatory_capabilities) == {"market_data", "news_search"}


def test_kb_mapping_does_not_invent_a_second_budget_ladder() -> None:
    for name in (
        "has_sector_theme_attribution_intent",
        "should_guide_kb_channel",
        "_with_kb_channel_guidance",
    ):
        source = inspect.getsource(getattr(evidence_capabilities_mod, name))
        assert "select_mode_for_remaining" not in source
        assert "remaining_seconds" not in source
        assert "HYBRID_MIN_REMAINING" not in source
