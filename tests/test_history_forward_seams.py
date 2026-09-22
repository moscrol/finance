"""Keep historical scope and the current main's material contracts together."""

import pytest

from intelligence.services.material_contract import compile_material_contract
from intelligence.services.user_task import (
    requests_previous_answer_review,
    split_user_message,
)


def _contract(text, inherited=None):
    return compile_material_contract(
        split_user_message(text).regions, inherited_contract=inherited,
    )


@pytest.mark.parametrize("instruction", [
    "如果当前分析窗太短，只能在之前授权的日期范围内继续观察。",
    "如果需要验证，请先核对证据。",
    "如果数据无法获取，请说明缺口。",
    "如果材料缺失，请说明不能计算。",
])
def test_procedure_and_missing_inputs_do_not_grant_fictional_basis(instruction):
    contract = _contract(instruction)
    assert contract is None or contract.authenticity != "fictional"
    assert contract is None or not contract.premise_calculation
    # Numbered questions must use the same exclusion as top-level instructions.
    numbered = _contract(f"1. {instruction}")
    assert numbered is None or numbered.authenticity != "fictional"
    assert numbered is None or all(mark.authenticity != "fictional" for mark in numbered.premise_marks)


def test_actual_market_hypothesis_is_still_classified():
    contract = _contract("如果营收增长20%，利润会怎样？")
    assert contract.authenticity == "fictional"
    assert contract.premise_marks
    assert not contract.premise_calculation  # No blanket math-proof exemption.


@pytest.mark.parametrize("continuation", [
    "复核你刚才的解释。范围与截止日继续不变。",
    "仍沿用上一轮信息截止和研究范围。",
    "请遵守上一轮研究范围与截止。",
])
def test_both_review_and_history_continuations_keep_the_user_read_ceiling(continuation):
    base = _contract("只依据材料回答。")
    contract = _contract(continuation, base)
    assert contract.continuation_requested
    assert contract.data_scope == "material_only"
    assert not contract.data_scope_declared
    assert _contract(continuation).classification == "state_unavailable"
    for quoted in (f"“{continuation}”", f"> {continuation}", f"```text\n{continuation}\n```"):
        compiled = _contract(quoted)
        assert compiled is None or not compiled.continuation_requested
        assert not requests_previous_answer_review(quoted)
    if continuation.startswith("复核"):
        assert requests_previous_answer_review(continuation)
