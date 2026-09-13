"""summarize：分母纪律、判据阻断、synthetic 隔离、三态分离（spec §5 验收 1、4、6、7）。"""

from __future__ import annotations

import copy
import json
import random
from datetime import datetime, timezone

from intelligence.services.product_value import contracts as C
from intelligence.services.product_value.evidence import InMemoryEvidenceReader
from intelligence.services.product_value.measure import measure_pair
from intelligence.services.product_value.protocol import freeze_protocol
from intelligence.services.product_value.summarize import (
    UNKNOWN_CONSENT,
    UNKNOWN_GAP,
    UNKNOWN_SAMPLE,
    UNKNOWN_UNSTARTED,
    summarize,
)
from intelligence.tests.product_value_fixtures import (
    PROVENANCE_SYNTHETIC,
    SOURCE_FRONTEND,
    SOURCE_MANUAL,
    SOURCE_SERVER,
    build_protocol,
    build_scenario,
    ev,
    scenario_cohort_signals,
    scenario_complete_pair,
    ts,
)

PROTOCOL = build_protocol()
P_HASH = PROTOCOL["protocol_hash"]
IMPORTED = "imported"


def _split(events: list[dict]) -> tuple[list[dict], list[dict]]:
    assignments = [e for e in events if e["event_type"] == "assignment_created"]
    cohort = [e for e in events if e["event_type"] != "assignment_created"]
    return assignments, cohort


def _pipeline(names: list[str], *, provenance: str, protocol: dict = PROTOCOL, extra_events: list[dict] | None = None, due=None, as_of=None):
    """按场景造事件 → 逐配对 measure → summarize；返回 (summary, receipts, all_events)。"""
    events: list[dict] = []
    evidence = {"runs": []}
    due_from_fixture = None
    for name in names:
        scenario_events, scenario_evidence, scenario_due = build_scenario(name, protocol["protocol_hash"], provenance=provenance)
        events.extend(scenario_events)
        evidence["runs"].extend(scenario_evidence["runs"])
        if scenario_due is not None:
            due_from_fixture = scenario_due
    if extra_events:
        events.extend(extra_events)
    reader = InMemoryEvidenceReader.from_json(evidence)
    pairs = sorted({e["case_pair_id"] for e in events if e.get("case_pair_id")})
    cohort_only = [e for e in events if not e.get("case_pair_id")]
    receipts = [measure_pair([e for e in events if e.get("case_pair_id") == pair] + cohort_only, protocol, reader, case_pair_id=pair) for pair in pairs]
    assignments, cohort = _split(events)
    summary = summarize(receipts, assignments, protocol, cohort_events=cohort, due_rechecks=due if due is not None else due_from_fixture, as_of=as_of)
    return summary, receipts, events


def _criteria(summary: dict, *, synthetic: bool = False) -> dict[str, dict]:
    block = summary["synthetic_check"] if synthetic else summary
    return {c["criterion_id"]: c for c in block["criteria_results"]}


def _metric(summary: dict, metric_id: str, *, synthetic: bool = False) -> dict:
    block = summary["synthetic_check"] if synthetic else summary
    return next(m for m in block["metrics"] if m["metric_id"] == metric_id)


# ------------------------------------------------------------- 六对配对协议 -----


def _six_pair_protocol() -> dict:
    proto = build_protocol()
    proto.pop("protocol_hash")
    for i in range(1, 7):
        category = "fact_check" if i % 2 else "judgment_recheck"
        proto["cases"].append({"case_id": f"case-x{i}a", "case_version": "1", "category": category, "title": f"x{i}a"})
        proto["cases"].append({"case_id": f"case-x{i}b", "case_version": "1", "category": category, "title": f"x{i}b"})
        proto["case_pairs"].append({"case_pair_id": f"pair-x{i}", "category": category, "case_ids": [f"case-x{i}a", f"case-x{i}b"]})
    return freeze_protocol(proto)


def _clone_complete_pair(i: int, participant: str, new_hash: str, *, provenance: str) -> tuple[list[dict], dict]:
    events, evidence = scenario_complete_pair(P_HASH, provenance=provenance)
    text = json.dumps({"events": events, "evidence": evidence}, ensure_ascii=False)
    for old, new in (("pair-01", f"pair-x{i}"), ("case-fc-01", f"case-x{i}a"), ("case-fc-02", f"case-x{i}b"), ('"p01"', f'"{participant}"'), ("-cp-", f"-x{i}-"), (P_HASH, new_hash)):
        text = text.replace(old, new)
    data = json.loads(text)
    return data["events"], data["evidence"]


def _six_pairs(*, provenance: str, mutate=None):
    proto = _six_pair_protocol()
    events: list[dict] = []
    evidence = {"runs": []}
    for i in range(1, 7):
        pair_events, pair_evidence = _clone_complete_pair(i, f"p1{(i - 1) % 3}", proto["protocol_hash"], provenance=provenance)
        if mutate:
            mutate(i, pair_events)
        events.extend(pair_events)
        evidence["runs"].extend(pair_evidence["runs"])
    reader = InMemoryEvidenceReader.from_json(evidence)
    receipts = [measure_pair([e for e in events if e.get("case_pair_id") == f"pair-x{i}"] + [e for e in events if not e.get("case_pair_id")], proto, reader) for i in range(1, 7)]
    assignments, cohort = _split(events)
    return proto, receipts, assignments, cohort


# ------------------------------------------------------------------ 确定性 -----


def test_summary_is_deterministic_and_order_invariant() -> None:
    summary, receipts, events = _pipeline(["complete_pair", "failed_retry", "cost_gaps", "cohort_signals"], provenance=PROVENANCE_SYNTHETIC)
    assignments, cohort = _split(events)
    shuffled_receipts = list(reversed(receipts))
    noisy_cohort = copy.deepcopy(cohort) + copy.deepcopy(cohort[:5])
    random.Random(11).shuffle(noisy_cohort)
    again = summarize(shuffled_receipts, list(reversed(assignments)), PROTOCOL, cohort_events=noisy_cohort, due_rechecks=build_scenario("cohort_signals", P_HASH)[2], now=datetime(2027, 1, 1, tzinfo=timezone.utc))
    assert again["summary_id"] == summary["summary_id"]
    assert again["generated_at"] != summary["generated_at"]
    assert again["metrics"] == summary["metrics"]
    assert again["synthetic_check"]["metrics"] == summary["synthetic_check"]["metrics"]
    assert again["event_accounting"]["duplicates"] == sorted(e["event_id"] for e in cohort[:5])


# ------------------------------------------------------------ synthetic 隔离 -----


