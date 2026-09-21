"""Malformed financial updates must not silently keep the previous valid value."""
import pytest

from intelligence.tests.test_premise_financial_calculation import (
    ARITHMETIC, FOLLOWUP, CALCULATION_MARKER, PremiseSource, compile_case, values,
)

HISTORY = (PremiseSource("first", ARITHMETIC), PremiseSource("second", FOLLOWUP))


@pytest.mark.parametrize("statement, metric, period", [
    ("股价改为30", "price", None),
    ("总股本改为20", "shares", None),
    ("2025年归母净利润改为10", "profit", 2025),
    ("2025年经营现金流改为5", "cash_flow", 2025),
    ("股价由24改为30元", "price", None),
])
def test_unitless_update_cannot_use_the_previous_input(statement, metric, period):
    calc = compile_case(f"沿用上一轮。{statement}。请重新计算。", HISTORY)
    assert calc.issues
    assert not any(item.metric == metric and item.period == period for item in calc.inputs)
    assert calc.admit(CALCULATION_MARKER, status="completed")[1]


def test_multiple_unitless_updates_do_not_crash_on_mixed_periods():
    calc = compile_case(
        "沿用上一轮。股价改为30，2025年归母净利润改为10。", HISTORY,
    )
    assert calc.issues
    assert "market_cap" not in values(calc)


def test_bare_continue_cannot_clear_unresolved_units():
    calc = compile_case(
        "沿用上一轮，继续。",
        (*HISTORY, PremiseSource("third", "沿用上一轮。股价改为30。")),
    )
    assert calc.issues
    assert "market_cap" not in values(calc)


def test_unit_clarification_can_validate_the_original_price_and_resume():
    calc = compile_case(
        "沿用上一轮。股价由24元改为30元。",
        (*HISTORY, PremiseSource("third", "沿用上一轮。股价改为30。")),
    )
    assert not calc.issues
    assert values(calc)["market_cap"] == 300
    assert values(calc)["static_pe"] == pytest.approx(300 / 9)


def test_complete_annual_restatement_resolves_unknown_units():
    calc = compile_case(
        "沿用上一轮。2025年归母净利润改为10亿元。",
        (*HISTORY, PremiseSource("third", "沿用上一轮。2025年归母净利润改为10。")),
    )
    assert not calc.issues
    assert values(calc)["static_pe"] == 24


def test_missing_scenario_percentage_is_not_the_previous_percentage():
    calc = compile_case("沿用上一轮。下一年归母净利润下降10。", HISTORY)
    assert calc.issues
    assert "scenario_pe" not in values(calc)


def test_percentage_clarification_resumes_the_latest_scenario():
    calc = compile_case(
        "沿用上一轮。下一年归母净利润下降10%。",
        (*HISTORY, PremiseSource("third", "沿用上一轮。下一年归母净利润下降10。")),
    )
    assert not calc.issues
    assert values(calc)["scenario_profit"] == pytest.approx(8.1)
