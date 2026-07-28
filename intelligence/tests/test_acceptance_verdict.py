from __future__ import annotations

import hashlib
import json
from pathlib import Path

from intelligence.eval.acceptance_verdict import (
    ExperienceState,
    OperationalState,
    VerdictState,
    compile_case_contract,
    evaluate_case,
    load_verdict_overlay,
)


ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = ROOT / "intelligence/eval/cases/acceptance_cases.json"
SNAPSHOT_DIR = ROOT / "intelligence/eval/cases/reference_snapshots"
CANONICAL_CASES_SHA256 = "a25c68253a92be536b94d2403ffa010b6cd15a20b7eea581450159cb6444a1c6"


def test_missing_run_is_not_run_on_operational_and_truth_axes() -> None:
    contract = compile_case_contract(
        {
            "id": "C1-future-date-no-data",
            "tier": "long_tail",
            "query": "2026-07-25 市场怎么样",
            "date": "2026-07-25",
            "expect_refusal": True,
            "pass_rule": "必须明确说无数据",
        },
        {"coverage": "structured"},
    )

    verdict = evaluate_case(contract, None)

    assert verdict.operational.state is OperationalState.NOT_RUN
    assert verdict.truth.state is VerdictState.NOT_RUN
    assert verdict.experience.state is ExperienceState.UNLABELED
    assert verdict.to_dict()["truth"]["state"] == "not_run"


def test_overlay_names_every_canonical_case_once() -> None:
    doc = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    overlay = load_verdict_overlay()

    assert set(overlay) == {case["id"] for case in doc["cases"]}
    assert len(overlay) == 28
    for entry in overlay.values():
        assert entry["coverage"] in {"structured", "semantic_required"}
        if entry["coverage"] == "semantic_required":
            assert entry.get("reason")


def test_all_cases_compile_without_mutating_frozen_assets() -> None:
    before = hashlib.sha256(CASES_PATH.read_bytes()).hexdigest()
    assert before == CANONICAL_CASES_SHA256
    snapshot_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in SNAPSHOT_DIR.glob("*.json")
    }
    doc = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    overlay = load_verdict_overlay()

    contracts = [
        compile_case_contract(case, overlay[case["id"]]) for case in doc["cases"]
    ]

    assert len(contracts) == 28
    assert {contract.case_id for contract in contracts} == set(overlay)
    assert all(not contract.diagnostics for contract in contracts)
    assert hashlib.sha256(CASES_PATH.read_bytes()).hexdigest() == before
    assert {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in SNAPSHOT_DIR.glob("*.json")
    } == snapshot_hashes


def test_unknown_case_field_is_visible_in_contract_diagnostics() -> None:
    contract = compile_case_contract(
        {
            "id": "X1",
            "tier": "long_tail",
            "query": "x",
            "pass_rule": "x",
            "mystery_gate": True,
        },
        {"coverage": "semantic_required", "reason": "manual"},
    )

    assert contract.diagnostics == ("unknown case fields: mystery_gate",)


def test_operational_state_does_not_decide_truth() -> None:
    contract = compile_case_contract(
        {
            "id": "C1",
            "tier": "long_tail",
            "query": "future",
            "expect_refusal": True,
            "pass_rule": "say no data",
        },
        {"coverage": "structured"},
    )
    blocked = evaluate_case(contract, {"turns": [], "blocked_reason": "preflight"})
    failed = evaluate_case(
        contract,
        {"turns": [{"status": "timeout", "error": "deadline"}]},
    )
    degraded = evaluate_case(
        contract,
        {
            "turns": [
                {
                    "status": "completed",
                    "answer": "没有可用数据",
                    "degrades": ["evidence gap"],
                }
            ]
        },
    )
    completed = evaluate_case(
        contract,
        {"turns": [{"status": "completed", "answer": "made up 42", "degrades": []}]},
    )

    assert blocked.operational.state is OperationalState.BLOCKED
    assert blocked.truth.state is VerdictState.UNJUDGEABLE
    assert failed.operational.state is OperationalState.FAILED
    assert failed.truth.state is VerdictState.UNJUDGEABLE
    assert degraded.operational.state is OperationalState.DEGRADED
    assert completed.operational.state is OperationalState.COMPLETED
    assert completed.truth.state is not VerdictState.PASS


def _completed(answer: str, **extra):
    turn = {"status": "completed", "answer": answer, "degrades": []}
    turn.update(extra)
    return {"turns": [turn]}


def _rule(verdict, rule_id: str):
    return next(rule for rule in verdict.truth.rules if rule.rule_id == rule_id)