def test_synthetic_inputs_never_become_field_or_revenue() -> None:
    summary, _, _ = _pipeline(["complete_pair", "failed_retry", "cost_gaps", "cohort_signals"], provenance=PROVENANCE_SYNTHETIC)
    assert summary["engineering_status"] == C.ENGINEERING_COMPLETE
    assert summary["field_status"] == C.FIELD_PENDING
    assert summary["commercial_status"] == C.COMMERCIAL_UNSTARTED
    assert summary["provenance"]["synthetic"] is True
    assert all(m["value"] is None for m in summary["metrics"])
    assert "real_participants_absent" in summary["limitations"]
    check = summary["synthetic_check"]
    assert check["counts_toward_field"] is False and check["synthetic"] is True
    # 同一套判据在仿真数据上确实算出了东西——工程被验证，效果没被宣布。
    assert _metric(summary, "time_saving_median", synthetic=True)["value"] == 0.4
    # 复用分母是激活队列：做过配对任务的 p01–p03 也在里面，他们没有复用观察记录，
    # 于是比率不完整 → unknown(gap)。旧期望 fail 建立在「分母只有 p04–p06」之上，
    # 那个分母本身漏掉了没复用的人（评审 PV3）。
    syn_reuse = _metric(summary, "proactive_reuse_rate", synthetic=True)
    assert syn_reuse["denominator_ids"] == ["p01", "p02", "p03", "p04", "p05", "p06"]
    assert syn_reuse["numerator_ids"] == ["p04"] and syn_reuse["value"] == 0.1667
    assert _criteria(summary, synthetic=True)["proactive_reuse"]["verdict"] == C.VERDICT_UNKNOWN
    assert _metric(summary, "cost_full_status", synthetic=True)["detail"]["revenue_by_currency"] == {"CNY": 199.0}
    assert _criteria(summary)["recheck"]["reason"] == "no_real_inputs"


def test_mixed_real_and_synthetic_receipts_are_partitioned() -> None:
    real_events, real_evidence, _ = build_scenario("complete_pair", P_HASH, provenance=IMPORTED)
    syn_events, syn_evidence, _ = build_scenario("failed_retry", P_HASH)
    reader = InMemoryEvidenceReader.from_json({"runs": real_evidence["runs"] + syn_evidence["runs"]})
    receipts = [measure_pair(real_events, PROTOCOL, reader), measure_pair(syn_events, PROTOCOL, reader)]
    assignments, cohort = _split(real_events + syn_events)
    summary = summarize(receipts, assignments, PROTOCOL, cohort_events=cohort, due_rechecks=[])
    provenance = summary["provenance"]
    assert provenance["real_receipts"] == 1 and provenance["synthetic_receipts"] == 1
    assert provenance["real_events"] == len(real_events) and provenance["synthetic_events"] == len(syn_events)
    assert provenance["synthetic"] is True
    assert _metric(summary, "assisted_completion_rate")["denominator_ids"] == ["t-cp-a"]
    assert _metric(summary, "assisted_completion_rate", synthetic=True)["denominator_ids"] == ["t-fr-a"]
    assert summary["field_status"] != C.FIELD_PENDING


# ---------------------------------------------------------------- 真人分母 -----


def test_imported_inputs_reach_field_and_commercial_status() -> None:
    summary, _, _ = _pipeline(["complete_pair", "cohort_signals"], provenance=IMPORTED)
    assert summary["field_status"] == C.FIELD_OBSERVED  # 回检有真实读数
    assert summary["commercial_status"] == C.COMMERCIAL_OBSERVED  # p04 有凭据核验的实付
    assert _metric(summary, "recheck_completion_rate")["value"] == 0.5
    assert summary["synthetic_check"] is None


def test_time_saving_unknown_until_sample_met_then_pass() -> None:
    summary, _, _ = _pipeline(["complete_pair", "failed_retry", "cost_gaps"], provenance=IMPORTED, due=[])
    ts_result = _criteria(summary)["time_saving"]
    assert ts_result["verdict"] == C.VERDICT_UNKNOWN and ts_result["unknown_kind"] == UNKNOWN_SAMPLE
    assert "complete_pairs_below_min" in ts_result["reason"]
    assert summary["field_status"] == C.FIELD_INCONCLUSIVE  # pair-03 漏审是数据缺口，不是样本不足

    proto, receipts, assignments, cohort = _six_pairs(provenance=IMPORTED)
    summary6 = summarize(receipts, assignments, proto, cohort_events=cohort, due_rechecks=[])
    metric = _metric(summary6, "time_saving_median")
    assert metric["value"] == 0.5556
    assert metric["coverage"] == {"participants": 3, "complete_pairs": 6, "categories": ["fact_check", "judgment_recheck"], "excluded_zero_original_share": 0.0}
    assert _criteria(summary6)["time_saving"]["verdict"] == C.VERDICT_PASS
    assert _criteria(summary6)["completion_quality"]["verdict"] == C.VERDICT_PASS
    assert summary6["recommendation"] == "keep_observing"  # 主动复用没样本，不能建议继续验证
    assert summary6["field_status"] == C.FIELD_OBSERVED


def test_time_saving_fails_when_assistant_is_slower() -> None:
    def slow_assisted(i: int, events: list[dict]) -> None:
        for event in events:
            if event["event_id"] == f"e-x{i}-a-done":
                event["event_at"] = ts("09-15", "16:00:00")
            if event["event_id"] == f"e-x{i}-a-int3":
                event["payload"]["end"] = ts("09-15", "16:00:00")

    proto, receipts, assignments, cohort = _six_pairs(provenance=IMPORTED, mutate=slow_assisted)
    summary = summarize(receipts, assignments, proto, cohort_events=cohort, due_rechecks=[])
    assert _metric(summary, "time_saving_median")["value"] < 0
    assert _criteria(summary)["time_saving"]["verdict"] == C.VERDICT_FAIL


def test_fast_but_lower_quality_blocks_and_pauses_recruitment() -> None:
    def degrade_quality(i: int, events: list[dict]) -> None:
        if i == 2:
            review = next(e for e in events if e["event_id"] == "e-x2-a-review")
            review["payload"]["dimensions"] = {"fact_sourcing": 1, "calculation": 1, "assumption_gaps": 1, "task_completion": 1}

    proto, receipts, assignments, cohort = _six_pairs(provenance=IMPORTED, mutate=degrade_quality)
    summary = summarize(receipts, assignments, proto, cohort_events=cohort, due_rechecks=[])
    assert _criteria(summary)["time_saving"]["verdict"] == C.VERDICT_PASS
    cq = _criteria(summary)["completion_quality"]
    assert cq["verdict"] == C.VERDICT_FAIL and "assisted_quality_lower_in_some_pairs" in cq["reason"]
    assert summary["recommendation"] == "pause_recruitment"


def test_severe_error_blocks_pass() -> None:
    def severe(i: int, events: list[dict]) -> None:
        if i == 1:
            next(e for e in events if e["event_id"] == "e-x1-a-review")["payload"]["severe_error_count"] = 1

    proto, receipts, assignments, cohort = _six_pairs(provenance=IMPORTED, mutate=severe)
    summary = summarize(receipts, assignments, proto, cohort_events=cohort, due_rechecks=[])
    assert _metric(summary, "severe_error_count_assisted")["value"] == 1
    assert "severe_errors_present" in _criteria(summary)["completion_quality"]["reason"]
    assert _criteria(summary)["completion_quality"]["verdict"] == C.VERDICT_FAIL


