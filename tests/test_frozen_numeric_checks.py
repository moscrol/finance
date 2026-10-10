"""Typed numeric support is source-bound calculation, never a free-prose pass."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from intelligence.eval import frozen_numeric_checks as checks
from intelligence.services.agent_runtime import public_agent_evidence
from intelligence.services.owned_results import OwnedResultError
from intelligence.tests.owned_result_support import IMMUNE_KEY, source_fixture


def packet_fixture():
    source = source_fixture()
    public = {"tool": source.tool, "ok": True, "status": "success", "dataset": source.dataset,
              "query": source.query, "observation": source.observation,
              "evidence": [public_agent_evidence(item) for item in source.evidence],
              "evidence_hashes": list(source.evidence_hashes), "query_basis": deepcopy(source.query_basis)}
    return {"question": "Review the supplied mainline observations.", "information_cutoff": "2026-09-30",
            "observations": [{"id": "O1", "tool": "mainline_context", "arguments": {}, "result": public}]}


def test_qualification_reuses_existing_rule_and_keeps_volume_independent():
    packet = packet_fixture()
    before = deepcopy(packet)
    receipt = checks.compile_numeric_checks(packet)
    selected = next(row for row in receipt["checks"][0]["preview_qualifications"] if tuple(row["key"]) == IMMUNE_KEY)
    assert selected["turnover_change_pct"] == 44.2976
    assert selected["turnover_yi"] == 349.327
    assert selected["price_direction"] == selected["turnover_direction"] == "up"
    assert selected["strict_double_red"] is False
    assert "不满足严格双红" in selected["qualification_text"]
    assert sum(row["strict_double_red"] is True for row in receipt["checks"][0]["preview_qualifications"]) == 3
    assert receipt["authority"] == "calculation_only_no_prose_certification"
    assert all(not group["full_counts_available"] for group in receipt["checks"][0]["groups"])
    assert packet == before


def test_missing_input_retains_unknown_qualification_not_false():
    packet = packet_fixture()
    row = packet["observations"][0]["result"]["query_basis"]["price_volume_signals"][0]
    row.update(sector_amount=None, strict_double_red=None, inputs_complete=False, missing_inputs=["sector_amount"])
    receipt = checks.compile_numeric_checks(packet)
    selected = receipt["checks"][0]["preview_qualifications"][0]
    assert selected["strict_double_red"] is None
    assert selected["turnover_direction"] == "up"


@pytest.mark.parametrize("matching,unknown,expected", [(4, 0, "yes"), (2, 0, "no"), (2, 2, "unknown")])
def test_full_counts_calculate_bounds_not_preview_proportions(matching, unknown, expected):
    n = 6
    group = {"theme_name": "fixture", "total_rows": n, "preview_rows": 2, "omitted_rows": 4}
    group["full_group_counts"] = {
        "distinct_sector_codes": n,
        "price_up": matching, "price_down": n-matching-unknown, "price_flat": 0, "price_unknown": unknown,
        "turnover_up": n, "turnover_down": 0, "turnover_flat": 0, "turnover_unknown": 0,
        "double_red": 1, "not_double_red": n-1-unknown, "double_red_unknown": unknown,
    }
    result = checks._group_summary(group)
    assert result["price_up_majority_of_records"] == expected
    assert result["price_up_count_bounds"] == [matching, matching+unknown]
    assert result["count_unit"] == "theme_sector_records"
    assert result["double_red_share_pct_bounds"][0] == "16.6667"
    assert result["double_red_share_pct_bounds"][1] == ("50.0000" if unknown else "16.6667")


@pytest.mark.parametrize("mutation", [
    lambda packet: packet.update(information_cutoff="2026-09-29"),
    lambda packet: packet["observations"][0]["result"].update(telemetry={"withheld": "future"}),
    lambda packet: packet["observations"].append(deepcopy(packet["observations"][0])),
    lambda packet: packet["observations"][0]["result"]["query_basis"]["price_volume_signals"][0].update(strict_double_red=True),
    lambda packet: packet["observations"][0]["result"]["evidence"][0].update(detail="Changed source detail"),
])
def test_conflicting_inputs_do_not_generate_numeric_certificates(mutation):
    packet = packet_fixture()
    mutation(packet)
    with pytest.raises((ValueError, OwnedResultError)):
        checks.compile_numeric_checks(packet)


def test_empty_group_has_no_percentage_or_majority():
    counts = dict.fromkeys(("distinct_sector_codes", "price_up", "price_down", "price_flat", "price_unknown",
                           "turnover_up", "turnover_down", "turnover_flat", "turnover_unknown",
                           "double_red", "not_double_red", "double_red_unknown"), 0)
    result = checks._group_summary({"theme_name": "empty", "total_rows": 0, "preview_rows": 0,
                                    "omitted_rows": 0, "full_group_counts": counts})
    assert result["price_up_majority_of_records"] == "unknown"
    assert result["price_up_share_pct_bounds"] == result["double_red_share_pct_bounds"] == [None, None]


def test_complete_group_receipt_keeps_full_and_preview_scopes_separate():
    packet = packet_fixture()
    group = packet["observations"][0]["result"]["query_basis"]["groups"][0]
    assert group["total_rows"] == group["preview_rows"] == 6
    group["full_group_counts"] = {
        "distinct_sector_codes": 6,
        "price_up": 6, "price_down": 0, "price_flat": 0, "price_unknown": 0,
        "turnover_up": 6, "turnover_down": 0, "turnover_flat": 0, "turnover_unknown": 0,
        "double_red": 1, "not_double_red": 5, "double_red_unknown": 0,
    }
    receipt = checks.compile_numeric_checks(packet)["checks"][0]
    assert receipt["groups"][0]["full_counts_available"] is True
    assert receipt["groups"][0]["price_up_share_pct_bounds"] == ["100.0000", "100.0000"]
    assert receipt["groups"][0]["double_red_share_pct_bounds"] == ["16.6667", "16.6667"]
    assert all(not group["full_counts_available"] for group in receipt["groups"][1:])


def test_self_consistent_counts_cannot_contradict_delivered_members():
    packet = packet_fixture()
    group = packet["observations"][0]["result"]["query_basis"]["groups"][0]
    n = group["total_rows"]
    group["full_group_counts"] = {
        "distinct_sector_codes": n,
        "price_up": 0, "price_down": n, "price_flat": 0, "price_unknown": 0,
        "turnover_up": n, "turnover_down": 0, "turnover_flat": 0, "turnover_unknown": 0,
        "double_red": 0, "not_double_red": n, "double_red_unknown": 0,
    }
    with pytest.raises(ValueError, match="contradict"):
        checks.compile_numeric_checks(packet)


def test_plain_text_values_are_not_silently_parsed_into_calculation_inputs():
    packet = {"information_cutoff": "2026-09-30", "question": "mean?", "observations": [{
        "id": "O1", "tool": "finance_query", "result": {"tool": "finance_query", "ok": True,
        "status": "success", "observation": "amount=2; amount=4; their average is 999"},
    }]}
    receipt = checks.compile_numeric_checks(packet)
    assert receipt["checks"] == []
    assert receipt["unsupported_observations"] == [{"observation_ref": "O1", "reason": "no_supported_typed_numeric_contract"}]
    assert "999" not in str(receipt)


def test_existing_compiler_is_the_qualification_authority(monkeypatch):
    actual = checks.compile_owned_results

    def without_result(source, context):
        assert context is None
        return replace(actual(source, context), blocks=())

    monkeypatch.setattr(checks, "compile_owned_results", without_result)
    result = checks.compile_numeric_checks(packet_fixture())
    assert result["checks"] == []
    assert result["unsupported_observations"][0]["reason"] == "no_validated_source_cards"


def test_numeric_document_is_generated_without_a_model_and_keeps_preview_limits():
    receipt = checks.compile_numeric_checks(packet_fixture())
    document = checks.render_numeric_checks(receipt)
    assert checks.render_numeric_checks(deepcopy(receipt)) == document
    assert "349.327 | 不满足 |" in document
    assert "44.2976" in document
    assert "未提供 | 未提供 | 未提供" in document
    assert "明细" in document and "不外推" in document
    assert "不是对研究解释或整篇答案的认证" in document
    group = receipt["checks"][0]["groups"][0]
    assert group["validated_preview_rows"] == 6
    assert group["preview_counts"]["price_up"] == 6
    assert group["preview_counts"]["double_red"] == 1


def test_table_labels_are_escaped_not_executable_markdown():
    receipt = checks.compile_numeric_checks(packet_fixture())
    receipt["checks"][0]["preview_qualifications"][0]["title"] = "<script>|evil\nnew row"
    document = checks.render_numeric_checks(receipt)
    assert "<script>" not in document
    assert "&lt;script&gt;&#124;evil new row" in document


def test_numeric_renderer_refuses_a_prose_approval_receipt():
    with pytest.raises(ValueError):
        checks.render_numeric_checks({"schema": "frozen_numeric_checks_v1", "authority": "whole_answer_passed"})
