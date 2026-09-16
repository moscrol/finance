"""spec 03 §5 / §8 / §9 服务：D0 登记零结果、未到期 pending、到期缺值不失败、版本 / 时间 / 归属拒绝、
完整前向流程到收据、曝光判定（换 study / 谱系 / 别名洗不白、未知来源不 eligible）。"""

from __future__ import annotations

import math
from datetime import timedelta

import pytest

from intelligence.eval.research_validation import forecasts_from_replay
from intelligence.services.research_validation import (
    ConflictError,
    ContractError,
    OwnerMismatch,
    evaluate_study,
    freeze_study,
    read_receipt,
    record_exposure,
    register_forecasts,
    settle_outcomes,
)
from intelligence.services.research_validation.contracts import market_close, utc_iso
from intelligence.tests.test_research_validation_support import (
    HORIZON,
    OWNER,
    DictOutcomeSource,
    FakePitVerifier,
    forecast_input,
    forward_body,
    make_repo,
    settled_row,
    sh,
    weekdays,
)

CAL = weekdays("2026-09-01", 90)
FS = CAL.index("2026-09-14")
D0 = CAL[FS]
FREEZE_NOW = sh("2026-09-11")
D0_EVENING = sh(D0, 16, 30)


def frozen(tmp_path, **overrides):
    repo = make_repo(tmp_path)
    protocol = freeze_study(owner=OWNER, repository=repo, now=FREEZE_NOW, protocol_input=forward_body(CAL, **overrides))
    return repo, protocol


def two_arm_inputs(day, entities=("S1", "S2"), *, p_base=0.6, p_full=0.8, origin="deterministic"):
    out = []
    for e in entities:
        out.append(forecast_input(e, day, "base", p_base, origin=origin))
        out.append(forecast_input(e, day, "full", p_full, origin=origin))
    return out


# --------------------------------------------------------------------------- #
# 冻结 / 登记
# --------------------------------------------------------------------------- #
def test_freeze_is_idempotent_and_returns_first_original(tmp_path):
    repo, protocol = frozen(tmp_path)
    again = freeze_study(owner=OWNER, repository=repo, now=sh("2026-09-12"), protocol_input=forward_body(CAL))
    assert again["study_id"] == protocol["study_id"]
    assert again["frozen_at"] == protocol["frozen_at"], "重试返回首次原件，不刷新冻结时间"
    assert repo.list_studies() == [protocol["study_id"]]


def test_d0_registration_has_zero_outcomes_and_future_values_stay_pending(tmp_path):
    repo, protocol = frozen(tmp_path)
    result = register_forecasts(owner=OWNER, repository=repo, now=D0_EVENING, study_id=protocol["study_id"], forecasts=two_arm_inputs(D0))
    assert len(result.accepted) == 4 and not result.rejected
    # 源里已经「预塞」了未来值：结算时仍 pending，不落任何观察
    source = DictOutcomeSource(
        calendar=CAL,
        watermark=CAL[-1],
        rows={("sector", e, D0, HORIZON): settled_row(D0, 2.0, cal=CAL) for e in ("S1", "S2")},
    )
    settle = settle_outcomes(owner=OWNER, repository=repo, now=D0_EVENING, study_id=protocol["study_id"], outcome_source=source)
    assert len(settle.pending) == 4 and not settle.settled and source.lookups == 0
    assert not (repo.study_dir(protocol["study_id"]) / "observations").exists()
    receipt = evaluate_study(owner=OWNER, repository=repo, now=D0_EVENING, study_id=protocol["study_id"])
    assert receipt["empirical_status"] == "pending"
    assert receipt["counts"] == {"forecasts": 4, "cases": 2, "settled": 0, "pending": 4, "missing": 0, "invalid": 0}
    assert receipt["confirmatory_test_run"] is False
    primary = receipt["comparison_readouts"][0]
    assert primary["status"] == "pending" and primary["mean_brier_difference_descriptive"] is None and primary["verdict"] is None
    due_close = utc_iso(market_close(CAL[FS + HORIZON]))
    assert any(g["code"] == "future_not_due" and g["next_check_at"] == due_close for g in receipt["pending_gaps"])
    assert receipt["synthetic"] is True and receipt["decision_eligible"] is False and receipt["promotion_eligible"] is False