def test_missing_blind_review_makes_criterion_unknown_gap() -> None:
    def drop_review(i: int, events: list[dict]) -> None:
        if i == 3:
            events[:] = [e for e in events if e["event_id"] != "e-x3-a-review"]

    proto, receipts, assignments, cohort = _six_pairs(provenance=IMPORTED, mutate=drop_review)
    summary = summarize(receipts, assignments, proto, cohort_events=cohort, due_rechecks=[])
    cq = _criteria(summary)["completion_quality"]
    assert cq["verdict"] == C.VERDICT_UNKNOWN and cq["unknown_kind"] == UNKNOWN_GAP
    assert {"id": "t-x3-a", "reason": "no_independent_review"} in _metric(summary, "severe_error_count_assisted")["unknown"]


def test_dropping_failed_receipts_cannot_improve_completion_rate() -> None:
    """只保留成功样本：分母来自全部分配，没有收据的任务照样在分母里。"""

    def fail_pair_four(i: int, events: list[dict]) -> None:
        if i == 4:
            done = next(e for e in events if e["event_id"] == "e-x4-a-done")
            done["event_type"] = "task_failed"
            done["payload"]["terminal_reason"] = "wrong_answer"
            done["object_refs"] = []

    proto, receipts, assignments, cohort = _six_pairs(provenance=IMPORTED, mutate=fail_pair_four)
    survivors = [r for r in receipts if r["case_pair_id"] != "pair-x4"]
    summary = summarize(survivors, assignments, proto, cohort_events=cohort, due_rechecks=[])
    rate = _metric(summary, "assisted_completion_rate")
    assert rate["value"] == 0.8333
    assert "t-x4-a" in rate["denominator_ids"] and "t-x4-a" not in rate["numerator_ids"]
    assert {"id": "t-x4-a", "reason": "unmeasured"} in rate["unknown"]
    assert _metric(summary, "timeout_or_incomplete_rate")["value"] == 0.1667
    # 不删收据时同样不能通过：失败任务的分母与完成率一起被看见。
    full = summarize(receipts, assignments, proto, cohort_events=cohort, due_rechecks=[])
    assert _metric(full, "assisted_completion_rate")["value"] == 0.8333
    assert "assisted_completion_below_original" in _criteria(full)["completion_quality"]["reason"]
    assert _criteria(full)["completion_quality"]["verdict"] == C.VERDICT_FAIL


# ------------------------------------------------------ 主动复用 / 回检 / 续费 -----


def test_manual_reminder_and_unknown_source_are_not_proactive() -> None:
    summary, _, _ = _pipeline(["cohort_signals"], provenance=IMPORTED)
    metric = _metric(summary, "proactive_reuse_rate")
    assert metric["value"] == 0.3333
    assert metric["numerator_ids"] == ["p04"] and metric["denominator_ids"] == ["p04", "p05", "p06"]
    assert metric["detail"]["system_reminder_count"] == 1
    assert metric["detail"]["not_proactive_reasons"] == {"p05": ["manual_reminder_within_quiet_hours"], "p06": ["reminder_source_unknown"]}
    assert _criteria(summary)["proactive_reuse"]["verdict"] == C.VERDICT_FAIL


def test_auto_recheck_and_view_only_are_not_completion() -> None:
    summary, _, _ = _pipeline(["cohort_signals"], provenance=IMPORTED)
    metric = _metric(summary, "recheck_completion_rate")
    assert metric["value"] == 0.5
    assert metric["numerator_ids"] == ["j-02"] and metric["denominator_ids"] == ["j-01", "j-02"]
    assert metric["detail"]["viewed_only"] == ["j-01"]
    assert metric["detail"]["auto_recheck_not_counted"] == ["j-01"]
    assert metric["detail"]["not_yet_due"] == ["j-03"] and metric["detail"]["inaccessible"] == ["j-04"]
    assert _criteria(summary)["recheck"]["verdict"] == C.VERDICT_OBSERVED_ONLY


def test_due_list_unavailable_is_a_gap_not_zero() -> None:
    summary, _, _ = _pipeline(["cohort_signals"], provenance=IMPORTED, due=None)
    events = build_scenario("cohort_signals", P_HASH, provenance=IMPORTED)[0]
    assignments, cohort = _split(events)
    summary = summarize([], assignments, PROTOCOL, cohort_events=cohort, due_rechecks=None)
    assert _metric(summary, "recheck_completion_rate")["value"] is None
    recheck = _criteria(summary)["recheck"]
    assert recheck["verdict"] == C.VERDICT_UNKNOWN and recheck["unknown_kind"] == UNKNOWN_GAP
    assert "due_list_unavailable" in summary["limitations"]


def test_renewal_needs_verified_second_payment_and_refunds_reverse() -> None:
    events = build_scenario("cohort_signals", P_HASH, provenance=IMPORTED)[0]
    assignments, cohort = _split(events)
    early = summarize([], assignments, PROTOCOL, cohort_events=cohort, due_rechecks=[], as_of="2026-10-11")
    renewal = _criteria(early)["renewal"]
    assert renewal["verdict"] == C.VERDICT_UNKNOWN and renewal["reason"] == "renewal_window_not_reached"
    assert _metric(early, "renewal_rate")["detail"]["first_payers"] == ["p04"]  # p05 已退款，不是首付者
    assert _metric(early, "renewal_rate")["detail"]["refund_count"] == 1

    late = summarize([], assignments, PROTOCOL, cohort_events=cohort, due_rechecks=[], as_of="2026-11-30")
    assert _metric(late, "renewal_rate")["value"] == 0.0
    assert _metric(late, "renewal_rate")["denominator_ids"] == ["p04"]

    second = ev("payment_recorded", event_id="e-cs-pay-04-2", at=ts("10-15", "09:00:00"), channel=SOURCE_MANUAL, participant="p04", provenance=IMPORTED, payload={"payment_ref": "pay-04-2", "amount": 199, "currency": "CNY", "service_period": {"start": "2026-10-15", "end": "2026-11-14"}, "status": "paid", "verified_by": "bank-statement-2026-10"})
    renewed = summarize([], assignments, PROTOCOL, cohort_events=cohort + [second], due_rechecks=[], as_of="2026-11-30")
    assert _metric(renewed, "renewal_rate")["value"] == 1.0
    assert _criteria(renewed)["renewal"]["verdict"] == C.VERDICT_OBSERVED_ONLY


def test_no_first_payment_means_unstarted_and_null() -> None:
    summary, _, _ = _pipeline(["complete_pair"], provenance=IMPORTED, due=[])
    assert summary["commercial_status"] == C.COMMERCIAL_UNSTARTED
    assert _metric(summary, "renewal_rate")["value"] is None
    assert _criteria(summary)["renewal"]["unknown_kind"] == UNKNOWN_UNSTARTED


# ------------------------------------------------------------ 成本与其它纪律 -----


