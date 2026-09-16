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