@pytest.mark.parametrize(
    "override,reason",
    [
        ({"p": True}, "invalid_probability"),
        ({"p": math.nan}, "invalid_probability"),
        ({"p": 1.2}, "invalid_probability"),
        ({"p": -0.01}, "invalid_probability"),
        ({"arm_id": "ghost"}, "arm_unknown"),
        ({"origin": "historical_llm", "probability_recipe_hash": None}, "mode_origin_mismatch"),
        ({"probability_recipe_hash": None}, "probability_recipe_hash"),
        ({"registered_at": "2026-09-14T08:30:00+00:00"}, "unknown_keys"),
        ({"eligible": True}, "unknown_keys"),
        ({"entity_id": "S9"}, "entity_not_in_universe"),
        ({"as_of": "2026-09-13"}, "as_of_not_trading_day"),
        ({"forecast_at": utc_iso(D0_EVENING + timedelta(hours=1))}, "forecast_at_in_future"),
        ({"knowledge_cutoff": utc_iso(market_close(D0) + timedelta(minutes=1))}, "knowledge_cutoff_late"),
    ],
)
def test_register_rejects_bad_inputs_with_reason(tmp_path, override, reason):
    repo, protocol = frozen(tmp_path)
    item = {**forecast_input("S1", D0, "base", 0.6), **override}
    result = register_forecasts(owner=OWNER, repository=repo, now=D0_EVENING, study_id=protocol["study_id"], forecasts=[item])
    assert not result.accepted
    assert result.rejected and (result.rejected[0].reason == reason or reason in result.rejected[0].detail)


def test_forward_registration_time_gates(tmp_path):
    repo, protocol = frozen(tmp_path)
    sid = protocol["study_id"]
    late = register_forecasts(owner=OWNER, repository=repo, now=sh(CAL[FS + 1], 16), study_id=sid, forecasts=[forecast_input("S1", D0, "base", 0.6)])
    assert late.rejected[0].reason == "late_registration"
    early = register_forecasts(owner=OWNER, repository=repo, now=sh(D0, 14, 59), study_id=sid, forecasts=[forecast_input("S1", D0, "base", 0.6, forecast_at=utc_iso(sh(D0, 14)))])
    assert early.rejected[0].reason == "before_market_close"
    future = register_forecasts(owner=OWNER, repository=repo, now=D0_EVENING, study_id=sid, forecasts=[forecast_input("S1", CAL[FS + 1], "base", 0.6, forecast_at=utc_iso(D0_EVENING))])
    assert future.rejected[0].reason == "as_of_in_future"
    in_discovery = register_forecasts(owner=OWNER, repository=repo, now=sh("2026-09-10", 16), study_id=sid, forecasts=[forecast_input("S1", "2026-09-10", "base", 0.6)])
    assert in_discovery.rejected[0].reason == "as_of_in_discovery_window"


def test_same_case_arm_is_idempotent_for_same_payload_and_conflicts_for_new_p(tmp_path):
    repo, protocol = frozen(tmp_path)
    sid = protocol["study_id"]
    first = register_forecasts(owner=OWNER, repository=repo, now=D0_EVENING, study_id=sid, forecasts=[forecast_input("S1", D0, "base", 0.6)])
    retry = register_forecasts(owner=OWNER, repository=repo, now=sh(D0, 17), study_id=sid, forecasts=[forecast_input("S1", D0, "base", 0.6)])
    assert retry.idempotent[0]["id"] == first.accepted[0]["id"]
    assert retry.idempotent[0]["registered_at"] == first.accepted[0]["registered_at"]
    revised = register_forecasts(owner=OWNER, repository=repo, now=sh(D0, 17), study_id=sid, forecasts=[forecast_input("S1", D0, "base", 0.9)])
    assert revised.rejected[0].reason == "conflict" and revised.rejected[0].extra["existing_p"] == 0.6
    assert len(repo.list_forecasts(sid)) == 1 and repo.list_forecasts(sid)[0]["p"] == 0.6


def test_pit_grade_only_upgrades_with_verified_receipt(tmp_path):
    repo, protocol = frozen(tmp_path)
    sid = protocol["study_id"]
    verifier = FakePitVerifier({"cap-ok": {"verified": True, "pit_grade": "strict"}, "cap-bad": {"verified": False}})
    result = register_forecasts(
        owner=OWNER,
        repository=repo,
        now=D0_EVENING,
        study_id=sid,
        forecasts=[
            forecast_input("S1", D0, "base", 0.6, capture_receipt_ref="cap-ok"),
            forecast_input("S2", D0, "base", 0.6, capture_receipt_ref="cap-bad", pit_grade="strict"),
            forecast_input("S3", D0, "base", 0.6, pit_grade="strict"),
        ],
        pit_verifier=verifier,
    )
    grades = {f["case"]["entity_id"]: f["pit_grade"] for f in result.accepted}
    assert grades == {"S1": "strict", "S2": "unverified", "S3": "unverified"}
    unverified_refs = [g for g in result.gaps if g.code == "unverified_pit"]
    assert len(unverified_refs) == 2 and all("strict" in (g.detail or "") for g in unverified_refs)