def test_cost_unknown_blocks_gross_margin() -> None:
    summary, _, _ = _pipeline(["failed_retry", "cohort_signals"], provenance=IMPORTED)
    detail = _metric(summary, "cost_full_status")["detail"]
    assert detail["full_cost_status"] == "unknown"
    assert detail["gross_margin"] is None and detail["gross_margin_reason"] == "cost_unknown"
    assert detail["known_cost_by_currency"] == {"CNY": 50.12}  # 0.12 + 托管 50，未知项另列不归零
    # 有用量没费率的 c-fr-2，外加整份试点一条账都没有的 9 个费用类别（评审 PV2）。
    # 旧期望只数收据自己列出的 1 项，等于默认「没观察到的类别 = 没花钱」。
    unknown = {u["id"]: u["reason"] for u in _metric(summary, "cost_full_status")["unknown"]}
    assert unknown["c-fr-2"] == "usage_without_rate"
    # PV10：t-fr-a 有一次成功 attempt（evidence ok）但只挂了 writer 的账——review 缺账在任务级
    # 另列（与试点级 cost_category:review_model 并存：一个是「该任务缺」，一个是「整份试点没人挂」）。
    # 组件级核验引入前此场景只数类别级缺口（10），那时的「有任意费用即覆盖」正是 PV10 修的 bug。
    assert unknown["unmeasured_task:t-fr-a"] == "assisted_task_model_cost_unbilled"
    assert {k for k, v in unknown.items() if v == "cost_category_unobserved"} == {
        f"cost_category:{c}" for c in ("acquisition_allocation", "data_license", "manual_import", "manual_maintenance", "manual_rescue", "other_model", "retry", "review_model", "tool")
    }
    assert detail["unknown_component_count"] == 11


def test_exposures_and_chat_volume_do_not_enter_metrics() -> None:
    exposures = [
        ev("task_exposed", event_id=f"e-cp-expose-{n}", at=ts("09-15", f"13:{n:02d}:00"), channel=SOURCE_FRONTEND, participant="p01", task="t-cp-a", case="case-fc-02", case_version="1", pair="pair-01", condition="assisted", provenance=IMPORTED, payload={"task_id": "t-cp-a", "policy_version": "policy-v1", "view_id": "view-list", "client_at": ts("09-15", f"13:{n:02d}:00")})
        for n in range(50)
    ]
    plain, _, _ = _pipeline(["complete_pair"], provenance=IMPORTED, due=[])
    noisy, noisy_receipts, _ = _pipeline(["complete_pair"], provenance=IMPORTED, due=[], extra_events=exposures)
    # 曝光事件被接收、入账（可审计），但不进入任何指标：只有引用收据 id 的字段会变。
    assert all(f"e-cp-expose-{n}" in noisy_receipts[0]["input_event_ids"] for n in range(50))

    def _semantic(metrics: list[dict]) -> list[tuple]:
        return [(m["metric_id"], m["value"], m["numerator_ids"], m["unknown"], m["coverage"], {k: v for k, v in m["detail"].items() if k != "invalid_receipts_included"}) for m in metrics]

    assert _semantic(noisy["metrics"]) == _semantic(plain["metrics"])
    assert noisy["criteria_results"] == plain["criteria_results"]
    assert not any("exposure" in m["metric_id"] or "chat" in m["metric_id"] or "visit" in m["metric_id"] for m in noisy["metrics"])


def test_empty_cohort_gives_null_values_and_collecting_status() -> None:
    summary, _, _ = _pipeline(["empty_cohort"], provenance=IMPORTED, due=[])
    assert all(m["value"] is None for m in summary["metrics"])
    assert summary["field_status"] == C.FIELD_COLLECTING
    assert summary["commercial_status"] == C.COMMERCIAL_UNSTARTED
    assert summary["engineering_status"] == C.ENGINEERING_COMPLETE
    assert all(c["verdict"] == C.VERDICT_UNKNOWN for c in summary["criteria_results"])


def test_receipt_from_other_protocol_is_input_error() -> None:
    summary, receipts, events = _pipeline(["complete_pair"], provenance=IMPORTED, due=[])
    foreign = copy.deepcopy(receipts[0])
    foreign["protocol_hash"] = "0" * 64
    assignments, cohort = _split(events)
    bad = summarize(receipts + [foreign], assignments, PROTOCOL, cohort_events=cohort, due_rechecks=[])
    assert bad["engineering_status"] == C.ENGINEERING_INPUT_ERROR
    assert bad["input_errors"][0]["code"] == "receipt_protocol_hash_mismatch"
    assert "receipt_errors" in bad["limitations"]


def test_server_channel_recheck_completed_by_participant_counts_only_once() -> None:
    events = build_scenario("cohort_signals", P_HASH, provenance=IMPORTED)[0]
    duplicate = copy.deepcopy(next(e for e in events if e["event_id"] == "e-cs-recheck-done-02"))
    duplicate["recorded_at"] = ts("09-22", "10:05:00")
    assignments, cohort = _split(events)
    summary = summarize([], assignments, PROTOCOL, cohort_events=cohort + [duplicate], due_rechecks=build_scenario("cohort_signals", P_HASH)[2])
    assert _metric(summary, "recheck_completion_rate")["numerator_ids"] == ["j-02"]
    assert summary["event_accounting"]["duplicates"] == ["e-cs-recheck-done-02"]
    assert SOURCE_SERVER == "server"


# ------------------------------------------- 返修 PV1：缺同意必须挡住效果判据 -----


def _six_pairs_without_consent():
    """六对三人，删掉全部 consent_changed；其余完成 / 计时 / 盲审事件照旧。"""
    proto = _six_pair_protocol()
    events: list[dict] = []
    evidence = {"runs": []}
    for i in range(1, 7):
        pair_events, pair_evidence = _clone_complete_pair(i, f"p1{(i - 1) % 3}", proto["protocol_hash"], provenance=IMPORTED)
        events.extend(e for e in pair_events if e["event_type"] != "consent_changed")
        evidence["runs"].extend(pair_evidence["runs"])
    reader = InMemoryEvidenceReader.from_json(evidence)
    receipts = [measure_pair([e for e in events if e.get("case_pair_id") == f"pair-x{i}"] + [e for e in events if not e.get("case_pair_id")], proto, reader) for i in range(1, 7)]
    assignments, cohort = _split(events)
    return proto, receipts, assignments, cohort


def test_missing_consent_makes_quality_and_time_saving_unknown() -> None:
    """评审 PV1：缺同意的收据只标 incomplete 是不够的，判据必须 unknown。

    原实现 summarize 只排除 invalid 收据，六对三人全部缺同意时照样判 pass。
    """
    proto, receipts, assignments, cohort = _six_pairs_without_consent()
    assert [r["status"] for r in receipts] == [C.RECEIPT_INCOMPLETE] * 6
    summary = summarize(receipts, assignments, proto, cohort_events=cohort, due_rechecks=[])
    cq, tsv = _criteria(summary)["completion_quality"], _criteria(summary)["time_saving"]
    assert cq["verdict"] == C.VERDICT_UNKNOWN and cq["unknown_kind"] == UNKNOWN_CONSENT
    assert "consent_unknown" in cq["reason"]
    assert tsv["verdict"] == C.VERDICT_UNKNOWN and tsv["unknown_kind"] == UNKNOWN_CONSENT
    assert "consent_unknown" in tsv["reason"]
    # 受影响配对逐条列出，不静默丢弃。
    flagged = {u["id"] for u in _metric(summary, "time_saving_median")["unknown"] if u["reason"] == "consent_unknown"}
    assert flagged == {f"pair-x{i}" for i in range(1, 7)}
    assert {u["id"] for u in _metric(summary, "pair_quality_not_lower_count")["unknown"]} == {f"pair-x{i}" for i in range(1, 7)}
    assert summary["field_status"] == C.FIELD_INCONCLUSIVE


