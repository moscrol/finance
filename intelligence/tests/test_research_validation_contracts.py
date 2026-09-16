"""spec 03 §4 合同：语义身份、拒收边界、窗口递进、统计口径不可放宽。"""

from __future__ import annotations

import math

import pytest

from intelligence.services.checkpoints import DEFAULT_CALIBRATION_MIN_N
from intelligence.services.methodology_backtest.rules import DEFAULT_MIN_N
from intelligence.services.methodology_backtest.stats import DEFAULT_BLOCK_BOOT, DEFAULT_BLOCK_SEED, DEFAULT_MIN_BLOCKS
from intelligence.services.research_validation import contracts as c
from intelligence.tests.test_research_validation_support import OWNER, forward_body, sh, weekdays

CAL = weekdays("2026-09-01", 90)
FREEZE_NOW = sh("2026-09-11")


def test_canonical_bytes_rejects_non_finite_numbers():
    for bad in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValueError):
            c.canonical_bytes({"p": bad})
    assert c.canonical_bytes({"b": 1, "a": [1, 2]}) == b'{"a":[1,2],"b":1}'


@pytest.mark.parametrize(
    "value,expected",
    [(0.5, True), (0, True), (1, True), (True, False), (False, False), (float("nan"), False), (1.2, False), (-0.1, False), ("0.5", False)],
)
def test_probability_validation(value, expected):
    assert c.is_probability(value) is expected


def test_study_identity_ignores_record_time_but_changes_with_meaning():
    body = forward_body(CAL)
    a = c.freeze_protocol_content(body, owner=OWNER, now=FREEZE_NOW)
    b = c.freeze_protocol_content(body, owner=OWNER, now=sh("2026-09-11", 18, 30))
    assert a["study_id"] == b["study_id"]
    assert a["frozen_at"] != b["frozen_at"]
    assert c.validate_frozen_protocol(a, owner=OWNER)["study_id"] == a["study_id"]

    changed_question = c.freeze_protocol_content({**body, "question": body["question"] + " v2"}, owner=OWNER, now=FREEZE_NOW)
    assert changed_question["study_id"] != a["study_id"]
    changed_baseline = c.freeze_protocol_content(
        {**body, "baseline_spec": {**body["baseline_spec"], "p_baseline": 0.56}}, owner=OWNER, now=FREEZE_NOW
    )
    assert changed_baseline["study_id"] != a["study_id"]
    assert changed_baseline["baseline_hash"] != a["baseline_hash"]
    assert changed_baseline["framework_hash"] == a["framework_hash"], "改基准不改方法框架"


def test_freeze_rejects_caller_supplied_state_and_foreign_owner():
    body = forward_body(CAL)
    with pytest.raises(c.ContractError, match="未知键"):
        c.freeze_protocol_content({**body, "eligible": True}, owner=OWNER, now=FREEZE_NOW)
    with pytest.raises(c.ContractError, match="未知键"):
        c.freeze_protocol_content({**body, "study_id": "x" * 64}, owner=OWNER, now=FREEZE_NOW)
    with pytest.raises(c.OwnerMismatch):
        c.freeze_protocol_content({**body, "owner_user_id": "someone_else"}, owner=OWNER, now=FREEZE_NOW)
    with pytest.raises(c.ContractError):
        c.freeze_protocol_content(body, owner="bad/owner", now=FREEZE_NOW)


@pytest.mark.parametrize(
    "policy,message",
    [
        ({"min_n": DEFAULT_MIN_N - 1}, "低于冻结缺省"),
        ({"min_blocks": DEFAULT_MIN_BLOCKS - 1}, "低于冻结缺省"),
        ({"n_boot": DEFAULT_BLOCK_BOOT - 1}, "低于冻结缺省"),
        ({"calibration_min_n": DEFAULT_CALIBRATION_MIN_N - 1}, "低于冻结缺省"),
        ({"seed": DEFAULT_BLOCK_SEED + 1}, "换种子"),
        ({"null_p0": 0.55}, "对称胜负"),
        ({"block_len": 4}, "outcome horizon"),
        ({"ties": "drop"}, "平局"),
        ({"bonus": 1}, "未知键"),
    ],
)
def test_analysis_policy_cannot_be_loosened(policy, message):
    body = forward_body(CAL, analysis_policy={"exposure_ledger_complete": True, **policy})
    with pytest.raises(c.ContractError, match=message):
        c.freeze_protocol_content(body, owner=OWNER, now=FREEZE_NOW)


