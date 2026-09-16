"""I14 消费合同：客户端隐藏区间进现有05纯函数，不产生虚假端到端加速。"""
from intelligence.services.product_value.evidence import InMemoryEvidenceReader
from intelligence.services.product_value.measure import measure_pair
from intelligence.tests.product_value_fixtures import (
    SOURCE_FRONTEND,
    build_protocol,
    build_scenario,
    ev,
    ts,
)


def test_hidden_interval_keeps_end_to_end_and_only_removes_in_app_active_time():
    protocol = build_protocol()
    events, evidence, _ = build_scenario("complete_pair", protocol["protocol_hash"])
    # 沿用冻结任务/同意/终态/独立证据，只替换辅助任务的客户端区间。
    events = [e for e in events if not (e.get("task_id") == "t-cp-a" and e["event_type"] == "time_interval")]
    for index, (start, end, hidden) in enumerate([
        ("14:00:00", "14:05:00", False),
        ("14:05:00", "14:15:00", True),
        ("14:15:00", "14:30:00", False),
    ]):
        events.append(ev(
            "time_interval", event_id=f"visibility-{index}", at=ts("09-15", end),
            channel=SOURCE_FRONTEND, participant="p01", task="t-cp-a",
            case="case-fc-02", case_version="1", pair="pair-01", condition="assisted",
            payload={
                "interval_id": f"visibility-{index}", "start": ts("09-15", start), "end": ts("09-15", end),
                "activity": "pause" if hidden else "user_active", "clock_source": "client",
                "pause_reason": "tab_hidden" if hidden else None, "visibility": "hidden" if hidden else "visible",
            },
        ))
    result = measure_pair(events, protocol, InMemoryEvidenceReader.from_json(evidence))
    timing = result["timing"]["assisted"]
    assert timing["end_to_end_minutes"] == 30.0
    assert timing["user_active_minutes"] == 20.0
    assert timing["pause_deducted_minutes"] == 0.0
    assert timing["pause_not_deducted"] == [{"interval_id": "visibility-1", "pause_reason": "tab_hidden"}]