def test_consented_pairs_still_reach_a_verdict() -> None:
    """反向钉：同意齐全时判据照常 pass，缺同意的门不能误伤正常样本。"""
    proto, receipts, assignments, cohort = _six_pairs(provenance=IMPORTED)
    summary = summarize(receipts, assignments, proto, cohort_events=cohort, due_rechecks=[])
    assert _criteria(summary)["completion_quality"]["verdict"] == C.VERDICT_PASS
    assert _criteria(summary)["time_saving"]["verdict"] == C.VERDICT_PASS


# ------------------------------------- 返修 PV4：空壳收据不能顶替任务级测量 -----


def test_shell_receipt_without_task_evidence_keeps_cost_unknown() -> None:
    """评审 PV4：只有分配、没有耗时 / 尝试 / 费用的测量收据是空壳——
    任务条目出现在收据里 ≠ 费用已覆盖，完整成本仍 unknown（spec §3/§4：没观察到 ≠ 0 元）。
    原流程「明确无模型费用」由收据自己的 cost_items / unknown 表达，不靠收据存在性顶替。
    """
    proto = _six_pair_protocol()
    proto.pop("protocol_hash")
    proto["criteria"]["cost"] = {"not_applicable_components": sorted(C.COST_COMPONENTS - {"writer_model", "review_model"})}
    proto = freeze_protocol(proto)
    complete, evidence = _clone_complete_pair(1, "p10", proto["protocol_hash"], provenance=IMPORTED)
    second, _ = _clone_complete_pair(2, "p11", proto["protocol_hash"], provenance=IMPORTED)
    stub_events = [e for e in second if e["event_type"] in ("consent_changed", "assignment_created")]
    reader = InMemoryEvidenceReader.from_json(evidence)
    receipt_ok = measure_pair(complete, proto, reader)
    receipt_shell = measure_pair(stub_events, proto, reader)
    assert receipt_shell["status"] == "incomplete"  # 空壳：只有分配，没有任何测量事实
    assignments = [e for e in complete + stub_events if e["event_type"] == "assignment_created"]
    cohort = complete + stub_events
    without_shell = summarize([receipt_ok], assignments, proto, cohort_events=cohort, due_rechecks=[])
    with_shell = summarize([receipt_ok, receipt_shell], assignments, proto, cohort_events=cohort, due_rechecks=[])
    base = _metric(without_shell, "cost_full_status")
    shelled = _metric(with_shell, "cost_full_status")
    # 空壳收据没有带来任何新的费用事实：判读不得从 unknown 变 known，缺口不得消失。
    assert base["detail"]["full_cost_status"] == "unknown"
    assert shelled["detail"]["full_cost_status"] == "unknown"
    assert shelled["detail"]["known_cost_by_currency"] == base["detail"]["known_cost_by_currency"]
    gaps = {u["id"] for u in shelled["unknown"] if u["reason"] == "measurement_receipt_without_task_evidence"}
    assert gaps == {"unmeasured_task:t-x2-a", "unmeasured_task:t-x2-o"}


# ------------------------------------- 返修 PV5：后续未结束窗口不收缩复用分母 -----


def test_later_unfinished_window_does_not_shrink_reuse_denominator() -> None:
    """评审 PV5：已完成首轮完整观察周的人，不因下一轮观察窗未结束而退出分母
    （spec §4 分母为「激活后进入完整观察周者」；§3 失败 / 放弃 / 退出不能为了改善读数删除）。
    后续窗口的缺测另列可见，不顶替已取得的队列资格。
    """
    proto = build_protocol()
    cohort_src, _, _ = scenario_cohort_signals(proto["protocol_hash"], provenance=IMPORTED)
    reuse_true = next(e for e in cohort_src if e["event_type"] == "reuse_observed" and e["participant_id"] == "p04")
    reuse_false = next(e for e in cohort_src if e["event_type"] == "reuse_observed" and e["participant_id"] == "p05")
    consent = next(e for e in cohort_src if e["event_type"] == "consent_changed")
    cohort: list[dict] = []
    for index in range(1, 7):
        row = copy.deepcopy(reuse_true if index <= 2 else reuse_false)
        row["event_id"] = f"reuse-{index}-first-window"
        row["participant_id"] = f"q{index}"
        row["payload"]["first_task_id"] = f"q{index}-a"
        row["payload"]["new_task_id"] = f"q{index}-b"
        row["payload"]["new_task_started_at"] = ts("09-23", "10:00:00")
        cohort.append(row)
        granted = copy.deepcopy(consent)
        granted["participant_id"] = f"q{index}"
        granted["event_id"] = f"consent-{index}"
        cohort.append(granted)
    before = summarize([], [], proto, cohort_events=cohort, due_rechecks=[], as_of="2026-10-11")
    next_windows = []
    for index in (4, 5, 6):
        row = copy.deepcopy(next(e for e in cohort if e["event_id"] == f"reuse-{index}-first-window"))
        row["event_id"] = f"reuse-{index}-second-window"
        row["event_at"] = row["recorded_at"] = ts("10-10", "12:00:00")
        row["payload"]["new_task_id"] = f"q{index}-c"
        row["payload"]["new_task_started_at"] = ts("10-09", "10:00:00")
        row["payload"]["observation_window"] = {"start": ts("10-05", "00:00:00"), "end": ts("10-18", "23:59:59")}
        next_windows.append(row)
    after = summarize([], [], proto, cohort_events=cohort + next_windows, due_rechecks=[], as_of="2026-10-11")
    base = _metric(before, "proactive_reuse_rate")
    metric = _metric(after, "proactive_reuse_rate")
    assert base["denominator_ids"] == [f"q{i}" for i in range(1, 7)] and base["value"] == 0.3333
    # 追加未结束窗口后：分母、比率、判据全部不变（修前 2/6 fail 会被洗成 2/3 pass）。
    assert metric["denominator_ids"] == base["denominator_ids"]
    assert metric["value"] == base["value"]
    assert _criteria(after)["proactive_reuse"]["verdict"] == _criteria(before)["proactive_reuse"]["verdict"] == C.VERDICT_FAIL
    # 后续窗口的缺测另列：可见，但不剥夺已取得的队列资格。
    later = {u["id"] for u in metric["unknown"] if u["reason"] == "later_observation_window_incomplete"}
    assert later == {"q4", "q5", "q6"}


# ------------------------------------- 返修 PV6：放弃终态也不能顶替费用覆盖 -----


