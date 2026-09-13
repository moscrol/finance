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
    # round-9：成功 attempt a-fr-2 只挂了 writer 的账——review 缺口由收据自身携带（与汇总层同规则）
    assert [u["reason"] for u in receipt["unknown_cost_components"]] == ["no_usage_evidence_for_attempt", "usage_without_rate"]
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
        # round-9：失败执行缺的是 writer 模型账（retry 是费用类别，不是该次执行被漏记的消耗）
        ("writer_model", "no_usage_evidence_for_attempt"),
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
    # round-9：成功 attempt 无任何账 → 逐组件缺口 writer+review 两条（不再合并为一条）
    unbilled = [u for u in receipt["unknown_cost_components"] if u["reason"] == "no_usage_evidence_for_attempt"]
    assert {u["component"] for u in unbilled} == {"writer_model", "review_model"}
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


def test_attempt_run_conflict_is_flagged_and_blocks_full_cost():
    """round-8 补遗 P1：同一 attempt_id 绑定到两个不同 run——合并前必须验身份冲突，
    显式留错并降级收据、阻断完整成本，不能静默保留第一条让第二次执行消失。"""
    import copy as _copy
    from datetime import datetime as _dt, timedelta as _td

    from intelligence.services.product_value.summarize import summarize
    from intelligence.tests.test_product_value_summarize import _r7_setup

    proto, complete, evidence1, _, evidence2, writer, review, base = _r7_setup()
    attempt1 = next(e for e in base if e["event_type"] == "run_started")["payload"]["attempt_id"]
    run2 = "qc-r8-run-2"
    extra_events = []
    for event in base:
        if event["event_type"] in {"run_started", "run_finished"}:
            extra = _copy.deepcopy(event)
            extra["event_id"] += "-second"
            extra["run_ids"] = [run2]
            extra["payload"].update(run_id=run2, attempt_id=attempt1)  # 第二次生命周期误复用 attempt1
            for key in ("event_at", "recorded_at"):
                extra[key] = (_dt.fromisoformat(extra[key]) + _td(minutes=8)).isoformat()
            extra_events.append(extra)
    evidence_extra = _copy.deepcopy(evidence2["runs"][0])
    evidence_extra.update(run_id=run2, artifacts={})
    for key in ("created_at", "finished_at"):
        evidence_extra[key] = (_dt.fromisoformat(evidence_extra[key]) + _td(minutes=8)).isoformat()
    reader = InMemoryEvidenceReader.from_json({"runs": evidence1["runs"] + evidence2["runs"] + [evidence_extra]})
    events = base + extra_events + [writer, review]  # 只给 run1 完整费用
    r2 = measure_pair(events, proto, reader)
    assert r2["invalid_reasons"] == [] and r2["event_accounting"]["rejected"] == []
    assert r2["status"] == "incomplete"  # 不是 valid——冲突必须降级
    assert any(lim.startswith("attempt_run_conflict:") for lim in r2["limitations"])
    conflict = [u for u in r2["unknown_cost_components"] if u["reason"] == "attempt_run_conflict"]
    assert conflict and conflict[0]["attempt_id"] == attempt1
    summary = summarize(
        [measure_pair(complete, proto, reader), r2],
        [e for e in complete + events if e["event_type"] == "assignment_created"],
        proto, cohort_events=complete + events, due_rechecks=[],
    )
    cost = next(m for m in summary["metrics"] if m["metric_id"] == "cost_full_status")
    assert cost["detail"]["full_cost_status"] == "unknown"


