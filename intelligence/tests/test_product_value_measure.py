"""measure_pair：计时 / 质量 / 费用 / 分母 / 无效判定（spec §5 验收 1–5、7、8 的配对层）。"""

from __future__ import annotations

import copy
import random
from datetime import datetime, timezone

from intelligence.services.product_value import contracts as C
from intelligence.services.product_value.evidence import InMemoryEvidenceReader
from intelligence.services.product_value.measure import measure_pair
from intelligence.tests.product_value_fixtures import (
    HASH_A,
    OWNER,
    SOURCE_FRONTEND,
    SOURCE_MANUAL,
    build_protocol,
    build_scenario,
    ev,
    ts,
)

PROTOCOL = build_protocol()
P_HASH = PROTOCOL["protocol_hash"]


def _scenario(name: str):
    events, evidence, _ = build_scenario(name, P_HASH)
    return events, InMemoryEvidenceReader.from_json(evidence)


def _find(events: list[dict], event_id: str) -> dict:
    return next(e for e in events if e["event_id"] == event_id)


def _without(events: list[dict], *event_ids: str) -> list[dict]:
    return [e for e in events if e["event_id"] not in event_ids]


def _codes(receipt: dict) -> set[str]:
    return {item["code"] for item in receipt["invalid_reasons"]}


# ---------------------------------------------------------------- 完整配对 -----


def test_complete_pair_is_valid_with_expected_readings() -> None:
    events, reader = _scenario("complete_pair")
    receipt = measure_pair(events, PROTOCOL, reader)
    assert receipt["schema_version"] == C.RECEIPT_SCHEMA
    assert receipt["status"] == C.RECEIPT_VALID, receipt["limitations"]
    assert receipt["protocol_hash"] == P_HASH
    timing = receipt["timing"]
    # 原流程 10:00→10:50 扣 5 分钟预登记暂停 = 45；主动时间 40+10 也扣掉暂停 = 45。
    assert timing["original"]["end_to_end_minutes"] == 45.0
    assert timing["original"]["pause_deducted_minutes"] == 5.0
    assert timing["original"]["user_active_minutes"] == 45.0
    assert timing["assisted"]["end_to_end_minutes"] == 20.0
    assert timing["assisted"]["model_wait_minutes"] == 7.0
    assert timing["assisted"]["user_active_minutes"] == 13.0
    assert timing["time_saving_ratio"] == 0.5556
    quality = receipt["quality"]
    assert quality["original"]["total"] == 7 and quality["assisted"]["total"] == 8
    assert quality["assisted_not_lower"] is True
    assert quality["severe_error_count_assisted"] == 0
    assert receipt["known_cost_by_currency"] == {"CNY": 0.46}
    assert receipt["estimated_cost_by_currency"] == {}
    assert receipt["unknown_cost_components"] == []
    assert receipt["numerator_ids"] == ["t-cp-a", "t-cp-o"]
    assert receipt["denominator_ids"] == ["t-cp-a", "t-cp-o"]
    assert receipt["provenance"]["synthetic"] is True
    assert receipt["tasks"]["assisted"]["completion_evidence"][0]["status"] == "ok"


def test_repeat_measure_gives_same_content_id_with_generated_at_aside() -> None:
    events, reader = _scenario("complete_pair")
    first = measure_pair(events, PROTOCOL, reader, now=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc))
    second = measure_pair(events, PROTOCOL, reader, now=datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc))
    assert first["receipt_id"] == second["receipt_id"]
    assert first["generated_at"] != second["generated_at"]
    assert {k: v for k, v in first.items() if k != "generated_at"} == {k: v for k, v in second.items() if k != "generated_at"}


def test_shuffled_and_duplicated_input_does_not_change_receipt_or_denominator() -> None:
    events, reader = _scenario("complete_pair")
    baseline = measure_pair(events, PROTOCOL, reader)
    noisy = copy.deepcopy(events) + copy.deepcopy(events[:6])
    for dup in noisy[len(events):]:
        dup["recorded_at"] = ts("09-30", "00:00:00")
    random.Random(3).shuffle(noisy)
    receipt = measure_pair(noisy, PROTOCOL, reader)
    assert receipt["receipt_id"] == baseline["receipt_id"]
    assert receipt["denominator_ids"] == baseline["denominator_ids"]
    assert receipt["event_accounting"]["duplicates"] == sorted(e["event_id"] for e in events[:6])