def test_abandoned_terminal_without_cost_evidence_keeps_cost_unknown() -> None:
    """评审 PV6：终态（含放弃）证明任务状态，不证明费用已被测量。

    只有分配 + 同意 + 放弃的收据（无 run / 耗时 / 费用证据）仍是空壳：并入后完整成本
    必须保持 unknown，缺口逐条在列。前端放弃意图与服务端放弃终态两种输入都验。
    原流程「无 run 但有人工计时」的合法通路不受影响（耗时本身就是测量事实）。
    """
    proto = _six_pair_protocol()
    proto.pop("protocol_hash")
    proto["criteria"]["cost"] = {"not_applicable_components": sorted(C.COST_COMPONENTS - {"writer_model", "review_model"})}
    proto = freeze_protocol(proto)
    complete, evidence = _clone_complete_pair(1, "p10", proto["protocol_hash"], provenance=IMPORTED)
    second, _ = _clone_complete_pair(2, "p11", proto["protocol_hash"], provenance=IMPORTED)
    stubs = [e for e in second if e["event_type"] in ("consent_changed", "assignment_created")]
    reader = InMemoryEvidenceReader.from_json(evidence)
    receipt_ok = measure_pair(complete, proto, reader)
    assignments = [e for e in complete + stubs if e["event_type"] == "assignment_created"]
    for source in (SOURCE_FRONTEND, SOURCE_SERVER):
        terminals = []
        for e in second:
            if e["event_type"] == "task_completed":
                t = copy.deepcopy(e)
                t.update(event_type="task_abandoned", event_id=e["event_id"] + "-abandoned", source_channel=source, object_refs=[], run_ids=[])
                t["payload"].update(completion_evidence_refs=[], terminal_reason="user stopped; cost not measured")
                terminals.append(t)
        events = stubs + terminals
        receipt_shell = measure_pair(events, proto, reader)
        assert receipt_shell["status"] == "incomplete" and receipt_shell["cost_items"] == []
        with_shell = summarize([receipt_ok, receipt_shell], assignments, proto, cohort_events=complete + events, due_rechecks=[])
        detail = _metric(with_shell, "cost_full_status")["detail"]
        assert detail["full_cost_status"] == "unknown", source
        assert detail["known_cost_by_currency"] == {"CNY": 0.46}, source
        gaps = {u["id"] for u in _metric(with_shell, "cost_full_status")["unknown"] if u["reason"] == "measurement_receipt_without_task_evidence"}
        assert gaps == {"unmeasured_task:t-x2-a", "unmeasured_task:t-x2-o"}, source


# ------------------------------------- 返修 PV7：激活推导的成熟资格不被未来窗撤销 -----


def test_future_window_preserves_task_started_mature_denominator() -> None:
    """评审 PV7：队列资格由可信激活时刻 + 冻结协议观察周确立，独立于复用观测是否存在。

    六人 09-15 均有服务端 task_started，截至 10-11 完整观察周已过；q1-q3 有首轮主动复用，
    q4-q6 缺复用观测。仅给 q4-q6 追加未结束的后续窗：分母必须保持 6 人、判据保持 unknown
    （缺测不消失），后续窗只增缺测标签。现有 p20 控制是刚激活未满周，不能据其排除本例。
    """
    proto = build_protocol()
    cohort_src, _, _ = scenario_cohort_signals(proto["protocol_hash"], provenance=IMPORTED)
    reuse_true = next(e for e in cohort_src if e["event_type"] == "reuse_observed" and e["participant_id"] == "p04")
    consent = next(e for e in cohort_src if e["event_type"] == "consent_changed")
    cohort: list[dict] = []
    for index in range(1, 7):
        who = f"q{index}"
        cohort.append(
            ev(
                "task_started",
                event_id=f"start-{who}",
                at=ts("09-15", "10:00:00"),
                channel=SOURCE_SERVER,
                participant=who,
                task=f"{who}-a",
                provenance=IMPORTED,
                payload={"task_id": f"{who}-a", "policy_version": "v1", "view_id": "view-task", "client_at": ts("09-15", "10:00:00"), "initiator": "participant"},
            )
        )
        granted = copy.deepcopy(consent)
        granted.update(participant_id=who, event_id=f"consent-{who}")
        cohort.append(granted)
        if index <= 3:
            row = copy.deepcopy(reuse_true)
            row.update(participant_id=who, event_id=f"reuse-{who}")
            row["payload"].update(first_task_id=f"{who}-a", new_task_id=f"{who}-b", new_task_started_at=ts("09-23", "10:00:00"))
            cohort.append(row)
    before = summarize([], [], proto, cohort_events=cohort, due_rechecks=[], as_of="2026-10-11")
    future = []
    for index in (4, 5, 6):
        who = f"q{index}"
        row = copy.deepcopy(reuse_true)
        row.update(participant_id=who, event_id=f"reuse-{who}-next", event_at=ts("10-10", "12:00:00"), recorded_at=ts("10-10", "12:00:00"))
        row["payload"].update(
            first_task_id=f"{who}-a",
            new_task_id=f"{who}-c",
            new_task_started_at=ts("10-09", "10:00:00"),
            observation_window={"start": ts("10-05", "00:00:00"), "end": ts("10-18", "23:59:59")},
        )
        future.append(row)
    after = summarize([], [], proto, cohort_events=cohort + future, due_rechecks=[], as_of="2026-10-11")
    base = _metric(before, "proactive_reuse_rate")
    metric = _metric(after, "proactive_reuse_rate")
    assert base["denominator_ids"] == [f"q{i}" for i in range(1, 7)] and base["value"] == 0.5
    # 追加未结束窗口后：分母、比率、判据全部不变（修前 3/6 unknown 会被洗成 3/3 pass）。
    assert metric["denominator_ids"] == base["denominator_ids"]
    assert metric["value"] == base["value"]
    assert _criteria(after)["proactive_reuse"]["verdict"] == _criteria(before)["proactive_reuse"]["verdict"] == C.VERDICT_UNKNOWN
    # 缺首轮复用观测仍在列，后续窗的缺测另列——两者都不剥夺已成熟资格。
    assert {u["id"] for u in metric["unknown"] if u["reason"] == "reuse_observation_missing"} == {"q4", "q5", "q6"}
    assert {u["id"] for u in metric["unknown"] if u["reason"] == "later_observation_window_incomplete"} == {"q4", "q5", "q6"}


# ------------------------------------- 返修 PV2：完整成本要对照任务与费用类别 -----


def test_assigned_task_without_cost_evidence_blocks_full_cost() -> None:
    """评审 PV2：已分配但没有测量 / 没有账目的任务，不能当成零费用。"""
    summary, receipts, events = _pipeline(["complete_pair"], provenance=IMPORTED, due=[])
    assignments, cohort = _split(events)
    extra = copy.deepcopy(assignments)
    for event in extra:
        event["event_id"] += "-unmeasured"
        event["task_id"] += "-unmeasured"
        event["payload"]["task_id"] = event["task_id"]
        event["case_pair_id"] = "pair-02"
        event["payload"]["case_pair_id"] = "pair-02"
        event["case_id"] = "case-jr-01" if event["assistance_condition"] == "original" else "case-jr-02"
        event["payload"]["case_id"] = event["case_id"]
    with_unmeasured = summarize(receipts, assignments + extra, PROTOCOL, cohort_events=cohort, due_rechecks=[])
    detail = _metric(with_unmeasured, "cost_full_status")["detail"]
    assert detail["full_cost_status"] == "unknown"
    assert detail["full_cost_reason"] == "unknown_components_present"
    assert detail["gross_margin"] is None and detail["gross_margin_reason"] == "cost_unknown"
    gaps = {u["id"] for u in _metric(with_unmeasured, "cost_full_status")["unknown"] if u["reason"] == "no_measurement_receipt_for_assigned_task"}
    assert gaps == {"unmeasured_task:t-cp-a-unmeasured", "unmeasured_task:t-cp-o-unmeasured"}