def test_receipt_gap_clearance_uses_joint_identity():
    """round-8 补遗 P1：收据层派生缺口与汇总层共用联合身份——错配费用（attempt_id 指
    第二次执行、run_id 是第一次的 run）不得消掉执行缺账；收据自身携带缺口并降级。"""
    import copy as _copy
    from datetime import datetime as _dt, timedelta as _td

    from intelligence.tests.test_product_value_summarize import _r7_fee, _r7_setup

    proto, complete, evidence1, _, evidence2, writer, review, base = _r7_setup()
    run2, attempt2 = "qc-r8-run-2", "qc-r8-attempt-2"
    extra_events = []
    for event in base:
        if event["event_type"] in {"run_started", "run_finished"}:
            extra = _copy.deepcopy(event)
            extra["event_id"] += "-second"
            extra["run_ids"] = [run2]
            extra["payload"].update(run_id=run2, attempt_id=attempt2)
            for key in ("event_at", "recorded_at"):
                extra[key] = (_dt.fromisoformat(extra[key]) + _td(minutes=8)).isoformat()
            extra_events.append(extra)
    evidence_extra = _copy.deepcopy(evidence2["runs"][0])
    evidence_extra.update(run_id=run2, artifacts={})
    for key in ("created_at", "finished_at"):
        evidence_extra[key] = (_dt.fromisoformat(evidence_extra[key]) + _td(minutes=8)).isoformat()
    two_runs = evidence2["runs"] + [evidence_extra]
    two_base = base + extra_events + [writer, review]
    run1 = writer["payload"]["cost_item"]["run_id"]
    reader = InMemoryEvidenceReader.from_json({"runs": evidence1["runs"] + two_runs})

    mismatched = [
        _r7_fee(writer, "tool", 0.01, run_id=run1, attempt_id=attempt2, suffix="-mm-tool"),
        _r7_fee(writer, "writer_model", 0.36, run_id=run1, attempt_id=attempt2, suffix="-mm-writer"),
        _r7_fee(writer, "review_model", 0.10, run_id=run1, attempt_id=attempt2, suffix="-mm-review"),
    ]
    r2 = measure_pair(two_base + mismatched, proto, reader)
    assert r2["status"] == "incomplete"  # 收据自身降级
    gaps = [u for u in r2["unknown_cost_components"] if u["reason"] == "no_usage_evidence_for_attempt" and u["attempt_id"] == attempt2]
    assert gaps, "错配费用不得消掉第二次执行的缺账"
    # 合法对照：联合一致的同一组费用 → 收据 valid、无执行缺账
    consistent = [
        _r7_fee(writer, "tool", 0.01, run_id=run2, attempt_id=attempt2, suffix="-ok-tool"),
        _r7_fee(writer, "writer_model", 0.36, run_id=run2, attempt_id=attempt2, suffix="-ok-writer"),
        _r7_fee(writer, "review_model", 0.10, run_id=run2, attempt_id=attempt2, suffix="-ok-review"),
    ]
    r2_ok = measure_pair(two_base + consistent, proto, reader)
    assert r2_ok["status"] == "valid"
    assert [u for u in r2_ok["unknown_cost_components"] if u["reason"] == "no_usage_evidence_for_attempt"] == []


def _r9_two_attempt_base():
    """round-9 公共夹具：第二配对 + 第二次执行（run2×attempt2），第一次执行账齐。"""
    import copy as _copy
    from datetime import datetime as _dt, timedelta as _td

    from intelligence.tests.test_product_value_summarize import _r7_setup

    proto, complete, evidence1, _, evidence2, writer, review, base = _r7_setup()
    run2, attempt2 = "qc-r9-run-2", "qc-r9-attempt-2"
    extra_events = []
    for event in base:
        if event["event_type"] in {"run_started", "run_finished"}:
            extra = _copy.deepcopy(event)
            extra["event_id"] += "-second"
            extra["run_ids"] = [run2]
            extra["payload"].update(run_id=run2, attempt_id=attempt2)
            for key in ("event_at", "recorded_at"):
                extra[key] = (_dt.fromisoformat(extra[key]) + _td(minutes=8)).isoformat()
            extra_events.append(extra)
    evidence_extra = _copy.deepcopy(evidence2["runs"][0])
    evidence_extra.update(run_id=run2, artifacts={})
    for key in ("created_at", "finished_at"):
        evidence_extra[key] = (_dt.fromisoformat(evidence_extra[key]) + _td(minutes=8)).isoformat()
    reader = InMemoryEvidenceReader.from_json({"runs": evidence1["runs"] + evidence2["runs"] + [evidence_extra]})
    return proto, complete, evidence1, writer, review, base, extra_events, reader, run2, attempt2, evidence2["runs"] + [evidence_extra]


def test_excluded_fine_fee_cannot_clear_attempt_gap():
    """round-9 P1：被去重排除（selected=False）的费用不能核销执行缺口——先统一有效
    费用候选集，再做身份匹配。错配 run 级粗账（attempt_id 指第一次执行）+ 身份正确的
    attempt 级细账（被粗账挤出）→ 收据仍 incomplete、缺口保留。"""
    from intelligence.tests.test_product_value_summarize import _r7_fee

    proto, _, _, writer, _, base, extra_events, reader, run2, attempt2, _ = _r9_two_attempt_base()
    attempt1 = next(e for e in base if e["event_type"] == "run_started")["payload"]["attempt_id"]
    run1 = writer["payload"]["cost_item"]["run_id"]
    coarse = _r7_fee(writer, "writer_model", 0.36, run_id=run2, attempt_id=attempt1, suffix="-r9-coarse")  # 身份错配的 run 级粗账
    fine = _r7_fee(writer, "writer_model", 0.36, run_id=run2, attempt_id=attempt2, suffix="-r9-fine")  # 身份正确的 attempt 级细账
    fine["payload"]["cost_item"]["coverage_scope"] = "attempt"
    events = base + extra_events + [writer, _r7_fee(writer, "review_model", 0.10, run_id=run1, attempt_id=attempt1, suffix="-r9-review")]
    r2 = measure_pair(events + [coarse, fine], proto, reader)
    fine_item = next(i for i in r2["cost_items"] if i["cost_id"].endswith("-r9-fine"))
    assert fine_item["selected"] is False  # 前置：细账确实被去重排除
    assert r2["status"] == "incomplete"  # 被排除的账不能证明「账齐了」
    gaps = {u["component"] for u in r2["unknown_cost_components"] if u["reason"] == "no_usage_evidence_for_attempt" and u["attempt_id"] == attempt2}
    assert gaps == {"writer_model", "review_model"}


