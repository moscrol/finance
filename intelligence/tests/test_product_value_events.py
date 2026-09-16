"""ProductValueEvent 合同校验与幂等（spec §5 验收 1 / 5 / 8 的事件层）。"""

from __future__ import annotations

import copy
import random

import pytest

from intelligence.services.product_value import contracts as C
from intelligence.services.product_value.events import prepare_events, validate_event
from intelligence.tests.product_value_fixtures import (
    SCENARIOS,
    build_protocol,
    build_scenario,
    ts,
)

PROTOCOL = build_protocol()
P_HASH = PROTOCOL["protocol_hash"]


def _events(name: str) -> list[dict]:
    return build_scenario(name, P_HASH)[0]


def _find(events: list[dict], event_id: str) -> dict:
    return copy.deepcopy(next(e for e in events if e["event_id"] == event_id))


def _codes(event: dict, *, protocol=PROTOCOL) -> set[str]:
    return {issue.code for issue in validate_event(event, protocol=protocol).issues}


def test_all_fixture_scenarios_validate_clean() -> None:
    for name in SCENARIOS:
        prepared = prepare_events(_events(name), protocol=PROTOCOL)
        assert not prepared.rejected, (name, prepared.rejected)
        assert not prepared.conflicts, name
        assert prepared.accepted


def test_valid_event_normalizes_and_hashes_without_recorded_at() -> None:
    event = _find(_events("complete_pair"), "e-cp-a-done")
    first = validate_event(event, protocol=PROTOCOL)
    assert first.ok and first.normalized is not None
    later = copy.deepcopy(event)
    later["recorded_at"] = ts("09-20", "00:00:00")
    assert validate_event(later, protocol=PROTOCOL).content_hash == first.content_hash


@pytest.mark.parametrize("field", ["pilot_id", "event_at", "recorded_at", "provenance", "source_channel", "payload", "run_ids"])
def test_missing_top_level_field_rejected(field: str) -> None:
    event = _find(_events("complete_pair"), "e-cp-a-done")
    del event[field]
    assert C.ERR_MISSING_FIELD in _codes(event)


def test_null_nullable_field_needs_gap_reason() -> None:
    event = _find(_events("cohort_signals"), "e-cs-reuse-04")
    assert event["task_id"] is None and event.get("gaps")
    assert validate_event(event, protocol=PROTOCOL).ok
    event.pop("gaps")
    assert C.ERR_NULL_WITHOUT_REASON in _codes(event)


def test_schema_version_mismatch_rejected() -> None:
    event = _find(_events("complete_pair"), "e-cp-a-done")
    event["schema_version"] = "product-value-event/v0"
    assert C.ERR_SCHEMA_VERSION in _codes(event)


@pytest.mark.parametrize("field", ["event_at", "recorded_at"])
def test_naive_timestamp_rejected(field: str) -> None:
    event = _find(_events("complete_pair"), "e-cp-a-done")
    event[field] = "2026-09-15T14:20:00"
    assert C.ERR_TIMESTAMP_NAIVE in _codes(event)


def test_negative_interval_rejected() -> None:
    event = _find(_events("complete_pair"), "e-cp-a-int1")
    event["payload"]["start"], event["payload"]["end"] = event["payload"]["end"], event["payload"]["start"]
    assert C.ERR_INTERVAL_NEGATIVE in _codes(event)


def test_interval_payload_start_without_timezone_rejected() -> None:
    event = _find(_events("complete_pair"), "e-cp-a-int1")
    event["payload"]["start"] = "2026-09-15T14:00:00"
    assert C.ERR_TIMESTAMP_NAIVE in _codes(event)


