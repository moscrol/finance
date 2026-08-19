"""W2: judge_unavailable vs content_degraded classification."""

from __future__ import annotations

from intelligence.services.judge_degrade import (
    classify_degrade_counts,
    degrade_class_for_status,
    extract_judge_status,
    split_degrade_from_payloads,
)


def test_unavailable_is_judge_class_even_without_timeout_or_exc() -> None:
    ju, cd = classify_degrade_counts(judge_status="unavailable")
    assert (ju, cd) == (1, 0)
    assert degrade_class_for_status("unavailable") == "judge_unavailable"


def test_unavailable_with_timeout_triplet_stays_judge_class() -> None:
    ju, cd = classify_degrade_counts(
        judge_status="unavailable",
        extra_degrade_count=1,
        exc_class="TimeoutError",
        timeout_asked=25.0,
    )
    assert (ju, cd) == (1, 0)


def test_none_plus_timeout_is_not_judge_unavailable() -> None:
    ju, cd = classify_degrade_counts(
        judge_status=None,
        extra_degrade_count=1,
        exc_class="TimeoutError",
        timeout_asked=25.0,
    )
    assert (ju, cd) == (0, 1)


def test_not_applicable_is_not_judge_unavailable() -> None:
    ju, cd = classify_degrade_counts(
        judge_status="not_applicable",
        extra_degrade_count=1,
    )
    assert (ju, cd) == (0, 1)


def test_other_degrades_are_content() -> None:
    ju, cd = classify_degrade_counts(
        judge_status="passed",
        extra_degrade_count=2,
    )
    assert (ju, cd) == (0, 2)
    assert degrade_class_for_status("passed") is None
    assert degrade_class_for_status("repaired") is None


def test_rejected_judge_is_not_vendor_unavailable() -> None:
    ju, cd = classify_degrade_counts(judge_status="rejected", extra_degrade_count=1)
    assert (ju, cd) == (0, 1)
    assert degrade_class_for_status("rejected") is None


def test_extract_judge_status_reads_semantic_and_gate_shapes() -> None:
    assert (
        extract_judge_status({"semantic_verifier": {"judge_status": "unavailable"}})
        == "unavailable"
    )
    assert (
        extract_judge_status({"gate_receipt": {"judge_status": "not_applicable"}})
        == "not_applicable"
    )


def test_split_from_payloads_keeps_ask_not_applicable_out_of_judge_bucket() -> None:
    counts = split_degrade_from_payloads(
        ["llm_unavailable_template_answer"],
        {"judge_status": "not_applicable"},
    )
    assert counts == {
        "judge_unavailable_count": 0,
        "content_degraded_count": 1,
    }