def test_analysis_policy_defaults_come_from_existing_modules():
    frozen = c.freeze_protocol_content(forward_body(CAL), owner=OWNER, now=FREEZE_NOW)
    policy = frozen["analysis_policy"]
    assert policy["min_n"] == DEFAULT_MIN_N
    assert policy["min_blocks"] == DEFAULT_MIN_BLOCKS
    assert policy["n_boot"] == DEFAULT_BLOCK_BOOT
    assert policy["seed"] == DEFAULT_BLOCK_SEED
    assert policy["calibration_min_n"] == DEFAULT_CALIBRATION_MIN_N
    assert policy["block_len"] == frozen["outcome_spec"]["horizon"]
    assert policy["null_p0"] == 0.5


def test_windows_must_be_strictly_progressive_and_on_calendar():
    body = forward_body(CAL)
    overlapping = {**body, "validation_window": {"start": "2026-09-10", "end": "2026-09-11"}}
    with pytest.raises(c.ContractError, match="严格递进"):
        c.freeze_protocol_content(overlapping, owner=OWNER, now=FREEZE_NOW)
    weekend = {**body, "discovery_window": {"start": "2026-09-05", "end": "2026-09-10"}}
    with pytest.raises(c.ContractError, match="交易日"):
        c.freeze_protocol_content(weekend, owner=OWNER, now=FREEZE_NOW)
    too_early_forward = {**body, "forward_start": "2026-09-10"}
    with pytest.raises(c.ContractError, match="发现窗"):
        c.freeze_protocol_content(too_early_forward, owner=OWNER, now=FREEZE_NOW)


def test_forward_protocol_must_freeze_before_forward_start():
    body = forward_body(CAL)
    with pytest.raises(c.ContractError, match="forward_start"):
        c.freeze_protocol_content(body, owner=OWNER, now=sh("2026-09-15"))
    # forward_start 当日冻结允许（D0 盘后登记之前）
    assert c.freeze_protocol_content(body, owner=OWNER, now=sh("2026-09-14", 9))["status"] == "frozen"


def test_calendar_must_cover_outcome_due_after_evaluation_end():
    body = forward_body(CAL)
    body["evaluation_end"] = CAL[-2]
    with pytest.raises(c.ContractError, match="日历不足"):
        c.freeze_protocol_content(body, owner=OWNER, now=FREEZE_NOW)


def test_baseline_without_valid_dates_must_be_null_not_half():
    body = forward_body(CAL)
    body["baseline_spec"] = {**body["baseline_spec"], "n_dates": 0, "p_baseline": 0.5}
    with pytest.raises(c.ContractError, match="不得填 0.5"):
        c.freeze_protocol_content(body, owner=OWNER, now=FREEZE_NOW)
    body["baseline_spec"] = {**body["baseline_spec"], "n_dates": 0, "p_baseline": None}
    assert c.freeze_protocol_content(body, owner=OWNER, now=FREEZE_NOW)["baseline_spec"]["p_baseline"] is None


def test_historical_mode_requires_version_hashes():
    body = forward_body(CAL, mode="historical_rule", version_hashes={})
    body["validation_window"] = {"start": body["forward_start"], "end": body["evaluation_end"]}
    with pytest.raises(c.ContractError, match="version_hashes"):
        c.freeze_protocol_content(body, owner=OWNER, now=FREEZE_NOW)