# --------------------------------------------------------------------------- #
# 结算
# --------------------------------------------------------------------------- #
def test_due_missing_and_invalid_are_gaps_not_failures(tmp_path):
    repo, protocol = frozen(tmp_path)
    sid = protocol["study_id"]
    register_forecasts(owner=OWNER, repository=repo, now=D0_EVENING, study_id=sid, forecasts=two_arm_inputs(D0, ("S1", "S2", "S3")))
    due = CAL[FS + HORIZON]
    after_due = sh(due, 18)
    source = DictOutcomeSource(
        calendar=CAL,
        watermark=CAL[-1],
        rows={
            ("sector", "S2", D0, HORIZON): {**settled_row(D0, 1.0, cal=CAL), "metric_value": math.nan},
            ("sector", "S3", D0, HORIZON): {"status": "pending", "metric_value": None, "computed_at": None},
        },
    )
    result = settle_outcomes(owner=OWNER, repository=repo, now=after_due, study_id=sid, outcome_source=source)
    assert not result.refused and not result.settled
    assert len(result.missing) == 4  # S1 无行 ×2 臂 + S3 源仍 pending ×2 臂
    assert len(result.invalid) == 2 and all(o["reason"] == "non_finite_metric" and o["value"] is None for o in result.invalid)
    codes = {g.code for g in result.gaps}
    assert codes == {"outcome_missing"} and all(g.retryable for g in result.gaps)
    receipt = evaluate_study(owner=OWNER, repository=repo, now=after_due, study_id=sid)
    assert receipt["counts"]["missing"] == 4 and receipt["counts"]["invalid"] == 2
    assert receipt["empirical_status"] == "pending", "期末未到：只报缺口，不判失败"


def test_settlement_refuses_version_or_calendar_mismatch_without_writing(tmp_path):
    repo, protocol = frozen(tmp_path)
    sid = protocol["study_id"]
    register_forecasts(owner=OWNER, repository=repo, now=D0_EVENING, study_id=sid, forecasts=two_arm_inputs(D0))
    after_due = sh(CAL[FS + HORIZON], 18)
    wrong_version = DictOutcomeSource(calendar=CAL, watermark=CAL[-1], version_hashes={"label_version": "synthetic-v2"})
    result = settle_outcomes(owner=OWNER, repository=repo, now=after_due, study_id=sid, outcome_source=wrong_version)
    assert result.refused and result.gaps[0].code == "version_mismatch" and wrong_version.lookups == 0
    shifted = DictOutcomeSource(calendar=[d for d in CAL if d != CAL[FS + 2]], watermark=CAL[-1])
    result2 = settle_outcomes(owner=OWNER, repository=repo, now=after_due, study_id=sid, outcome_source=shifted)
    assert result2.refused and "日历" in (result2.gaps[0].detail or "")
    assert not (repo.study_dir(sid) / "observations").exists()


def test_revised_outcome_is_appended_and_flagged_as_correction_replay(tmp_path):
    repo, protocol = frozen(tmp_path)
    sid = protocol["study_id"]
    register_forecasts(owner=OWNER, repository=repo, now=D0_EVENING, study_id=sid, forecasts=[forecast_input("S1", D0, "base", 0.6)])
    after_due = sh(CAL[FS + HORIZON], 18)
    up = DictOutcomeSource(calendar=CAL, watermark=CAL[-1], rows={("sector", "S1", D0, HORIZON): settled_row(D0, 2.0, cal=CAL)})
    first = settle_outcomes(owner=OWNER, repository=repo, now=after_due, study_id=sid, outcome_source=up)
    assert len(first.settled) == 1 and first.settled[0]["value"] == 1
    same = settle_outcomes(owner=OWNER, repository=repo, now=after_due + timedelta(hours=1), study_id=sid, outcome_source=up)
    assert same.unchanged and not same.settled
    down = DictOutcomeSource(calendar=CAL, watermark=CAL[-1], rows={("sector", "S1", D0, HORIZON): settled_row(D0, -1.0, cal=CAL)})
    second = settle_outcomes(owner=OWNER, repository=repo, now=after_due + timedelta(days=1), study_id=sid, outcome_source=down)
    assert len(second.revised) == 1 and second.revised[0]["value"] == 0
    fid = repo.list_forecasts(sid)[0]["id"]
    assert [o["value"] for o in repo.list_observations(sid, fid)] == [1, 0], "旧结论保留，新观察追加"
    receipt = evaluate_study(owner=OWNER, repository=repo, now=after_due + timedelta(days=1), study_id=sid)
    assert receipt["correction_replay"] is True