def test_unobserved_cost_categories_are_unknown_not_zero() -> None:
    """评审 PV2：只有写手 / 自审两类费用不构成「完整成本已知」。

    spec §3 要求覆盖托管、数据授权、获客分摊等类别；未观察到调用不作零费用依据。
    """
    summary, _, _ = _pipeline(["complete_pair"], provenance=IMPORTED, due=[])
    metric = _metric(summary, "cost_full_status")
    assert metric["detail"]["full_cost_status"] == "unknown"
    missing = {u["id"] for u in metric["unknown"] if u["reason"] == "cost_category_unobserved"}
    assert {"cost_category:hosting", "cost_category:data_license", "cost_category:acquisition_allocation"} <= missing
    # 已经有账的类别不重复报缺。
    assert "cost_category:writer_model" not in missing and "cost_category:review_model" not in missing


def test_declared_not_applicable_cost_categories_stop_being_gaps() -> None:
    """事前在冻结协议里声明「本试点无此类费用」的类别不再报缺；未声明的照报。"""
    proto = build_protocol()
    proto.pop("protocol_hash")
    proto["criteria"]["cost"] = {
        "not_applicable_components": ["other_model", "tool", "retry", "manual_import", "manual_rescue", "manual_maintenance", "data_license", "hosting", "acquisition_allocation"]
    }
    proto = freeze_protocol(proto)
    events, evidence, _ = build_scenario("complete_pair", proto["protocol_hash"], provenance=IMPORTED)
    reader = InMemoryEvidenceReader.from_json(evidence)
    receipts = [measure_pair(events, proto, reader)]
    assignments, cohort = _split(events)
    summary = summarize(receipts, assignments, proto, cohort_events=cohort, due_rechecks=[])
    metric = _metric(summary, "cost_full_status")
    assert [u for u in metric["unknown"] if u["reason"] == "cost_category_unobserved"] == []
    assert metric["detail"]["full_cost_status"] == "known"
    assert metric["detail"]["not_applicable_components"] == [
        "acquisition_allocation", "data_license", "hosting", "manual_import", "manual_maintenance", "manual_rescue", "other_model", "retry", "tool"
    ]


# --------------------------------- 返修 PV3：复用分母是激活队列，不是复用事件 -----


def test_reuse_denominator_counts_activated_participants_without_reuse() -> None:
    """评审 PV3：六人激活、观察周已完整、仅一人复用，分母必须是六个人。

    原实现从 reuse_observed 建行再直接当分母，没复用的人根本不出现，报出 100%。
    """
    cohort_events = build_scenario("cohort_signals", P_HASH, provenance=IMPORTED)[0]
    cohort = [e for e in cohort_events if e["event_type"] in ("reuse_observed", "task_started") and e.get("participant_id") == "p04"]
    for i in range(4, 10):
        cohort.append(
            ev(
                "task_started",
                event_id=f"probe-start-{i}",
                at=ts("09-15", "10:00:00"),
                channel=SOURCE_SERVER,
                participant=f"p{i:02d}",
                task=f"probe-first-{i}",
                provenance=IMPORTED,
                payload={"task_id": f"probe-first-{i}", "policy_version": "v1", "view_id": "view-task", "client_at": ts("09-15", "10:00:00"), "initiator": "participant"},
            )
        )
    summary = summarize([], [], PROTOCOL, cohort_events=cohort, due_rechecks=[], as_of="2026-10-11")
    metric = _metric(summary, "proactive_reuse_rate")
    assert metric["denominator_ids"] == [f"p{i:02d}" for i in range(4, 10)]
    assert metric["numerator_ids"] == ["p04"]
    assert metric["value"] == 0.1667
    # 没有复用观察记录的人不被静默删除：留在分母里，同时逐条列为缺测。
    assert {u["id"] for u in metric["unknown"] if u["reason"] == "reuse_observation_missing"} == {f"p{i:02d}" for i in range(5, 10)}
    reuse = _criteria(summary)["proactive_reuse"]
    assert reuse["verdict"] == C.VERDICT_UNKNOWN and reuse["unknown_kind"] == UNKNOWN_GAP


def test_reuse_window_not_yet_complete_stays_out_of_denominator() -> None:
    """观察周还没走完的人不进分母，也不当成没复用，而是列 unknown。"""
    cohort = [
        ev(
            "task_started",
            event_id="fresh-start",
            at=ts("10-09", "10:00:00"),
            channel=SOURCE_SERVER,
            participant="p20",
            task="fresh-task",
            provenance=IMPORTED,
            payload={"task_id": "fresh-task", "policy_version": "v1", "view_id": "view-task", "client_at": ts("10-09", "10:00:00"), "initiator": "participant"},
        )
    ]
    summary = summarize([], [], PROTOCOL, cohort_events=cohort, due_rechecks=[], as_of="2026-10-11")
    metric = _metric(summary, "proactive_reuse_rate")
    assert metric["denominator_ids"] == [] and metric["value"] is None
    assert {"id": "p20", "reason": "observation_window_incomplete"} in metric["unknown"]


def test_timed_assisted_task_without_usage_facts_does_not_cover_model_cost():
    """PV8：人工计时只覆盖「花了多少时间」，不覆盖辅助服务费用——辅助任务没有
    run / 用量 / 费用事实时，不能核销 writer_model / review_model 这类模型成本。"""
    proto = _six_pair_protocol()
    proto.pop("protocol_hash")
    proto["criteria"]["cost"] = {"not_applicable_components": sorted(C.COST_COMPONENTS - {"writer_model", "review_model"})}
    proto = freeze_protocol(proto)
    complete, evidence = _clone_complete_pair(1, "p10", proto["protocol_hash"], provenance="imported")
    second, _ = _clone_complete_pair(2, "p11", proto["protocol_hash"], provenance="imported")
    reader = InMemoryEvidenceReader.from_json(evidence)
    r1 = measure_pair(complete, proto, reader)
    # 原流程保留真实人工计时/交付物事实；辅助流程只有同意 + 分配 + 开始/放弃时间戳，无 run 与用量
    original = [e for e in second if e["event_type"] == "consent_changed" or e.get("assistance_condition") == "original"]
    assisted = [e for e in second if e.get("assistance_condition") == "assisted" and e["event_type"] in ("assignment_created", "task_started")]
    for e in second:
        if e.get("assistance_condition") == "assisted" and e["event_type"] == "task_completed":
            abandoned = copy.deepcopy(e)
            abandoned.update(event_type="task_abandoned", event_id=e["event_id"] + "-abandoned", object_refs=[], run_ids=[])
            abandoned["payload"].update(completion_evidence_refs=[], terminal_reason="abandoned; run and billing records unavailable")
            assisted.append(abandoned)
    events = original + assisted
    r2 = measure_pair(events, proto, reader)
    # 合法通路负控：人工计时本身仍被测量，不因为没有费用事实被抹掉
    assert r2["tasks"]["assisted"]["attempts"] == []
    assert r2["tasks"]["assisted"]["timing"]["end_to_end_minutes"] == 20
    assert r2["cost_items"] == []
    assignments = [e for e in complete + events if e["event_type"] == "assignment_created"]

    def _cost(receipts):
        summary = summarize(receipts, assignments, proto, cohort_events=complete + events, due_rechecks=[])
        return next(m for m in summary["metrics"] if m["metric_id"] == "cost_full_status")

    before = _cost([r1])
    assert before["detail"]["full_cost_status"] == "unknown"
    after = _cost([r1, r2])
    assert after["detail"]["known_cost_by_currency"] == {"CNY": 0.46}
    assert after["detail"]["full_cost_status"] == "unknown"


