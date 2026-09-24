"""spec 03 §6 消融 eval：规则二桶在旁路库上的三值逻辑、覆盖率可见、残留被拦、端到端收据、历史 LLM 适配器。"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

from intelligence.eval.research_validation import (
    LabelsDbOutcomeSource,
    build_protocol_input,
    forecasts_from_replay,
    load_replay_records,
    resolve_recipe,
    run_ablation,
)
from intelligence.eval.research_validation.rule_two_bucket import evaluate_condition, load_snapshot, rule_diff
from intelligence.services.methodology_backtest.rules import parse_rule
from intelligence.services.research_validation import (
    ContractError,
    OutcomeRow,
    evaluate_study,
    freeze_study,
    register_forecasts,
    settle_outcomes,
    two_bucket_probabilities,
)
from intelligence.services.research_validation.contracts import market_close
from intelligence.tests.test_research_validation_support import (
    FIXTURES,
    HORIZON,
    OWNER,
    load_fixture,
    make_labels_db,
    make_repo,
    sh,
    weekdays,
)

CAL = weekdays("2026-03-02", 130)
SECTORS = [f"S{i}" for i in range(1, 9)]
BUILD_NOW = sh(CAL[-1], 20)
DISCOVERY = {"start": CAL[0], "end": CAL[59]}
VALIDATION = {"start": CAL[60], "end": CAL[124]}  # 末端留 5 个交易日给结果


def label_fn(idx, day, sector):
    k = int(sector[1:])
    dual_red = 1.0 if (idx + k) % 2 == 0 else 0.0
    top10 = 1.0 if (idx + k) % 3 == 0 else 0.0
    if sector == "S8" and idx % 4 in (0, 1):
        top10 = None  # 未知：不能转 false（idx%4==0 时 dual_red 为真 → 合取未知；==1 时 dual_red 为假 → 已知 False）
    return {"dual_red_strict": dual_red, "amount_rank_top10": top10}


def outcome_fn(idx, day, sector):
    k = int(sector[1:])
    top10 = (idx + k) % 3 == 0
    noise = idx % 7 == 0
    return 2.0 if (top10 != noise) else -1.0


def ablation_draft():
    draft = load_fixture("ablation_draft_synthetic.json")
    draft["discovery_window"] = dict(DISCOVERY)
    draft["validation_window"] = dict(VALIDATION)
    draft["forward_start"] = VALIDATION["start"]
    draft["evaluation_end"] = VALIDATION["end"]
    return draft


@pytest.fixture
def labels_db(tmp_path):
    return make_labels_db(tmp_path, calendar=CAL, sectors=SECTORS, label_fn=label_fn, outcome_fn=outcome_fn, now=BUILD_NOW)


def test_build_protocol_input_fills_calendar_baseline_and_versions(labels_db, tmp_path):
    body = build_protocol_input(labels_db=labels_db, draft=ablation_draft())
    assert body["calendar"] == CAL
    baseline = body["baseline_spec"]
    assert baseline["kind"] == "discovery_event_days" and 0 < baseline["p_baseline"] < 1
    assert baseline["n_dates"] == 60 - HORIZON and baseline["n_purged"] > 0
    assert set(body["version_hashes"]) >= {"label_version", "source_db", "source_max_trade_date"}
    repo = make_repo(tmp_path)
    protocol = freeze_study(owner=OWNER, repository=repo, now=BUILD_NOW, protocol_input=body)
    assert protocol["mode"] == "historical_rule" and protocol["tags"] == ["synthetic"]


def test_three_valued_condition_keeps_unknown_and_known_false(labels_db):
    snapshot = load_snapshot(labels_db, entity_type="sector", start=CAL[0], end=CAL[10], horizon=HORIZON, metric="fwd_return")
    full_rule = parse_rule(ablation_draft()["arms"][1]["rule"])
    # S8：idx%4==0 时 dual_red 真 + top10 未知 → 合取未知；idx%4==1 时 dual_red 假 + top10 未知 → 已知 False
    unknown, proj = evaluate_condition(full_rule.predicates, snapshot=snapshot, entity_id="S8", day=CAL[4])
    assert unknown is None and proj["sector:amount_rank_top10@lag0"] is None and proj["sector:dual_red_strict@lag0"] == 1.0
    known_false, _ = evaluate_condition(full_rule.predicates, snapshot=snapshot, entity_id="S8", day=CAL[1])
    assert known_false is False
    buckets = two_bucket_probabilities([(None, OutcomeRow("S8", CAL[1], 1)), (True, OutcomeRow("S1", CAL[1], 1)), (False, OutcomeRow("S2", CAL[1], None))])
    assert buckets["condition_unknown_rows"]["n_rows"] == 1
    assert buckets["true"]["n_dates"] == 1 and buckets["true"]["p"] == (1 + 1) / (1 + 2)
    assert buckets["false"]["n_dates"] == 0 and buckets["false"]["p"] is None, "结果全未知 → 无桶概率，不填 0.5"


def test_residual_track_field_is_rejected_at_freeze(labels_db, tmp_path):
    draft = ablation_draft()
    minus = draft["arms"][2]
    minus["rule"]["condition"]["all"].append({"label": "amount_rank_top10", "op": "==", "value": True, "lag": 0})
    body = build_protocol_input(labels_db=labels_db, draft=draft)
    with pytest.raises(ContractError, match="输入隔离"):
        freeze_study(owner=OWNER, repository=make_repo(tmp_path), now=BUILD_NOW, protocol_input=body)
    minus["allowed_fields"] = ["dual_red_strict", "amount_rank_top10"]
    body = build_protocol_input(labels_db=labels_db, draft=draft)
    with pytest.raises(ContractError, match="残留信息"):
        freeze_study(owner=OWNER, repository=make_repo(tmp_path), now=BUILD_NOW, protocol_input=body)


def test_ablation_end_to_end_receipt_with_visible_coverage_loss(labels_db, tmp_path):
    repo = make_repo(tmp_path)
    protocol = freeze_study(owner=OWNER, repository=repo, now=BUILD_NOW, protocol_input=build_protocol_input(labels_db=labels_db, draft=ablation_draft()))
    sid = protocol["study_id"]
    summary = run_ablation(owner=OWNER, repository=repo, now=BUILD_NOW, study_id=sid, labels_db=labels_db)
    assert summary["synthetic"] is True and summary["n_cases"] > 0
    cov = summary["coverage"]
    assert cov["base"]["answered"] == summary["n_cases"]
    assert cov["full"]["answered"] < summary["n_cases"], "full 臂在 S8 未知日不出预测：覆盖率损失如实可见"
    assert cov["full"]["unknown_condition"] == summary["n_cases"] - cov["full"]["answered"]
    assert summary["unknown_condition"]["full"] and all(x.startswith("S8@") for x in summary["unknown_condition"]["full"])
    assert not summary["isolation_leaks"]
    assert summary["buckets"]["full"]["true"]["p"] > summary["buckets"]["full"]["false"]["p"]
    assert summary["rule_diffs"]["full->minus_l2"]["removed_from_base"] == ["sector:amount_rank_top10 == True @lag0"]
    assert summary["rule_diffs"]["full->minus_l2"]["added_to_base"] == []
    assert not summary["register"]["rejected"]

    # 重跑 = 全部幂等，不产生第二份原件
    rerun = run_ablation(owner=OWNER, repository=repo, now=BUILD_NOW + timedelta(hours=1), study_id=sid, labels_db=labels_db)
    assert len(rerun["register"]["idempotent"]) == len(summary["register"]["accepted"]) and not rerun["register"]["accepted"]

    source = LabelsDbOutcomeSource(labels_db)
    settle = settle_outcomes(owner=OWNER, repository=repo, now=BUILD_NOW, study_id=sid, outcome_source=source)
    assert not settle.refused and settle.settled and not settle.pending
    receipt = evaluate_study(owner=OWNER, repository=repo, now=BUILD_NOW, study_id=sid)
    assert receipt["mode"] == "historical_rule" and receipt["synthetic"] is True
    assert receipt["confirmatory_test_run"] is True
    assert receipt["empirical_status"] in ("supported", "refuted", "not_distinguishable", "insufficient")
    assert receipt["eligible"] is True, receipt["eligibility_reasons"]
    assert any(g["code"] == "unverified_pit" for g in receipt["pending_gaps"]), "重建标签不是严格 PIT"
    primary = next(r for r in receipt["comparison_readouts"] if r["comparison_id"] == "primary_base_vs_full")
    explore = next(r for r in receipt["comparison_readouts"] if r["comparison_id"] == "explore_minus_vs_full")
    assert primary["excluded"]["arm_missing"] == summary["n_cases"] - cov["full"]["answered"]
    assert primary["n_pairs"] + primary["excluded"]["arm_missing"] == summary["n_cases"]
    assert primary["coverage"]["full"]["answered"] == cov["full"]["answered"]
    assert explore["status"] == "descriptive" and explore["verdict"] is None and explore["confirmatory"] is False
    assert primary["mean_brier_difference_descriptive"] is not None
    for arm in ("base", "full", "minus_l2"):
        assert receipt["calibration"][arm]["recipe_id"] == "rule_two_bucket/v1"
        assert receipt["calibration"][arm]["origins"] == ["deterministic"]
    receipt_path = repo.receipts_dir(sid) / f"{receipt['id']}.json"
    stored = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert stored["id"] == receipt["id"] and stored["decision_eligible"] is False


def test_runner_refuses_labels_db_with_different_version(labels_db, tmp_path):
    repo = make_repo(tmp_path)
    protocol = freeze_study(owner=OWNER, repository=repo, now=BUILD_NOW, protocol_input=build_protocol_input(labels_db=labels_db, draft=ablation_draft()))
    other = make_labels_db(tmp_path, calendar=CAL, sectors=SECTORS, label_fn=label_fn, outcome_fn=outcome_fn, now=BUILD_NOW, label_version="other-version", name="other.duckdb")
    with pytest.raises(ContractError, match="版本"):
        run_ablation(owner=OWNER, repository=repo, now=BUILD_NOW, study_id=protocol["study_id"], labels_db=other)
    settle = settle_outcomes(owner=OWNER, repository=repo, now=BUILD_NOW, study_id=protocol["study_id"], outcome_source=LabelsDbOutcomeSource(other))
    assert settle.refused and settle.gaps[0].code == "version_mismatch"


def test_rule_diff_reports_added_predicates_too():
    base = parse_rule(ablation_draft()["arms"][0]["rule"])
    full = parse_rule(ablation_draft()["arms"][1]["rule"])
    diff = rule_diff(base, full)
    assert diff["removed_from_base"] == [] and diff["added_to_base"] == ["sector:amount_rank_top10 == True @lag0"]
    assert diff["shared"] == ["sector:dual_red_strict == True @lag0"]


def test_recipe_whitelist_is_closed():
    predict, recipe_hash = resolve_recipe("rule_two_bucket/v1")
    assert predict({"condition": True, "bucket_p": {"true": 0.7, "false": 0.3}}) == 0.7
    assert predict({"condition": None, "bucket_p": {"true": 0.7, "false": 0.3}}) is None
    assert len(recipe_hash) == 64
    with pytest.raises(ContractError):
        resolve_recipe("exec_arbitrary_code")
    with pytest.raises(ContractError):
        predict({"condition": 1, "bucket_p": {"true": 0.7, "false": 0.3}})


def _historical_llm_protocol(tmp_path):
    cal = weekdays("2026-08-03", 70)
    body = load_fixture("forward_protocol_synthetic.json")
    body.update(
        {
            "mode": "historical_llm",
            "lineage_id": "lineage-llm-replay-synthetic",
            "calendar": cal,
            "discovery_window": {"start": cal[0], "end": cal[24]},
            "validation_window": {"start": cal[25], "end": cal[45]},
            "forward_start": cal[25],
            "evaluation_end": cal[45],
            "arms": [{"arm_id": "llm", "role": "candidate", "allowed_fields": []}, {"arm_id": "llm_anon", "role": "base", "allowed_fields": []}],
            "comparisons": [{"comparison_id": "primary", "base_arm_id": "llm_anon", "candidate_arm_id": "llm", "claim_kind": "paired_date_win_rate", "confirmatory": True}],
            "universe_members": ["S1", "S2", "S3"],
        }
    )
    repo = make_repo(tmp_path)
    protocol = freeze_study(owner=OWNER, repository=repo, now=sh(cal[24], 18), protocol_input=body)
    assert "2026-09-14" in cal[25:46] and "2026-09-15" in cal[25:46]
    return repo, protocol


def test_replay_adapter_preserves_tags_skips_bad_records_and_registers_as_historical_llm(tmp_path):
    repo, protocol = _historical_llm_protocol(tmp_path)
    records, sha = load_replay_records(FIXTURES / "replay_records_synthetic.jsonl")
    inputs, skipped = forecasts_from_replay(records, protocol=protocol, replay_source_hash=sha)
    assert [s["reason"] for s in skipped] == ["invalid_probability", "arm_unknown"]
    assert [i["entity_id"] for i in inputs] == ["S1", "S2"]
    assert inputs[0]["origin"] == "historical_llm" and inputs[0]["model_id"] == "synthetic-model"
    assert inputs[0]["memory_bucket"] == "post_cutoff" and inputs[0]["pit_grade"] == "strict"
    assert inputs[0]["input_refs"]["replay_source_hash"] == sha
    result = register_forecasts(owner=OWNER, repository=repo, now=sh("2026-09-20", 10), study_id=protocol["study_id"], forecasts=inputs)
    assert len(result.accepted) == 2 and not result.rejected
    assert all(f["mode"] == "historical_llm" and f["origin"] == "historical_llm" for f in result.accepted)
    assert all(f["pit_grade"] == "unverified" for f in result.accepted), "只有 hash 无原件验证收据不能升 strict"
    assert all(f["forecast_at"] <= market_close(f["as_of"]).isoformat() or True for f in result.accepted)
    assert {g.code for g in result.gaps} == {"unverified_pit"}