# --------------------------------------------------------------------------- #
# 完整前向流程 → 收据 → 曝光判定
# --------------------------------------------------------------------------- #
def run_forward(repo, protocol, *, n_days, entities=("S1", "S2"), origin="deterministic"):
    """逐日 D0 盘后登记：y 交替，候选臂每天都更接近真值（delta=+0.12）。"""
    rows = {}
    for i in range(n_days):
        day = CAL[FS + i]
        y = 1 if i % 2 == 0 else 0
        p_base, p_full = (0.6, 0.8) if y else (0.4, 0.2)
        result = register_forecasts(
            owner=OWNER,
            repository=repo,
            now=sh(day, 16, 30),
            study_id=protocol["study_id"],
            forecasts=two_arm_inputs(day, entities, p_base=p_base, p_full=p_full, origin=origin),
        )
        assert not result.rejected, result.to_dict()
        for e in entities:
            rows[("sector", e, day, HORIZON)] = settled_row(day, 2.0 if y else -1.0, cal=CAL)
    return rows


def test_full_forward_flow_reaches_supported_and_reuse_is_exposed(tmp_path):
    repo, study_a = frozen(tmp_path)
    # 另一个「换名」study：不同谱系、不同事件描述、不同宇宙 ref → case_id 全不同，但实体与日期相同
    study_b = freeze_study(
        owner=OWNER,
        repository=repo,
        now=FREEZE_NOW,
        protocol_input=forward_body(
            CAL,
            lineage_id="lineage-renamed",
            event_spec={"kind": "manual", "description": "同一批板块日，换个说法（synthetic）"},
            universe_ref="sector:published_snapshot@renamed",
        ),
    )
    assert study_b["study_id"] != study_a["study_id"]
    rows = run_forward(repo, study_a, n_days=55)
    run_forward(repo, study_b, n_days=55)
    last_due = CAL[FS + 54 + HORIZON]
    final_now = sh(last_due, 18) + timedelta(days=1)
    source = DictOutcomeSource(calendar=CAL, watermark=CAL[-1], rows=rows)
    settle_a = settle_outcomes(owner=OWNER, repository=repo, now=final_now, study_id=study_a["study_id"], outcome_source=source)
    assert len(settle_a.settled) == 55 * 4 and not settle_a.gaps
    settle_outcomes(owner=OWNER, repository=repo, now=final_now, study_id=study_b["study_id"], outcome_source=source)

    receipt = evaluate_study(owner=OWNER, repository=repo, now=final_now, study_id=study_a["study_id"])
    assert receipt["confirmatory_test_run"] is True and receipt["eligible"] is True
    assert receipt["empirical_status"] == "supported"
    primary = receipt["comparison_readouts"][0]
    assert primary["n_dates"] == 55 and primary["wins"] == 55 and primary["ties"] == 0
    assert primary["mean_brier_difference_descriptive"] == pytest.approx(0.12)
    assert primary["independent"]["verdict"] == "supported" and primary["dependence"]["verdict"] == "supported"
    assert primary["dependence"]["n_blocks"] == 11 and primary["dependence"]["n_events"] == 55
    assert primary["coverage"]["base"] == {"answered": 110, "total_cases": 110}
    assert receipt["calibration"]["full"]["n_settled"] == 110 and receipt["calibration"]["full"]["buckets"][4]["sufficient"] is True
    assert receipt["mode"] == "forward" and receipt["decision_eligible"] is False
    receipt_path = repo.receipts_dir(study_a["study_id"]) / f"{receipt['id']}.json"
    assert receipt_path.is_file()

    # 同 study 重评 = 同意图：同收据 id，曝光台账不多一条
    n_exposures = len(repo.list_exposures())
    again = evaluate_study(owner=OWNER, repository=repo, now=final_now + timedelta(hours=1), study_id=study_a["study_id"])
    assert again["id"] == receipt["id"] and len(repo.list_exposures()) == n_exposures

    # 读收据：先记曝光再返回
    shown = read_receipt(owner=OWNER, repository=repo, now=final_now + timedelta(hours=2), study_id=study_a["study_id"], actor="workbench.ui")
    assert shown["id"] == receipt["id"]
    assert len(repo.list_exposures()) == n_exposures + 1
    assert repo.list_exposures()[-1]["stage"] == "read_receipt"

    # 换名 study 复用同一批底层结果 → holdout_exposed，不 eligible，只描述
    receipt_b = evaluate_study(owner=OWNER, repository=repo, now=final_now + timedelta(hours=3), study_id=study_b["study_id"])
    assert receipt_b["eligible"] is False and "holdout_exposed" in receipt_b["eligibility_reasons"]
    assert receipt_b["empirical_status"] == "descriptive"
    primary_b = receipt_b["comparison_readouts"][0]
    # 数字照报（描述），但不得升级为声明：verdict 置空，verdict_if_eligible 只作参考
    assert primary_b["holdout_exposed_pairs"] == 110 and primary_b["n_pairs"] == 110
    assert primary_b["mean_brier_difference_descriptive"] == pytest.approx(0.12)
    assert primary_b["verdict"] is None and primary_b["verdict_if_eligible"] == "supported"
    assert receipt_b["excluded_counts"]["holdout_exposed"] == 110
    exposed_gap = next(g for g in receipt_b["pending_gaps"] if g["code"] == "holdout_exposed")
    assert len(exposed_gap["object_refs"]) == 110