def test_task_scoped_fee_does_not_cover_missing_model_components():
    """PV9：一笔工具费不能替缺失的模型费用作证——无 run 辅助任务的费用核销按组件逐个核验，
    writer 有账也不能替缺失的 review 作证；三件套补齐才是合法 known。"""
    proto = _six_pair_protocol()
    proto.pop("protocol_hash")
    proto["criteria"]["cost"] = {"not_applicable_components": sorted(C.COST_COMPONENTS - {"writer_model", "review_model", "tool"})}
    proto = freeze_protocol(proto)
    complete, evidence = _clone_complete_pair(1, "p10", proto["protocol_hash"], provenance="imported")
    second, _ = _clone_complete_pair(2, "p11", proto["protocol_hash"], provenance="imported")
    reader = InMemoryEvidenceReader.from_json(evidence)
    r1 = measure_pair(complete, proto, reader)
    original = [e for e in second if e["event_type"] == "consent_changed" or e.get("assistance_condition") == "original"]
    assisted = [e for e in second if e.get("assistance_condition") == "assisted" and e["event_type"] in ("assignment_created", "task_started")]
    template = None
    for e in second:
        if e.get("assistance_condition") == "assisted" and e["event_type"] == "task_completed":
            template = copy.deepcopy(e)
            template.update(event_type="task_abandoned", event_id=e["event_id"] + "-abandoned", object_refs=[], run_ids=[])
            template["payload"].update(completion_evidence_refs=[], terminal_reason="abandoned; run and billing records unavailable")
            assisted.append(template)
    events = original + assisted

    def _fee(component, amount):
        e = copy.deepcopy(template)
        e.update(event_id=f"qc-fee-{component}", event_type="cost_recorded", source_channel="server", object_refs=[], run_ids=[])
        e["payload"] = {
            "initiator": template["payload"]["initiator"],
            "assistance_source": template["payload"]["assistance_source"],
            "cost_item": {
                "cost_id": f"qc-cost-{component}", "component": component, "run_id": None, "attempt_id": None, "span_id": None,
                "coverage_scope": "task", "quantity": 1, "unit": "calls", "amount": amount, "currency": "CNY",
                "certainty": "known", "evidence_ref": f"invoice:{component}", "rate_version": "qc-rate-v1", "allocation_rule": None,
            },
        }
        return e

    def _measured(extra):
        evs = events + list(extra)
        r2 = measure_pair(evs, proto, reader)
        assert r2["invalid_reasons"] == [] and r2["event_accounting"]["rejected"] == []
        assert r2["tasks"]["assisted"]["attempts"] == []
        assignments = [e for e in complete + evs if e["event_type"] == "assignment_created"]
        summary = summarize([r1, r2], assignments, proto, cohort_events=complete + evs, due_rechecks=[])
        return next(m for m in summary["metrics"] if m["metric_id"] == "cost_full_status")

    assert _measured([])["detail"]["full_cost_status"] == "unknown"
    assert _measured([_fee("tool", 0.01)])["detail"]["full_cost_status"] == "unknown"
    assert _measured([_fee("tool", 0.01), _fee("writer_model", 0.36)])["detail"]["full_cost_status"] == "unknown"
    full = _measured([_fee("tool", 0.01), _fee("writer_model", 0.36), _fee("review_model", 0.10)])
    assert full["detail"]["full_cost_status"] == "known"
    assert full["detail"]["known_cost_by_currency"] == {"CNY": 0.93}


def test_run_scoped_fee_does_not_cover_missing_model_components():
    """PV10：组件级核验贯穿有 run 分支——解析成功的真实 run 摆着，仅 tool 或 writer+tool
    的账仍不能替缺失的模型费作证；writer+review+tool 三件套才是合法 known 0.93。"""
    proto = _six_pair_protocol()
    proto.pop("protocol_hash")
    proto["criteria"]["cost"] = {"not_applicable_components": sorted(C.COST_COMPONENTS - {"writer_model", "review_model", "tool"})}
    proto = freeze_protocol(proto)
    complete, evidence1 = _clone_complete_pair(1, "p10", proto["protocol_hash"], provenance="imported")
    second, evidence2 = _clone_complete_pair(2, "p11", proto["protocol_hash"], provenance="imported")
    reader = InMemoryEvidenceReader.from_json({"runs": evidence1["runs"] + evidence2["runs"]})
    r1 = measure_pair(complete, proto, reader)
    fees = [e for e in second if e["event_type"] == "cost_recorded" and e["payload"]["cost_item"]["coverage_scope"] == "run"]
    template = next(e for e in fees if e["payload"]["cost_item"]["component"] == "writer_model")
    base = [e for e in second if e["event_type"] != "cost_recorded"]
    tool = copy.deepcopy(template)
    tool["event_id"] = "qc-r6-run-tool-fee"
    tool["payload"]["cost_item"].update(cost_id="qc-r6-tool", component="tool", amount=0.01, quantity=1, unit="calls", evidence_ref="invoice:tool")
    writer = next(e for e in fees if e["payload"]["cost_item"]["component"] == "writer_model")
    review = next(e for e in fees if e["payload"]["cost_item"]["component"] == "review_model")

    def _measured(extra):
        events = base + list(extra)
        r2 = measure_pair(events, proto, reader)
        assert r2["invalid_reasons"] == [] and r2["event_accounting"]["rejected"] == []
        assert r2["tasks"]["assisted"]["attempts"][0]["evidence_status"] == "ok"
        assignments = [e for e in complete + events if e["event_type"] == "assignment_created"]
        summary = summarize([r1, r2], assignments, proto, cohort_events=complete + events, due_rechecks=[])
        return next(m for m in summary["metrics"] if m["metric_id"] == "cost_full_status")

    assert _measured([])["detail"]["full_cost_status"] == "unknown"
    assert _measured([tool])["detail"]["full_cost_status"] == "unknown"
    assert _measured([writer, tool])["detail"]["full_cost_status"] == "unknown"
    full = _measured([writer, review, tool])
    assert full["detail"]["full_cost_status"] == "known"
    assert full["detail"]["known_cost_by_currency"] == {"CNY": 0.93}