def test_conflicting_event_id_invalidates_receipt() -> None:
    events, reader = _scenario("complete_pair")
    tampered = copy.deepcopy(_find(events, "e-cp-a-done"))
    tampered["payload"]["terminal_reason"] = "edited"
    receipt = measure_pair(events + [tampered], PROTOCOL, reader)
    assert receipt["status"] == C.RECEIPT_INVALID
    assert "conflicting_event_id" in _codes(receipt)
    assert {"id": "e-cp-a-done", "reason": "conflicting_event_id", "rule_version": "1"} in receipt["exclusions"]


def test_parent_child_cost_not_double_counted() -> None:
    events, reader = _scenario("complete_pair")
    receipt = measure_pair(events, PROTOCOL, reader)
    span = next(i for i in receipt["cost_items"] if i["cost_id"] == "c-cp-span")
    assert span["selected"] is False and span["dedup_reason"] == "covered_by_run"
    assert receipt["known_cost_by_currency"] == {"CNY": 0.46}  # 0.36 + 0.10，不加 span 的 0.15


def test_pause_only_deducted_when_pre_registered() -> None:
    events, reader = _scenario("complete_pair")
    _find(events, "e-cp-o-int2")["payload"]["pause_reason"] = "coffee"
    receipt = measure_pair(events, PROTOCOL, reader)
    original = receipt["timing"]["original"]
    assert original["end_to_end_minutes"] == 50.0
    assert original["pause_deducted_minutes"] == 0.0
    assert original["pause_not_deducted"] == [{"interval_id": "i-cp-o-2", "pause_reason": "coffee"}]


def test_frontend_interval_cannot_override_server_version() -> None:
    events, reader = _scenario("complete_pair")
    fake = ev(
        "time_interval",
        event_id="e-cp-a-int2-client",
        at=ts("09-15", "14:30:00"),
        channel=SOURCE_FRONTEND,
        participant="p01",
        task="t-cp-a",
        case="case-fc-02",
        case_version="1",
        pair="pair-01",
        condition="assisted",
        payload={"interval_id": "i-cp-a-2", "start": ts("09-15", "14:05:00"), "end": ts("09-15", "14:30:00"), "activity": "model_wait", "clock_source": "client", "pause_reason": None, "visibility": "visible"},
    )
    receipt = measure_pair(events + [fake], PROTOCOL, reader)
    assert receipt["timing"]["assisted"]["model_wait_minutes"] == 7.0
    assert receipt["timing"]["assisted"]["frontend_overridden"] == ["i-cp-a-2"]


def test_frontend_abandon_intent_is_not_completion() -> None:
    events, reader = _scenario("complete_pair")
    events = _without(events, "e-cp-a-done")
    intent = ev(
        "task_abandoned",
        event_id="e-cp-a-quit",
        at=ts("09-15", "14:20:00"),
        channel=SOURCE_FRONTEND,
        participant="p01",
        task="t-cp-a",
        case="case-fc-02",
        case_version="1",
        pair="pair-01",
        condition="assisted",
        payload={"task_id": "t-cp-a", "completion_evidence_refs": [], "terminal_reason": "gave_up"},
    )
    receipt = measure_pair(events + [intent], PROTOCOL, reader)
    task = receipt["tasks"]["assisted"]
    assert task["terminal_state"] == C.TERMINAL_ABANDONED
    assert task["terminal_source"] == "frontend_intent"
    assert receipt["numerator_ids"] == ["t-cp-o"]
    assert receipt["denominator_ids"] == ["t-cp-a", "t-cp-o"]


def test_completion_after_deadline_is_timed_out_but_still_counted() -> None:
    events, reader = _scenario("complete_pair")
    _find(events, "e-cp-a-done")["event_at"] = ts("09-17", "10:00:00")
    receipt = measure_pair(events, PROTOCOL, reader)
    assert receipt["tasks"]["assisted"]["timed_out"] is True
    assert "t-cp-a" in receipt["numerator_ids"]