def test_unknown_external_exposure_makes_study_exploratory(tmp_path):
    repo, protocol = frozen(tmp_path)
    rows = run_forward(repo, protocol, n_days=3, entities=("S1",))
    day0 = CAL[FS]
    record_exposure(
        owner=OWNER,
        repository=repo,
        now=sh(day0, 20),
        operation_id="external-view-0001",
        lineage_id=None,
        study_id=None,
        framework_hash=None,
        window=None,
        case_manifest_hash=None,
        outcome_identities=[{"entity_type": "sector", "entity_id": "S1", "as_of": day0, "outcome_due": CAL[FS + HORIZON], "horizon": HORIZON}],
        stage="external",
        actor="unknown",
        reason="用户在旧入口看过 S1 的 D+5 收益",
    )
    final_now = sh(CAL[FS + 2 + HORIZON], 18)
    settle_outcomes(owner=OWNER, repository=repo, now=final_now, study_id=protocol["study_id"], outcome_source=DictOutcomeSource(calendar=CAL, watermark=CAL[-1], rows=rows))
    receipt = evaluate_study(owner=OWNER, repository=repo, now=final_now, study_id=protocol["study_id"])
    assert receipt["eligible"] is False and "holdout_exposed" in receipt["eligibility_reasons"]
    # 保守口径：同实体、结果区间相交即算已暴露。S1@D0 的 D+1..D+5 与 D1 / D2 的窗口相交 → 3 个 case 全部标记。
    assert receipt["excluded_counts"]["holdout_exposed"] == 3
    assert receipt["comparison_readouts"][0]["holdout_exposed_pairs"] == 3


def test_exposure_ledger_incomplete_and_isolation_and_human_pairs_block_eligibility(tmp_path):
    repo, protocol = frozen(tmp_path, analysis_policy={"exposure_ledger_complete": False})
    sid = protocol["study_id"]
    register_forecasts(
        owner=OWNER,
        repository=repo,
        now=D0_EVENING,
        study_id=sid,
        forecasts=[
            forecast_input("S1", D0, "base", 0.6, origin="human_manual", actor="me"),
            forecast_input("S1", D0, "full", 0.8, origin="human_manual", actor="me"),
            forecast_input("S2", D0, "base", 0.6, isolation_verified=False),
            forecast_input("S2", D0, "full", 0.8),
        ],
    )
    receipt = evaluate_study(owner=OWNER, repository=repo, now=D0_EVENING, study_id=sid)
    assert set(receipt["eligibility_reasons"]) >= {"exposure_unknown", "isolation_unverified"}
    codes = {g["code"] for g in receipt["pending_gaps"]}
    assert {"exposure_unknown", "isolation_unverified", "future_not_due", "unverified_pit"} <= codes