def test_explicit_refusal_and_forbidden_text_are_deterministic() -> None:
    contract = compile_case_contract(
        {
            "id": "C1",
            "tier": "long_tail",
            "query": "future",
            "expect_refusal": True,
            "forbid_phrases": ["涨停家数为"],
            "pass_rule": "must explicitly say no data",
        },
        {
            "coverage": "structured",
            "required_any_phrases": ["无数据", "没有可用", "超出覆盖范围"],
        },
    )

    passed = evaluate_case(contract, _completed("该日没有可用的市场数据。"))
    vague = evaluate_case(contract, _completed("现有证据不足，暂不能可靠回答。"))
    fabricated = evaluate_case(
        contract,
        _completed("该日无数据，但预计涨停家数为 88 家。"),
    )

    assert passed.truth.state is VerdictState.PASS
    assert _rule(vague, "required_any_phrases").state is VerdictState.FAIL
    assert vague.truth.state is VerdictState.FAIL
    assert _rule(fabricated, "forbidden_phrases").state is VerdictState.FAIL


def test_numeric_and_literal_fact_rules_respect_tolerances() -> None:
    contract = compile_case_contract(
        {
            "id": "A1",
            "tier": "high_freq",
            "query": "market",
            "expect_facts": [
                {"field": "total_amount", "value": 21949.97, "tol_pct": 1.0},
                {"field": "amount_vs_yesterday_pct", "value": -17.27, "tol_abs": 0.5},
                {"field": "market_stage", "value": "反弹阶段"},
            ],
            "pass_rule": "facts",
        },
        {
            "coverage": "structured",
            "fact_aliases": {
                "total_amount": ["成交额"],
                "amount_vs_yesterday_pct": ["环比"],
                "market_stage": ["阶段"],
            },
        },
    )

    passed = evaluate_case(
        contract,
        _completed("成交额 21,950 亿元，环比 -17.3%，处于反弹阶段。"),
    )
    failed = evaluate_case(
        contract,
        _completed("成交额 18,000 亿元，环比 -12%，处于反弹阶段。"),
    )

    assert passed.truth.state is VerdictState.PASS
    assert _rule(failed, "fact:total_amount").state is VerdictState.FAIL
    assert _rule(failed, "fact:amount_vs_yesterday_pct").state is VerdictState.FAIL
    assert failed.truth.state is VerdictState.FAIL


def test_cutoff_uses_structured_citation_dates_and_prediction_context() -> None:
    contract = compile_case_contract(
        {
            "id": "C7",
            "tier": "long_tail",
            "query": "forecast",
            "date": "2026-07-21",
            "forbid_future_data": True,
            "pass_rule": "no future realized data",
        },
        {"coverage": "structured"},
    )
    clean = evaluate_case(
        contract,
        _completed(
            "7月22日大概率偏强震荡。",
            citations=[{"date": "2026-07-21"}],
        ),
    )
    leaked = evaluate_case(
        contract,
        _completed(
            "7月22日实际收跌 1.2%。",
            citations=[{"date": "2026-07-22"}],
        ),
    )
    missing = evaluate_case(contract, _completed("7月22日大概率偏强震荡。"))

    assert _rule(clean, "cutoff").state is VerdictState.PASS
    assert clean.truth.state is VerdictState.PASS
    assert _rule(leaked, "cutoff").state is VerdictState.FAIL
    assert leaked.truth.state is VerdictState.FAIL
    assert _rule(missing, "cutoff").state is VerdictState.UNJUDGEABLE
    assert missing.truth.state is VerdictState.UNJUDGEABLE


def test_citation_integrity_checks_only_minted_tags() -> None:
    contract = compile_case_contract(
        {
            "id": "C9",
            "tier": "long_tail",
            "query": "cause",
            "check_citation_registry": True,
            "pass_rule": "citations",
        },
        {"coverage": "structured"},
    )
    dangling = evaluate_case(
        contract,
        _completed(
            "原因见 [E1][W2]。",
            evidence=[{"label": "[E1] 市场证据", "status": "hit"}],
        ),
    )
    minted = evaluate_case(
        contract,
        _completed(
            "原因见 [E1][W2]。",
            evidence=[
                {"label": "[E1] 市场证据", "status": "hit"},
                {"label": "[W2] Wiki", "status": "hit"},
            ],
        ),
    )
    no_tags = evaluate_case(contract, _completed("现有证据不足。"))

    assert _rule(dangling, "citation_integrity").state is VerdictState.FAIL
    assert _rule(minted, "citation_integrity").state is VerdictState.PASS
    assert _rule(no_tags, "citation_integrity").state is VerdictState.PASS


def test_semantic_coverage_never_silently_passes() -> None:
    contract = compile_case_contract(
        {
            "id": "C9",
            "tier": "long_tail",
            "query": "cause",
            "check_citation_registry": True,
            "pass_rule": "must explain the cause and cite it",
        },
        {
            "coverage": "semantic_required",
            "reason": "citation validity does not establish causal quality",
        },
    )
    unjudged = evaluate_case(contract, _completed("没有引用标签。"))
    judged = evaluate_case(
        contract,
        _completed("给出完整因果链。"),
        observations={
            "truth_observations": {
                "pass_rule": {"state": "pass", "reason": "blind semantic review"}
            }
        },
    )

    assert _rule(unjudged, "pass_rule").state is VerdictState.UNJUDGEABLE
    assert unjudged.truth.state is VerdictState.UNJUDGEABLE
    assert _rule(judged, "pass_rule").state is VerdictState.PASS
    assert judged.truth.state is VerdictState.PASS