# ------------------------------------------------------------ 失败 / 降级 -----


def test_failed_run_without_report_counts_failure_and_known_cost() -> None:
    events, reader = _scenario("failed_retry")
    receipt = measure_pair(events, PROTOCOL, reader)
    task = receipt["tasks"]["assisted"]
    assert task["attempt_count"] == 2
    assert task["failed_attempt_count"] == 1
    assert task["degraded_attempt_count"] == 1
    failed = next(a for a in task["attempts"] if a["attempt_id"] == "a-fr-1")
    assert failed["failed"] is True and failed["run_status"] == "failed" and failed["has_error"] is True
    assert task["terminal_state"] == C.TERMINAL_COMPLETED
    assert receipt["known_cost_by_currency"] == {"CNY": 0.12}
    assert [u["reason"] for u in receipt["unknown_cost_components"]] == ["usage_without_rate"]
    assert receipt["status"] == C.RECEIPT_INCOMPLETE
    assert "cost_unknown:c-fr-2" in receipt["limitations"]
    assert receipt["numerator_ids"] == ["t-fr-a", "t-fr-o"]
    assert receipt["timing"]["time_saving_ratio"] == 0.4


def test_degraded_run_is_recorded_not_dropped_by_success_binding() -> None:
    events, reader = _scenario("failed_retry")
    receipt = measure_pair(events, PROTOCOL, reader)
    degraded = next(a for a in receipt["tasks"]["assisted"]["attempts"] if a["attempt_id"] == "a-fr-2")
    assert degraded["degraded"] is True
    assert degraded["degrades"] == ["llm_unavailable_template_answer"]
    assert degraded["failed"] is False


def test_missing_run_evidence_makes_receipt_incomplete_not_invalid() -> None:
    events, _ = _scenario("failed_retry")
    receipt = measure_pair(events, PROTOCOL, InMemoryEvidenceReader())
    assert receipt["status"] == C.RECEIPT_INCOMPLETE
    assert {"run_evidence_missing:r-fr-1", "run_evidence_missing:r-fr-2"} <= set(receipt["limitations"])
    # 事件自报的 failed 仍然入账：分母不能因为 store 暂时读不到而少一个失败。
    assert receipt["tasks"]["assisted"]["failed_attempt_count"] == 1


# ------------------------------------------------------------------ 费用缺口 -----


def test_cost_gaps_are_retained_not_zeroed_or_merged() -> None:
    events, reader = _scenario("cost_gaps")
    receipt = measure_pair(events, PROTOCOL, reader)
    assert receipt["status"] == C.RECEIPT_INCOMPLETE
    assert receipt["known_cost_by_currency"] == {"CNY": 0.3, "USD": 0.05}  # 混币种并列，不合并
    reasons = {(u["component"], u["reason"]) for u in receipt["unknown_cost_components"]}
    assert reasons == {
        ("writer_model", "usage_without_rate"),  # 总 tokens 缺费率
        ("retry", "no_usage_evidence_for_attempt"),  # 失败重试无账
        ("manual_rescue", "manual_time_uncosted"),  # 人工救援未计费
    }
    assert "usage_missing:c-cg-r" in receipt["limitations"]  # 自审缺用量
    assert receipt["manual_minutes"] == {"rescue": 10.0}
    assert receipt["timing"]["original"]["certainty"] == C.CERTAINTY_ESTIMATED
    assert receipt["timing"]["assisted"]["manual_rescue_minutes"] == 10.0


def test_review_without_blind_review_consent_is_excluded_and_quality_unknown() -> None:
    events, reader = _scenario("cost_gaps")
    receipt = measure_pair(events, PROTOCOL, reader)
    assert receipt["quality"]["assisted"] == {"status": "unknown", "reason": "no_independent_review"}
    assert {"id": "e-cg-a-review", "reason": "blind_review_consent_missing", "rule_version": "1"} in receipt["exclusions"]
    assert "quality_unknown:t-cg-a" in receipt["limitations"]