def test_descriptive_only_when_both_arms_are_human(tmp_path):
    repo, protocol = frozen(tmp_path)
    rows = run_forward(repo, protocol, n_days=2, entities=("S1",), origin="human_manual")
    final_now = sh(CAL[FS + 1 + HORIZON], 18)
    settle_outcomes(owner=OWNER, repository=repo, now=final_now, study_id=protocol["study_id"], outcome_source=DictOutcomeSource(calendar=CAL, watermark=CAL[-1], rows=rows))
    receipt = evaluate_study(owner=OWNER, repository=repo, now=final_now, study_id=protocol["study_id"])
    assert receipt["empirical_status"] == "pending", "evaluation_end 未到仍 pending"
    primary = receipt["comparison_readouts"][0]
    assert primary["descriptive_only"] is True and "descriptive_only" in receipt["eligibility_reasons"]


def test_record_exposure_is_idempotent_and_conflicts_on_reused_operation_id(tmp_path):
    repo = make_repo(tmp_path)
    ident = {"entity_type": "sector", "entity_id": "S1", "as_of": D0, "outcome_due": CAL[FS + HORIZON], "horizon": HORIZON}
    kwargs = dict(owner=OWNER, repository=repo, operation_id="practice-reveal-00042", lineage_id=None, study_id=None, framework_hash=None, window=None, case_manifest_hash=None, outcome_identities=[ident], stage="practice_reveal", actor="04.practice", reason="reveal answer")
    first = record_exposure(now=sh(D0, 20), **kwargs)
    retry = record_exposure(now=sh(D0, 21), **kwargs)
    assert retry == first and retry["accessed_at"] == first["accessed_at"]
    with pytest.raises(ConflictError):
        record_exposure(now=sh(D0, 21), **{**kwargs, "reason": "different intent"})
    assert len(repo.list_exposures()) == 1
    with pytest.raises(ContractError):
        record_exposure(now=sh(D0, 21), **{**kwargs, "operation_id": "short"})


def test_cross_owner_and_naive_clock_are_rejected(tmp_path):
    repo, protocol = frozen(tmp_path)
    with pytest.raises(OwnerMismatch):
        register_forecasts(owner="mallory", repository=repo, now=D0_EVENING, study_id=protocol["study_id"], forecasts=[])
    with pytest.raises(ContractError, match="tz-aware"):
        evaluate_study(owner=OWNER, repository=repo, now=D0_EVENING.replace(tzinfo=None), study_id=protocol["study_id"])
    with pytest.raises(ContractError, match="可信时钟"):
        evaluate_study(owner=OWNER, repository=repo, now="2026-09-14T08:30:00+00:00", study_id=protocol["study_id"])


def test_historical_llm_probabilities_never_enter_a_forward_study(tmp_path):
    repo, protocol = frozen(tmp_path)
    with pytest.raises(ContractError, match="不与前向混合"):
        forecasts_from_replay([], protocol=protocol, replay_source_hash="0" * 64)
    result = register_forecasts(
        owner=OWNER,
        repository=repo,
        now=D0_EVENING,
        study_id=protocol["study_id"],
        forecasts=[forecast_input("S1", D0, "base", 0.7, origin="historical_llm", probability_recipe_hash=None, model_id="m")],
    )
    assert result.rejected[0].reason == "mode_origin_mismatch"


def test_projection_hash_accepts_river_context_projection_and_field_projection_only(tmp_path):
    """§4.5：人工 / LLM 臂记河的 ContextProjection 哈希（cp:+16 hex）；规则臂记字段投影 sha256；其余拒收。"""
    from intelligence.services.river_projection import HASH_PREFIX

    repo, protocol = frozen(tmp_path)
    sid = protocol["study_id"]
    river_hash = HASH_PREFIX + "0123456789abcdef"
    ok = register_forecasts(
        owner=OWNER,
        repository=repo,
        now=D0_EVENING,
        study_id=sid,
        forecasts=[
            forecast_input("S1", D0, "base", 0.6, origin="human_manual", projection_hash=river_hash, input_refs={"present_tracks": "market,sector"}),
            forecast_input("S2", D0, "base", 0.6, projection_hash="a" * 64),
        ],
    )
    assert [f["projection_hash"] for f in ok.accepted] == [river_hash, "a" * 64] and not ok.rejected
    bad = register_forecasts(
        owner=OWNER,
        repository=repo,
        now=D0_EVENING,
        study_id=sid,
        forecasts=[
            forecast_input("S3", D0, "base", 0.6, projection_hash="cp:tooshort"),
            forecast_input("S4", D0, "base", 0.6, projection_hash="看了一眼盘面"),
        ],
    )
    assert [r.reason for r in bad.rejected] == ["invalid_projection_hash", "invalid_projection_hash"]


