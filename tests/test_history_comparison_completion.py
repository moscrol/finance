"""An omitted optional envelope must not hide an unfinished comparison request."""

import pytest

from intelligence.services.historical_research.research import assess_history_finish
from intelligence.services.research_harness import FinanceResearchHarness
from intelligence.tests.test_historical_research_harness import _context, _frame, _result


@pytest.mark.parametrize("operation", ["inspect_history", "compute_history", "find_analogues"])
@pytest.mark.parametrize("extension", [False, True])
def test_partial_comparison_cannot_be_upgraded_by_omitting_optional_envelope(operation, extension):
    context = _context(_frame(), purpose="historical_comparison")
    context.history_results.append(_result(operation))
    payload = {"status": "completed"}
    if extension:
        payload["history_research"] = {
            "purpose": "historical_comparison", "result_refs": ["query-1"],
            "claim_level": "single_case", "research_only": True,
            "decision_eligible": False, "promotion_eligible": False,
        }
    result = assess_history_finish(payload, context=context)
    assert result.force_partial
    assert "尚未完成" in result.gap
    publication = FinanceResearchHarness().assess_publication(context=context)
    assert publication.max_status == "partial"
    assert result.gap in publication.required_public_notices


def test_full_comparison_has_no_missing_operation_notice():
    context = _context(_frame(), purpose="historical_comparison")
    context.history_results.append(_result("compare_cases"))
    assert not assess_history_finish({}, context=context).force_partial


def test_save_receipt_does_not_count_as_historical_calculation():
    context = _context(_frame())
    context.history_results.append({
        "operation": "save_history_research", "execution_status": "success",
        "result_ref": "case-reference", "purpose": "retrospective_discovery",
    })
    assert assess_history_finish({}, context=context).force_partial


def _asked(context, requested: bool | None):
    """把「本轮是否要求样本全集」这一条单独拨到某个值，其余权限不变。"""
    from dataclasses import replace

    return replace(
        context,
        history_intent=replace(context.history_intent, comparison_requested=requested),
    )


def test_only_the_turn_that_asks_for_a_rule_must_finish_the_comparison():
    """四道真题走真实推断路径：只有第四题要求把结论建在样本全集上。"""
    from intelligence.services.historical_research.intent import (
        infer_history_intent,
        inherit_history_followup,
    )
    from tests.test_history_live_seams import FIRST, FOLLOWUPS

    intent = infer_history_intent(FIRST)
    asked = [intent.requires_full_comparison]
    for question in FOLLOWUPS:
        intent = inherit_history_followup(question, intent)
        asked.append(intent.requires_full_comparison)

    # 第四题：「如果要说有后续收益规律，请把未启动或失败样本、缺数和未成熟样本也纳入比较」。
    # 前三题问的是市场阶段、当时谁走强、有没有别的板块接上——都不是规律请求。
    assert asked == [False, False, False, True]
    # 研究模式仍然整轮继承，权限不因这条判据改变。
    assert intent.purpose == "historical_comparison"


def test_a_descriptive_followup_is_not_told_it_owes_a_comparison():
    context = _asked(_context(_frame(), purpose="historical_comparison"), False)
    context.history_results.append(_result("trace_history"))
    result = assess_history_finish({}, context=context)
    assert not result.force_partial
    assert "尚未完成" not in result.gap
    assert FinanceResearchHarness().assess_publication(context=context).max_status != "partial"


def test_the_turn_that_asks_for_a_rule_still_owes_the_comparison():
    context = _asked(_context(_frame(), purpose="retrospective_discovery"), True)
    context.history_results.append(_result("find_analogues"))
    result = assess_history_finish({}, context=context)
    # 即使研究模式是「事后发现」，这一轮问了规律就得给条件全集比较。
    assert result.force_partial
    assert "条件全集" in result.gap


def test_claiming_a_rule_without_compare_cases_is_still_rejected():
    """兜底：本轮没要求样本全集，不等于可以自称规律已验证。"""
    from intelligence.services.historical_research.research import HistoryFinishRejection

    context = _asked(_context(_frame(), purpose="historical_comparison"), False)
    context.history_results.append(_result("find_analogues"))
    payload = {
        "status": "completed",
        "history_research": {
            "purpose": "historical_comparison", "result_refs": ["query-1"],
            "claim_level": "historical_comparison", "research_only": True,
            "decision_eligible": False, "promotion_eligible": False,
        },
    }
    with pytest.raises(HistoryFinishRejection) as caught:
        assess_history_finish(payload, context=context)
    assert caught.value.code == "history_missing_comparison"


def test_the_prompt_tells_the_turn_what_it_actually_owes():
    """判据改了，发给模型的说明也要跟着改，否则它仍会把预算花在凑比较上。"""
    from intelligence.services.historical_research.research import history_research_prompt

    descriptive, _ = history_research_prompt(
        _asked(_context(_frame(), purpose="historical_comparison"), False),
        available_tools=("history_query", "read_history_result"),
    )
    assert "不必另起 compare_cases" in descriptive
    assert "只要你要说「有规律」" in descriptive

    rule_turn, meta = history_research_prompt(
        _asked(_context(_frame(), purpose="historical_comparison"), True),
        available_tools=("history_query", "read_history_result"),
    )
    assert "不必另起 compare_cases" not in rule_turn
    # 逐轮判据本身也进模型视图，别让模型只能猜。
    assert '"comparison_requested": true' in meta