@pytest.mark.parametrize(
    "scenario,event_id,channel",
    [
        ("complete_pair", "e-cp-a-done", C.SOURCE_FRONTEND),  # 前端不能自报完成
        ("complete_pair", "e-cp-a-review", C.SOURCE_FRONTEND),  # 前端不能自评质量
        ("complete_pair", "e-cp-a-cost-w", C.SOURCE_FRONTEND),  # 前端不能自报金额
        ("cohort_signals", "e-cs-pay-04", C.SOURCE_SERVER),  # 付款只能凭据导入
        ("cohort_signals", "e-cs-recheck-done-02", C.SOURCE_FRONTEND),  # 打开不算完成
        ("complete_pair", "e-cp-a-run-finish", C.SOURCE_FRONTEND),  # run 生命周期只认服务端
    ],
)
def test_source_channel_whitelist(scenario: str, event_id: str, channel: str) -> None:
    event = _find(_events(scenario), event_id)
    event["source_channel"] = channel
    assert C.ERR_SOURCE_NOT_ALLOWED in _codes(event)


def test_frontend_interval_must_use_client_clock() -> None:
    event = _find(_events("complete_pair"), "e-cp-a-int1")
    event["payload"]["clock_source"] = "server"
    assert C.ERR_SOURCE_NOT_ALLOWED in _codes(event)


def test_manual_import_requires_evidence_fields() -> None:
    event = _find(_events("complete_pair"), "e-cp-o-done")
    event["payload"]["evidence_hash"] = ""
    assert C.ERR_MANUAL_IMPORT_EVIDENCE in _codes(event)


def test_cross_owner_object_ref_rejected() -> None:
    event = _find(_events("complete_pair"), "e-cp-a-done")
    event["object_refs"][0]["scope"]["owner_user_id"] = "someone_else"
    assert C.ERR_REF_CROSS_OWNER in _codes(event)


def test_object_ref_without_namespace_or_version_rejected() -> None:
    event = _find(_events("complete_pair"), "e-cp-a-done")
    event["object_refs"][0]["namespace"] = ""
    assert C.ERR_ID_INVALID in _codes(event)
    event = _find(_events("complete_pair"), "e-cp-a-done")
    event["object_refs"][0]["version_or_hash"] = None
    assert C.ERR_REF_INVALID in _codes(event)
    event["object_refs"][0]["reason"] = "legacy_run_without_hash"
    assert validate_event(event, protocol=PROTOCOL).ok


def test_assignment_under_other_protocol_hash_rejected() -> None:
    event = _find(_events("complete_pair"), "e-cp-assign-a")
    event["payload"]["protocol_hash"] = "0" * 64
    assert C.ERR_PROTOCOL_HASH in _codes(event)
    # 不带协议时只做合同校验，不知道哈希该是什么。
    assert validate_event(event, protocol=None).ok


def test_protocol_and_rubric_version_mismatch_rejected() -> None:
    event = _find(_events("complete_pair"), "e-cp-a-done")
    event["source_version"]["protocol_version"] = "pilot-old"
    assert C.ERR_PROTOCOL_VERSION in _codes(event)
    review = _find(_events("complete_pair"), "e-cp-a-review")
    review["payload"]["rubric_version"] = "rubric-v0"
    assert C.ERR_RUBRIC_VERSION in _codes(review)


def test_rubric_dimension_out_of_range_rejected() -> None:
    review = _find(_events("complete_pair"), "e-cp-a-review")
    review["payload"]["dimensions"]["calculation"] = 3
    assert C.ERR_DIMENSION_OUT_OF_RANGE in _codes(review)
    review["payload"]["dimensions"]["calculation"] = 2
    review["payload"]["dimensions"]["style"] = 1
    assert C.ERR_DIMENSION_OUT_OF_RANGE in _codes(review)


def test_known_cost_requires_amount_currency_and_evidence() -> None:
    cost = _find(_events("complete_pair"), "e-cp-a-cost-w")
    cost["payload"]["cost_item"]["amount"] = None
    assert C.ERR_COST_ITEM_INVALID in _codes(cost)
    cost = _find(_events("complete_pair"), "e-cp-a-cost-w")
    cost["payload"]["cost_item"]["evidence_ref"] = None
    assert C.ERR_COST_ITEM_INVALID in _codes(cost)
    cost = _find(_events("complete_pair"), "e-cp-a-cost-w")
    cost["payload"]["cost_item"]["component"] = "vibes"
    assert C.ERR_ENUM_INVALID in _codes(cost)