def test_no_cost_evidence_for_attempt_is_unknown_not_zero() -> None:
    events, reader = _scenario("complete_pair")
    receipt = measure_pair(_without(events, "e-cp-a-cost-w", "e-cp-a-cost-r", "e-cp-a-cost-span"), PROTOCOL, reader)
    assert receipt["known_cost_by_currency"] == {}
    assert [u["reason"] for u in receipt["unknown_cost_components"]] == ["no_usage_evidence_for_attempt"]
    assert receipt["status"] == C.RECEIPT_INCOMPLETE


def test_missing_review_makes_quality_unknown_and_receipt_incomplete() -> None:
    events, reader = _scenario("complete_pair")
    receipt = measure_pair(_without(events, "e-cp-a-review"), PROTOCOL, reader)
    assert receipt["quality"]["assisted"]["status"] == "unknown"
    assert receipt["quality"]["assisted_not_lower"] is None
    assert receipt["status"] == C.RECEIPT_INCOMPLETE
    assert "quality_unknown:t-cp-a" in receipt["limitations"]


# ------------------------------------------------------------------ 无效判定 -----


def test_artifact_hash_mismatch_invalidates() -> None:
    events, evidence, _ = build_scenario("complete_pair", P_HASH)
    evidence["runs"][0]["artifacts"]["art-cp-1"] = "9" * 64
    receipt = measure_pair(events, PROTOCOL, InMemoryEvidenceReader.from_json(evidence))
    assert receipt["status"] == C.RECEIPT_INVALID
    assert "artifact_hash_mismatch" in _codes(receipt)


def test_cross_owner_run_invalidates_without_leaking() -> None:
    events, evidence, _ = build_scenario("complete_pair", P_HASH)
    evidence["runs"][0]["owner_user_id"] = "someone_else"
    receipt = measure_pair(events, PROTOCOL, InMemoryEvidenceReader.from_json(evidence))
    assert receipt["status"] == C.RECEIPT_INVALID
    assert "run_cross_owner" in _codes(receipt)
    attempt = receipt["tasks"]["assisted"]["attempts"][0]
    assert attempt["evidence_status"] == "cross_owner" and attempt["run_status"] is None


def test_condition_mismatch_invalidates() -> None:
    events, reader = _scenario("complete_pair")
    _find(events, "e-cp-a-int2")["assistance_condition"] = "original"
    receipt = measure_pair(events, PROTOCOL, reader)
    assert receipt["status"] == C.RECEIPT_INVALID
    assert "condition_mismatch" in _codes(receipt)


def test_case_version_mismatch_invalidates() -> None:
    events, reader = _scenario("complete_pair")
    _find(events, "e-cp-a-int2")["case_version"] = "2"
    receipt = measure_pair(events, PROTOCOL, reader)
    assert "case_version_mismatch" in _codes(receipt)


def test_assignment_under_other_protocol_is_rejected_and_pair_unmeasurable() -> None:
    events, reader = _scenario("complete_pair")
    _find(events, "e-cp-assign-a")["payload"]["protocol_hash"] = "0" * 64
    receipt = measure_pair(events, PROTOCOL, reader)
    assert receipt["event_accounting"]["rejected"][0]["event_id"] == "e-cp-assign-a"
    assert "missing_assignment:assisted" in receipt["limitations"]
    assert receipt["status"] == C.RECEIPT_INCOMPLETE


def test_same_participant_same_case_invalidates() -> None:
    events, reader = _scenario("complete_pair")
    for event in events:
        if event.get("assistance_condition") == "assisted":
            event["case_id"] = "case-fc-01"
    receipt = measure_pair(events, PROTOCOL, reader)
    assert "same_participant_same_case" in _codes(receipt)


def test_events_of_another_pair_invalidate_instead_of_silently_dropping() -> None:
    events, reader = _scenario("complete_pair")
    other_events, _, _ = build_scenario("failed_retry", P_HASH)
    receipt = measure_pair(events + [other_events[3]], PROTOCOL, reader, case_pair_id="pair-01")
    assert C.ERR_PAIR_MISMATCH in _codes(receipt)