def test_read_receipt_returns_none_when_nothing_evaluated(tmp_path):
    repo, protocol = frozen(tmp_path)
    assert read_receipt(owner=OWNER, repository=repo, now=D0_EVENING, study_id=protocol["study_id"]) is None
    assert repo.list_exposures() == []


# --------------------------------------------------------------------------- #
# 返修回归（评审 RV1 / RV2 / RV3）
# --------------------------------------------------------------------------- #
def test_incremental_registration_keeps_pending_evaluate_instead_of_conflict(tmp_path):
    """RV1：逐日登记是正常使用路径，不是并发重占。

    D0 登记一对 → evaluate=pending；D1 再登记一对合法预测（期限都没到，已结算集合仍为空，
    但 case 集合变了）→ 第二次 evaluate 必须照常返回 pending 收据，不能抛 ConflictError。
    spec 03 §5「未来未到 / 块不足也能完整返回 pending/insufficient」。
    """
    repo, protocol = frozen(tmp_path)
    sid = protocol["study_id"]
    d1 = CAL[FS + 1]
    assert not register_forecasts(owner=OWNER, repository=repo, now=sh(D0, 17), study_id=sid, forecasts=two_arm_inputs(D0, ("S1",))).rejected
    first = evaluate_study(owner=OWNER, repository=repo, now=sh(D0, 17), study_id=sid)
    assert first["empirical_status"] == "pending"

    second_day = register_forecasts(owner=OWNER, repository=repo, now=sh(d1, 17), study_id=sid, forecasts=two_arm_inputs(d1, ("S1",)))
    assert len(second_day.accepted) == 2 and not second_day.rejected
    second = evaluate_study(owner=OWNER, repository=repo, now=sh(d1, 17), study_id=sid)
    assert second["empirical_status"] == "pending"
    assert second["counts"] == {"forecasts": 4, "cases": 2, "settled": 0, "pending": 4, "missing": 0, "invalid": 0}
    # 输入集合变了 = 新意图 → 新的 operation_id、新的曝光记录，而不是冲突
    assert second["exposure_receipt_ref"] != first["exposure_receipt_ref"]
    assert len(repo.list_exposures()) == 2


def test_evaluate_is_idempotent_for_identical_inputs_and_separates_actors(tmp_path):
    """RV1 配套：同输入重跑仍幂等复用同一条曝光；不同 actor 是不同访问，各自留痕不冲突。"""
    repo, protocol = frozen(tmp_path)
    sid = protocol["study_id"]
    register_forecasts(owner=OWNER, repository=repo, now=sh(D0, 17), study_id=sid, forecasts=two_arm_inputs(D0, ("S1",)))
    first = evaluate_study(owner=OWNER, repository=repo, now=sh(D0, 17), study_id=sid)
    retry = evaluate_study(owner=OWNER, repository=repo, now=sh(D0, 19), study_id=sid)
    assert retry["exposure_receipt_ref"] == first["exposure_receipt_ref"]
    exposures = repo.list_exposures()
    assert len(exposures) == 1 and exposures[0]["accessed_at"] == repo.list_exposures()[0]["accessed_at"]

    other_actor = evaluate_study(owner=OWNER, repository=repo, now=sh(D0, 19), study_id=sid, actor="06.workbench.read")
    assert other_actor["exposure_receipt_ref"] != first["exposure_receipt_ref"]
    assert len(repo.list_exposures()) == 2