def test_comparisons_need_exactly_one_confirmatory_primary():
    body = forward_body(CAL)
    body["comparisons"] = [
        {**body["comparisons"][0]},
        {"comparison_id": "second", "base_arm_id": "full", "candidate_arm_id": "base", "claim_kind": "paired_date_win_rate", "confirmatory": True},
    ]
    with pytest.raises(c.ContractError, match="只能有一个确认性主比较"):
        c.freeze_protocol_content(body, owner=OWNER, now=FREEZE_NOW)
    body["comparisons"][1]["confirmatory"] = False
    body["comparisons"][1]["claim_kind"] = "mean_brier_difference_descriptive"
    body["primary_comparison_id"] = "second"
    with pytest.raises(c.ContractError, match="primary_comparison_id"):
        c.freeze_protocol_content(body, owner=OWNER, now=FREEZE_NOW)


def test_arm_isolation_declared_residual_is_rejected():
    body = forward_body(CAL)
    body["arms"] = [
        {"arm_id": "base", "role": "base", "allowed_fields": ["dual_red_strict"]},
        {
            "arm_id": "full",
            "role": "minus_track",
            "allowed_fields": ["dual_red_strict", "amount_rank_top10"],
            "removed_track": {"track_id": "l2", "fields": ["amount_rank_top10"], "derived_fields": []},
        },
    ]
    with pytest.raises(c.ContractError, match="残留信息"):
        c.freeze_protocol_content(body, owner=OWNER, now=FREEZE_NOW)
    body["arms"][1]["allowed_fields"] = ["dual_red_strict"]
    body["arms"][1]["removed_track"]["derived_fields"] = ["dual_red_strict"]
    with pytest.raises(c.ContractError, match="残留信息"):
        c.freeze_protocol_content(body, owner=OWNER, now=FREEZE_NOW)


def test_case_id_is_shared_by_arms_and_independent_of_probability():
    kwargs = dict(entity_type="sector", entity_id="S1", as_of="2026-09-14", event_spec_hash="a" * 64, outcome_due="2026-09-21", universe_hash="b" * 64)
    assert c.derive_case_id(**kwargs) == c.derive_case_id(**kwargs)
    assert c.derive_case_id(**{**kwargs, "event_spec_hash": "c" * 64}) != c.derive_case_id(**kwargs)
    assert c.derive_case_id(**{**kwargs, "entity_id": "S2"}) != c.derive_case_id(**kwargs)


def test_outcome_identity_matches_by_entity_and_interval_only():
    a = c.outcome_identity(entity_type="sector", entity_id="S1", as_of="2026-09-14", outcome_due="2026-09-21", horizon=5)
    same_entity_overlap = c.outcome_identity(entity_type="sector", entity_id="S1", as_of="2026-09-18", outcome_due="2026-09-25", horizon=5)
    disjoint = c.outcome_identity(entity_type="sector", entity_id="S1", as_of="2026-09-22", outcome_due="2026-09-29", horizon=5)
    other = c.outcome_identity(entity_type="sector", entity_id="S2", as_of="2026-09-14", outcome_due="2026-09-21", horizon=5)
    assert c.identities_overlap(a, same_entity_overlap)
    assert not c.identities_overlap(a, disjoint)
    assert not c.identities_overlap(a, other)
    tampered = {**a, "identity": "0" * 64}
    with pytest.raises(c.ContractError, match="哈希"):
        c.validate_outcome_identity(tampered)


def test_gap_codes_are_closed_set():
    gap = c.make_gap("future_not_due", ["x"], retryable=True, next_check_at="2026-09-21T07:00:00+00:00")
    assert gap.to_dict()["retryable"] is True
    with pytest.raises(c.ContractError):
        c.make_gap("made_up_code")


def test_outcome_predicate_unknown_stays_unknown():
    spec = {"metric": "fwd_return", "horizon": 5, "op": ">", "value": 0.0}
    assert c.outcome_predicate(spec, 1.5) is True
    assert c.outcome_predicate(spec, -0.2) is False
    assert c.outcome_predicate(spec, None) is None
    assert c.outcome_predicate(spec, math.nan) is None