def test_original_time_zero_is_excluded_under_registered_rule() -> None:
    events, reader = _scenario("complete_pair")
    events = _without(events, "e-cp-o-int2", "e-cp-o-int3")
    zero = _find(events, "e-cp-o-int1")["payload"]
    zero["start"] = zero["end"] = ts("09-15", "10:00:00")
    _find(events, "e-cp-o-done")["event_at"] = ts("09-15", "10:00:00")
    receipt = measure_pair(events, PROTOCOL, reader)
    assert receipt["timing"]["original"]["end_to_end_minutes"] == 0.0
    assert receipt["timing"]["time_saving_ratio"] is None
    assert receipt["timing"]["time_saving_reason"] == "original_time_zero"
    assert {"id": "pair-01", "reason": "original_time_zero", "rule_version": "1"} in receipt["exclusions"]


# ------------------------------------------------------------------- 同意 -----


def test_withdrawn_consent_excludes_events_but_keeps_task_in_denominator() -> None:
    events, reader = _scenario("complete_pair")
    withdraw = ev(
        "consent_changed",
        event_id="e-cp-consent-withdraw",
        at=ts("09-14", "20:00:00"),
        channel=SOURCE_MANUAL,
        participant="p01",
        payload={"consent_version": "consent-v1", "scopes": ["research"], "effective_at": ts("09-14", "20:00:00"), "action": "withdraw", "terms_hash": "sha256:" + "f" * 64},
    )
    receipt = measure_pair(events + [withdraw], PROTOCOL, reader)
    assert any(x["reason"] == "consent_withdrawn" and x["rule_version"] == "1" for x in receipt["exclusions"])
    assert receipt["denominator_ids"] == ["t-cp-a", "t-cp-o"]
    assert receipt["numerator_ids"] == []  # 撤回后的完成事件不进有效测量
    assert receipt["status"] == C.RECEIPT_INCOMPLETE


def test_missing_consent_record_is_unknown_not_assumed() -> None:
    events, reader = _scenario("complete_pair")
    receipt = measure_pair(_without(events, "e-cp-consent"), PROTOCOL, reader)
    assert "consent_unknown:p01" in receipt["limitations"]
    assert receipt["status"] == C.RECEIPT_INCOMPLETE


def test_cohort_level_events_without_pair_are_not_orphans() -> None:
    events, reader = _scenario("complete_pair")
    cohort_events, _, _ = build_scenario("cohort_signals", P_HASH)
    receipt = measure_pair(events + cohort_events, PROTOCOL, reader, case_pair_id="pair-01")
    assert receipt["status"] == C.RECEIPT_VALID
    assert not any(lim.startswith("orphan_task_events") for lim in receipt["limitations"])


def test_owner_is_taken_from_events_and_hash_a_matches_reader() -> None:
    events, reader = _scenario("complete_pair")
    receipt = measure_pair(events, PROTOCOL, reader)
    assert receipt["owner_user_id"] == OWNER
    assert reader.resolve_run(OWNER, "r-cp-1")["artifacts"] == {"art-cp-1": HASH_A}


# ------------------------------------------------- 返修 PV1：缺同意不得当作已同意 -----


def test_missing_consent_record_blocks_blind_review_quality() -> None:
    """评审 PV1：没有任何同意记录时，盲审既不能进质量读数，也不能让配对可比。

    原实现只在「有 scopes 但不含 blind_review」时排除评审，未知同意范围被当成已同意，
    于是缺同意的配对照样算出 assisted_not_lower，汇总层据此判 pass。
    """
    events, reader = _scenario("complete_pair")
    receipt = measure_pair(_without(events, "e-cp-consent"), PROTOCOL, reader)
    assert "consent_unknown:p01" in receipt["limitations"]
    for condition in (C.CONDITION_ORIGINAL, C.CONDITION_ASSISTED):
        assert receipt["tasks"][condition]["quality"] == {
            "status": "unknown",
            "reason": "blind_review_consent_unknown",
        }
    assert {"id": "e-cp-a-review", "reason": "blind_review_consent_unknown", "rule_version": "1"} in receipt["exclusions"]
    assert receipt["quality"]["assisted_not_lower"] is None
    assert receipt["quality"]["severe_error_count_assisted"] is None
    assert receipt["status"] == C.RECEIPT_INCOMPLETE