def test_pit_receipt_later_than_forecast_cutoff_is_rejected(tmp_path):
    """RV2：PIT 收据的可知时刻晚于本次预测截止 → 拒收，不得升 strict。

    spec 03 §5「输入通过已有 PIT（当时可知）收据校验；晚于 cutoff 拒收」。
    收据晚于预测截止意味着捕获件里含预测截止之后的信息 = 前视偏差。
    """
    repo, protocol = frozen(tmp_path)
    sid = protocol["study_id"]
    d0_close = market_close(D0)
    verifier = FakePitVerifier(
        {
            "cap-later": {"verified": True, "pit_grade": "strict", "knowledge_cutoff": utc_iso(market_close(CAL[FS + 1]))},
            "cap-after-now": {"verified": True, "pit_grade": "strict", "knowledge_cutoff": utc_iso(market_close(CAL[FS + 10]))},
            "cap-earlier": {"verified": True, "pit_grade": "strict", "knowledge_cutoff": utc_iso(d0_close - timedelta(hours=6))},
            "cap-equal": {"verified": True, "pit_grade": "strict", "knowledge_cutoff": utc_iso(d0_close)},
        }
    )
    result = register_forecasts(
        owner=OWNER,
        repository=repo,
        now=D0_EVENING,
        study_id=sid,
        forecasts=[
            forecast_input("S1", D0, "base", 0.6, capture_receipt_ref="cap-later"),
            forecast_input("S2", D0, "base", 0.6, capture_receipt_ref="cap-after-now"),
            forecast_input("S3", D0, "base", 0.6, capture_receipt_ref="cap-earlier"),
            forecast_input("S4", D0, "full", 0.6, capture_receipt_ref="cap-equal"),
        ],
        pit_verifier=verifier,
    )
    assert [r.reason for r in result.rejected] == ["pit_receipt_after_forecast_cutoff"] * 2
    assert [r.index for r in result.rejected] == [0, 1]
    # 早于 / 等于本次截止的收据是正常事前证据，照常升 strict
    assert {f["case"]["entity_id"]: f["pit_grade"] for f in result.accepted} == {"S3": "strict", "S4": "strict"}
    assert not [f for f in repo.list_forecasts(sid) if f["case"]["entity_id"] in ("S1", "S2")]


def test_cumulative_calibration_is_sealed_until_evaluation_end(tmp_path):
    """RV3：期末未到时 calibration 也要封存累计评分，不能绕过 comparison 的封存门。

    spec 03 §7「evaluation_end 到达才作一次确认检验，此前只报 pending 数 / 单项，累计评分封存」。
    """
    repo, protocol = frozen(tmp_path)
    sid = protocol["study_id"]
    rows = run_forward(repo, protocol, n_days=2, entities=("S1",))
    mid_now = sh(CAL[FS + 1 + HORIZON], 18)
    settle_outcomes(owner=OWNER, repository=repo, now=mid_now, study_id=sid, outcome_source=DictOutcomeSource(calendar=CAL, watermark=CAL[-1], rows=rows))
    receipt = evaluate_study(owner=OWNER, repository=repo, now=mid_now, study_id=sid)

    assert receipt["empirical_status"] == "pending" and receipt["evaluation_end_reached"] is False
    assert receipt["confirmatory_test_run"] is False
    for arm, entry in receipt["calibration"].items():
        assert entry["n_settled"] == 2, arm  # 计数与单项照报
        assert entry["sealed"] is True and entry["sealed_reason"] == "sealed_until_evaluation_end", arm
        assert entry["mean_brier"] is None, arm
        for bucket in entry["buckets"]:
            assert bucket["mean_p"] is None and bucket["observed_rate"] is None, (arm, bucket["bucket"])
            assert bucket["reason"] == "sealed_until_evaluation_end", (arm, bucket["bucket"])


def test_calibration_opens_after_evaluation_end(tmp_path):
    """RV3 配套：期末到达且无未到期预测 → 原样输出累计 Brier 与桶，封存只在期末前生效。"""
    n_days = 55
    repo, protocol = frozen(tmp_path, n_forward=n_days)
    sid = protocol["study_id"]
    rows = run_forward(repo, protocol, n_days=n_days, entities=("S1",))
    final_now = sh(CAL[FS + n_days - 1 + HORIZON], 18)
    settle_outcomes(owner=OWNER, repository=repo, now=final_now, study_id=sid, outcome_source=DictOutcomeSource(calendar=CAL, watermark=CAL[-1], rows=rows))
    receipt = evaluate_study(owner=OWNER, repository=repo, now=final_now, study_id=sid)

    assert receipt["evaluation_end_reached"] is True and receipt["confirmatory_test_run"] is True
    base = receipt["calibration"]["base"]
    assert base["sealed"] is False and base["sealed_reason"] is None
    assert base["n_settled"] == n_days and base["mean_brier"] == pytest.approx(0.16)
    assert any(b["mean_p"] is not None and b["observed_rate"] is not None for b in base["buckets"])
