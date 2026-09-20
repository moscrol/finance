"""Scope directives must honor negation and remain clarifiable across turns."""
import pytest

from intelligence.tests.test_premise_financial_calculation import (
    ARITHMETIC,
    CALCULATION_MARKER,
    FOLLOWUP,
    PremiseSource,
    compile_case,
    values,
)

HISTORY = (PremiseSource("first", ARITHMETIC), PremiseSource("second", FOLLOWUP))
CONFLICT = (
    "沿用上一轮。只计算静态市盈率。"
    "下一年归母净利润增长10%，请计算情景市盈率。"
)


@pytest.mark.parametrize("prefix", ["不要", "请不要", "不应"])
def test_negated_static_only_must_keep_scenario(prefix):
    calc = compile_case(
        f"沿用上一轮。{prefix}只计算静态市盈率，还要保留之前的情景。", HISTORY,
    )
    assert not calc.issues
    assert values(calc)["scenario_profit"] == pytest.approx(7.2)


def test_cancel_and_new_scenario_must_not_silently_complete():
    calc = compile_case(
        "沿用上一轮。取消情景。下一年归母净利润增长10%，请计算情景市盈率。", HISTORY,
    )
    assert calc.issues


def test_explicit_clarification_resolves_previous_scope_conflict():
    calc = compile_case(
        "沿用上一轮。下一年归母净利润增长10%，请计算情景市盈率。",
        (*HISTORY, PremiseSource("third", CONFLICT)),
    )
    assert not calc.issues
    assert values(calc)["scenario_profit"] == pytest.approx(9.9)


def test_bare_continue_keeps_previous_scope_conflict():
    calc = compile_case(
        "沿用上一轮，继续给出结果。", (*HISTORY, PremiseSource("third", CONFLICT)),
    )
    assert calc.issues


def test_polite_cancellation_is_recognized():
    calc = compile_case("沿用上一轮。请取消情景计算。", HISTORY)
    assert not calc.issues
    assert "scenario_pe" not in values(calc)


def test_additional_scenario_cannot_silently_replace_the_original():
    calc = compile_case(
        "沿用上一轮。再加一个情景：下一年归母净利润增长10%，请比较两个情景市盈率。", HISTORY,
    )
    assert any("多个情景" in issue for issue in calc.issues)


def test_static_only_conflict_cannot_silently_drop_requested_metrics():
    calc = compile_case(
        "这次只计算静态市盈率，还要给出收入同比。", HISTORY,
    )
    assert any("其他指标" in issue for issue in calc.issues)
    assert calc.admit(CALCULATION_MARKER, status="completed")[1]


def test_current_static_only_can_retire_metrics_from_prior_user_messages():
    calc = compile_case("沿用上一轮。只计算静态市盈率。", HISTORY)
    assert not calc.issues
    assert values(calc)["static_pe"] == pytest.approx(240 / 9)


def test_cross_sentence_current_scope_conflict_is_not_silent():
    calc = compile_case(
        "沿用上一轮。请给出收入同比。这次只计算静态市盈率。", HISTORY,
    )
    assert any("其他指标" in issue for issue in calc.issues)
    assert calc.admit(CALCULATION_MARKER, status="completed")[1]