def test_payload_common_fields_required() -> None:
    event = _find(_events("complete_pair"), "e-cp-a-start-f")
    event["payload"].pop("initiator")
    assert C.ERR_PAYLOAD_MISSING_FIELD in _codes(event)


def test_unknown_event_type_and_provenance_rejected() -> None:
    event = _find(_events("complete_pair"), "e-cp-a-start-f")
    event["event_type"] = "chat_length_recorded"
    assert C.ERR_UNKNOWN_EVENT_TYPE in _codes(event)
    event = _find(_events("complete_pair"), "e-cp-a-start-f")
    event["provenance"]["kind"] = "trusted"
    assert C.ERR_PROVENANCE_INVALID in _codes(event)


def test_run_event_must_register_run_id() -> None:
    event = _find(_events("complete_pair"), "e-cp-a-run-finish")
    event["run_ids"] = []
    assert C.ERR_REF_INVALID in _codes(event)


def test_refund_must_reference_original_payment() -> None:
    event = _find(_events("cohort_signals"), "e-cs-refund-05")
    event["payload"].pop("refunds_payment_ref")
    assert C.ERR_PAYLOAD_MISSING_FIELD in _codes(event)


def test_same_id_same_content_is_idempotent() -> None:
    events = _events("complete_pair")
    dup = copy.deepcopy(events[5])
    dup["recorded_at"] = ts("09-20", "00:00:00")
    prepared = prepare_events(events + [dup], protocol=PROTOCOL)
    assert prepared.duplicates == [dup["event_id"]]
    assert len(prepared.accepted) == len(events)
    assert not prepared.conflicts


def test_same_id_different_content_is_rejected_as_conflict() -> None:
    events = _events("complete_pair")
    original = _find(events, "e-cp-a-done")
    tampered = copy.deepcopy(original)
    tampered["payload"]["terminal_reason"] = "changed"
    prepared = prepare_events(events + [tampered], protocol=PROTOCOL)
    assert [c["event_id"] for c in prepared.conflicts] == ["e-cp-a-done"]
    assert all(e["event_id"] != "e-cp-a-done" for e in prepared.accepted)
    # 到达顺序反过来也是同一个结论。
    reversed_prepared = prepare_events([tampered] + events, protocol=PROTOCOL)
    assert [c["event_id"] for c in reversed_prepared.conflicts] == ["e-cp-a-done"]


def test_supersedes_replaces_original() -> None:
    events = _events("complete_pair")
    revision = _find(events, "e-cp-a-review")
    revision["event_id"] = "e-cp-a-review-v2"
    revision["supersedes_event_id"] = "e-cp-a-review"
    revision["payload"]["dimensions"]["calculation"] = 1
    prepared = prepare_events(events + [revision], protocol=PROTOCOL)
    ids = {e["event_id"] for e in prepared.accepted}
    assert "e-cp-a-review-v2" in ids and "e-cp-a-review" not in ids
    assert prepared.superseded == ["e-cp-a-review"]


def test_order_independence() -> None:
    events = _events("failed_retry")
    shuffled = copy.deepcopy(events)
    random.Random(7).shuffle(shuffled)
    a = prepare_events(events, protocol=PROTOCOL)
    b = prepare_events(shuffled, protocol=PROTOCOL)
    assert [e["event_id"] for e in a.accepted] == [e["event_id"] for e in b.accepted]
    assert a.content_hashes == b.content_hashes


def test_rejected_events_are_reported_not_dropped_silently() -> None:
    events = _events("complete_pair")
    broken = _find(events, "e-cp-a-int1")
    broken["event_at"] = "not a time"
    prepared = prepare_events(events + [broken], protocol=PROTOCOL)
    # 同 id 的坏副本被拒收，好副本照常入账；拒收清单带稳定码。
    assert prepared.rejected and prepared.rejected[0]["event_id"] == "e-cp-a-int1"
    assert {i["code"] for i in prepared.rejected[0]["issues"]} & {C.ERR_TIMESTAMP_INVALID}
    assert any(e["event_id"] == "e-cp-a-int1" for e in prepared.accepted)