def test_external_observations_cannot_erase_hard_failure_or_mix_experience() -> None:
    contract = compile_case_contract(
        {
            "id": "C9",
            "tier": "long_tail",
            "query": "cause",
            "forbid_phrases": ["编造数字"],
            "check_citation_registry": True,
            "pass_rule": "must explain cause",
        },
        {
            "coverage": "semantic_required",
            "reason": "needs semantic observation",
        },
    )
    verdict = evaluate_case(
        contract,
        _completed("编造数字，但没有引用标签。"),
        observations={
            "truth_observations": {
                "pass_rule": {"state": "pass", "reason": "semantic pass"}
            },
            "experience_verdict": {
                "eligible": True,
                "label": "workbench",
                "reason": "blind preference",
            },
        },
    )

    assert _rule(verdict, "pass_rule").state is VerdictState.PASS
    assert _rule(verdict, "forbidden_phrases").state is VerdictState.FAIL
    assert verdict.truth.state is VerdictState.FAIL
    assert verdict.experience.state is ExperienceState.LABELED
    assert verdict.experience.label == "workbench"


def test_inconsistency_falsifiability_and_cross_turn_checks_are_conservative() -> None:
    inconsistency = compile_case_contract(
        {
            "id": "C5",
            "tier": "long_tail",
            "query": "dirty",
            "require_flag_inconsistency": True,
            "pass_rule": "flag inconsistency",
        },
        {"coverage": "structured"},
    )
    assert evaluate_case(
        inconsistency, _completed("两日数据互相矛盾，疑似重复。")
    ).truth.state is VerdictState.PASS
    assert evaluate_case(
        inconsistency, _completed("两日数据完全正常。")
    ).truth.state is VerdictState.FAIL

    falsifiable = compile_case_contract(
        {
            "id": "A2",
            "tier": "high_freq",
            "query": "tomorrow",
            "require_falsifiable": True,
            "pass_rule": "condition",
        },
        {"coverage": "structured"},
    )
    assert evaluate_case(
        falsifiable, _completed("若指数跌破 3,500 点，则判断失效。")
    ).truth.state is VerdictState.PASS
    assert evaluate_case(
        falsifiable, _completed("明天继续看涨。")
    ).truth.state is VerdictState.FAIL

    multi_turn = compile_case_contract(
        {
            "id": "C10",
            "tier": "long_tail",
            "query": "set",
            "check_cross_turn_consistency": True,
            "pass_rule": "consistent",
        },
        {"coverage": "structured"},
    )
    lost = evaluate_case(
        multi_turn,
        {
            "turns": [
                {"status": "completed", "answer": "电网设备。", "degrades": []},
                {"status": "completed", "answer": "你指的是哪个板块？", "degrades": []},
            ]
        },
    )
    plausible = evaluate_case(
        multi_turn,
        {
            "turns": [
                {"status": "completed", "answer": "电网设备。", "degrades": []},
                {"status": "completed", "answer": "仍是电网设备，共 1 个。", "degrades": []},
            ]
        },
    )

    assert _rule(lost, "cross_turn_consistency").state is VerdictState.FAIL
    assert lost.truth.state is VerdictState.FAIL
    assert _rule(plausible, "cross_turn_consistency").state is VerdictState.UNJUDGEABLE
    assert plausible.truth.state is VerdictState.UNJUDGEABLE


def test_historical_run_calibration_is_honest_and_reproducible() -> None:
    cases_doc = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in cases_doc["cases"]}
    overlay = load_verdict_overlay()
    run = json.loads(
        (ROOT / "intelligence/eval/runs/20260727T032229Z.json").read_text(
            encoding="utf-8"
        )
    )
    runs = {item["case_id"]: item for item in run["cases"]}

    verdicts = {
        case_id: evaluate_case(
            compile_case_contract(cases[case_id], overlay[case_id]),
            runs[case_id],
        )
        for case_id in (
            "C1-future-date-no-data",
            "C7-temporal-leakage",
            "C9-citation-integrity",
            "C10-multi-turn-consistency",
        )
    }

    assert verdicts["C1-future-date-no-data"].truth.state is VerdictState.UNJUDGEABLE
    assert _rule(
        verdicts["C1-future-date-no-data"], "refusal"
    ).state is VerdictState.PASS
    assert _rule(
        verdicts["C1-future-date-no-data"], "forbidden_phrases"
    ).state is VerdictState.PASS
    assert verdicts["C7-temporal-leakage"].truth.state is VerdictState.PASS
    assert verdicts["C9-citation-integrity"].truth.state is VerdictState.UNJUDGEABLE
    assert _rule(
        verdicts["C9-citation-integrity"], "citation_integrity"
    ).state is VerdictState.PASS
    assert _rule(
        verdicts["C9-citation-integrity"], "pass_rule"
    ).state is VerdictState.UNJUDGEABLE
    assert verdicts["C10-multi-turn-consistency"].truth.state is VerdictState.FAIL