def test_receipt_gap_requires_per_component_completeness():
    """round-9 P1：收据层与汇总层共用「按协议 × 执行实例 × 组件」规则——一笔工具费
    不能核销整个执行的缺口；成功执行要 writer+review，失败执行只要 writer（合法通路）。"""
    import copy as _copy

    from intelligence.tests.test_product_value_summarize import _r7_fee

    proto, _, _, writer, review, base, extra_events, reader, run2, attempt2, runs2 = _r9_two_attempt_base()
    run1 = writer["payload"]["cost_item"]["run_id"]
    attempt1 = next(e for e in base if e["event_type"] == "run_started")["payload"]["attempt_id"]
    first_bills = [writer, _r7_fee(review, "review_model", 0.10, run_id=run1, attempt_id=attempt1, suffix="-r9-r1")]
    two_base = base + extra_events + first_bills

    def gaps_for(fees):
        r2 = measure_pair(two_base + fees, proto, reader)
        gaps = {u["component"] for u in r2["unknown_cost_components"] if u["reason"] == "no_usage_evidence_for_attempt" and u["attempt_id"] == attempt2}
        return r2, gaps

    r2, gaps = gaps_for([_r7_fee(writer, "tool", 0.01, run_id=run2, attempt_id=attempt2, suffix="-r9-t")])
    assert r2["status"] == "incomplete" and gaps == {"writer_model", "review_model"}  # 只有工具费
    r2, gaps = gaps_for([
        _r7_fee(writer, "writer_model", 0.36, run_id=run2, attempt_id=attempt2, suffix="-r9-w"),
        _r7_fee(writer, "tool", 0.01, run_id=run2, attempt_id=attempt2, suffix="-r9-t"),
    ])
    assert r2["status"] == "incomplete" and gaps == {"review_model"}  # 写手+工具费
    r2, gaps = gaps_for([
        _r7_fee(writer, "writer_model", 0.36, run_id=run2, attempt_id=attempt2, suffix="-r9-w"),
        _r7_fee(review, "review_model", 0.10, run_id=run2, attempt_id=attempt2, suffix="-r9-r"),
        _r7_fee(writer, "tool", 0.01, run_id=run2, attempt_id=attempt2, suffix="-r9-t"),
    ])
    assert r2["status"] == "valid" and gaps == set()  # 合法对照：三件套
    # 合法通路：失败执行只要 writer 账（review 未发生不强要）
    failed_events = _copy.deepcopy(extra_events)
    for event in failed_events:
        if event["event_type"] == "run_finished":
            event["payload"].update(status="failed", error_ref="err:writer-timeout")
            event["event_id"] += "-f"
        else:
            event["event_id"] += "-f"
    failed_run = _copy.deepcopy(runs2[-1])  # 克隆已知良好的 run 证据记录，只改身份与状态
    failed_run.update(run_id="qc-r9-run-3", status="failed", error="writer timeout", artifacts={})
    for event in failed_events:
        event["run_ids"] = ["qc-r9-run-3"]
        event["payload"].update(run_id="qc-r9-run-3", attempt_id="qc-r9-attempt-3")
    reader2 = InMemoryEvidenceReader.from_json({"runs": runs2 + [failed_run]})
    r2 = measure_pair(base + failed_events + first_bills + [
        _r7_fee(writer, "writer_model", 0.36, run_id="qc-r9-run-3", attempt_id="qc-r9-attempt-3", suffix="-r9-fw"),
    ], proto, reader2)
    gaps = {u["component"] for u in r2["unknown_cost_components"] if u["reason"] == "no_usage_evidence_for_attempt" and u["attempt_id"] == "qc-r9-attempt-3"}
    assert r2["status"] == "valid" and gaps == set()
